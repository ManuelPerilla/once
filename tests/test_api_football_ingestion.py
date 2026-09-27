"""Real response shapes and cross-source boundaries for the API-Football adapter."""

import datetime as dt
from types import SimpleNamespace

import httpx
import pytest
from sqlmodel import Session, select

from src import database
from src.models import Competicion, Equipo, MediaAsset, Partido, ProviderMapping, Temporada
from src.providers import APIFootballClient, ProviderError
from src.providers.api_batch import BatchDetailsHandler
from src.providers.automation import FixturesHandler, _identity, validate_scope_config
from src.sync.models import SyncScope
from src.sync.service import PermanentError


def context():
    return SimpleNamespace(job_id="api-football-test", actor="service:sync", observed_at=None)


def plan(session, kind="fixtures", **selector):
    scope = SyncScope(
        name="Colombia API",
        provider="api-football",
        kind=kind,
        selector={"league_id": 239, "season": 2026, **selector},
    )
    session.add(scope)
    session.flush()
    return scope


def payload():
    return {
        "league": {
            "response": [
                {
                    "league": {
                        "id": 239,
                        "name": "Primera A",
                        "type": "League",
                        "logo": "https://media.api-sports.io/football/leagues/239.png",
                    },
                    "country": {"name": "Colombia"},
                    "seasons": [{"year": 2026, "current": True}],
                }
            ]
        },
        "teams": {
            "response": [
                {
                    "team": {
                        "id": 100,
                        "name": "Norte Real",
                        "national": False,
                        "logo": "https://media.api-sports.io/football/teams/100.png",
                        "founded": 1930,
                    }
                },
                {
                    "team": {
                        "id": 101,
                        "name": "Sur Unido",
                        "national": False,
                        "logo": "https://media.api-sports.io/football/teams/101.png",
                    }
                },
            ]
        },
        "fixtures": {
            "response": [
                {
                    "fixture": {
                        "id": fixture_id,
                        "date": f"2026-{month}-12T18:00:00+00:00",
                        "status": {"short": "FT"},
                    },
                    "league": {"id": 239, "season": 2026, "round": f"{edition} - 1"},
                    "teams": {"home": {"id": 100}, "away": {"id": 101}},
                    "goals": {"home": 2, "away": 0},
                }
                for fixture_id, edition, month in [
                    (1200, "Apertura", "01"),
                    (1300, "Clausura", "07"),
                ]
            ]
        },
    }


def test_client_accepts_status_object_and_never_exposes_error_body():
    observed = []

    def transport(url, **kwargs):
        observed.append((url, kwargs))
        return httpx.Response(
            200,
            json={"response": {"subscription": {"active": True}}},
            request=httpx.Request("GET", url),
        )

    client = APIFootballClient(api_key="test-secret", transport=transport)
    assert client.status()["response"]["subscription"]["active"] is True
    assert observed[0][0].endswith("/status")
    assert observed[0][1]["headers"]["x-apisports-key"] == "test-secret"

    def rejected(url, **kwargs):
        return httpx.Response(
            200,
            json={"errors": {"token": "test-secret"}, "response": []},
            request=httpx.Request("GET", url),
        )

    with pytest.raises(ProviderError) as caught:
        APIFootballClient(api_key="test-secret", transport=rejected).league(239)
    assert not caught.value.retryable and "test-secret" not in str(caught.value)


@pytest.mark.parametrize("status,errors", [(200, {"rateLimit": "slow"}), (499, {})])
def test_provider_timeout_and_json_rate_limit_are_retryable(status, errors):
    def transport(url, **kwargs):
        return httpx.Response(
            status, json={"errors": errors, "response": []}, request=httpx.Request("GET", url)
        )

    with pytest.raises(ProviderError) as caught:
        APIFootballClient(api_key="test", transport=transport).league(239)
    assert caught.value.retryable


