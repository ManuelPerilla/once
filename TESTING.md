# Pruebas y verificación de ONCE

Comprueba un cambio desde su regla más pequeña hasta su recorrido en Docker, sin usar la base de trabajo como entorno de pruebas.
Esta guía distingue procedimientos reproducibles, referencia de herramientas y evidencia de ejecuciones anteriores.

**Mapa del proyecto:** [Inicio](README.md) · [Contexto](CONTEXT.md) · [Arquitectura](ARCHITECTURE.md) · [Instalación](SETUP.md) · [Despliegue](DEPLOYMENT.md) · [Diagnóstico](TROUBLESHOOTING.md) · [Contribución](CONTRIBUTING.md).

## Referencia: qué comprueba cada capa

| Capa | Herramienta real | Qué demuestra | Qué no demuestra |
| --- | --- | --- | --- |
| Análisis estático | Ruff 0.16.9; Oxlint 1.82.0 | Errores detectables y reglas de estilo configuradas | Corrección funcional o ausencia de vulnerabilidades |
| Reglas y adaptadores | pytest 9.1.1; `node:test` con Node 24 | Casos de dominio, serialización, filtros y selección de datos | Comportamiento del navegador o del proveedor disponible hoy |
| API y persistencia | pytest, FastAPI TestClient, SQLite/PostgreSQL 15 | Autenticación, integridad, consultas, reservas y transacciones | Tráfico real a través de NGINX |
| Integración del despliegue | `scripts.smoke_test` | Proxy, cookie, catálogos, documentación y cierre de sesión | Todos los recorridos de la interfaz |
| Navegador | Playwright 1.63, Chromium | Interacciones, navegación, estados y tamaños de pantalla | Compatibilidad certificada con todos los navegadores |
| Rendimiento | `scripts.benchmark_automation` | Latencias ASGI y PostgreSQL bajo carga sintética | Latencia de Internet, renderizado o capacidad sostenida de producción |
| Asistentes de red | pytest y Pester 3.4 en Windows | Descubrimiento, guardas, recuperación y contrato de la regla con dependencias simuladas | Conectividad real entre dispositivos o políticas efectivas del router/firewall |

Las versiones Python se fijan en [requirements-dev.txt](requirements-dev.txt); las del frontend se resuelven con [package-lock.json](frontend/package-lock.json).
`package.json` admite Oxlint desde `^1.81.0`; el lock vigente fija 1.82.0, que es la versión reproducida por `npm ci`.
Node 24 es la versión usada en CI y en el Dockerfile del frontend; Python usa 3.12.
No hay Selenium, k6, medición de cobertura porcentual ni umbral automático de cobertura implantados.
La pirámide describe responsabilidades: no es una promesa de proporciones entre tipos de pruebas.

La revisión manual completa esa pirámide: comprueba legibilidad a 320 px, foco de teclado, contraste y comprensión de los estados «sin datos», «en espera» y «pendiente de revisión». Playwright puede verificar que un filtro funciona; la persona revisora debe confirmar que su significado sea evidente. Los ejemplos deportivos ambiguos se contrastan con su procedencia antes de aceptar el resultado visual.

## Tutorial: tu primera comprobación local

Desde la raíz, crea un entorno Python e instala las dependencias de desarrollo.
En PowerShell puedes ejecutar el intérprete directamente, sin cambiar la política de ejecución:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:DATABASE_URL = 'sqlite://'
$env:TEST_DATABASE_URL = 'sqlite://'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.local/pytest-primer-paso
Remove-Item Env:DATABASE_URL, Env:TEST_DATABASE_URL
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
```

En una terminal POSIX:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
export DATABASE_URL=sqlite://
export TEST_DATABASE_URL=sqlite://
.venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=.local/pytest-primer-paso
unset DATABASE_URL TEST_DATABASE_URL
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m ruff format --check src tests scripts
```

