"""Cada prueba usa tablas aisladas; nunca se conecta a DATABASE_URL de la app."""

import os
import secrets

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from src import database, main
from src.security import get_auth_settings, hash_password

TEST_USERNAME = "operador_test"
TEST_PASSWORD = "solo-para-pruebas-vertice"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_auth_settings.cache_clear()
    yield
    get_auth_settings.cache_clear()


@pytest.fixture
def client(monkeypatch):
    test_url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    options = {}
    if test_url.startswith("sqlite"):
        options = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    test_engine = create_engine(test_url, **options)
    if test_url.startswith("sqlite"):

        @event.listens_for(test_engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setenv("SECRET_KEY", secrets.token_hex(32))
    monkeypatch.setenv("ADMIN_USERNAME", TEST_USERNAME)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", TEST_PASSWORD_HASH)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setattr(database, "engine", test_engine)
    get_auth_settings.cache_clear()
    # TEST_DATABASE_URL debe apuntar a una base desechable, como la del CI.
    SQLModel.metadata.drop_all(test_engine)
    try:
        with TestClient(main.create_app()) as test_client:
            yield test_client
    finally:
        SQLModel.metadata.drop_all(test_engine)
        test_engine.dispose()


@pytest.fixture
def authenticated(client):
    response = client.post("/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert response.status_code == 200
    return client


@pytest.fixture
def catalog(authenticated):
    def create(path, payload):
        response = authenticated.post(path, json=payload)
        assert response.status_code == 200, response.text
        return response.json()

    conf = create(
        "/confederaciones/",
        {"nombre": "Confederación de prueba", "logo": "https://example.com/logo.svg"},
    )
    comp = create(
        "/competiciones/",
        {
            "nombre": "Liga de prueba",
            "logo": "https://example.com/logo.svg",
            "tipo": "liga_nacional",
            "pais": "Colombia",
            "confederacion_id": conf["id"],
        },
    )
    teams = []
    for nombre, tipo, pais in [
        ("Local", "club", "Colombia"),
        ("Visitante", "club", "Colombia"),
        ("Sin matrícula", "club", "Colombia"),
        ("Selección", "seleccion", "Colombia"),
        ("Extranjero", "club", "España"),
    ]:
        teams.append(
            create(
                "/equipos/",
                {
                    "nombre": nombre,
                    "logo": "https://example.com/logo.svg",
                    "tipo": tipo,
                    "pais": pais,
                    "confederacion_id": conf["id"],
                },
            )
        )
    for team in teams[:2]:
        response = authenticated.post(f"/equipos/{team['id']}/matricular/{comp['id']}")
        assert response.status_code == 200 and response.json()["ok"]
    return {"conf": conf, "comp": comp, "teams": teams}


@pytest.fixture
def match_payload(catalog):
    return {
        "competicion_id": catalog["comp"]["id"],
        "equipo_local_id": catalog["teams"][0]["id"],
        "equipo_visitante_id": catalog["teams"][1]["id"],
        "marcador_local": 0,
        "marcador_visitante": 0,
        "estado": "programado",
    }