def test_fixture_import_automatically_separates_editions_and_preserves_source_logos(client):
    with Session(database.engine) as session:
        previous_teams = len(session.exec(select(Equipo)).all())
        scope = plan(session)
        first = FixturesHandler().apply(session, scope, payload(), context())
        session.commit()
        assert first["created"] == 2 and len(first["season_ids"]) == 2
        assert {row.nombre for row in session.exec(select(Temporada))} == {
            "2026 Apertura",
            "2026 Clausura",
        }
        assert len(session.exec(select(Equipo)).all()) == previous_teams + 2
        assert len(session.exec(select(MediaAsset)).all()) == 3
        assert all(
            row.logo.startswith("https://media.api-sports.io/")
            for row in session.exec(
                select(Equipo).where(Equipo.nombre.in_(["Norte Real", "Sur Unido"]))
            )
        )
        second = FixturesHandler().apply(session, scope, payload(), context())
        session.commit()
        assert second["created"] == 0 and second["changed"] == 0
        assert len(session.exec(select(Partido)).all()) == 2


def test_season_of_another_year_does_not_block_new_season(client):
    with Session(database.engine) as session:
        scope = plan(session)
        comp = Competicion(nombre="Primera A", logo="", tipo="liga_nacional", pais="Colombia")
        session.add(comp)
        session.flush()
        session.add(Temporada(competicion_id=comp.id, nombre="2025 Apertura"))
        session.flush()
        season, _ = _identity(
            session,
            scope,
            "season",
            2026,
            {"competicion_id": comp.id, "nombre": "2026 Apertura"},
            external_scope="league:239:edition:Apertura",
            context=context(),
        )
        assert season is not None


def test_explicit_team_links_reuse_canonical_id_and_conflicts_are_rejected(client):
    with Session(database.engine) as session:
        previous_teams = len(session.exec(select(Equipo)).all())
        team = Equipo(
            nombre="Club histórico",
            logo="/api/assets/crests/local.svg",
            tipo="club",
            pais="Colombia",
        )
        session.add(team)
        session.flush()
        scope = plan(session, team_ids={"100": team.id})
        FixturesHandler().apply(session, scope, payload(), context())
        session.commit()
        link = session.exec(
            select(ProviderMapping).where(
                ProviderMapping.provider == "api-football",
                ProviderMapping.entity_type == "team",
                ProviderMapping.external_id == "100",
            )
        ).one()
        assert (
            link.local_id == team.id
            and len(session.exec(select(Equipo)).all()) == previous_teams + 2
        )
        assert team.logo == "/api/assets/crests/local.svg"
        with pytest.raises(PermanentError, match="otra ficha"):
            _identity(
                session,
                scope,
                "team",
                100,
                {"nombre": "Norte Real", "pais": "Colombia", "tipo": "club"},
                target_id=999,
                context=context(),
            )


def test_batch_details_uses_twenty_ids_max_and_retains_missing_details(client, monkeypatch):
    with Session(database.engine) as session:
        scope = plan(session)
        FixturesHandler().apply(session, scope, payload(), context())
        batch = plan(session, kind="details_batch")
        session.commit()
        selected = BatchDetailsHandler._pending(batch)
        assert len(selected) == 2
        incoming = {
            "selected": selected,
            "response": payload()["fixtures"]["response"],
            "more": False,
        }
        result = BatchDetailsHandler().apply(session, batch, incoming, context())
        session.commit()
        assert result["matches_received"] == 2
        # Both fixture dates are historical; successful batches are not fetched again.
        assert BatchDetailsHandler._pending(batch) == []
        batch_id = batch.id
    calls = []

    def pending(_):
        return [{"fixture_id": value, "match_id": value, "live": False} for value in range(1, 22)]

    class Client:
        def __init__(self, **kwargs):
            pass

        def fixture_batch(self, ids):
            calls.append(ids)
            return {"response": []}

    monkeypatch.setattr(BatchDetailsHandler, "_pending", staticmethod(pending))
    monkeypatch.setattr(BatchDetailsHandler, "_batch_size", staticmethod(lambda: 20))
    monkeypatch.setattr("src.providers.api_batch.APIFootballClient", Client)
    with Session(database.engine) as session:
        result = BatchDetailsHandler().fetch(session.get(SyncScope, batch_id), context())
    assert len(calls[0]) == 20 and result.payload["more"]


def test_same_existing_fixture_requires_review_instead_of_creating_duplicate(client):
    with Session(database.engine) as session:
        scope = plan(session)
        FixturesHandler().apply(session, scope, payload(), context())
        first = session.exec(
            select(ProviderMapping).where(
                ProviderMapping.entity_type == "match", ProviderMapping.external_id == "1200"
            )
        ).one()
        first.provider = "openfootball"
        session.add(first)
        session.commit()
        result = FixturesHandler().apply(session, scope, payload(), context())
        assert result["skipped"] == [{"fixture_id": 1200, "reason": "match_identity_review"}]
        assert len(session.exec(select(Partido)).all()) == 2


