# Desarrollo y verificación

El camino principal de ejecución es Docker. Los asistentes en `scripts` resuelven la raíz a partir de su propia ubicación, por lo que siguen funcionando al renombrar la carpeta.

## API: pruebas y calidad

Sin instalar dependencias Python en el anfitrión:

```sh
docker build --target test -t once-api-tests .
docker run --rm --network none once-api-tests
docker run --rm --network none once-api-tests python -m ruff check src tests scripts
docker run --rm --network none once-api-tests python -m ruff format --check src tests scripts
```

La imagen normal no contiene pytest ni Ruff. El objetivo `test` incluye herramientas y pruebas; usa SQLite en memoria de forma predeterminada. Las pruebas validan autenticación, relaciones, reglas de participación, importación atómica, procedencia y consultas por lotes.

Para desarrollo Python local:

```sh
python -m venv .venv
```

Activa `.venv` según tu sistema (`.venv\Scripts\Activate.ps1` en PowerShell; `source .venv/bin/activate` en Unix), y ejecuta:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m scripts.check_links
```

`TEST_DATABASE_URL` puede apuntar a PostgreSQL **desechable**. La suite elimina y crea tablas: nunca uses la base de trabajo. `python -m scripts.migration_smoke` usa `DATABASE_URL`, exige una base vacía terminada en `_test` y comprueba adopción, actualización y rechazo del downgrade que eliminaría cuentas o auditoría. Para volver atrás se restaura una copia verificada en otra instalación. El flujo de CI proporciona esa base cuando se ejecuta manualmente; consulta el [manual de GitHub](deployment/github.md).

## Frontend

Con Node 24, desde `frontend`:

```sh
npm ci
npm test
npm run lint
npm run build
npm run dev
```

Vite reenvía `/api` a `http://127.0.0.1:8000`; `API_PROXY_TARGET` permite cambiarlo. El lock vigente es `package-lock.json`: no mezcles gestores ni generes un segundo lock. Las [responsabilidades del frontend](../frontend/README.md) explican qué editar.

## Navegador contra Docker aislado

Desde la raíz, compila las imágenes y crea la configuración local de pruebas:

```sh
docker compose build
python -m scripts.prepare_qa
docker compose -f .local/compose.qa.json up -d --wait
```

El generador crea el proyecto `once-qa`, con su propio volumen y puerto `18080`. Si existe una configuración anterior, la conserva, incluidos su nombre y secretos; no la sobrescribe mientras una base pueda depender de ellos.

En PowerShell, desde `frontend`:

```powershell
$env:SMOKE_BASE_URL = 'http://127.0.0.1:18080'
$env:SMOKE_DISPOSABLE = '1'
$env:SMOKE_USERNAME = 'once_test'
$env:SMOKE_PASSWORD = 'once-disposable-test'
npx playwright install chromium
npm run test:e2e
```

En Linux/macOS exporta las mismas variables antes de ejecutar las pruebas. Esa contraseña es exclusiva del conjunto desechable. Los recorridos prueban login, edición, matrículas, partidos, sesión, tamaños de pantalla, navegación y demo. Para probar también una importación real desde Wikidata, define `CATALOG_LIVE_TEST=1`; requiere conexión y disponibilidad de la fuente.

Al terminar, desde la raíz:

```sh
docker compose -f .local/compose.qa.json down --volumes
```

La eliminación de volumen en ese comando es exclusiva del archivo QA. No la ejecutes con el Compose de trabajo.

## Verificación de la reorganización (27 de septiembre de 2026)

Se comprobaron las mismas 45 rutas OpenAPI, 87 pruebas de API tanto en SQLite como en PostgreSQL, 27 pruebas unitarias del frontend y 9 recorridos de navegador. La importación real desde Wikidata y el cierre de sesión durante una recarga retrasada están incluidos. Ruff y Oxlint no presentan errores ni advertencias del código; el cliente de pruebas de Starlette emite dos avisos de deprecación de sus dependencias, pendientes de una actualización coordinada.

También se ensayaron las migraciones y una copia/restauración real en PostgreSQL aislado, comparando los recuentos con el origen y verificando que se rechace una base de destino con tablas. Este registro describe una ejecución concreta; no sustituye las pruebas al modificar el proyecto.

## Verificación del rediseño y los escudos (27 de septiembre de 2026)

