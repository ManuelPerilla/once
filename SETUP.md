# Instalación y desarrollo local de ONCE

[Inicio](README.md) · [Contexto](CONTEXT.md) · [Arquitectura](ARCHITECTURE.md) · [Pruebas](TESTING.md) · [Despliegue](DEPLOYMENT.md) · [Diagnóstico](TROUBLESHOOTING.md) · [Contribuir](CONTRIBUTING.md)

La ruta habitual es **Docker Compose**: ejecuta PostgreSQL, API, trabajador y frontend con la configuración del proyecto. La ruta manual permite desarrollar backend y frontend por separado, usando una instancia PostgreSQL de desarrollo. No es necesario contratar una fuente externa para arrancar la aplicación.

## 1. Requisitos y versiones

| Herramienta | Referencia del repositorio | Necesaria para |
| --- | --- | --- |
| Docker Engine/Desktop y Compose | Plugin `docker compose` con `--wait`; 5.5.1 comprobado, mínimo no fijado | Ruta Docker |
| Python | `3.12`, usado por Docker y CI | Configurar secretos; backend manual y utilidades |
| PostgreSQL | `15`, imagen `postgres:15-alpine` | Persistencia; instalación nativa solo en ruta manual |
| Node.js | `24`, imagen `node:24-alpine` | Frontend manual; Docker lo incluye al compilar |
| FastAPI / Uvicorn | `0.141.1` / `0.52.4` | Instalados desde `requirements.txt` |
| SQLModel / SQLAlchemy / Alembic | `0.0.42` / `2.0.52` / `1.20.0` | Instalados desde `requirements.txt` |
| React / React DOM | Rango `^19.2.8`; lock `19.3.0` | Instalados mediante `npm ci` |
| Vite | Lock `8.3.0` | Desarrollo y compilación web |
| NGINX | Etiqueta móvil `nginx:alpine` | Solo imagen frontend; no requiere instalación anfitriona |

Python tiene dependencias fijadas en [requirements.txt](requirements.txt); desarrollo añade [requirements-dev.txt](requirements-dev.txt). JavaScript se resuelve con [package-lock.json](frontend/package-lock.json). Las imágenes fijan familia o versión mayor, no digest ni parche exacto. Una actualización de dependencias debe incluir su verificación; no sustituya `npm ci` por una actualización indiscriminada.

Compruebe `docker version` y `docker compose version`: Docker Desktop instalado pero con el motor detenido no basta. La primera compilación necesita acceso a los registros y paquetes externos. Puertos habituales: `80` para ONCE, `8000` para la API local y `5173` para Vite.

## 2. Primera instalación con Docker

Obtenga una copia completa del repositorio y abra una terminal en la carpeta `once`. Si ya tiene una base y archivos de medios, siga primero [transferencia](docs/deployment/transfer.md); una instalación nueva no recupera automáticamente esos datos.

**PowerShell**, con Python 3.12 instalado:

```powershell
Set-Location C:\ruta\once
py -3.12 -m src.configure
```

**POSIX**, desde la misma raíz del código:

```sh
cd /ruta/once
python3.12 -m src.configure
```

El asistente solicita usuario y contraseña administrativa, confirma la contraseña y genera `.env`. Guarda un hash de acceso, una clave de firma aleatoria y la contraseña de PostgreSQL. En una base nueva puede generar esta última; si conserva un volumen existente, debe introducir la contraseña que ya utiliza. No muestra los secretos en la salida y se niega a sobrescribir un `.env` existente.

Después, estos comandos sirven en ambas terminales:

```sh
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
```

El primer comando valida la configuración sin imprimir su contenido expandido. El arranque aplica migraciones antes de servir la API y espera las comprobaciones de salud. El trabajador reutiliza la imagen backend local; no requiere publicar esa imagen en un registro.

