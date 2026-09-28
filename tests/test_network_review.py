"""Regression checks from the portable-network safety review; no Docker calls."""

import io
import json
from types import SimpleNamespace

import pytest

from scripts import network


def test_effective_remote_context_cannot_hide_behind_local_docker_host(monkeypatch):
    for key in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    monkeypatch.setenv("DOCKER_CONTEXT", "remote-review")
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        if arguments[:3] == ["docker", "context", "inspect"]:
            return '"ssh://remote.example.invalid"'
        return "29.0.0"

    monkeypatch.setattr(network, "run", fake_run)
    with pytest.raises(network.NetworkError):
        network.docker_preflight()
    assert not any(arguments[:2] == ["docker", "info"] for arguments in calls)


def test_network_edit_never_changes_a_line_inside_an_opaque_multiline_secret():
    private_assignment = b"PRIVATE_NOTE='first line\nFRONTEND_BIND=private-content\nlast line'\n"
    original = private_assignment + b"FRONTEND_PORT=80\n"
    try:
        updated = network.edited_env(original, {"FRONTEND_BIND": "0.0.0.0"})
    except network.NetworkError as exc:
        # Rejecting unsupported dotenv syntax is also a safe, documented outcome.
        assert "private-content" not in str(exc)
        return
    assert private_assignment in updated
    assert b"\nFRONTEND_BIND=0.0.0.0\n" in updated


def test_non_object_health_payload_is_unhealthy_instead_of_bypassing_rollback(monkeypatch):
    response = io.BytesIO(b"[]")
    response.status = 200
    opener = SimpleNamespace(open=lambda *args, **kwargs: response)
    monkeypatch.setattr(network.urllib.request, "build_opener", lambda *args: opener)
    assert network.health(8080) is False


@pytest.mark.parametrize("key", ["COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES"])
@pytest.mark.parametrize("prefix", ["", "export "])
def test_dotenv_compose_override_is_rejected_before_docker(tmp_path, monkeypatch, key, prefix):
    original = (
        b"SECRET_KEY='private-value-must-remain-opaque'\nFRONTEND_PORT=8080\n"
        + f"{prefix}{key}='other-installation'\n".encode()
    )
    path = tmp_path / ".env"
    path.write_bytes(original)
    monkeypatch.setattr(network, "ROOT", tmp_path)

    def forbidden_run(*args, **kwargs):
        pytest.fail("A rejected dotenv override reached a subprocess")

    monkeypatch.setattr(network, "run", forbidden_run)
    with pytest.raises(network.NetworkError, match=key) as failure:
        network.execute("lan", no_build=True)
    assert "private-value-must-remain-opaque" not in str(failure.value)
    assert path.read_bytes() == original


def test_status_rejects_another_clone_before_reporting_its_port(tmp_path, monkeypatch, capsys):
    path = tmp_path / ".env"
    original = b"FRONTEND_PORT=8080\nFRONTEND_BIND=0.0.0.0\nCOOKIE_SECURE=false\n"
    path.write_bytes(original)
    monkeypatch.setattr(network, "ROOT", tmp_path)
    monkeypatch.setattr(network, "docker_preflight", lambda: None)
    calls = []

    def compose(*args, **kwargs):
        calls.append(args)
        assert args == ("ps", "--all", "--quiet")
        return "foreign-container"

    def inspect(arguments, **kwargs):
        assert arguments == ["docker", "inspect", "foreign-container"]
        return json.dumps(
            [
                {
                    "Config": {
                        "Labels": {
                            "com.docker.compose.project.working_dir": str(tmp_path / "other-clone")
                        }
                    }
                }
            ]
        )

    monkeypatch.setattr(network, "compose", compose)
    monkeypatch.setattr(network, "run", inspect)
    with pytest.raises(network.NetworkError, match="otra carpeta"):
        network.execute("status")
    assert calls == [("ps", "--all", "--quiet")]
    assert "Puerto publicado" not in capsys.readouterr().out
    assert path.read_bytes() == original
