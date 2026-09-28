"""Portable HTTP access modes for ONCE: python -m scripts.network lan|local|status."""

import argparse
import contextlib
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from scripts.network_addresses import discover_addresses

ROOT = Path(__file__).resolve().parents[1]
MANAGED = ("FRONTEND_BIND", "FRONTEND_PORT", "COOKIE_SECURE")
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
COMPOSE_OVERRIDES = ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "COMPOSE_PROFILES")
QUOTED_LINE = re.compile(r"""(?:'[^']*'|"(?:\\.|[^"\\])*")\s*(?:#.*)?""")


class NetworkError(RuntimeError):
    pass


def port_number(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise NetworkError("El puerto debe ser un entero entre 1 y 65535.") from None
    if not 1 <= port <= 65535:
        raise NetworkError("El puerto debe estar entre 1 y 65535.")
    return port


def setting(value):
    """Read only public network settings; all other .env bytes remain opaque."""
    value = value.strip()
    if value.startswith(("'", '"')):
        end = value.find(value[0], 1)
        if end < 0 or (value[end + 1 :].strip() and not value[end + 1 :].strip().startswith("#")):
            raise NetworkError("Una variable de red contiene comillas o comentarios inválidos.")
        return value[1:end], value[end + 1 :].strip()
    plain, marker, comment = value.partition("#")
    return plain.strip(), marker + comment


def network_values(content):
    values = {}
    for line in content.decode("utf-8-sig").splitlines():
        match = ASSIGNMENT.fullmatch(line)
        if match:
            key, value = match.groups()
            raw = value.strip()
            if raw.startswith(("'", '"')) and not QUOTED_LINE.fullmatch(raw):
                raise NetworkError(
                    "El editor de red no admite valores multilínea o comillas sin cerrar en .env. Conserva el archivo y configura la red manualmente."
                )
            if key in COMPOSE_OVERRIDES and setting(value)[0]:
                raise NetworkError(
                    f"{key} en .env redirige Compose; este asistente requiere la configuración base del proyecto."
                )
            if key not in (*MANAGED, "VITE_API_URL"):
                continue
            if key in values:
                raise NetworkError(f"{key} está duplicada en .env; conserva una sola definición.")
            values[key] = setting(value)[0]
    return values


def edited_env(content, changes):
    network_values(content)
    text = content.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    seen, lines = set(), []
    for line in text.splitlines(keepends=True):
        match = ASSIGNMENT.fullmatch(line.rstrip("\r\n"))
        if match and match[1] in changes:
            key = match[1]
            comment = setting(match[2])[1]
            ending = line[len(line.rstrip("\r\n")) :]
            line = f"{key}={changes[key]}" + (f" {comment}" if comment else "") + ending
            seen.add(key)
        lines.append(line)
    result = "".join(lines)
    for key, value in changes.items():
        if key not in seen:
            if result and not result.endswith(("\r", "\n")):
                result += newline
            result += f"{key}={value}{newline}"
    return (b"\xef\xbb\xbf" if content.startswith(b"\xef\xbb\xbf") else b"") + result.encode(
        "utf-8"
    )


def replace_env(path, expected, replacement):
    if path.is_symlink() or path.read_bytes() != expected:
        raise NetworkError(".env cambió durante la operación o es un enlace; no se sobrescribió.")
    if expected == replacement:
        return
    descriptor, filename = tempfile.mkstemp(prefix=".env.network-", dir=path.parent)
    temporary = Path(filename)
    os.close(descriptor)
    try:
        if os.name == "nt":
            # Apply the source access list before any credential bytes reach staging.
            source = str(path).replace("'", "''")
            destination = str(temporary).replace("'", "''")
            run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    f"$ErrorActionPreference='Stop'; $acl=[System.IO.File]::GetAccessControl('{source}'); "
                    "$acl.SetAccessRuleProtection($true,$true); "
                    f"[System.IO.File]::SetAccessControl('{destination}', $acl)",
                ],
                timeout=30,
            )
        with temporary.open("wb") as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copystat(path, temporary)
        if path.read_bytes() != expected:
            raise NetworkError(".env cambió durante la operación; no se sobrescribió.")
        if os.name == "nt":
            # ReplaceFile preserves the original Windows DACL; never ignore ACL errors.
            replace = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
            replace.argtypes = [ctypes.c_wchar_p] * 3 + [
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ]
            replace.restype = ctypes.c_int
            if not replace(str(path), str(temporary), None, 0, None, None):
                raise NetworkError(
                    f"Windows no pudo actualizar .env (código {ctypes.get_last_error()}); "
                    f"se conserva el temporal privado {temporary.name}."
                )
        else:
            os.replace(temporary, path)
    except NetworkError:
        # On a native replacement failure retain recovery evidence instead of deleting it.
        raise
    except OSError as exc:
        raise NetworkError(f"No se pudo guardar .env ({type(exc).__name__}).") from None
    else:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def operation_lock():
    directory = ROOT / ".local"
    directory.mkdir(exist_ok=True)
    with (directory / "network.lock").open("a+b") as lock:
        try:
            lock.seek(0)
            if not lock.read(1):
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise NetworkError(
                "Otro comando de red de ONCE está en curso. Espera a que termine."
            ) from None
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def run(arguments, *, env=None, timeout=60, visible=False):
    executable = shutil.which(arguments[0])
    if not executable:
        raise NetworkError(f"No se encontró {arguments[0]}; revisa SETUP.md.")
    try:
        result = subprocess.run(
            [executable, *arguments[1:]],
            cwd=ROOT,
            env=env,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=not visible,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise NetworkError(f"{arguments[0]} excedió su tiempo de espera.") from None
    if result.returncode:
        # Compose config/inspect may contain secrets: never print captured output.
        raise NetworkError(f"{arguments[0]} no completó la operación (salida {result.returncode}).")
    return result.stdout or ""


def compose(*arguments, env=None, visible=False, timeout=180):
    return run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(ROOT / ".env"),
            "-f",
            str(ROOT / "docker-compose.yml"),
            *arguments,
        ],
        env=env,
        visible=visible,
        timeout=timeout,
    )


