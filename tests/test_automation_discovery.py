"""Discovery prepares verified selectors, cache saves requests, cadence respects quota."""

import datetime as dt
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from src import database
from src.models import Fase, ProviderMapping, ProviderSnapshot, Temporada
from src.providers.automation import DiscoveryHandler, FixturesHandler
from src.sync.handlers import FetchResult
from src.sync.models import SyncBudget, SyncIssue, SyncObservation, SyncScope
from src.sync.service import SyncEngine, enqueue, set_global_mode


def context():
    return SimpleNamespace(job_id="discovery-test", actor="service:sync", observed_at=None)


def source(year=2026, country="Colombia", coverage=True):
    return {
        "response": [
            {
                "league": {"id": 239, "name": "Primera A", "type": "League"},
                "country": {"name": country},
                "seasons": [
                    {
                        "year": year,
                        "current": True,
                        "coverage": {"fixtures": {"events": True}, "standings": True}
                        if coverage
                        else {},
                    }
                ],
            }
        ]
    }


def scope(session, kind="discovery", **kwargs):
    row = SyncScope(
        name="Colombia",
        provider="api-football",
        kind=kind,
        mode="automatic",
        selector=kwargs.pop("selector", {"country": "Colombia"}),
        **kwargs,
    )
    session.add(row)
    session.flush()
    return row


def test_discovery_prepares_paused_profiles_once_without_inventing_editions(client):
    with Session(database.engine) as session:
        parent = scope(session)
        handler = DiscoveryHandler()
        first = handler.apply(session, parent, source(), context())
        session.commit()
        second = handler.apply(session, parent, source(), context())
        session.commit()
        plans = session.exec(select(SyncScope).where(SyncScope.kind == "fixtures")).all()
        assert len(first["prepared_profiles"]) == 1 and second["prepared_profiles"] == []
        assert len(plans) == 1 and plans[0].mode == "paused"
        assert plans[0].selector["coverage_status"] == "access_unverified"
        assert "round_prefix" not in plans[0].selector
        assert session.exec(select(Temporada)).all() == []
        assert session.exec(select(SyncIssue).where(SyncIssue.scope_id == plans[0].id)).first()


@pytest.mark.parametrize(
    "payload", [source(country="Brazil"), source(coverage=False), source(year=2100)]
)
def test_uncovered_or_foreign_competitions_never_get_active_profiles(client, payload):
    with Session(database.engine) as session:
        parent = scope(session)
        result = DiscoveryHandler().apply(session, parent, payload, context())
        session.commit()
        assert result["prepared_profiles"] == []


def test_discovery_prepares_standings_only_when_local_edition_is_unambiguous(catalog):
    with Session(database.engine) as session:
        parent = scope(session)
        season = Temporada(competicion_id=catalog["comp"]["id"], nombre="2026")
        session.add(season)
        session.flush()
        session.add(
            ProviderMapping(
                provider="api-football",
                entity_type="season",
                local_id=season.id,
                external_id="2026",
                external_scope="league:239",
            )
        )
        session.flush()
        DiscoveryHandler().apply(session, parent, source(), context())
        session.commit()
        plan = session.exec(select(SyncScope).where(SyncScope.kind == "standings")).one()
        assert plan.mode == "paused" and plan.selector["season_id"] == season.id


def test_discovery_does_not_choose_between_multiple_phases(catalog):
    with Session(database.engine) as session:
        parent = scope(session)
        season = Temporada(competicion_id=catalog["comp"]["id"], nombre="2026")
        session.add(season)
        session.flush()
        session.add(
            ProviderMapping(
                provider="api-football",
                entity_type="season",
                local_id=season.id,
                external_id="2026",
                external_scope="league:239",
            )
        )
        session.add_all(
            [
                Fase(temporada_id=season.id, nombre="Apertura"),
                Fase(temporada_id=season.id, nombre="Clausura"),
            ]
        )
        session.flush()
        DiscoveryHandler().apply(session, parent, source(), context())
        assert not session.exec(select(SyncScope).where(SyncScope.kind == "standings")).first()


