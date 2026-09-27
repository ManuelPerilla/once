"""Persist calculated tables independently from externally published standings."""

import hashlib
import json
from collections import defaultdict

from sqlmodel import select

from src.audit.service import open_issue
from src.football.standings import StandingsConfig, calculate_standings
from src.models import (
    Equipo,
    Fase,
    Grupo,
    OfficialStandingSnapshot,
    ParticipacionFase,
    ParticipacionGrupo,
    ParticipacionTemporada,
    Partido,
    StandingAdjustment,
    StandingProjection,
    StandingRule,
    Temporada,
    utcnow,
)


class StandingsScopeError(ValueError):
    pass


def scope_key(season_id, phase_id=None, group_id=None):
    return f"season:{season_id}:phase:{phase_id or 0}:group:{group_id or 0}"


def validate_scope(session, season_id, phase_id=None, group_id=None):
    season = session.get(Temporada, season_id)
    if season is None:
        raise StandingsScopeError("Temporada no encontrada")
    if phase_id:
        phase = session.get(Fase, phase_id)
        if phase is None or phase.temporada_id != season_id:
            raise StandingsScopeError("La fase no pertenece a esta temporada")
    if group_id:
        group = session.get(Grupo, group_id)
        if group is None or group.fase_id != phase_id:
            raise StandingsScopeError("El grupo no pertenece a esta fase")
    return season


def _participants(session, season_id, phase_id, group_id):
    if group_id:
        link, column, value = ParticipacionGrupo, ParticipacionGrupo.grupo_id, group_id
    elif phase_id:
        link, column, value = ParticipacionFase, ParticipacionFase.fase_id, phase_id
    else:
        link, column, value = ParticipacionTemporada, ParticipacionTemporada.temporada_id, season_id
    return session.exec(
        select(Equipo)
        .join(link, link.equipo_id == Equipo.id)
        .where(column == value)
        .order_by(Equipo.id)
    ).all()


def latest_rule(session, key):
    return session.exec(
        select(StandingRule)
        .where(StandingRule.scope_key == key)
        .order_by(StandingRule.version.desc())
        .limit(1)
    ).first()


def rule_inputs(session, rule):
    validate_scope(session, rule.temporada_id, rule.fase_id, rule.grupo_id)
    config = StandingsConfig.model_validate(rule.config)
    phase_ids = session.exec(select(Fase.id).where(Fase.temporada_id == rule.temporada_id)).all()
    if not rule.fase_id and phase_ids and not config.included_phase_ids:
        raise StandingsScopeError("Elige una fase o las fases expresas de una tabla acumulada")
    if config.included_phase_ids and not set(config.included_phase_ids).issubset(phase_ids):
        raise StandingsScopeError("La tabla incluye fases ajenas a esta temporada")
    if rule.fase_id and config.included_phase_ids:
        raise StandingsScopeError("Una tabla de fase no puede incluir otras fases")
    if rule.fase_id and not rule.grupo_id:
        has_groups = session.exec(
            select(Grupo.id).where(Grupo.fase_id == rule.fase_id).limit(1)
        ).first()
        if has_groups:
            raise StandingsScopeError("Esta fase contiene grupos; elige un grupo para su tabla")
    teams = _participants(session, rule.temporada_id, rule.fase_id, rule.grupo_id)
    if not teams:
        raise StandingsScopeError("Aún no hay participantes verificados para esta tabla")
    statement = select(Partido).where(Partido.temporada_id == rule.temporada_id)
    if rule.fase_id:
        statement = statement.where(Partido.fase_id == rule.fase_id)
    elif config.included_phase_ids:
        statement = statement.where(Partido.fase_id.in_(config.included_phase_ids))
    if rule.grupo_id:
        statement = statement.where(Partido.grupo_id == rule.grupo_id)
    matches = session.exec(statement.order_by(Partido.id)).all()
    ids = {team.id for team in teams}
    if any(
        match.equipo_local_id not in ids or match.equipo_visitante_id not in ids
        for match in matches
    ):
        raise StandingsScopeError(
            "Hay partidos cuyos participantes no están verificados en este ámbito"
        )
    adjustments = session.exec(
        select(StandingAdjustment)
        .where(StandingAdjustment.scope_key == rule.scope_key)
        .order_by(StandingAdjustment.id)
    ).all()
    if any(adjustment.equipo_id not in ids for adjustment in adjustments):
        raise StandingsScopeError("Hay ajustes de equipos ajenos al ámbito")
    return teams, matches, adjustments, config


