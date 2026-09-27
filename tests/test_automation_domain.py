"""Critical domain invariants for automatic ingestion and human corrections."""

import datetime
import os

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, select

from src.audit.service import (
    AuditConflict,
    apply_source_changes,
    correct_field,
    protect_manual_fields,
    release_field,
)
from src.football.projections import (
    StandingsScopeError,
    read_standings,
    rebuild_season_standings,
    scope_key,
    store_official_standings,
)
from src.football.standings import StandingsConfig, calculate_standings
from src.models import (
    AuditChange,
    Competicion,
    DataIssue,
    EntityRevision,
    Equipo,
    EstadoPartido,
    Fase,
    Grupo,
    ParticipacionFase,
    ParticipacionGrupo,
    ParticipacionTemporada,
    Partido,
    ProviderMapping,
    StandingAdjustment,
    StandingProjection,
    StandingRule,
    Temporada,
)


@pytest.fixture
def domain():
    engine = create_engine(os.getenv("TEST_DATABASE_URL", "sqlite://"))
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        competition = Competicion(nombre="Liga", logo="", tipo="liga_nacional", pais="Colombia")
        session.add(competition)
        session.flush()
        teams = [
            Equipo(nombre=name, logo="", tipo="club", pais="Colombia") for name in ("A", "B", "C")
        ]
        session.add_all(teams)
        season = Temporada(competicion_id=competition.id, nombre="2026-I")
        other = Temporada(competicion_id=competition.id, nombre="2026-II")
        session.add_all([season, other])
        session.flush()
        for team in teams[:2]:
            session.add(
                ParticipacionTemporada(equipo_id=team.id, temporada_id=season.id, source="test")
            )
        session.commit()
        yield session, competition, teams, season, other
    engine.dispose()


def make_match(session, comp, teams, season, **values):
    defaults = dict(
        competicion_id=comp.id,
        temporada_id=season.id,
        equipo_local_id=teams[0].id,
        equipo_visitante_id=teams[1].id,
        estado=EstadoPartido.FINALIZADO,
        marcador_local=2,
        marcador_visitante=1,
    )
    match = Partido(**(defaults | values))
    session.add(match)
    session.flush()
    return match


def make_rule(session, season, **values):
    defaults = dict(
        scope_key=scope_key(season.id),
        temporada_id=season.id,
        version=1,
        name="Regla de prueba",
        source_url="https://example.org/regulation",
        verified=True,
        config={},
        actor="reviewer",
    )
    row = StandingRule(**(defaults | values))
    session.add(row)
    session.flush()
    return row


