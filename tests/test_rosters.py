import datetime as dt

import pytest
from sqlalchemy import event
from sqlmodel import Session

from src import database
from src.models import Equipo, Jugador, JugadorEquipo


@pytest.fixture
def roster(catalog):
    with Session(database.engine) as session:
        first, second = Jugador(nombre="Alex"), Jugador(nombre="Bruno")
        session.add_all([first, second])
        session.flush()
        rows = [
            JugadorEquipo(jugador_id=first.id, equipo_id=catalog["teams"][0]["id"], dorsal=9),
            JugadorEquipo(
                jugador_id=first.id,
                equipo_id=catalog["teams"][0]["id"],
                fecha_fin=dt.date(2050, 1, 1),
            ),
            JugadorEquipo(
                jugador_id=second.id,
                equipo_id=catalog["teams"][1]["id"],
                fecha_inicio=dt.date(2050, 1, 1),
            ),
        ]
        session.add_all(rows)
        session.commit()
        return {
            "player": first.id,
            "team": catalog["teams"][0]["id"],
            "ids": [row.id for row in rows],
        }


def test_rosters_are_authenticated_read_only(client, authenticated):
    authenticated.cookies.clear()
    assert client.get("/plantillas/").status_code == 401
    assert client.post("/plantillas/", json={}).status_code == 405


def test_rosters_filters_and_pagination_keep_memberships_separate(authenticated, roster):
    response = authenticated.get("/plantillas/", params={"page_size": 1})
    assert response.status_code == 200, response.text
    first = response.json()
    second = authenticated.get("/plantillas/?page_size=1&page=2").json()
    assert first["total"] == second["total"] == 3
    assert first["items"][0]["id"] == roster["ids"][0]
    assert second["items"][0]["id"] == roster["ids"][1]
    assert first["items"][0]["jugador_nombre"] == "Alex"
    assert first["items"][0]["equipo_nombre"] == "Local"
    filtered = authenticated.get(
        "/plantillas/",
        params={
            "equipo_id": roster["team"],
            "jugador_id": roster["player"],
            "estado": "active",
        },
    ).json()
    assert filtered["total"] == 1 and filtered["items"][0]["dorsal"] == 9
    by_team = authenticated.get("/plantillas/?search=visitaNte").json()
    assert by_team["total"] == 1 and by_team["items"][0]["jugador_nombre"] == "Bruno"
    assert authenticated.get("/plantillas/?search=%").json()["total"] == 0
    assert authenticated.get("/plantillas/?jugador_id=999999").json()["total"] == 0
    assert authenticated.get("/plantillas/?page=99").json()["items"] == []


def test_roster_closure_filter_does_not_claim_current_eligibility(authenticated, roster):
    open_rows = authenticated.get("/plantillas/?estado=active").json()
    closed = authenticated.get("/plantillas/?estado=closed").json()
    assert open_rows["total"] == 2
    assert any(row["fecha_inicio"] == "2050-01-01" for row in open_rows["items"])
    assert closed["total"] == 1 and closed["items"][0]["fecha_fin"] == "2050-01-01"


def test_rosters_handle_blank_names_and_legacy_missing_references(authenticated):
    with Session(database.engine) as session:
        player = Jugador(nombre="  ")
        team = Equipo(nombre="", logo="", tipo="club")
        session.add_all([player, team])
        session.flush()
        session.add(JugadorEquipo(jugador_id=player.id, equipo_id=team.id))
        session.commit()
    # Simulate an already damaged legacy row only inside the fixture's disposable database.
    with database.engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        disable = "PRAGMA foreign_keys=OFF" if sqlite else "SET session_replication_role = replica"
        enable = "PRAGMA foreign_keys=ON" if sqlite else "SET session_replication_role = origin"
        try:
            connection.exec_driver_sql(disable)
            connection.execute(
                JugadorEquipo.__table__.insert().values(jugador_id=999999, equipo_id=999999)
            )
            connection.commit()
        finally:
            connection.rollback()
            connection.exec_driver_sql(enable)
            connection.commit()
    response = authenticated.get("/plantillas/")
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert all(row["jugador_nombre"] == "Jugador no disponible" for row in response.json()["items"])
    assert all(row["equipo_nombre"] == "Equipo no disponible" for row in response.json()["items"])


def test_roster_list_uses_two_selects_and_no_writes(authenticated, roster):
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        assert authenticated.get("/plantillas/?page_size=1").status_code == 200
    finally:
        event.remove(database.engine, "before_cursor_execute", capture)
    assert len(statements) == 2
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)


@pytest.mark.parametrize("query", ["page=0", "page_size=101", "equipo_id=-1", "estado=live"])
def test_rosters_validate_filters(authenticated, query):
    assert authenticated.get(f"/plantillas/?{query}").status_code == 422
