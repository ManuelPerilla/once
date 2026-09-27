"""Bounded local read paths; no provider requests during navigation."""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, or_
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.football.queries import matches_query, partido_publico, teams_query
from src.models import (
    AlineacionPartido,
    Competicion,
    Equipo,
    EquipoConCompeticionesRead,
    EstadoPartido,
    EventoPartido,
    Jugador,
    JugadorEquipo,
    Participacion,
    Partido,
    ProviderMapping,
)

router = APIRouter()


def incomplete():
    return or_(
        Partido.competicion_id.is_(None),
        Partido.equipo_local_id.is_(None),
        Partido.equipo_visitante_id.is_(None),
        Partido.temporada_id.is_(None),
        Partido.fecha.is_(None),
    )


class MatchFilters:
    def __init__(
        self,
        competition_id: int | None = Query(None, gt=0),
        season_id: str | None = None,
        phase_id: int | None = Query(None, gt=0),
        team_id: int | None = Query(None, gt=0),
        player_id: int | None = Query(None, gt=0),
        status: str | None = None,
        search: str = Query("", max_length=120),
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        date_start: dt.datetime | None = None,
        date_end: dt.datetime | None = None,
        attention: bool = False,
        sort: Literal["recent", "newest", "oldest"] = "recent",
        page: int = Query(1, ge=1, le=100_000),
        page_size: int = Query(30, ge=1, le=100),
    ):
        self.page, self.page_size, self.sort = page, page_size, sort
        self.conditions = []
        for column, value in (
            (Partido.competicion_id, competition_id),
            (Partido.fase_id, phase_id),
        ):
            if value is not None:
                self.conditions.append(column == value)
        if season_id and season_id != "all":
            if season_id == "unassigned":
                self.conditions.append(Partido.temporada_id.is_(None))
            elif season_id.isdigit() and int(season_id) > 0:
                self.conditions.append(Partido.temporada_id == int(season_id))
            else:
                raise HTTPException(422, "Temporada no válida.")
        if team_id:
            self.conditions.append(
                or_(Partido.equipo_local_id == team_id, Partido.equipo_visitante_id == team_id)
            )
        if player_id:
            self.conditions.append(
                or_(
                    Partido.id.in_(
                        select(AlineacionPartido.partido_id).where(
                            AlineacionPartido.jugador_id == player_id
                        )
                    ),
                    Partido.id.in_(
                        select(EventoPartido.partido_id).where(
                            or_(
                                EventoPartido.jugador_id == player_id,
                                EventoPartido.asistente_id == player_id,
                            )
                        )
                    ),
                )
            )
        if status and status != "all":
            aliases = {"live": "en vivo", "scheduled": "programado", "finished": "finalizado"}
            try:
                self.conditions.append(Partido.estado == EstadoPartido(aliases.get(status, status)))
            except ValueError as exc:
                raise HTTPException(422, "Estado de partido no válido.") from exc
        if search.strip():
            pattern = "%" + search.strip().replace("%", "\\%").replace("_", "\\_") + "%"
            teams = select(Equipo.id).where(Equipo.nombre.ilike(pattern, escape="\\"))
            competitions = select(Competicion.id).where(
                Competicion.nombre.ilike(pattern, escape="\\")
            )
            self.conditions.append(
                or_(
                    Partido.equipo_local_id.in_(teams),
                    Partido.equipo_visitante_id.in_(teams),
                    Partido.competicion_id.in_(competitions),
                )
            )
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "El rango de fechas está invertido.")
        if any(value is not None and value.tzinfo is None for value in (date_start, date_end)):
            raise HTTPException(422, "Los límites de hora requieren una zona horaria.")
        start = date_start or (
            dt.datetime.combine(date_from, dt.time(), dt.UTC) if date_from else None
        )
        end = date_end or (
            dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time(), dt.UTC)
            if date_to
            else None
        )
        if start and end and start >= end:
            raise HTTPException(422, "El rango de fechas está invertido.")
        if start:
            self.conditions.append(Partido.fecha >= start)
        if end:
            self.conditions.append(Partido.fecha < end)
        if attention:
            self.conditions.append(incomplete())


