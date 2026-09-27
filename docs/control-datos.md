# Organización y control de datos

ONCE separa la identidad del catálogo, la organización de las competiciones, la operación de los partidos y la procedencia de la información. Las relaciones conectan estos módulos mediante registros existentes; no convierten sus pantallas en un único formulario.

## Inventario de responsabilidades

| Módulo | Registros y relaciones | Capacidad actual del servidor |
| --- | --- | --- |
| Catálogo | Confederaciones, competiciones, clubes y selecciones | Crear, consultar, editar y eliminar identidades. |
| Participaciones | Equipo → competición, edición, fase o grupo | Matrícula general compatible con el sistema anterior y participación explícita por ámbito con procedencia. |
| Temporadas | Competición → edición | Crear y consultar. |
| Fases y grupos | Temporada → fase → grupo | Crear, consultar y corregir campos autorizados; las relaciones se validan por ámbito. |
| Estadios | Sedes y ubicación | Crear y consultar. |
| Jugadores | Identidad de cada persona | Crear y consultar. |
| Plantillas | Jugador → equipo y fechas | Consulta administrativa paginada de la pertenencia registrada. No hay editor manual de estos vínculos. |
| Partidos | Local, visitante, torneo, edición, fase, fecha y resultado | Lecturas paginadas, detalle bajo demanda y correcciones protegidas; el proveedor actualiza diferencias autorizadas. |
| Detalle del partido | Eventos, alineaciones y estadísticas | Crear y consultar dentro del partido. Los datos importados conservan su fuente. |
| Fuentes | Colecciones, búsquedas, equivalencias e importaciones | Configurar ámbitos automáticos y conservar herramientas explícitas de revisión; permisos de gestión de fuentes. |
| Automatización | Cola, cuotas, pausa, observaciones y recuperación | Trabajo fuera de la API, control persistente y excepciones operativas. |
| Revisión e historial | Valores, protecciones, decisiones y personas | Corrección por campo con actor, motivo y versión; historial de solo anexado. |
| Clasificaciones | Edición, fase, grupo, regla y ajustes | Cálculo ONCE y tabla externa separados; no se publica un cálculo sin regla revisada. |
| Personas | Usuarios nominales y permisos | Auditor, editor, operador y administrador; desactivación revoca sesiones. |
| Control de datos | Calidad del estado actual y procedencia disponible | Consultar hallazgos, vínculos, lotes, observaciones e imágenes. Nunca corrige ni importa. |
| Experiencia pública | Competiciones, equipos, partidos y clasificaciones | Lectura; las herramientas de administración requieren sesión. |

La navegación administrativa debe ofrecer filtros propios de cada módulo. Por ejemplo, una fase se localiza por competición y temporada; un equipo por tipo, país o confederación; un partido por competición, edición, estado o fecha. Cambiar un filtro superior invalida una selección inferior incompatible. Un listado vacío debe distinguirse de un error de carga.

`GET /plantillas/` consulta la pertenencia guardada con filtros opcionales `equipo_id`, `jugador_id`, `search` (nombre de jugador o equipo) y `estado`. Admite `page` desde 1 y `page_size` entre 1 y 100; devuelve `items`, `total`, `page` y `page_size`. `estado=active` significa **sin cierre registrado** (`fecha_fin` vacía), y `estado=closed`, **con cierre registrado**. Estos filtros no certifican vigencia, elegibilidad ni alineación actual: una fecha puede ser futura y un vínculo sin fechas puede estar incompleto. La lectura conserva referencias dañadas o nombres vacíos con una etiqueta de registro no disponible, sin descartarlos ni corregirlos. No añade operaciones de escritura.

## Qué controla la nueva consulta

`GET /control/summary` devuelve cantidades por módulo, comprobaciones del estado actual, fuentes disponibles, tipos de registro y los límites de esta consulta. Los avisos sin confederación o sin temporada son revisiones: esos vínculos son opcionales y algunos torneos son globales. Las referencias locales ausentes o las fechas invertidas se señalan como errores de datos.

