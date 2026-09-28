"""Network mode changes must preserve credentials, target the right clone and recover."""

import json
import os

import pytest

from scripts import dev, network


@pytest.fixture
def installation(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_bytes(
        b"# private\r\nAPI_FOOTBALL_KEY='keep$# secret'\r\nFRONTEND_PORT=8080\r\nCOOKIE_SECURE=true\r\n"
    )
    monkeypatch.setattr(network, "ROOT", tmp_path)
    monkeypatch.setattr(network, "docker_preflight", lambda: None)
    monkeypatch.setattr(network, "existing_services", lambda env: True)
    monkeypatch.setattr(network, "health", lambda port: True)
    monkeypatch.setattr(network, "discover_addresses", lambda: ["192.168.4.20"])
    for key in (*network.MANAGED, "VITE_API_URL"):
        monkeypatch.delenv(key, raising=False)
    calls = []
    monkeypatch.setattr(
        network, "compose", lambda *args, **kwargs: calls.append((args, kwargs)) or ""
    )
    return path, calls


def test_editor_preserves_secret_bytes_bom_comments_and_crlf():
    before = b"\xef\xbb\xbf# keep\r\nSECRET_KEY='literal$# = value'\r\nFRONTEND_PORT='80' # web\r\n"
    after = network.edited_env(before, {"FRONTEND_PORT": "8080", "FRONTEND_BIND": "0.0.0.0"})
    assert (
        after
        == before.replace(b"FRONTEND_PORT='80'", b"FRONTEND_PORT=8080")
        + b"FRONTEND_BIND=0.0.0.0\r\n"
    )


def test_ambiguous_duplicate_setting_is_rejected():
    with pytest.raises(network.NetworkError, match="duplicada"):
        network.edited_env(b"FRONTEND_PORT=80\nFRONTEND_PORT=8080\n", {"FRONTEND_PORT": "80"})


@pytest.mark.parametrize("port", [0, -1, 65536, "not-a-port"])
def test_invalid_port_does_not_mutate_installation(installation, port):
    path, calls = installation
    before = path.read_bytes()
    with pytest.raises(network.NetworkError, match="puerto"):
        network.execute("lan", port=port)
    assert path.read_bytes() == before and not calls


def test_lan_is_idempotent_and_existing_worker_is_not_restarted(installation):
    path, calls = installation
    assert network.execute("lan", no_build=True) == 0
    after = path.read_bytes()
    assert b"API_FOOTBALL_KEY='keep$# secret'\r\n" in after
    assert network.network_values(after) == {
        "FRONTEND_BIND": "0.0.0.0",
        "FRONTEND_PORT": "8080",
        "COOKIE_SECURE": "false",
    }
    assert network.execute("lan", no_build=True) == 0
    assert path.read_bytes() == after
    up = [args for args, _ in calls if args[0] == "up"]
    assert len(up) == 2 and all(args[-2:] == ("api", "frontend") for args in up)


def test_first_install_starts_all_compose_services(installation, monkeypatch):
    _, calls = installation
    monkeypatch.setattr(network, "existing_services", lambda env: False)
    assert network.execute("lan", no_build=True) == 0
    up = [args for args, _ in calls if args[0] == "up"]
    assert up == [("up", "--no-build", "-d", "--wait", "--wait-timeout", "120")]


def test_local_restores_loopback_without_replacing_credentials(installation):
    path, _ = installation
    network.execute("lan", no_build=True)
    network.execute("local", no_build=True)
    assert network.network_values(path.read_bytes())["FRONTEND_BIND"] == "127.0.0.1"
    assert b"API_FOOTBALL_KEY='keep$# secret'\r\n" in path.read_bytes()


@pytest.mark.parametrize(
    "key,value",
    [
        ("FRONTEND_BIND", "127.0.0.1"),
        ("COOKIE_SECURE", "true"),
        ("VITE_API_URL", "http://localhost:8000"),
    ],
)
def test_process_conflicts_are_rejected_before_mutation(installation, monkeypatch, key, value):
    path, calls = installation
    original = path.read_bytes()
    monkeypatch.setenv(key, value)
    with pytest.raises(network.NetworkError, match=key):
        network.execute("lan")
    assert path.read_bytes() == original and not calls


def test_preview_does_not_call_docker_or_modify_env(installation):
    path, calls = installation
    before = path.read_bytes()
    assert network.execute("lan", port=18080, dry_run=True) == 0
    assert path.read_bytes() == before and not calls


def test_failed_build_leaves_configuration_untouched(installation, monkeypatch):
    path, _ = installation
    before = path.read_bytes()

    def compose(*args, **kwargs):
        if args[0] == "build":
            raise network.NetworkError("build failed")

    monkeypatch.setattr(network, "compose", compose)
    with pytest.raises(network.NetworkError, match="build failed"):
        network.execute("lan")
    assert path.read_bytes() == before


def test_failed_start_restores_exact_file_and_reapplies_previous_mode(installation, monkeypatch):
    path, _ = installation
    before, starts = path.read_bytes(), []

    def compose(*args, **kwargs):
        if args[0] == "up":
            starts.append(kwargs["env"])
            if len(starts) == 1:
                raise network.NetworkError("port busy")

    monkeypatch.setattr(network, "compose", compose)
    with pytest.raises(network.NetworkError, match="anterior vuelve a responder"):
        network.execute("lan", port=18080, no_build=True)
    assert path.read_bytes() == before
    assert starts[1]["FRONTEND_PORT"] == "8080"
    assert starts[1]["FRONTEND_BIND"] == "127.0.0.1"
    assert starts[1]["COOKIE_SECURE"] == "true"


def test_concurrent_env_edit_is_not_overwritten_during_recovery(installation, monkeypatch):
    path, _ = installation
    changed = []

    def compose(*args, **kwargs):
        if args[0] == "up":
            path.write_bytes(path.read_bytes() + b"# concurrent edit\r\n")
            changed.append(path.read_bytes())
            raise network.NetworkError("start failed")

    monkeypatch.setattr(network, "compose", compose)
    with pytest.raises(network.NetworkError, match="no se sobrescribió"):
        network.execute("lan", no_build=True)
    assert path.read_bytes() == changed[0]


def test_firewall_permission_failure_precedes_all_changes(installation, monkeypatch):
    path, calls = installation
    before = path.read_bytes()

    def denied():
        raise network.NetworkError("administrator required")

    monkeypatch.setattr(network, "firewall_preflight", denied)
    with pytest.raises(network.NetworkError, match="administrator"):
        network.execute("lan", with_firewall=True)
    assert path.read_bytes() == before and not calls


def test_firewall_port_change_removes_only_previous_managed_rule(installation, monkeypatch):
    mutations = []
    monkeypatch.setattr(network, "firewall_preflight", lambda: None)
    monkeypatch.setattr(network, "firewall", lambda action, port: mutations.append((action, port)))
    assert network.execute("lan", port=8081, with_firewall=True, no_build=True) == 0
    assert mutations == [("Enable", 8081), ("Disable", 8080)]


def test_status_reports_drift_without_claiming_current_url(installation, monkeypatch, capsys):
    path, _ = installation
    before = path.read_bytes()
    monkeypatch.setattr(network, "compose", lambda *args, **kwargs: "0.0.0.0:9090")
    assert network.execute("status") == 1
    assert "no coincide" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_other_clone_container_identity_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(network, "ROOT", tmp_path / "new-clone")
    monkeypatch.setattr(network, "compose", lambda *args, **kwargs: "container-id")
    containers = [
        {
            "Config": {
                "Labels": {"com.docker.compose.project.working_dir": str(tmp_path / "original")}
            }
        }
    ]
    monkeypatch.setattr(network, "run", lambda *args, **kwargs: json.dumps(containers))
    with pytest.raises(network.NetworkError, match="otra carpeta"):
        network.existing_services({})


def test_remote_docker_context_is_rejected(monkeypatch):
    for key in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES", "DOCKER_HOST"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(network, "run", lambda *args, **kwargs: '"ssh://server.example"')
    with pytest.raises(network.NetworkError, match="local"):
        network.docker_preflight()


def test_second_network_operation_cannot_take_existing_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(network, "ROOT", tmp_path)
    with network.operation_lock():
        with pytest.raises(network.NetworkError, match="en curso"):
            with network.operation_lock():
                pytest.fail("Second writer acquired the lock")


def test_atomic_edit_and_stale_write_guard(tmp_path):
    path = tmp_path / ".env"
    path.write_bytes(b"unchanged-secret\nFRONTEND_PORT=80\n")
    os.chmod(path, 0o600)
    before = path.read_bytes()
    after = before.replace(b"=80", b"=8080")
    network.replace_env(path, before, after)
    assert path.read_bytes() == after
    with pytest.raises(network.NetworkError, match="no se sobrescribió"):
        network.replace_env(path, before, b"stale")
    assert path.read_bytes() == after


@pytest.mark.parametrize(
    "task,mode", [("lan", "lan"), ("local", "local"), ("network-status", "status")]
)
def test_dev_shortcuts_forward_network_options(monkeypatch, task, mode):
    calls = []
    monkeypatch.setattr(dev, "python", lambda *args: calls.append(args))
    dev.execute(task, dev.ROOT / ".env", ("--dry-run",))
    assert calls == [("-m", "scripts.network", mode, "--dry-run")]
