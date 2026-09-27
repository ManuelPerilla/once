"""Small persistence primitives; each write endpoint owns its transaction."""

from sqlalchemy import inspect


def audit_pending(session, reason="Edición desde la administración"):
    """Capture explicit API writes before flush; provider transactions do not call this."""
    from src.audit.service import record_change
    from src.football.entities import ENTITY_MODELS
    from src.models import EntityRevision, FieldState, utcnow
    from src.security import get_auth_settings
    from src.sync.models import SyncNotification

    kinds = {model: kind for kind, model in ENTITY_MODELS.items()}
    request = session.info.get("request")
    actor = (
        (getattr(request.state, "actor", None) if request else None)
        or session.info.get("actor")
        or get_auth_settings().admin_username
    )
    pending = []
    for row in list(session.new) + list(session.dirty) + list(session.deleted):
        kind = kinds.get(type(row))
        if not kind:
            continue
        state = inspect(row)
        action = (
            "manual_delete"
            if row in session.deleted
            else "manual_create"
            if row in session.new
            else "manual_update"
        )
        changes = {}
        for name in type(row).model_fields:
            if name == "id":
                continue
            history = state.attrs[name].history
            if action != "manual_update" or history.has_changes():
                changes[name] = (
                    history.deleted[0]
                    if history.deleted
                    else getattr(row, name)
                    if action == "manual_delete"
                    else None,
                    None if action == "manual_delete" else getattr(row, name),
                )
        if changes:
            pending.append((row, kind, action, changes))
    session.flush()
    for row, kind, action, changes in pending:
        revision = session.get(EntityRevision, (kind, row.id))
        if revision is None:
            revision = EntityRevision(entity_type=kind, entity_id=row.id)
        revision.version += 1
        session.add(revision)
        for field, (before, after) in changes.items():
            state = session.get(FieldState, (kind, row.id, field)) or FieldState(
                entity_type=kind, entity_id=row.id, field=field
            )
            state.protected, state.source, state.observed_at = True, f"manual:{actor}", utcnow()
            session.add(state)
            record_change(
                session,
                entity_type=kind,
                entity_id=row.id,
                field=field,
                before=before,
                after=after,
                action=action,
                actor=actor,
                reason=reason,
                version=revision.version,
            )
        session.add(
            SyncNotification(
                topic="matches"
                if kind in {"match", "event", "lineup", "statistics"}
                else "catalog",
                payload={"entity_type": kind, "entity_id": row.id},
            )
        )


def save(session, entity):
    session.add(entity)
    audit_pending(session)
    session.commit()
    session.refresh(entity)
    return entity
