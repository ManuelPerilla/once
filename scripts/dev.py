"""Cross-platform development tasks. Never evaluate .env as shell code."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
QA_FILE = ROOT / ".local" / "compose.qa.json"
TASKS = {
    "configure": "Generar .env sin reemplazar uno existente",
    "backend-install": "Instalar dependencias Python de desarrollo",
    "frontend-install": "Instalar frontend con npm ci",
    "api": "Migrar e iniciar la API manual en 127.0.0.1:8000",
    "worker": "Iniciar el trabajador manual con el mismo .env",
    "web": "Iniciar Vite local en 127.0.0.1:5173",
    "up": "Arrancar Docker y esperar su salud",
    "down": "Detener Docker conservando los volúmenes",
    "logs": "Consultar los últimos 100 registros de Docker",
    "health": "Consultar /api/health del frontend local",
    "lan": "Compartir ONCE por HTTP en la red local y mostrar sus direcciones",
    "local": "Restringir ONCE por HTTP a este equipo",
    "network-status": "Consultar configuración, puerto publicado y salud de la red",
    "lint": "Comprobar Ruff, formato y Oxlint",
    "test-api": "Ejecutar pytest en base aislada",
    "test-web": "Ejecutar pruebas unitarias del frontend",
    "build": "Compilar imágenes Docker sin reiniciar servicios",
    "docs-check": "Comprobar enlaces locales de Markdown",
    "check": "Lint, pruebas API/frontend y enlaces",
    "qa-up": "Preparar y arrancar once-qa en 127.0.0.1:18080",
    "qa-test": "Ejecutar Playwright únicamente contra once-qa",
    "qa-down": "Detener once-qa conservando sus volúmenes",
    "ci-local": "Check, build y navegador QA; detener QA al terminar",
    "backup": "Crear copia PostgreSQL y medios; pausar escrituras antes",
    "benchmark": "Banco destructivo: requiere sus argumentos y guardas",
}


def read_env(path):
    """Read literal KEY=value lines; process variables take precedence at launch."""
    values = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if not match:
            raise ValueError(f"Formato .env inválido en la línea {number}; usa CLAVE=valor.")
        key, value = match.groups()
        value = value.strip()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Comillas incompletas en .env, línea {number}.")
            value = value[1:-1]
        values[key] = value
    return values


def local_environment(env_file):
    return {**read_env(env_file), **os.environ}


def run(args, *, cwd=ROOT, env=None):
    executable = shutil.which(str(args[0]))
    if executable is None:
        raise ValueError(f"No se encontró {Path(args[0]).name}. Consulta SETUP.md.")
    result = subprocess.run([executable, *args[1:]], cwd=cwd, env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def python(*args, **kwargs):
    run([sys.executable, *args], **kwargs)


def npm(*args, **kwargs):
    run(["npm", *args], cwd=ROOT / "frontend", **kwargs)


def qa_config():
    config = json.loads(QA_FILE.read_text(encoding="utf-8"))
    services = config.get("services", {})
    if (
        config.get("name") != "once-qa"
        or services.get("frontend", {}).get("ports") != ["127.0.0.1:18080:80"]
        or services.get("db", {}).get("volumes") != ["qa_data:/var/lib/postgresql/data"]
        or any(value for value in config.get("volumes", {}).values())
        or config.get("networks")
        or any(
            service.get(key)
            for service in services.values()
            for key in ("env_file", "networks", "network_mode", "extra_hosts", "extends")
        )
    ):
        raise ValueError("El atajo QA exige el proyecto desechable once-qa y volúmenes propios.")
    for name in ("api", "worker"):
        service = services.get(name, {})
        env = service.get("environment", {})
        if (
            not isinstance(env, dict)
            or env.get("DATABASE_URL")
            or env.get("POSTGRES_HOST") != "db"
            or str(env.get("POSTGRES_PORT", 5432)) != "5432"
            or env.get("POSTGRES_DB", "vertice_db") != "vertice_db"
            or service.get("volumes") != ["qa_media:/app/.media"]
        ):
            raise ValueError(
                "La API y el trabajador QA deben usar exclusivamente su base db y medios QA."
            )
    return config


def qa_compose(*args):
    qa_config()
    run(["docker", "compose", "--project-name", "once-qa", "-f", str(QA_FILE), *args])


def check_test_database(value):
    if not value:
        return
    url = urlsplit(value)
    if url.scheme.split("+")[0] == "sqlite":
        if url.netloc or url.path not in ("", "/:memory:") or url.query:
            raise ValueError(
                "El atajo pytest solo admite SQLite en memoria, nunca archivos de trabajo."
            )
    elif not url.path.endswith("_test"):
        raise ValueError("TEST_DATABASE_URL debe nombrar una base desechable terminada en _test.")


def execute(task, env_file, extra=()):
    if task in {"lan", "local", "network-status"}:
        if env_file.resolve() != (ROOT / ".env").resolve():
            raise ValueError("Los modos de red usan el .env del proyecto, no --env-file.")
        python("-m", "scripts.network", "status" if task == "network-status" else task, *extra)
    elif task == "configure":
        python("-m", "src.configure")
    elif task == "backend-install":
        python("-m", "pip", "install", "-r", "requirements-dev.txt")
    elif task == "frontend-install":
        npm("ci")
    elif task in {"api", "worker"}:
        env = local_environment(env_file)
        if not env.get("DATABASE_URL") and env.get("POSTGRES_HOST") == "db":
            raise ValueError(
                "Para ejecución manual, configura POSTGRES_HOST=127.0.0.1 y su puerto."
            )
        if task == "api":
            python("-m", "src.migrate", env=env)
            python(
                "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8000", env=env
            )
        else:
            python("-m", "src.sync.worker", env=env)
    elif task == "web":
        npm("run", "dev", "--", "--host", "127.0.0.1")
    elif task in {"up", "down", "build", "logs"}:
        arguments = {
            "up": ["up", "-d", "--wait"],
            "down": ["down"],
            "build": ["build"],
            "logs": ["logs", "--tail=100", "api", "worker", "frontend", "db"],
        }
        run(["docker", "compose", *arguments[task]])
    elif task == "health":
        env = local_environment(env_file)
        host = env.get("FRONTEND_BIND", "127.0.0.1")
        host = "127.0.0.1" if host == "0.0.0.0" else host
        port = int(env.get("FRONTEND_PORT", "80"))
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=10) as response:
            print(response.read().decode())
    elif task == "lint":
        python("-m", "ruff", "check", "src", "tests", "scripts")
        python("-m", "ruff", "format", "--check", "src", "tests", "scripts")
        npm("run", "lint")
    elif task == "test-api":
        check_test_database(os.getenv("TEST_DATABASE_URL"))
        python(
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--basetemp=.local/pytest-dev-{uuid4().hex}",
        )
    elif task == "test-web":
        npm("test")
    elif task == "docs-check":
        python("-m", "scripts.check_links")
    elif task == "check":
        for step in ("lint", "test-api", "test-web", "docs-check"):
            execute(step, env_file)
    elif task == "qa-up":
        python("-m", "scripts.prepare_qa")
        qa_compose("up", "-d", "--wait")
    elif task == "qa-test":
        qa_config()
        env = {
            **os.environ,
            "SMOKE_BASE_URL": "http://127.0.0.1:18080",
            "SMOKE_DISPOSABLE": "1",
            "SMOKE_USERNAME": "once_test",
            "SMOKE_PASSWORD": os.getenv("SMOKE_PASSWORD", "once-disposable-test"),
        }
        qa_compose("up", "-d", "--wait")
        npm("run", "test:e2e", env=env)
    elif task == "qa-down":
        qa_compose("down")
    elif task == "ci-local":
        execute("check", env_file)
        execute("build", env_file)
        try:
            execute("qa-up", env_file)
            execute("qa-test", env_file)
        finally:
            if QA_FILE.exists():
                execute("qa-down", env_file)
    elif task == "backup":
        python("-m", "scripts.backup", "--include-media")
    elif task == "benchmark":
        python("-m", "scripts.benchmark_automation", *(extra or ["--help"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default="help", choices=["help", *TASKS])
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args, extra = parser.parse_known_args()
    if extra and args.task not in {"benchmark", "lan", "local", "network-status"}:
        parser.error("Solo benchmark y las tareas de red aceptan argumentos adicionales.")
    if args.task == "help":
        for task, description in TASKS.items():
            print(f"{task:18} {description}")
        return
    try:
        execute(args.task, args.env_file, extra)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
