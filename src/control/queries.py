"""Bounded SQL reads; no remote requests, reconciliation or implicit repairs."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import and_, func, literal, or_, union_all
from sqlalchemy.orm import aliased
from sqlmodel import select

from src.catalog.collections import COLLECTIONS
from src.football.entities import ENTITY_MODELS as ALL_ENTITY_MODELS
from src.models import (
    AlineacionPartido,
    CatalogImportBatch,
    Competicion,
    Equipo,
    EstadisticasPartido,
    EventoPartido,
    JugadorEquipo,
    MediaAsset,
    Participacion,
    Partido,
    ProviderMapping,
    ProviderSnapshot,
    Temporada,
)

from .schemas import ControlPage, ControlRecord, ControlSummary, QualityCheck

ENTITY_LABELS = {
    "confederation": ("Confederaciones", "confederations"),
    "competition": ("Competiciones", "competitions"),
    "team": ("Equipos", "teams"),
    "match": ("Partidos", "matches"),
    "season": ("Temporadas", "seasons"),
    "stage": ("Fases", "stages"),
    "venue": ("Estadios", "venues"),
    "player": ("Jugadores", "players"),
}
ENTITY_MODELS = {kind: ALL_ENTITY_MODELS[kind] for kind in ENTITY_LABELS}
RECORD_MODELS = {
    "imports": CatalogImportBatch,
    "links": ProviderMapping,
    "observations": ProviderSnapshot,
    "media": MediaAsset,
}
OBSERVATION_LABELS = {
    "catalog_identity": "Identidad del catálogo",
    "fixture": "Ficha del partido",
    "fixtures": "Programación de partidos",
    "events": "Sucesos del partido",
    "lineups": "Alineaciones",
    "statistics": "Estadísticas",
}
SCOPE_NOTES = [
    "Este control consulta los datos guardados. No importa, corrige ni consulta fuentes externas.",
    "Los avisos de revisión señalan datos opcionales o pendientes; no prueban por sí solos un error.",
    "Cada observación conserva solo la última respuesta por fuente, registro y categoría.",
    "Cada lote conserva su última aplicación. La fecha de consulta no es la fecha de creación local.",
    "Las correcciones protegidas y sus autores se consultan en Automatización, apartado Auditoría.",
]


def _entities():
    """Resolve names in one join, including polymorphic references left by deletions."""
    home, away = aliased(Equipo), aliased(Equipo)
    branches = [
        select(
            literal(kind).label("entity_type"),
            model.id.label("entity_id"),
            model.nombre.label("entity_name"),
        )
        for kind, model in ENTITY_MODELS.items()
        if kind != "match"
    ]
    branches.append(
        select(
            literal("match").label("entity_type"),
            Partido.id.label("entity_id"),
            (
                func.coalesce(home.nombre, "Local pendiente")
                + " · "
                + func.coalesce(away.nombre, "Visitante pendiente")
            ).label("entity_name"),
        )
        .outerjoin(home, home.id == Partido.equipo_local_id)
        .outerjoin(away, away.id == Partido.equipo_visitante_id)
    )
    return union_all(*branches).subquery("local_entities")


def _reference_statement(kind):
    model = RECORD_MODELS[kind]
    entities = _entities()
    local_id = model.entity_id if kind == "media" else model.local_id
    return select(model, entities.c.entity_name).outerjoin(
        entities,
        and_(model.entity_type == entities.c.entity_type, local_id == entities.c.entity_id),
    )


def _page(session, statement, page, page_size, render):
    total = session.exec(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ).one()
    rows = session.exec(statement.offset((page - 1) * page_size).limit(page_size)).all()
    return ControlPage(
        items=[render(row) for row in rows], total=total, page=page, page_size=page_size
    )


def _name_filter(column, search):
    # Literal substring semantics: '%' and '_' entered by an operator are not wildcards.
    return column.icontains(search.strip(), autoescape=True)


def _blank(column):
    return func.trim(func.coalesce(column, "")) == ""


def _text(value):
    return value if isinstance(value, str) else None


def _record(kind, row):
    if kind == "imports":
        batch = row
        result = batch.last_result or {}
        applied = batch.last_result is not None
        return ControlRecord(
            id=batch.id,
            kind=kind,
            title=COLLECTIONS.get(batch.collection, {}).get("name", batch.collection),
            provider="wikidata",
            recorded_at=batch.fetched_at,
            status="applied" if applied else "prepared",
            detail=(
                "Consulta revisada y aplicada; se muestra el último resultado guardado."
                if applied
                else "Consulta preparada. No consta una aplicación guardada de este lote."
            ),
            metadata={
                "collection": batch.collection,
                "observed_rows": len(batch.payload.get("rows", [])),
                **{key: result.get(key, 0) for key in ("created", "linked", "reused", "skipped")},
                "applied_at": result.get("applied_at"),
            },
        )
    record, name = row
    entity_id = record.entity_id if kind == "media" else record.local_id
    values = {
        "id": str(record.id),
        "kind": kind,
        "entity_type": record.entity_type,
        "entity_id": entity_id,
        "entity_name": name,
        "module": ENTITY_LABELS.get(record.entity_type, (None, None))[1],
        "title": (
            name or f"Registro sin nombre · {entity_id}"
            if name is not None
            else f"Registro no encontrado · {entity_id}"
        ),
        "status": "recorded" if name is not None else "orphaned",
    }
    if kind == "links":
        return ControlRecord(
            **values,
            provider=record.provider,
            recorded_at=record.verified_at,
            detail=f"Identificador externo: {record.external_id}",
            source_url=record.source_url,
            metadata={"external_id": record.external_id},
        )
    if kind == "observations":
        return ControlRecord(
            **values,
            provider=record.provider,
            recorded_at=record.fetched_at,
            detail=OBSERVATION_LABELS.get(record.kind, record.kind),
            source_url=_text(record.payload.get("source_url")),
            metadata={
                "observation_kind": record.kind,
                "license": _text(record.payload.get("license")),
                "import_batch_id": _text(record.payload.get("import_batch_id")),
            },
        )
    if not record.license or not record.license.strip():
        values["status"] = "review" if name is not None else "orphaned"
    return ControlRecord(
        **values,
        provider=record.source,
        recorded_at=record.verified_at,
        detail="Escudo" if record.tipo == "escudo" else "Imagen del registro",
        source_url=record.source_url,
        metadata={
            "author": record.author,
            "license": record.license,
            "license_url": record.license_url,
            "credit": record.credit,
            "image_url": record.original_url,
        },
    )


def records(session, kind, provider=None, entity_type=None, search=None, page=1, page_size=20):
    model = RECORD_MODELS[kind]
    if kind == "imports":
        statement = select(model)
        if provider and provider != "wikidata":
            statement = statement.where(literal(False))
        if search and search.strip():
            collections = [
                key
                for key, definition in COLLECTIONS.items()
                if search.casefold().strip() in definition["name"].casefold()
            ]
            statement = statement.where(
                or_(_name_filter(model.collection, search), model.collection.in_(collections))
            )
        statement = statement.order_by(model.fetched_at.desc(), model.id.desc())
    else:
        statement = _reference_statement(kind)
        if provider:
            statement = statement.where(
                (model.source if kind == "media" else model.provider) == provider
            )
        if entity_type:
            statement = statement.where(model.entity_type == entity_type)
        if search and search.strip():
            name = statement.selected_columns.entity_name
            identifier = (
                model.remote_id
                if kind == "media"
                else (model.external_id if kind == "links" else model.kind)
            )
            statement = statement.where(
                or_(_name_filter(name, search), _name_filter(identifier, search))
            )
        timestamp = model.fetched_at if kind == "observations" else model.verified_at
        statement = statement.order_by(timestamp.desc().nulls_last(), model.id.desc())
    return _page(session, statement, page, page_size, lambda row: _record(kind, row))


@dataclass(frozen=True)
class CheckDefinition:
    code: str
    label: str
    description: str
    module: str
    entity_type: str | None = None
    condition: object = None
    record_kind: str | None = None
    severity: str = "review"


CHECKS = (
    CheckDefinition(
        "teams_without_confederation",
        "Equipos sin confederación",
        "Revisa si la afiliación está pendiente o no corresponde.",
        "teams",
        "team",
        Equipo.confederacion_id.is_(None),
    ),
    CheckDefinition(
        "competitions_without_confederation",
        "Competiciones sin confederación",
        "Las competiciones globales pueden no tener una única confederación.",
        "competitions",
        "competition",
        Competicion.confederacion_id.is_(None),
    ),
    CheckDefinition(
        "matches_without_date",
        "Partidos sin fecha",
        "Confirma su programación antes de usarlos en un calendario automático.",
        "matches",
        "match",
        Partido.fecha.is_(None),
    ),
    CheckDefinition(
        "matches_without_season",
        "Partidos sin temporada",
        "La temporada es opcional; revisa si debe asignarse para ordenar el torneo.",
        "matches",
        "match",
        Partido.temporada_id.is_(None),
    ),
    CheckDefinition(
        "matches_incomplete",
        "Partidos con referencias incompletas",
        "Falta la competición o alguno de los dos equipos.",
        "matches",
        "match",
        or_(
            Partido.competicion_id.is_(None),
            Partido.equipo_local_id.is_(None),
            Partido.equipo_visitante_id.is_(None),
        ),
        severity="error",
    ),
    CheckDefinition(
        "seasons_invalid_dates",
        "Temporadas con fechas invertidas",
        "La fecha final es anterior a la fecha inicial.",
        "seasons",
        "season",
        Temporada.fecha_fin < Temporada.fecha_inicio,
        severity="error",
    ),
    CheckDefinition(
        "links_without_record",
        "Vínculos sin registro local",
        "La identidad externa apunta a un registro que ya no existe.",
        "control",
        record_kind="links",
        severity="error",
    ),
    CheckDefinition(
        "observations_without_record",
        "Observaciones sin registro local",
        "La observación conservada apunta a un registro que ya no existe.",
        "control",
        record_kind="observations",
        severity="error",
    ),
    CheckDefinition(
        "media_without_record",
        "Imágenes sin registro local",
        "La imagen conservada apunta a un registro que ya no existe.",
        "control",
        record_kind="media",
        severity="error",
    ),
    CheckDefinition(
        "media_without_license",
        "Imágenes sin licencia documentada",
        "Revisa las condiciones de uso de la imagen en su fuente.",
        "control",
        condition=_blank(MediaAsset.license),
        record_kind="media",
    ),
)


def _issue_statement(check):
    if check.record_kind:
        statement = _reference_statement(check.record_kind)
        condition = check.condition
        if condition is None:
            condition = statement.selected_columns.entity_name.is_(None)
        model = RECORD_MODELS[check.record_kind]
        return statement.where(condition).order_by(model.id)
    entities = _entities()
    model = ENTITY_MODELS[check.entity_type]
    return (
        select(model.id, entities.c.entity_name)
        .join(
            entities,
            and_(entities.c.entity_type == check.entity_type, entities.c.entity_id == model.id),
        )
        .where(check.condition)
        .order_by(model.id)
    )


def issues(session, code, page=1, page_size=20):
    check = next(item for item in CHECKS if item.code == code)

    def render(row):
        if check.record_kind:
            record = _record(check.record_kind, row)
            record.detail = check.description
            return record
        entity_id, name = row
        return ControlRecord(
            id=str(entity_id),
            kind="issues",
            entity_type=check.entity_type,
            entity_id=entity_id,
            entity_name=name,
            module=check.module,
            title=name,
            status="review",
            detail=check.description,
        )

    return _page(session, _issue_statement(check), page, page_size, render)


def summary(session):
    models = {
        **{ENTITY_LABELS[kind][1]: model for kind, model in ENTITY_MODELS.items()},
        "rosters": JugadorEquipo,
        "enrollments": Participacion,
        "statistics": EstadisticasPartido,
        "events": EventoPartido,
        "lineups": AlineacionPartido,
        **RECORD_MODELS,
    }
    # Independent scalar subqueries avoid materializing every row or N+1 queries.
    count_query = select(
        *[
            select(func.count()).select_from(model).scalar_subquery().label(name)
            for name, model in models.items()
        ]
    )
    counts = dict(zip(models, session.exec(count_query).one(), strict=True))
    check_query = select(
        *[
            select(func.count())
            .select_from(_issue_statement(check).order_by(None).subquery())
            .scalar_subquery()
            .label(check.code)
            for check in CHECKS
        ]
    )
    check_counts = session.exec(check_query).one()
    providers_query = union_all(
        select(ProviderMapping.provider),
        select(ProviderSnapshot.provider),
        select(MediaAsset.source),
        select(literal("wikidata")).select_from(CatalogImportBatch),
    ).subquery()
    providers = session.exec(
        select(providers_query.c.provider).distinct().order_by(providers_query.c.provider)
    ).all()
    return ControlSummary(
        counts=counts,
        checks=[
            QualityCheck(
                code=check.code,
                label=check.label,
                description=check.description,
                count=count,
                severity=check.severity,
                module=check.module,
            )
            for check, count in zip(CHECKS, check_counts, strict=True)
        ],
        providers=providers,
        entity_types=[
            {"value": kind, "label": label} for kind, (label, _) in ENTITY_LABELS.items()
        ],
        scope_notes=SCOPE_NOTES,
        checked_at=dt.datetime.now(dt.timezone.utc),
    )