def test_invalid_reviewed_team_ids_fail_before_source_fetch():
    with pytest.raises(ValueError):
        validate_scope_config(
            "api-football",
            "fixtures",
            {"league_id": 239, "season": dt.date.today().year, "team_ids": {"100": True}},
        )


def test_plan_restriction_exposes_only_numeric_allowed_seasons():
    def transport(url, **kwargs):
        return httpx.Response(
            200,
            json={
                "errors": {
                    "plan": "Free plans do not have access to this season, try from 2022 to 2024. secret-value"
                },
                "response": [],
            },
            request=httpx.Request("GET", url),
        )

    with pytest.raises(ProviderError) as caught:
        APIFootballClient(api_key="test", transport=transport).fixtures(239, 2026)
    assert caught.value.code == "plan" and caught.value.allowed_seasons == [2022, 2023, 2024]
    assert "secret-value" not in str(caught.value)


def test_free_batch_fetches_one_fixture_without_using_restricted_ids(client, monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def fixture(self, fixture_id):
            calls.append(fixture_id)
            return {"response": []}

        def fixture_batch(self, ids):
            pytest.fail("Free access must not use the ids parameter")

    monkeypatch.setattr("src.providers.api_batch.APIFootballClient", Client)
    monkeypatch.setattr("src.providers.api_batch.fixture_dependencies_ready", lambda scope: True)
    monkeypatch.setattr(
        BatchDetailsHandler,
        "_pending",
        staticmethod(
            lambda scope: [
                {"fixture_id": 1200, "match_id": 1},
                {"fixture_id": 1300, "match_id": 2},
            ]
        ),
    )
    with Session(database.engine) as session:
        result = BatchDetailsHandler().fetch(plan(session, kind="details_batch"), context())
    assert calls == [1200] and result.payload["more"] is True


def test_group_tables_resolve_by_fixture_participants_not_array_order(client):
    from src.models import Grupo, OfficialStandingSnapshot
    from src.providers.api_standings import BatchStandingsHandler

    data = payload()
    data["teams"]["response"].extend(
        [
            {"team": {"id": 102, "name": "Oriente Azul"}},
            {"team": {"id": 103, "name": "Occidente Verde"}},
        ]
    )
    fixtures = []
    for fixture_id, edition, home, away in (
        (1, "Apertura", 100, 101),
        (2, "Apertura", 102, 103),
        (3, "Clausura", 100, 102),
        (4, "Clausura", 101, 103),
    ):
        fixtures.append(
            {
                "fixture": {"id": fixture_id, "status": {"short": "FT"}},
                "league": {"id": 239, "season": 2026, "round": f"{edition} - Quadrangular - 1"},
                "teams": {"home": {"id": home}, "away": {"id": away}},
                "goals": {"home": 0, "away": 0},
            }
        )
    data["fixtures"]["response"] = fixtures

    def table(ids):
        return [
            {
                "team": {"id": team},
                "group": "Group A",
                "rank": index + 1,
                "points": 1,
                "goalsDiff": 0,
                "all": {
                    "played": 1,
                    "win": 0,
                    "draw": 1,
                    "lose": 0,
                    "goals": {"for": 0, "against": 0},
                },
            }
            for index, team in enumerate(ids)
        ]

    tables = {
        "response": [
            {
                "league": {
                    "id": 239,
                    "season": 2026,
                    "standings": [table([100, 102]), table([100, 101])],
                }
            }
        ]
    }
    with Session(database.engine) as session:
        scope = plan(session)
        FixturesHandler().apply(session, scope, data, context())
        result = BatchStandingsHandler().apply(session, scope, tables, context())
        session.commit()
        assert result["tables"] == 2 and result["requires_review"] == 0
        assert len(session.exec(select(Grupo)).all()) == 2
        assert len(session.exec(select(OfficialStandingSnapshot)).all()) == 2
        assert BatchStandingsHandler().apply(session, scope, tables, context())["changed"] == 0


@pytest.mark.parametrize("kind", ["details_batch", "standings_batch"])
def test_batch_waits_for_fixtures_without_spending_requests_or_raising_issues(
    client, kind, monkeypatch
):
    from src.providers.api_standings import BatchStandingsHandler
    from src.sync.models import SyncIssue

    monkeypatch.setattr(
        "src.providers.automation._fetch",
        lambda *args: pytest.fail("No provider call before fixtures"),
    )
    handler = BatchDetailsHandler() if kind == "details_batch" else BatchStandingsHandler()
    with Session(database.engine) as session:
        scope = plan(session, kind=kind)
        session.commit()
        response = handler.fetch(scope, context())
        assert response.payload["waiting_dependencies"] is True
        assert (
            handler.next_interval(session, scope, response.payload, dt.datetime.now(dt.UTC)) == 300
        )
        applied = handler.apply(session, scope, response.payload, context())
        assert applied["waiting_dependencies"] and applied["changed"] == 0
        assert session.exec(select(SyncIssue)).all() == []


def test_historical_standings_poll_weekly_after_first_success(client):
    from src.providers.api_standings import BatchStandingsHandler

    with Session(database.engine) as session:
        scope = plan(session, kind="standings_batch", season=2024)
        scope.interval_seconds = 3600
        assert (
            BatchStandingsHandler.next_interval(
                session, scope, {"response": [{}]}, dt.datetime(2026, 9, 27, tzinfo=dt.UTC)
            )
            == 604800
        )


def test_annual_championship_is_separate_from_apertura_and_clausura(client):
    data = payload()
    final = {**data["fixtures"]["response"][0]}
    final["fixture"] = {"id": 999, "status": {"short": "FT"}}
    final["league"] = {"id": 239, "season": 2026, "round": "Championship - Final"}
    data["fixtures"]["response"].append(final)
    with Session(database.engine) as session:
        scope = plan(session)
        result = FixturesHandler().apply(session, scope, data, context())
        assert result["created"] == 3 and len(result["season_ids"]) == 3
        seasons = session.exec(select(Temporada)).all()
        assert {row.nombre for row in seasons} == {
            "2026 Apertura",
            "2026 Clausura",
            "2026 Championship",
        }


def test_fixture_metadata_checkpoint_survives_quota_between_requests(client, monkeypatch):
    from src.sync.service import QuotaExhausted

    calls, blocked = [], {"teams", "fixtures"}

    class Provider:
        def __init__(self, **kwargs):
            pass

        def league(self, *args):
            calls.append("league")
            return payload()["league"]

        def teams(self, *args):
            calls.append("teams")
            if "teams" in blocked:
                blocked.remove("teams")
                raise QuotaExhausted("Wait", 60)
            return payload()["teams"]

        def fixtures(self, *args):
            calls.append("fixtures")
            if "fixtures" in blocked:
                blocked.remove("fixtures")
                raise QuotaExhausted("Wait", 60)
            return payload()["fixtures"]

    monkeypatch.setattr("src.providers.automation.APIFootballClient", Provider)
    with Session(database.engine, expire_on_commit=False) as session:
        scope = plan(session)
        session.commit()
    handler = FixturesHandler()
    for _ in range(2):
        with pytest.raises(QuotaExhausted):
            handler.fetch(scope, context())
    assert handler.fetch(scope, context()).payload["fixtures"]["response"]
    assert calls == ["league", "teams", "teams", "fixtures", "fixtures"]


def test_transport_short_wait_rechecks_pause_before_network(monkeypatch):
    from src.providers.automation import Transport
    from src.sync.service import PacingWait, StaleWork

    attempts, sleeps = [], []

    def reserve(provider):
        attempts.append(provider)
        if len(attempts) == 1:
            raise PacingWait("spacing", 6.1)
        raise StaleWork("paused")

    monkeypatch.setattr("src.providers.automation.time.sleep", sleeps.append)
    ctx = SimpleNamespace(reserve_request=reserve, report_quota=lambda **kwargs: None)
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: pytest.fail("No HTTP after pause"))
    ) as client:
        with pytest.raises(StaleWork):
            Transport(ctx, client)("https://v3.football.api-sports.io/fixtures")
    assert sleeps == [6.1] and len(attempts) == 2


