"""Legacy previews remain useful without bypassing shared quotas or activating imports."""

import httpx
import pytest
from sqlmodel import Session, select

from src import database
from src.models import Partido
from src.sync.models import SyncBudget, SyncControl, SyncScope, utcnow
from src.sync.service import QuotaExhausted, SyncEngine, enqueue, set_global_mode


@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "private-preview-test-key")
    calls = []

    class Remote:
        def __init__(self, method, url, **kwargs):
            calls.append((url, kwargs.get("params")))
            self.response = httpx.Response(
                200,
                json={"response": [], "results": 0},
                headers={
                    "x-ratelimit-requests-limit": "100",
                    "x-ratelimit-requests-remaining": "99",
                },
                request=httpx.Request(method, url),
            )

        def __enter__(self):
            return self.response

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        httpx.Client, "stream", lambda self, method, url, **kwargs: Remote(method, url, **kwargs)
    )
    return calls


@pytest.mark.parametrize(
    ("path", "params", "endpoint"),
    [
        ("league/239", {"season": 2024}, "leagues"),
        ("fixtures", {"league_id": 239, "season": 2024}, "fixtures"),
        ("fixture/123", {}, "fixtures"),
        ("teams", {"league_id": 239, "season": 2024}, "teams"),
        ("rounds", {"league_id": 239, "season": 2024}, "fixtures/rounds"),
    ],
)
def test_each_preview_reserves_budget_while_imports_stay_paused(
    authenticated, remote, path, params, endpoint
):
    with Session(database.engine) as session:
        existing = session.exec(select(Partido)).all()
    result = authenticated.get(f"/providers/api-football/preview/{path}", params=params)
    assert result.status_code == 200, result.text
    assert len(remote) == 1 and remote[0][0] == f"https://v3.football.api-sports.io/{endpoint}"
    assert "private-preview-test-key" not in result.text
    with Session(database.engine) as session:
        assert session.get(SyncBudget, "api-football").day_used == 1
        assert session.get(SyncControl, 1).mode == "paused"
        assert session.exec(select(SyncScope)).one().mode == "paused"
        assert session.exec(select(Partido)).all() == existing


def test_exhausted_preview_is_rejected_before_any_http_request(authenticated, remote):
    with Session(database.engine) as session:
        session.add(
            SyncBudget(provider="api-football", day=utcnow().strftime("%Y-%m-%d"), day_used=100)
        )
        session.commit()
    response = authenticated.get(
        "/providers/api-football/preview/fixtures", params={"league_id": 239, "season": 2024}
    )
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert remote == []


def test_preview_and_worker_use_the_same_daily_allowance(authenticated, remote):
    engine = SyncEngine(database.engine)
    with engine.transaction() as session:
        set_global_mode(session, "automatic", "tester")
        scope = SyncScope(
            name="Colombia",
            provider="api-football",
            kind="fixtures",
            mode="automatic",
            daily_limit=1,
        )
        session.add(scope)
        session.flush()
        enqueue(session, scope)
    result = authenticated.get(
        "/providers/api-football/preview/fixtures", params={"league_id": 239, "season": 2024}
    )
    assert result.status_code == 200, result.text
    with pytest.raises(QuotaExhausted):
        engine.claim("worker").reserve_request()
    assert len(remote) == 1
