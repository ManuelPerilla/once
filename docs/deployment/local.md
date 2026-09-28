# Despliegue local con Docker

## Requisitos

- Docker Desktop en Windows/macOS, o Docker Engine con Compose en Linux.
- Puertos 80 y 8000 libres; `FRONTEND_PORT` permite cambiar el primero.
- Python 3.12 para generar configuración, copias y entornos de prueba. No hace falta instalar las dependencias Python para esos asistentes.
- Internet para descargar imágenes y dependencias en la primera compilación. Las importaciones externas también requieren conexión.

El código puede estar en una carpeta llamada `once`. Ejecuta los comandos desde su raíz. En Linux/macOS usa `python3` si `python` no está disponible.

## Primera instalación

1. Copia el código completo o clona tu repositorio.
2. Si traes una base existente, utiliza primero el [manual de transferencia](transfer.md).
3. Si no existe `.env`, ejecuta:

```sh
python -m src.configure
```

El asistente genera secretos y guarda un hash de la contraseña administrativa. Para HTTP local se usa `COOKIE_SECURE=false`. No sobrescribas un `.env` existente ni cambies la contraseña de una base ya inicializada como forma de recuperar acceso.

```sh
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
```

Abre [el administrador](http://localhost/) y [la experiencia pública](http://localhost/explore). La [demo](http://localhost/explore?demo=1) funciona con datos ficticios sin escribir en PostgreSQL. Windows dispone además de [iniciar-once.cmd](../../iniciar-once.cmd).

## Servicios y configuración

| Servicio | Función | Acceso desde el equipo |
| --- | --- | --- |
| frontend | NGINX, React y proxy `/api` | `127.0.0.1:80`, configurable |
| api | FastAPI y migraciones al arrancar | `127.0.0.1:8000` |
| worker | Cola durable, cuotas e importación en segundo plano | Sin puertos públicos |
| db | PostgreSQL 15 y datos persistentes | Solo la red de Compose |
| pgadmin | Administración opcional | `127.0.0.1:5050` |

[.env.example](../../.env.example) explica las variables. API-Football es opcional; Wikidata no requiere clave. `WIKIDATA_USER_AGENT` identifica la instalación. `VITE_API_URL` cambia una opción de compilación: requiere reconstruir el frontend; para la instalación normal conserva `/api`.

Para pgAdmin, configura su correo y contraseña y ejecuta `docker compose --profile admin up -d pgadmin`. Conecta con servidor `db`, puerto `5432`, usuario `postgres` y base `vertice_db`.

### Acceso desde otros equipos de la red local

Desde la raíz, con Python 3.12 y Docker funcionando:

```sh
python -m scripts.network lan
```

En Windows también puedes abrir [compartir-once.cmd](../../compartir-once.cmd). El asistente configura una instalación nueva si falta `.env` y la terminal es interactiva; conserva los secretos existentes. Construye API y frontend con caché y muestra las IPv4 privadas candidatas del equipo. En una instalación nueva arranca el conjunto; en una existente adapta API/frontend con su dependencia de base, sin cambiar deliberadamente el estado del trabajador.

Abre la dirección mostrada desde otro equipo conectado a la misma red: `http://IP_DEL_EQUIPO/explore` para explorar o `http://IP_DEL_EQUIPO/` para iniciar sesión. El marcador representa la dirección descubierta en tu ejecución. Usa `lan --port 8080` para cambiar el puerto y añádelo a la dirección. No necesitas fijar la IP del anfitrión en el código: `/api` mantiene cliente y API bajo el mismo origen.

Consulta con `python -m scripts.network status` y vuelve al acceso exclusivo del anfitrión con `python -m scripts.network local`. Los equivalentes son `python -m scripts.dev lan`, `local` y `network-status`, o `make lan`, `make local` y `make network-status`. `--dry-run` permite revisar el cambio; `--no-build` solo debe usarse con imágenes ya actualizadas.

Docker y el anfitrión deben permanecer encendidos. Si el firewall impide conectarse, Windows admite `lan --firewall` desde una terminal administradora: crea una regla propia TCP, limitada al puerto seleccionado y a `LocalSubnet`, para cualquier perfil de red. `local --firewall` retira esa regla. Sin la opción, el asistente no modifica el firewall. No publica PostgreSQL ni la API en la LAN; ambos modos mantienen `COOKIE_SECURE=false` porque utilizan HTTP.

Una respuesta HTTP local correcta no demuestra acceso desde otro dispositivo. Consulta el [manual de red](network.md) para restricciones de router, permisos, recuperación y cambio de equipo. Dos clones en el mismo Docker no obtienen volúmenes independientes por estar en carpetas distintas; el asistente detiene la operación si los contenedores pertenecen a otra carpeta. Para llevar datos a otra máquina utiliza [transferencia](transfer.md). Este asistente no configura un despliegue HTTPS público.

## Actualizar, detener y volver atrás

Antes de una actualización relevante, pausa la automatización, evita ediciones durante la copia y ejecuta `python -m scripts.backup --include-media`. Registra la revisión del código (`git rev-parse HEAD`; los cambios sin commit deben conservarse por separado). Al actualizar una versión anterior sin volumen de medios, usa la copia sin `--include-media` una última vez.

```sh
docker compose up --build -d --wait
```

Las migraciones se aplican antes de iniciar la API. El seed inserta el conjunto inicial solo cuando no encuentra confederaciones; no rellena automáticamente catálogos existentes. Para detener el conjunto, `docker compose down` conserva el volumen. **No añadas `--volumes` a la instalación de trabajo.**

El trabajador arranca después de la API sana y conserva el estado de pausa guardado. En una base nueva empieza pausado: configura las fuentes desde **Datos → Automatización**. El volumen `media_data` guarda escudos locales y se comparte entre API y trabajador. Consulta el [manual de operación](../automation.md) para cadencia, cuotas, correcciones y roles.

El nombre Compose está fijado en `vertice` para mantener el volumen `vertice_postgres_data` aunque cambies de carpeta. `-p` y `COMPOSE_PROJECT_NAME` pueden sobrescribirlo: no los cambies por accidente. Si se necesita otra instalación independiente en el mismo motor, usa un proyecto distinto y puertos distintos deliberadamente.

### Renombrar la carpeta en Windows

Si Windows indica que la carpeta está en uso, cierra completamente el editor o la aplicación que la mantiene abierta. Desde una terminal situada en la carpeta superior, puedes usar [scripts/renombrar-proyecto.ps1](../../scripts/renombrar-proyecto.ps1):

```powershell
& ./vertice/scripts/renombrar-proyecto.ps1 -Source ./vertice -Name once
```

El script valida ambas rutas y la identidad de Compose; no sobrescribe carpetas existentes ni modifica la base. `-WhatIf` permite comprobar la operación. Después abre `once` como carpeta del proyecto en el editor y ejecuta `docker compose up -d --wait` desde allí. Si desarrollas fuera de Docker, recrea el entorno virtual para actualizar sus rutas locales.

Si una actualización falla, conserva los logs y la copia. Volver al código anterior solo es válido si admite el esquema existente. Si no, restaura la copia previa en una instalación vacía y prueba allí; no hagas un downgrade automático de la base de trabajo.

### Si algo no arranca

```bash
docker compose ps
docker compose logs api --tail=80
docker compose logs worker --tail=80
```

- **Puerto 80 ocupado:** cambia `FRONTEND_PORT=8080` en `.env`, vuelve a ejecutar Compose y abre [localhost:8080](http://localhost:8080).
- **Puerto 5432 ocupado:** el Compose actual no publica PostgreSQL en el anfitrión. Si sigue apareciendo ese error, revisa si conservas un Compose antiguo o un archivo de override.
- **`password authentication failed`:** la contraseña de `.env` no coincide con la del volumen PostgreSQL. Cambiar `.env` no cambia una base ya inicializada. Recupera la contraseña correcta o restablécela dentro de PostgreSQL; no borres el volumen para resolverlo.
- **Login correcto, pero vuelve a pedir sesión:** en HTTP local necesitas `COOKIE_SECURE=false`. En HTTPS debe ser `true`. Aplica los cambios con `docker compose up -d`.

### Docker pide restaurar de fábrica por `sailor-ingest.sock`

Docker Desktop 4.91 puede fallar al reutilizar sus sockets temporales en Windows. El error concreto del registro es `initializing Ingest server` seguido de `rename ... sailor-ingest.sock ... El sistema no tiene acceso al archivo`. También puede afectar a `docker-secrets-engine/engine.sock`. Este [problema está reportado a Docker](https://github.com/docker/desktop-feedback/issues/554).

Para ese error, cierra Docker Desktop con **Quit** y ejecuta desde PowerShell:

```powershell
./scripts/reparar-docker-temporales.ps1
```

El script comprueba que Docker esté cerrado y que las carpetas contengan únicamente los sockets esperados. Conserva las carpetas afectadas con el sufijo `before-once-repair-<fecha>` y crea otras vacías; no elimina nada ni toca los discos WSL o los volúmenes. Después abre Docker Desktop y ejecuta `iniciar-once.cmd`. Puedes revisar la operación previamente añadiendo `-WhatIf`.

Es una recuperación para ese fallo, no una corrección del propio Docker: puede repetirse al reiniciarlo. Si el mensaje es distinto o el script detecta contenido inesperado, conserva los datos y revisa el nuevo error antes de aplicar una restauración.


## Publicación en un servidor

El Compose incluido escucha en loopback por defecto; el acceso LAN se configura en la sección anterior. Para publicarlo en Internet, usa un dominio y un proxy HTTPS del servidor que apunte al frontend local, con `FRONTEND_BIND=127.0.0.1`; conserva PostgreSQL dentro de la red privada. Configura `COOKIE_SECURE=true` y vuelve a comprobar inicio/cierre de sesión a través de HTTPS. El proxy exterior debe permitir las rutas profundas y `/api`.

Hay cuentas con roles, pero no despliegue público automático ni alta disponibilidad configurada. Antes de una publicación externa se debe concretar el servidor, TLS, acceso administrativo, copias fuera del host y monitorización. El proxy exterior debe permitir SSE sin buffering en `/api/public/changes`. El [manual de GitHub](github.md) describe cómo preparar una entrega revisable sin publicar secretos.