def match_page(session, filters):
    total = session.exec(select(func.count()).select_from(Partido).where(*filters.conditions)).one()
    order = (
        (Partido.id.desc(),)
        if filters.sort == "recent"
        else (
            (Partido.fecha.asc().nulls_last(), Partido.id.asc())
            if filters.sort == "oldest"
            else (Partido.fecha.desc().nulls_last(), Partido.id.desc())
        )
    )
    statement = matches_query(details=False).where(*filters.conditions).order_by(*order)
    rows = session.exec(
        statement.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    ).all()
    sources = match_sources(session, [row.id for row in rows])
    return {
        "items": [
            {
                **partido_publico(row, details=False).model_dump(mode="json"),
                "data_source": sources[row.id],
            }
            for row in rows
        ],
        "total": total,
        "page": filters.page,
        "page_size": filters.page_size,
    }


def match_sources(session, ids):
    """One indexed lookup per page; manual records are never labelled as live feeds."""
    result = {identity: {"provider": "manual", "verified_at": None} for identity in ids}
    if not ids:
        return result
    mappings = session.exec(
        select(ProviderMapping)
        .where(
            ProviderMapping.entity_type == "match",
            ProviderMapping.local_id.in_(ids),
            ProviderMapping.provider.in_(["api-football", "openfootball"]),
        )
        .order_by(ProviderMapping.provider.desc())
    ).all()
    for mapping in mappings:
        result[mapping.local_id] = {
            "provider": mapping.provider,
            "verified_at": mapping.verified_at,
        }
    return result


@router.get("/public/partidos/page")
def public_matches(filters: MatchFilters = Depends(), session: Session = Depends(get_session)):
    return match_page(session, filters)


@router.get("/partidos/page", dependencies=[Depends(verificar_token)])
def admin_matches(filters: MatchFilters = Depends(), session: Session = Depends(get_session)):
    return match_page(session, filters)


def detail(session, match_id):
    row = session.exec(matches_query().where(Partido.id == match_id)).first()
    if not row:
        raise HTTPException(404, "Partido no encontrado")
    result = partido_publico(row).model_dump(mode="json")
    result["data_source"] = match_sources(session, [match_id])[match_id]
    ids = {item.jugador_id for item in row.alineaciones}
    ids.update(
        value for item in row.eventos for value in (item.jugador_id, item.asistente_id) if value
    )
    names = (
        {
            player.id: player.nombre
            for player in session.exec(select(Jugador).where(Jugador.id.in_(ids))).all()
        }
        if ids
        else {}
    )
    for item in result["alineaciones"]:
        item["jugador_nombre"] = names.get(item["jugador_id"])
    for item in result["eventos"]:
        item["jugador_nombre"] = names.get(item["jugador_id"])
        item["asistente_nombre"] = names.get(item["asistente_id"])
    return result


@router.get("/public/partidos/{match_id}")
def public_detail(match_id: int, session: Session = Depends(get_session)):
    return detail(session, match_id)


@router.get("/partidos/{match_id}", dependencies=[Depends(verificar_token)])
def admin_detail(match_id: int, session: Session = Depends(get_session)):
    return detail(session, match_id)


