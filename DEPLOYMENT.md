# Despliegue y operación de ONCE

Esta guía reúne el primer despliegue, las tareas operativas, la configuración de referencia y las decisiones de recuperación. El destino soportado es Docker Compose en un equipo local o un servidor Linux. No presupone infraestructura cloud ni un despliegue remoto ya creado.

**Estado actual:** publicar código en `main` no despliega ONCE ni ejecuta CI automáticamente. [El flujo existente](.github/workflows/ci.yml) se inicia manualmente; el ejemplo por `push` al final es una propuesta opcional que no está instalada.

## Aprender: preparar una instalación

Necesitas Docker Engine con Compose, Python 3.12 para los asistentes y espacio para imágenes, base de datos, medios y copias. En Windows local utiliza Docker Desktop; para un servidor público añade NGINX, un dominio y un certificado TLS con renovación configurada.

Desde la raíz del código, en una instalación **nueva**:

```sh
python3 -m src.configure
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
```

En Windows sustituye `python3` por `python`. Para trasladar datos existentes, restaura primero en una base vacía: arrancar la API crea el esquema y bloquea esa restauración. Sigue [transferencia entre equipos](docs/deployment/transfer.md).

### Equipo local y red local

La configuración habitual escucha en `127.0.0.1:80`; abre `http://localhost/`. El asistente prepara las credenciales locales. Consulta el [manual local](docs/deployment/local.md) si el motor Docker no arranca.

Para acceso HTTP desde **una LAN de confianza**, configura `FRONTEND_BIND=0.0.0.0`, `FRONTEND_PORT=80` y `COOKIE_SECURE=false` en `.env`; limita el firewall a esa subred y reconstruye el servicio. No abras el router a Internet ni publiques los puertos de PostgreSQL o pgAdmin.

### Servidor Linux con HTTPS

Prepara una copia del repositorio y su `.env` propio; el ejemplo opcional de automatización utiliza `/srv/once`. Configura allí:

```dotenv
FRONTEND_BIND=127.0.0.1
FRONTEND_PORT=8080
VITE_API_URL=/api
COOKIE_SECURE=true
CORS_ORIGINS=https://once.example.com
API_FOOTBALL_KEY=
```

Sustituye el dominio y guarda la clave del proveedor únicamente en `.env`, con permisos `600`. No uses variables `VITE_` para secretos. Instala NGINX en el host: recibe 80/443, redirige HTTP a HTTPS y reenvía a `127.0.0.1:8080` conservando `/api` y las rutas profundas.

El [manual completo de servidor](docs/deployment/server.md) contiene la configuración TLS, las cabeceras y la excepción de buffering para `/api/public/changes`. Valida con `nginx -t` antes de recargar. El certificado debe existir antes de habilitar su bloque TLS.

```sh
docker compose up --build -d --wait
curl --fail http://127.0.0.1:8080/api/health
curl --fail https://once.example.com/api/health
```

Comprueba desde otro equipo inicio/cierre de sesión, cookie `Secure`, permisos de cada rol, recarga de rutas y escudos. Comprueba SSE según el manual de servidor; una conexión abierta que alcanza el límite de tiempo de curl no equivale por sí sola a un fallo.

## Referencia: qué se despliega

| Componente | Responsabilidad y exposición |
| --- | --- |
| `frontend` | React servido por NGINX; mismo origen para web y `/api`. |
| `api` | FastAPI; ejecuta migraciones al arrancar; puerto del host `127.0.0.1:8000`. |
| `worker` | Procesa sincronizaciones compartidas; sin puerto público. |
| `db` | PostgreSQL 15; accesible por la red interna de Compose. |
| `pgadmin` | Perfil opcional `admin`; solo `127.0.0.1:5050`. |
| NGINX exterior | Solo en publicación HTTPS; certificado y proxy en el host. |

