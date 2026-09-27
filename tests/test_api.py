import datetime

import pytest
from sqlmodel import Session, select

from src import database
from src.models import EstadisticasPartido
from src.providers import APIFootballClient, WikidataClient


def test_leer_partidos_devuelve_lista_y_200(authenticated):
    response = authenticated.get("/partidos/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_crear_partido_inserta_datos_correctamente(authenticated, match_payload, catalog):
    response = authenticated.post("/partidos/", json=match_payload)
    assert response.status_code == 200
    saved = response.json()
    assert saved["equipo_local"]["id"] == catalog["teams"][0]["id"]
    assert saved["estado"] == "programado"
    detail = authenticated.get(f"/partidos/{saved['id']}")
    assert detail.status_code == 200
    assert detail.json()["competicion"]["id"] == match_payload["competicion_id"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("estado", "estado_inventado"),
        ("marcador_local", -1),
        ("marcador_visitante", -1),
        ("competicion_id", None),
        ("equipo_local_id", None),
        ("equipo_visitante_id", 0),
    ],
)
def test_invalid_match_input_returns_422(authenticated, match_payload, field, value):
    response = authenticated.post("/partidos/", json={**match_payload, field: value})
    assert response.status_code == 422
    assert authenticated.get("/partidos/").json() == []


@pytest.mark.parametrize("team_index", [2, 3, 4])
def test_unregistered_or_incompatible_teams_cannot_play(
    authenticated, match_payload, catalog, team_index
):
    payload = {**match_payload, "equipo_visitante_id": catalog["teams"][team_index]["id"]}
    response = authenticated.post("/partidos/", json=payload)
    assert response.status_code == 400
    assert authenticated.get("/partidos/").json() == []


def test_team_cannot_play_itself(authenticated, match_payload):
    payload = {**match_payload, "equipo_visitante_id": match_payload["equipo_local_id"]}
    assert authenticated.post("/partidos/", json=payload).status_code == 400


def test_unknown_team_returns_404(authenticated, match_payload):
    payload = {**match_payload, "equipo_visitante_id": 999999}
    assert authenticated.post("/partidos/", json=payload).status_code == 404


@pytest.mark.parametrize("team_index", [3, 4])
def test_incompatible_enrollment_is_rejected(authenticated, catalog, team_index):
    team_id = catalog["teams"][team_index]["id"]
    response = authenticated.post(f"/equipos/{team_id}/matricular/{catalog['comp']['id']}")
    assert response.status_code == 400


@pytest.mark.parametrize(
    "field,value", [("tipo", "seleccion"), ("pais", "España"), ("confederacion_id", None)]
)
def test_team_edit_cannot_invalidate_enrollment(authenticated, catalog, field, value):
    original = catalog["teams"][0]
    payload = {**original, field: value}
    assert authenticated.put(f"/equipos/{original['id']}", json=payload).status_code == 400
    saved = next(t for t in authenticated.get("/equipos/").json() if t["id"] == original["id"])
    assert saved[field] == original[field]


@pytest.mark.parametrize("field,value", [("tipo", "internacional_selecciones"), ("pais", "España")])
def test_competition_edit_cannot_invalidate_enrollment(authenticated, catalog, field, value):
    original = catalog["comp"]
    assert (
        authenticated.put(
            f"/competiciones/{original['id']}", json={**original, field: value}
        ).status_code
        == 400
    )
    saved = next(
        c for c in authenticated.get("/competiciones/").json() if c["id"] == original["id"]
    )
    assert saved[field] == original[field]


def statistics_payload(match_id):
    return {
        "partido_id": match_id,
        "posesion_local": 55,
        "posesion_visitante": 45,
        "tiros_puerta_local": 4,
        "tiros_puerta_visitante": 3,
    }


def test_delete_match_removes_only_its_statistics(authenticated, match_payload):
    first = authenticated.post("/partidos/", json=match_payload).json()["id"]
    second = authenticated.post("/partidos/", json=match_payload).json()["id"]
    for match_id in (first, second):
        assert (
            authenticated.post("/estadisticas/", json=statistics_payload(match_id)).status_code
            == 200
        )
    assert authenticated.delete(f"/partidos/{first}").status_code == 200
    assert authenticated.get(f"/partidos/{first}").status_code == 404
    assert authenticated.get(f"/partidos/{second}").status_code == 200
    with Session(database.engine) as session:
        remaining = session.exec(select(EstadisticasPartido)).all()
        assert [s.partido_id for s in remaining] == [second]


