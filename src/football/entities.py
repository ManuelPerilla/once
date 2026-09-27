"""Canonical local targets for external identities and media references."""

from src.models import (
    AlineacionPartido,
    Competicion,
    Confederacion,
    Equipo,
    Estadio,
    EstadisticasPartido,
    EventoPartido,
    Fase,
    Jugador,
    Partido,
    Temporada,
)

ENTITY_MODELS = {
    "confederation": Confederacion,
    "competition": Competicion,
    "team": Equipo,
    "match": Partido,
    "season": Temporada,
    "stage": Fase,
    "venue": Estadio,
    "player": Jugador,
    "event": EventoPartido,
    "lineup": AlineacionPartido,
    "statistics": EstadisticasPartido,
}
