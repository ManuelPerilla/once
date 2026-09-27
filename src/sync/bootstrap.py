"""Prepare the free Colombian pilot once, without enabling synchronization."""

from sqlmodel import Session, select

from src import database
from src.sync.models import SyncScope
from src.sync.service import control, history

PROFILES = (
    (
        "Confederaciones · catálogo abierto",
        "wikidata",
        "catalog",
        {"collection": "confederaciones"},
        604800,
    ),
    (
        "Colombia · equipos, competiciones y escudos",
        "wikidata",
        "catalog",
        {"collection": "colombia"},
        86400,
    ),
    ("Colombia 2025 · archivo histórico", "openfootball", "archive", {"season": 2025}, 604800),
)


def prepare(session, *, actor="service:setup"):
    control(session, lock=True)
    existing = session.exec(select(SyncScope)).all()
    created = []
    for name, provider, kind, selector, interval in PROFILES:
        if any(
            row.provider == provider
            and row.kind == kind
            and all(row.selector.get(key) == value for key, value in selector.items())
            for row in existing
        ):
            continue
        if len(existing) >= 50:
            break
        scope = SyncScope(
            name=name,
            provider=provider,
            kind=kind,
            selector=selector,
            mode="paused",
            interval_seconds=interval,
        )
        session.add(scope)
        session.flush()
        history(
            session,
            actor,
            "scope_created",
            scope.id,
            reason="Preparación del piloto abierto colombiano; permanece pausado.",
        )
        existing.append(scope)
        created.append(scope.id)
    return created


if __name__ == "__main__":
    with Session(database.engine) as session:
        created = prepare(session)
        session.commit()
    print(
        f"{len(created)} tareas preparadas. Actívalas desde Datos > Automatización después de revisar su selección."
    )
