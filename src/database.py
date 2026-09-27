import os

from sqlalchemy import URL
from sqlmodel import SQLModel, create_engine

# DATABASE_URL permite usar una base aislada en pruebas. En Docker usamos
# componentes separados para admitir contraseñas con caracteres especiales.
URL_BASE_DATOS = os.getenv("DATABASE_URL")
if not URL_BASE_DATOS:
    if not os.getenv("POSTGRES_PASSWORD"):
        raise RuntimeError("Configura DATABASE_URL o POSTGRES_PASSWORD antes de iniciar la API.")
    URL_BASE_DATOS = URL.create(
        "postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER", "postgres"),
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "vertice_db"),
    )

engine = create_engine(URL_BASE_DATOS)


def crear_tablas_db():
    SQLModel.metadata.create_all(engine)
