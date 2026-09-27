"""Edition participation, rule versions and separately labelled standings."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import func, literal
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.audit.service import record_change
from src.football.projections import (
    StandingsScopeError,
    latest_rule,
    read_standings,
    rebuild_season_standings,
    scope_key,
    validate_scope,
)
from src.football.rules import validar_compatibilidad
from src.football.standings import StandingsConfig
from src.models import (
    Competicion,
    Equipo,
    Fase,
    Grupo,
    OfficialStandingSnapshot,
    ParticipacionFase,
    ParticipacionGrupo,
    ParticipacionTemporada,
    StandingAdjustment,
    StandingProjection,
    StandingRule,
    Temporada,
)

router = APIRouter()


class ParticipantInput(BaseModel):
    equipo_id: int = Field(gt=0)
    fase_id: int | None = Field(default=None, gt=0)
    grupo_id: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=3, max_length=1000)


class GroupInput(BaseModel):
    fase_id: int = Field(gt=0)
    nombre: str = Field(min_length=1, max_length=100)


class RuleInput(BaseModel):
    temporada_id: int = Field(gt=0)
    fase_id: int | None = Field(default=None, gt=0)
    grupo_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=3, max_length=200)
    source_url: AnyHttpUrl
    verified: bool = False
    config: StandingsConfig = Field(default_factory=StandingsConfig)


class AdjustmentInput(BaseModel):
    temporada_id: int = Field(gt=0)
    fase_id: int | None = Field(default=None, gt=0)
    grupo_id: int | None = Field(default=None, gt=0)
    equipo_id: int = Field(gt=0)
    points: int = Field(ge=-100, le=100)
    reason: str = Field(min_length=3, max_length=1000)
    source_url: AnyHttpUrl


def _scope(session, season_id, phase_id=None, group_id=None):
    try:
        return validate_scope(session, season_id, phase_id, group_id)
    except StandingsScopeError as exc:
        raise HTTPException(422, str(exc)) from exc


def _lock_season(session, season_id):
    return session.exec(select(Temporada).where(Temporada.id == season_id).with_for_update()).one()


@router.get("/public/temporadas/{season_id}/clasificacion")
def standings(
    season_id: int,
    phase_id: int | None = None,
    group_id: int | None = None,
    session: Session = Depends(get_session),
):
    _scope(session, season_id, phase_id, group_id)
    return read_standings(session, season_id, phase_id, group_id)


@router.get("/public/grupos/")
def groups(season_id: int = Query(gt=0), session: Session = Depends(get_session)):
    return session.exec(
        select(Grupo)
        .join(Fase)
        .where(Fase.temporada_id == season_id)
        .order_by(Fase.orden, Grupo.nombre)
    ).all()


@router.get("/public/temporadas/{season_id}/context")
def season_context(season_id: int, session: Session = Depends(get_session)):
    _scope(session, season_id)
    phases = session.exec(
        select(Fase).where(Fase.temporada_id == season_id).order_by(Fase.orden, Fase.id)
    ).all()
    season_groups = groups(season_id, session)
    scopes = {scope_key(season_id): {"phase_id": None, "group_id": None}}
    for phase in phases:
        scopes[scope_key(season_id, phase.id)] = {"phase_id": phase.id, "group_id": None}
        for group in season_groups:
            if group.fase_id == phase.id:
                scopes[scope_key(season_id, phase.id, group.id)] = {
                    "phase_id": phase.id,
                    "group_id": group.id,
                }
    # Return availability only, without loading every historic table's rows.
    latest = (
        select(StandingRule.scope_key, func.max(StandingRule.version).label("version"))
        .where(StandingRule.temporada_id == season_id)
        .group_by(StandingRule.scope_key)
        .subquery()
    )
    official = select(OfficialStandingSnapshot.scope_key, literal("official")).where(
        OfficialStandingSnapshot.scope_key.in_(scopes),
        func.json_array_length(OfficialStandingSnapshot.rows) > 0,
    )
    calculated = (
        select(StandingProjection.scope_key, literal("calculated"))
        .join(StandingRule, StandingRule.id == StandingProjection.rule_id)
        .join(
            latest,
            (latest.c.scope_key == StandingRule.scope_key)
            & (latest.c.version == StandingRule.version),
        )
        .where(
            StandingProjection.scope_key.in_(scopes),
            StandingRule.verified.is_(True),
            func.json_array_length(StandingProjection.rows) > 0,
        )
    )
    available = {}
    for key, source in session.exec(official.union(calculated)).all():
        available.setdefault(key, []).append(source)
    return {
        "phases": phases,
        "groups": season_groups,
        "available_standings": [
            {**scope, "sources": available[key]}
            for key, scope in scopes.items()
            if key in available
        ],
    }


@router.get(
    "/football/temporadas/{season_id}/participantes", dependencies=[Depends(verificar_token)]
)
def participants(season_id: int, session: Session = Depends(get_session)):
    _scope(session, season_id)
    return session.exec(
        select(ParticipacionTemporada).where(ParticipacionTemporada.temporada_id == season_id)
    ).all()


@router.post("/football/temporadas/{season_id}/participantes")
def add_participant(
    season_id: int,
    data: ParticipantInput,
    session: Session = Depends(get_session),
    actor: str = Depends(verificar_token),
):
    season = _scope(session, season_id, data.fase_id, data.grupo_id)
    _lock_season(session, season_id)
    team = session.get(Equipo, data.equipo_id)
    if team is None:
        raise HTTPException(404, "Equipo no encontrado")
    validar_compatibilidad(team, session.get(Competicion, season.competicion_id))
    targets = [(ParticipacionTemporada, "temporada_id", season_id)]
    if data.fase_id:
        targets.append((ParticipacionFase, "fase_id", data.fase_id))
    if data.grupo_id:
        targets.append((ParticipacionGrupo, "grupo_id", data.grupo_id))
    created = False
    for model, field, identity in targets:
        if session.get(model, (team.id, identity)):
            continue
        payload = {"equipo_id": team.id, field: identity}
        payload["source"] = f"manual:{actor}"
        session.add(model(**payload))
        created = True
    if created:
        record_change(
            session,
            entity_type="season",
            entity_id=season_id,
            field="participantes",
            before=None,
            after=data.model_dump(),
            action="participation",
            actor=actor,
            reason=data.reason,
            version=0,
        )
    rebuild_season_standings(session, season_id)
    session.commit()
    return {"ok": True, "created": created}


@router.post("/football/grupos")
def add_group(
    data: GroupInput, session: Session = Depends(get_session), actor: str = Depends(verificar_token)
):
    phase = session.get(Fase, data.fase_id)
    if phase is None:
        raise HTTPException(404, "Fase no encontrada")
    _lock_season(session, phase.temporada_id)
    existing = session.exec(
        select(Grupo).where(Grupo.fase_id == data.fase_id, Grupo.nombre == data.nombre)
    ).first()
    if existing:
        return existing
    row = Grupo(**data.model_dump())
    session.add(row)
    session.flush()
    record_change(
        session,
        entity_type="stage",
        entity_id=phase.id,
        field="grupos",
        before=None,
        after=row.model_dump(),
        action="group_create",
        actor=actor,
        reason="Grupo creado explícitamente por el operador",
        version=0,
    )
    session.commit()
    session.refresh(row)
    return row


@router.get("/football/reglas", dependencies=[Depends(verificar_token)])
def rules(season_id: int = Query(gt=0), session: Session = Depends(get_session)):
    return session.exec(
        select(StandingRule)
        .where(StandingRule.temporada_id == season_id)
        .order_by(StandingRule.version.desc())
    ).all()


@router.post("/football/reglas")
def add_rule(
    data: RuleInput, session: Session = Depends(get_session), actor: str = Depends(verificar_token)
):
    _scope(session, data.temporada_id, data.fase_id, data.grupo_id)
    _lock_season(session, data.temporada_id)
    key = scope_key(data.temporada_id, data.fase_id, data.grupo_id)
    previous = latest_rule(session, key)
    row = StandingRule(
        scope_key=key,
        temporada_id=data.temporada_id,
        fase_id=data.fase_id,
        grupo_id=data.grupo_id,
        version=previous.version + 1 if previous else 1,
        name=data.name,
        source_url=str(data.source_url),
        verified=data.verified,
        config=data.config.model_dump(),
        actor=actor,
    )
    session.add(row)
    session.flush()
    record_change(
        session,
        entity_type="season",
        entity_id=data.temporada_id,
        field="reglamento",
        before=previous.model_dump(mode="json") if previous else None,
        after=row.model_dump(mode="json"),
        action="rule_version",
        actor=actor,
        reason=data.name,
        version=row.version,
    )
    rebuild_season_standings(session, data.temporada_id)
    session.commit()
    session.refresh(row)
    return row


@router.post("/football/ajustes")
def add_adjustment(
    data: AdjustmentInput,
    session: Session = Depends(get_session),
    actor: str = Depends(verificar_token),
):
    from src.football.projections import _participants

    _scope(session, data.temporada_id, data.fase_id, data.grupo_id)
    _lock_season(session, data.temporada_id)
    teams = _participants(session, data.temporada_id, data.fase_id, data.grupo_id)
    if data.equipo_id not in {team.id for team in teams}:
        raise HTTPException(422, "El equipo no participa en el ámbito elegido")
    row = StandingAdjustment(
        scope_key=scope_key(data.temporada_id, data.fase_id, data.grupo_id),
        equipo_id=data.equipo_id,
        points=data.points,
        reason=data.reason,
        source_url=str(data.source_url),
        actor=actor,
    )
    session.add(row)
    session.flush()
    record_change(
        session,
        entity_type="season",
        entity_id=data.temporada_id,
        field="ajustes",
        before=None,
        after=row.model_dump(mode="json"),
        action="standing_adjustment",
        actor=actor,
        reason=data.reason,
        version=0,
    )
    rebuild_season_standings(session, data.temporada_id)
    session.commit()
    session.refresh(row)
    return row
