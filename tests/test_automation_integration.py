"""Regression boundaries between canonical data, automatic work and bounded reads."""

import datetime as dt
import gzip
from types import SimpleNamespace

import httpx
import pytest
from sqlmodel import Session, select

from src import database
from src.models import Partido, ProviderMapping, Temporada
from src.providers.automation import CatalogHandler, Transport, validate_scope_config
from src.providers.media_cache import cache_asset
from src.providers.sync import SyncConfigurationError, sync_competition_fixtures
from src.sync.models import SyncScope


def test_bounded_transport_decodes_compressed_responses_once():
    calls = []
    context = SimpleNamespace(
        reserve_request=lambda provider: calls.append(provider),
        report_quota=lambda **kwargs: None,
    )

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-encoding": "gzip", "content-type": "application/json"},
            content=gzip.compress(b'{"entities":{"Q35572":{"id":"Q35572"}}}'),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = Transport(context, client)("https://www.wikidata.org/w/api.php")
    assert response.json()["entities"]["Q35572"]["id"] == "Q35572"
    assert calls == ["wikidata"]
    assert "content-encoding" not in response.headers


def test_paged_matches_filter_before_limit_and_never_include_details(authenticated, match_payload):
    with Session(database.engine) as session:
        for index in range(45):
            session.add(
                Partido(
                    **{**match_payload, "estado": "finalizado" if index % 2 else "programado"},
                    fecha=dt.datetime(2025, 1, 1, tzinfo=dt.UTC) + dt.timedelta(days=index),
                )
            )
        session.commit()
    result = authenticated.get(
        "/public/partidos/page",
        params={"status": "finished", "page": 2, "page_size": 5, "sort": "oldest"},
    )
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["total"] == 22 and len(page["items"]) == 5
    assert page["items"][0]["fecha"].startswith("2025-01-12")
    assert all("eventos" not in row and "alineaciones" not in row for row in page["items"])
    assert authenticated.get("/public/partidos/page?season_id=oops").status_code == 422
    assert authenticated.get("/public/partidos/page?page_size=10000").status_code == 422


def test_session_summary_and_full_team_facets_are_independent_of_match_pages(
    authenticated, match_payload
):
    authenticated.post("/partidos/", json=match_payload)
    assert authenticated.get("/auth/session").json()["username"] == "operador_test"
    assert authenticated.get("/admin/summary").json()["counts"]["matches"] == 1
    facets = authenticated.get("/public/equipos/filters")
    assert facets.status_code == 200
    assert "Colombia" in facets.json()["countries"]
    authenticated.cookies.clear()
    assert authenticated.get("/auth/session").status_code == 401
    assert authenticated.get("/partidos/page").status_code == 401


def linked_fixture(authenticated, catalog):
    season = authenticated.post(
        "/temporadas/", json={"competicion_id": catalog["comp"]["id"], "nombre": "2026"}
    ).json()
    for kind, local, external in (
        ("competition", catalog["comp"]["id"], "239"),
        ("season", season["id"], "2026"),
        ("team", catalog["teams"][0]["id"], "100"),
        ("team", catalog["teams"][1]["id"], "101"),
    ):
        result = authenticated.post(
            "/providers/mappings/",
            json={
                "provider": "api-football",
                "entity_type": kind,
                "local_id": local,
                "external_id": external,
            },
        )
        assert result.status_code == 200, result.text
    source = {
        "fixture": {"id": 123, "status": {"short": "NS"}},
        "league": {"id": 239, "season": 2026},
        "teams": {"home": {"id": 100}, "away": {"id": 101}},
        "goals": {"home": None, "away": None},
    }
    return season, source


def test_legacy_sync_endpoint_cannot_bypass_global_pause(authenticated, catalog):
    season, _ = linked_fixture(authenticated, catalog)
    response = authenticated.post(
        f"/providers/api-football/sync/competition/{catalog['comp']['id']}/season/{season['id']}"
    )
    assert response.status_code == 409
    assert authenticated.get("/public/partidos/page").json()["total"] == 0


