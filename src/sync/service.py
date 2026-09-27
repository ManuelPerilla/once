"""Small transactions serialize controls, leases and quota; HTTP stays outside."""

import hashlib
import json
import os
import random
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import partial

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session, select

from src.models import ProviderSnapshot

from .handlers import FetchResult, JobContext
from .models import (
    SyncBudget,
    SyncControl,
    SyncHeartbeat,
    SyncHistory,
    SyncIssue,
    SyncJob,
    SyncNotification,
    SyncObservation,
    SyncScope,
    utcnow,
)

MODES = {"paused", "observe", "automatic"}
ACTIVE = {"queued", "running", "waiting"}
LEASE_SECONDS = 300


class SyncError(Exception):
    pass


class StaleWork(SyncError):
    pass


class RetryableError(SyncError):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class PermanentError(SyncError):
    pass


class QuotaExhausted(RetryableError):
    pass


class PacingWait(QuotaExhausted):
    """A short wait before reservation, without consuming a request or holding a lock."""


def now(session):
    if session.bind.dialect.name == "postgresql":
        return session.scalar(select(func.clock_timestamp()))
    return utcnow()


def control(session, lock=False):
    if session.bind.dialect.name == "postgresql":
        statement = select(SyncControl).where(SyncControl.id == 1)
        if lock:
            statement = statement.with_for_update()
        existing = session.exec(statement.execution_options(populate_existing=True)).first()
        if existing is not None:
            return existing
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    session.execute(
        insert(SyncControl)
        .values(
            id=1,
            mode="paused",
            epoch=0,
            delivery_cursor=0,
            updated_at=utcnow(),
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    if lock and session.bind.dialect.name == "sqlite":
        # A write also gives SQLite the publication fence used by PostgreSQL row locks.
        session.execute(
            update(SyncControl).where(SyncControl.id == 1).values(epoch=SyncControl.epoch)
        )
    if session.bind.dialect.name == "postgresql" and lock:
        return session.exec(select(SyncControl).where(SyncControl.id == 1).with_for_update()).one()
    return session.get(SyncControl, 1, populate_existing=True)


def history(session, actor, action, scope_id=None, job_id=None, **detail):
    session.add(
        SyncHistory(actor=actor, action=action, scope_id=scope_id, job_id=job_id, detail=detail)
    )


def issue(session, scope_id, code, message, severity="warning"):
    row = session.exec(
        select(SyncIssue).where(
            SyncIssue.scope_id == scope_id,
            SyncIssue.code == code,
        )
    ).first()
    if row is None:
        row = SyncIssue(scope_id=scope_id, code=code, message=message[:1000], severity=severity)
    else:
        row.occurrences += 1
        row.last_seen_at = now(session)
        row.message = message[:1000]
        row.status = "open"
        row.resolved_at = None
        row.resolution = None
    session.add(row)
    return row


def scoped(session, scope_id):
    row = session.get(SyncScope, scope_id, populate_existing=True)
    if row is None:
        raise SyncError("El ámbito ya no existe.")
    return row


def finish(job, status, instant, result=None):
    job.status, job.active_key, job.owner = status, None, None
    job.lease_until, job.finished_at = None, instant
    if result is not None:
        job.result = result


def enqueue(session, scope, *, actor="service:scheduler"):
    settings = control(session, lock=True)
    if settings.mode == "paused" or scope.mode == "paused":
        raise SyncError("Activa la automatización y este ámbito antes de actualizar.")
    existing = session.exec(select(SyncJob).where(SyncJob.active_key == scope.id)).first()
    if existing and (existing.global_epoch, existing.scope_epoch) == (settings.epoch, scope.epoch):
        return existing
    if existing:
        finish(existing, "cancelled", now(session))
        session.add(existing)
        session.flush()
    job = SyncJob(
        scope_id=scope.id,
        active_key=scope.id,
        global_epoch=settings.epoch,
        scope_epoch=scope.epoch,
        mode="observe" if "observe" in {settings.mode, scope.mode} else "automatic",
    )
    session.add(job)
    history(session, actor, "queued", scope.id, job.id)
    return job


def set_global_mode(session, mode, actor):
    settings = control(session, lock=True)
    if mode != settings.mode:
        previous = settings.mode
        settings.mode, settings.epoch, settings.updated_at = mode, settings.epoch + 1, now(session)
        session.add(settings)
        history(session, actor, "global_mode", previous=previous, mode=mode)
        # Cancel queued polls now; running calls drain but cannot pass the changed fence.
        for job in session.exec(select(SyncJob).where(SyncJob.status.in_(["queued", "waiting"]))):
            finish(job, "cancelled", settings.updated_at)
            session.add(job)
        if mode != "paused":
            for scope in session.exec(select(SyncScope).where(SyncScope.mode != "paused")):
                scope.next_run_at = settings.updated_at
                session.add(scope)
    return settings


def _connection_snapshot(session, kind):
    return session.exec(
        select(ProviderSnapshot).where(
            ProviderSnapshot.provider == "api-football",
            ProviderSnapshot.entity_type == "connection",
            ProviderSnapshot.local_id == 1,
            ProviderSnapshot.kind == kind,
        )
    ).first()


def _positive_integer(value):
    return value if type(value) is int and value > 0 else None


def _checked_at(payload):
    try:
        instant = datetime.fromisoformat(payload.get("checked_at", ""))
        return instant.astimezone(UTC) if instant.tzinfo else None
    except (TypeError, ValueError):
        return None


def _api_fingerprint():
    credential = os.getenv("API_FOOTBALL_KEY")
    return hashlib.sha256(credential.encode()).hexdigest() if credential else None


def effective_api_limits(session):
    """A verified plan caps local budgets; it never raises their configured values."""
    snapshot = _connection_snapshot(session, "status")
    payload = snapshot.payload if snapshot else {}
    checked = _checked_at(payload)
    instant = now(session)
    if (
        payload.get("active") is not True
        or (
            payload.get("credential_fingerprint") is not None
            and payload["credential_fingerprint"] != _api_fingerprint()
        )
        or checked is None
        or not timedelta() <= instant - checked <= timedelta(days=1)
    ):
        return 100, 10
    return (
        _positive_integer(payload.get("requests_limit_day")) or 100,
        _positive_integer(payload.get("minute_limit")) or 10,
    )


def _remote_quota(session, instant):
    """Only counters and timestamps are persisted, never the account/status response."""
    snapshot = _connection_snapshot(session, "quota")
    if snapshot is None:
        snapshot = ProviderSnapshot(
            provider="api-football", entity_type="connection", local_id=1, kind="quota", payload={}
        )
    allowed = {
        "day",
        "minute",
        "pending_day",
        "pending_minute",
        "remaining_day",
        "remaining_minute",
        "limit_day",
        "limit_minute",
        "checked_at",
        "credential_fingerprint",
        "next_request_at",
    }
    payload = {key: value for key, value in snapshot.payload.items() if key in allowed}
    fingerprint = _api_fingerprint()
    if payload.get("credential_fingerprint") != fingerprint:
        # Remote capacity belongs to one account; local consumption survives rotation.
        payload = {}
    payload["credential_fingerprint"] = fingerprint
    for window, key in (("day", "%Y-%m-%d"), ("minute", "%Y-%m-%dT%H:%M")):
        current = instant.strftime(key)
        if payload.get(window) != current:
            payload[window] = current
            payload[f"pending_{window}"] = 0
            payload.pop(f"remaining_{window}", None)
    return snapshot, payload


def _save_remote_quota(session, snapshot, payload, instant):
    snapshot.payload, snapshot.fetched_at = payload, instant
    session.add(snapshot)


def budget_for(session, provider, scope):
    budget = session.get(SyncBudget, provider)
    if budget is None:
        budget = SyncBudget(provider=provider)
    limits = session.exec(
        select(SyncScope).where(SyncScope.provider == provider, SyncScope.mode != "paused")
    ).all()
    # A paused diagnostic scope still contributes its own deliberate local limit.
    limits = [*limits, scope]
    budget.day_limit = min(row.daily_limit for row in limits)
    budget.minute_limit = min(row.minute_limit for row in limits)
    instant = now(session)
    if provider == "api-football":
        day_limit, minute_limit = effective_api_limits(session)
        remote = _connection_snapshot(session, "quota")
        checked = _checked_at(remote.payload) if remote else None
        if (
            checked
            and remote.payload.get("credential_fingerprint") == _api_fingerprint()
            and timedelta() <= instant - checked <= timedelta(days=1)
        ):
            day_limit = min(
                day_limit, _positive_integer(remote.payload.get("limit_day")) or day_limit
            )
            minute_limit = min(
                minute_limit, _positive_integer(remote.payload.get("limit_minute")) or minute_limit
            )
        budget.day_limit = min(budget.day_limit, day_limit)
        budget.minute_limit = min(budget.minute_limit, minute_limit)
    day, minute = instant.strftime("%Y-%m-%d"), instant.strftime("%Y-%m-%dT%H:%M")
    if budget.day != day:
        budget.day, budget.day_used = day, 0
    if budget.minute != minute:
        budget.minute, budget.minute_used = minute, 0
    session.add(budget)
    return budget


def reserve_provider_request(session, provider, scope):
    """Reserve one request under the caller's SyncControl lock, including diagnostics."""
    instant = now(session)
    budget = budget_for(session, provider, scope)
    midnight = (instant + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if budget.blocked_until and budget.blocked_until > instant:
        raise QuotaExhausted(
            "La fuente indicó una pausa temporal.", (budget.blocked_until - instant).total_seconds()
        )
    if budget.day_used >= budget.day_limit:
        raise QuotaExhausted(
            "Se agotó el presupuesto diario de la fuente.", (midnight - instant).total_seconds()
        )
    if budget.minute_used >= budget.minute_limit:
        raise QuotaExhausted("Se alcanzó el límite por minuto.", 61 - instant.second)
    if provider == "api-football":
        snapshot, payload = _remote_quota(session, instant)
        next_request = _checked_at({"checked_at": payload.get("next_request_at")})
        if next_request and next_request > instant:
            raise PacingWait(
                "Espaciamos las consultas para respetar el ritmo de la fuente.",
                (next_request - instant).total_seconds(),
            )
        for window, delay in (
            ("day", (midnight - instant).total_seconds()),
            ("minute", 61 - instant.second),
        ):
            remaining = payload.get(f"remaining_{window}")
            if remaining is not None and remaining <= 0:
                raise QuotaExhausted("La cuenta de la fuente agotó su cuota disponible.", delay)
        for window in ("day", "minute"):
            key = f"remaining_{window}"
            if key in payload:
                payload[key] -= 1
            payload[f"pending_{window}"] = payload.get(f"pending_{window}", 0) + 1
        payload["next_request_at"] = (
            instant + timedelta(seconds=max(0.2, 60 / budget.minute_limit) + 0.1)
        ).isoformat()
        _save_remote_quota(session, snapshot, payload, instant)
    budget.day_used += 1
    budget.minute_used += 1
    session.add(budget)
    return budget


def fenced(session, context):
    settings = control(session, lock=True)
    scope = scoped(session, context.scope_id)
    job = session.get(SyncJob, context.job_id, populate_existing=True)
    instant = now(session)
    if (
        job is None
        or job.status != "running"
        or job.token != context.token
        or job.owner != context.owner
        or job.lease_until is None
        or job.lease_until <= instant
        or settings.mode == "paused"
        or scope.mode == "paused"
        or settings.epoch != job.global_epoch
        or scope.epoch != job.scope_epoch
    ):
        raise StaleWork("La pausa, configuración o reserva del trabajo cambió.")
    return scope, job, instant


class SyncEngine:
    def __init__(self, engine, registry=None):
        self.engine = engine
        self.registry = registry if registry is not None else {}

    @contextmanager
    def transaction(self):
        with Session(self.engine, expire_on_commit=False) as session:
            with session.begin():
                yield session

    def tick(self, owner):
        """Recover expired leases and coalesce one due poll per scope."""
        with self.transaction() as session:
            settings = control(session, lock=True)
            instant = now(session)
            beat = session.get(SyncHeartbeat, "worker")
            if (
                beat is None
                or beat.owner != owner
                or beat.last_seen_at < instant - timedelta(seconds=30)
            ):
                beat = beat or SyncHeartbeat(owner=owner)
                beat.owner, beat.last_seen_at = owner, instant
                session.add(beat)
            for job in session.exec(
                select(SyncJob).where(
                    SyncJob.status == "running",
                    SyncJob.lease_until <= instant,
                )
            ):
                scope = scoped(session, job.scope_id)
                if (
                    settings.mode == "paused"
                    or scope.mode == "paused"
                    or settings.epoch != job.global_epoch
                    or scope.epoch != job.scope_epoch
                ):
                    finish(job, "cancelled", instant)
                elif job.attempts >= job.max_attempts:
                    finish(job, "failed", instant)
                    issue(
                        session,
                        scope.id,
                        "lease_exhausted",
                        "El trabajo perdió su reserva varias veces.",
                    )
                else:
                    job.status, job.owner, job.lease_until = "queued", None, None
                    job.due_at = instant
                session.add(job)
            if settings.mode == "paused":
                return
            scopes = session.exec(
                select(SyncScope)
                .where(
                    SyncScope.mode != "paused",
                    SyncScope.next_run_at <= instant,
                )
                .order_by(SyncScope.next_run_at)
                .limit(50)
            ).all()
            for scope in scopes:
                enqueue(session, scope)
                scope.next_run_at = instant + timedelta(seconds=scope.interval_seconds)
                session.add(scope)

    def claim(self, owner):
        with self.transaction() as session:
            settings = control(session, lock=True)
            if settings.mode == "paused":
                return None
            instant = now(session)
            jobs = session.exec(
                select(SyncJob)
                .where(
                    SyncJob.status.in_(["queued", "waiting"]),
                    SyncJob.due_at <= instant,
                )
                .order_by(SyncJob.due_at, SyncJob.id)
                .limit(50)
                .with_for_update(skip_locked=True)
            ).all()
            for job in jobs:
                scope = scoped(session, job.scope_id)
                if (
                    scope.mode == "paused"
                    or job.global_epoch != settings.epoch
                    or job.scope_epoch != scope.epoch
                ):
                    finish(job, "cancelled", instant)
                    session.add(job)
                    continue
                job.status, job.owner = "running", owner
                job.token, job.attempts = job.token + 1, job.attempts + 1
                job.lease_until = instant + timedelta(seconds=LEASE_SECONDS)
                job.started_at, job.error = instant, None
                session.add(job)
                return JobContext(
                    job.id,
                    scope.id,
                    job.token,
                    owner,
                    partial(self.reserve, job.id, scope.id, job.token, owner),
                    partial(self.report_quota, scope.id),
                    observed_at=instant,
                )
        return None

    def reserve(self, job_id, scope_id, token, owner, provider=None):
        context = JobContext(job_id, scope_id, token, owner, lambda *_: None, lambda **_: None)
        deferred = None
        with self.transaction() as session:
            scope, job, instant = fenced(session, context)
            try:
                reserve_provider_request(session, provider or scope.provider, scope)
            except QuotaExhausted as exc:
                deferred = exc
            else:
                job.lease_until = instant + timedelta(seconds=LEASE_SECONDS)
                session.add(job)
                beat = session.get(SyncHeartbeat, "worker")
                if (
                    beat
                    and beat.owner == owner
                    and beat.last_seen_at < instant - timedelta(seconds=30)
                ):
                    beat.last_seen_at = instant
                    session.add(beat)
        if deferred:
            raise deferred

    def report_quota(
        self,
        scope_id,
        provider=None,
        remaining_day=None,
        remaining_minute=None,
        retry_after=None,
        limit_day=None,
        limit_minute=None,
        finalize_request=True,
    ):
        with self.transaction() as session:
            control(session, lock=True)
            scope = scoped(session, scope_id)
            provider = provider or scope.provider
            instant = now(session)
            budget = budget_for(session, provider, scope)
            if provider == "api-football":
                snapshot, payload = _remote_quota(session, instant)
                for window, remaining, limit in (
                    ("day", remaining_day, limit_day),
                    ("minute", remaining_minute, limit_minute),
                ):
                    pending = max(0, payload.get(f"pending_{window}", 0) - int(finalize_request))
                    payload[f"pending_{window}"] = pending
                    if _positive_integer(limit):
                        # The verified plan and local caps still bound any reported upgrade.
                        payload[f"limit_{window}"] = limit
                    if type(remaining) is int and remaining >= 0:
                        key = f"remaining_{window}"
                        # In-flight reservations may not be reflected by the remote header yet.
                        available = max(0, remaining - pending)
                        payload[key] = min(payload.get(key, available), available)
                payload["checked_at"] = instant.isoformat()
                _save_remote_quota(session, snapshot, payload, instant)
                budget = budget_for(session, provider, scope)
            else:
                for remaining, limit, used in (
                    (remaining_day, "day_limit", "day_used"),
                    (remaining_minute, "minute_limit", "minute_used"),
                ):
                    if remaining is not None:
                        # Never refund local requests based on potentially delayed headers.
                        setattr(
                            budget,
                            used,
                            max(
                                getattr(budget, used),
                                getattr(budget, limit) - max(0, int(remaining)),
                            ),
                        )
            if retry_after is not None:
                blocked = instant + timedelta(seconds=max(1, min(float(retry_after), 86400)))
                budget.blocked_until = max(budget.blocked_until or blocked, blocked)
            session.add(budget)

    def publish(self, context, fetched, handler):
        encoded = json.dumps(
            fetched.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        if len(encoded.encode("utf-8")) > 8 * 1024 * 1024:
            raise PermanentError("La respuesta excede el límite de 8 MiB; reduce el ámbito.")
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self.transaction() as session:
            scope, job, instant = fenced(session, context)
            observation = session.exec(
                select(SyncObservation).where(
                    SyncObservation.scope_id == scope.id,
                    SyncObservation.digest == digest,
                )
            ).first()
            if observation is None:
                observation = SyncObservation(
                    scope_id=scope.id,
                    digest=digest,
                    payload=fetched.payload,
                    complete=fetched.complete,
                    received_at=instant,
                    last_seen_at=instant,
                )
            else:
                observation.last_seen_at = instant
            session.add(observation)
            job.observation_id = observation.id
            scope.last_checked_at = instant
            if not fetched.complete:
                issue(
                    session,
                    scope.id,
                    "incomplete",
                    "La fuente devolvió información incompleta. Se conservaron los datos publicados.",
                )
                result, status = {"changed": 0, "complete": False}, "observed"
            elif job.mode == "observe":
                result, status = (
                    {"changed": 0, "complete": True, "observation_id": observation.id},
                    "observed",
                )
            else:
                result, status = (
                    handler.apply(session, scope, fetched.payload, context) or {},
                    "succeeded",
                )
                # The global lock remains held throughout apply and commit.
                if result.get("changed", 0):
                    scope.last_changed_at = instant
                    for topic in sorted(set(result.get("topics") or ["catalog"])):
                        if topic in {"catalog", "matches", "standings", "media", "history"}:
                            session.add(
                                SyncNotification(
                                    topic=topic,
                                    scope_id=scope.id,
                                    payload={"changed": result["changed"]},
                                )
                            )
            if now(session) >= job.lease_until:
                raise StaleWork(
                    "El lote tardó demasiado; se descartó para conservar una publicación coherente."
                )
            cadence = getattr(handler, "next_interval", None)
            if fetched.complete and cadence is not None:
                interval = max(
                    30, min(2592000, int(cadence(session, scope, fetched.payload, instant)))
                )
                scope.next_run_at = instant + timedelta(seconds=interval)
                result["next_interval_seconds"] = interval
            finish(job, status, instant, result)
            session.add(job)
            session.add(scope)
            history(
                session,
                context.actor,
                status,
                scope.id,
                job.id,
                changed=result.get("changed", 0),
                observation_id=observation.id,
            )
            return result

    def fail(self, context, exc):
        # Never persist raw provider exceptions: URLs, payloads or credentials can occur there.
        safe = (
            str(exc)[:500]
            if isinstance(exc, SyncError)
            else "Falló la actualización. Revisa la fuente y vuelve a intentarlo."
        )
        with self.transaction() as session:
            settings = control(session, lock=True)
            job = session.get(SyncJob, context.job_id)
            if job is None or job.token != context.token or job.owner != context.owner:
                return
            scope, instant = scoped(session, context.scope_id), now(session)
            stale = (
                isinstance(exc, StaleWork)
                or settings.mode == "paused"
                or scope.mode == "paused"
                or job.global_epoch != settings.epoch
                or job.scope_epoch != scope.epoch
            )
            if stale:
                finish(job, "cancelled", instant)
            elif isinstance(exc, QuotaExhausted):
                job.status, job.owner, job.lease_until = "waiting", None, None
                job.attempts = max(0, job.attempts - 1)
                job.due_at = instant + timedelta(seconds=max(1, exc.retry_after or 60))
            elif isinstance(exc, PermanentError) or job.attempts >= job.max_attempts:
                finish(job, "failed", instant)
                issue(session, scope.id, "source_error", safe, "error")
                # A failed scope circuit stays paused until an operator fixes it.
                scope.mode, scope.epoch = "paused", scope.epoch + 1
                session.add(scope)
            else:
                delay = max(
                    getattr(exc, "retry_after", None) or 0,
                    min(3600, 15 * 2**job.attempts + random.uniform(0, 10)),
                )
                job.status, job.owner, job.lease_until = "waiting", None, None
                job.due_at = instant + timedelta(seconds=delay)
            job.error = safe
            session.add(job)
            history(session, context.actor, job.status, scope.id, job.id, reason=safe)

    def run_one(self, owner):
        context = self.claim(owner)
        if context is None:
            return False
        try:
            with Session(self.engine) as session:
                scope = session.get(SyncScope, context.scope_id)
                session.expunge(scope)
            handler = self.registry.get((scope.provider, scope.kind))
            if handler is None:
                raise PermanentError(
                    "Esta combinación de fuente y tarea no tiene un adaptador disponible."
                )
            fetched = handler.fetch(scope, context)
            if not isinstance(fetched, FetchResult) or not isinstance(fetched.payload, dict):
                raise PermanentError("El adaptador devolvió una respuesta incompatible.")
            self.publish(context, fetched, handler)
        except Exception as exc:
            self.fail(context, exc)
        return True

    def deliver(self, limit=200):
        """Only committed notifications receive their monotonically ordered cursor."""
        with Session(self.engine) as probe:
            pending = probe.exec(
                select(SyncNotification.id).where(SyncNotification.sequence.is_(None)).limit(1)
            ).first()
            if pending is None:
                return 0
        with self.transaction() as session:
            settings = control(session, lock=True)
            pending = session.exec(
                select(SyncNotification)
                .where(SyncNotification.sequence.is_(None))
                .order_by(SyncNotification.created_at, SyncNotification.id)
                .limit(limit)
            ).all()
            for notification in pending:
                settings.delivery_cursor += 1
                notification.sequence = settings.delivery_cursor
                notification.delivered_at = now(session)
                session.add(notification)
            session.add(settings)
            return len(pending)
