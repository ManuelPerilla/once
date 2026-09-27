"""Run one bounded worker: python -m src.sync.worker [--health]."""

import argparse
import logging
import os
import signal
import socket
import time
from datetime import timedelta
from uuid import uuid4

from sqlmodel import Session

import src.models  # noqa: F401 - register domain metadata in worker process
from src import database

from .handlers import REGISTRY, register_default_handlers
from .maintenance import cleanup
from .models import SyncHeartbeat
from .service import SyncEngine, now

logger = logging.getLogger("once.sync")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    if args.health:
        try:
            with Session(database.engine) as session:
                beat = session.get(SyncHeartbeat, "worker")
                healthy = beat and beat.last_seen_at > now(session) - timedelta(seconds=180)
            return 0 if healthy else 1
        except Exception:
            return 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    register_default_handlers()
    engine = SyncEngine(database.engine, REGISTRY)
    owner = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
    stopped = False
    next_cleanup = time.monotonic() + 3600

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("Trabajador iniciado; se conserva el modo persistido de automatización.")
    while not stopped:
        try:
            if time.monotonic() >= next_cleanup:
                cleanup(database.engine)
                next_cleanup = time.monotonic() + 3600
            engine.tick(owner)
            if not engine.run_one(owner):
                time.sleep(2)
        except Exception:
            # Deliberately omit untrusted exception strings and provider payloads.
            logger.error("El ciclo no pudo completarse; se recuperará desde la cola persistida.")
            time.sleep(5)
    logger.info("Trabajador detenido; las reservas pendientes se recuperan al reiniciar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
