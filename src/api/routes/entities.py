from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.api.persistence import save
from src.football.queries import teams_query
from src.football.rules import normalizar_competicion, validar_compatibilidad
from src.models import (
    Competicion,
    CompeticionBase,
    CompeticionRead,
    Confederacion,
    ConfederacionBase,
    ConfederacionRead,
    Equipo,
    EquipoBase,
    EquipoConCompeticionesRead,
    EquipoRead,
    TipoEquipo,
)

router = APIRouter(dependencies=[Depends(verificar_token)])


@router.post("/confederaciones/", response_model=ConfederacionRead)
def crear_confederacion(conf_in: ConfederacionBase, session: Session = Depends(get_session)):
    conf_db = Confederacion.model_validate(conf_in)
    return save(session, conf_db)


@router.get("/confederaciones/", response_model=list[ConfederacionRead])
def leer_confederaciones(session: Session = Depends(get_session)):
    return session.exec(select(Confederacion)).all()


@router.put("/confederaciones/{id}", response_model=ConfederacionRead)
def editar_confederacion(
    id: int, conf_in: ConfederacionBase, session: Session = Depends(get_session)
):
    conf = session.get(Confederacion, id)
    if not conf:
        raise HTTPException(status_code=404, detail="Confederación no encontrada")
    for key, value in conf_in.model_dump().items():
        setattr(conf, key, value)
    return save(session, conf)


@router.delete("/confederaciones/{id}")
def eliminar_confederacion(id: int, session: Session = Depends(get_session)):
    conf = session.get(Confederacion, id)
    if not conf:
        raise HTTPException(status_code=404, detail="Confederación no encontrada")

    for c in conf.competiciones:
        c.confederacion_id = None
    for e in conf.equipos:
        e.confederacion_id = None

    session.delete(conf)
    session.commit()
    return {"ok": True, "mensaje": "Confederación eliminada. Datos asociados intactos y huérfanos."}


@router.post("/competiciones/", response_model=CompeticionRead)
def crear_competicion(comp_in: CompeticionBase, session: Session = Depends(get_session)):
    normalizar_competicion(comp_in)

    comp_db = Competicion.model_validate(comp_in)
    return save(session, comp_db)


@router.get("/competiciones/", response_model=list[CompeticionRead])
def leer_competiciones(session: Session = Depends(get_session)):
    return session.exec(select(Competicion)).all()


@router.put("/competiciones/{id}", response_model=CompeticionRead)
def editar_competicion(id: int, comp_in: CompeticionBase, session: Session = Depends(get_session)):
    comp = session.get(Competicion, id)
    if not comp:
        raise HTTPException(status_code=404, detail="Competición no encontrada")

    normalizar_competicion(comp_in)

    for equipo in comp.equipos:
        validar_compatibilidad(equipo, comp_in)

    for key, value in comp_in.model_dump().items():
        setattr(comp, key, value)
    return save(session, comp)


@router.delete("/competiciones/{id}")
def eliminar_competicion(id: int, session: Session = Depends(get_session)):
    comp = session.get(Competicion, id)
    if not comp:
        raise HTTPException(status_code=404, detail="Competición no encontrada")

    for p in comp.partidos:
        p.competicion_id = None

    session.delete(comp)
    session.commit()
    return {"ok": True, "mensaje": "Competición eliminada."}


@router.post("/equipos/", response_model=EquipoRead)
def crear_equipo(equipo_in: EquipoBase, session: Session = Depends(get_session)):
    if equipo_in.tipo == TipoEquipo.SELECCION:
        equipo_in.pais = equipo_in.nombre

    equipo_db = Equipo.model_validate(equipo_in)
    return save(session, equipo_db)


@router.get("/equipos/", response_model=list[EquipoConCompeticionesRead])
def leer_equipos(session: Session = Depends(get_session)):
    return session.exec(teams_query()).all()


@router.put("/equipos/{id}", response_model=EquipoRead)
def editar_equipo(id: int, eq_in: EquipoBase, session: Session = Depends(get_session)):
    eq = session.get(Equipo, id)
    if not eq:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    if eq_in.tipo == TipoEquipo.SELECCION:
        eq_in.pais = eq_in.nombre

    for competicion in eq.competiciones:
        validar_compatibilidad(eq_in, competicion)

    for key, value in eq_in.model_dump().items():
        setattr(eq, key, value)
    return save(session, eq)


@router.delete("/equipos/{id}")
def eliminar_equipo(id: int, session: Session = Depends(get_session)):
    eq = session.get(Equipo, id)
    if not eq:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    for p in eq.partidos_local:
        p.equipo_local_id = None
    for p in eq.partidos_visitante:
        p.equipo_visitante_id = None

    session.delete(eq)
    session.commit()
    return {"ok": True, "mensaje": "Equipo eliminado."}


@router.post("/equipos/{equipo_id}/matricular/{competicion_id}")
def matricular_equipo(equipo_id: int, competicion_id: int, session: Session = Depends(get_session)):
    equipo = session.get(Equipo, equipo_id)
    competicion = session.get(Competicion, competicion_id)
    if not equipo or not competicion:
        raise HTTPException(status_code=404, detail="Equipo o Competición no encontrados")
    validar_compatibilidad(equipo, competicion)

    if competicion in equipo.competiciones:
        return {
            "ok": False,
            "mensaje": f"El equipo {equipo.nombre} ya participa en {competicion.nombre}",
        }

    equipo.competiciones.append(competicion)
    session.add(equipo)
    session.commit()
    return {
        "ok": True,
        "mensaje": f"{equipo.nombre} matriculado exitosamente en {competicion.nombre}",
    }