El rediseño pasó 100 pruebas de API en SQLite y otras 100 en PostgreSQL, 27 pruebas unitarias del frontend y 13 recorridos de navegador contra Docker aislado, incluida una importación real del catálogo. Se verificaron pantallas de 320 a 1440 píxeles, el menú lateral con ventanas de solo 320 píxeles de alto, los controles móviles y el cierre de sesión durante una carga pendiente. Ruff, Oxlint, compilación y enlaces de documentación pasaron sus comprobaciones.

También se probó el escudo real de UEFA desde Wikidata y Commons: vista previa, guardado explícito, créditos y presentación sin marco, en una base desechable. El cambio no requiere una migración de esquema ni reemplaza imágenes manuales. La cobertura depende de las fuentes y la transparencia depende del archivo original. Estos resultados registran una ejecución concreta y no garantizan disponibilidad futura de las fuentes externas.

## Verificación de módulos y control de datos (27 de septiembre de 2026)

Se aprobaron 121 pruebas de API en SQLite y otras 121 en PostgreSQL, 38 pruebas unitarias del frontend y 19 recorridos de navegador contra Docker desechable, con la importación real de Wikidata habilitada. Los recorridos incluyen aislamiento de temporadas, filtros dependientes, consulta paginada sin escrituras, repetición de filtros vacíos, plantillas y vistas móviles a 320 píxeles. Las lecturas de control y plantillas comprueban autenticación y ausencia de escrituras; el esquema no cambia. Ruff, Oxlint, compilación y enlaces de documentación pasaron sus verificaciones.

## Verificación de la automatización (27 de septiembre de 2026)

La implementación tiene pruebas específicas del [motor](../tests/test_sync_engine.py), [controles administrativos](../tests/test_sync_routes.py), [concurrencia PostgreSQL](../tests/test_sync_postgres.py), [cursor SSE](../tests/test_sync_events.py), [archivo abierto](../tests/test_openfootball.py) y [descubrimiento/cadencia](../tests/test_automation_discovery.py). Comprueban pausa durante descarga, transacciones en curso, reservas vencidas, presupuesto compartido, respuestas incompletas, auditoría, repetición idempotente y separación de ediciones.

La ejecución integrada aprobó 225 pruebas en SQLite (4 casos específicos de PostgreSQL omitidos) y las 229 en PostgreSQL 15. El frontend aprobó 41 unitarias y 22 recorridos E2E sobre Docker; se omitió el recorrido optativo de importación masiva real. Lint, formato y compilación pasaron; permanecen dos avisos de deprecación del cliente de pruebas. Los ajustes posteriores de preparación del piloto y cruce de identidades se verifican por separado y no se suman a esa ejecución integrada.

La imagen de pruebas Docker posterior, con Python 3.12, aprobó 234 pruebas y omitió los 4 casos exclusivos de PostgreSQL. Las ampliaciones de identidad, preparación y cuota pasaron además una selección de 50 pruebas en PostgreSQL. El último ajuste de fechas aprobó las 8 pruebas de seguridad/lectura afectadas, elevó las unitarias del frontend a 44 y volvió a pasar su E2E: conserva días locales completos, incluidos cambios de horario de verano. No se presenta la suma de ejecuciones repetidas como número de pruebas distintas.

En una instalación Docker restaurada desde los datos anteriores se aplicaron las migraciones hasta `0007`. El trabajador importó un escudo real de UEFA y sus hechos históricos; al repetir ambas tareas el número de cambios fue cero. La consulta masiva de Wikidata devolvió `maxlag`: se respetó la espera y no se publicó ese lote. Una prueba de regresión cubre respuestas HTTP comprimidas para impedir doble descompresión.

También se ensayó una transferencia completa de PostgreSQL y medios locales a otro proyecto Compose vacío: integridad SHA-256, archivos y referencias restaurados, historial conservado, control en pausa y trabajador sano. Se conservó la protección de solo anexado de la auditoría. Las bases de trabajo no se usaron para pruebas destructivas.

La instalación desde cero compiló una imagen nueva y arrancó sobre volúmenes vacíos: PostgreSQL, API y trabajador quedaron sanos, el esquema llegó a `0007_accounts` y la sincronización comenzó en pausa. El trabajador reutilizó la imagen local sin intentar descargarla de un registro. La prueba de migraciones sobre otra base PostgreSQL vacía comprobó además que el downgrade destructivo se rechaza y conserva la revisión vigente; la recuperación se realiza mediante una copia verificada.

