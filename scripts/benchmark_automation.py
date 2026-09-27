"""Reproducible destructive benchmark restricted to a disposable local PostgreSQL DB.

Example (database must already exist; credentials are never printed):
  TEST_DATABASE_URL=postgresql+psycopg2://.../once_sync_test \
  python -m scripts.benchmark_automation --allow-disposable-db

This measures the real ASGI routes plus Docker PostgreSQL. It does not measure
Nginx, browser rendering or Internet freshness. Synthetic worker requests use
the production durable queue, fencing, budget and audited publication path.
"""

import argparse
import datetime as dt
import json
import math
import os
import re
import secrets
import statistics
import subprocess
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("TEST_DATABASE_URL"))
    parser.add_argument(
        "--allow-disposable-db",
        action="store_true",
        help="Acknowledge replacing all data in the verified local test database.",
    )
    parser.add_argument("--sizes", default="10000,100000")
    parser.add_argument("--requests-per-reader", type=int, default=50)
    parser.add_argument("--readers", type=int, default=10)
    parser.add_argument("--docker-container", default="once-sync-qa")
    parser.add_argument("--output", default=".local/benchmarks/automation.json")
    args = parser.parse_args()
    from sqlalchemy.engine import make_url

    if not args.database_url or not args.allow_disposable_db:
        parser.error(
            "Provide TEST_DATABASE_URL and --allow-disposable-db; this benchmark replaces test data."
        )
    try:
        target = make_url(args.database_url)
    except Exception:
        parser.error("Invalid test database URL.")
    if (
        target.get_backend_name() != "postgresql"
        or target.host not in {"localhost", "127.0.0.1"}
        or not re.fullmatch(r"once_[a-z0-9_]+_test", target.database or "")
        or target.port in {None, 5432}
    ):
        parser.error(
            "Only localhost PostgreSQL on a non-default port with DB once_*_test is allowed."
        )
    if not 1 <= args.readers <= 25 or not 10 <= args.requests_per_reader <= 1000:
        parser.error("Use 1–25 readers and 10–1000 requests per reader.")
    try:
        args.sizes = [int(size) for size in args.sizes.split(",")]
        if sorted(set(args.sizes)) != args.sizes or any(
            size < 1000 or size > 100000 for size in args.sizes
        ):
            raise ValueError
    except ValueError:
        parser.error("Sizes must be increasing unique integers from 1000 to 100000.")
    if not re.fullmatch(r"once-[a-z0-9-]*qa", args.docker_container):
        parser.error("Docker metrics can only inspect a named once-…qa container.")
    args.target = {"host": target.host, "port": target.port, "database": target.database}
    return args


def distribution(samples):
    values = sorted(samples)
    if not values:
        return {"count": 0}

    def percentile(fraction):
        return round(values[min(len(values) - 1, math.ceil(len(values) * fraction) - 1)], 2)

    return {
        "count": len(values),
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "max_ms": round(values[-1], 2),
    }


def resources(engine, container):
    from sqlalchemy import text

    with engine.connect() as connection:
        database = dict(
            connection.execute(
                text("""SELECT pg_database_size(current_database()) AS bytes,
            numbackends, xact_commit, xact_rollback, blks_read, blks_hit, deadlocks
            FROM pg_stat_database WHERE datname = current_database()""")
            )
            .mappings()
            .one()
        )
    result = {"postgres": database}
    try:
        output = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", container],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        result["docker_postgres"] = json.loads(output.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        result["docker_postgres"] = {"available": False}
    return result


