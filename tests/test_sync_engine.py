"""Fault-oriented tests for the durable worker, without real provider requests."""

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from src import database
from src.sync.handlers import FetchResult
from src.sync.models import (
    SyncBudget,
    SyncControl,
    SyncHistory,
    SyncIssue,
    SyncJob,
    SyncNotification,
    SyncObservation,
    SyncScope,
    utcnow,
)
from src.sync.service import (
    QuotaExhausted,
    StaleWork,
    SyncEngine,
    control,
    enqueue,
    set_global_mode,
)


@pytest.fixture
def engine(client):
    return SyncEngine(database.engine)


def configured(engine, mode="automatic", **kwargs):
    with engine.transaction() as session:
        set_global_mode(session, "automatic", "tester")
        scope = SyncScope(name="Colombia", provider="test", kind="fixtures", mode=mode, **kwargs)
        session.add(scope)
        session.flush()
        job = enqueue(session, scope)
        return scope.id, job.id


class Handler:
    def fetch(self, scope, context):
        context.reserve_request()
        return FetchResult({"fixture": 1})

    def apply(self, session, scope, payload, context):
        existing = session.exec(
            select(SyncHistory).where(SyncHistory.action == "domain_change")
        ).first()
        if existing:
            return {"changed": 0}
        session.add(SyncHistory(actor=context.actor, action="domain_change", detail=payload))
        return {"changed": 1, "topics": ["matches"]}


def rows(engine, model):
    with Session(engine.engine) as session:
        return session.exec(select(model)).all()


def test_starts_paused_and_restart_preserves_it(engine):
    engine.tick("worker")
    assert rows(engine, SyncControl)[0].mode == "paused"
    assert SyncEngine(engine.engine).claim("restarted") is None


def test_pending_polls_coalesce(engine):
    scope_id, job_id = configured(engine)
    with engine.transaction() as session:
        duplicate = enqueue(session, session.get(SyncScope, scope_id))
        assert duplicate.id == job_id
    engine.tick("worker")
    assert len(rows(engine, SyncJob)) == 1


def test_pause_during_http_prevents_any_publication(engine):
    scope_id, _ = configured(engine)

    class PauseDuringFetch(Handler):
        def fetch(self, scope, context):
            context.reserve_request()
            with engine.transaction() as session:
                set_global_mode(session, "paused", "operator")
            return FetchResult({"fixture": 1})

    engine.registry = {("test", "fixtures"): PauseDuringFetch()}
    assert engine.run_one("worker")
    assert rows(engine, SyncJob)[0].status == "cancelled"
    assert not rows(engine, SyncObservation)
    assert not rows(engine, SyncNotification)
    assert not [item for item in rows(engine, SyncHistory) if item.action == "domain_change"]


def test_scope_epoch_change_fences_old_work(engine):
    scope_id, _ = configured(engine)
    context = engine.claim("worker")
    with engine.transaction() as session:
        control(session, lock=True)
        scope = session.get(SyncScope, scope_id)
        scope.epoch += 1
        session.add(scope)
    with pytest.raises(StaleWork):
        engine.publish(context, FetchResult({"ok": True}), Handler())
    assert not rows(engine, SyncObservation)


def test_observe_saves_evidence_without_domain_changes(engine):
    configured(engine, mode="observe")
    engine.registry = {("test", "fixtures"): Handler()}
    assert engine.run_one("worker")
    assert rows(engine, SyncJob)[0].status == "observed"
    assert len(rows(engine, SyncObservation)) == 1
    assert not rows(engine, SyncNotification)


def test_global_observe_overrides_automatic_scope(engine):
    scope_id, _ = configured(engine)
    with engine.transaction() as session:
        set_global_mode(session, "observe", "operator")
        enqueue(session, session.get(SyncScope, scope_id))
    engine.registry = {("test", "fixtures"): Handler()}
    engine.run_one("worker")
    assert not rows(engine, SyncNotification)
    assert any(job.status == "observed" for job in rows(engine, SyncJob))


def test_repeated_payload_deduplicates_observation_and_domain_effect(engine):
    scope_id, _ = configured(engine)
    engine.registry = {("test", "fixtures"): Handler()}
    engine.run_one("worker")
    with engine.transaction() as session:
        enqueue(session, session.get(SyncScope, scope_id))
    engine.run_one("worker")
    assert len(rows(engine, SyncObservation)) == 1
    assert len(rows(engine, SyncNotification)) == 1
    assert len([row for row in rows(engine, SyncHistory) if row.action == "domain_change"]) == 1


