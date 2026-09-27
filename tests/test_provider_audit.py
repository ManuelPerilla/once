"""External identity and media decisions retain a named audit trail."""

from src.providers import WikidataClient


def named_source_admin(client):
    credentials = {"username": "source_reviewer", "password": "reviewer-test-password"}
    response = client.post(
        "/accounts", json={**credentials, "display_name": "Revisión de fuentes", "role": "admin"}
    )
    assert response.status_code == 201
    assert client.post("/login", json=credentials).status_code == 200


def relevant_history(client, team_id):
    return [
        row
        for row in client.get(f"/audit/entities/team/{team_id}").json()["history"]
        if row["action"] in {"identity_link", "identity_unlink", "media_import", "media_create"}
    ]


def test_mapping_create_delete_is_audited_and_canonical_team_survives(authenticated, catalog):
    named_source_admin(authenticated)
    team_id = catalog["teams"][0]["id"]
    before = authenticated.get(f"/audit/entities/team/{team_id}").json()["version"]
    payload = {
        "provider": "api-football",
        "entity_type": "team",
        "local_id": team_id,
        "external_id": "123",
    }
    response = authenticated.post("/providers/mappings/", json=payload)
    assert response.status_code == 200, response.text
    mapping_id = response.json()["id"]
    assert authenticated.post("/providers/mappings/", json=payload).status_code == 409
    history = relevant_history(authenticated, team_id)
    assert len(history) == 1 and history[0]["actor"] == "source_reviewer"
    assert history[0]["after"]["external_id"] == "123"
    assert history[0]["version"] == before + 1
    assert authenticated.put("/automation/global", json={"mode": "automatic"}).status_code == 200
    assert authenticated.delete(f"/providers/mappings/{mapping_id}").status_code == 409
    authenticated.put("/automation/global", json={"mode": "paused"})
    assert authenticated.delete(f"/providers/mappings/{mapping_id}").status_code == 200
    assert authenticated.get(f"/audit/entities/team/{team_id}").status_code == 200
    history = relevant_history(authenticated, team_id)
    assert [row["action"] for row in history] == ["identity_unlink", "identity_link"]
    assert history[0]["before"]["external_id"] == "123" and history[0]["after"] is None
    assert history[0]["version"] == before + 2


def test_implicit_media_mapping_and_attribution_changes_have_history(
    authenticated, catalog, monkeypatch
):
    named_source_admin(authenticated)
    team_id = catalog["teams"][0]["id"]
    payload = {
        "qid": "Q123",
        "filename": "Club.svg",
        "property": "P154",
        "original_url": "https://upload.wikimedia.org/Club.svg",
        "source_url": "https://commons.wikimedia.org/wiki/File:Club.svg",
        "license": "CC0",
        "author": "Example author",
        "credit": "Original credit",
        "mime_type": "image/svg+xml",
    }
    monkeypatch.setattr(WikidataClient, "commons_media", lambda *args, **kwargs: dict(payload))
    path = f"/providers/wikidata/import-media/team/{team_id}/Q123"
    first = authenticated.post(path)
    assert first.status_code == 200, first.text
    assert authenticated.post(path).status_code == 200
    history = relevant_history(authenticated, team_id)
    assert len(history) == 2
    assert {row["action"] for row in history} == {"identity_link", "media_import"}
    assert {row["actor"] for row in history} == {"source_reviewer"}
    payload["credit"] = "Corrected attribution"
    updated = authenticated.post(path)
    assert updated.status_code == 200
    assert updated.json()["id"] == first.json()["id"]
    history = relevant_history(authenticated, team_id)
    assert len(history) == 3
    assert history[0]["before"]["credit"] == "Original credit"
    assert history[0]["after"]["credit"] == "Corrected attribution"


def test_manual_media_creation_is_audited(authenticated, catalog):
    named_source_admin(authenticated)
    team_id = catalog["teams"][0]["id"]
    response = authenticated.post(
        "/media/",
        json={
            "entity_type": "team",
            "entity_id": team_id,
            "tipo": "escudo",
            "source": "manual",
            "original_url": "https://example.org/crest.svg",
            "license": "CC0",
            "author": "Author",
        },
    )
    assert response.status_code == 200, response.text
    history = relevant_history(authenticated, team_id)
    assert len(history) == 1 and history[0]["action"] == "media_create"
    assert history[0]["actor"] == "source_reviewer"
    assert history[0]["after"]["license"] == "CC0"