`GET /control/issues?code=…` permite revisar los registros de cada hallazgo, con nombre, módulo y referencia local cuando existe. Las referencias genéricas de fuentes pueden sobrevivir a una eliminación; el control muestra ese caso sin borrarlas ni inventar una asociación.

`GET /control/records?kind=…` mantiene cuatro listados separados:

| `kind` | Qué representa | Qué significa la fecha |
| --- | --- | --- |
| `imports` | Consulta de una colección y su último resultado aplicado | `recorded_at` es la consulta a la fuente. `metadata.applied_at` es la última aplicación guardada. |
| `links` | Identidad externa vinculada a un registro local | Verificación guardada, si existe; no es necesariamente la fecha de creación. |
| `observations` | Última respuesta conservada por proveedor, registro y categoría | Consulta a la fuente. No es un historial de respuestas anteriores. |
| `media` | Imagen con su origen, autor, créditos y licencia | Verificación guardada, si existe. |

Las listas admiten `page` desde 1 y `page_size` entre 1 y 100. Devuelven `items`, `total`, `page` y `page_size`. Los filtros `provider`, `entity_type` y `search` se aplican en la base de datos antes de paginar; `entity_type` no corresponde a lotes completos y se rechaza para `imports`. La búsqueda usa texto literal, sin tratar `%` o `_` como comodines. La ordenación añade el identificador como desempate para que las páginas sean estables con datos sin cambios.

Solo se resuelven nombres y metadatos necesarios para cada página; las respuestas originales completas no se envían a estos listados. El resumen ejecuta tres consultas agregadas y cada lista dos consultas: cantidad y página. Todas las rutas requieren autenticación, no escriben y no hacen solicitudes a proveedores. El módulo no añade tablas ni migraciones.

## Calidad, auditoría y operación son consultas distintas

`/control/*` conserva el inventario del estado actual: fichas incompletas, referencias ausentes y metadatos de fuentes. `/audit/*` conserva cambios canónicos, correcciones protegidas y discrepancias por campo. `/automation/*` informa de ejecuciones, cuotas, pausas y problemas del proveedor. Una incidencia operativa no modifica por sí sola el marcador ni suprime una ficha.

El historial de cambios registra actor, motivo, valores y versión. Las correcciones de campo comprueban la versión esperada para detectar ediciones simultáneas. Si una fuente propone otro valor para un campo protegido, la revisión permite mantener la corrección o volver a aceptar futuras observaciones. Resolver una incidencia no acepta automáticamente su propuesta.

Los eventos de auditoría se anexan y PostgreSQL migrado impide UPDATE/DELETE sobre ellos mediante un disparador. Esto no representa una certificación ni inmutabilidad frente al propietario de la base. Los lotes revisados de catálogo siguen conservando su último resultado, y `ProviderSnapshot` continúa siendo una observación reciente; el motor incorpora su propio historial de trabajos y observaciones deduplicadas.

Las cuentas nominales tienen permisos verificados en el servidor. El auditor consulta, el editor corrige, el operador controla ámbitos existentes y el administrador gestiona fuentes y personas. La cuenta de entorno sigue disponible como acceso de recuperación. Aprobación por una segunda persona y requisitos regulatorios específicos no forman parte de esta entrega.

La pausa persiste incluso después de reiniciar Docker. «Comprobado» significa que se consultó una fuente; no garantiza que esta publique resultados deportivos en directo. Cada ámbito conserva configuración, cobertura, cuota y últimas fechas. Un fallo externo mantiene el último dato local válido y expone el problema.

Las [reglas de datos](data.md), el [manual de automatización](automation.md), la [auditoría por campo](automation/domain-and-audit.md) y los [contratos de proveedores](providers.md) describen el comportamiento y sus límites. Las pruebas de inventario siguen en [tests/test_control.py](../tests/test_control.py); correcciones, cuentas y versiones se verifican en [tests/test_accounts_audit_api.py](../tests/test_accounts_audit_api.py).