def test_delete_match_without_statistics(authenticated, match_payload):
    match_id = authenticated.post("/partidos/", json=match_payload).json()["id"]
    assert authenticated.delete(f"/partidos/{match_id}").status_code == 200
    assert authenticated.delete(f"/partidos/{match_id}").status_code == 404


def test_statistics_for_unknown_match_return_404(authenticated):
    assert authenticated.post("/estadisticas/", json=statistics_payload(999999)).status_code == 404


@pytest.mark.parametrize(
    "field,value", [("posesion_local", 101), ("posesion_visitante", -1), ("tiros_puerta_local", -1)]
)
def test_invalid_statistics_return_422(authenticated, match_payload, field, value):
    match_id = authenticated.post("/partidos/", json=match_payload).json()["id"]
    payload = {**statistics_payload(match_id), field: value}
    assert authenticated.post("/estadisticas/", json=payload).status_code == 422
    assert authenticated.get(f"/partidos/{match_id}").json()["estadisticas"] == []


def test_public_catalog_is_readable_without_login(client, catalog):
    # catalog fixture creates data through an authenticated setup client, then the
    # same TestClient can read the explicitly public endpoints without depending
    # on authorization headers for the route itself.
    client.cookies.clear()

    competitions = client.get("/public/competiciones/")
    teams = client.get("/public/equipos/")

    assert competitions.status_code == 200
    assert teams.status_code == 200
    assert any(item["id"] == catalog["comp"]["id"] for item in competitions.json())
    assert any(item["id"] == catalog["teams"][0]["id"] for item in teams.json())


def test_public_match_detail_is_readable_without_login(client, authenticated, match_payload):
    match_id = authenticated.post("/partidos/", json=match_payload).json()["id"]
    client.cookies.clear()

    response = client.get(f"/public/partidos/{match_id}")

    assert response.status_code == 200
    assert response.json()["id"] == match_id
    assert response.json()["equipo_local"]["id"] == match_payload["equipo_local_id"]


def test_public_unknown_match_returns_404(client):
    response = client.get("/public/partidos/999999")
    assert response.status_code == 404


def test_match_accepts_season_stage_venue_and_date(authenticated, match_payload, catalog):
    season = authenticated.post(
        "/temporadas/",
        json={
            "competicion_id": catalog["comp"]["id"],
            "nombre": "2026-II",
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-12-20",
            "activa": True,
        },
    )
    assert season.status_code == 200

    stage = authenticated.post(
        "/fases/",
        json={
            "temporada_id": season.json()["id"],
            "nombre": "Todos contra todos",
            "tipo": "liga",
            "orden": 1,
        },
    )
    assert stage.status_code == 200

    venue = authenticated.post(
        "/estadios/",
        json={
            "nombre": "Estadio de prueba",
            "ciudad": "Ibagué",
            "pais": "Colombia",
            "latitud": 4.4389,
            "longitud": -75.2322,
        },
    )
    assert venue.status_code == 200

    payload = {
        **match_payload,
        "temporada_id": season.json()["id"],
        "fase_id": stage.json()["id"],
        "estadio_id": venue.json()["id"],
        "fecha": "2026-09-21T20:00:00-05:00",
        "jornada": "Fecha 10",
    }
    created = authenticated.post("/partidos/", json=payload)
    assert created.status_code == 200, created.text
    saved = created.json()
    assert saved["temporada"]["nombre"] == "2026-II"
    assert saved["fase"]["nombre"] == "Todos contra todos"
    assert saved["estadio"]["ciudad"] == "Ibagué"
    assert saved["jornada"] == "Fecha 10"
    stored = datetime.datetime.fromisoformat(saved["fecha"].replace("Z", "+00:00"))
    expected = datetime.datetime.fromisoformat("2026-09-21T20:00:00-05:00")
    assert stored == expected


def test_match_rejects_stage_from_another_season(authenticated, match_payload, catalog):
    first = authenticated.post(
        "/temporadas/",
        json={
            "competicion_id": catalog["comp"]["id"],
            "nombre": "2026-I",
            "activa": False,
        },
    ).json()
    second = authenticated.post(
        "/temporadas/",
        json={
            "competicion_id": catalog["comp"]["id"],
            "nombre": "2026-II",
            "activa": True,
        },
    ).json()
    stage = authenticated.post(
        "/fases/",
        json={
            "temporada_id": first["id"],
            "nombre": "Fase 1",
            "tipo": "liga",
            "orden": 1,
        },
    ).json()

    response = authenticated.post(
        "/partidos/",
        json={
            **match_payload,
            "temporada_id": second["id"],
            "fase_id": stage["id"],
        },
    )
    assert response.status_code == 400


