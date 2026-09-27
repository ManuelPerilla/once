"""Control-plane authorization and effective pause semantics at the API boundary."""

import pytest
from sqlmodel import Session

from src import database
from src.sync.service import SyncEngine, issue


@pytest.fixture
def scope(authenticated, monkeypatch):
    # Adapter-specific selectors have separate tests; these exercise control transactions.
    monkeypatch.setattr("src.sync.routes.validate_adapter", lambda config: None)
    response = authenticated.post(
        "/automation/scopes",
        json={
            "name": "Liga colombiana",
            "provider": "api_football",
            "kind": "fixtures",
            "selector": {"league_id": 239, "season": 2026},
            "mode": "automatic",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_automation_requires_authentication(client):
    assert client.get("/automation/overview").status_code == 401
    assert client.put("/automation/global", json={"mode": "automatic"}).status_code == 401
    assert client.get("/automation/history").status_code == 401


def test_new_installation_paused_and_run_does_not_bypass_global(authenticated, scope):
    overview = authenticated.get("/automation/overview").json()
    assert overview["global"]["mode"] == "paused"
    assert overview["scopes"][0]["provider"] == "api-football"
    assert overview["scopes"][0]["status"] == "paused"
    assert authenticated.post(f"/automation/scopes/{scope['id']}/run").status_code == 409


def test_run_is_enqueued_and_repeated_click_coalesces(authenticated, scope):
    assert authenticated.put("/automation/global", json={"mode": "observe"}).status_code == 200
    first = authenticated.post(f"/automation/scopes/{scope['id']}/run")
    second = authenticated.post(f"/automation/scopes/{scope['id']}/run")
    assert first.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "queued" and first.json()["mode"] == "observe"
    page = authenticated.get("/automation/jobs?limit=1").json()
    assert page["total"] == 1 and len(page["items"]) == 1


def test_pause_exposes_draining_then_paused_and_cancels_inflight(authenticated, scope):
    authenticated.put("/automation/global", json={"mode": "automatic"})
    authenticated.post(f"/automation/scopes/{scope['id']}/run")
    worker = SyncEngine(database.engine)
    context = worker.claim("test-worker")
    assert (
        authenticated.patch(
            f"/automation/scopes/{scope['id']}", json={"mode": "paused"}
        ).status_code
        == 200
    )
    assert authenticated.get("/automation/overview").json()["scopes"][0]["status"] == "pausing"
    worker.fail(context, RuntimeError("cancel"))
    assert authenticated.get("/automation/overview").json()["scopes"][0]["status"] == "paused"


def test_control_changes_record_actor_and_cannot_store_credentials(authenticated, scope):
    response = authenticated.patch(
        f"/automation/scopes/{scope['id']}", json={"selector": {"api_key": "secret"}}
    )
    assert response.status_code == 422
    response = authenticated.patch(f"/automation/scopes/{scope['id']}", json={"name": "   "})
    assert response.status_code == 422
    response = authenticated.patch(f"/automation/scopes/{scope['id']}", json={"mode": "observe"})
    assert response.status_code == 200
    items = authenticated.get("/automation/history").json()["items"]
    assert any(
        row["action"] == "scope_updated" and row["actor"] == "operador_test" for row in items
    )
    assert "secret" not in str(items)


def test_repeated_incidence_groups_and_requires_resolution_reason(authenticated, scope):
    with Session(database.engine) as session:
        row = issue(session, scope["id"], "missing", "Falta un equipo.")
        session.flush()
        issue(session, scope["id"], "missing", "Falta un equipo.")
        session.commit()
        issue_id = row.id
    page = authenticated.get("/automation/issues?status=open").json()
    assert page["total"] == 1 and page["items"][0]["occurrences"] == 2
    assert (
        authenticated.post(
            f"/automation/issues/{issue_id}/resolve", json={"note": "   "}
        ).status_code
        == 422
    )
    assert (
        authenticated.post(
            f"/automation/issues/{issue_id}/resolve", json={"note": "Identidad corregida."}
        ).status_code
        == 200
    )
    assert authenticated.get("/automation/issues?status=open").json()["total"] == 0
