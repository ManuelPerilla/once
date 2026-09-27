"""Human-readable audit and protected-correction endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.audit.service import (
    EDITABLE_FIELDS,
    AuditConflict,
    correct_field,
    record_change,
    release_field,
)
from src.football.entities import ENTITY_MODELS
from src.models import AuditChange, DataIssue, EntityRevision, FieldState

router = APIRouter(prefix="/audit", dependencies=[Depends(verificar_token)])


class Correction(BaseModel):
    value: Any
    reason: str = Field(min_length=3, max_length=1000)
    expected_version: int = Field(ge=0)


class Release(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    expected_version: int = Field(ge=0)


class Resolution(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


def get_entity(session, entity_type, entity_id):
    model = ENTITY_MODELS.get(entity_type)
    entity = session.get(model, entity_id) if model else None
    if entity is None:
        raise HTTPException(404, "Ficha no encontrada")
    return entity


@router.get("/entities/{entity_type}/{entity_id}")
def entity_audit(entity_type: str, entity_id: int, session: Session = Depends(get_session)):
    entity = get_entity(session, entity_type, entity_id)
    revision = session.get(EntityRevision, (entity_type, entity_id))
    states = {
        state.field: state
        for state in session.exec(
            select(FieldState).where(
                FieldState.entity_type == entity_type, FieldState.entity_id == entity_id
            )
        ).all()
    }
    history = session.exec(
        select(AuditChange)
        .where(AuditChange.entity_type == entity_type, AuditChange.entity_id == entity_id)
        .order_by(AuditChange.id.desc())
        .limit(50)
    ).all()
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "label": getattr(entity, "nombre", f"Partido {entity_id}"),
        "version": revision.version if revision else 0,
        "fields": [
            {
                "name": field,
                "value": getattr(entity, field),
                "protected": bool(states.get(field) and states[field].protected),
                "source": states[field].source if field in states else None,
                "observed_at": states[field].observed_at if field in states else None,
            }
            for field in sorted(EDITABLE_FIELDS.get(entity_type, set()))
        ],
        "history": history,
    }


def _notify(session, entity_type, entity_id):
    from src.sync.models import SyncNotification

    session.add(
        SyncNotification(
            topic="matches"
            if entity_type in {"match", "event", "lineup", "statistics"}
            else "catalog",
            payload={"entity_type": entity_type, "entity_id": entity_id},
        )
    )


@router.patch("/entities/{entity_type}/{entity_id}/{field}")
def correct(
    entity_type: str,
    entity_id: int,
    field: str,
    data: Correction,
    session: Session = Depends(get_session),
    actor: str = Depends(verificar_token),
):
    entity = get_entity(session, entity_type, entity_id)
    try:
        version = correct_field(
            session,
            entity_type,
            entity,
            field,
            data.value,
            actor=actor,
            reason=data.reason,
            expected_version=data.expected_version,
        )
        if entity_type == "match" and entity.temporada_id:
            from src.football.projections import rebuild_season_standings

            rebuild_season_standings(session, entity.temporada_id)
        _notify(session, entity_type, entity_id)
        session.commit()
    except AuditConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True, "version": version}


@router.post("/entities/{entity_type}/{entity_id}/{field}/release")
def release(
    entity_type: str,
    entity_id: int,
    field: str,
    data: Release,
    session: Session = Depends(get_session),
    actor: str = Depends(verificar_token),
):
    entity = get_entity(session, entity_type, entity_id)
    try:
        version = release_field(
            session,
            entity_type,
            entity,
            field,
            actor=actor,
            reason=data.reason,
            expected_version=data.expected_version,
        )
        session.commit()
    except AuditConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True, "version": version}


def _page(session, model, filters, page, page_size):
    total = session.exec(select(func.count()).select_from(model).where(*filters)).one()
    items = session.exec(
        select(model)
        .where(*filters)
        .order_by(model.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/changes")
def changes(
    entity_type: str | None = None,
    entity_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    filters = []
    if entity_type:
        filters.append(AuditChange.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AuditChange.entity_id == entity_id)
    return _page(session, AuditChange, filters, page, page_size)


@router.get("/issues")
def issues(
    status: str = "open",
    entity_type: str | None = None,
    entity_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_session),
):
    filters = []
    if status != "all":
        filters.append(DataIssue.status == status)
    if entity_type:
        filters.append(DataIssue.entity_type == entity_type)
    if entity_id is not None:
        filters.append(DataIssue.entity_id == entity_id)
    return _page(session, DataIssue, filters, page, page_size)


@router.post("/issues/{issue_id}/resolve")
def resolve_issue(
    issue_id: int,
    data: Resolution,
    session: Session = Depends(get_session),
    actor: str = Depends(verificar_token),
):
    from src.models import utcnow

    issue = session.exec(
        select(DataIssue).where(DataIssue.id == issue_id).with_for_update()
    ).first()
    if issue is None:
        raise HTTPException(404, "Incidencia no encontrada")
    if issue.status != "resolved":
        issue.status, issue.updated_at = "resolved", utcnow()
        session.add(issue)
        record_change(
            session,
            entity_type=issue.entity_type,
            entity_id=issue.entity_id,
            field=issue.field or "incidencia",
            before="open",
            after="resolved",
            action="issue_resolution",
            actor=actor,
            reason=data.reason,
            version=0,
        )
        session.commit()
    return {"ok": True, "status": "resolved"}
