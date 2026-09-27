"""Read-only membership inventory, distinct from match lineups and eligibility."""

from sqlalchemy import func, or_
from sqlmodel import select

from src.models import Equipo, Jugador, JugadorEquipo, PlantillaPage, PlantillaRead


def roster_page(
    session, equipo_id=None, jugador_id=None, estado=None, search=None, page=1, page_size=20
):
    statement = (
        select(JugadorEquipo, Jugador.nombre, Equipo.nombre)
        .outerjoin(Jugador, Jugador.id == JugadorEquipo.jugador_id)
        .outerjoin(Equipo, Equipo.id == JugadorEquipo.equipo_id)
    )
    if equipo_id is not None:
        statement = statement.where(JugadorEquipo.equipo_id == equipo_id)
    if jugador_id is not None:
        statement = statement.where(JugadorEquipo.jugador_id == jugador_id)
    if estado == "active":
        statement = statement.where(JugadorEquipo.fecha_fin.is_(None))
    elif estado == "closed":
        statement = statement.where(JugadorEquipo.fecha_fin.is_not(None))
    if search and search.strip():
        statement = statement.where(
            or_(
                Jugador.nombre.icontains(search.strip(), autoescape=True),
                Equipo.nombre.icontains(search.strip(), autoescape=True),
            )
        )
    total = session.exec(select(func.count()).select_from(statement.subquery())).one()
    rows = session.exec(
        statement.order_by(
            Jugador.nombre.asc().nulls_last(), Equipo.nombre.asc().nulls_last(), JugadorEquipo.id
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PlantillaPage(
        items=[
            PlantillaRead(
                **row.model_dump(),
                jugador_nombre=player_name.strip()
                if player_name and player_name.strip()
                else "Jugador no disponible",
                equipo_nombre=team_name.strip()
                if team_name and team_name.strip()
                else "Equipo no disponible",
            )
            for row, player_name, team_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
