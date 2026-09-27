"""Domain policies independent of HTTP and database sessions."""

from src.models import CompeticionBase, EquipoBase, TipoCompeticion, TipoEquipo


class FootballRuleError(ValueError):
    pass


def validar_compatibilidad(equipo: EquipoBase, competicion: CompeticionBase):
    if (
        competicion.tipo == TipoCompeticion.INTERNACIONAL_SELECCIONES
        and equipo.tipo != TipoEquipo.SELECCION
    ):
        raise FootballRuleError("A torneos de selecciones solo pueden entrar selecciones.")
    if (
        competicion.tipo != TipoCompeticion.INTERNACIONAL_SELECCIONES
        and equipo.tipo == TipoEquipo.SELECCION
    ):
        raise FootballRuleError("Una selección no puede disputar torneos de clubes.")

    if competicion.tipo in [TipoCompeticion.LIGA_NACIONAL, TipoCompeticion.COPA_NACIONAL]:
        if equipo.pais != competicion.pais:
            raise FootballRuleError(
                f"Un equipo de {equipo.pais} no puede jugar en la liga de {competicion.pais}."
            )

    if competicion.confederacion_id and competicion.confederacion_id != equipo.confederacion_id:
        raise FootballRuleError("El equipo no pertenece a la misma confederación del torneo.")


def normalizar_competicion(competicion: CompeticionBase):
    if competicion.tipo in (TipoCompeticion.LIGA_NACIONAL, TipoCompeticion.COPA_NACIONAL):
        if not competicion.pais or competicion.pais.lower() == "internacional":
            raise FootballRuleError("Ligas Nacionales deben tener un país específico.")
    else:
        competicion.pais = "Internacional"