def rebuild_projection(session, rule):
    if not rule.verified:
        return None
    teams, matches, adjustments, config = rule_inputs(session, rule)
    payload = {
        "rule": rule.id,
        "config": rule.config,
        "teams": [team.model_dump(mode="json") for team in teams],
        "matches": [
            {
                key: getattr(match, key)
                for key in (
                    "id",
                    "equipo_local_id",
                    "equipo_visitante_id",
                    "marcador_local",
                    "marcador_visitante",
                    "estado",
                )
            }
            for match in matches
        ],
        "adjustments": [
            {"id": row.id, "team": row.equipo_id, "points": row.points} for row in adjustments
        ],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    projection = session.get(StandingProjection, rule.scope_key)
    if projection and projection.input_hash == digest:
        return projection
    by_team = defaultdict(int)
    for adjustment in adjustments:
        by_team[adjustment.equipo_id] += adjustment.points
    rows = [
        row.model_dump(mode="json")
        for row in calculate_standings(teams, matches, rules=config, adjustments=by_team)
    ]
    if projection is None:
        projection = StandingProjection(
            scope_key=rule.scope_key, rule_id=rule.id, input_hash=digest, rows=rows
        )
    else:
        projection.rule_id, projection.input_hash = rule.id, digest
        projection.rows, projection.updated_at = rows, utcnow()
    session.add(projection)
    return projection


def rebuild_season_standings(session, season_id):
    """Rebuild each latest verified scope once in the caller's transaction."""
    session.flush()
    # Serialize concurrent result corrections before reading all the inputs.
    # The second transaction must see the first committed correction, not replace
    # its projection with a calculation made from an earlier snapshot.
    season = session.exec(
        select(Temporada).where(Temporada.id == season_id).with_for_update()
    ).first()
    if season is None:
        return []
    rules = session.exec(
        select(StandingRule)
        .where(StandingRule.temporada_id == season_id)
        .order_by(StandingRule.scope_key, StandingRule.version.desc())
    ).all()
    seen, rebuilt = set(), []
    for rule in rules:
        if rule.scope_key in seen:
            continue
        seen.add(rule.scope_key)
        try:
            projection = rebuild_projection(session, rule)
            if projection:
                rebuilt.append(projection.scope_key)
        except StandingsScopeError as exc:
            # Invalidated projections must not continue being served as current.
            stale = session.get(StandingProjection, rule.scope_key)
            if stale:
                session.delete(stale)
            open_issue(
                session,
                key=f"standings:{rule.scope_key}",
                entity_type="season",
                entity_id=season_id,
                source="once",
                reason=str(exc),
            )
    return rebuilt


def store_official_standings(
    session, *, season_id, phase_id=None, group_id=None, source, source_url, rows, observed_at=None
):
    """Preserve separately a provider table, validating canonical participants."""
    validate_scope(session, season_id, phase_id, group_id)
    key = scope_key(season_id, phase_id, group_id)
    session.exec(select(Temporada).where(Temporada.id == season_id).with_for_update()).one()
    participants = {team.id for team in _participants(session, season_id, phase_id, group_id)}
    teams = [row.get("team_id") for row in rows]
    if not rows or len(teams) != len(set(teams)) or set(teams) != participants:
        raise StandingsScopeError("La tabla externa no tiene participantes válidos y únicos")
    required = {
        "team_id",
        "rank",
        "points",
        "played",
        "won",
        "drawn",
        "lost",
        "goals_for",
        "goals_against",
    }
    for row in rows:
        if not required.issubset(row) or any(
            not isinstance(row[name], int) or isinstance(row[name], bool) for name in required
        ):
            raise StandingsScopeError("La tabla externa está incompleta")
        if any(row[name] < 0 for name in required - {"points"}) or row["rank"] < 1:
            raise StandingsScopeError("La tabla externa contiene valores imposibles")
        if row["played"] != row["won"] + row["drawn"] + row["lost"]:
            raise StandingsScopeError("Los partidos de la tabla externa no cuadran")
        if row.get("goal_difference") is not None and row["goal_difference"] != (
            row["goals_for"] - row["goals_against"]
        ):
            raise StandingsScopeError("La diferencia de goles de la tabla externa no cuadra")
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    current = session.exec(
        select(OfficialStandingSnapshot)
        .where(
            OfficialStandingSnapshot.scope_key == key,
            OfficialStandingSnapshot.source == source,
        )
        .order_by(OfficialStandingSnapshot.fetched_at.desc(), OfficialStandingSnapshot.id.desc())
        .limit(1)
    ).first()
    if current and (
        current.content_hash == digest
        or (observed_at is not None and observed_at < current.fetched_at)
    ):
        return current
    snapshot = OfficialStandingSnapshot(
        scope_key=key,
        source=source,
        source_url=source_url,
        content_hash=digest,
        rows=rows,
        fetched_at=observed_at or utcnow(),
    )
    session.add(snapshot)
    return snapshot


def read_standings(session, season_id, phase_id=None, group_id=None):
    validate_scope(session, season_id, phase_id, group_id)
    key = scope_key(season_id, phase_id, group_id)
    rule = latest_rule(session, key)
    projection = session.get(StandingProjection, key)
    official = session.exec(
        select(OfficialStandingSnapshot)
        .where(OfficialStandingSnapshot.scope_key == key)
        .order_by(OfficialStandingSnapshot.fetched_at.desc(), OfficialStandingSnapshot.id.desc())
        .limit(1)
    ).first()
    status = "missing_rules" if not rule else "unverified_rules" if not rule.verified else "pending"
    if rule and rule.verified and projection and projection.rule_id == rule.id:
        status = "ready"
    official_data = None
    if official:
        ids = [row["team_id"] for row in official.rows]
        teams = {
            team.id: team.model_dump(mode="json")
            for team in session.exec(select(Equipo).where(Equipo.id.in_(ids))).all()
        }
        official_data = {
            **official.model_dump(),
            "rows": [{**row, "team": teams.get(row["team_id"])} for row in official.rows],
        }
    return {
        "scope_key": key,
        "status": status,
        "rule": rule,
        "calculated": projection if status == "ready" else None,
        "official": official_data,
        "provisional": None,
    }
