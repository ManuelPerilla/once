"""Comprueba que una base pre-Alembic adopta el baseline sin perder el esquema."""

from alembic import command
from sqlalchemy import inspect, text

from src.database import engine
from src.migrate import BASELINE_REVISION, alembic_config, migrate


def main() -> None:
    config = alembic_config()

    # Construimos exactamente el esquema legacy mediante su revisión base.
    command.upgrade(config, BASELINE_REVISION)

    # Simulamos una instalación anterior a Alembic: existen las tablas, pero
    # todavía no hay tabla de versionado.
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))

    migrate()

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected_tables = {
        "temporada",
        "fase",
        "estadio",
        "jugador",
        "eventopartido",
        "alineacionpartido",
        "providermapping",
        "mediaasset",
    }
    missing = expected_tables - tables
    if missing:
        raise RuntimeError(f"Faltan tablas después de migrar: {sorted(missing)}")

    match_columns = {column["name"] for column in inspector.get_columns("partido")}
    expected_columns = {"temporada_id", "fase_id", "estadio_id", "fecha", "jornada"}
    missing_columns = expected_columns - match_columns
    if missing_columns:
        raise RuntimeError(
            f"Faltan columnas de partido después de migrar: {sorted(missing_columns)}"
        )

    command.downgrade(config, "base")
    print("Migración legacy -> head verificada.")


if __name__ == "__main__":
    main()
