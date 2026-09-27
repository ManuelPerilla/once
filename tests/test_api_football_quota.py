"""Plan verification and remote account capacity never bypass ONCE's local budget."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from src import database
from src.models import ProviderSnapshot
from src.sync.models import SyncBudget, SyncScope, utcnow
from src.sync.service import (
    PacingWait,
    QuotaExhausted,
    SyncEngine,
    budget_for,
    control,
    effective_api_limits,
    enqueue,
    reserve_provider_request,
    set_global_mode,
)


@pytest.fixture
def engine(client, monkeypatch):
    engine = SyncEngine(database.engine)
    # Start on a known minute boundary, after the real timestamps used by job defaults.
    # The simulated seven-second spacing must not accidentally reset a quota window.
    engine.clock = [(utcnow() + timedelta(minutes=2)).replace(second=0, microsecond=0)]
    monkeypatch.setattr("src.sync.service.now", lambda session: engine.clock[0])
    return engine


def reserve(engine, context):
    if hasattr(engine, "clock"):
        engine.clock[0] += timedelta(seconds=7)
    context.reserve_request()


def account(session, **changes):
    payload = {
        "plan": "Pro",
        "active": True,
        "requests_current": 1100,
        "requests_limit_day": 7500,
        "minute_limit": 300,
        "checked_at": utcnow().isoformat(),
        **changes,
    }
    session.add(
        ProviderSnapshot(
            provider="api-football",
            entity_type="connection",
            local_id=1,
            kind="status",
            payload=payload,
        )
    )


def configured(engine, **limits):
    with engine.transaction() as session:
        set_global_mode(session, "automatic", "tester")
        account(session)
        scope = SyncScope(
            name="Colombia", provider="api-football", kind="fixtures", mode="automatic", **limits
        )
        session.add(scope)
        session.flush()
        enqueue(session, scope)
        return scope.id


def quota(engine):
    with Session(engine.engine) as session:
        return (
            session.exec(select(ProviderSnapshot).where(ProviderSnapshot.kind == "quota"))
            .one()
            .payload
        )


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, (7500, 300)),
        ({"active": False}, (100, 10)),
        ({"requests_limit_day": True, "minute_limit": None}, (100, 10)),
        ({"checked_at": "not-a-date"}, (100, 10)),
        ({"checked_at": "2026-01-01T12:00:00"}, (100, 10)),
    ],
)
def test_only_verified_active_account_limits_are_usable(engine, changes, expected):
    with engine.transaction() as session:
        account(session, **changes)
        assert effective_api_limits(session) == expected


@pytest.mark.parametrize("age", [timedelta(hours=25), timedelta(hours=-1)])
def test_expired_or_future_plan_observation_reverts_to_conservative_limits(engine, age):
    with engine.transaction() as session:
        account(session, checked_at=(utcnow() - age).isoformat())
        assert effective_api_limits(session) == (100, 10)


def test_missing_status_cannot_raise_default_limits(engine):
    with engine.transaction() as session:
        assert effective_api_limits(session) == (100, 10)


def test_paid_account_does_not_change_deliberate_local_budget(engine):
    scope_id = configured(engine)
    with engine.transaction() as session:
        scope = session.get(SyncScope, scope_id)
        budget = budget_for(session, "api-football", scope)
        assert (budget.day_limit, budget.minute_limit) == (100, 10)
        assert (scope.daily_limit, scope.minute_limit) == (100, 10)


def test_only_active_scopes_and_caller_contribute_local_caps(engine):
    scope_id = configured(engine, daily_limit=5000, minute_limit=200)
    with engine.transaction() as session:
        archived = SyncScope(
            name="Old plan", provider="api-football", kind="fixtures", daily_limit=1
        )
        diagnostic = SyncScope(name="Connection check", provider="api-football", kind="discovery")
        session.add_all([archived, diagnostic])
        scope = session.get(SyncScope, scope_id)
        assert budget_for(session, "api-football", scope).day_limit == 5000
        # Explicit calls made on a paused diagnostic scope still honor its own cap.
        assert budget_for(session, "api-football", diagnostic).day_limit == 100
        scope.mode = "paused"
        session.add(scope)
        assert budget_for(session, "api-football", diagnostic).day_limit == 100


def test_source_headers_can_lower_confirmed_plan_but_cannot_raise_local_cap(engine):
    scope_id = configured(engine, daily_limit=5000, minute_limit=200)
    engine.report_quota(scope_id, limit_day=100, limit_minute=10)
    with engine.transaction() as session:
        scope = session.get(SyncScope, scope_id)
        budget = budget_for(session, "api-football", scope)
        assert (budget.day_limit, budget.minute_limit) == (100, 10)
    engine.report_quota(scope_id, limit_day=7500, limit_minute=300)
    with engine.transaction() as session:
        budget = budget_for(session, "api-football", session.get(SyncScope, scope_id))
        assert (budget.day_limit, budget.minute_limit) == (5000, 200)


def test_external_account_consumption_is_not_counted_as_local_use(engine):
    configured(engine)
    context = engine.claim("worker")
    reserve(engine, context)
    context.report_quota(limit_day=7500, remaining_day=6400, limit_minute=300, remaining_minute=298)
    reserve(engine, context)
    with Session(engine.engine) as session:
        budget = session.get(SyncBudget, "api-football")
        assert (budget.day_used, budget.day_limit) == (2, 100)
    assert quota(engine)["remaining_day"] == 6399


def test_remote_exhaustion_stops_before_local_budget_and_delayed_response_cannot_refund(engine):
    configured(engine)
    context = engine.claim("worker")
    reserve(engine, context)
    context.report_quota(limit_day=7500, remaining_day=1)
    reserve(engine, context)
    with pytest.raises(QuotaExhausted):
        reserve(engine, context)
    context.report_quota(limit_day=7500, remaining_day=7000)
    assert quota(engine)["remaining_day"] == 0
    with pytest.raises(QuotaExhausted):
        SyncEngine(engine.engine).reserve(
            context.job_id, context.scope_id, context.token, context.owner
        )
    with Session(engine.engine) as session:
        assert session.get(SyncBudget, "api-football").day_used == 2


def test_first_response_also_accounts_for_other_inflight_reservations(engine):
    configured(engine)
    context = engine.claim("worker")
    reserve(engine, context)
    reserve(engine, context)
    context.report_quota(limit_day=7500, remaining_day=1)
    assert quota(engine)["remaining_day"] == 0
    assert quota(engine)["pending_day"] == 1
    with pytest.raises(QuotaExhausted):
        reserve(engine, context)
    context.report_quota(limit_day=7500, remaining_day=2)
    assert quota(engine)["pending_day"] == 0
    assert quota(engine)["remaining_day"] == 0


@pytest.mark.parametrize("window", ["minute", "day"])
def test_remote_window_expires_without_resetting_the_other_budget(engine, monkeypatch, window):
    scope_id = configured(engine)
    context = engine.claim("worker")
    reserve(engine, context)
    context.report_quota(**{f"remaining_{window}": 0})
    with pytest.raises(QuotaExhausted):
        reserve(engine, context)
    instant = engine.clock[0]
    if window == "day":
        instant = (instant + timedelta(days=1)).replace(hour=0, minute=0, second=1)
    else:
        instant = (instant + timedelta(minutes=1)).replace(second=8)
    monkeypatch.setattr("src.sync.service.now", lambda session: instant)
    with engine.transaction() as session:
        control(session, lock=True)
        budget = reserve_provider_request(session, "api-football", session.get(SyncScope, scope_id))
        assert budget.minute_used == 1
        assert budget.day_used == (1 if window == "day" else 2)


def test_diagnostic_reserves_same_budget_while_global_automation_is_paused(engine):
    with engine.transaction() as session:
        control(session, lock=True)
        scope = SyncScope(name="Check", provider="api-football", kind="discovery", daily_limit=1)
        session.add(scope)
        reserve_provider_request(session, "api-football", scope)
        with pytest.raises(QuotaExhausted):
            reserve_provider_request(session, "api-football", scope)
        assert control(session).mode == "paused"


def test_remote_quota_never_copies_account_identity_or_unrecognized_fields(engine):
    configured(engine)
    with engine.transaction() as session:
        status = session.exec(
            select(ProviderSnapshot).where(ProviderSnapshot.kind == "status")
        ).one()
        status.payload = {**status.payload, "account": {"email": "private@example.invalid"}}
        session.add(status)
    context = engine.claim("worker")
    reserve(engine, context)
    context.report_quota(limit_day=7500, remaining_day=6400)
    payload = quota(engine)
    assert set(payload) <= {
        "day",
        "minute",
        "pending_day",
        "pending_minute",
        "remaining_day",
        "remaining_minute",
        "limit_day",
        "limit_minute",
        "checked_at",
        "credential_fingerprint",
        "next_request_at",
    }
    assert "private" not in str(payload) and "account" not in payload


def test_rotated_key_discards_other_account_capacity_without_refunding_local_use(
    engine, monkeypatch
):
    monkeypatch.setenv("API_FOOTBALL_KEY", "old-account-key")
    scope_id = configured(engine, daily_limit=5000, minute_limit=200)
    with engine.transaction() as session:
        status = session.exec(
            select(ProviderSnapshot).where(ProviderSnapshot.kind == "status")
        ).one()
        status.payload = {
            **status.payload,
            "credential_fingerprint": hashlib.sha256(b"old-account-key").hexdigest(),
        }
        session.add(status)
        assert effective_api_limits(session) == (7500, 300)
    context = engine.claim("worker")
    reserve(engine, context)
    context.report_quota(limit_day=7500, remaining_day=0)
    with pytest.raises(QuotaExhausted):
        reserve(engine, context)
    monkeypatch.setenv("API_FOOTBALL_KEY", "new-account-key")
    with engine.transaction() as session:
        assert effective_api_limits(session) == (100, 10)
    reserve(engine, context)
    with engine.transaction() as session:
        budget = budget_for(session, "api-football", session.get(SyncScope, scope_id))
        assert (budget.day_used, budget.day_limit) == (2, 100)
    assert quota(engine)["credential_fingerprint"] == hashlib.sha256(b"new-account-key").hexdigest()
    assert "new-account-key" not in str(quota(engine))


def test_status_body_report_does_not_finalize_another_pending_request(engine):
    configured(engine)
    context = engine.claim("worker")
    reserve(engine, context)
    reserve(engine, context)
    context.report_quota()  # The status transport completed, without quota headers.
    context.report_quota(limit_day=7500, remaining_day=1, finalize_request=False)
    assert quota(engine)["pending_day"] == 1
    assert quota(engine)["remaining_day"] == 0
    with pytest.raises(QuotaExhausted):
        reserve(engine, context)


def test_pacing_survives_restart_and_clock_minute_boundary_without_spending_requests(engine):
    configured(engine)
    context = engine.claim("worker")
    engine.clock[0] = engine.clock[0].replace(second=59, microsecond=0)
    context.reserve_request()
    engine.clock[0] += timedelta(seconds=1)
    restarted = SyncEngine(engine.engine)
    with pytest.raises(PacingWait) as caught:
        restarted.reserve(context.job_id, context.scope_id, context.token, context.owner)
    assert caught.value.retry_after == pytest.approx(5.1)
    with Session(engine.engine) as session:
        assert session.get(SyncBudget, "api-football").day_used == 1
    engine.clock[0] += timedelta(seconds=5.1)
    context.reserve_request()
    with Session(engine.engine) as session:
        assert session.get(SyncBudget, "api-football").day_used == 2


def test_paid_rate_is_still_spaced_and_local_slow_cap_wins(engine):
    scope_id = configured(engine, daily_limit=5000, minute_limit=300)
    context = engine.claim("worker")
    context.reserve_request()
    with pytest.raises(PacingWait) as caught:
        context.reserve_request()
    assert caught.value.retry_after == pytest.approx(0.3)
    engine.clock[0] += timedelta(seconds=1)
    with engine.transaction() as session:
        scope = session.get(SyncScope, scope_id)
        scope.minute_limit = 10
        session.add(scope)
    context.reserve_request()
    with pytest.raises(PacingWait) as caught:
        context.reserve_request()
    assert caught.value.retry_after == pytest.approx(6.1)


def test_worker_and_manual_connection_check_cannot_spend_same_remote_request(tmp_path):
    connection = create_engine(
        f"sqlite:///{(tmp_path / 'remote-quota.db').as_posix()}", connect_args={"timeout": 15}
    )
    SQLModel.metadata.create_all(connection)
    engine = SyncEngine(connection)
    scope_id = configured(engine)
    context = engine.claim("worker")
    engine.report_quota(scope_id, limit_day=7500, remaining_day=1)
    with engine.transaction() as session:
        diagnostic = SyncScope(name="Check", provider="api-football", kind="discovery")
        session.add(diagnostic)
        diagnostic_id = diagnostic.id
    barrier = Barrier(2)

    def concurrent_reserve(manual):
        barrier.wait(timeout=5)
        try:
            if manual:
                with engine.transaction() as session:
                    control(session, lock=True)
                    reserve_provider_request(
                        session, "api-football", session.get(SyncScope, diagnostic_id)
                    )
            else:
                reserve(engine, context)
            return "reserved"
        except QuotaExhausted:
            return "limited"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            calls = [pool.submit(concurrent_reserve, manual) for manual in (True, False)]
            assert sorted(call.result(timeout=20) for call in calls) == ["limited", "reserved"]
        assert quota(engine)["remaining_day"] == 0
        with Session(connection) as session:
            assert session.get(SyncBudget, "api-football").day_used == 1
    finally:
        connection.dispose()