def docker_preflight():
    for key in COMPOSE_OVERRIDES:
        if os.getenv(key):
            raise NetworkError(
                f"Retira {key} de esta terminal; este comando usa el Compose del proyecto."
            )
    context = os.getenv("DOCKER_CONTEXT")
    host = None if context else os.getenv("DOCKER_HOST")
    if not host:
        host = json.loads(
            run(
                [
                    "docker",
                    "context",
                    "inspect",
                    *([context] if context else []),
                    "--format",
                    "{{json .Endpoints.docker.Host}}",
                ]
            )
        )
    if not host.startswith(("npipe://", "unix://")):
        raise NetworkError(
            "Este comando necesita un motor Docker local, no un contexto remoto o TCP."
        )
    run(["docker", "info", "--format", "{{.ServerVersion}}"])


def existing_services(env):
    ids = compose("ps", "--all", "--quiet", env=env).split()
    if not ids:
        return False
    containers = json.loads(run(["docker", "inspect", *ids]))
    for container in containers:
        labels = container.get("Config", {}).get("Labels", {})
        directory = labels.get("com.docker.compose.project.working_dir")
        if not directory or os.path.normcase(os.path.abspath(directory)) != os.path.normcase(
            str(ROOT.resolve())
        ):
            raise NetworkError(
                "La identidad Compose pertenece a otra carpeta. No se modificó esa instalación."
            )
    return True


def firewall_preflight():
    if os.name != "nt":
        raise NetworkError(
            "--firewall automatiza Windows. En Linux/macOS configura el firewall del anfitrión."
        )
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise NetworkError(
            "--firewall necesita una terminal como administrador. El modo sin esa opción no la exige."
        )


def firewall(action, port):
    run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "network-firewall.ps1"),
            "-Action",
            action,
            "-Port",
            str(port),
        ],
        visible=True,
    )


def health(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=10) as response:
            payload = json.load(response)
            return (
                response.status == 200
                and isinstance(payload, dict)
                and payload.get("status") == "ok"
            )
    except (OSError, ValueError, urllib.error.URLError):
        return False


def show_addresses(mode, port):
    suffix = "" if port == 80 else f":{port}"
    print(f"En este equipo: http://localhost{suffix}/")
    if mode == "lan":
        addresses = discover_addresses()
        for address in addresses:
            print(
                f"En tu red: http://{address}{suffix}/  |  Explorar: http://{address}{suffix}/explore"
            )
        if not addresses:
            print("No se detectó una IPv4 privada activa. Comprueba la conexión Wi-Fi/Ethernet.")
        print(
            "Los otros dispositivos deben estar en la misma red; la prueba local no verifica su firewall ni el router."
        )


