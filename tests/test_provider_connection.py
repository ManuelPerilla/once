"""Real onboarding contracts without external HTTP or stored credentials."""

import httpx
import pytest
from sqlmodel import Session, select

from src import database
from src.models import ProviderSnapshot
from src.providers.api_football import APIFootballClient, ProviderError
from src.providers.connection import check_season_access
from src.sync.models import SyncBudget

BASE = "/providers/api-football"


def test_real_plan_denial_exposes_only_confirmed_years():
    class FreeProvider:
        def fixtures(self, league, season):
            assert (league, season) == (239, 2026)
            raise ProviderError("Restricted", code="plan", access_seasons=[2022, 2023, 2024])

    account = {"checked_at": "2026-09-27T00:00:00+00:00"}
    check_season_access(
        FreeProvider(), [{"league_id": 239, "seasons": [{"year": 2026, "current": True}]}], account
    )
    assert account["current_access"] is False
    assert account["allowed_seasons"] == [2022, 2023, 2024]
    assert "last_error" not in account


@pytest.fixture
def source(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "test-secret-no-persist")
    calls = []

    def fetch(self, path, params=None, **kwargs):
        calls.append(path)
        if path == "status":
            return {
                "response": {
                    "account": {"firstname": "Private", "email": "private@example.org"},
                    "subscription": {"plan": "Free", "active": True},
                    "requests": {"current": 12, "limit_day": 100},
                }
            }
        return {
            "response": [
                {
                    "league": {"id": 239, "name": "Primera A", "type": "League"},
                    "country": {"name": "Colombia"},
                    "seasons": [
                        {
                            "year": 2024,
                            "current": False,
                            "coverage": {"fixtures": {"events": True, "lineups": True}},
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(APIFootballClient, "_get", fetch)
    return calls


def test_read_status_is_local_and_key_is_never_returned(authenticated, source):
    result = authenticated.get(f"{BASE}/connection")
    assert result.status_code == 200
    assert result.json()["state"] == "unchecked"
    assert source == []
    assert "test-secret" not in result.text


def test_explicit_check_sanitizes_account_and_preserves_pause(authenticated, source):
    response = authenticated.post(f"{BASE}/check")
    assert response.status_code == 200, response.text
    data = response.json()
    assert source == ["status", "leagues"]
    assert data["state"] == "connected"
    assert data["global_mode"] == "paused"
    assert data["account"]["requests_limit_day"] == 100
    assert len(data["competitions"]) == 1
    assert data["profiles"] == []
    with Session(database.engine) as session:
        stored = str(session.exec(select(ProviderSnapshot)).all())
    assert "private@example.org" not in stored
    assert "test-secret-no-persist" not in stored
    assert "credential_fingerprint" not in response.text
    assert authenticated.post(f"{BASE}/check").status_code == 429
    assert source == ["status", "leagues"]


def test_prepare_is_paused_idempotent_and_only_advertised_seasons(authenticated, source):
    authenticated.post(f"{BASE}/check")
    body = {"selections": [{"league_id": 239, "season": 2024}], "include_details": True}
    first = authenticated.post(f"{BASE}/prepare", json=body)
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 2
    second = authenticated.post(f"{BASE}/prepare", json=body)
    assert second.json()["created"] == 0
    assert second.json()["scope_ids"] == first.json()["scope_ids"]
    assert all(scope["mode"] == "paused" for scope in second.json()["connection"]["profiles"])
    assert source == ["status", "leagues"]
    body["selections"][0]["season"] = 2026
    assert authenticated.post(f"{BASE}/prepare", json=body).status_code == 422


def test_replaced_key_invalidates_verified_status(authenticated, source, monkeypatch):
    authenticated.post(f"{BASE}/check")
    monkeypatch.setenv("API_FOOTBALL_KEY", "replacement-key")
    state = authenticated.get(f"{BASE}/connection").json()
    assert state["state"] == "unchecked" and state["competitions"] == []
    assert (
        authenticated.post(
            f"{BASE}/prepare", json={"selections": [{"league_id": 239, "season": 2024}]}
        ).status_code
        == 409
    )


def test_diagnostics_share_budget_and_no_requests_on_get(authenticated, monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "private-key")
    calls = []

    class Remote:
        def __init__(self, method, url, **kwargs):
            calls.append(url)
            raw = (
                {
                    "subscription": {"plan": "Free", "active": True},
                    "requests": {"current": 1, "limit_day": 100},
                }
                if url.endswith("/status")
                else []
            )
            self.response = httpx.Response(
                200, json={"response": raw}, request=httpx.Request(method, url)
            )

        def __enter__(self):
            return self.response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        httpx.Client, "stream", lambda self, method, url, **kwargs: Remote(method, url, **kwargs)
    )
    response = authenticated.post(f"{BASE}/check")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "connected"
    assert len(calls) == 2
    authenticated.get(f"{BASE}/connection")
    assert len(calls) == 2
    with Session(database.engine) as session:
        budget = session.get(SyncBudget, "api-football")
        assert budget.day_used == 2


def test_connection_changes_require_source_admin(authenticated, source):
    created = authenticated.post(
        "/accounts/",
        json={
            "username": "source_operator",
            "display_name": "Operador de fuentes",
            "password": "a-valid-test-password",
            "role": "operator",
        },
    )
    assert created.status_code in {200, 201}, created.text
    authenticated.post("/logout")
    assert (
        authenticated.post(
            "/login", json={"username": "source_operator", "password": "a-valid-test-password"}
        ).status_code
        == 200
    )
    assert authenticated.get(f"{BASE}/connection").status_code == 200
    assert authenticated.post(f"{BASE}/check").status_code == 403
    assert (
        authenticated.post(
            f"{BASE}/prepare", json={"selections": [{"league_id": 239, "season": 2024}]}
        ).status_code
        == 403
    )
    assert source == []
