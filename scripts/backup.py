"""Portable binary PostgreSQL backups; no shell redirection or plaintext credentials."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compose_args(compose_file=None):
    return ["docker", "compose", *(["-f", str(compose_file)] if compose_file else [])]


def backup(directory, compose_file=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"once-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.dump"
    base = compose_args(compose_file)
    with path.open("xb") as stream:
        subprocess.run(
            [*base, "exec", "-T", "db", "pg_dump", "-U", "postgres", "-d", "vertice_db", "-Fc"],
            cwd=ROOT,
            stdout=stream,
            check=True,
        )
    with path.open("rb") as stream:
        subprocess.run(
            [*base, "exec", "-T", "db", "pg_restore", "--list"],
            cwd=ROOT,
            stdin=stream,
            stdout=subprocess.DEVNULL,
            check=True,
        )
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "file": path.name,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "created_at": datetime.now(UTC).isoformat(),
                "format": "postgresql-custom",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / ".local" / "backups")
    parser.add_argument("--compose-file", type=Path)
    args = parser.parse_args()
    print(backup(args.directory, args.compose_file))
