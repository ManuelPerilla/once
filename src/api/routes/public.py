from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, exists, or_
from sqlmodel import Session, select

from src.api.dependencies import get_session
from src.football.queries import competitions_query, matches_query, partido_publico, teams_query
from src.football.standings import calculate_standings
from src.models import (
    Competicion,
    CompeticionPublicRead,
    Confederacion,
    Equipo,
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
    phase_id: int | None = None,
    group_id: int | None = None,
    session: Session = Depends(get_session),
):
    from src.football.projections import StandingsScopeError, read_standings

    competition = session.get(Competicion, competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competición no encontrada")
    if season_id is not None:
        season = session.get(Temporada, season_id)
        if not season or season.competicion_id != competition_id:
            raise HTTPException(
                status_code=404, detail="Temporada no encontrada para esta competición"
            )
        try:
            result = read_standings(session, season_id, phase_id, group_id)
        except StandingsScopeError as exc:
            raise HTTPException(422, str(exc)) from exc
        # Legacy clients only receive reviewed, scoped ONCE calculations.
        return result["calculated"].rows if result["calculated"] is not None else []
    if phase_id is not None or group_id is not None:
        raise HTTPException(422, "Selecciona una temporada antes de elegir fase o grupo")
    statement = select(Partido).where(
        Partido.competicion_id == competition_id,
        Partido.temporada_id.is_(None),
        Partido.estado == EstadoPartido.FINALIZADO,
    )
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


@router.get("/public/crests/", response_model=list[MediaAssetRead])
def public_crests(session: Session = Depends(get_session)):
    """One local query for attribution, restricted to badges currently in use."""
    selected = or_(
        *(
            and_(
                MediaAsset.entity_type == kind,
                exists().where(
                    model.id == MediaAsset.entity_id,
                    or_(model.logo == MediaAsset.original_url, model.logo == MediaAsset.local_url),
                ),
            )
            for kind, model in (
                ("team", Equipo),
                ("competition", Competicion),
                ("confederation", Confederacion),
            )
        )
    )
    return session.exec(
        select(MediaAsset).where(
            MediaAsset.tipo == "escudo",
            MediaAsset.license.is_not(None),
            MediaAsset.verified_at.is_not(None),
            selected,
        )
    ).all()
