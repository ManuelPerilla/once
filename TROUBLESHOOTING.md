# Resolver problemas en ONCE

Localiza primero la capa que falla: motor Docker, acceso web, PostgreSQL, sesión o fuente de datos.
La instalación conserva información en volúmenes; reiniciar un servicio y borrar sus datos son operaciones distintas.
Esta guía ofrece cinco diagnósticos principales y un procedimiento de recuperación que conserva la evidencia.

**Mapa del proyecto:** [Inicio](README.md) · [Contexto](CONTEXT.md) · [Arquitectura](ARCHITECTURE.md) · [Instalación](SETUP.md) · [Pruebas](TESTING.md) · [Despliegue](DEPLOYMENT.md) · [Contribución](CONTRIBUTING.md).

## Tutorial: delimitar el problema en cinco minutos

Desde la raíz del repositorio, comprueba si el motor responde y qué servicios llegaron a arrancar:

```sh
docker info --format '{{.ServerVersion}}'
docker compose ps
docker compose logs --since 10m --tail 120 db api worker frontend
```

Si Docker no responde, los siguientes comandos de contenedores tampoco ayudarán: empieza por el diagnóstico 1.
Si el motor funciona, anota qué servicio está `unhealthy`, detenido o reiniciándose y la hora del primer error relevante.
Las cuatro piezas habituales son `db`, `api`, `worker` y `frontend`; pgAdmin pertenece a un perfil opcional.
Un worker sano puede estar en pausa deliberada: salud del proceso no significa que deba consultar una fuente.

Comprueba la API mediante el mismo proxy que usa el navegador. Ajusta el puerto si tu configuración usa otro:

```powershell
Invoke-RestMethod http://127.0.0.1/api/health
```

```sh
curl --fail --show-error http://127.0.0.1/api/health
```

No publiques `.env`, la salida completa de `docker compose config`, cookies, tokens ni capturas de credenciales.
Los mensajes que siguen se identifican como texto real del código o como ejemplos ilustrativos; un ejemplo no acredita un incidente ocurrido.

## Referencia rápida: los cinco errores principales

| Diagnóstico | Síntoma | Comprobación | Reparación inicial |
| --- | --- | --- | --- |
| 1. Motor Docker indisponible | No arranca ningún contenedor o Desktop propone restaurar | `docker info`; mensaje exacto de Desktop | Completar arranque/actualización; recuperación reversible solo si coincide el fallo de sockets |
| 2. Web inaccesible o puerto ocupado | Conexión rechazada, frontend ausente o funciona solo en el anfitrión | Salud del frontend, puerto publicado y dirección LAN | Liberar/cambiar el puerto o ajustar bind y firewall de la red local |
| 3. PostgreSQL rechaza acceso o recuperación | API reinicia; autenticación de base falla; restaurador se niega a continuar | Logs de `db`/`api`, base y volumen previstos | Recuperar configuración coherente o restaurar en una instalación vacía |
| 4. Sesión o permisos incorrectos | Login seguido de 401, contraseña rechazada o acción con 403 | Cookie, esquema HTTP/HTTPS, cuenta y rol | Corregir cookie/configuración o acceso autorizado de la cuenta |
| 5. Fuente detenida, limitada o sin cobertura | 429, trabajo en espera o faltan datos recientes | Estado de la fuente, presupuesto, próxima ejecución e incidencias | Respetar la espera y verificar plan, alcance e identidades |

## Cómo resolver 1: Docker no termina de arrancar

Un error del motor antecede a ONCE: recompilar la aplicación no repara un servicio Docker detenido.
Abre Docker Desktop y termina la actualización pendiente; espera a que indique que el motor está listo.
Repite `docker info` una vez antes de intentar arrancar el proyecto.

Ejemplo ilustrativo de un cliente sin motor disponible; el texto concreto depende del sistema:

```text
Cannot connect to the Docker daemon
```

Si Desktop propone restaurar de fábrica, conserva primero el diagnóstico; esa opción puede eliminar los datos de Docker.
El repositorio incluye una recuperación muy concreta para temporales de sockets en Windows, documentada en [Despliegue local](docs/deployment/local.md).
El script solo acepta dos carpetas temporales conocidas, sockets vacíos esperados y ausencia de procesos Docker activos.
No arregla cualquier error de WSL, virtualización, disco o instalación.