@pytest.mark.parametrize(
    "year, rounds",
    [
        (2022, ["Apertura - 1", "Apertura - 17", "Quarter-finals", "Semi-finals", "Final"]),
        (
            2024,
            [
                "Apertura - 1",
                "Apertura - 15",
                "Quadrangular Semi-finals - 1",
                "Quadrangular Semi-finals - 6",
                "Championship - Final",
            ],
        ),
    ],
)
def test_womens_historical_tournament_preserves_annual_edition_and_all_phases(client, year, rounds):
    from src.models import Fase

    data = payload()
    league = data["league"]["response"][0]
    league["league"] = {"id": 712, "name": "Liga Femenina", "type": "League"}
    league["seasons"] = [{"year": year, "current": False}]
    template = data["fixtures"]["response"][0]
    data["fixtures"]["response"] = [
        {
            **template,
            "fixture": {"id": 2000 + index, "status": {"short": "FT"}},
            "league": {"id": 712, "season": year, "round": label},
        }
        for index, label in enumerate(rounds)
    ]
    with Session(database.engine) as session:
        scope = plan(session, league_id=712, season=year)
        result = FixturesHandler().apply(session, scope, data, context())
        assert result["created"] == len(rounds) and result["skipped"] == []
        assert len(session.exec(select(Temporada)).all()) == 1
        assert session.exec(select(Temporada)).one().nombre == str(year)
        assert (
            session.exec(select(ProviderMapping).where(ProviderMapping.entity_type == "season"))
            .one()
            .external_scope
            == "league:712"
        )
        assert {phase.nombre for phase in session.exec(select(Fase))} == {
            label.rsplit(" - ", 1)[0] if label.rsplit(" - ", 1)[-1].isdigit() else label
            for label in rounds
        }
        assert FixturesHandler().apply(session, scope, data, context())["changed"] == 0