def test_incomplete_payload_never_applies(engine):
    configured(engine)
    context = engine.claim("worker")
    engine.publish(context, FetchResult({}, complete=False), Handler())
    assert not rows(engine, SyncNotification)
    assert rows(engine, SyncIssue)[0].code == "incomplete"
    assert not rows(engine, SyncObservation)[0].complete


def test_crash_and_reclaim_rejects_previous_lease_token(engine):
    _, job_id = configured(engine)
    old = engine.claim("worker-old")
    with engine.transaction() as session:
        job = session.get(SyncJob, job_id)
        job.lease_until = utcnow() - timedelta(seconds=1)
        session.add(job)
    engine.tick("worker-new")
    current = engine.claim("worker-new")
    assert current.token > old.token
    with pytest.raises(StaleWork):
        engine.publish(old, FetchResult({"old": True}), Handler())
    engine.publish(current, FetchResult({"current": True}), Handler())
    assert rows(engine, SyncJob)[0].status == "succeeded"


def test_quota_is_shared_by_scopes_and_survives_worker_restart(engine):
    configured(engine, daily_limit=1)
    first = engine.claim("worker")
    first.reserve_request()
    configured(engine, daily_limit=99)
    second = SyncEngine(engine.engine).claim("worker-2")
    with pytest.raises(QuotaExhausted):
        second.reserve_request()
    assert rows(engine, SyncBudget)[0].day_used == 1


def test_quota_wait_does_not_consume_retry_attempts(engine):
    configured(engine, daily_limit=1)
    context = engine.claim("worker")
    context.reserve_request()
    with pytest.raises(QuotaExhausted) as caught:
        context.reserve_request()
    engine.fail(context, caught.value)
    job = rows(engine, SyncJob)[0]
    assert job.status == "waiting" and job.attempts == 0
    assert job.due_at > utcnow()


def test_retry_after_and_remote_budget_never_refund_requests(engine):
    scope_id, _ = configured(engine, daily_limit=10, minute_limit=10)
    context = engine.claim("worker")
    context.reserve_request()
    context.report_quota(remaining_day=2, remaining_minute=1, retry_after=120)
    context.report_quota(remaining_day=10, remaining_minute=10)
    budget = rows(engine, SyncBudget)[0]
    assert budget.day_used == 8 and budget.minute_used == 9
    with pytest.raises(QuotaExhausted):
        context.reserve_request()


def test_publication_failure_rolls_back_domain_evidence_and_notification(engine):
    configured(engine)
    context = engine.claim("worker")

    class Broken(Handler):
        def apply(self, session, scope, payload, context):
            super().apply(session, scope, payload, context)
            session.flush()
            raise RuntimeError("intentional")

    with pytest.raises(RuntimeError):
        engine.publish(context, FetchResult({"ok": True}), Broken())
    assert not rows(engine, SyncObservation)
    assert not rows(engine, SyncNotification)
    assert not [row for row in rows(engine, SyncHistory) if row.action == "domain_change"]


def test_failure_is_bounded_and_does_not_store_untrusted_secrets(engine):
    scope_id, job_id = configured(engine)
    context = engine.claim("worker")
    engine.fail(context, RuntimeError("secret=do-not-store"))
    assert "secret" not in rows(engine, SyncJob)[0].error
    with engine.transaction() as session:
        job = session.get(SyncJob, job_id)
        job.attempts, job.due_at = job.max_attempts - 1, utcnow()
        session.add(job)
    engine.fail(engine.claim("worker"), RuntimeError("failed"))
    assert rows(engine, SyncJob)[0].status == "failed"
    assert rows(engine, SyncScope)[0].mode == "paused"
    assert rows(engine, SyncIssue)[0].status == "open"


def test_notification_cursor_assigned_after_commit_not_creation_order(engine):
    with engine.transaction() as session:
        newer = SyncNotification(topic="matches", created_at=utcnow())
        session.add(newer)
        newer_id = newer.id
    engine.deliver()
    with engine.transaction() as session:
        # Represents the earlier-started transaction that only committed later.
        older = SyncNotification(topic="catalog", created_at=utcnow() - timedelta(minutes=1))
        session.add(older)
        older_id = older.id
    engine.deliver()
    delivered = {row.id: row.sequence for row in rows(engine, SyncNotification)}
    assert delivered[newer_id] == 1 and delivered[older_id] == 2
    assert engine.deliver() == 0


def test_expired_lease_does_not_reserve_more_external_requests(engine):
    _, job_id = configured(engine)
    context = engine.claim("worker")
    with engine.transaction() as session:
        job = session.get(SyncJob, job_id)
        job.lease_until = utcnow() - timedelta(seconds=1)
        session.add(job)
    with pytest.raises(StaleWork):
        context.reserve_request()
    assert not rows(engine, SyncBudget)
