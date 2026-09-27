"""Read models with explicit loading: no extra query per list row."""

from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select

from src.models import Competicion, Equipo, Partido, PartidoConEstadisticasRead, PartidoReadDetail


def teams_query():
    return select(Equipo).options(selectinload(Equipo.competiciones))


def competitions_query():
    return select(Competicion).options(selectinload(Competicion.temporadas))


def matches_query(*, details=True):
    statement = select(Partido).options(
        *(
            joinedload(relation)
            for relation in (
                Partido.competicion_rel,
                Partido.temporada_rel,
                Partido.fase_rel,
                Partido.estadio_rel,
                Partido.equipo_local_rel,
                Partido.equipo_visitante_rel,
            )
        )
    )
    if details:
        statement = statement.options(
            *(
                selectinload(relation)
                for relation in (
                    Partido.estadisticas,
                    Partido.eventos,
                    Partido.alineaciones,
                )
            )
        )
    return statement


def partido_publico(partido: Partido, *, details=True):
    values = {
        **partido.model_dump(),
        "competicion": partido.competicion_rel,
        "temporada": partido.temporada_rel,
        "fase": partido.fase_rel,
        "estadio": partido.estadio_rel,
        "equipo_local": partido.equipo_local_rel,
        "equipo_visitante": partido.equipo_visitante_rel,
    }
    if details:
        return PartidoConEstadisticasRead(
            **values,
            estadisticas=partido.estadisticas,
            eventos=partido.eventos,
            alineaciones=partido.alineaciones,
        )
    return PartidoReadDetail(**values)