Compose conserva `name: vertice` para reutilizar `vertice_postgres_data` y `vertice_media_data`. El nombre comercial y la carpeta pueden ser ONCE; no cambies la identidad de Compose ni ejecutes `down -v` sobre la instalación conservada.

Consulta [.env.example](.env.example) y [docker-compose.yml](docker-compose.yml) para los valores vigentes. API y trabajador comparten clave y medios; los visitantes leen PostgreSQL, no generan una consulta al proveedor por visita. La instalación Free verificada permite temporadas 2022–2024; no implica datos actuales en directo. El [manual de automatización](docs/automation.md) explica cobertura, presupuesto y pausa general.

## Cómo operar: copias, actualización y restauración

Antes de actualizar, pausa la automatización desde el panel y establece una ventana sin ediciones. Espera a que los trabajos activos terminen; detén el trabajador y conserva la API en ejecución para copiar los medios.

```sh
docker compose stop worker
python3 -m scripts.backup --include-media --directory /srv/once-backups
git rev-parse HEAD
```

El asistente produce `.dump`, manifiesto `.json` con SHA-256 y `.media.tar`; comprueba que PostgreSQL puede leer el archivo. Conserva los tres fuera del servidor, junto con la revisión del código. Respalda `.env` por un canal privado separado. Una copia en el mismo disco no protege de la pérdida del host.

Para una actualización manual, selecciona una revisión revisada del repositorio, conserva las imágenes anteriores y ejecuta:

```sh
docker compose build api frontend
docker compose up --no-build -d --wait
docker compose ps
curl --fail http://127.0.0.1:8080/api/health
docker compose logs --tail=100 api worker
```

Usa el puerto 80 en la instalación local predeterminada. Verifica también HTTPS y los flujos de usuario antes de reanudar la automatización. No ejecutes limpieza de imágenes o volúmenes durante esta ventana.

### Ensayar o recuperar una copia

En **otro destino vacío**, con el código correspondiente y `.env` configurado, inicia únicamente la base. Sustituye la ruta siguiente por el archivo real y conserva a su lado manifiesto y medios:

```sh
docker compose up -d db --wait
docker compose build api
python3 -m scripts.restore_backup /srv/once-backups/once-FECHA.dump --include-media
docker compose up --build -d --wait
```

La restauración exige API y trabajador detenidos, valida la huella, rechaza bases con tablas y usa una transacción para PostgreSQL. Valida los archivos de medios antes de extraerlos; la copia debe proceder de una fuente de confianza. La sincronización restaurada queda pausada y los trabajos antiguos se cancelan para impedir su repetición inadvertida.

Los asistentes aceptan `--compose-file RUTA` para un entorno independiente. Si ensayas en el mismo host, prepara expresamente otros volúmenes, identidad y puertos; copiar la carpeta sin cambiar estos elementos reutiliza la instalación original. Revisa el resultado antes de apuntar NGINX al destino restaurado.

### Recuperar una actualización fallida

Detén el trabajador, conserva logs, copia y revisión anterior. No borres volúmenes. Un estado saludable de HTTP no demuestra que una migración sea compatible hacia atrás: consulta las revisiones Alembic y el cambio de esquema antes de decidir.

Si el esquema admite el código anterior, vuelve a esa revisión y a sus imágenes conservadas; comprueba salud y funcionalidad antes de reanudar. Si no lo admite, restaura la copia previa en un destino vacío, verifica allí y cambia el servicio hacia ese destino. Reconcilia las escrituras posteriores a la copia antes del cambio: no deben desaparecer silenciosamente.

ONCE no aplica un downgrade destructivo automático. Un fallo de despliegue tampoco autoriza restaurar sobre producción. Conserva el destino fallido hasta terminar el diagnóstico y la recuperación.

## Referencia: integración continua actual

El flujo `Integracion Continua ONCE` usa `workflow_dispatch`, `permissions: contents: read` y concurrencia por flujo/referencia con `cancel-in-progress: true`. Una nueva ejecución manual de la misma referencia puede cancelar la anterior.