La instalación principal se actualizó después de una nueva copia de seguridad. Las migraciones conservaron sus 20 equipos, cinco competiciones y un partido existentes. El piloto abierto añadió 200 encuentros, cuatro equipos y una edición de 2025; la lectura pública paginada confirmó 201 partidos y SSE entregó un evento `change` a través de NGINX. Los cuatro servicios quedaron sanos. Los proyectos, contenedores y volúmenes desechables se retiraron después de las pruebas para no consumir recursos del equipo. No se creó ningún commit ni se ejecutó GitHub Actions durante esta entrega.

La primera ejecución de los tres perfiles terminó correctamente: archivo colombiano, confederaciones y catálogo colombiano. Se guardaron hechos estructurados para 26 fichas y 14 recursos visuales locales con procedencia. Cinco recursos visuales quedaron como incidencias de descarga; no impidieron conservar el catálogo. Las cuotas y la espera solicitada por Commons se respetaron. Se generó además una copia completa posterior con base de datos y medios.

Se ejecutaron pruebas del motor y el archivo con SQLite y PostgreSQL 15 aislado. Los casos de concurrencia específica de PostgreSQL se omiten al usar SQLite: para comprobarlos se necesita `TEST_DATABASE_URL` de una base desechable. Las ampliaciones posteriores se vuelven a ejecutar con el conjunto integrado antes del despliegue; los resultados de entregas anteriores no se suman para presentar una cifra de pruebas vigente.

Un ensayo real del trabajador descargó el archivo CC0 colombiano de 2025 y creó 200 partidos, veinte equipos y una edición en una base QA. Conservó 33 resultados desconocidos. Una segunda ejecución produjo cero cambios canónicos, mantuvo una sola observación por contenido y consumió una segunda consulta registrada. La prueba acredita el archivo histórico; no acredita resultados de 2026 ni servicio en vivo.

Sobre una copia de los datos existentes, otro ensayo creó los mismos 200 partidos sin duplicar clubes: reutilizó quince identidades Wikidata verificadas y un vínculo revisado de Llaneros. Conservó los 20 equipos anteriores, añadió cuatro y pasó de un partido a 201. El resultado registró cero encuentros omitidos; repetirlo produjo cero cambios. La zona horaria no declarada del archivo permanece explícita en la cobertura y no se inventan instantes UTC.

El [banco de rendimiento](automation/performance.md) ejercitó 10.000 y 100.000 partidos, hasta un millón de eventos, diez lectores, un auditor y un trabajador con descarga simulada. Emplea rutas ASGI reales y PostgreSQL en Docker, no navegador ni NGINX. El script recrea únicamente una base local de pruebas que supere sus comprobaciones y requiere `--allow-disposable-db`; sus archivos JSON se conservan en `.local/benchmarks/` y no se publican en Git.

En Windows, si el directorio temporal de pytest tiene permisos heredados incompatibles, usa una carpeta nueva bajo `.local`, por ejemplo `--basetemp=.local/pytest-verificacion-01`, y `-p no:cacheprovider` para evitar la caché protegida. No cambies permisos globales ni dirijas esa carpeta a documentos del usuario.

## Conexión e importación real de API-Football (27 de septiembre de 2026)

La cuenta Free se verificó desde el servidor, sin exponer la clave al navegador o al repositorio. La fuente confirmó 100 consultas diarias, diez por minuto y acceso a 2022–2024; rechazó 2026 y las consultas de detalle mediante varios identificadores. Se respetó la decisión de conservar el plan gratuito. El detalle se consulta por partido y conserva un marcador de progreso para evitar descargar de nuevo cada encuentro histórico terminado.

Los quince calendarios correspondientes a cinco competiciones y tres años se importaron. La instantánea de las 23:01 UTC contiene 2.890 partidos API-Football y 201 registros previos, para un total de 3.091. Se conservan 62 equipos, siete competiciones, 26 ediciones, 379 jugadores, 293 eventos, 610 registros de alineación y 35 tablas publicadas. Los detalles siguen creciendo con la cola; esos recuentos no afirman que cada encuentro disponga de estadísticas completas.

| Competición de API-Football | Partidos importados de 2022–2024 |
| --- | ---: |
| Primera A | 1.336 |
| Primera B | 909 |
| Copa Colombia | 208 |
| Liga Femenina | 431 |
| Superliga | 6 |

