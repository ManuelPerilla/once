"""Protected corrections and atomic audit records; callers own the transaction."""

import datetime
import json
from enum import Enum

from pydantic import TypeAdapter
from sqlalchemy import event
from sqlmodel import select

from src.football.entities import ENTITY_MODELS
from src.models import AuditChange, DataIssue, EntityRevision, FieldState, utcnow

EDITABLE_FIELDS = {
    "confederation": {"nombre", "logo"},
    "competition": {"nombre", "logo", "pais"},
    "team": {"nombre", "logo", "pais"},
    "match": {"fecha", "jornada", "marcador_local", "marcador_visitante", "estado"},
    "season": {"nombre", "fecha_inicio", "fecha_fin", "activa"},
    "stage": {"nombre", "tipo", "orden"},
    "venue": {"nombre", "ciudad", "pais", "latitud", "longitud"},
    "player": {"nombre", "nombre_completo", "posicion", "nacionalidad", "fecha_nacimiento"},
    "event": {"tipo", "minuto", "adicional", "detalle"},
    "lineup": {"titular", "posicion", "dorsal", "orden"},
    "statistics": {
        "posesion_local",
        "posesion_visitante",
        "tiros_puerta_local",
        "tiros_puerta_visitante",
    },
}


class AuditConflict(ValueError):
    pass


def json_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@event.listens_for(AuditChange, "before_update")
@event.listens_for(AuditChange, "before_delete")
def audit_is_append_only(*_):
    raise AuditConflict("El historial de cambios es de solo anexado.")