`--basetemp` permite a pytest limpiar esa carpeta: usa una ruta exclusiva de pruebas, nunca una carpeta con documentos o copias.
Usa una terminal de pruebas independiente: retiramos sus variables al terminar para que no sustituyan la conexión de `.env` al arrancar luego la API manual.
En las siguientes instrucciones, `python` representa el intérprete del entorno virtual; actívalo o sustituye ese nombre por su ruta.
Estas pruebas usan fuentes simuladas: no necesitan una clave API-Football ni consumen su cuota.

Después, comprueba el frontend con Node 24:

```sh
cd frontend
npm ci
npm test
npm run lint
npm run build
cd ..
python -m scripts.check_links
```

Un resultado correcto combina código de salida cero con las pruebas esperadas ejecutadas.
Un `skip` se interpreta según su motivo: SQLite omite los casos exclusivos de concurrencia PostgreSQL.
Para los atajos de desarrollo y revisión de cambios, consulta [CONTRIBUTING.md](CONTRIBUTING.md).

Salida abreviada observada al validar esta entrega el 27-09-2026; el tiempo no es un objetivo de rendimiento:

```text
320 passed, 4 skipped, 2 warnings in 66.14s (0:01:06)
```

Los dos avisos son deprecaciones de Starlette/TestClient y AnyIO, descritas en el registro de desarrollo. El frontend informó por separado:

```text
tests 53
pass 53
fail 0
skipped 0
```

## Cómo ejecutar las pruebas Python dentro de Docker

Esta alternativa no requiere instalar pytest ni Ruff en el anfitrión:

```sh
docker build --target test -t once-api-tests .
docker run --rm --network none once-api-tests
docker run --rm --network none once-api-tests python -m ruff check src tests scripts
docker run --rm --network none once-api-tests python -m ruff format --check src tests scripts
```

La imagen de pruebas usa SQLite en memoria y no monta el volumen de PostgreSQL de trabajo.
`--network none` refuerza que la ejecución no dependa de proveedores remotos; la compilación sí necesita descargar dependencias.
La imagen `runtime` no incluye las herramientas de pruebas. El comprobador de documentación se ejecuta desde el repositorio completo.

## Cómo comprobar los asistentes de red

Las pruebas Python de LAN utilizan adaptadores, rutas, respuestas HTTP y comandos Docker simulados. No habilitan puertos, modifican el firewall del anfitrión ni consultan proveedores. Los archivos de configuración de cada caso se crean en directorios temporales de pruebas.

Desde una terminal de pruebas con el Python de `.venv`, fija las dos conexiones en memoria para que la infraestructura compartida de pytest no apunte a una base persistente. PowerShell:

```powershell
$env:DATABASE_URL = 'sqlite://'
$env:TEST_DATABASE_URL = 'sqlite://'
python -m pytest -q -p no:cacheprovider --basetemp=.local/pytest-network-docs tests/test_network_addresses.py tests/test_network_commands.py tests/test_network_review.py
Remove-Item Env:DATABASE_URL, Env:TEST_DATABASE_URL
```

En POSIX, las asignaciones pueden limitarse a la ejecución:

```sh
DATABASE_URL=sqlite:// TEST_DATABASE_URL=sqlite:// python -m pytest -q -p no:cacheprovider --basetemp=.local/pytest-network-docs tests/test_network_addresses.py tests/test_network_commands.py tests/test_network_review.py
```

| Archivo | Contratos cubiertos |
| --- | --- |
| [test_network_addresses.py](tests/test_network_addresses.py) | Interfaces activas de Windows/Linux/macOS, prioridad de ruta, exclusión de VPN/virtuales identificables, RFC1918, duplicados y comandos no disponibles |
| [test_network_commands.py](tests/test_network_commands.py) | Modos LAN/local, opciones, primer arranque, preservación de configuración, fallos de aplicación, identidad Compose y atajos |
| [test_network_review.py](tests/test_network_review.py) | Contexto Docker remoto, overrides Compose, pertenencia al consultar estado, contenido multilínea y respuesta de salud inválida |
| [network-firewall.Tests.ps1](tests/network-firewall.Tests.ps1) | TCP/puerto/LocalSubnet, repetición sin duplicados, retirada selectiva, colisiones y ausencia de permiso administrativo |

