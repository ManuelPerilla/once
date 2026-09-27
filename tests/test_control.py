import datetime as dt

import pytest
from sqlalchemy import event
from sqlmodel import Session

from src import database
from src.models import (
    CatalogImportBatch,
    MediaAsset,
    Partido,
    ProviderMapping,
    ProviderSnapshot,
    Temporada,
)


@pytest.fixture
def provenance(catalog):
    timestamp = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    with Session(database.engine) as session:
        links = [
            ProviderMapping(
                provider="wikidata",
                entity_type="team",
                local_id=team["id"],
                external_id=f"Q{index}",
                verified_at=timestamp,
            )
            for index, team in enumerate(catalog["teams"][:3], start=10)
        ]
        orphan = ProviderMapping(
            provider="legacy", entity_type="team", local_id=999999, external_id="missing"
        )
        unknown_type = ProviderMapping(
            provider="legacy", entity_type="unsupported", local_id=1, external_id="legacy"
        )
        observation = ProviderSnapshot(
            provider="wikidata",
            entity_type="team",
            local_id=catalog["teams"][0]["id"],
            kind="catalog_identity",
            fetched_at=timestamp,
            payload={
                "source_url": "https://www.wikidata.org/wiki/Q10",
                "license": "CC0-1.0",
                "entity": {"private_payload_not_for_list": "large response"},
            },
        )
        media = MediaAsset(
            entity_type="team",
            entity_id=catalog["teams"][1]["id"],
            tipo="escudo",
            source="wikimedia-commons",
            original_url="https://example.test/image.svg",
            author="Autor de prueba",
            license="   ",
            verified_at=timestamp,
        )
        batch = CatalogImportBatch(
            id="control-batch",
            collection="colombia",
            fetched_at=timestamp,
            payload={"rows": [{"qid": "Q10"}], "entities": {"do_not_expose": True}},
            last_result={
                "created": 1,
                "linked": 0,
                "reused": 0,
                "skipped": 0,
                "applied_at": "2026-01-02T02:00:00+00:00",
                "items": [],
            },
        )
        session.add_all([*links, orphan, unknown_type, observation, media, batch])
        session.commit()
        return {"ids": [row.id for row in links], "orphan": orphan.id, "media": media.id}


@pytest.mark.parametrize(
    "path",
    [
        "/control/summary",
        "/control/records?kind=links",
        "/control/issues?code=matches_without_date",
    ],
)
def test_control_requires_authentication(client, path):
    assert client.get(path).status_code == 401


def test_control_filters_before_pagination_with_stable_ties(authenticated, catalog, provenance):
    params = {"kind": "links", "provider": "wikidata", "entity_type": "team", "page_size": 1}
    first = authenticated.get("/control/records", params=params).json()
    second = authenticated.get("/control/records", params={**params, "page": 2}).json()
    assert first["total"] == second["total"] == 3
    assert first["items"][0]["id"] == str(provenance["ids"][-1])
    assert second["items"][0]["id"] == str(provenance["ids"][-2])
    assert first["items"][0]["entity_name"] == "Sin matrícula"
    filtered = authenticated.get(
        "/control/records", params={**params, "search": "visitante"}
    ).json()
    assert filtered["total"] == 1 and filtered["items"][0]["entity_name"] == "Visitante"
    literal = authenticated.get("/control/records", params={**params, "search": "%"}).json()
    assert literal["total"] == 0
    empty = authenticated.get("/control/records", params={**params, "page": 20}).json()
    assert empty["total"] == 3 and empty["items"] == []


def test_control_distinguishes_consultation_application_and_latest_snapshot(
    authenticated, provenance
):
    imports = authenticated.get("/control/records?kind=imports&search=Colombia").json()
    assert imports["total"] == 1
    batch = imports["items"][0]
    assert batch["status"] == "applied" and batch["metadata"]["created"] == 1
    assert batch["recorded_at"].startswith("2026-01-02T00:00:00")
    assert batch["metadata"]["applied_at"].startswith("2026-01-02T02:00:00")
    assert "payload" not in batch and "entities" not in batch["metadata"]
    observations = authenticated.get("/control/records?kind=observations").json()
    row = observations["items"][0]
    assert row["title"] == "Local" and row["metadata"]["license"] == "CC0-1.0"
    assert "private_payload_not_for_list" not in str(row)
    assert authenticated.get("/control/records?kind=imports&provider=unknown").json()["total"] == 0


def test_control_quality_lists_missing_references_without_modification(
    authenticated, catalog, provenance
):
    with Session(database.engine) as session:
        session.add(Partido(estado="programado"))
        session.add(
            Temporada(
                competicion_id=catalog["comp"]["id"],
                nombre="Fechas a revisar",
                fecha_inicio=dt.date(2026, 8, 1),
                fecha_fin=dt.date(2026, 1, 1),
            )
        )
        session.commit()
    summary = authenticated.get("/control/summary").json()
    checks = {row["code"]: row for row in summary["checks"]}
    assert checks["links_without_record"]["count"] == 2
    assert checks["media_without_license"]["count"] == 1
    assert checks["matches_incomplete"]["count"] == 1
    assert checks["seasons_invalid_dates"]["count"] == 1
    assert checks["matches_without_season"]["severity"] == "review"
    assert summary["counts"]["links"] == 5 and summary["counts"]["imports"] == 1
    assert len(summary["counts"]) == 17
    assert summary["providers"] == ["legacy", "wikidata", "wikimedia-commons"]
    assert any("Auditoría" in note for note in summary["scope_notes"])
    orphaned = authenticated.get("/control/issues?code=links_without_record").json()
    assert orphaned["total"] == 2 and all(row["status"] == "orphaned" for row in orphaned["items"])
    dates = authenticated.get("/control/issues?code=seasons_invalid_dates").json()
    assert dates["items"][0]["title"] == "Fechas a revisar"
    assert dates["items"][0]["module"] == "seasons"
    media = authenticated.get("/control/records?kind=media").json()["items"][0]
    assert media["status"] == "review" and media["metadata"]["author"] == "Autor de prueba"


def test_control_only_executes_bounded_local_reads(authenticated, provenance, monkeypatch):
    import httpx

    def remote_forbidden(*args, **kwargs):
        raise AssertionError("El control no debe consultar servicios externos")

    monkeypatch.setattr(httpx, "get", remote_forbidden)
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        for path in (
            "/control/summary",
            "/control/records?kind=links&page_size=1",
            "/control/records?kind=observations",
            "/control/records?kind=media",
            "/control/records?kind=imports",
            "/control/issues?code=links_without_record",
        ):
            response = authenticated.get(path)
            assert response.status_code == 200, response.text
    finally:
        event.remove(database.engine, "before_cursor_execute", capture)
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert len(statements) == 13  # Summary: 3 aggregates; each list: count + bounded page.


@pytest.mark.parametrize(
    "query",
    [
        "kind=unknown",
        "kind=links&page=0",
        "kind=links&page_size=101",
        "kind=links&entity_type=invalid",
        "kind=imports&entity_type=team",
    ],
)
def test_control_rejects_invalid_filters(authenticated, query):
    assert authenticated.get(f"/control/records?{query}").status_code == 422
    assert authenticated.get("/control/issues?code=unknown").status_code == 422
