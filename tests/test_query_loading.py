"""Query growth regression guards using actual HTTP serialization."""

from contextlib import contextmanager

from sqlalchemy import event

from src import database


@contextmanager
def select_queries():
    statements = []

    def record(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(database.engine, "before_cursor_execute", record)


def test_catalog_lists_load_relationships_in_batches(authenticated, catalog):
    for path, field in (
        ("/public/equipos/", "competiciones"),
        ("/equipos/", "competiciones"),
        ("/public/competiciones/", "temporadas"),
    ):
        with select_queries() as statements:
            response = authenticated.get(path)
        assert response.status_code == 200
        assert len(response.json()) > 1
        assert all(field in row for row in response.json())
        assert len(statements) <= 2


def test_match_queries_remain_bounded_as_the_list_grows(authenticated, match_payload):
    first = authenticated.post("/partidos/", json=match_payload).json()
    stats = {
        "partido_id": first["id"],
        "posesion_local": 60,
        "posesion_visitante": 40,
        "tiros_puerta_local": 4,
        "tiros_puerta_visitante": 2,
    }
    assert authenticated.post("/estadisticas/", json=stats).status_code == 200

    def read(path, limit):
        with select_queries() as statements:
            response = authenticated.get(path)
        assert response.status_code == 200
        assert len(statements) <= limit
        return response.json(), len(statements)

    _, baseline = read("/public/partidos/", 4)
    for _ in range(12):
        assert authenticated.post("/partidos/", json=match_payload).status_code == 200
    matches, count = read("/public/partidos/", 4)
    assert count == baseline
    assert len(matches) == 13
    detailed = next(item for item in matches if item["id"] == first["id"])
    assert detailed["estadisticas"][0]["posesion_local"] == 60
    assert detailed["equipo_local"]["id"] == match_payload["equipo_local_id"]
    # Provenance adds one bounded lookup, independent of the number of matches.
    public_detail = read(f"/public/partidos/{first['id']}", 5)[0]
    assert public_detail.pop("data_source")["provider"] == "manual"
    assert public_detail == detailed
    admin_detail = read(f"/partidos/{first['id']}", 5)[0]
    assert admin_detail.pop("data_source")["provider"] == "manual"
    assert admin_detail == detailed
    admin, _ = read("/partidos/", 1)
    assert len(admin) == 13 and "estadisticas" not in admin[0]
