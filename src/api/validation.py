from fastapi import HTTPException
from sqlmodel import Session

from src.models import Competicion, Estadio, Fase, PartidoCreate, Temporada


def validar_contexto_partido(
    partido_in: PartidoCreate, comp: Competicion, session: Session
) -> None:
    if partido_in.temporada_id:
        temporada = session.get(Temporada, partido_in.temporada_id)
        if not temporada:
            raise HTTPException(status_code=404, detail="Temporada no encontrada")
        if temporada.competicion_id != comp.id:
            raise HTTPException(
                status_code=400, detail="La temporada no pertenece a la competición"
            )

    if partido_in.fase_id:
        fase = session.get(Fase, partido_in.fase_id)
        if not fase:
            raise HTTPException(status_code=404, detail="Fase no encontrada")
        if not partido_in.temporada_id or fase.temporada_id != partido_in.temporada_id:
            raise HTTPException(
                status_code=400, detail="La fase no pertenece a la temporada indicada"
            )

    if partido_in.estadio_id and not session.get(Estadio, partido_in.estadio_id):
        raise HTTPException(status_code=404, detail="Estadio no encontrado")
