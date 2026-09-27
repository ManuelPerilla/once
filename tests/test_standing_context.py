"""Public defaults advertise stored tables without crossing season boundaries."""

from sqlmodel import Session

from src import database
from src.football.projections import scope_key
from src.models import (
    Competicion,
    Fase,
    Grupo,
    OfficialStandingSnapshot,
    StandingProjection,
    StandingRule,
    Temporada,
)


def catalog(session):
    competition = Competicion(nombre="Liga", logo="", tipo="liga_nacional", pais="Colombia")
    session.add(competition)
    session.flush()
    seasons = [
        Temporada(competicion_id=competition.id, nombre=name) for name in ("Apertura", "Clausura")
    ]
    session.add_all(seasons)
    session.flush()
    phases = [
        Fase(temporada_id=season.id, nombre="Cuadrangular", tipo="grupos", orden=1)
        for season in seasons
    ]
    session.add_all(phases)
    session.flush()
    group = Grupo(fase_id=phases[0].id, nombre="Grupo A")
    session.add(group)
    session.flush()
    return seasons, phases, group


def official(key):
    return OfficialStandingSnapshot(
        scope_key=key,
        source="api-football",
        source_url="https://www.api-football.com/",
        content_hash="test",
        rows=[{"team_id": 1}],
    )


def test_context_only_advertises_tables_in_its_season_and_groups(client):
    with Session(database.engine) as session:
        seasons, phases, group = catalog(session)
        first, second = seasons
        valid = scope_key(first.id, phases[0].id, group.id)
        session.add_all(
            [
                official(valid),
                official(valid),
                official(scope_key(second.id, phases[1].id)),
                official(scope_key(first.id, phases[1].id)),
            ]
        )
        session.commit()
        first_id, second_id, phase_id, group_id = first.id, second.id, phases[0].id, group.id
    result = client.get(f"/public/temporadas/{first_id}/context")
    assert result.status_code == 200
    assert result.json()["available_standings"] == [
        {"phase_id": phase_id, "group_id": group_id, "sources": ["official"]}
    ]
    assert (
        len(client.get(f"/public/temporadas/{second_id}/context").json()["available_standings"])
        == 1
    )


def test_context_only_advertises_a_calculation_using_the_latest_verified_rule(client):
    with Session(database.engine) as session:
        seasons, phases, _ = catalog(session)
        key = scope_key(seasons[0].id, phases[0].id)
        rule = StandingRule(
            scope_key=key,
            temporada_id=seasons[0].id,
            fase_id=phases[0].id,
            version=1,
            name="Regla revisada",
            source_url="https://example.org/rule",
            verified=True,
            config={},
            actor="test",
        )
        session.add(rule)
        session.flush()
        session.add(
            StandingProjection(
                scope_key=key, rule_id=rule.id, input_hash="test", rows=[{"team_id": 1}]
            )
        )
        session.commit()
        season_id, phase_id = seasons[0].id, phases[0].id
    path = f"/public/temporadas/{season_id}/context"
    assert client.get(path).json()["available_standings"] == [
        {"phase_id": phase_id, "group_id": None, "sources": ["calculated"]}
    ]
    with Session(database.engine) as session:
        session.add(
            StandingRule(
                scope_key=key,
                temporada_id=season_id,
                fase_id=phase_id,
                version=2,
                name="Pendiente de revisar",
                source_url="https://example.org/rule",
                verified=False,
                config={},
                actor="test",
            )
        )
        session.commit()
    assert client.get(path).json()["available_standings"] == []
