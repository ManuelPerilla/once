FROM python:3.12-slim AS app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations/ ./migrations/
COPY src/ ./src/

FROM app AS test
COPY requirements-dev.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ ./tests/
COPY scripts/ ./scripts/
ENV DATABASE_URL=sqlite://
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM app AS runtime
CMD ["sh", "-c", "python -m src.migrate && uvicorn src.main:app --host 0.0.0.0 --port 8000"]