def test_events_and_lineups_are_exposed_in_public_match(
    client, authenticated, match_payload, catalog
):
    match_id = authenticated.post("/partidos/", json=match_payload).json()["id"]
    player = authenticated.post(
        "/jugadores/",
        json={
            "nombre": "Jugador de prueba",
            "posicion": "Delantero",
            "nacionalidad": "Colombia",
        },
    )
    assert player.status_code == 200
    player_id = player.json()["id"]

    lineup = authenticated.post(
        "/alineaciones/",
        json={
            "partido_id": match_id,
            "equipo_id": catalog["teams"][0]["id"],
            "jugador_id": player_id,
            "titular": True,
            "posicion": "9",
            "dorsal": 9,
            "orden": 1,
        },
    )
    assert lineup.status_code == 200

    event = authenticated.post(
        "/eventos/",
        json={
            "partido_id": match_id,
            "equipo_id": catalog["teams"][0]["id"],
            "jugador_id": player_id,
            "tipo": "gol",
            "minuto": 37,
            "adicional": 0,
            "detalle": "Remate",
        },
    )
    assert event.status_code == 200

    client.cookies.clear()
    public = client.get(f"/public/partidos/{match_id}")
    assert public.status_code == 200
    assert public.json()["eventos"][0]["tipo"] == "gol"
    assert public.json()["alineaciones"][0]["jugador_id"] == player_id


def test_provider_mapping_preserves_internal_ids(authenticated, catalog):
    response = authenticated.post(
        "/providers/mappings/",
        json={
            "provider": "example-provider",
            "entity_type": "team",
            "local_id": catalog["teams"][0]["id"],
            "external_id": "EXT-7788",
            "source_url": "https://example.com/team/EXT-7788",
        },
    )
    assert response.status_code == 200
    mapping = response.json()
    assert mapping["local_id"] == catalog["teams"][0]["id"]
    assert mapping["external_id"] == "EXT-7788"

    duplicate = authenticated.post(
        "/providers/mappings/",
        json={
            "provider": "example-provider",
            "entity_type": "team",
            "local_id": catalog["teams"][1]["id"],
            "external_id": "EXT-7788",
        },
    )
    assert duplicate.status_code == 409


def test_public_competitions_include_seasons(client, authenticated, catalog):
    created = authenticated.post(
        "/temporadas/",
        json={
            "competicion_id": catalog["comp"]["id"],
            "nombre": "2026",
            "activa": True,
        },
    )
    assert created.status_code == 200
    client.cookies.clear()

    response = client.get("/public/competiciones/")
    assert response.status_code == 200
    competition = next(item for item in response.json() if item["id"] == catalog["comp"]["id"])
    assert [season["nombre"] for season in competition["temporadas"]] == ["2026"]


