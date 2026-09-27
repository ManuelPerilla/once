"""Authenticated controls enqueue work; they never call a sports provider."""

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token

from .models import SyncBudget, SyncHeartbeat, SyncHistory, SyncIssue, SyncJob, SyncScope
from .service import (
    SyncError,
    control,
    enqueue,
    finish,
    history,
    now,
    scoped,
    set_global_mode,
)

router = APIRouter(
    prefix="/automation", tags=["Automatización"], dependencies=[Depends(verificar_token)]
)
Mode = Literal["paused", "observe", "automatic"]
Kind = Literal[
    "catalog",
    "fixtures",
    "detail",
    "details_batch",
    "media",
    "history",
    "standings",
    "standings_batch",
    "discovery",
    "archive",
]


class ModeInput(BaseModel):
    mode: Mode


class ScopeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: Literal["api-football", "wikidata", "openfootball"]
    kind: Kind
    selector: dict = Field(default_factory=dict)
    mode: Mode = "paused"
    interval_seconds: int = Field(default=86400, ge=30, le=2592000)
    daily_limit: int = Field(default=100, ge=1, le=100000)
    minute_limit: int = Field(default=10, ge=1, le=1000)

    @field_validator("provider", mode="before")
    @classmethod
    def canonical_provider(cls, value):
        return "api-football" if value == "api_football" else value

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Escribe un nombre para el ámbito.")
        return value.strip()

    @field_validator("selector")
    @classmethod
    def safe_selector(cls, value):
        import json

        if len(json.dumps(value)) > 8000:
            raise ValueError("La configuración del ámbito es demasiado grande.")
        forbidden = {"token", "api_key", "apikey", "password", "secret", "authorization", "headers"}

        def check(item):
            if isinstance(item, dict):
                for key, nested in item.items():
                    if key.lower() in forbidden:
                        raise ValueError(
                            "Las credenciales se configuran en el servidor, nunca en el ámbito."
                        )
                    check(nested)
            elif isinstance(item, list):
                for nested in item:
                    check(nested)

        check(value)
        return value


class ScopePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    selector: dict | None = None
    mode: Mode | None = None
    interval_seconds: int | None = Field(default=None, ge=30, le=2592000)
    daily_limit: int | None = Field(default=None, ge=1, le=100000)
    minute_limit: int | None = Field(default=None, ge=1, le=1000)