La suite de firewall se ejecuta **por separado en Windows PowerShell con Pester 3.4.0**. Ese es el contrato usado para estos ejemplos; otras versiones de Pester no están verificadas. Comprueba primero qué versión tienes, sin instalar ni actualizar módulos globales como parte de una prueba:

```powershell
Get-Module -ListAvailable Pester | Select-Object Name, Version
powershell.exe -NoProfile -Command "Import-Module Pester -RequiredVersion 3.4.0 -ErrorAction Stop; Invoke-Pester -Script './tests/network-firewall.Tests.ps1' -EnableExit"
```

Las operaciones `Get-NetFirewallRule`, `New-NetFirewallRule`, `Set-NetFirewallRule` y `Remove-NetFirewallRule`, además de la comprobación administrativa, se sustituyen por mocks. Esta suite no necesita elevar la terminal ni debe sustituirse por una ejecución del asistente con `--firewall`. Si Pester 3.4.0 no está instalado, informa que esta selección no se ejecutó; una suite Python correcta no la reemplaza.

El ensayo real es distinto: desde una instalación de prueba identificada, aplica `lan`, consulta `status`, abre la dirección anunciada desde un segundo dispositivo y comprueba exploración e inicio/cierre de sesión. Después vuelve a `local` y comprueba que el acceso se limite al anfitrión. Registra revisión, sistema operativo, puerto, operaciones realizadas y resultado; una propuesta de ensayo no es evidencia de ejecución. Revisa [el procedimiento de red](docs/deployment/network.md) antes de aplicarlo: el asistente usa la identidad Compose principal y no acepta overrides para redirigirlo a `once-qa`; un clon adicional en el mismo motor tampoco crea volúmenes independientes por sí solo.

## Cómo comprobar PostgreSQL sin tocar los datos de trabajo

**La fixture de pytest elimina y recrea tablas en `TEST_DATABASE_URL`.** A diferencia del banco de rendimiento, no valida el nombre de la base.
El atajo `scripts.dev test-api` añade guardas para SQLite en memoria y nombres externos `_test`; estos comandos directos de pytest no pasan por él.
La URL debe identificar una base creada exclusivamente para pruebas; jamás uses `vertice_db` de la instalación principal.
El siguiente ejemplo emplea una contraseña pública de QA y un puerto de loopback distinto del habitual.
Si el nombre del contenedor o el puerto ya están ocupados, elige otros; no retires un servicio que no hayas identificado.

```sh
docker run --detach --name once-tests-qa --label once.purpose=qa --publish 127.0.0.1:15436:5432 --env POSTGRES_PASSWORD=qa_local_only --env POSTGRES_DB=once_pytest_test postgres:15-alpine
docker exec once-tests-qa pg_isready -U postgres -d once_pytest_test
```