def test_unknown_scores_stay_unknown_and_partial_observation_keeps_valid_values(
    authenticated, catalog
):
    season, source = linked_fixture(authenticated, catalog)
    with Session(database.engine) as session:
        sync_competition_fixtures(
            session, catalog["comp"]["id"], season["id"], {"response": [source]}
        )
        match = session.exec(select(Partido)).one()
        assert match.marcador_local is None and match.marcador_visitante is None
        source["goals"] = {"home": 2, "away": 1}
        sync_competition_fixtures(
            session, catalog["comp"]["id"], season["id"], {"response": [source]}
        )
        source["goals"] = {"home": None}
        sync_competition_fixtures(
            session, catalog["comp"]["id"], season["id"], {"response": [source]}
        )
        session.refresh(match)
        assert (match.marcador_local, match.marcador_visitante) == (2, 1)


def test_fixture_from_different_league_is_rejected_before_any_write(authenticated, catalog):
    season, source = linked_fixture(authenticated, catalog)
    source["league"]["id"] = 999
    with Session(database.engine) as session:
        with pytest.raises(SyncConfigurationError, match="otra competición"):
            sync_competition_fixtures(
                session, catalog["comp"]["id"], season["id"], {"response": [source]}
            )
        assert session.exec(select(Partido)).all() == []


def test_two_competitions_can_map_same_year(authenticated, catalog):
    first, _ = linked_fixture(authenticated, catalog)
    second_comp = authenticated.post(
        "/competiciones/",
        json={"nombre": "Otra liga", "logo": "", "pais": "Colombia", "tipo": "liga_nacional"},
    ).json()
    second = authenticated.post(
        "/temporadas/", json={"competicion_id": second_comp["id"], "nombre": "2026"}
    ).json()
    for kind, local, external in (
        ("competition", second_comp["id"], "240"),
        ("season", second["id"], "2026"),
    ):
        response = authenticated.post(
            "/providers/mappings/",
            json={
                "provider": "api-football",
                "entity_type": kind,
                "local_id": local,
                "external_id": external,
            },
        )
        assert response.status_code == 200, response.text
    with Session(database.engine) as session:
        mappings = session.exec(
            select(ProviderMapping).where(ProviderMapping.entity_type == "season")
        ).all()
        assert {row.external_scope for row in mappings} == {"league:239", "league:240"}
        assert session.get(Temporada, first["id"])


def test_catalog_payload_does_not_invent_missing_entities(authenticated):
    with Session(database.engine) as session:
        scope = SyncScope(
            name="Catálogo",
            provider="wikidata",
            kind="catalog",
            selector={"collection": "colombia"},
        )
        session.add(scope)
        session.commit()
        result = CatalogHandler().apply(
            session,
            scope,
            {"collection": "colombia", "entities": {}},
            SimpleNamespace(job_id="test", observed_at=None),
        )
        assert result["changed"] == 0


def test_archive_rejects_claim_of_current_season():
    with pytest.raises(ValueError):
        validate_scope_config("openfootball", "archive", {"season": 2026})


def test_svg_cache_removes_active_content_and_reuses_a_valid_local_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ONCE_MEDIA_DIR", str(tmp_path))
    content = b'<svg xmlns="http://www.w3.org/2000/svg" onload="evil()"><script>alert(1)</script><path d="M0 0h1"/><use href="https://example.com/evil.svg"/></svg>'
    calls = []

    def transport(url, **kwargs):
        calls.append(url)
        return httpx.Response(
            200,
            headers={"content-type": "image/svg+xml"},
            content=content,
            request=httpx.Request("GET", url),
        )

    media = {"original_url": "https://upload.wikimedia.org/example.svg"}
    saved = cache_asset(media, transport)
    file = tmp_path / saved["local_url"].rsplit("/", 1)[-1]
    assert (
        b"script" not in file.read_bytes()
        and b"onload" not in file.read_bytes()
        and b"https://" not in file.read_bytes()
    )
    assert cache_asset(media, transport)["local_url"] == saved["local_url"]
    assert len(calls) == 1


def test_media_cache_never_fetches_arbitrary_hosts(tmp_path, monkeypatch):
    monkeypatch.setenv("ONCE_MEDIA_DIR", str(tmp_path))
    from src.providers import ProviderError

    with pytest.raises(ProviderError):
        cache_asset(
            {"original_url": "http://127.0.0.1/private"},
            lambda *_: pytest.fail("No network expected"),
        )
