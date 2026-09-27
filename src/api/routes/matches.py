from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from src.api.dependencies import get_session, verificar_token
from src.api.persistence import save
from src.api.validation import validar_contexto_partido
from src.football.queries import matches_query, partido_publico
from src.football.rules import validar_compatibilidad
from src.models import (
    AlineacionPartido,
    AlineacionPartidoBase,
    AlineacionPartidoRead,
    Competicion,
    Equipo,
    EstadisticasCreate,
    EstadisticasPartido,
    EventoPartido,
    EventoPartidoBase,
    EventoPartidoRead,
    Jugador,
    Partido,
    PartidoConEstadisticasRead,
    PartidoCreate,
    PartidoReadDetail,
)

router = APIRouter(dependencies=[Depends(verificar_token)])


@router.post("/eventos/", response_model=EventoPartidoRead)
def crear_evento(evento_in: EventoPartidoBase, session: Session = Depends(get_session)):
    partido = session.get(Partido, evento_in.partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if evento_in.equipo_id and not session.get(Equipo, evento_in.equipo_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if evento_in.jugador_id and not session.get(Jugador, evento_in.jugador_id):
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if evento_in.asistente_id and not session.get(Jugador, evento_in.asistente_id):
        raise HTTPException(status_code=404, detail="Asistente no encontrado")
    if evento_in.equipo_id not in (None, partido.equipo_local_id, partido.equipo_visitante_id):
        raise HTTPException(
            status_code=400, detail="El equipo del evento no participa en el partido"
        )

    evento = EventoPartido.model_validate(evento_in)
    return save(session, evento)


@router.post("/alineaciones/", response_model=AlineacionPartidoRead)
def crear_alineacion(alineacion_in: AlineacionPartidoBase, session: Session = Depends(get_session)):
    partido = session.get(Partido, alineacion_in.partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if alineacion_in.equipo_id not in (partido.equipo_local_id, partido.equipo_visitante_id):
        raise HTTPException(status_code=400, detail="El equipo no participa en el partido")
    if not session.get(Jugador, alineacion_in.jugador_id):
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    alineacion = AlineacionPartido.model_validate(alineacion_in)
    return save(session, alineacion)


@router.post("/partidos/", response_model=PartidoReadDetail)
def crear_partido(partido_in: PartidoCreate, session: Session = Depends(get_session)):
    comp = session.get(Competicion, partido_in.competicion_id)
    local = session.get(Equipo, partido_in.equipo_local_id)
    visita = session.get(Equipo, partido_in.equipo_visitante_id)

    if not comp or not local or not visita:
        raise HTTPException(status_code=404, detail="Faltan datos de Competición o Equipos")
    if local.id == visita.id:
        raise HTTPException(status_code=400, detail="Un equipo no puede jugar contra sí mismo")

    validar_contexto_partido(partido_in, comp, session)

    for equipo in (local, visita):
        validar_compatibilidad(equipo, comp)
        if comp not in equipo.competiciones:
            raise HTTPException(
                status_code=400,
                detail=f"{equipo.nombre} no está matriculado en {comp.nombre}.",
            )

    partido_db = Partido.model_validate(partido_in)
    session.add(partido_db)
    session.commit()
    session.refresh(partido_db)
    return partido_publico(partido_db, details=False)


@router.get("/partidos/", response_model=list[PartidoReadDetail])
def leer_partidos(session: Session = Depends(get_session)):
    partidos = session.exec(matches_query(details=False)).all()
    return [partido_publico(partido, details=False) for partido in partidos]


@router.get("/partidos/{partido_id}", response_model=PartidoConEstadisticasRead)
def leer_detalle_partido(partido_id: int, session: Session = Depends(get_session)):
    partido = session.exec(matches_query().where(Partido.id == partido_id)).first()
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido_publico(partido)


@router.post("/estadisticas/", response_model=EstadisticasPartido)
def crear_estadisticas(estadisticas: EstadisticasCreate, session: Session = Depends(get_session)):
    if not session.get(Partido, estadisticas.partido_id):
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    estadisticas_db = EstadisticasPartido.model_validate(estadisticas)
    return save(session, estadisticas_db)


@router.delete("/partidos/{partido_id}")
def eliminar_partido(partido_id: int, session: Session = Depends(get_session)):
    partido = session.get(Partido, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    session.delete(partido)
    session.commit()
    return {"ok": True, "mensaje": f"Partido {partido_id} eliminado correctamente"}
