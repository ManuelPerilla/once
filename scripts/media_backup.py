"""Portable media volume copies, restored without starting synchronization."""

import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

from scripts.backup import ROOT, compose_args


def backup_media(database_backup, compose_file=None):
    destination = Path(database_backup).with_suffix(".media.tar")
    with destination.open("xb") as stream:
        subprocess.run(
            [
                *compose_args(compose_file),
                "exec",
                "-T",
                "api",
                "tar",
                "-C",
                "/app/.media",
                "--exclude=*.tmp",
                "-cf",
                "-",
                ".",
            ],
            cwd=ROOT,
            stdout=stream,
            check=True,
        )
    with tarfile.open(destination) as archive:
        for item in archive.getmembers():
            if not (item.isfile() or item.isdir()):
                raise ValueError("La copia contiene un tipo de archivo no permitido.")
    with destination.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"file": destination.name, "sha256": digest, "bytes": destination.stat().st_size}


RESTORE = r"""
import hashlib,io,os,re,sys,tarfile
from pathlib import Path
folder=Path(os.environ.get('ONCE_MEDIA_DIR','/app/.media')).resolve()
folder.mkdir(parents=True,exist_ok=True)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
    for item in archive:
        if item.isdir() and item.name in ('.','./'):
            continue
        name=item.name.removeprefix('./')
        if not item.isfile() or not re.fullmatch(r'[a-f0-9]{64}\.(png|jpg|gif|webp|svg|json)',name) or item.size>5*1024*1024:
            raise ValueError('Entrada de medios no permitida')
        data=archive.extractfile(item).read()
        target=folder/name
        if target.exists():
            if target.read_bytes()!=data:
                raise ValueError('El destino contiene otro archivo con ese nombre')
        else:
            target.write_bytes(data)
print('Medios restaurados; trabajador no iniciado.')
"""


def restore_media(database_backup, compose_file=None):
    backup = Path(database_backup).resolve(strict=True)
    manifest = json.loads(backup.with_suffix(".json").read_text(encoding="utf-8"))
    media = manifest.get("media")
    if not media:
        return False
    path = backup.parent / media["file"]
    if path.parent.resolve() != backup.parent or not path.is_file():
        raise ValueError("No se encontró el archivo de medios junto a la copia.")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != media["sha256"]:
            raise ValueError("La copia de medios no coincide con su SHA-256.")
        stream.seek(0)
        subprocess.run(
            [
                *compose_args(compose_file),
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "--entrypoint",
                "python",
                "worker",
                "-c",
                RESTORE,
            ],
            cwd=ROOT,
            stdin=stream,
            check=True,
        )
    return True
