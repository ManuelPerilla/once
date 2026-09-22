"""Adopta bases legacy y aplica migraciones versionadas antes de arrancar la API."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from src.database import engine


BASELINE_REVISION = "0001_legacy_baseline"


def alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def migrate() -> None:
    config = alembic_config()

    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())

    # Las instalaciones anteriores a Alembic ya tienen el esquema original.
    # Lo adoptamos como baseline sin recrear ni borrar sus tablas.
    if "partido" in tables and "alembic_version" not in tables:
        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")


if __name__ == "__main__":
    migrate()
