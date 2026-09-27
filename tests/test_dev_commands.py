"""Development shortcuts must preserve secrets and isolate destructive test targets."""

import json

import pytest

from scripts import dev, prepare_qa


def test_generated_qa_configuration_passes_shortcut_guards(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_qa, "ROOT", tmp_path)
    monkeypatch.setattr(dev, "QA_FILE", tmp_path / ".local" / "compose.qa.json")
    prepare_qa.prepare()
    config = dev.qa_config()
    assert config["name"] == "once-qa"
    assert config["services"]["worker"]["environment"]["POSTGRES_HOST"] == "db"


def test_literal_env_preserves_password_and_process_override(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("# generated\nPOSTGRES_PASSWORD='literal$# = value'\nPOSTGRES_PORT=15432\n")
    monkeypatch.setenv("POSTGRES_PORT", "15433")
    env = dev.local_environment(path)
    assert env["POSTGRES_PASSWORD"] == "literal$# = value"
    assert env["POSTGRES_PORT"] == "15433"


def test_invalid_env_reports_line_without_revealing_value(tmp_path):
    path = tmp_path / ".env"
    path.write_text("SECRET_KEY='do-not-print-this\n")
    with pytest.raises(ValueError, match="línea 1") as failure:
        dev.read_env(path)
    assert "do-not-print-this" not in str(failure.value)


@pytest.mark.parametrize("value", [None, "sqlite://", "postgresql://localhost/once_test"])
def test_isolated_database_names_are_accepted(value):
    dev.check_test_database(value)


def test_development_test_shortcut_rejects_working_database_name():
    with pytest.raises(ValueError, match="desechable"):
        dev.check_test_database("postgresql://localhost/vertice_db")


@pytest.mark.parametrize("value", ["sqlite:///working.db", "sqlite+pysqlite:///working.db"])
def test_development_test_shortcut_rejects_persistent_sqlite(value):
    with pytest.raises(ValueError, match="memoria"):
        dev.check_test_database(value)


@pytest.mark.parametrize("change", ["name", "volume", "port"])
def test_qa_shortcuts_reject_reused_production_identity(tmp_path, monkeypatch, change):
    config = {
        "name": "once-qa",
        "services": {
            "frontend": {"ports": ["127.0.0.1:18080:80"]},
            "db": {"volumes": ["qa_data:/var/lib/postgresql/data"]},
        },
        "volumes": {"qa_data": {}},
    }
    if change == "name":
        config["name"] = "vertice"
    elif change == "volume":
        config["volumes"]["qa_data"] = {"external": True, "name": "vertice_postgres_data"}
    else:
        config["services"]["frontend"]["ports"] = ["127.0.0.1:80:80"]
    path = tmp_path / "qa.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(dev, "QA_FILE", path)
    with pytest.raises(ValueError, match="desechable"):
        dev.qa_config()


def test_api_migrates_before_starting_and_does_not_replace_process_settings(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("POSTGRES_HOST=db\nPOSTGRES_PORT=5432\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "15432")
    calls = []
    monkeypatch.setattr(dev, "python", lambda *args, **kwargs: calls.append((args, kwargs)))
    dev.execute("api", path)
    assert calls[0][0] == ("-m", "src.migrate")
    assert calls[1][0][:3] == ("-m", "uvicorn", "src.main:app")
    assert calls[1][1]["env"]["POSTGRES_PORT"] == "15432"


@pytest.mark.parametrize("change", ["url", "host", "env_file", "network"])
def test_qa_shortcuts_reject_external_database_routing(tmp_path, monkeypatch, change):
    service = {"environment": {"POSTGRES_HOST": "db"}, "volumes": ["qa_media:/app/.media"]}
    config = {
        "name": "once-qa",
        "services": {
            "frontend": {"ports": ["127.0.0.1:18080:80"]},
            "db": {"volumes": ["qa_data:/var/lib/postgresql/data"]},
            "api": service,
            "worker": service,
        },
        "volumes": {"qa_data": {}, "qa_media": {}},
    }
    if change == "url":
        service["environment"]["DATABASE_URL"] = "postgresql://example.invalid/production"
    elif change == "host":
        service["environment"]["POSTGRES_HOST"] = "host.docker.internal"
    elif change == "env_file":
        service["env_file"] = [".env"]
    else:
        service["network_mode"] = "host"
    path = tmp_path / "qa.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(dev, "QA_FILE", path)
    with pytest.raises(ValueError):
        dev.qa_config()
