from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.api.persistence import save
from src.models import (
    Competicion,
    Estadio,
    EstadioBase,
    EstadioRead,
    Fase,
    FaseBase,
    FaseRead,
    Jugador,
    JugadorBase,
    JugadorRead,
    Temporada,
    TemporadaBase,
    TemporadaRead,
)

router = APIRouter(dependencies=[Depends(verificar_token)])


@router.post("/temporadas/", response_model=TemporadaRead)
def crear_temporada(temporada_in: TemporadaBase, session: Session = Depends(get_session)):
    if not session.get(Competicion, temporada_in.competicion_id):
        raise HTTPException(status_code=404, detail="Competición no encontrada")
    temporada = Temporada.model_validate(temporada_in)
    return save(session, temporada)


@router.get("/temporadas/", response_model=list[TemporadaRead])
def leer_temporadas(session: Session = Depends(get_session)):
    return session.exec(select(Temporada)).all()


@router.post("/fases/", response_model=FaseRead)
def crear_fase(fase_in: FaseBase, session: Session = Depends(get_session)):
    if not session.get(Temporada, fase_in.temporada_id):
        raise HTTPException(status_code=404, detail="Temporada no encontrada")
    fase = Fase.model_validate(fase_in)
    return save(session, fase)


@router.get("/fases/", response_model=list[FaseRead])
def leer_fases(session: Session = Depends(get_session)):
    return session.exec(select(Fase)).all()


@router.post("/estadios/", response_model=EstadioRead)
def crear_estadio(estadio_in: EstadioBase, session: Session = Depends(get_session)):
    estadio = Estadio.model_validate(estadio_in)
    return save(session, estadio)


@router.get("/estadios/", response_model=list[EstadioRead])
def leer_estadios(session: Session = Depends(get_session)):
    return session.exec(select(Estadio)).all()


@router.post("/jugadores/", response_model=JugadorRead)
def crear_jugador(jugador_in: JugadorBase, session: Session = Depends(get_session)):
    jugador = Jugador.model_validate(jugador_in)
    return save(session, jugador)


@router.get("/jugadores/", response_model=list[JugadorRead])
def leer_jugadores(session: Session = Depends(get_session)):
    return session.exec(select(Jugador)).all()
