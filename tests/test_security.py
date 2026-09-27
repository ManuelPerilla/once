from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.security import get_auth_settings, hash_password, verify_password
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def test_login_cookie_and_logout(client):
    assert client.get("/partidos/").status_code == 401
    response = client.post("/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert client.get("/partidos/").status_code == 200
    assert client.post("/logout").status_code == 200
    assert client.get("/partidos/").status_code == 401


@pytest.mark.parametrize(
    "username", [TEST_USERNAME.upper(), f" {TEST_USERNAME} ", f" {TEST_USERNAME.upper()} "]
)
def test_login_normalizes_username_and_keeps_canonical_session(client, username):
    response = client.post("/login", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200
    assert response.json()["username"] == TEST_USERNAME
    session = client.get("/auth/session")
    assert session.status_code == 200
    assert session.json()["username"] == TEST_USERNAME
    assert session.json()["role"] == "admin"


@pytest.mark.parametrize("password", [TEST_PASSWORD.upper(), f" {TEST_PASSWORD} "])
def test_login_never_normalizes_password(client, password):
    response = client.post("/login", json={"username": TEST_USERNAME.upper(), "password": password})
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_login_retains_configured_username_spelling(client, monkeypatch):
    canonical = TEST_USERNAME.upper()
    monkeypatch.setenv("ADMIN_USERNAME", canonical)
    get_auth_settings.cache_clear()
    response = client.post("/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert response.status_code == 200
    assert client.get("/auth/session").json()["username"] == canonical


@pytest.mark.parametrize(
    "username,password", [("desconocido", TEST_PASSWORD), (TEST_USERNAME, "incorrecta")]
)
def test_wrong_credentials_are_rejected(client, username, password):
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert "vertice_token" not in client.cookies


@pytest.mark.parametrize(
    "invalid", ["expired", "no_exp", "no_sub", "other_user", "wrong_key", "legacy_token"]
)
def test_invalid_tokens_are_rejected(client, invalid):
    settings = get_auth_settings()
    payload = {"sub": TEST_USERNAME, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    key = settings.secret_key
    if invalid == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif invalid == "no_exp":
        payload.pop("exp")
    elif invalid == "no_sub":
        payload.pop("sub")
    elif invalid == "other_user":
        payload["sub"] = "otro_usuario"
    elif invalid == "wrong_key":
        key = "otra-clave-que-no-pertenece-a-esta-api-12345"
    token = (
        "vertice_qa_token_2026"
        if invalid == "legacy_token"
        else jwt.encode(payload, key, algorithm="HS256")
    )
    assert client.get("/partidos/", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_valid_bearer_token_is_supported(client):
    token = jwt.encode(
        {"sub": TEST_USERNAME, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        get_auth_settings().secret_key,
        algorithm="HS256",
    )
    assert client.get("/partidos/", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_secure_cookie_defaults_to_true(client, monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE")
    get_auth_settings.cache_clear()
    response = client.post("/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert "Secure" in response.headers["set-cookie"]


@pytest.mark.parametrize("missing", ["SECRET_KEY", "ADMIN_USERNAME", "ADMIN_PASSWORD_HASH"])
def test_missing_auth_configuration_is_rejected(client, monkeypatch, missing):
    monkeypatch.delenv(missing)
    get_auth_settings.cache_clear()
    with pytest.raises(RuntimeError, match="Configura"):
        get_auth_settings()


@pytest.mark.parametrize(
    "name,value",
    [
        ("SECRET_KEY", "clave-corta"),
        ("ADMIN_PASSWORD_HASH", "texto-plano"),
        ("COOKIE_SECURE", "maybe"),
    ],
)
def test_invalid_auth_configuration_is_rejected(client, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    get_auth_settings.cache_clear()
    with pytest.raises(RuntimeError):
        get_auth_settings()


def test_password_hashes_are_salted_and_verify():
    first = hash_password(TEST_PASSWORD)
    second = hash_password(TEST_PASSWORD)
    assert first != second
    assert TEST_PASSWORD not in first
    assert verify_password(TEST_PASSWORD, first)
    assert not verify_password("incorrecta", first)
