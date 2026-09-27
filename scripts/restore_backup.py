"""Restore a verified backup into an EMPTY database; existing tables are never dropped."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from scripts.backup import ROOT, compose_args

PAUSE_RESTORED_SQL = """
DO $restore$
BEGIN
    IF to_regclass('public.synccontrol') IS NOT NULL THEN
        UPDATE synccontrol SET mode='paused', epoch=epoch+1, updated_at=now();
        UPDATE syncjob SET status='cancelled', active_key=NULL, owner=NULL,
            lease_until=NULL, token=token+1, finished_at=now(),
            error='La copia fue restaurada; el trabajo debe conciliarse al reanudar.'
            WHERE status IN ('queued', 'waiting', 'running');
        INSERT INTO synchistory(id, actor, action, detail, created_at)
            VALUES (md5(random()::text || clock_timestamp()::text),
                    'service:restore', 'backup_restored_paused',
                    '{"reason":"Restauración verificada; automatización pausada y reservas anteriores invalidadas."}'::json,
                    now());
    END IF;
END
$restore$;
"""


def restore(path, compose_file=None):
    path = Path(path).resolve(strict=True)
    manifest = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    base = compose_args(compose_file)
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"]:
            raise ValueError("La copia no coincide con su SHA-256. No se restauró nada.")
        running = subprocess.check_output(
            [*base, "ps", "--status", "running", "--services"], cwd=ROOT, text=True
        ).splitlines()
        if {"api", "worker"}.intersection(running):
            raise ValueError(
                "Detén la API y el trabajador antes de restaurar; inicia únicamente la base vacía. "
                "No se restauró nada."
            )
        count = subprocess.check_output(
            [
                *base,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "postgres",
                "-d",
                "vertice_db",
                "-Atc",
                "SELECT count(*) FROM pg_tables WHERE schemaname='public'",
            ],
            cwd=ROOT,
            text=True,
        )
        if int(count.strip()):
            raise ValueError(
                "La base ya contiene tablas. Usa una instalación vacía; no se borró nada."
            )
        stream.seek(0)
        subprocess.run(
            [
                *base,
                "exec",
                "-T",
                "db",
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                "vertice_db",
                "--no-owner",
                "--no-privileges",
                "--single-transaction",
                "--exit-on-error",
            ],
            cwd=ROOT,
            stdin=stream,
            check=True,
        )
    # pg_restore recreates append-only triggers after copying their table data.
    # With API and worker stopped, this second transaction cannot race ingestion.
    subprocess.run(
        [
            *base,
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "vertice_db",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            PAUSE_RESTORED_SQL,
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--compose-file", type=Path)
    parser.add_argument("--include-media", action="store_true")
    args = parser.parse_args()
    restore(args.backup, args.compose_file)
    if args.include_media:
        from scripts.media_backup import restore_media

        restore_media(args.backup, args.compose_file)
    print(
        "Restauración completada. La automatización está pausada; revisa fuentes y cuotas antes de reanudarla."
    )
