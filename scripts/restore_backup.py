"""Restore a verified backup into an EMPTY database; existing tables are never dropped."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from scripts.backup import ROOT, compose_args


def restore(path, compose_file=None):
    path = Path(path).resolve(strict=True)
    manifest = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    base = compose_args(compose_file)
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"]:
            raise ValueError("La copia no coincide con su SHA-256. No se restauró nada.")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--compose-file", type=Path)
    args = parser.parse_args()
    restore(args.backup, args.compose_file)
    print("Restauración completada. Ya puedes iniciar la API y el frontend.")
