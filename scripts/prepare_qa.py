"""Generate an isolated Compose stack for browser tests; never uses the working database."""

import json
import secrets
from pathlib import Path

from src.security import hash_password

ROOT = Path(__file__).resolve().parents[1]


def add_worker(config):
    services = config["services"]
    api = services["api"]
    api.setdefault("environment", {})["ONCE_MEDIA_DIR"] = "/app/.media"
    api["volumes"] = ["qa_media:/app/.media"]
    api["healthcheck"]["test"][-1] = (
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
    )
    config.setdefault("volumes", {})["qa_media"] = {}
    services["worker"] = {
        "image": api["image"],
        "command": ["python", "-m", "src.sync.worker"],
        "environment": {**api["environment"], "DB_POOL_SIZE": "2", "DB_MAX_OVERFLOW": "1"},
        "volumes": ["qa_media:/app/.media"],
        "depends_on": {"api": {"condition": "service_healthy"}},
        "healthcheck": {
            "test": ["CMD", "python", "-m", "src.sync.worker", "--health"],
            "interval": "5s",
            "timeout": "5s",
            "start_period": "10s",
            "retries": 10,
        },
    }
    return config


def prepare():
    target = ROOT / ".local" / "compose.qa.json"
    if target.exists():
        config = json.loads(target.read_text(encoding="utf-8"))
        target.write_text(json.dumps(add_worker(config), indent=2), encoding="utf-8")
        print(f"Configuración QA actualizada; identidad y secretos conservados: {target}")
        return
    password = secrets.token_hex(24)
    config = {
        "name": "once-qa",
        "services": {
            "db": {
                "image": "postgres:15-alpine",
                "environment": {"POSTGRES_PASSWORD": password, "POSTGRES_DB": "vertice_db"},
                "volumes": ["qa_data:/var/lib/postgresql/data"],
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U postgres -d vertice_db"],
                    "interval": "2s",
                    "timeout": "5s",
                    "retries": 20,
                },
            },
            "api": {
                "image": "vertice-api:latest",
                "depends_on": {"db": {"condition": "service_healthy"}},
                "environment": {
                    "POSTGRES_HOST": "db",
                    "POSTGRES_PASSWORD": password,
                    "SECRET_KEY": secrets.token_hex(32),
                    "ADMIN_USERNAME": "once_test",
                    "ADMIN_PASSWORD_HASH": hash_password("once-disposable-test"),
                    "COOKIE_SECURE": "false",
                    "ROOT_PATH": "/api",
                },
                "healthcheck": {
                    "test": [
                        "CMD",
                        "python",
                        "-c",
                        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/public/competiciones/', timeout=3)",
                    ],
                    "interval": "3s",
                    "timeout": "5s",
                    "start_period": "20s",
                    "retries": 20,
                },
            },
            "frontend": {
                "image": "vertice-frontend:latest",
                "ports": ["127.0.0.1:18080:80"],
                "depends_on": {"api": {"condition": "service_healthy"}},
                "healthcheck": {
                    "test": ["CMD", "wget", "-q", "--spider", "http://127.0.0.1/"],
                    "interval": "3s",
                    "timeout": "5s",
                    "retries": 10,
                },
            },
        },
        "volumes": {"qa_data": {}},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(add_worker(config), indent=2), encoding="utf-8")
    print(f"Configuración desechable preparada: {target}")


if __name__ == "__main__":
    prepare()
