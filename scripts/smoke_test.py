"""Comprueba el stack real a través de NGINX sin modificar sus catálogos.

Solo la espera inicial tolera errores transitorios. Una vez lista la API,
cualquier fallo de login, permisos, documentación o logout hace fallar la prueba.
"""

import http.client
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie


def wait_for_api(base_url, attempts=30, interval=1, timeout=3):
    """Esperar al 401 esperado de una ruta protegida, no solo a un puerto abierto."""
    last_error = "sin respuesta"
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(base_url + "/api/partidos/", timeout=timeout) as response:
                # Una respuesta pública 200 NO significa que la autenticación esté bien.
                raise AssertionError(
                    f"La ruta protegida devolvió HTTP {response.status}, se esperaba 401"
                )
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status == 401:
                return
            if status not in {502, 503, 504}:
                raise AssertionError(
                    f"La comprobación de disponibilidad devolvió HTTP {status}"
                ) from error
            last_error = f"HTTP {status} del proxy durante el arranque"
        except (
            urllib.error.URLError,
            ConnectionError,
            TimeoutError,
            http.client.HTTPException,
        ) as error:
            # Un puerto publicado por Docker puede resetear/cerrar conexiones antes
            # de que NGINX haya terminado su entrypoint. No siempre es un URLError.
            last_error = type(error).__name__
        if attempt + 1 < attempts:
            time.sleep(interval)
    raise RuntimeError(f"La API no arrancó detrás de NGINX tras {attempts} intentos ({last_error})")


def expect_unauthorized(opener, request, label):
    try:
        with opener.open(request, timeout=5):
            raise AssertionError(f"{label}: se esperaba HTTP 401")
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        if status != 401:
            raise AssertionError(f"{label}: HTTP {status} en vez de 401") from error


def check_stack(base_url, username, password):
    wait_for_api(base_url)
    print("OK: API protegida disponible detrás de NGINX.")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def login_request(value):
        return urllib.request.Request(
            base_url + "/api/login",
            data=json.dumps({"username": username, "password": value}).encode(),
            headers={"Content-Type": "application/json"},
        )

    expect_unauthorized(opener, login_request(password + "-incorrecta"), "Contraseña incorrecta")
    with opener.open(login_request(password), timeout=5) as response:
        cookie = SimpleCookie()
        cookie.load(response.headers.get("Set-Cookie", ""))
        assert response.status == 200 and json.load(response)["ok"], "El login no tuvo éxito"
        assert "vertice_token" in cookie and cookie["vertice_token"]["httponly"], (
            "Falta la cookie HttpOnly"
        )
        assert cookie["vertice_token"]["path"] == "/", "La cookie no cubre las rutas del panel"
    print("OK: login y cookie HttpOnly.")

    for name in ("confederaciones", "competiciones", "equipos", "partidos"):
        with opener.open(f"{base_url}/api/{name}/", timeout=5) as response:
            assert isinstance(json.load(response), list), f"El catálogo {name} no es una lista"
    print("OK: los cuatro catálogos responden con la sesión autenticada.")
    with opener.open(base_url + "/api/openapi.json", timeout=5) as response:
        assert json.load(response)["info"]["title"] == "ONCE API", "OpenAPI no corresponde a ONCE"
    with opener.open(base_url + "/api/docs", timeout=5) as response:
        assert b"/api/openapi.json" in response.read(), "La documentación perdió el prefijo /api"
    with opener.open(base_url + "/", timeout=5) as response:
        assert 'id="root"' in response.read().decode(), "NGINX no sirve el frontend"
    print("OK: documentación y frontend accesibles.")
    with opener.open(
        urllib.request.Request(base_url + "/api/logout", data=b""), timeout=5
    ) as response:
        assert json.load(response)["ok"], "El logout no tuvo éxito"
    assert not any(cookie.name == "vertice_token" for cookie in jar), "Logout no eliminó la cookie"
    expect_unauthorized(opener, base_url + "/api/partidos/", "Acceso después de logout")
    print("OK: logout y acceso anónimo rechazado.")


if __name__ == "__main__":
    check_stack(
        os.getenv("SMOKE_BASE_URL", "http://localhost:18080").rstrip("/"),
        os.getenv("SMOKE_USERNAME", "smoke"),
        os.environ["SMOKE_PASSWORD"],
    )
