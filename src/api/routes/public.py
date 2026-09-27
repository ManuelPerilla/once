from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.api.dependencies import get_session
from src.football.queries import competitions_query, matches_query, partido_publico, teams_query
from src.football.standings import calculate_standings
from src.models import (
    Competicion,
    CompeticionPublicRead,
    EquipoConCompeticionesRead,
    Estadio,
    EstadioRead,
    EstadoPartido,
    Fase,
    FaseRead,
    Jugador,
    JugadorRead,
    MediaAsset,
    MediaAssetRead,
    Partido,
    PartidoConEstadisticasRead,
    StandingRow,
    Temporada,
    TemporadaRead,
)

router = APIRouter()


@router.get("/public/competiciones/", response_model=list[CompeticionPublicRead])
def public_competiciones(session: Session = Depends(get_session)):
    return session.exec(competitions_query()).all()


@router.get("/public/competiciones/{competition_id}/standings", response_model=list[StandingRow])
def public_standings(
    competition_id: int,
    season_id: int | None = None,
    session: Session = Depends(get_session),
):
    competition = session.get(Competicion, competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competición no encontrada")

    if season_id is not None:
        season = session.get(Temporada, season_id)
        if not season or season.competicion_id != competition_id:
            raise HTTPException(
                status_code=404, detail="Temporada no encontrada para esta competición"
            )

    statement = select(Partido).where(
        Partido.competicion_id == competition_id,
        Partido.estado == EstadoPartido.FINALIZADO,
    )
    if season_id is not None:
        statement = statement.where(Partido.temporada_id == season_id)

    return calculate_standings(competition.equipos, session.exec(statement).all())


@router.get("/public/temporadas/", response_model=list[TemporadaRead])
def public_temporadas(session: Session = Depends(get_session)):
    return session.exec(select(Temporada)).all()


@router.get("/public/fases/", response_model=list[FaseRead])
def public_fases(session: Session = Depends(get_session)):
    return session.exec(select(Fase)).all()


@router.get("/public/estadios/", response_model=list[EstadioRead])
def public_estadios(session: Session = Depends(get_session)):
    return session.exec(select(Estadio)).all()


@router.get("/public/jugadores/", response_model=list[JugadorRead])
def public_jugadores(session: Session = Depends(get_session)):
    return session.exec(select(Jugador)).all()


@router.get("/public/equipos/", response_model=list[EquipoConCompeticionesRead])
def public_equipos(session: Session = Depends(get_session)):
    return session.exec(teams_query()).all()


@router.get("/public/partidos/", response_model=list[PartidoConEstadisticasRead])
def public_partidos(session: Session = Depends(get_session)):
    partidos = session.exec(matches_query()).all()
    return [partido_publico(partido) for partido in partidos]


@router.get("/public/partidos/{partido_id}", response_model=PartidoConEstadisticasRead)
def public_detalle_partido(partido_id: int, session: Session = Depends(get_session)):
    partido = session.exec(matches_query().where(Partido.id == partido_id)).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido_publico(partido)


@router.get("/public/media/{entity_type}/{entity_id}", response_model=list[MediaAssetRead])
def public_media(entity_type: str, entity_id: int, session: Session = Depends(get_session)):
    statement = select(MediaAsset).where(
        MediaAsset.entity_type == entity_type,
        MediaAsset.entity_id == entity_id,
    )
    return session.exec(statement).all()