@pytest.mark.parametrize(
    "league_id,year,rounds",
    [
        (239, 2024, ["Apertura - 1", "Final"]),
        (712, 2026, ["Apertura - 1", "Final"]),
        (712, 2024, ["Apertura - 1", "Clausura - 1", "Final"]),
        (712, 2024, ["Apertura - 1", "Unreviewed Phase"]),
    ],
)
def test_womens_annual_policy_never_applies_to_other_or_unknown_formats(league_id, year, rounds):
    from src.providers.automation import _annual_women_layout

    assert not _annual_women_layout(
        league_id, year, [{"league": {"round": value}} for value in rounds]
    )


@pytest.mark.parametrize(
    "league_id,year,promotion_round,accepted",
    [
        (240, 2022, "Promotion Play-offs - Final", True),
        (240, 2023, "Promotion Play-offs - Final", False),
        (239, 2022, "Promotion Play-offs - Final", False),
        (240, 2022, "Promotion Play-offs - Semi-finals", False),
    ],
)
def test_primera_b_promotion_final_has_a_separate_reviewed_historical_edition(
    client, league_id, year, promotion_round, accepted
):
    data = payload()
    league = data["league"]["response"][0]
    league["league"] = {"id": league_id, "name": "Primera B", "type": "League"}
    league["seasons"] = [{"year": year, "current": False}]
    template = data["fixtures"]["response"][0]
    rounds = [
        "Apertura - 1",
        "Clausura - 1",
        "Championship - Final",
        "Championship - Final",
        promotion_round,
        promotion_round,
    ]
    data["fixtures"]["response"] = [
        {
            **template,
            "fixture": {"id": 3000 + index, "status": {"short": "FT"}},
            "league": {"id": league_id, "season": year, "round": label},
        }
        for index, label in enumerate(rounds)
    ]
    with Session(database.engine) as session:
        scope = plan(session, league_id=league_id, season=year)
        result = FixturesHandler().apply(session, scope, data, context())
        if not accepted:
            assert result["requires_review"] is True
            assert session.exec(select(Temporada)).all() == []
            assert session.exec(select(Partido)).all() == []
            return
        assert result["created"] == 6 and result["skipped"] == []
        assert len(result["season_ids"]) == 4
        promotion = session.exec(
            select(Temporada).where(Temporada.nombre == "2022 Promotion Play-offs")
        ).one()
        assert (
            len(session.exec(select(Partido).where(Partido.temporada_id == promotion.id)).all())
            == 2
        )
        mapping = session.exec(
            select(ProviderMapping).where(
                ProviderMapping.entity_type == "season", ProviderMapping.local_id == promotion.id
            )
        ).one()
        assert mapping.external_scope == "league:240:edition:Promotion Play-offs"
        assert FixturesHandler().apply(session, scope, data, context())["changed"] == 0