| Dirección predeterminada | Resultado esperado |
| --- | --- |
| [http://localhost/](http://localhost/) | Acceso a la administración con el usuario configurado |
| [http://localhost/explore](http://localhost/explore) | Experiencia pública con datos locales |
| [http://localhost/api/health](http://localhost/api/health) | API responde y ejecuta `SELECT 1` contra su base |
| [http://localhost:8000/docs](http://localhost:8000/docs) | Documentación interactiva desde el equipo anfitrión |

`/explore?demo=1` activa expresamente datos de demostración; esa pantalla no acredita una importación real. Una base vacía recibe el catálogo inicial del proyecto. Los datos de su instalación anterior requieren una copia/restauración, y las fuentes externas requieren perfiles de importación.

El [handler de salud](src/api/routes/reading.py) no es una respuesta estática: abre la sesión y consulta la base. Su éxito no acredita las migraciones completas, la integridad del catálogo, el trabajador ni la disponibilidad de una fuente externa.

## 3. Configuración: qué se necesita y dónde se utiliza

Edite `.env` localmente. No lo añada a Git, no pegue claves en incidencias y no copie sus valores al frontend. Compose carga ese archivo para interpolar las variables declaradas en `docker-compose.yml`; **no transmite automáticamente cada variable a cada contenedor**.

| Variable mínima | Propósito | Si falta o es incorrecta |
| --- | --- | --- |
| `SECRET_KEY` | Firma de sesión; mínimo 32 bytes aleatorios | Compose rechaza ausencia; la API rechaza claves cortas al arrancar |
| `ADMIN_USERNAME` | Cuenta administrativa de configuración | Ausencia impide el arranque; un usuario distinto no autentica esa cuenta |
| `ADMIN_PASSWORD_HASH` | Hash PBKDF2 generado por ONCE | Ausencia o formato inválido impiden iniciar la API; no acepta contraseña plana |
| `POSTGRES_PASSWORD` | Contraseña de la base | Compose exige valor; uno distinto al del volumen impide conectar. Python manual puede usar `DATABASE_URL` |

| Variable opcional | Valor o alcance | Síntoma de configuración incompatible |
| --- | --- | --- |
| `COOKIE_SECURE` | Código/Compose: `true`; asistente local: `false` | Valor distinto de `true/false`: falla el arranque. Una cookie segura necesita HTTPS para el acceso ordinario |
| `CORS_ORIGINS` | En desarrollo: `localhost:5173` y `127.0.0.1:5173` con esquema HTTP | Un origen omitido no recibe autorización CORS; el proxy del mismo origen no la necesita |
| `FRONTEND_BIND` / `FRONTEND_PORT` | `127.0.0.1` / `80` en Compose | IP inválida o puerto ocupado: frontend no publica su acceso |
| `API_FOOTBALL_KEY` | Vacía; secreto exclusivo de API y trabajador | Vacía: fuente no configurada; rechazada: comprobación/importación falla. La lectura local sigue disponible |
| `WIKIDATA_USER_AGENT` | Identificación del cliente externo | Sin personalizar usa el valor predeterminado; el adaptador no certifica que la fuente lo acepte |
| `SYNC_RETENTION_DAYS` | `30`, mínimo efectivo `7` | Valor no entero: falla la limpieza del trabajador; valores menores se ajustan a siete días |
| `DATABASE_URL` | Prioritaria en Python; Compose no la transmite | URL inválida impide crear el motor; una URL válida a otra base dirige allí migraciones y escrituras |
| `POSTGRES_HOST` / `POSTGRES_PORT` | Python: `localhost` / `5432`; Compose: `db` / `5432` | Host inaccesible o puerto incorrecto: no conecta; puerto no entero: falla la configuración |
| `POSTGRES_USER` / `POSTGRES_DB` | `postgres` / `vertice_db`; Compose fija estos valores | Usuario sin acceso o base inexistente: conexión/migración falla |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | API: `5` / `3`; trabajador Compose: `2` / `1` | Valores no enteros impiden crear el motor; agotamiento del pool espera hasta diez segundos |
| `ONCE_MEDIA_DIR` | Python: `.local/media`; Compose: `/app/.media` | Directorio sin permisos: puede impedir iniciar la API o guardar recursos |
| `ROOT_PATH` | Python: vacío; Compose: `/api` | Prefijo equivocado: enlaces generados y documentación apuntan a rutas incorrectas |
| `VITE_API_URL` | `/api`, público y fijado al compilar | URL equivocada: frontend consulta otro destino; cambiarla sin reconstruir no cambia el paquete servido |
| `API_PROXY_TARGET` | Vite: `http://127.0.0.1:8000`; ajuste en `frontend/.env.local` | Backend inaccesible: el proxy de desarrollo devuelve errores de conexión |
| `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` | Solo perfil opcional `admin` | Credenciales equivocadas impiden su acceso; API y trabajador no dependen de pgAdmin |

Estas diferencias proceden de [configuración y acceso](src/security.py), [conexión SQL](src/database.py), [retención](src/sync/maintenance.py), [Vite](frontend/vite.config.js) y [Compose](docker-compose.yml). Una variable omitida con valor predeterminado no equivale a un fallo.

Referencia ampliada para entender el archivo; **conserve los valores generados** en sus cuatro primeras variables. Los marcadores entre ángulos no son credenciales utilizables. Las variables de conexión manual no cambian por sí solas el PostgreSQL de Compose.

```dotenv
SECRET_KEY=<conservar-valor-generado>
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<conservar-hash-generado>
POSTGRES_PASSWORD='<conservar-contraseña-de-esta-base>'
COOKIE_SECURE=false
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FRONTEND_BIND=127.0.0.1
FRONTEND_PORT=80
API_FOOTBALL_KEY=
WIKIDATA_USER_AGENT=ONCE/0.2 (instancia local de futbol)
SYNC_RETENTION_DAYS=30
DATABASE_URL=
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_DB=vertice_db
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=3
ONCE_MEDIA_DIR=.local/media
ROOT_PATH=
VITE_API_URL=/api
PGADMIN_DEFAULT_EMAIL=
PGADMIN_DEFAULT_PASSWORD=
```

Un cambio de clave de proveedor requiere recrear API y trabajador: `docker compose up -d --force-recreate --wait api worker`. Un cambio de `VITE_API_URL` requiere reconstruir el frontend. Cambiar `POSTGRES_PASSWORD` en un archivo no cambia la contraseña dentro de una base ya inicializada.

## 4. Desarrollo manual con PostgreSQL

Esta alternativa ejecuta API, trabajador y Vite en terminales independientes. Use una base de desarrollo propia: las migraciones y la edición de datos afectan a la base seleccionada. SQLite en memoria sirve para ciertas pruebas; no sustituye la persistencia, los bloqueos ni la auditoría PostgreSQL de la instalación principal.

Si Docker ya ocupa el puerto `8000`, detenga sus procesos API y trabajador antes de iniciar los manuales: `docker compose stop api worker`. Su frontend Docker queda temporalmente sin API; restablezca la instalación con `docker compose up -d --wait` al terminar. Para cambiar únicamente la interfaz, puede conservar la API Docker y ejecutar solo Vite contra ese puerto, sin preparar otro backend.

### Preparar Python

PowerShell; no necesita cambiar la política de ejecución para activar el entorno:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m src.configure
```

POSIX:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m src.configure
```

Ejecute `src.configure` únicamente cuando todavía no exista `.env`. Para esta ruta, introduzca la contraseña de su PostgreSQL de desarrollo cuando el asistente la solicite. Las dependencias de desarrollo incluyen todas las de ejecución.

### Crear y arrancar un PostgreSQL 15 independiente

1. Instale los binarios de PostgreSQL 15, incluidos `initdb`, `pg_ctl`, `pg_isready` y `createdb`. Añada su carpeta `bin` al `PATH`; en Windows suele ser `C:\Program Files\PostgreSQL\15\bin`. Use una terminal de usuario normal, no `root`. Compruebe que `initdb --version` indica **15**.
2. Cree una copia privada de configuración si aún no existe: PowerShell, `if (-not (Test-Path .env.manual)) { Copy-Item .env .env.manual }`; POSIX, `test -e .env.manual || cp .env .env.manual`. Edite **solo `.env.manual`**: deje `DATABASE_URL=` y `API_FOOTBALL_KEY=` vacías y asigne a `POSTGRES_PASSWORD` una contraseña para esta base nueva. Conserve las claves administrativas generadas. El patrón `.env.*` la excluye de Git.
3. Compruebe que el puerto `15432` está libre. Los comandos siguientes crean **otro clúster** dentro de `.local/postgres-dev15`; no administran el servicio PostgreSQL del sistema ni los volúmenes de Compose.

```sh
initdb -D .local/postgres-dev15 -U postgres --auth=scram-sha-256 --pwprompt
pg_ctl -D .local/postgres-dev15 -l .local/postgres-dev15.log -o "-h 127.0.0.1 -p 15432" -w start
pg_isready -h 127.0.0.1 -p 15432
createdb -h 127.0.0.1 -p 15432 -U postgres -W once_dev
```

4. En `initdb`, introduzca dos veces la contraseña escrita en `.env.manual`; `createdb` vuelve a solicitarla sin mostrarla. `pg_isready` debe indicar que acepta conexiones. Si falla un paso, consulte el registro y deténgase antes del siguiente; no reutilice otra base como sustituto.
5. **`initdb` y `createdb` se ejecutan solo la primera vez.** Si ya existe este directorio o base, compruebe su identidad; no los borre para repetir la instalación. En arranques posteriores use únicamente el comando `pg_ctl ... start`; para detener este clúster, `pg_ctl -D .local/postgres-dev15 -m fast -w stop`. Sus archivos quedan conservados.

### Arrancar la API y el trabajador

**Uvicorn no carga `.env` automáticamente.** Los ayudantes `scripts.dev api` y `scripts.dev worker` cargan el entorno de forma literal y aceptan `--env-file RUTA`; las variables del proceso prevalecen sobre el archivo. No use `eval`, `source .env` ni una concatenación del archivo como órdenes de terminal. Una `DATABASE_URL` explícita prevalece sobre los componentes; no la deje apuntando a otra instalación.

PowerShell, en la terminal de la API:

```powershell
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '15432'
$env:POSTGRES_DB = 'once_dev'
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m scripts.dev api --env-file .env.manual
```

POSIX, en la terminal de la API:

```sh
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=15432
export POSTGRES_DB=once_dev
unset DATABASE_URL
.venv/bin/python -m scripts.dev api --env-file .env.manual
```

El ayudante aplica migraciones y después arranca Uvicorn en `127.0.0.1:8000`. En una **segunda terminal**, configure los mismos componentes y ejecute `python -m scripts.dev worker` con el Python de `.venv` de su plataforma. Un `POSTGRES_HOST=db` copiado de Docker no identifica normalmente la base desde el anfitrión; use el host local explícito.

| Segunda terminal, después de repetir las variables | Orden del trabajador |
| --- | --- |
| PowerShell | `.\.venv\Scripts\python.exe -m scripts.dev worker --env-file .env.manual` |
| POSIX | `.venv/bin/python -m scripts.dev worker --env-file .env.manual` |

### Arrancar el frontend

Desde una tercera terminal, con Node.js 24 en `PATH`:

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Abra la dirección que indique Vite, normalmente `http://127.0.0.1:5173`. Su proxy transforma `/api/...` en solicitudes a `http://127.0.0.1:8000/...`. No hace falta instalar NGINX para este modo. `VITE_*` es configuración pública: nunca coloque `API_FOOTBALL_KEY`, contraseñas o claves de sesión bajo ese prefijo.

## 5. Primera carga de datos y verificación

1. Inicie sesión y compruebe que la página de automatización muestra el trabajador disponible.
2. En Docker, prepare el piloto abierto con `docker compose exec -T api python -m src.sync.bootstrap`; crea perfiles pausados sin duplicarlos. La administración permite configurar los perfiles también al ejecutar el backend manualmente.
3. En **Datos → Automatización**, revise selección, procedencia y modo. Activar una tarea no verifica por sí mismo el acceso a una temporada externa.
4. Para API-Football, guarde la clave solamente en `.env`, recree API/trabajador y use la comprobación de cuenta. Seleccione los años permitidos y prepare calendarios, clasificaciones y detalles progresivos.
5. Confirme los resultados en la experiencia pública y consulte incidencias. Una cuenta gratuita puede agotar su cuota mientras la lectura local continúa funcionando.

La cuenta Free comprobada durante el desarrollo permitió 2022–2024 y rechazó 2026 y los detalles con varios IDs. La comprobación de su cuenta es la autoridad para su instalación; no se promete cobertura actual por el nombre de un perfil. El procedimiento detallado está en [automatización](docs/automation.md).

```sh
docker compose ps
docker compose logs --tail 80 api worker
docker compose exec -T api python -m src.sync.worker --health
```

Estos comandos comprueban servicios y actividad; no prueban por sí solos la integridad completa del catálogo. Para verificaciones reproducibles, use [TESTING.md](TESTING.md) y una base desechable, nunca la base de trabajo.

El atajo `scripts.dev test-api` solo acepta SQLite en memoria o una base PostgreSQL cuyo nombre termine en `_test`; rechaza archivos SQLite, incluso si se nombran como pruebas. Los atajos QA verifican proyecto `once-qa`, puerto `18080`, base interna `db`, medios y volúmenes propios, y rechazan conexiones, montajes o redes que puedan dirigir las pruebas a la instalación de trabajo. Estas guardas pertenecen al ayudante; no convierten cualquier invocación directa de pytest en segura.

El [Makefile](Makefile) ofrece atajos opcionales como `make up`, `make api`, `make worker` y `make web`. Use `make PYTHON=.venv/bin/python api` para elegir el intérprete en POSIX; en Windows no hace falta instalar GNU Make: los mismos pasos están disponibles mediante `python -m scripts.dev help` y sus tareas.

## 6. Red local, parada y continuidad

Para compartir la interfaz en su LAN por HTTP, configure `FRONTEND_BIND=0.0.0.0` y `COOKIE_SECURE=false`; aplique `docker compose up -d --no-deps --wait api frontend`. Abra `http://IP_DEL_EQUIPO/` desde el otro dispositivo y añada el puerto si es distinto de 80. El proxy conserva el mismo origen; `CORS_ORIGINS` solo necesita ajustes si separa el origen del cliente y la API. Permita el puerto elegido en el firewall de la red privada; no necesita publicar API ni PostgreSQL. Vuelva a `127.0.0.1` para restringir el acceso al anfitrión.

`docker compose down` detiene la instalación conservando volúmenes. **No utilice `--volumes` sobre la instalación de trabajo.** En modo manual, detenga cada proceso con `Ctrl+C`; PostgreSQL y sus archivos conservan los datos. Mantenga la misma configuración cuando reinicie.

Antes de trasladar o actualizar una instalación con datos, prepare una copia de PostgreSQL y medios según [DEPLOYMENT.md](DEPLOYMENT.md). La publicación en Internet requiere dominio, HTTPS y cookies seguras; abrir el puerto de desarrollo no reemplaza ese procedimiento. Para fallos de arranque, permisos o conexión, continúe en [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