def seed(engine, size, previous=0):
    from sqlalchemy import text

    started = time.perf_counter()
    with engine.begin() as connection:
        if previous == 0:
            connection.execute(
                text(
                    "INSERT INTO confederacion (id,nombre,logo) VALUES (1,'QA synthetic confederation','')"
                )
            )
            connection.execute(
                text("""INSERT INTO competicion (id,nombre,logo,tipo,pais,confederacion_id)
                SELECT i,'QA competition '||i,'','LIGA_NACIONAL','Colombia',1 FROM generate_series(1,20) i""")
            )
            connection.execute(
                text("""INSERT INTO equipo (id,nombre,logo,tipo,pais,confederacion_id)
                SELECT i,'QA team '||i,'','CLUB','Colombia',1 FROM generate_series(1,400) i""")
            )
            connection.execute(
                text("""INSERT INTO temporada (id,competicion_id,nombre,activa)
                SELECT i,1+((i-1)%20),'QA edition '||i,false FROM generate_series(1,1000) i""")
            )
            connection.execute(
                text("""INSERT INTO fase (id,temporada_id,nombre,tipo,orden)
                SELECT i,i,'Regular','liga',1 FROM generate_series(1,1000) i""")
            )
            connection.execute(
                text("""INSERT INTO participacion (equipo_id,competicion_id)
                SELECT i,1+((i-1)/20) FROM generate_series(1,400) i""")
            )
        connection.execute(
            text("""INSERT INTO partido
            (id,competicion_id,temporada_id,fase_id,equipo_local_id,equipo_visitante_id,
             fecha,jornada,marcador_local,marcador_visitante,estado,estado_fuente)
            SELECT i,1+((i-1)%20),1+((i-1)%1000),1+((i-1)%1000),
                1+((i-1)%20)*20+((i/20)%20),1+((i-1)%20)*20+(((i/20)+1)%20),
                CASE WHEN i%37=0 THEN NULL ELSE timestamptz '2025-01-01 12:00:00+00' + i * interval '5 minutes' END,
                'Round '||(1+((i-1)%38)),i%4,(i+1)%3,
                (CASE WHEN i%25=0 THEN 'VIVO' WHEN i%30=0 THEN 'PROGRAMADO' ELSE 'FINALIZADO' END)::estadopartido,
                'synthetic'
            FROM generate_series(:first,:last) i"""),
            {"first": previous + 1, "last": size},
        )
        connection.execute(
            text("""INSERT INTO eventopartido
            (id,partido_id,source,source_key,tipo,minuto,adicional,detalle)
            SELECT i,1+((i-1)/10),'benchmark',i::text,'gol',1+((i-1)%90),0,'Synthetic load-test event'
            FROM generate_series(:first,:last) i"""),
            {"first": previous * 10 + 1, "last": size * 10},
        )
        connection.execute(text("ANALYZE"))
    return round(time.perf_counter() - started, 2)


def scenario(client, engine, size, args, loaded):
    from sqlalchemy import func
    from sqlmodel import Session, select

    from src.audit.service import apply_source_changes
    from src.models import Partido
    from src.sync.handlers import FetchResult
    from src.sync.models import SyncJob, SyncScope
    from src.sync.service import SyncEngine, enqueue, set_global_mode

    paths = {
        "edition_page": "/public/partidos/page?competition_id=1&season_id=1&page_size=30",
        "competition_page": "/public/partidos/page?competition_id=1&page=2&page_size=30",
        "live_page": "/public/partidos/page?status=live&page_size=30",
        "team_page": "/public/partidos/page?team_id=20&page_size=30",
        "detail": f"/public/partidos/{size // 2}",
    }
    for path in paths.values():
        for _ in range(2):
            response = client.get(path)
            if response.status_code != 200:
                raise RuntimeError(f"Warmup failed for {path}: HTTP {response.status_code}")
    records, lock, stop = [], threading.Lock(), threading.Event()
    writes, audits, errors = [], [], []

    class SyntheticHandler:
        def __init__(self):
            self.sequence = 0

        def fetch(self, scope, context):
            context.reserve_request("benchmark")
            self.sequence += 1
            time.sleep(0.02)  # Simulated network delay explicitly outside the transaction.
            return FetchResult({"iteration": self.sequence})

        def apply(self, session, scope, payload, context):
            changed = 0
            for match_id in range(25, 251, 25):
                match = session.get(Partido, match_id)
                changed += bool(
                    apply_source_changes(
                        session,
                        "match",
                        match,
                        {"marcador_local": payload["iteration"] % 5},
                        source="benchmark",
                        actor=context.actor,
                        run_id=context.job_id,
                        observed_at=context.observed_at,
                    )
                )
            return {"changed": changed, "topics": ["matches"]}

    def worker():
        runner = SyncEngine(engine, {("benchmark", "fixtures"): SyntheticHandler()})
        with runner.transaction() as session:
            set_global_mode(session, "automatic", "benchmark")
            scope = SyncScope(
                name=f"Benchmark {size}",
                provider="benchmark",
                kind="fixtures",
                mode="automatic",
                daily_limit=100000,
                minute_limit=1000,
            )
            session.add(scope)
            session.flush()
            scope_id = scope.id
        while not stop.is_set():
            try:
                with runner.transaction() as session:
                    enqueue(session, session.get(SyncScope, scope_id))
                started = time.perf_counter()
                runner.run_one("benchmark-worker")
                runner.deliver()
                writes.append((time.perf_counter() - started) * 1000)
            except Exception as exc:
                errors.append({"kind": "worker", "error_type": type(exc).__name__})
            stop.wait(0.25)
        with runner.transaction() as session:
            set_global_mode(session, "paused", "benchmark")

    def auditor():
        while not stop.is_set():
            started = time.perf_counter()
            response = client.get("/audit/changes?page_size=20")
            audits.append((time.perf_counter() - started) * 1000)
            if response.status_code != 200:
                errors.append({"kind": "auditor", "status": response.status_code})
            stop.wait(0.2)

    def reader(index):
        selections = list(paths.items())
        for iteration in range(args.requests_per_reader):
            name, path = selections[(index + iteration) % len(selections)]
            started = time.perf_counter()
            response = client.get(path)
            elapsed = (time.perf_counter() - started) * 1000
            with lock:
                records.append((name, elapsed, len(response.content), response.status_code))

    extras = []
    if loaded:
        extras = [
            threading.Thread(target=worker, daemon=True),
            threading.Thread(target=auditor, daemon=True),
        ]
        for thread in extras:
            thread.start()
    started = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=args.readers) as pool:
            list(pool.map(reader, range(args.readers)))
    finally:
        stop.set()
        for thread in extras:
            thread.join(timeout=30)
            if thread.is_alive():
                raise RuntimeError("Background benchmark task did not stop.")
    elapsed = time.perf_counter() - started
    grouped = defaultdict(list)
    for name, latency, count, status in records:
        grouped[name].append((latency, count))
        if status != 200:
            errors.append({"kind": name, "status": status})
    outcomes = {}
    if loaded:
        with Session(engine) as session:
            outcomes = dict(
                session.exec(
                    select(SyncJob.status, func.count())
                    .join(SyncScope, SyncScope.id == SyncJob.scope_id)
                    .where(SyncScope.name == f"Benchmark {size}")
                    .group_by(SyncJob.status)
                ).all()
            )
        if set(outcomes) - {"succeeded"} or outcomes.get("succeeded", 0) != len(writes):
            errors.append({"kind": "worker_outcomes", "states": outcomes})
    result = {
        "loaded": loaded,
        "duration_seconds": round(elapsed, 2),
        "requests_per_second": round(len(records) / elapsed, 2),
        "routes": {
            name: {
                **distribution([value[0] for value in samples]),
                "average_bytes": round(statistics.mean(value[1] for value in samples)),
            }
            for name, samples in grouped.items()
        },
        "auditor": distribution(audits),
        "worker_cycles": distribution(writes),
        "worker_outcomes": outcomes,
        "errors": errors,
    }
    return result