def test_fixture_cache_reuses_only_matching_fresh_metadata(client, monkeypatch):
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        def league(self, *args):
            calls.append("league")
            return source()

        def teams(self, *args):
            calls.append("teams")
            return {"response": []}

        def fixtures(self, *args):
            calls.append("fixtures")
            return {"response": [], "results": 0}

    monkeypatch.setattr("src.providers.automation.APIFootballClient", Provider)
    with Session(database.engine, expire_on_commit=False) as session:
        target = scope(session, "fixtures", selector={"league_id": 239, "season": 2026})
        session.commit()
    handler = FixturesHandler()
    first = handler.fetch(target, context())
    assert calls == ["league", "teams", "fixtures"]
    with Session(database.engine) as session:
        session.add(SyncObservation(scope_id=target.id, digest="test", payload=first.payload))
        session.commit()
    calls.clear()
    handler.fetch(target, context())
    assert calls == ["fixtures"]
    with Session(database.engine) as session:
        observation = session.exec(select(SyncObservation)).one()
        observation.payload = {
            **observation.payload,
            "metadata_checked_at": (dt.datetime.now(dt.UTC) - dt.timedelta(days=2)).isoformat(),
        }
        session.add(observation)
        checkpoint = session.exec(
            select(ProviderSnapshot).where(ProviderSnapshot.entity_type == "league")
        ).one()
        checkpoint.payload = {
            **checkpoint.payload,
            "metadata_checked_at": observation.payload["metadata_checked_at"],
        }
        session.add(checkpoint)
        session.commit()
    calls.clear()
    handler.fetch(target, context())
    assert calls == ["league", "teams", "fixtures"]


def test_adaptive_cadence_changes_with_match_window_and_budget(client):
    instant = dt.datetime(2026, 9, 27, 18, tzinfo=dt.UTC)
    with Session(database.engine) as session:
        target = scope(session, "fixtures", interval_seconds=30, daily_limit=10000)
        live = {"fixtures": {"response": [{"fixture": {"status": {"short": "1H"}}}]}}
        # The pilot's provider cap still applies if a profile requests a larger allowance.
        assert FixturesHandler.next_interval(session, target, live, instant) >= 90
        target.daily_limit = 100
        session.add(target)
        session.flush()
        assert FixturesHandler.next_interval(session, target, live, instant) >= 90
        session.add(SyncBudget(provider="api-football", day="2026-09-27", day_used=78))
        session.flush()
        assert FixturesHandler.next_interval(session, target, live, instant) >= 3600
        archived = {
            "fixtures": {
                "response": [
                    {"fixture": {"date": "2025-01-01T12:00:00+00:00", "status": {"short": "FT"}}}
                ]
            }
        }
        assert FixturesHandler.next_interval(session, target, archived, instant) >= 604800


def test_cadence_never_runs_faster_than_operator_interval(client):
    with Session(database.engine) as session:
        target = scope(session, "fixtures", interval_seconds=3600, daily_limit=10000)
        live = {"fixtures": {"response": [{"fixture": {"status": {"short": "1H"}}}]}}
        assert FixturesHandler.next_interval(session, target, live, dt.datetime.now(dt.UTC)) == 3600


def test_worker_persists_adaptive_next_run_even_in_observation_mode(client):
    runner = SyncEngine(database.engine)
    with runner.transaction() as session:
        set_global_mode(session, "observe", "tester")
        target = scope(
            session, "fixtures", selector={"league_id": 239, "season": 2026}, interval_seconds=30
        )
        enqueue(session, target)
        scope_id = target.id
    work = runner.claim("worker")
    observed = runner.publish(work, FetchResult({"fixtures": {"response": []}}), FixturesHandler())
    with Session(database.engine) as session:
        target = session.get(SyncScope, scope_id)
        assert observed["next_interval_seconds"] >= 86400
        assert target.next_run_at >= target.last_checked_at + dt.timedelta(days=1)