Primera B 2022 conserva cuatro ediciones: Apertura (131 partidos), Clausura (154), Championship (2) y Promotion Play-offs (2). La regla de promoción reconoce únicamente la liga, año y ronda contrastados. Liga Femenina conserva su formato anual, con las fases de cada año. Ninguna de esas excepciones convierte un formato desconocido en una importación automática.

La auditoría de los 2.890 encuentros API comprobó cero relaciones huérfanas, equipos idénticos en un encuentro, incoherencias entre competición/edición/fase/grupo o identificadores externos duplicados. Las identidades de equipos masculinos y femeninos permanecen separadas. Un vínculo duplicado de Cúcuta se reconcilió con copia previa, comprobación de referencias y auditoría de cada cambio. Las incidencias anteriores de identidades y formatos se resolvieron después de verificar los lotes completos.

Se mantiene abierta una incidencia de **Primera B 2023, Clausura**: la tabla publicada contiene 16 equipos, mientras los partidos contienen 17 identidades; Valledupar aparece en dos encuentros y Real Cundinamarca en catorce. No se infiere una sucesión ni se fusionan fichas automáticamente. Las otras cinco tablas de ese año se publicaron. El archivo abierto de 2025 conserva su aviso de 33 resultados ausentes y los recursos visuales previamente pendientes mantienen sus incidencias.

La imagen Docker final de pruebas con Python 3.12 aprobó **303 pruebas** y omitió cuatro exclusivas de PostgreSQL. Una ejecución previa en PostgreSQL 15 aprobó 273 pruebas; después, las 68 pruebas afectadas por conexión, cuota, vistas previas, concurrencia e ingesta volvieron a pasar en PostgreSQL. Los dos casos nuevos de disponibilidad de tablas también pasaron en PostgreSQL 15 aislado. Son ejecuciones distintas, no una suma de pruebas únicas. Permanecen dos avisos de deprecación del cliente de pruebas, sin fallos de ejecución.

El frontend aprobó **53 pruebas unitarias**, los recorridos de navegador de conexión, procedencia, selección de tablas y aislamiento de ediciones, además de lint y compilación. La comprobación adicional de lectura contra el Docker principal verificó cuenta conectada, exclusión de 2026 del selector, procedencia API-Football, apertura de la tabla oficial de 20 equipos y un detalle real con 19 eventos y 36 registros de alineación. Se comprobaron tamaños móvil/escritorio y ausencia de errores de JavaScript o desplazamiento horizontal de la página. Ninguna navegación de usuario consume solicitudes de API-Football.

La comprobación con 22 titulares reales detectó superposición en la representación inicial de la cancha. Se sustituyó por filas legibles de cada equipo, con nombres, dorsales y orden publicado; no se inventan posiciones tácticas. El ajuste visual se verificó con once titulares por equipo a 320, 390 y 1440 píxeles, sin solapamientos ni desbordamiento, y se compiló en la imagen final del frontend.

La copia completa posterior a la carga se generó a las 23:04 UTC, con el trabajador detenido durante la captura de PostgreSQL y medios. El archivo de base se verificó mediante su índice de restauración; el manifiesto conserva las sumas SHA-256 de ambos archivos. Después se reactivó el trabajador. Los 36 perfiles de importación quedaron automáticos; la comprobación de cuenta es un perfil manual separado. Al agotarse la cuota comunicada por el proveedor, los trabajos quedaron esperando su renovación y la consulta de datos locales siguió funcionando.

El [manual de servidor](deployment/server.md) incorpora dominio, HTTPS, NGINX, copia/restauración y configuración de cookies. Su configuración de NGINX pasó una comprobación aislada con certificado de ensayo. La entrega está ejecutándose en Docker local; no se ha desplegado en un servidor remoto. Durante este trabajo no se creó ningún commit ni se ejecutó GitHub Actions.

## Manuales operativos y herramientas de desarrollo (27 de septiembre de 2026)

La raíz contiene ocho manuales conectados: contexto, entrada, arquitectura, instalación, pruebas, despliegue, diagnóstico y contribución. La colección distingue tutoriales, guías, referencias y explicaciones; documenta la implementación real y etiqueta los ejemplos y propuestas. No presenta porcentajes de cobertura sin medir, Redis instalado ni despliegues remotos inexistentes. El flujo por push de `DEPLOYMENT.md` es un ejemplo opcional: la CI del repositorio conserva exclusivamente `workflow_dispatch`.

