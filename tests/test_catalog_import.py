import copy
import datetime as dt

import httpx
import pytest
from sqlmodel import Session, select

from src import database
from src.catalog.collections import COLLECTIONS
from src.models import CatalogImportBatch, ProviderMapping, ProviderSnapshot
from src.providers import ProviderError, WikidataClient


@pytest.fixture
def source(monkeypatch):
    entries = [
        {
            "qid": "Q900001",
            "entity_type": "confederation",
            "preferred_name": "Confederación importada",
        },
        {
            "qid": "Q900002",
            "entity_type": "competition",
            "tipo": "liga_nacional",
            "pais": "Colombia",
            "country_qid": "Q739",
            "confederation_qid": "Q900001",
        },
        {
            "qid": "Q900003",
            "entity_type": "team",
            "tipo": "club",
            "pais": "Colombia",
            "country_qid": "Q739",
            "confederation_qid": "Q900001",
        },
    ]
    monkeypatch.setitem(
        COLLECTIONS,
        "test",
        {"name": "Colección de prueba", "description": "Test", "entries": entries},
    )

    def claim(qid):
        return {"rank": "normal", "mainsnak": {"datavalue": {"value": {"id": qid}}}}

    entities = {
        entry["qid"]: {
            "id": entry["qid"],
            "lastrevid": 12345,
            "labels": {"es": {"value": name}},
            "aliases": {},
            "claims": {"P641": [claim("Q2736")], "P17": [claim("Q739")]},
        }
        for entry, name in zip(
            entries, ["Confederación importada", "Liga importada", "Club importado"], strict=True
        )
    }
    calls = []

    def fetch(self, qids, **kwargs):
        calls.append(qids)
        return copy.deepcopy(entities)

    monkeypatch.setattr(WikidataClient, "entities", fetch)
    return entities, calls


def prepare(client):
    response = client.post("/catalog/prepare/test")
    assert response.status_code == 200, response.text
    return response.json()


def decisions(batch):
    return [
        {"qid": row["qid"], "action": "create", "expected_status": row["status"]}
        for row in batch["rows"]
    ]


def apply(client, batch, choices=None):
    return client.post(
        f"/catalog/batches/{batch['id']}/apply", json={"decisions": choices or decisions(batch)}
    )


def test_catalog_is_admin_only(client):
    assert client.get("/catalog/collections").status_code == 401
    assert client.post("/catalog/prepare/colombia").status_code == 401
    assert client.post("/catalog/batches/unknown/apply", json={"decisions": []}).status_code == 401


def test_preview_batches_network_and_does_not_modify_catalog(authenticated, source):
    before = authenticated.get("/equipos/").json()
    first = prepare(authenticated)
    second = prepare(authenticated)
    assert first["cached"] is False and second["cached"] is True
    assert first["id"] == second["id"] and len(source[1]) == 1
    assert authenticated.get("/equipos/").json() == before
    assert all(row["status"] == "new" for row in first["rows"])
    assert authenticated.get("/providers/mappings/").json() == []


def test_import_is_atomic_connected_repeatable_and_preserves_provenance(authenticated, source):
    batch = prepare(authenticated)
    first = apply(authenticated, batch)
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 3
    second = apply(authenticated, batch)
    assert second.status_code == 200 and second.json()["created"] == 0
    assert second.json()["reused"] == 3
    team = next(
        item for item in authenticated.get("/equipos/").json() if item["nombre"] == "Club importado"
    )
    conf = next(
        item
        for item in authenticated.get("/confederaciones/").json()
        if item["nombre"] == "Confederación importada"
    )
    assert team["confederacion_id"] == conf["id"]
    assert team["competiciones"] == []  # Catalog identity is not a season enrollment.
    assert team["logo"] == ""  # Image rights are handled separately.
    with Session(database.engine) as session:
        snapshots = session.exec(select(ProviderSnapshot)).all()
        assert len(snapshots) == 3
        assert all(
            s.payload["license"] == "CC0-1.0" and s.payload["entity"]["lastrevid"] == 12345
            for s in snapshots
        )
        assert len(session.exec(select(ProviderMapping)).all()) == 3


def test_link_preserves_manual_name_logo_and_uses_alias(authenticated, source):
    batch = prepare(authenticated)
    first = apply(authenticated, batch, [decisions(batch)[0]])
    conf_id = first.json()["items"][0]["local_id"]
    existing = authenticated.post(
        "/equipos/",
        json={
            "nombre": "Club importado",
            "logo": "https://example.test/own.svg",
            "tipo": "club",
            "pais": "Colombia",
            "confederacion_id": conf_id,
        },
    ).json()
    updated = prepare(authenticated)
    row = next(row for row in updated["rows"] if row["entity_type"] == "team")
    assert row["status"] == "review" and row["candidates"][0]["id"] == existing["id"]
    result = apply(
        authenticated,
        updated,
        [
            {
                "qid": row["qid"],
                "action": "link",
                "local_id": existing["id"],
                "expected_status": "review",
            }
        ],
    )
    assert result.status_code == 200 and result.json()["linked"] == 1
    after = next(t for t in authenticated.get("/equipos/").json() if t["id"] == existing["id"])
    assert after["nombre"] == existing["nombre"] and after["logo"] == existing["logo"]