| Trabajo | Límite | Validación |
| --- | --- | --- |
| `pruebas-api` | 15 min | Python 3.12; Ruff y formato; enlaces; pytest con PostgreSQL 15 desechable; adopción legacy y protección de migraciones. |
| `pruebas-frontend` | 10 min | Node 24; instalación por lockfile; pruebas unitarias; lint y compilación. |
| `prueba-docker` | 20 min | Tras ambos: Compose real; login/cookie/API por NGINX; Playwright; logs y diagnóstico si falla. |

CI genera secretos temporales para sus contenedores y limpia **su entorno desechable** con `down -v`. Los diagnósticos de navegador duran tres días. No utiliza secretos de producción ni despliega al servidor. Ejecuta esta validación antes de una entrega; evita cadenas de publicaciones pequeñas solo para corregir el flujo.

## Explicación y ejemplo: despliegue opcional desde un push

El siguiente archivo YAML completo es una **alternativa futura**, no una descripción del flujo instalado. Añadirlo iniciaría validación con cada `push` a `main`; el despliegue requiere habilitación expresa. Mantén además las pruebas Docker y de navegador del flujo actual antes de aprobar una entrega: este ejemplo no las duplica.

Primero verifica la disponibilidad de revisores obligatorios en el repositorio privado. Según la documentación vigente, Free permite entornos solo en repositorios públicos; Pro y Team permiten entornos privados, pero sus revisores obligatorios siguen limitados a repositorios públicos. No se presupone que esta cuenta tenga esa protección. Si no está disponible, conserva despliegues manuales y deja `ENABLE_SSH_DEPLOY` sin activar. [Disponibilidad y protección de entornos](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

Solo después de confirmar esa disponibilidad, crea `production`, restringe sus ramas a `main` y configura revisores obligatorios. Declarar `environment` en YAML no crea una aprobación ni configura sus reglas.

Define en `production` las variables fijas `DEPLOY_HOST` y `DEPLOY_USER`, y los secretos `DEPLOY_SSH_KEY` y `DEPLOY_KNOWN_HOSTS`. Este último debe contener la clave del servidor verificada por un canal de confianza; no se obtiene con un escaneo durante el despliegue. La llave SSH se dedica a ese destino y el usuario dispone de acceso Docker, Python 3.12 y `flock`.

Prepara previamente `/srv/once` con instalación saludable, `.env` privado, puerto interno 8080 y acceso Git de solo lectura al repositorio privado mediante credencial propia del servidor. Reserva `/srv/once-backups` con permisos privados. El árbol debe estar limpio. Antes de aprobar, pausa la automatización y bloquea ediciones durante la ventana; tras verificar el despliegue, reanúdala desde el panel.

Activa la variable **del repositorio** `ENABLE_SSH_DEPLOY=true` solo después de verificar esas condiciones. Las acciones se fijan a revisiones completas; el servidor solo acepta un SHA de la historia publicada en `main`. Las imágenes base actuales siguen usando etiquetas: esto no promete compilaciones idénticas ni un registro de imágenes ya provisionado. [Sintaxis de flujos](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) y [seguridad de acciones](https://docs.github.com/en/actions/reference/security/secure-use).

```yaml
name: Entrega opcional ONCE
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: once-production
  cancel-in-progress: false
jobs:
  validar:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    services:
      db:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: ci_only
          POSTGRES_DB: vertice_test
        ports: [5432:5432]
        options: >-
          --health-cmd "pg_isready -U postgres -d vertice_test"
          --health-interval 5s --health-timeout 5s --health-retries 10
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5
        with:
          python-version: '3.12'
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4
        with:
          node-version: '24'
      - env:
          TEST_DATABASE_URL: postgresql://postgres:ci_only@localhost:5432/vertice_test
          DATABASE_URL: postgresql://postgres:ci_only@localhost:5432/vertice_test
        run: |
          pip install -r requirements-dev.txt
          python -m ruff check src tests scripts
          python -m ruff format --check src tests scripts
          python -m scripts.check_links
          python -m pytest -q
          python -m scripts.migration_smoke
      - working-directory: frontend
        run: |
          npm ci
          npm test
          npm run lint
          npm run build
  desplegar:
    needs: validar
    if: github.ref == 'refs/heads/main' && vars.ENABLE_SSH_DEPLOY == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: production
    env:
      RELEASE_SHA: ${{ github.sha }}
      DEPLOY_HOST: ${{ vars.DEPLOY_HOST }}
      DEPLOY_USER: ${{ vars.DEPLOY_USER }}
      DEPLOY_SSH_KEY: ${{ secrets.DEPLOY_SSH_KEY }}
      DEPLOY_KNOWN_HOSTS: ${{ secrets.DEPLOY_KNOWN_HOSTS }}
    steps:
      - name: Copiar, actualizar y comprobar el destino aprobado
        shell: bash
        run: |
          set -euo pipefail
          [[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]
          [[ "$DEPLOY_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]]
          [[ "$DEPLOY_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]
          umask 077
          key=$(mktemp); hosts=$(mktemp)
          trap 'rm -f "$key" "$hosts"' EXIT
          printf '%s\n' "$DEPLOY_SSH_KEY" > "$key"
          printf '%s\n' "$DEPLOY_KNOWN_HOSTS" > "$hosts"
          ssh -i "$key" -o BatchMode=yes -o IdentitiesOnly=yes \
            -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$hosts" \
            "$DEPLOY_USER@$DEPLOY_HOST" "bash -s -- $RELEASE_SHA" <<'REMOTE'
          set -euo pipefail
          cd /srv/once
          umask 077
          mkdir -p .local/releases
          exec 9>.local/deploy.lock
          flock -n 9
          git diff --quiet
          git diff --cached --quiet
          test -z "$(git ls-files --others --exclude-standard)"
          release=$1
          git fetch --no-tags origin main
          git merge-base --is-ancestor "$release" FETCH_HEAD
          previous=$(git rev-parse HEAD)
          printf '%s\n' "$previous" > ".local/releases/$release.previous"
          for service in api frontend; do
            container=$(docker compose ps -q "$service")
            image=$(docker inspect --format='{{.Image}}' "$container")
            docker image tag "$image" "once-$service:$previous"
          done
          trap 'docker compose stop worker || true' ERR
          docker compose stop worker
          python3 -m scripts.backup --include-media --directory /srv/once-backups
          git checkout --detach "$release"
          docker compose config --quiet
          docker compose build api frontend
          docker compose up --no-build -d --wait --wait-timeout 180
          curl --fail --retry 3 http://127.0.0.1:8080/api/health
          REMOTE
```

El ejemplo conserva las imágenes anteriores como `once-api:SHA` y `once-frontend:SHA`, registra la revisión y realiza una copia antes del cambio. Un fallo deja el trabajador detenido para revisión; no restaura datos ni revierte migraciones automáticamente. Comprueba también el dominio HTTPS desde fuera del host antes de reabrir ediciones.

Para volver a imágenes conservadas, primero confirma compatibilidad del esquema, selecciona la revisión anterior y etiqueta sus imágenes como `vertice-api` y `vertice-frontend`; levanta con `--no-build`. Si falta compatibilidad, sigue la restauración en destino vacío. Protege el acceso Docker como acceso administrativo al servidor.

## Límites y mantenimiento

Esta topología tiene un único servidor; no incorpora alta disponibilidad, métricas centralizadas ni un SLA. Supervisa salud, disco, certificados, copias verificadas y presupuesto de fuentes. Ensaya recuperación antes de necesitarla. Revisa esta guía cuando cambien Compose, puertos, migraciones, scripts de copia o el flujo de CI.