Cierra Docker Desktop mediante **Quit**, revisa el caso y simula la operación:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/reparar-docker-temporales.ps1 -WhatIf
```

Si la previsualización corresponde exactamente al fallo documentado, ejecuta el mismo comando sin `-WhatIf`.
La excepción de política se limita a ese proceso y script revisado; no modifica la política global de Windows.
Las carpetas anteriores se conservan con sufijo `before-once-repair-<fecha>`; no se borran discos WSL ni volúmenes.
Si el script rechaza rutas o contenido, detente: sus guardas evitan aplicar una reparación sobre datos inesperados.

Texto real de [scripts/reparar-docker-temporales.ps1](scripts/reparar-docker-temporales.ps1):

```text
Cierra Docker Desktop (Quit) y sus comandos de arranque antes de ejecutar la reparacion.
```

Vuelve a abrir Desktop. Cuando responda el motor, utiliza `docker compose up -d --wait` y comprueba los cuatro servicios.

## Cómo resolver 2: la página no abre o el puerto está ocupado

Comprueba primero `docker compose ps frontend` y `docker compose port frontend 80`.
Si no aparece el puerto esperado, revisa `FRONTEND_PORT` y `FRONTEND_BIND` en tu configuración local sin compartir sus otros valores.
El puerto por defecto es 80 y el bind por defecto es `127.0.0.1`.

Ejemplo ilustrativo de un conflicto de publicación:

```text
Bind for 127.0.0.1:80 failed: port is already allocated
```

En Windows, identifica el proceso que escucha antes de decidir si debe detenerse:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 80 | Select-Object LocalAddress, LocalPort, OwningProcess
```

Puedes elegir `FRONTEND_PORT=8080` y aplicar solo el servicio web:

```sh
docker compose up -d --no-deps --wait frontend
```

Abre después `http://localhost:8080/`; cambiar la variable no modifica una pestaña que conserva el puerto anterior.
Para LAN, usa `FRONTEND_BIND=0.0.0.0` y la IPv4 del adaptador activo del anfitrión; desde otro equipo, `localhost` identifica ese otro equipo.
El firewall debe permitir el puerto TCP del frontend desde la subred prevista. No es necesario exponer PostgreSQL ni abrir la API a la LAN.
El aislamiento de clientes de una red de invitados también puede impedir llegar al anfitrión aunque Docker esté sano.

La interfaz y la API deben conservar el mismo origen mediante `VITE_API_URL=/api` y `ROOT_PATH=/api`.
Un cambio de `VITE_API_URL` requiere reconstruir el frontend porque Vite lo incorpora al compilar.
No uses `CORS_ORIGINS=*` para resolver un puerto cerrado: CORS no abre conexiones ni sustituye al firewall.
Para HTTPS público, sigue [Servidor y proxy](docs/deployment/server.md); el bind LAN no configura TLS ni un despliegue en Internet.

## Cómo resolver 3: PostgreSQL, migraciones o restauración

Un contenedor PostgreSQL puede estar sano mientras la API utiliza una contraseña distinta.
Cambiar `POSTGRES_PASSWORD` en `.env` no cambia la contraseña de un volumen ya inicializado.
Conserva la identidad Compose `vertice`: renombrarla puede conectar el proyecto a otros volúmenes y aparentar una pérdida de datos.

Ejemplo ilustrativo de PostgreSQL; no contiene una credencial real:

```text
FATAL: password authentication failed for user "postgres"
```

Revisa los logs acotados y recupera la configuración privada que corresponde a esa base.
Si necesitas cambiar su contraseña, hazlo mediante un procedimiento PostgreSQL autorizado, actualizando después API y worker conjuntamente.
No regeneres `.env` ni borres el volumen como forma de recuperar acceso.

Cuando PostgreSQL permita generar una copia, guárdala antes de intervenir sobre datos o migraciones:

```sh
python -m scripts.backup --include-media
```

La copia con medios requiere también la API disponible; `python -m scripts.backup` permite respaldar solo PostgreSQL si la API no está operativa.
Una ejecución fallida no es una copia válida. Conserva el `.dump`, su manifiesto `.json` y el `.media.tar` cuando exista.
El SHA-256 verifica integridad respecto al manifiesto; no acredita por sí solo quién produjo la copia.

Texto real de [src/database.py](src/database.py):

```text
Configura DATABASE_URL o POSTGRES_PASSWORD antes de iniciar la API.
```

Ese mensaje indica configuración ausente, no una base corrupta. El arranque normal ejecuta `src.migrate` antes de servir la API.
Si una migración falla, conserva su revisión y error completos, toma una copia y reproduce el caso en un destino independiente.
No edites `alembic_version` ni fuerces un downgrade para ocultar una migración fallida.

Texto real del restaurador cuando el destino no está vacío:

```text
La base ya contiene tablas. Usa una instalación vacía; no se borró nada.
```

Es una protección correcta. El [manual de transferencia](docs/deployment/transfer.md) exige iniciar solo una base vacía, con API y worker detenidos.
La restauración valida el hash, conserva auditoría y deja la automatización pausada antes de retomar las consultas externas.
El ensayo de migración y las pruebas que recrean tablas pertenecen exclusivamente a entornos desechables: consulta [TESTING.md](TESTING.md).

## Cómo resolver 4: login, cookie o rol

Separa los tres resultados: 401 por credenciales o sesión, 403 por permisos y fallo de red antes de recibir respuesta.
En el navegador, revisa el estado de `/api/login` y luego `/api/auth/session`; no copies el contenido de `Set-Cookie`.
Una cookie `HttpOnly` no se consulta mediante JavaScript; puede inspeccionarse en las herramientas del navegador.

Mensajes reales de [autenticación](src/api/routes/auth.py) y [dependencias](src/api/dependencies.py):

```text
Credenciales incorrectas
No autenticado. Falta la cookie o el token de sesión.
Tu cuenta no tiene permiso para esta acción.
```