def test_invalid_link_rolls_back_earlier_creates(authenticated, source):
    batch = prepare(authenticated)
    choices = decisions(batch)
    choices[-1].update(action="link", local_id=999999)
    assert apply(authenticated, batch, choices).status_code == 409
    assert not any(
        item["nombre"] == "Confederación importada"
        for item in authenticated.get("/confederaciones/").json()
    )
    assert authenticated.get("/providers/mappings/").json() == []


def test_missing_dependency_does_not_import_or_guess(authenticated, source):
    batch = prepare(authenticated)
    assert apply(authenticated, batch, [decisions(batch)[-1]]).status_code == 409
    assert not any(
        item["nombre"] == "Club importado" for item in authenticated.get("/equipos/").json()
    )


def test_wrong_country_and_missing_entity_are_blocked(authenticated, source):
    source[0]["Q900003"]["claims"]["P17"] = []
    del source[0]["Q900002"]
    batch = prepare(authenticated)
    assert [row["status"] for row in batch["rows"]] == ["new", "blocked", "blocked"]
    assert apply(authenticated, batch).status_code == 409
    assert authenticated.get("/providers/mappings/").json() == []


def test_expired_batch_requires_new_observations(authenticated, source):
    batch = prepare(authenticated)
    with Session(database.engine) as session:
        record = session.get(CatalogImportBatch, batch["id"])
        record.fetched_at -= dt.timedelta(days=2)
        session.add(record)
        session.commit()
    assert apply(authenticated, batch).status_code == 409
    assert prepare(authenticated)["id"] != batch["id"]
    assert len(source[1]) == 2


def test_stale_preview_cannot_silently_create_duplicate(authenticated, source):
    batch = prepare(authenticated)
    authenticated.post("/confederaciones/", json={"nombre": "Confederación importada", "logo": ""})
    response = apply(authenticated, batch)
    assert response.status_code == 409 and "cambió" in response.json()["detail"]
    assert authenticated.get("/providers/mappings/").json() == []


def test_duplicate_decisions_rejected(authenticated, source):
    batch = prepare(authenticated)
    choice = decisions(batch)[0]
    assert apply(authenticated, batch, [choice, choice]).status_code == 409


def test_commercial_alias_is_reviewed_without_automatic_merge(authenticated, source):
    source[0]["Q900002"]["aliases"] = {"es": [{"value": "Liga BetPlay Dimayor"}]}
    existing = authenticated.post(
        "/competiciones/",
        json={
            "nombre": "Liga BetPlay",
            "logo": "",
            "tipo": "liga_nacional",
            "pais": "Colombia",
        },
    ).json()
    batch = prepare(authenticated)
    row = next(row for row in batch["rows"] if row["entity_type"] == "competition")
    assert row["status"] == "review"
    assert existing["id"] in {candidate["id"] for candidate in row["candidates"]}
    assert authenticated.get("/providers/mappings/").json() == []


def test_wikidata_batch_failure_does_not_cache_incomplete_result(authenticated, monkeypatch):
    def failed(self, qids, **kwargs):
        raise ProviderError("Wikidata no disponible")

    monkeypatch.setattr(WikidataClient, "entities", failed)
    assert authenticated.post("/catalog/prepare/colombia").status_code == 502
    with Session(database.engine) as session:
        assert session.exec(select(CatalogImportBatch)).all() == []


def test_batch_transport_respects_rate_limit_without_immediate_retry(monkeypatch):
    calls = []

    def limited(*args, **kwargs):
        calls.append(kwargs)
        return httpx.Response(
            429, request=httpx.Request("GET", "https://www.wikidata.org/w/api.php")
        )

    monkeypatch.setattr(httpx, "get", limited)
    with pytest.raises(ProviderError, match="reducir"):
        WikidataClient().entities(["Q58733", "Q35572"])
    assert len(calls) == 1 and calls[0]["params"]["maxlag"] == 5


def test_interactive_batch_uses_documented_human_request_policy(monkeypatch):
    calls = []

    def response(*args, **kwargs):
        calls.append(kwargs)
        return httpx.Response(
            200,
            json={"entities": {"Q58733": {"id": "Q58733"}}},
            request=httpx.Request("GET", "https://www.wikidata.org/w/api.php"),
        )

    monkeypatch.setattr(httpx, "get", response)
    assert "Q58733" in WikidataClient().entities(["Q58733"], interactive=True)
    assert "maxlag" not in calls[0]["params"]


def test_background_maxlag_is_reported_without_retry(monkeypatch):
    calls = []

    def busy(*args, **kwargs):
        calls.append(kwargs)
        return httpx.Response(
            200,
            json={"error": {"code": "maxlag", "lag": 9}},
            request=httpx.Request("GET", "https://www.wikidata.org/w/api.php"),
        )

    monkeypatch.setattr(httpx, "get", busy)
    with pytest.raises(ProviderError, match="réplicas"):
        WikidataClient().entities(["Q58733"])
    assert len(calls) == 1
