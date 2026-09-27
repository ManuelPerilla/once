"""Genera la configuración local: python -m src.configure (solo Python estándar)."""

import getpass
import os
import re
import secrets
from pathlib import Path

from src.security import hash_password


def main():
    target = Path(__file__).resolve().parents[1] / ".env"
    if target.exists():
        raise SystemExit(".env ya existe. Edítalo para conservar tu configuración actual.")
    username = input("Usuario administrador [admin]: ").strip() or "admin"
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
        raise SystemExit("Usa entre 3 y 64 letras, números, puntos, guiones o guiones bajos.")
    password = getpass.getpass("Nueva contraseña del administrador (mínimo 12 caracteres): ")
    if not 12 <= len(password) <= 1024:
        raise SystemExit("La contraseña debe tener entre 12 y 1024 caracteres.")
    if password != getpass.getpass("Repite la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    print("Si conservas un volumen PostgreSQL, introduce su contraseña actual.")
    database_password = getpass.getpass(
        "Contraseña de PostgreSQL (Enter genera una para una base nueva): "
    )
    database_password = database_password or secrets.token_hex(24)
    if any(char in database_password for char in "\r\n'\\"):
        raise SystemExit(
            "La contraseña de PostgreSQL no puede incluir saltos de línea, comillas simples o barras inversas."
        )
    config = (
        f"SECRET_KEY={secrets.token_hex(32)}\n"
        f"ADMIN_USERNAME={username}\n"
        f"ADMIN_PASSWORD_HASH={hash_password(password)}\n"
        "COOKIE_SECURE=false\n"
        f"POSTGRES_PASSWORD='{database_password}'\n"
        "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n"
        "FRONTEND_PORT=80\n"
    )
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(config)
    print("Configuración guardada en .env. Ejecuta: docker compose up --build -d")


if __name__ == "__main__":
    main()