class Resolution(BaseModel):
    note: str = Field(min_length=3, max_length=1000)

    @field_validator("note")
    @classmethod
    def meaningful_note(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Escribe el motivo de la resolución.")
        return value.strip()


def validate_adapter(config):
    from src.providers.automation import validate_scope_config

    try:
        selector = validate_scope_config(config.provider, config.kind, config.selector)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if selector is not None:
        config.selector = selector


def need_scope(session, scope_id):
    try:
        return scoped(session, scope_id)
    except SyncError as exc:
        raise HTTPException(404, str(exc)) from exc


def count_by(session, model, attribute, condition=None):
    statement = select(attribute, func.count()).group_by(attribute)
    if condition is not None:
        statement = statement.where(condition)
    return dict(session.exec(statement).all())


@router.get("/overview")
def overview(session: Session = Depends(get_session)):
    settings = control(session)
    instant = now(session)
    counts = count_by(session, SyncJob, SyncJob.status)
    running = count_by(session, SyncJob, SyncJob.scope_id, SyncJob.status == "running")
    issues = count_by(session, SyncIssue, SyncIssue.scope_id, SyncIssue.status == "open")
    scopes = []
    for row in session.exec(select(SyncScope).order_by(SyncScope.created_at)).all():
        paused = settings.mode == "paused" or row.mode == "paused"
        active = running.get(row.id, 0)
        status = (
            "pausing"
            if paused and active
            else "paused"
            if paused
            else "updating"
            if active
            else "attention"
            if issues.get(row.id)
            else "waiting"
            if row.last_checked_at is None
            else "delayed"
            if row.last_checked_at + timedelta(seconds=max(300, row.interval_seconds * 2)) < instant
            else "checked"
        )
        scopes.append(
            {
                **row.model_dump(),
                "status": status,
                "active_jobs": active,
                "open_issues": issues.get(row.id, 0),
            }
        )
    beat = session.get(SyncHeartbeat, "worker")
    budgets = []
    for row in session.exec(select(SyncBudget)).all():
        data = row.model_dump()
        if row.day != instant.strftime("%Y-%m-%d"):
            data["day_used"] = 0
        if row.minute != instant.strftime("%Y-%m-%dT%H:%M"):
            data["minute_used"] = 0
        budgets.append(data)
    result = {
        "global": settings.model_dump(),
        "scopes": scopes,
        "worker": {
            "last_seen_at": beat.last_seen_at if beat else None,
            "healthy": bool(beat and beat.last_seen_at > instant - timedelta(seconds=180)),
        },
        "jobs": {key: counts.get(key, 0) for key in ["queued", "running", "waiting", "failed"]},
        "budget": budgets,
    }
    session.commit()
    return result


@router.put("/global")
def global_mode(
    payload: ModeInput, actor=Depends(verificar_token), session: Session = Depends(get_session)
):
    settings = set_global_mode(session, payload.mode, actor)
    session.commit()
    session.refresh(settings)
    return settings


@router.post("/scopes", status_code=201)
def create_scope(
    payload: ScopeCreate, actor=Depends(verificar_token), session: Session = Depends(get_session)
):
    validate_adapter(payload)
    control(session, lock=True)
    if session.scalar(select(func.count()).select_from(SyncScope)) >= 50:
        raise HTTPException(
            409, "El piloto admite hasta 50 ámbitos. Revisa los existentes antes de añadir otro."
        )
    scope = SyncScope(**payload.model_dump())
    session.add(scope)
    history(session, actor, "scope_created", scope.id, config=payload.model_dump())
    session.commit()
    session.refresh(scope)
    return scope


@router.patch("/scopes/{scope_id}")
def update_scope(
    scope_id: str,
    payload: ScopePatch,
    request: Request,
    actor=Depends(verificar_token),
    session: Session = Depends(get_session),
):
    control(session, lock=True)
    scope = need_scope(session, scope_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if set(changes) - {"mode"} and "manage_sources" not in request.state.permissions:
        raise HTTPException(403, "Tu cuenta puede pausar ámbitos, pero no cambiar sus fuentes.")
    # Reuse creation validation for merged configuration, including selector secrets.
    try:
        config = ScopeCreate.model_validate({**scope.model_dump(), **changes})
    except ValidationError as exc:
        raise HTTPException(422, "La configuración del ámbito no es válida.") from exc
    validate_adapter(config)
    before = {key: getattr(scope, key) for key in changes}
    for key in changes:
        setattr(scope, key, getattr(config, key))
    if changes and before != {key: getattr(scope, key) for key in changes}:
        scope.epoch += 1
        scope.updated_at = now(session)
        scope.next_run_at = scope.updated_at
        session.add(scope)
        for job in session.exec(
            select(SyncJob).where(
                SyncJob.scope_id == scope.id,
                SyncJob.status.in_(["queued", "waiting"]),
            )
        ):
            finish(job, "cancelled", scope.updated_at)
            session.add(job)
        history(session, actor, "scope_updated", scope.id, before=before, after=changes)
    session.commit()
    session.refresh(scope)
    return scope


@router.post("/scopes/{scope_id}/run", status_code=202)
def run_scope(
    scope_id: str, actor=Depends(verificar_token), session: Session = Depends(get_session)
):
    control(session, lock=True)
    scope = need_scope(session, scope_id)
    try:
        job = enqueue(session, scope, actor=actor)
    except SyncError as exc:
        raise HTTPException(409, str(exc)) from exc
    session.commit()
    session.refresh(job)
    return job


def page(session, model, limit, offset, scope_id=None, status=None):
    filters = []
    if scope_id:
        filters.append(model.scope_id == scope_id)
    if status and hasattr(model, "status"):
        filters.append(model.status == status)
    total = session.scalar(select(func.count()).select_from(model).where(*filters))
    order = model.last_seen_at if model is SyncIssue else model.created_at
    items = session.exec(
        select(model).where(*filters).order_by(order.desc(), model.id).offset(offset).limit(limit)
    ).all()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/jobs")
def jobs(
    scope_id: str | None = None,
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    return page(session, SyncJob, limit, offset, scope_id, status)


@router.get("/issues")
def issues(
    scope_id: str | None = None,
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    return page(session, SyncIssue, limit, offset, scope_id, status)


@router.get("/history")
def activity(
    scope_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    return page(session, SyncHistory, limit, offset, scope_id)


@router.post("/issues/{issue_id}/resolve")
def resolve(
    issue_id: str,
    payload: Resolution,
    actor=Depends(verificar_token),
    session: Session = Depends(get_session),
):
    control(session, lock=True)
    row = session.get(SyncIssue, issue_id)
    if row is None:
        raise HTTPException(404, "No se encontró la incidencia.")
    row.status, row.resolved_at, row.resolution = "resolved", now(session), payload.note.strip()
    session.add(row)
    history(session, actor, "issue_resolved", row.scope_id, issue_id=row.id, note=row.resolution)
    session.commit()
    return {"ok": True}
