"""Comprueba adopción legacy y rechazo del downgrade destructivo en una base vacía de pruebas."""

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from src.database import engine
from src.migrate import BASELINE_REVISION, alembic_config, migrate


def main() -> None:
    config = alembic_config()
    memory = engine.dialect.name == "sqlite" and engine.url.database in (None, "", ":memory:")
    if not memory and not (engine.url.database or "").endswith("_test"):
        raise RuntimeError("Usa exclusivamente una base desechable cuyo nombre termine en _test.")
    if inspect(engine).get_table_names():
        raise RuntimeError("La base de pruebas debe estar vacía; no se modificó ninguna tabla.")

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
        "providersnapshot",
        "catalogimportbatch",
        "synccontrol",
        "syncscope",
        "syncjob",
        "syncobservation",
        "auditchange",
        "fieldstate",
        "standingrule",
        "standingprojection",
        "adminaccount",
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

    # Accounts and append-only audit cannot be removed safely by downgrading.
    # Rollback is a verified backup restoration, tested by the transfer procedure.
    try:
        command.downgrade(config, "base")
    except RuntimeError as exc:
        if "Restore a verified backup" not in str(exc):
            raise
    else:
        raise RuntimeError("El downgrade eliminó un esquema que debe conservar su auditoría.")
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != ScriptDirectory.from_config(config).get_current_head():
        raise RuntimeError("El rechazo del downgrade no conservó la revisión actual.")
    print("Adopción legacy -> head y protección contra downgrade verificadas.")


if __name__ == "__main__":
    main()