Espera a que el segundo comando confirme que acepta conexiones. En PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://postgres:qa_local_only@127.0.0.1:15436/once_pytest_test'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.local/pytest-postgres
Remove-Item Env:TEST_DATABASE_URL
```

En POSIX, la variable puede limitarse a una sola ejecución:

```sh
TEST_DATABASE_URL=postgresql://postgres:qa_local_only@127.0.0.1:15436/once_pytest_test .venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=.local/pytest-postgres
```

Al terminar y después de verificar que es el contenedor creado arriba, retira solo ese entorno y su volumen anónimo:

```sh
docker inspect --format '{{json .Config.Labels}}' once-tests-qa
docker rm --force --volumes once-tests-qa
```

La migración tiene otro contrato: `python -m scripts.migration_smoke` usa `DATABASE_URL`, exige una base vacía terminada en `_test` y rechaza un downgrade destructivo.
Ejecuta ese ensayo en una base desechable independiente y vacía. [Desarrollo](docs/development.md) explica la adopción de esquemas anteriores.

## Cómo recorrer la interfaz en una instalación QA

Playwright crea y modifica registros. Su configuración exige `SMOKE_BASE_URL` y `SMOKE_DISPOSABLE=1`, pero esa declaración no identifica mágicamente una base segura.
Prepara el conjunto independiente desde la raíz:

```sh
docker compose build
python -m scripts.prepare_qa
docker compose -f .local/compose.qa.json up -d --wait
```

El generador crea `once-qa`, volúmenes propios y el frontend en `127.0.0.1:18080`.
Cuando el archivo ya existe conserva su identidad y secretos; si fue personalizado, utiliza sus credenciales conocidas sin publicarlo.
Para una configuración nueva, en PowerShell:

```powershell
$env:SMOKE_BASE_URL = 'http://127.0.0.1:18080'
$env:SMOKE_DISPOSABLE = '1'
$env:SMOKE_USERNAME = 'once_test'
$env:SMOKE_PASSWORD = 'once-disposable-test'
python -m scripts.smoke_test
Set-Location frontend
npx playwright install chromium
npm run test:e2e
Set-Location ..
```

En POSIX, usa estas asignaciones y después los mismos comandos de prueba desde la raíz:

```sh
export SMOKE_BASE_URL=http://127.0.0.1:18080
export SMOKE_DISPOSABLE=1
export SMOKE_USERNAME=once_test
export SMOKE_PASSWORD=once-disposable-test
python -m scripts.smoke_test
cd frontend
npx playwright install chromium
npm run test:e2e
cd ..
```

En Linux puede ser necesario instalar también las dependencias de Chromium con `npx playwright install --with-deps chromium`.
La configuración actual usa un trabajador, cero reintentos automáticos y conserva captura/traza cuando falla un recorrido.
Inspecciona `frontend/test-results/`; las trazas pueden contener datos de la sesión QA, por lo que se revisan antes de compartirlas.
`CATALOG_LIVE_TEST=1` habilita una importación real optativa: requiere red y disponibilidad externa; no pertenece a la prueba sin proveedores.
La importación real API-Football se valida por separado desde administración y consume presupuesto; no se activa por ejecutar estas pruebas.

Al acabar, retira exclusivamente el conjunto QA:

```sh
docker compose -f .local/compose.qa.json down --volumes
```

## Cómo medir rendimiento y leer el resultado

El [banco implementado](scripts/benchmark_automation.py) genera datos sintéticos y recrea las tablas del destino.
Prepara primero un PostgreSQL local desechable, como el del ejemplo anterior, y conserva `TEST_DATABASE_URL` apuntando únicamente a él.
Las guardas exigen PostgreSQL, host `localhost`/`127.0.0.1`, puerto explícito distinto de 5432 y nombre `once_*_test`.
También exigen `--allow-disposable-db`; `--docker-container` solo acepta nombres `once-…qa` para consultar métricas.

```sh
python -m scripts.benchmark_automation --help
python -m scripts.benchmark_automation --allow-disposable-db --docker-container once-tests-qa --sizes 10000,100000 --readers 10 --requests-per-reader 50 --output .local/benchmarks/automation.json
```

El segundo comando requiere restablecer la URL desechable si la retiraste al finalizar pytest; no arranca PostgreSQL por sí mismo.
Acepta 1–25 lectores, 10–1.000 solicitudes por lector y tamaños crecientes únicos de 1.000–100.000 partidos.
Cada partido recibe diez eventos sintéticos. El trabajador real usa la cola y publicación auditada con descarga simulada de 20 ms.
El informe compara lectura base e ingesta concurrente e incluye p50/p95/p99, errores, estados de trabajos y recursos de PostgreSQL.
Un ensayo corto no constituye un SLA; analiza errores y estados persistidos antes de comparar percentiles.
Los resultados originales y sus límites están descritos en [Rendimiento del piloto](docs/automation/performance.md).

Ejemplo ilustrativo del formato de consola, condicionado a que ambas etapas terminen sin errores; no representa una nueva medición:

```text
Preparing 10,000 matches / 100,000 events…
Recorded 10,000 matches. Errors: 0.
Preparing 100,000 matches / 1,000,000 events…
Recorded 100,000 matches. Errors: 0.
Report: /ruta/once/.local/benchmarks/automation.json
```

En el JSON, compara `sizes[].baseline` y `sizes[].ingesting`: `routes` contiene distribuciones de latencia; `errors` y `worker_outcomes` ayudan a descartar una mejora aparente obtenida con solicitudes o escrituras fallidas.

## Referencia: seleccionar las pruebas que corresponden

| Cambio | Selección inicial y comprobación adicional |
| --- | --- |
| Identidades, ediciones o importadores | `test_api_football_ingestion.py`, `test_automation_discovery.py`, `test_openfootball.py`; integridad PostgreSQL |
| Cuotas, pausa o transporte | `test_api_football_quota.py`, `test_provider_preview.py`, `test_sync_safety.py`; concurrencia PostgreSQL |
| Autenticación o roles | `test_security.py`, `test_accounts_audit_api.py`; smoke y recorrido de sesión |
| Tablas, filtros o procedencia | `test_standing_context.py`, `test_match_provenance.py`; unitarias y recorridos públicos afectados |
| Consultas o esquema | `test_query_loading.py`, pruebas PostgreSQL y ensayo de migración según el cambio |
| Contenedores o proxy | Compilación, salud, smoke y navegador contra el conjunto QA |
| Asistentes de red o firewall | `test_network_addresses.py`, `test_network_commands.py`, `test_network_review.py`; Pester en Windows y ensayo LAN separado cuando corresponda |

Por ejemplo: `python -m pytest -q tests/test_api_football_quota.py tests/test_provider_preview.py`.
Una selección sirve para iterar; la entrega incorpora además las comprobaciones compartidas que puedan verse afectadas.
No reproduzcas una carrera ajustando el reloj real: usa el reloj controlado de las pruebas y conserva la condición que debe verificarse.

## Referencia: CI disponible y evidencia histórica

El [flujo vigente](.github/workflows/ci.yml) se inicia únicamente con `workflow_dispatch`.
No se ejecuta por cada commit, PR o calendario. Tiene tres trabajos: API/PostgreSQL, frontend y Docker/navegador.
Docker depende de los dos primeros; las credenciales del flujo son desechables, los permisos son de lectura y no hay despliegue automático.
Una nueva ejecución en la misma rama cancela la anterior. Consulta [GitHub y entregas](docs/deployment/github.md) antes de lanzarlo.

| Registro del 27 de septiembre de 2026 | Resultado observado | Alcance |
| --- | --- | --- |
| Imagen Docker al cerrar estos manuales | 320 pruebas aprobadas; cuatro omitidas | Incluye 17 casos del ayudante de desarrollo; las cuatro omitidas requieren PostgreSQL |
| Imagen Docker anterior a estos manuales | 303 pruebas aprobadas; cuatro omitidas | Entrega de conexión e importación API-Football |
| Suite anterior en PostgreSQL 15 | 273 pruebas aprobadas | Revisión anterior a las ampliaciones finales |
| Regresiones posteriores PostgreSQL | 68 aprobadas; luego dos de disponibilidad de tablas | Ejecuciones separadas y parcialmente solapadas |
| Unitarias del frontend | 53 aprobadas | `node:test`; no equivale al total de recorridos E2E |

Estos resultados proceden del [registro de desarrollo](docs/development.md), no de una ejecución realizada al leer este documento.
No se suman como pruebas únicas ni se traducen a un porcentaje de cobertura. El número actual puede cambiar al incorporar casos.
Las ejecuciones citadas conservaron dos avisos de deprecación del cliente de pruebas; no se ocultaron como fallos del proyecto.
Registra siempre revisión, entorno, comandos, resultado y omisiones de una nueva entrega; comparte diagnósticos sin secretos ni datos de trabajo.