def execute(mode, *, port=None, no_build=False, with_firewall=False, dry_run=False):
    path = ROOT / ".env"
    if not path.exists():
        if mode == "status" or dry_run or not sys.stdin.isatty():
            raise NetworkError(
                "Falta .env. Configura esta instalación con: python -m src.configure"
            )
        run([sys.executable, "-m", "src.configure"], visible=True, timeout=600)
    with operation_lock():
        original = path.read_bytes()
        values = network_values(original)
        selected_port = port_number(port if port is not None else values.get("FRONTEND_PORT", "80"))
        if mode == "status":
            print(
                f"Configuración guardada: bind={values.get('FRONTEND_BIND', '127.0.0.1')}, puerto={selected_port}, cookie segura={values.get('COOKIE_SECURE', 'true')}"
            )
            docker_preflight()
            existing_services(os.environ.copy())
            published = compose("port", "frontend", "80").strip()
            print(f"Puerto publicado por Docker: {published or 'sin servicio activo'}")
            expected = f"{values.get('FRONTEND_BIND', '127.0.0.1')}:{selected_port}"
            if published != expected:
                print(
                    "Docker no coincide con la configuración guardada. Aplica lan o local para reconciliarla."
                )
                return 1
            healthy = health(selected_port)
            print(f"Salud HTTP local: {'correcta' if healthy else 'no disponible'}")
            show_addresses(
                "lan" if values.get("FRONTEND_BIND") == "0.0.0.0" else "local", selected_port
            )
            return 0 if healthy else 1
        changes = {
            "FRONTEND_BIND": "0.0.0.0" if mode == "lan" else "127.0.0.1",
            "FRONTEND_PORT": str(selected_port),
            "COOKIE_SECURE": "false",
        }
        for key, value in changes.items():
            if key in os.environ and os.environ[key] != value:
                raise NetworkError(
                    f"{key} en la terminal contradice el modo solicitado; retírala y repite."
                )
        if os.getenv("VITE_API_URL", values.get("VITE_API_URL", "/api")) != "/api":
            raise NetworkError(
                "El modo de red necesita VITE_API_URL=/api y frontend reconstruido para usar el mismo origen."
            )
        updated = edited_env(original, changes)
        if dry_run:
            print("Vista previa; no se modifica la instalación:")
            for key, value in changes.items():
                print(f"{key}={value}")
            show_addresses(mode, selected_port)
            return 0
        if with_firewall:
            firewall_preflight()
        docker_preflight()
        environment = {**os.environ, **changes}
        compose("config", "--quiet", env=environment)
        existing = existing_services(environment)
        if not no_build:
            print("Preparando las imágenes de ONCE...")
            compose("build", "api", "frontend", env=environment, visible=True, timeout=900)
        replace_env(path, original, updated)
        arguments = ["up", "--no-build", "-d", "--wait", "--wait-timeout", "120"]
        if existing:
            arguments += ["api", "frontend"]
        try:
            compose(*arguments, env=environment, visible=True)
            if not health(selected_port):
                raise NetworkError(
                    "La comprobación HTTP del nuevo puerto no respondió correctamente."
                )
        except NetworkError as exc:
            replace_env(path, updated, original)
            recovered = False
            if existing:
                previous = {
                    **os.environ,
                    "FRONTEND_BIND": values.get("FRONTEND_BIND", "127.0.0.1"),
                    "FRONTEND_PORT": values.get("FRONTEND_PORT", "80"),
                    "COOKIE_SECURE": values.get("COOKIE_SECURE", "true"),
                }
                try:
                    compose(
                        "up",
                        "--no-build",
                        "-d",
                        "--wait",
                        "--wait-timeout",
                        "120",
                        "api",
                        "frontend",
                        env=previous,
                        visible=True,
                    )
                    recovered = health(port_number(previous["FRONTEND_PORT"]))
                except NetworkError:
                    pass
            raise NetworkError(
                f"{exc} Se restauró .env. "
                + (
                    "La configuración anterior vuelve a responder."
                    if recovered
                    else "Docker puede quedar parcialmente actualizado. Revisa docker compose ps y recupera el arranque con docker compose up -d --wait."
                )
            ) from None
        if with_firewall:
            try:
                firewall("Enable" if mode == "lan" else "Disable", selected_port)
                previous_port = port_number(values.get("FRONTEND_PORT", "80"))
                if previous_port != selected_port:
                    firewall("Disable", previous_port)
            except NetworkError as exc:
                raise NetworkError(
                    f"ONCE responde, pero el firewall no se completó: {exc}"
                ) from None
        print(
            f"ONCE listo: modo {'red local' if mode == 'lan' else 'solo este equipo'}, HTTP, puerto {selected_port}."
        )
        show_addresses(mode, selected_port)
        if mode == "local" and not with_firewall and os.name == "nt":
            print(
                "Si creaste una regla con --firewall, local --firewall retira la de este puerto desde una terminal administradora."
            )
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("lan", "local", "status"))
    parser.add_argument(
        "--port", type=int, help="Puerto HTTP del frontend; conserva el configurado si se omite"
    )
    parser.add_argument(
        "--no-build", action="store_true", help="Reutilizar imágenes ya construidas"
    )
    parser.add_argument(
        "--firewall",
        action="store_true",
        help="Gestionar solo la regla LAN de Windows (requiere administrador)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Mostrar el cambio sin aplicarlo")
    args = parser.parse_args()
    if args.mode == "status" and (
        args.port is not None or args.no_build or args.firewall or args.dry_run
    ):
        parser.error("status no acepta opciones de cambio; consulta el estado real guardado.")
    try:
        return execute(
            args.mode,
            port=args.port,
            no_build=args.no_build,
            with_firewall=args.firewall,
            dry_run=args.dry_run,
        )
    except (NetworkError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        message = (
            str(exc)
            if isinstance(exc, NetworkError)
            else f"No se pudo consultar la instalación ({type(exc).__name__})."
        )
        print(f"ONCE: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