def _lock_entity(session, entity_type, entity):
    model = ENTITY_MODELS.get(entity_type)
    if model is None or not isinstance(entity, model):
        raise ValueError("Tipo de entidad incompatible")
    session.flush()
    session.exec(
        select(model)
        .where(model.id == entity.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    key = (entity_type, entity.id)
    revision = session.get(EntityRevision, key)
    if revision is not None:
        session.refresh(revision)
    if revision is None:
        revision = EntityRevision(entity_type=entity_type, entity_id=entity.id)
        session.add(revision)
        session.flush()
    return revision


def record_change(
    session,
    *,
    entity_type,
    entity_id,
    field,
    before,
    after,
    action,
    actor,
    reason,
    version,
    source=None,
    run_id=None,
):
    if not actor.strip() or not reason.strip():
        raise ValueError("Cada cambio requiere actor y motivo")
    row = AuditChange(
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        before=json_value(before),
        after=json_value(after),
        action=action,
        actor=actor,
        reason=reason,
        version=version,
        source=source,
        run_id=run_id,
    )
    session.add(row)
    return row


def open_issue(session, *, key, entity_type, entity_id, field=None, source, reason, proposed=None):
    issue = session.exec(select(DataIssue).where(DataIssue.key == key)).first()
    value = json_value(proposed)
    if issue is None:
        issue = DataIssue(
            key=key,
            entity_type=entity_type,
            entity_id=entity_id,
            field=field,
            source=source,
            reason=reason,
            proposed=value,
        )
    elif issue.proposed != value:
        issue.occurrences += 1
        issue.updated_at = utcnow()
        issue.proposed, issue.status, issue.reason = value, "open", reason
    session.add(issue)
    return issue


def _state(session, entity_type, entity_id, field):
    state = session.get(FieldState, (entity_type, entity_id, field))
    if state is None:
        state = FieldState(entity_type=entity_type, entity_id=entity_id, field=field)
        session.add(state)
    return state


def _validated(entity, field, value):
    model_field = type(entity).model_fields.get(field)
    if field == "id" or model_field is None:
        raise ValueError("Campo desconocido o identidad inmutable")
    return TypeAdapter(model_field.rebuild_annotation()).validate_python(value)


def _validate_correction(entity_type, entity, field, value):
    if field in {"nombre", "tipo", "pais"} and isinstance(value, str) and not value.strip():
        raise ValueError("Este campo no puede quedar vacío")
    candidate = type(entity).model_validate({**entity.model_dump(), field: value})
    if entity_type == "season" and candidate.fecha_inicio and candidate.fecha_fin:
        if candidate.fecha_fin < candidate.fecha_inicio:
            raise ValueError("La fecha final no puede ser anterior al inicio")
    if entity_type in {"team", "competition"} and field == "pais":
        from src.football.rules import normalizar_competicion, validar_compatibilidad

        if entity_type == "team":
            for competition in entity.competiciones:
                validar_compatibilidad(candidate, competition)
        else:
            normalizar_competicion(candidate)
            if candidate.pais != value:
                raise ValueError("Una competición internacional conserva el país Internacional")
            for team in entity.equipos:
                validar_compatibilidad(team, candidate)


def apply_source_changes(
    session,
    entity_type,
    entity,
    changes,
    *,
    source,
    observed_at=None,
    actor="service:sync",
    run_id=None,
):
    """Apply only authorized, non-stale differences. Returns names of changed fields."""
    revision = _lock_entity(session, entity_type, entity)
    observed_at = observed_at or utcnow()
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=datetime.timezone.utc)
    applied = []
    # Validate every value before modifying the canonical entity.
    values = {field: _validated(entity, field, value) for field, value in changes.items()}
    for field, value in values.items():
        state = _state(session, entity_type, entity.id, field)
        before = getattr(entity, field)
        if state.observed_at and state.observed_at > observed_at:
            continue
        if state.protected or (state.source and state.source != source):
            if before != value:
                open_issue(
                    session,
                    key=f"field:{entity_type}:{entity.id}:{field}:{source}",
                    entity_type=entity_type,
                    entity_id=entity.id,
                    field=field,
                    source=source,
                    reason="La fuente difiere de un campo protegido o de otra autoridad.",
                    proposed=value,
                )
            continue
        if before != value:
            if not applied:
                revision.version += 1
            setattr(entity, field, value)
            applied.append(field)
            record_change(
                session,
                entity_type=entity_type,
                entity_id=entity.id,
                field=field,
                before=before,
                after=value,
                action="source_update",
                actor=actor,
                reason="Actualización validada de la fuente",
                version=revision.version,
                source=source,
                run_id=run_id,
            )
        state.source, state.observed_at = source, observed_at
        session.add(state)
    session.add(entity)
    session.add(revision)
    return applied


def correct_field(session, entity_type, entity, field, value, *, actor, reason, expected_version):
    if field not in EDITABLE_FIELDS.get(entity_type, set()):
        raise ValueError("Este campo requiere una operación específica de estructura")
    if not reason.strip():
        raise ValueError("Explica brevemente el motivo de la corrección")
    revision = _lock_entity(session, entity_type, entity)
    if revision.version != expected_version:
        raise AuditConflict("La ficha cambió. Recarga y revisa el valor actual antes de corregir.")
    value = _validated(entity, field, value)
    _validate_correction(entity_type, entity, field, value)
    before = getattr(entity, field)
    state = _state(session, entity_type, entity.id, field)
    if before == value and state.protected:
        return revision.version
    revision.version += 1
    setattr(entity, field, value)
    state.protected = True
    record_change(
        session,
        entity_type=entity_type,
        entity_id=entity.id,
        field=field,
        before=before,
        after=value,
        action="correction",
        actor=actor,
        reason=reason,
        version=revision.version,
    )
    session.add_all([entity, state, revision])
    _resolve_field_issues(session, entity_type, entity.id, field)
    return revision.version


def release_field(session, entity_type, entity, field, *, actor, reason, expected_version):
    if field not in EDITABLE_FIELDS.get(entity_type, set()):
        raise ValueError("Campo no corregible")
    if not reason.strip():
        raise ValueError("Explica el motivo de volver a aceptar la fuente")
    revision = _lock_entity(session, entity_type, entity)
    if revision.version != expected_version:
        raise AuditConflict("La ficha cambió. Recarga antes de continuar.")
    state = _state(session, entity_type, entity.id, field)
    if not state.protected:
        return revision.version
    revision.version += 1
    state.protected = False
    # The next verified observation can claim a formerly manual/legacy field.
    if state.source is None or state.source.startswith(("manual:", "legacy:")):
        state.source, state.observed_at = None, None
    record_change(
        session,
        entity_type=entity_type,
        entity_id=entity.id,
        field=field,
        before=getattr(entity, field),
        after=getattr(entity, field),
        action="release",
        actor=actor,
        reason=reason,
        version=revision.version,
    )
    session.add_all([state, revision])
    _resolve_field_issues(session, entity_type, entity.id, field)
    return revision.version


def _resolve_field_issues(session, entity_type, entity_id, field):
    for issue in session.exec(
        select(DataIssue).where(
            DataIssue.entity_type == entity_type,
            DataIssue.entity_id == entity_id,
            DataIssue.field == field,
            DataIssue.status == "open",
        )
    ).all():
        issue.status, issue.updated_at = "resolved", utcnow()
        session.add(issue)


def protect_manual_fields(session, entity_type, entity, *, actor, reason, fields=None):
    """Record a manual creation and protect explicitly supplied scalar fields."""
    revision = _lock_entity(session, entity_type, entity)
    values = fields if fields is not None else entity.model_fields_set
    protected = []
    for field in sorted(set(values) - {"id"}):
        if field not in type(entity).model_fields:
            continue
        state = _state(session, entity_type, entity.id, field)
        if state.protected:
            continue
        if not protected:
            revision.version += 1
        state.protected, state.source, state.observed_at = True, f"manual:{actor}", utcnow()
        protected.append(field)
        record_change(
            session,
            entity_type=entity_type,
            entity_id=entity.id,
            field=field,
            before=None,
            after=getattr(entity, field),
            action="manual_create",
            actor=actor,
            reason=reason,
            version=revision.version,
        )
        session.add(state)
    session.add(revision)
    return protected