El Makefile delega en `scripts.dev`, disponible también en Windows sin GNU Make. Sus tareas cubren instalación, arranque, comprobaciones, QA aislado, copias y banco de carga. El lector manual de entorno no ejecuta shell ni expande valores; respeta variables del proceso. Los atajos de pytest rechazan archivos SQLite persistentes y bases externas sin sufijo `_test`; los de navegador comprueban identidad, puertos, conexiones y volúmenes de QA antes de arrancarlo.

La imagen final de pruebas, Python 3.12 y sin red, aprobó **320 pruebas**, omitió cuatro exclusivas de PostgreSQL y conservó los dos avisos de deprecación ya descritos. Incluye 17 casos de las nuevas herramientas: configuración literal, precedencia, orden de migración, aislamiento de base y aceptación del conjunto QA generado. Las **53 unitarias del frontend** y su lint volvieron a pasar; Ruff, formato y enlaces de toda la documentación también. Estos recuentos son ejecuciones concretas, no métricas de cobertura.

La ruta manual del ayudante se comprobó contra PostgreSQL 15 desechable: migraciones `0001`–`0007`, control inicialmente pausado, salud, login, sesión, catálogo público y logout. Se retiró el entorno QA al terminar. GNU Make, en un contenedor efímero, resolvió ayuda y todos sus targets en modo de simulación. El YAML de despliegue opcional pasó un parser y sus bloques Bash pasaron comprobación sintáctica; las revisiones fijadas de las acciones se contrastaron con sus repositorios oficiales. Estas comprobaciones no equivalen a ejecutar un despliegue SSH.

La revisión previa a esta publicación inspeccionó 313 archivos candidatos sin encontrar las credenciales locales ni patrones de claves privadas o tokens GitHub. Los secretos, copias y medios de trabajo siguen fuera de Git. Los cuatro servicios principales permanecieron saludables durante la elaboración de la documentación, y el atajo de salud obtuvo una respuesta correcta. No se invocó API-Football para verificar documentación ni se lanzó GitHub Actions.

## Acceso administrativo desde móvil por LAN (27 de septiembre de 2026)

Los registros mostraron intentos de Safari en iPhone que alcanzaban `POST /api/login` por la IP local y recibían 401; el acceso desde localhost funcionaba. La configuración activa de cookies ya admitía HTTP local. Se detectó y reprodujo una inconsistencia: las cuentas nominales normalizaban mayúsculas y espacios externos en el usuario, pero el administrador configurado exigía coincidencia exacta. El registro no conserva las credenciales introducidas, de modo que no acredita cuál fue la diferencia concreta escrita en el teléfono.

El login aplica ahora la misma normalización a ambas rutas y conserva el nombre canónico en la sesión y auditoría. No cambia contraseñas, hashes, roles ni la comprobación exacta de la contraseña. El formulario evita autocorrección y mayúsculas automáticas en usuario y contraseña, incluso con la contraseña visible.

Cuatro regresiones fallaron antes de la corrección. Después pasaron 34 pruebas de autenticación, cuentas y permisos, incluidas seis nuevas. Dos recorridos Playwright pasaron contra un conjunto PostgreSQL/Docker independiente, accedido mediante la IP LAN por HTTP: usuario en mayúsculas y con espacios externos, login a 390 × 844, persistencia tras recargar y cierre de sesión, además de la regresión de una respuesta retrasada tras logout. El navegador de esas pruebas fue Chromium; la comprobación final desde el iPhone corresponde al dispositivo del usuario. La compilación, lint y enlaces se verificaron antes de entregar la corrección.

## Al modificar una funcionalidad

Mantén URLs, errores, contratos y migraciones compatibles salvo cambio explícito. Coloca las reglas reutilizables fuera de los handlers HTTP; los componentes no deben conocer secretos ni proveedores remotos. Añade una prueba cuando exista una regla, regresión o condición de carrera relevante, y ejecuta el recorrido afectado en el conjunto desechable antes de actualizar la instalación de trabajo.

Los modelos no se cambian editando los SQL históricos. Añade una revisión Alembic y compruébala sobre una copia desechable. Un cambio de carpeta, marca o documentación no exige migrar las identidades internas de Docker.
