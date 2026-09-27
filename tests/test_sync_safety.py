"""Regression tests for destructive feed gaps, source authority and bounded retention."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from src import database
from src.models import (
    AlineacionPartido,
    AuditChange,
    DataIssue,
    Estadio,
    FieldState,
    Jugador,
    ParticipacionTemporada,
    Partido,
    ProviderMapping,
    Temporada,
)
from src.providers.sync import _player_from_source, _venue_for_fixture, sync_match_detail
from src.sync.maintenance import cleanup
from src.sync.models import SyncHistory, SyncJob, SyncNotification, SyncObservation, SyncScope
from src.sync.service import budget_for


def test_match_date_bounds_preserve_local_day_and_exclude_next_midnight(
    authenticated, match_payload
):
    for stamp in (
        "2026-09-27T04:59:59Z",
        "2026-09-27T05:00:00Z",
        "2026-09-28T04:59:59Z",
        "2026-09-28T05:00:00Z",
    ):
        assert (
            authenticated.post("/partidos/", json={**match_payload, "fecha": stamp}).status_code
            == 200
        )
    params = {"date_start": "2026-09-27T00:00:00-05:00", "date_end": "2026-09-28T00:00:00-05:00"}
    result = authenticated.get("/public/partidos/page", params=params)
    assert result.status_code == 200 and result.json()["total"] == 2
    assert (
        authenticated.get(
            "/public/partidos/page", params={"date_start": "2026-09-27T00:00:00"}
        ).status_code
        == 422
    )
    assert (
        authenticated.get(
            "/public/partidos/page",
            params={"date_start": params["date_end"], "date_end": params["date_start"]},
        ).status_code
        == 422
    )


def test_player_position_cannot_override_an_explicitly_protected_empty_field(client):
    with Session(database.engine) as session:
        player = Jugador(nombre="Jugador", posicion=None)
        session.add(player)
        session.flush()
        session.add(
            ProviderMapping(
                provider="api-football", entity_type="player", external_id="77", local_id=player.id
            )
        )
        session.add(
            FieldState(
                entity_type="player",
                entity_id=player.id,
                field="posicion",
                protected=True,
                source="manual:auditor",
            )
        )
        session.commit()
        assert _player_from_source(session, {"id": 77}, position="G").posicion is None
        assert session.exec(select(DataIssue)).one().field == "posicion"


def test_free_provider_budget_cannot_exceed_pilot_cap(client):
    with Session(database.engine) as session:
        scope = SyncScope(
            name="Petición de cuota mayor",
            provider="api-football",
            kind="fixtures",
            daily_limit=100000,
        )
        session.add(scope)
        session.flush()
        assert budget_for(session, "api-football", scope).day_limit == 100


def test_same_name_venue_requires_identity_review(client):
    with Session(database.engine) as session:
        venue = Estadio(nombre="Estadio Central", ciudad="Bogotá")
        session.add(venue)
        session.commit()
        assert (
            _venue_for_fixture(
                session,
                {"fixture": {"venue": {"id": 55, "name": venue.nombre, "city": venue.ciudad}}},
            )
            is None
        )
        assert (
            session.exec(
                select(ProviderMapping).where(ProviderMapping.entity_type == "venue")
            ).all()
            == []
        )
        assert session.exec(select(DataIssue)).one().proposed["candidate_id"] == venue.id


def test_partial_lineup_preserves_other_team_and_records_creation(authenticated, match_payload):
    match_id = authenticated.post("/partidos/", json=match_payload).json()["id"]
    with Session(database.engine) as session:
        match = session.get(Partido, match_id)
        for kind, external, local in (
            ("match", 90, match.id),
            ("team", 100, match.equipo_local_id),
            ("team", 101, match.equipo_visitante_id),
        ):
            session.add(
                ProviderMapping(
                    provider="api-football",
                    entity_type=kind,
                    external_id=str(external),
                    local_id=local,
                )
            )
        session.commit()
        empty = {"response": []}
        entries = [
            {
                "team": {"id": team},
                "startXI": [{"player": {"id": team + 1, "name": f"Jugador {team}", "pos": "G"}}],
            }
            for team in (100, 101)
        ]
        sync_match_detail(
            session,
            match.id,
            events_payload=empty,
            statistics_payload=empty,
            lineups_payload={"response": entries, "_complete": True},
        )
        original = {row.id for row in session.exec(select(AlineacionPartido)).all()}
        assert len(original) == 2
        sync_match_detail(
            session,
            match.id,
            events_payload=empty,
            statistics_payload=empty,
            lineups_payload={"response": entries[:1], "_complete": True},
        )
        assert {row.id for row in session.exec(select(AlineacionPartido)).all()} == original
        assert session.exec(select(DataIssue).where(DataIssue.entity_type == "lineup")).one()
        created = session.exec(
            select(AuditChange).where(
                AuditChange.entity_type == "lineup", AuditChange.action == "source_create"
            )
        ).all()
        assert len(created) == 2


def test_retention_keeps_active_work_audit_and_referenced_observations(client):
    old = datetime.now(UTC) - timedelta(days=45)
    with Session(database.engine) as session:
        scope = SyncScope(name="Archivo", provider="openfootball", kind="archive")
        session.add(scope)
        session.flush()
        observations = [
            SyncObservation(scope_id=scope.id, digest=str(i), received_at=old, last_seen_at=old)
            for i in range(2)
        ]
        session.add_all(observations)
        session.flush()
        session.add_all(
            [
                SyncJob(
                    scope_id=scope.id,
                    status="succeeded",
                    finished_at=old,
                    observation_id=observations[0].id,
                ),
                SyncJob(
                    scope_id=scope.id,
                    status="running",
                    created_at=old,
                    observation_id=observations[1].id,
                ),
                SyncNotification(topic="catalog", delivered_at=old, sequence=1),
                SyncNotification(topic="catalog"),
                SyncHistory(actor="service:sync", action="test", created_at=old),
            ]
        )
        session.commit()
    assert cleanup(database.engine) == {"jobs": 1, "observations": 1, "notifications": 1}
    with Session(database.engine) as session:
        assert session.exec(select(SyncJob)).one().status == "running"
        assert session.exec(select(SyncObservation)).one().digest == "1"
        assert session.exec(select(SyncHistory)).one().action == "test"
        assert session.exec(select(SyncNotification)).one().sequence is None


def test_deleting_entities_with_edition_history_is_a_reviewable_conflict(authenticated, catalog):
    with Session(database.engine) as session:
        season = Temporada(nombre="2025", competicion_id=catalog["comp"]["id"])
        session.add(season)
        session.flush()
        session.add(
            ParticipacionTemporada(
                equipo_id=catalog["teams"][0]["id"], temporada_id=season.id, source="openfootball"
            )
        )
        session.commit()
    assert authenticated.delete(f"/equipos/{catalog['teams'][0]['id']}").status_code == 409
    assert authenticated.delete(f"/competiciones/{catalog['comp']['id']}").status_code == 409


def test_recent_orders_registration_and_newest_orders_match_date(authenticated, match_payload):
    dated = authenticated.post(
        "/partidos/", json={**match_payload, "fecha": "2026-10-01T18:00:00Z"}
    ).json()
    undated = authenticated.post("/partidos/", json=match_payload).json()
    assert (
        authenticated.get("/public/partidos/page?sort=recent").json()["items"][0]["id"]
        == undated["id"]
    )
    assert (
        authenticated.get("/public/partidos/page?sort=newest").json()["items"][0]["id"]
        == dated["id"]
    )