def main():
    args = arguments()
    os.environ["DATABASE_URL"] = args.database_url
    os.environ["SECRET_KEY"] = secrets.token_hex(32)
    os.environ["ADMIN_USERNAME"] = "benchmark-admin"
    os.environ["COOKIE_SECURE"] = "false"
    from src.security import hash_password

    password = secrets.token_urlsafe(24)
    os.environ["ADMIN_PASSWORD_HASH"] = hash_password(password)
    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel

    from src import database
    from src import main as application

    # Scope was checked before imports could create a connection.
    SQLModel.metadata.drop_all(database.engine)
    SQLModel.metadata.create_all(database.engine)
    report = {
        "created_at": dt.datetime.now(dt.UTC).isoformat(),
        "target": args.target,
        "transport": "ASGI TestClient on host; PostgreSQL in Docker; no Nginx/browser",
        "readers": args.readers,
        "auditors_when_loaded": 1,
        "worker": "one real SyncEngine worker, simulated 20 ms fetch, ten audited changes per cycle, 250 ms gap",
        "dataset": "20 competitions, 400 teams, 1000 editions, ten synthetic events per match; not sports facts",
        "sizes": [],
        "limitations": [
            "In-process HTTP timing includes TestClient/thread scheduling.",
            "No Internet calls, source freshness, SSE delivery or browser rendering measured.",
            "Short test duration does not establish sustained-production capacity.",
        ],
    }
    previous = 0
    for size in args.sizes:
        print(f"Preparing {size:,} matches / {size * 10:,} events…", flush=True)
        seeded = seed(database.engine, size, previous)
        previous = size
        with TestClient(application.create_app()) as client:
            login = client.post(
                "/login", json={"username": "benchmark-admin", "password": password}
            )
            if login.status_code != 200:
                raise RuntimeError("Benchmark authentication failed.")
            entry = {
                "matches": size,
                "events": size * 10,
                "seed_seconds": seeded,
                "resources_before": resources(database.engine, args.docker_container),
                "baseline": scenario(client, database.engine, size, args, False),
                "ingesting": scenario(client, database.engine, size, args, True),
                "resources_after": resources(database.engine, args.docker_container),
            }
        report["sizes"].append(entry)
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(
            f"Recorded {size:,} matches. Errors: {len(entry['baseline']['errors']) + len(entry['ingesting']['errors'])}.",
            flush=True,
        )
    print(f"Report: {Path(args.output).resolve()}")
    return (
        0
        if all(
            not stage[key]["errors"]
            for stage in report["sizes"]
            for key in ("baseline", "ingesting")
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
