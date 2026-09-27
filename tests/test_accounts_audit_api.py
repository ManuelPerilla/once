"""Permission enforcement, named audit actors and protected corrections over HTTP."""

import pytest
from sqlmodel import Session, select

from src import database
from src.audit.service import apply_source_changes
from src.models import AuditChange, Equipo

PASSWORD = "named-account-test-password"


def account(client, role):
    response = client.post(
        "/accounts",
        json={
            "username": f"person_{role}",
            "display_name": role,
            "role": role,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    assert "password_hash" not in response.json()
    return response.json()


def login(client, username, password=PASSWORD):
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response


def test_auditor_reads_without_mutating_sources_or_accounts(authenticated, catalog):
    user = account(authenticated, "auditor")
    login(authenticated, user["username"])
    session = authenticated.get("/auth/session").json()
    assert session["role"] == "auditor" and session["permissions"] == ["read"]
    assert authenticated.get("/audit/changes").status_code == 200
    assert authenticated.get("/accounts").status_code == 403
    assert authenticated.put("/automation/global", json={"mode": "automatic"}).status_code == 403
    assert authenticated.get("/providers/api-football/preview/league/239").status_code == 403
    team = catalog["teams"][0]
    assert (
        authenticated.patch(
            f"/audit/entities/team/{team['id']}/nombre",
            json={"value": "Unwanted", "reason": "Cannot write", "expected_version": 0},
        ).status_code
        == 403
    )


def test_editor_correction_has_named_actor_and_survives_import(authenticated, catalog):
    user = account(authenticated, "editor")
    login(authenticated, user["username"])
    team_id = catalog["teams"][0]["id"]
    detail = authenticated.get(f"/audit/entities/team/{team_id}").json()
    response = authenticated.patch(
        f"/audit/entities/team/{team_id}/nombre",
        json={
            "value": "Nombre corregido",
            "reason": "Ficha oficial revisada",
            "expected_version": detail["version"],
        },
    )
    assert response.status_code == 200, response.text
    assert authenticated.put("/automation/global", json={"mode": "paused"}).status_code == 403
    with Session(database.engine) as session:
        team = session.get(Equipo, team_id)
        apply_source_changes(session, "team", team, {"nombre": "External"}, source="wikidata")
        session.commit()
        assert team.nombre == "Nombre corregido"
        changes = session.exec(
            select(AuditChange).where(AuditChange.actor == user["username"])
        ).all()
        assert len(changes) == 1 and changes[0].action == "correction"
    stale = authenticated.patch(
        f"/audit/entities/team/{team_id}/nombre",
        json={
            "value": "Old edit",
            "reason": "Concurrent edit",
            "expected_version": detail["version"],
        },
    )
    assert stale.status_code == 409
    issues = authenticated.get("/audit/issues").json()["items"]
    assert len(issues) == 1
    resolved = authenticated.post(
        f"/audit/issues/{issues[0]['id']}/resolve", json={"reason": "Se mantiene la corrección"}
    )
    assert resolved.status_code == 200
    assert authenticated.get("/audit/issues").json()["items"] == []


def test_operator_can_pause_but_cannot_create_sources(authenticated):
    user = account(authenticated, "operator")
    login(authenticated, user["username"])
    assert authenticated.put("/automation/global", json={"mode": "paused"}).status_code == 200
    assert (
        authenticated.post(
            "/automation/scopes",
            json={
                "name": "Forbidden",
                "provider": "wikidata",
                "kind": "catalog",
                "selector": {"collection": "confederations"},
            },
        ).status_code
        == 403
    )
    assert (
        authenticated.post(
            "/accounts", json={"username": "another", "display_name": "No", "password": PASSWORD}
        ).status_code
        == 403
    )


def test_disabling_account_revokes_existing_cookie(authenticated):
    user = account(authenticated, "editor")
    login(authenticated, user["username"])
    old_token = authenticated.cookies.get("vertice_token")
    login(authenticated, "operador_test", "solo-para-pruebas-vertice")
    update = authenticated.patch(
        f"/accounts/{user['id']}", json={"active": False, "reason": "Cuenta retirada del equipo"}
    )
    assert update.status_code == 200
    authenticated.cookies.clear()
    assert (
        authenticated.get(
            "/auth/session", headers={"Authorization": f"Bearer {old_token}"}
        ).status_code
        == 401
    )
    assert (
        authenticated.post(
            "/login", json={"username": user["username"], "password": PASSWORD}
        ).status_code
        == 401
    )
    with Session(database.engine) as session:
        audit_text = str([row.model_dump() for row in session.exec(select(AuditChange)).all()])
        assert PASSWORD not in audit_text and "pbkdf2_sha256:" not in audit_text


def test_account_names_reserve_bootstrap_and_canonicalize_duplicates(authenticated):
    response = authenticated.post(
        "/accounts",
        json={"username": "OPERADOR_TEST", "display_name": "Reserved", "password": PASSWORD},
    )
    assert response.status_code == 409
    account(authenticated, "auditor")
    response = authenticated.post(
        "/accounts",
        json={"username": "PERSON_AUDITOR", "display_name": "Duplicate", "password": PASSWORD},
    )
    assert response.status_code == 409


def test_season_participants_and_verified_rule_http(authenticated, catalog):
    response = authenticated.post(
        "/temporadas/", json={"competicion_id": catalog["comp"]["id"], "nombre": "2026-I"}
    )
    assert response.status_code == 200, response.text
    season_id = response.json()["id"]
    initial = authenticated.get(f"/public/temporadas/{season_id}/clasificacion").json()
    assert initial["status"] == "missing_rules" and initial["calculated"] is None
    for team in catalog["teams"][:2]:
        response = authenticated.post(
            f"/football/temporadas/{season_id}/participantes",
            json={"equipo_id": team["id"], "reason": "Inscripción confirmada"},
        )
        assert response.status_code == 200, response.text
    response = authenticated.post(
        "/football/reglas",
        json={
            "temporada_id": season_id,
            "name": "Reglamento de ejemplo validado",
            "source_url": "https://example.org/regulation",
            "verified": True,
            "config": {"points_win": 3, "points_draw": 1, "points_loss": 0},
        },
    )
    assert response.status_code == 200, response.text
    result = authenticated.get(f"/public/temporadas/{season_id}/clasificacion").json()
    assert result["status"] == "ready" and len(result["calculated"]["rows"]) == 2
    assert result["official"] is None
    context = authenticated.get(f"/public/temporadas/{season_id}/context").json()
    assert context == {
        "phases": [],
        "groups": [],
        "available_standings": [{"phase_id": None, "group_id": None, "sources": ["calculated"]}],
    }


@pytest.mark.parametrize("value", [-1, "not-a-number"])
def test_correction_rejects_invalid_score(authenticated, match_payload, value):
    match = authenticated.post("/partidos/", json=match_payload).json()
    current = authenticated.get(f"/audit/entities/match/{match['id']}").json()
    response = authenticated.patch(
        f"/audit/entities/match/{match['id']}/marcador_local",
        json={"value": value, "reason": "Invalid score", "expected_version": current["version"]},
    )
    assert response.status_code == 422
    assert authenticated.get(f"/partidos/{match['id']}").json()["marcador_local"] == 0


def test_legacy_standings_never_mix_edition_matches(authenticated, catalog, match_payload):
    from src.models import Partido, Temporada

    authenticated.post(
        "/partidos/",
        json={
            **match_payload,
            "estado": "finalizado",
            "marcador_local": 1,
            "marcador_visitante": 0,
        },
    )
    with Session(database.engine) as session:
        season = Temporada(competicion_id=catalog["comp"]["id"], nombre="2026-I")
        session.add(season)
        session.flush()
        season_id = season.id
        session.add(
            Partido(
                **{
                    **match_payload,
                    "temporada_id": season_id,
                    "estado": "finalizado",
                    "marcador_local": 99,
                }
            )
        )
        session.commit()
    legacy = authenticated.get(f"/public/competiciones/{catalog['comp']['id']}/standings").json()
    assert legacy[0]["goals_for"] == 1 and legacy[0]["played"] == 1
    unverified = authenticated.get(
        f"/public/competiciones/{catalog['comp']['id']}/standings", params={"season_id": season_id}
    ).json()
    assert unverified == []


def test_field_correction_preserves_competition_compatibility(authenticated, catalog):
    team_id = catalog["teams"][0]["id"]
    current = authenticated.get(f"/audit/entities/team/{team_id}").json()
    response = authenticated.patch(
        f"/audit/entities/team/{team_id}/pais",
        json={
            "value": "España",
            "reason": "Corrección incompatible",
            "expected_version": current["version"],
        },
    )
    assert response.status_code == 422
    assert (
        authenticated.get(f"/audit/entities/team/{team_id}").json()["version"] == current["version"]
    )
