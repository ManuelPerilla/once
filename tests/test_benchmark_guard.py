"""The destructive load generator must refuse ordinary application databases."""

import pytest

from scripts.benchmark_automation import arguments


@pytest.mark.parametrize(
    "url,flag",
    [
        ("postgresql://user:secret@localhost:5432/once_sync_test", True),
        ("postgresql://user:secret@localhost:15434/vertice_db", True),
        ("postgresql://user:secret@remote.example:15434/once_sync_test", True),
        ("postgresql://user:secret@localhost:15434/once_sync_test", False),
    ],
)
def test_benchmark_refuses_unsafe_targets(monkeypatch, url, flag):
    argv = ["benchmark", "--database-url", url]
    if flag:
        argv.append("--allow-disposable-db")
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(SystemExit) as result:
        arguments()
    assert result.value.code == 2


def test_benchmark_reports_target_without_password(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark",
            "--database-url",
            "postgresql://user:secret@localhost:15434/once_sync_test",
            "--allow-disposable-db",
        ],
    )
    config = arguments()
    assert "secret" not in str(config.target)
    assert config.target["database"] == "once_sync_test"