def test_season_mapping_identity_includes_competition_scope(domain):
    session, _, _, season, other = domain
    for scope, target in (("league:1", season.id), ("league:2", other.id)):
        session.add(
            ProviderMapping(
                provider="api-football",
                entity_type="season",
                external_id="2026",
                external_scope=scope,
                local_id=target,
            )
        )
    session.commit()
    assert len(session.exec(select(ProviderMapping)).all()) == 2
    session.add(
        ProviderMapping(
            provider="api-football",
            entity_type="season",
            external_id="2026",
            external_scope="league:1",
            local_id=other.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_sources_are_idempotent_and_corrections_survive(domain):
    session, _, teams, *_ = domain
    team = teams[0]
    timestamp = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    for _ in range(100):
        apply_source_changes(
            session, "team", team, {"nombre": "Correcto"}, source="wikidata", observed_at=timestamp
        )
    session.commit()
    assert len(session.exec(select(AuditChange)).all()) == 1
    version = session.get(EntityRevision, ("team", team.id)).version
    correct_field(
        session,
        "team",
        team,
        "nombre",
        "Corregido",
        actor="reviewer",
        reason="Nombre oficial",
        expected_version=version,
    )
    session.commit()
    for _ in range(5):
        assert (
            apply_source_changes(session, "team", team, {"nombre": "Externo"}, source="wikidata")
            == []
        )
    session.commit()
    assert team.nombre == "Corregido"
    assert len(session.exec(select(DataIssue)).all()) == 1
    assert len(session.exec(select(AuditChange)).all()) == 2
    with pytest.raises(AuditConflict):
        correct_field(
            session,
            "team",
            team,
            "nombre",
            "Otro",
            actor="reviewer2",
            reason="Cambio simultáneo",
            expected_version=version,
        )
    session.rollback()
    version = session.get(EntityRevision, ("team", team.id)).version
    release_field(
        session,
        "team",
        team,
        "nombre",
        actor="reviewer",
        reason="Fuente revisada",
        expected_version=version,
    )
    apply_source_changes(session, "team", team, {"nombre": "Externo"}, source="wikidata")
    session.commit()
    assert team.nombre == "Externo"
    assert session.exec(select(DataIssue)).one().status == "resolved"


def test_old_response_cannot_reverse_a_newer_score(domain):
    session, comp, teams, season, _ = domain
    match = make_match(session, comp, teams, season)
    new = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)
    old = new - datetime.timedelta(hours=1)
    apply_source_changes(
        session, "match", match, {"marcador_local": 3}, source="api-football", observed_at=new
    )
    apply_source_changes(
        session, "match", match, {"marcador_local": 1}, source="api-football", observed_at=old
    )
    session.commit()
    assert match.marcador_local == 3
    # A newer official correction may reduce a score.
    apply_source_changes(
        session,
        "match",
        match,
        {"marcador_local": 2},
        source="api-football",
        observed_at=new + datetime.timedelta(seconds=1),
    )
    assert match.marcador_local == 2


def test_manual_creation_is_protected_and_audit_cannot_be_edited(domain):
    session, _, teams, *_ = domain
    protect_manual_fields(session, "team", teams[0], actor="reviewer", reason="Ficha manual")
    session.commit()
    apply_source_changes(session, "team", teams[0], {"nombre": "Wrong"}, source="wikidata")
    assert teams[0].nombre == "A"
    first = session.exec(select(AuditChange)).first()
    first.reason = "Overwrite history"
    with pytest.raises(AuditConflict):
        session.flush()
    session.rollback()


def test_unknown_cancelled_and_other_season_scores_never_enter_table(domain):
    session, comp, teams, season, other = domain
    make_match(session, comp, teams, season)
    make_match(session, comp, teams, season, marcador_local=None, marcador_visitante=None)
    make_match(session, comp, teams, season, estado=EstadoPartido.CANCELADO, marcador_local=30)
    make_match(session, comp, teams, other, marcador_local=99)
    make_rule(session, season)
    rebuild_season_standings(session, season.id)
    session.commit()
    result = read_standings(session, season.id)
    assert result["status"] == "ready" and result["official"] is None
    rows = result["calculated"].rows
    assert len(rows) == 2 and rows[0]["played"] == 1
    assert rows[0]["goals_for"] == 2
    first_updated = result["calculated"].updated_at
    rebuild_season_standings(session, season.id)
    session.commit()
    assert session.get(StandingProjection, scope_key(season.id)).updated_at == first_updated


def test_phases_and_groups_require_explicit_scope(domain):
    session, comp, teams, season, _ = domain
    phase = Fase(temporada_id=season.id, nombre="Regular")
    session.add(phase)
    session.flush()
    make_match(session, comp, teams, season, fase_id=phase.id)
    make_rule(session, season)
    assert rebuild_season_standings(session, season.id) == []
    assert read_standings(session, season.id)["status"] == "pending"
    assert session.exec(select(DataIssue)).one().reason.startswith("Elige una fase")
    for team in teams[:2]:
        session.add(ParticipacionFase(equipo_id=team.id, fase_id=phase.id))
    make_rule(session, season, scope_key=scope_key(season.id, phase.id), fase_id=phase.id)
    rebuild_season_standings(session, season.id)
    assert read_standings(session, season.id, phase.id)["status"] == "ready"
    group = Grupo(fase_id=phase.id, nombre="A")
    session.add(group)
    session.flush()
    rebuild_season_standings(session, season.id)
    assert read_standings(session, season.id, phase.id)["status"] == "pending"
    for team in teams[:2]:
        session.add(ParticipacionGrupo(equipo_id=team.id, grupo_id=group.id))
    make_match(session, comp, teams, season, fase_id=phase.id, grupo_id=group.id)
    make_rule(
        session,
        season,
        scope_key=scope_key(season.id, phase.id, group.id),
        fase_id=phase.id,
        grupo_id=group.id,
    )
    rebuild_season_standings(session, season.id)
    assert (
        read_standings(session, season.id, phase.id, group.id)["calculated"].rows[0]["played"] == 1
    )


def test_adjustments_rebuild_and_official_table_stays_separate(domain):
    session, comp, teams, season, _ = domain
    make_match(session, comp, teams, season)
    make_rule(session, season)
    session.add(
        StandingAdjustment(
            scope_key=scope_key(season.id),
            equipo_id=teams[0].id,
            points=-3,
            reason="Sanción",
            source_url="https://example.org/ruling",
            actor="reviewer",
        )
    )
    rebuild_season_standings(session, season.id)
    official_rows = [
        dict(
            team_id=team.id,
            rank=index,
            points=3 if index == 1 else 0,
            played=1,
            won=1 if index == 1 else 0,
            drawn=0,
            lost=0 if index == 1 else 1,
            goals_for=2 if index == 1 else 1,
            goals_against=1 if index == 1 else 2,
        )
        for index, team in enumerate(teams[:2], 1)
    ]
    official = store_official_standings(
        session,
        season_id=season.id,
        source="fixture-provider",
        source_url="https://example.org/table",
        rows=official_rows,
    )
    session.commit()
    again = store_official_standings(
        session,
        season_id=season.id,
        source="fixture-provider",
        source_url="https://example.org/table",
        rows=official_rows,
    )
    assert again.id == official.id
    result = read_standings(session, season.id)
    assert result["calculated"].rows[0]["points"] == 0
    assert result["official"]["rows"][0]["points"] == 3
    with pytest.raises(StandingsScopeError):
        store_official_standings(
            session,
            season_id=season.id,
            source="provider",
            source_url="https://example.org/table",
            rows=[{"team_id": teams[2].id}],
        )


def test_rules_reject_unsupported_criteria_and_preserve_unresolved_ties(domain):
    _, _, teams, *_ = domain
    with pytest.raises(ValueError):
        StandingsConfig(tiebreakers=["invented_lottery"])
    rows = calculate_standings(teams[:2], [])
    assert [row.rank for row in rows] == [1, 1]


def test_official_source_corrections_can_return_to_a_previous_value(domain):
    session, _, teams, season, _ = domain
    from copy import deepcopy

    initial = [
        dict(
            team_id=team.id,
            rank=index,
            points=3 if index == 1 else 0,
            played=1,
            won=1 if index == 1 else 0,
            drawn=0,
            lost=0 if index == 1 else 1,
            goals_for=2 if index == 1 else 1,
            goals_against=1 if index == 1 else 2,
        )
        for index, team in enumerate(teams[:2], 1)
    ]
    revised = deepcopy(initial)
    revised[0]["points"] = 0
    ids = []
    for rows in (initial, revised, initial):
        saved = store_official_standings(
            session,
            season_id=season.id,
            source="test",
            source_url="https://example.org/table",
            rows=rows,
        )
        session.commit()
        ids.append(saved.id)
    assert len(set(ids)) == 3
    result = read_standings(session, season.id)
    assert result["official"]["id"] == ids[-1]
    assert result["official"]["rows"][0]["team"]["nombre"] == "A"
    with pytest.raises(StandingsScopeError):
        store_official_standings(
            session,
            season_id=season.id,
            source="test",
            source_url="https://example.org/table",
            rows=initial[:1],
        )


def test_standings_adapter_requires_unambiguous_table_and_canonical_teams(domain):
    from types import SimpleNamespace

    from src.providers.automation import StandingsHandler
    from src.sync.service import PermanentError

    session, comp, teams, season, _ = domain
    session.add(
        ProviderMapping(
            provider="api-football", entity_type="competition", local_id=comp.id, external_id="239"
        )
    )
    for team, external in zip(teams[:2], (100, 200), strict=True):
        session.add(
            ProviderMapping(
                provider="api-football",
                entity_type="team",
                local_id=team.id,
                external_id=str(external),
            )
        )
    session.flush()

    def table(name):
        return [
            {
                "rank": index,
                "points": 0,
                "goalsDiff": 0,
                "team": {"id": external},
                "group": name,
                "all": {
                    "played": 0,
                    "win": 0,
                    "draw": 0,
                    "lose": 0,
                    "goals": {"for": 0, "against": 0},
                },
            }
            for index, external in enumerate((100, 200), 1)
        ]

    payload = {
        "response": [
            {
                "league": {
                    "id": 239,
                    "season": 2026,
                    "standings": [table("Apertura"), table("Clausura")],
                }
            }
        ]
    }
    scope = SimpleNamespace(selector={"league_id": 239, "season": 2026, "season_id": season.id})
    handler = StandingsHandler()
    with pytest.raises(PermanentError, match="varias tablas"):
        handler.apply(session, scope, payload, SimpleNamespace())
    scope.selector["table_name"] = "Apertura"
    assert handler.apply(session, scope, payload, SimpleNamespace())["changed"] == 1
    session.commit()
    assert handler.apply(session, scope, payload, SimpleNamespace())["changed"] == 0
    result = read_standings(session, season.id)
    assert len(result["official"]["rows"]) == 2
    assert result["official"]["rows"][0]["team_id"] == teams[0].id
    payload["response"][0]["league"]["standings"][0][0]["team"]["id"] = 999
    with pytest.raises(PermanentError, match="identidad canónica"):
        handler.apply(session, scope, payload, SimpleNamespace())


def test_concurrent_result_corrections_rebuild_both_changes(domain):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    session, comp, teams, season, _ = domain
    if session.bind.dialect.name != "postgresql":
        pytest.skip("Row-lock concurrency is verified against PostgreSQL")
    first = make_match(session, comp, teams, season)
    second = make_match(session, comp, teams, season)
    make_rule(session, season)
    rebuild_season_standings(session, season.id)
    session.commit()
    season_id, first_id, second_id = season.id, first.id, second.id
    engine = session.bind
    held, second_written = Event(), Event()

    def first_editor():
        with Session(engine) as writer:
            writer.exec(select(Temporada).where(Temporada.id == season_id).with_for_update()).one()
            match = writer.get(Partido, first_id)
            apply_source_changes(writer, "match", match, {"marcador_local": 3}, source="test")
            writer.flush()
            held.set()
            assert second_written.wait(5)
            rebuild_season_standings(writer, season_id)
            writer.commit()

    def second_editor():
        assert held.wait(5)
        with Session(engine) as writer:
            match = writer.get(Partido, second_id)
            apply_source_changes(writer, "match", match, {"marcador_local": 4}, source="test")
            writer.flush()
            second_written.set()
            rebuild_season_standings(writer, season_id)
            writer.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(first_editor), pool.submit(second_editor)]
        for future in futures:
            future.result(timeout=15)
    session.expire_all()
    projection = session.get(StandingProjection, scope_key(season_id))
    assert projection.rows[0]["goals_for"] == 7
    assert projection.rows[0]["played"] == 2