def test_api_football_status_does_not_expose_secrets(authenticated, monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    response = authenticated.get("/providers/api-football/status")
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert "key" not in response.text.lower()


def test_api_football_preview_requires_configuration(authenticated, monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    response = authenticated.get(
        "/providers/api-football/preview/fixtures",
        params={"league_id": 239, "season": 2026},
    )
    assert response.status_code == 503


def test_wikidata_preview_rejects_invalid_qid_without_network(authenticated):
    response = authenticated.get("/providers/wikidata/preview/not-a-qid")
    assert response.status_code == 400


def test_api_football_sync_creates_and_updates_mapped_fixture(authenticated, catalog, monkeypatch):
    season = authenticated.post(
        "/temporadas/",
        json={
            "competicion_id": catalog["comp"]["id"],
            "nombre": "2026",
            "activa": True,
        },
    ).json()

    mappings = [
        {
            "provider": "api-football",
            "entity_type": "competition",
            "local_id": catalog["comp"]["id"],
            "external_id": "239",
        },
        {
            "provider": "api-football",
            "entity_type": "season",
            "local_id": season["id"],
            "external_id": "2026",
        },
        {
            "provider": "api-football",
            "entity_type": "team",
            "local_id": catalog["teams"][0]["id"],
            "external_id": "1001",
        },
        {
            "provider": "api-football",
            "entity_type": "team",
            "local_id": catalog["teams"][1]["id"],
            "external_id": "1002",
        },
    ]
    for mapping in mappings:
        response = authenticated.post("/providers/mappings/", json=mapping)
        assert response.status_code == 200, response.text

    score = {"home": 1, "away": 0}

    def fake_fixtures(_client, league_id, season_year):
        assert league_id == 239
        assert season_year == 2026
        return {
            "results": 1,
            "response": [
                {
                    "fixture": {
                        "id": 778899,
                        "date": "2026-09-21T20:00:00+00:00",
                        "status": {"short": "FT"},
                        "venue": {"id": 55, "name": "Estadio Integración", "city": "Ibagué"},
                    },
                    "league": {"id": 239, "season": 2026, "round": "Clausura - 10"},
                    "teams": {
                        "home": {"id": 1001, "name": "Local"},
                        "away": {"id": 1002, "name": "Visitante"},
                    },
                    "goals": dict(score),
                }
            ],
        }

    monkeypatch.setattr(APIFootballClient, "fixtures", fake_fixtures)

    first = authenticated.post(
        f"/providers/api-football/sync/competition/{catalog['comp']['id']}/season/{season['id']}"
    )
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 1
    assert first.json()["updated"] == 0

    matches = authenticated.get("/partidos/").json()
    assert len(matches) == 1
    assert matches[0]["jornada"] == "Clausura - 10"
    assert matches[0]["estadio"]["nombre"] == "Estadio Integración"
    assert matches[0]["marcador_local"] == 1

    score["home"] = 2
    score["away"] = 2
    second = authenticated.post(
        f"/providers/api-football/sync/competition/{catalog['comp']['id']}/season/{season['id']}"
    )
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["updated"] == 1

    matches = authenticated.get("/partidos/").json()
    assert len(matches) == 1
    assert matches[0]["marcador_local"] == 2
    assert matches[0]["marcador_visitante"] == 2


def test_api_football_sync_skips_unmapped_teams(authenticated, catalog, monkeypatch):
    season = authenticated.post(
        "/temporadas/",
        json={
            "competicion_id": catalog["comp"]["id"],
            "nombre": "2026",
            "activa": True,
        },
    ).json()
    for mapping in [
        {
            "provider": "api-football",
            "entity_type": "competition",
            "local_id": catalog["comp"]["id"],
            "external_id": "239",
        },
        {
            "provider": "api-football",
            "entity_type": "season",
            "local_id": season["id"],
            "external_id": "2026",
        },
    ]:
        assert authenticated.post("/providers/mappings/", json=mapping).status_code == 200

    monkeypatch.setattr(
        APIFootballClient,
        "fixtures",
        lambda *_args, **_kwargs: {
            "results": 1,
            "response": [
                {
                    "fixture": {"id": 9988, "status": {"short": "NS"}, "venue": {}},
                    "league": {"round": "Fecha 1"},
                    "teams": {
                        "home": {"id": 555, "name": "Desconocido A"},
                        "away": {"id": 556, "name": "Desconocido B"},
                    },
                    "goals": {"home": None, "away": None},
                }
            ],
        },
    )

    response = authenticated.post(
        f"/providers/api-football/sync/competition/{catalog['comp']['id']}/season/{season['id']}"
    )
    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert response.json()["skipped"][0]["reason"] == "team_mapping_missing"
    assert authenticated.get("/partidos/").json() == []


def test_public_standings_are_computed_from_finished_matches(
    client, authenticated, match_payload, catalog
):
    created = authenticated.post(
        "/partidos/",
        json={
            **match_payload,
            "marcador_local": 2,
            "marcador_visitante": 1,
            "estado": "finalizado",
        },
    )
    assert created.status_code == 200

    client.cookies.clear()
    response = client.get(f"/public/competiciones/{catalog['comp']['id']}/standings")
    assert response.status_code == 200
    rows = response.json()
    assert rows[0]["team"]["id"] == catalog["teams"][0]["id"]
    assert rows[0]["points"] == 3
    assert rows[0]["goal_difference"] == 1
    assert rows[1]["team"]["id"] == catalog["teams"][1]["id"]
    assert rows[1]["points"] == 0


def test_api_football_match_detail_sync_is_idempotent_and_keeps_manual_rows(
    authenticated, catalog, monkeypatch
):
    season = authenticated.post(
        "/temporadas/",
        json={
            "competicion_id": catalog["comp"]["id"],
            "nombre": "2026",
            "activa": True,
        },
    ).json()

    for mapping in [
        {
            "provider": "api-football",
            "entity_type": "competition",
            "local_id": catalog["comp"]["id"],
            "external_id": "239",
        },
        {
            "provider": "api-football",
            "entity_type": "season",
            "local_id": season["id"],
            "external_id": "2026",
        },
        {
            "provider": "api-football",
            "entity_type": "team",
            "local_id": catalog["teams"][0]["id"],
            "external_id": "1001",
        },
        {
            "provider": "api-football",
            "entity_type": "team",
            "local_id": catalog["teams"][1]["id"],
            "external_id": "1002",
        },
    ]:
        assert authenticated.post("/providers/mappings/", json=mapping).status_code == 200

    monkeypatch.setattr(
        APIFootballClient,
        "fixtures",
        lambda *_args, **_kwargs: {
            "results": 1,
            "response": [
                {
                    "fixture": {
                        "id": 778899,
                        "date": "2026-09-21T20:00:00+00:00",
                        "status": {"short": "FT"},
                        "venue": {},
                    },
                    "league": {"round": "Clausura - 10"},
                    "teams": {
                        "home": {"id": 1001, "name": "Local"},
                        "away": {"id": 1002, "name": "Visitante"},
                    },
                    "goals": {"home": 2, "away": 1},
                }
            ],
        },
    )
    synced = authenticated.post(
        f"/providers/api-football/sync/competition/{catalog['comp']['id']}/season/{season['id']}"
    )
    assert synced.status_code == 200
    match = authenticated.get("/partidos/").json()[0]

    manual_player = authenticated.post("/jugadores/", json={"nombre": "Jugador manual"}).json()
    manual_event = authenticated.post(
        "/eventos/",
        json={
            "partido_id": match["id"],
            "equipo_id": catalog["teams"][0]["id"],
            "jugador_id": manual_player["id"],
            "tipo": "Nota editorial",
            "minuto": 5,
            "detalle": "Registro manual",
        },
    )
    assert manual_event.status_code == 200

    events_payload = {
        "results": 1,
        "response": [
            {
                "time": {"elapsed": 31, "extra": None},
                "team": {"id": 1001, "name": "Local"},
                "player": {"id": 501, "name": "Delantero API"},
                "assist": {"id": 502, "name": "Asistente API"},
                "type": "Goal",
                "detail": "Normal Goal",
            }
        ],
    }
    lineups_payload = {
        "results": 2,
        "response": [
            {
                "team": {"id": 1001, "name": "Local"},
                "formation": "4-2-3-1",
                "startXI": [
                    {
                        "player": {
                            "id": 501,
                            "name": "Delantero API",
                            "number": 9,
                            "pos": "F",
                            "grid": "4:1",
                        }
                    },
                ],
                "substitutes": [],
            },
            {
                "team": {"id": 1002, "name": "Visitante"},
                "formation": "4-3-3",
                "startXI": [
                    {
                        "player": {
                            "id": 601,
                            "name": "Arquero API",
                            "number": 1,
                            "pos": "G",
                            "grid": "1:1",
                        }
                    },
                ],
                "substitutes": [],
            },
        ],
    }
    statistics_payload = {
        "results": 2,
        "response": [
            {
                "team": {"id": 1001, "name": "Local"},
                "statistics": [
                    {"type": "Ball Possession", "value": "57%"},
                    {"type": "Shots on Goal", "value": 6},
                ],
            },
            {
                "team": {"id": 1002, "name": "Visitante"},
                "statistics": [
                    {"type": "Ball Possession", "value": "43%"},
                    {"type": "Shots on Goal", "value": 2},
                ],
            },
        ],
    }

    monkeypatch.setattr(APIFootballClient, "fixture_events", lambda *_: events_payload)
    monkeypatch.setattr(APIFootballClient, "fixture_lineups", lambda *_: lineups_payload)
    monkeypatch.setattr(APIFootballClient, "fixture_statistics", lambda *_: statistics_payload)

    first = authenticated.post(f"/providers/api-football/sync/match/{match['id']}")
    assert first.status_code == 200, first.text
    assert first.json()["events"] == 1
    assert first.json()["lineup_entries"] == 2
    assert first.json()["statistics"] is True
    assert first.json()["players_touched"] == 3

    second = authenticated.post(f"/providers/api-football/sync/match/{match['id']}")
    assert second.status_code == 200

    detail = authenticated.get(f"/partidos/{match['id']}").json()
    assert len(detail["eventos"]) == 2
    assert sorted(event["source"] for event in detail["eventos"] if event["source"]) == [
        "api-football"
    ]
    assert any(
        event["tipo"] == "Nota editorial" and event["source"] is None for event in detail["eventos"]
    )
    assert len(detail["alineaciones"]) == 2
    assert all(item["source"] == "api-football" for item in detail["alineaciones"])
    provider_stats = [row for row in detail["estadisticas"] if row["source"] == "api-football"]
    assert len(provider_stats) == 1
    assert provider_stats[0]["posesion_local"] == 57
    assert provider_stats[0]["tiros_puerta_visitante"] == 2

    players = authenticated.get("/jugadores/").json()
    assert len([player for player in players if player["nombre"] == "Delantero API"]) == 1

    snapshots = authenticated.get(
        "/providers/snapshots/",
        params={"provider": "api-football", "entity_type": "match", "local_id": match["id"]},
    )
    assert snapshots.status_code == 200
    assert {item["kind"] for item in snapshots.json()} == {
        "fixture",
        "events",
        "lineups",
        "statistics",
    }


def test_api_football_match_detail_sync_requires_match_mapping(authenticated, match_payload):
    match_id = authenticated.post("/partidos/", json=match_payload).json()["id"]
    response = authenticated.post(f"/providers/api-football/sync/match/{match_id}")
    assert response.status_code == 400


def test_wikidata_media_import_upserts_asset_and_mapping(authenticated, catalog, monkeypatch):
    media_payload = {
        "qid": "Q123",
        "filename": "Example stadium.jpg",
        "source_url": "https://commons.wikimedia.org/wiki/File:Example_stadium.jpg",
        "original_url": "https://upload.wikimedia.org/example-stadium.jpg",
        "width": 1600,
        "height": 900,
        "mime_type": "image/jpeg",
        "author": "Fotógrafo de prueba",
        "credit": "Wikimedia Commons",
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "description": "Imagen de prueba",
        "attribution_required": "true",
    }

    monkeypatch.setattr(
        WikidataClient,
        "commons_media",
        lambda _client, qid: {**media_payload, "qid": qid.upper()},
    )

    path = f"/providers/wikidata/import-media/team/{catalog['teams'][0]['id']}/Q123"
    first = authenticated.post(path)
    assert first.status_code == 200, first.text
    asset = first.json()
    assert asset["source"] == "wikimedia-commons"
    assert asset["license"] == "CC BY-SA 4.0"
    assert asset["author"] == "Fotógrafo de prueba"
    assert asset["remote_id"] == "Example stadium.jpg"

    second_payload = {**media_payload, "credit": "Crédito actualizado"}
    monkeypatch.setattr(
        WikidataClient,
        "commons_media",
        lambda _client, qid: {**second_payload, "qid": qid.upper()},
    )
    second = authenticated.post(path)
    assert second.status_code == 200
    assert second.json()["id"] == asset["id"]
    assert second.json()["credit"] == "Crédito actualizado"

    assets = authenticated.get("/media/").json()
    assert len([item for item in assets if item["entity_type"] == "team"]) == 1

    mappings = authenticated.get("/providers/mappings/").json()
    wikidata = [
        item
        for item in mappings
        if item["provider"] == "wikidata"
        and item["entity_type"] == "team"
        and item["external_id"] == "Q123"
    ]
    assert len(wikidata) == 1
    assert wikidata[0]["local_id"] == catalog["teams"][0]["id"]


def test_wikidata_media_import_rejects_qid_linked_to_other_entity(
    authenticated, catalog, monkeypatch
):
    monkeypatch.setattr(
        WikidataClient,
        "commons_media",
        lambda *_args, **_kwargs: {
            "qid": "Q123",
            "filename": "Example.jpg",
            "source_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
            "original_url": "https://upload.wikimedia.org/example.jpg",
            "width": 100,
            "height": 100,
            "mime_type": "image/jpeg",
            "author": None,
            "credit": None,
            "license": "CC0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        },
    )

    first = authenticated.post(
        f"/providers/wikidata/import-media/team/{catalog['teams'][0]['id']}/Q123"
    )
    assert first.status_code == 200

    second = authenticated.post(
        f"/providers/wikidata/import-media/team/{catalog['teams'][1]['id']}/Q123"
    )
    assert second.status_code == 409
