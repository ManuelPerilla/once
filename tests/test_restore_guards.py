"""A restore must not write into an active or nonempty installation."""

import hashlib
import json

import pytest

from scripts.restore_backup import restore


def make_backup(tmp_path):
    path = tmp_path / "sample.dump"
    content = b"placeholder: actual PostgreSQL roundtrip is a separate integration check"
    path.write_bytes(content)
    path.with_suffix(".json").write_text(
        json.dumps({"sha256": hashlib.sha256(content).hexdigest()}), encoding="utf-8"
    )
    return path


def test_restore_rejects_corrupt_backup_before_contacting_docker(tmp_path, monkeypatch):
    path = make_backup(tmp_path)
    path.write_bytes(b"corrupted")
    calls = []
    monkeypatch.setattr(
        "scripts.restore_backup.subprocess.check_output", lambda *a, **k: calls.append(a)
    )
    monkeypatch.setattr("scripts.restore_backup.subprocess.run", lambda *a, **k: calls.append(a))
    with pytest.raises(ValueError, match="SHA-256"):
        restore(path)
    assert calls == []


@pytest.mark.parametrize("service", ["api", "worker"])
def test_restore_refuses_a_running_writer(tmp_path, monkeypatch, service):
    path = make_backup(tmp_path)
    writes = []
    monkeypatch.setattr(
        "scripts.restore_backup.subprocess.check_output", lambda *a, **k: f"db\n{service}\n"
    )
    monkeypatch.setattr("scripts.restore_backup.subprocess.run", lambda *a, **k: writes.append(a))
    with pytest.raises(ValueError, match="Detén la API"):
        restore(path)
    assert writes == []


def test_restore_refuses_to_replace_existing_tables(tmp_path, monkeypatch):
    path = make_backup(tmp_path)
    writes = []
    responses = iter(["db\n", "3\n"])
    monkeypatch.setattr(
        "scripts.restore_backup.subprocess.check_output", lambda *a, **k: next(responses)
    )
    monkeypatch.setattr("scripts.restore_backup.subprocess.run", lambda *a, **k: writes.append(a))
    with pytest.raises(ValueError, match="ya contiene tablas"):
        restore(path)
    assert writes == []
