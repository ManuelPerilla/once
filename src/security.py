"""Configuración de acceso y hashes de contraseña, sin secretos por defecto."""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache

PASSWORD_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256:{PASSWORD_ITERATIONS}:{salt}:{digest.hex()}"


def _password_hash_parts(encoded: str) -> tuple[bytes, bytes]:
    algorithm, iterations, salt, digest = encoded.split(":")
    if algorithm != "pbkdf2_sha256" or iterations != str(PASSWORD_ITERATIONS):
        raise ValueError("Formato de hash no admitido")
    salt_bytes, digest_bytes = bytes.fromhex(salt), bytes.fromhex(digest)
    if len(salt_bytes) != 16 or len(digest_bytes) != 32:
        raise ValueError("Hash incompleto")
    return salt_bytes, digest_bytes


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt, expected = _password_hash_parts(encoded)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return hmac.compare_digest(actual, expected)


@dataclass(frozen=True)
class AuthSettings:
    secret_key: str
    admin_username: str
    admin_password_hash: str
    cookie_secure: bool


@lru_cache
def get_auth_settings() -> AuthSettings:
    required = ("SECRET_KEY", "ADMIN_USERNAME", "ADMIN_PASSWORD_HASH")
    if any(not os.getenv(name, "").strip() for name in required):
        raise RuntimeError(
            "Configura SECRET_KEY, ADMIN_USERNAME y ADMIN_PASSWORD_HASH. "
            "Puedes generar .env con: python -m src.configure"
        )
    secret_key = os.environ["SECRET_KEY"]
    if len(secret_key.encode("utf-8")) < 32:
        raise RuntimeError("SECRET_KEY debe contener al menos 32 bytes aleatorios.")
    password_hash = os.environ["ADMIN_PASSWORD_HASH"]
    try:
        _password_hash_parts(password_hash)
    except ValueError as exc:
        raise RuntimeError(
            "ADMIN_PASSWORD_HASH no es válido; genera uno con src.configure."
        ) from exc
    cookie_secure = os.getenv("COOKIE_SECURE", "true").lower()
    if cookie_secure not in {"true", "false"}:
        raise RuntimeError("COOKIE_SECURE debe ser true o false.")
    return AuthSettings(
        secret_key=secret_key,
        admin_username=os.environ["ADMIN_USERNAME"].strip(),
        admin_password_hash=password_hash,
        cookie_secure=cookie_secure == "true",
    )