En HTTP local o LAN se necesita `COOKIE_SECURE=false`; en un servidor HTTPS debe ser `true`.
La excepción de algunos navegadores para localhost no debe confundirse con el comportamiento de una dirección IP por HTTP.
Mantén el resto de atributos existentes: `HttpOnly`, `SameSite=Lax` y `Path=/`.
Las sesiones de `localhost`, una IP y un dominio son distintas; inicia sesión en la dirección que realmente usarás.
La sesión vence a las 24 horas. Desactivar una cuenta o revocar su versión de autenticación invalida sus sesiones.

Los roles son explícitos: auditor lee; editor lee y corrige; operador lee y opera automatización; administrador añade gestión de fuentes y cuentas.
Un operador no obtiene gestión de fuentes por conocer la URL; las vistas previas de proveedores también requieren ese permiso.
Comprueba la cuenta y el rol en administración; no elimines controles del backend para hacer desaparecer un 403.

La configuración de autenticación se carga en caché durante la vida del proceso. Tras cambiarla, recrea la API:

```sh
docker compose up -d --no-deps --wait api
```

Cambiar `SECRET_KEY` invalida las sesiones existentes; no es el primer paso de diagnóstico.
No hay un token CSRF específico ni validación propia de `Origin`/`Referer`: no presentes CORS como una protección completa contra CSRF.
Con frontend y API bajo `/api` del mismo origen, el acceso LAN no requiere ampliar la lista de CORS.

## Cómo resolver 5: cuota, espera o datos que no aparecen

En administración, consulta la conexión de la fuente, cobertura, presupuesto y próxima ejecución antes de repetir una importación.
Una tarea en espera puede estar respetando `Retry-After`, el presupuesto diario, el espaciado de consultas o una dependencia aún no preparada.
Los controles de pausa global y de cada perfil tienen efecto propio; revisar una ficha pública no inicia consultas API-Football.

Mensajes reales del [motor](src/sync/service.py) y de [vistas previas](src/api/routes/providers.py):

```text
Se agotó el presupuesto diario de la fuente.
Se alcanzó el límite por minuto.
La cuenta de la fuente agotó su cuota disponible.
La fuente está en pausa por su cuota. Espera antes de volver a consultar.
```

No confundas 429 con credenciales incorrectas. Las consultas manuales y automáticas comparten presupuesto; reiniciar el worker no lo repone.
La configuración inicial limita a 100 consultas diarias y diez por minuto; una cuenta superior no eleva automáticamente el límite local.
Con diez por minuto se espacian las peticiones aproximadamente 6,1 segundos para evitar ráfagas en las ventanas del proveedor.
La cuota remota y el consumo de ONCE son distintos: otras aplicaciones con la misma cuenta también pueden agotar disponibilidad.
Respeta la próxima fecha permitida y `Retry-After`; no lances comprobaciones repetidas ni aumentes concurrencia para saltarte la espera.

La verificación real registrada en septiembre de 2026 confirmó temporadas 2022–2024 para la cuenta Free utilizada y rechazó 2026.
Es evidencia de esa cuenta y fecha, no una garantía perpetua de cobertura para todo plan.
Revisa la cobertura confirmada antes de pedir datos actuales; una credencial válida no concede automáticamente fútbol en vivo.
No compartas la clave por chat, capturas o frontend. Configúrala en el servidor y recrea API y worker si la cambias.

Las tablas oficiales y los detalles se cargan progresivamente. Una incidencia por formato o identidad requiere auditoría, no un equipo inventado.
Compara el alcance del perfil con la edición y fase seleccionadas; consulta el momento de finalización del trabajo, no solo cuándo entró en cola.
Si el error persiste después de su ventana válida, conserva proveedor, tipo de tarea, identificador y mensaje saneado.
La [guía de proveedores](docs/providers.md) y la [operación de automatización](docs/automation.md) describen el siguiente paso.

## Cómo cerrar una incidencia sin perder datos

1. Registra síntoma, hora, versión y uno de los cinco diagnósticos anteriores.
2. Conserva una copia verificada si la intervención afecta datos, migraciones o credenciales de la base.
3. Aplica el cambio mínimo y comprueba salud, lectura pública y sesión por el mismo acceso que utiliza la persona afectada.
4. Reproduce las regresiones necesarias en QA y verifica en administración si quedó alguna pausa deliberada.
5. Anota lo corregido, el resultado y cualquier límite de cobertura pendiente; después comparte solo evidencia saneada.

En Windows, permisos problemáticos de una carpeta temporal de pytest se evitan con un nuevo `--basetemp=.local/pytest-incidencia` y `-p no:cacheprovider`.
No concedas permisos globales, desactives el firewall completo ni ejecutes todas las herramientas como administrador para resolver un único caso.
En la instalación de trabajo, `docker compose down` conserva volúmenes; `down --volumes`, `system prune --volumes` y restaurar Docker de fábrica pueden destruirlos.
Los comandos de retirada de volúmenes de [TESTING.md](TESTING.md) son exclusivos de conjuntos QA identificados.
