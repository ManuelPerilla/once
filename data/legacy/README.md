# SQL históricos

`init.sql` y `datos_actuales.sql` se conservaron al organizar el proyecto. No se cargan automáticamente y no representan necesariamente la base actual. La fuente del esquema es Alembic; la copia de datos para un traslado debe generarse desde PostgreSQL con `python -m scripts.backup`.