def entity_page(session, model, search, page, page_size, conditions=()):
    conditions = list(conditions)
    if search.strip():
        pattern = "%" + search.strip().replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(model.nombre.ilike(pattern, escape="\\"))
    total = session.exec(select(func.count()).select_from(model).where(*conditions)).one()
    statement = teams_query() if model is Equipo else select(model)
    rows = session.exec(
        statement.where(*conditions)
        .order_by(model.nombre, model.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = (
        [EquipoConCompeticionesRead.model_validate(row) for row in rows]
        if model is Equipo
        else rows
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/public/equipos/filters")
def team_filters(session: Session = Depends(get_session)):
    return {
        "countries": session.exec(select(Equipo.pais).distinct().order_by(Equipo.pais)).all(),
        "types": session.exec(select(Equipo.tipo).distinct()).all(),
        "competitions": session.exec(select(Competicion).order_by(Competicion.nombre)).all(),
    }


@router.get("/public/equipos/page")
@router.get("/equipos/page", dependencies=[Depends(verificar_token)])
def public_teams(
    search: str = Query("", max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    competition_id: int | None = None,
    country: str | None = None,
    type: str | None = None,
    session: Session = Depends(get_session),
):
    conditions = (
        [
            Equipo.id.in_(
                select(Participacion.equipo_id).where(
                    Participacion.competicion_id == competition_id
                )
            )
        ]
        if competition_id
        else []
    )
    if country and country != "all":
        conditions.append(Equipo.pais == country)
    if type and type != "all":
        from src.models import TipoEquipo

        try:
            conditions.append(Equipo.tipo == TipoEquipo(type))
        except ValueError as exc:
            raise HTTPException(422, "Tipo de equipo no válido") from exc
    return entity_page(session, Equipo, search, page, page_size, conditions)


@router.get("/public/jugadores/page")
@router.get("/jugadores/page", dependencies=[Depends(verificar_token)])
def public_players(
    search: str = Query("", max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    team_id: int | None = None,
    session: Session = Depends(get_session),
):
    conditions = (
        [Jugador.id.in_(select(JugadorEquipo.jugador_id).where(JugadorEquipo.equipo_id == team_id))]
        if team_id
        else []
    )
    return entity_page(session, Jugador, search, page, page_size, conditions)


@router.get("/public/equipos/{entity_id}")
def public_team(entity_id: int, session: Session = Depends(get_session)):
    row = session.exec(teams_query().where(Equipo.id == entity_id)).first()
    if not row:
        raise HTTPException(404, "Equipo no encontrado")
    return EquipoConCompeticionesRead.model_validate(row)


@router.get("/public/jugadores/{entity_id}")
def public_player(entity_id: int, session: Session = Depends(get_session)):
    row = session.get(Jugador, entity_id)
    if not row:
        raise HTTPException(404, "Jugador no encontrado")
    return row


@router.get("/public/jugadores/{entity_id}/summary")
def player_summary(entity_id: int, session: Session = Depends(get_session)):
    if not session.get(Jugador, entity_id):
        raise HTTPException(404, "Jugador no encontrado")
    appearances = session.exec(
        select(func.count(func.distinct(AlineacionPartido.partido_id))).where(
            AlineacionPartido.jugador_id == entity_id
        )
    ).one()
    starts = session.exec(
        select(func.count(func.distinct(AlineacionPartido.partido_id))).where(
            AlineacionPartido.jugador_id == entity_id, AlineacionPartido.titular.is_(True)
        )
    ).one()
    goals = session.exec(
        select(func.count())
        .select_from(EventoPartido)
        .where(
            EventoPartido.jugador_id == entity_id,
            EventoPartido.tipo == "Goal",
            or_(
                EventoPartido.detalle.is_(None),
                ~EventoPartido.detalle.in_(["Own Goal", "Missed Penalty"]),
            ),
        )
    ).one()
    assists = session.exec(
        select(func.count())
        .select_from(EventoPartido)
        .where(EventoPartido.asistente_id == entity_id, EventoPartido.tipo == "Goal")
    ).one()
    cards = {}
    for key, detail_name in (("yellow_cards", "Yellow Card"), ("red_cards", "Red Card")):
        cards[key] = session.exec(
            select(func.count())
            .select_from(EventoPartido)
            .where(EventoPartido.jugador_id == entity_id, EventoPartido.detalle == detail_name)
        ).one()
    return {
        "appearances": appearances,
        "starts": starts,
        "goals": goals,
        "assists": assists,
        **cards,
        "coverage": "recorded_events",
    }


@router.get("/auth/session")
def session_info(request: Request, response: Response, username: str = Depends(verificar_token)):
    response.headers["Cache-Control"] = "no-store"
    return {
        "username": username,
        "role": request.state.role,
        "permissions": request.state.permissions,
    }


@router.get("/admin/summary", dependencies=[Depends(verificar_token)])
def summary(session: Session = Depends(get_session)):
    counts = {
        name: session.exec(select(func.count()).select_from(model)).one()
        for name, model in (
            ("matches", Partido),
            ("teams", Equipo),
            ("competitions", Competicion),
            ("players", Jugador),
            ("rosters", JugadorEquipo),
        )
    }
    for name, state in (
        ("scheduled", EstadoPartido.PROGRAMADO),
        ("live", EstadoPartido.VIVO),
        ("finished", EstadoPartido.FINALIZADO),
    ):
        counts[name] = session.exec(
            select(func.count()).select_from(Partido).where(Partido.estado == state)
        ).one()
    counts["incomplete"] = session.exec(
        select(func.count()).select_from(Partido).where(incomplete())
    ).one()
    counts["unregistered"] = session.exec(
        select(func.count())
        .select_from(Equipo)
        .where(~Equipo.id.in_(select(Participacion.equipo_id)))
    ).one()
    recent = session.exec(matches_query(details=False).order_by(Partido.id.desc()).limit(6)).all()
    return {"counts": counts, "recent": [partido_publico(row, details=False) for row in recent]}


@router.get("/health")
def health(session: Session = Depends(get_session)):
    session.exec(select(1)).one()
    return {"status": "ok"}
