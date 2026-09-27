# Fuentes, proveedores y procedencia

## Catálogos abiertos de ONCE

La primera importación gratuita de identidades ya está disponible desde Wikidata. Descarga colecciones acotadas en lotes, conserva una copia de 24 horas, propone coincidencias y aplica la selección de forma atómica. La preparación escribe únicamente el lote de observaciones; las entidades se crean o vinculan después de revisar la vista previa. Consulta [el alcance y la arquitectura de ingesta](ingestion.md).

ONCE debe poder cambiar de proveedor sin cambiar la identidad de sus entidades. Un equipo, partido o competición conserva siempre su ID local; los IDs externos viven en `ProviderMapping`.

## Regla principal

Un proveedor aporta observaciones sobre el fútbol. No define el modelo de ONCE.

Por eso:

- no se reutilizan IDs externos como claves primarias
- un fixture solo se sincroniza automáticamente cuando sus equipos ya están mapeados
- los equipos desconocidos quedan pendientes para revisión
- los previews de proveedores no escriben en el dominio; preparar un catálogo abierto sí conserva un lote revisable
- cada sincronización pasa por una cola con un control explícito de pausa, modo y presupuesto
- los recursos visuales externos deben conservar fuente y licencia en `MediaAsset`

## API-Football

Integración: `api-football`, con comprobación de cuenta, preparación de competiciones colombianas y actualizaciones mediante la cola de ONCE.

Configuración opcional:

```env
API_FOOTBALL_KEY=
```

La clave permanece en el backend y se comparte con el trabajador mediante la configuración del despliegue. No se introduce en la interfaz, no se envía al navegador ni se incluye en Git. Después de cambiarla, recrea API y trabajador como indica [el manual de despliegue](deployment/local.md).

### Conexión desde administración

En **Datos → Automatización → Conecta el juego real**, usa **Comprobar cuenta y cobertura**. El diagnóstico verifica la suscripción, consulta las competiciones de Colombia y prueba el acceso a una temporada actual: hasta tres solicitudes explícitas, con el mismo presupuesto que las importaciones. Puede ejecutarse con la importación pausada; consultar o refrescar la pantalla solo lee el estado guardado y no consume solicitudes externas. Las comprobaciones se espacian al menos un minuto.

El panel separa tres hechos: una clave configurada, una suscripción activa y el acceso efectivo a una temporada. Cuando la fuente comunica una lista válida de años permitidos, el selector muestra únicamente su intersección con las temporadas publicadas para cada competición. Si el acceso no está confirmado, se indica como pendiente; nunca se presupone que el plan gratuito incluya el año actual.

Selecciona competiciones y años, decide si quieres completar también los detalles y pulsa **Preparar competiciones**. Se prepara el calendario y, cuando la cobertura lo anuncia, una actualización de clasificaciones para ese año. La preparación es repetible: crea las tareas nuevas pausadas y conserva el modo de las existentes. **Activar estas actualizaciones** afecta a esos perfiles. El control general se modifica por separado y puede continuar pausado o en solo comprobación.

### Verificación real del piloto, 27 de septiembre de 2026

La cuenta de esta instalación confirmó una suscripción **Free** con **100 solicitudes diarias**. `/leagues?country=Colombia` devolvió cinco competiciones: Primera A (239), Primera B (240), Copa Colombia (241), Liga Femenina (712) y Superliga (713). Sus catálogos anuncian temporadas hasta 2026.

La consulta de partidos de Primera A en 2026 fue rechazada por el plan, que indicó acceso a **2022–2024**. Primera A 2024 devolvió **432 partidos**. Tras comprobar ese acceso se importaron los quince calendarios colombianos de esos tres años: 2.890 partidos y 35 tablas publicadas. El [registro de desarrollo](development.md) detalla la incidencia de una tabla de Primera B 2023 y la carga progresiva de detalles. La instalación conserva la cobertura gratuita y su archivo histórico; no presenta este acceso como seguimiento en vivo de 2026.

La fecha y los límites corresponden a esta comprobación concreta. Una nueva cuenta o un cambio de plan requieren repetirla. La [página oficial de planes](https://www.api-football.com/pricing) distingue el límite de temporadas del plan gratuito de la disponibilidad general de competiciones y endpoints.

La integración usa la API v3 de API-Football. En su documentación actual:

- `/leagues` expone cobertura por competición y temporada
- `/fixtures?league=...&season=...` entrega calendario/resultados
- `/fixtures/rounds` entrega rondas
- `/teams` entrega equipos y estadios asociados
- fixtures detallados pueden incluir eventos, alineaciones y estadísticas según cobertura
- la autenticación se realiza con el header `x-apisports-key`

Referencia: [documentación oficial de API-Football v3](https://www.api-football.com/documentation-v3).

### Sincronización de fixtures

Para aplicar los partidos deben existir vínculos canónicos de:

1. competición local → league ID
2. temporada local → año del proveedor
3. cada equipo participante → team ID

La automatización obtiene competición, equipos y estadios antes del calendario, crea identidades nuevas verificables y establece sus vínculos. Las coincidencias dudosas con el catálogo existente pasan a revisión; no se fusionan fichas por mera similitud. Un administrador también puede confirmar los vínculos explícitamente. Cuando están resueltos, la sincronización crea o actualiza partidos y conserva los IDs locales.

Si el año incluye Apertura y Clausura, la importación distingue las ediciones por los nombres publicados de las rondas. Una selección concreta de edición mantiene su propio alcance. Los metadatos de liga y equipos se reutilizan durante 24 horas.

Si falta el mapping de uno de los equipos, el fixture se reporta como `team_mapping_missing` y no se crea.

Cada fixture sincronizado conserva además un snapshot normalizado del payload original. Esto permite auditar qué respondió el proveedor sin convertir ese JSON en la fuente canónica del dominio.

### Profundización de un partido

La opción **Completar también el detalle de los partidos** prepara una tarea progresiva por competición y año. Prioriza partidos en curso y partidos finalizados pendientes. Con **Free**, consulta un partido por solicitud a `/fixtures?id=...`: la comprobación real devolvió un encuentro con diez eventos, dos alineaciones y estadísticas de los dos equipos. La consulta por varios identificadores fue rechazada por ese plan; por eso el trabajador selecciona de antemano la consulta individual. Completar centenares de encuentros puede necesitar varios días de cuota.

En cuentas que lo permiten, se consultan hasta veinte identificadores en una solicitud a `/fixtures?ids=...`; si el proveedor rechaza esa modalidad, se conserva la restricción y se vuelve a la consulta individual. El trabajador aplica las jugadas, alineaciones y estadísticas que la fuente devuelva, conservando el origen y las ausencias como incidencias. El panel muestra los partidos consultados, los devueltos y si quedan más lotes. Tener una temporada permitida no garantiza que todos sus partidos incluyan cada detalle.

Una vez que un partido tiene mapping de fixture, la sincronización explícita de detalle consulta tres superficies separadas de API-Football:

- eventos del partido
- alineaciones
- estadísticas por equipo

Los jugadores desconocidos se crean con ID interno propio y reciben un `ProviderMapping` de tipo `player`. Una alineación demuestra participación en ese partido; no modifica la plantilla vigente del club.

Los registros importados llevan `source=api-football` y una clave estable. Al repetir una consulta, ONCE actualiza las mismas filas y conserva sus IDs. Los campos corregidos manualmente están protegidos. La ausencia de una fila en una respuesta no la elimina: las respuestas completas por transporte también pueden ser parciales en contenido deportivo, por lo que se abre una incidencia para revisión.

Los payloads de eventos, alineaciones y estadísticas quedan guardados en `ProviderSnapshot` como última observación recibida para ese partido.

### Clasificaciones de la temporada

Cuando la cobertura anuncia clasificaciones, la preparación añade un perfil `standings_batch` para la competición y el año. Consulta las tablas publicadas y contrasta los equipos con los participantes y cruces ya importados antes de asociarlas a una edición, fase y grupo. Los cuadrangulares se mantienen separados de la fase regular. Las correspondencias ambiguas generan una revisión; no se inventan reglas ni se presenta como calculada una tabla que procede de la fuente.

## Wikidata y Wikimedia Commons

Wikidata se usa como fuente de enriquecimiento y referencias, no como fuente de resultados en vivo.

ONCE consulta entidades conocidas mediante la interfaz `Special:EntityData/QID.json` e identifica sus peticiones con un User-Agent configurable:

```env
WIKIDATA_USER_AGENT=ONCE/0.2 (personal local football catalog)
```

### Escudos con revisión antes de publicar

En **Datos → Traer información → Buscar escudos e imágenes**, el administrador elige la ficha por su nombre. Su vínculo con Wikidata permite encontrar el escudo sin introducir otro identificador cuando ya está conectado.

La búsqueda de escudos usa `P154`, la propiedad de logotipo de Wikidata. No sustituye un escudo ausente por una fotografía de equipo (`P18`), ni descarga marcas de sitios encontrados al azar. La búsqueda de imágenes generales sí admite `P18`. Entre varias afirmaciones se prioriza la de rango preferido y se omiten las obsoletas.

La vista previa muestra la imagen, nombre de la entidad, autor, crédito, licencia y enlace al archivo en Commons. Las condiciones se revisan por archivo: los datos estructurados CC0 de Wikidata no convierten los escudos en CC0. También pueden existir restricciones de marca independientes de la licencia del archivo.

Al confirmar se guarda `MediaAsset` junto con su procedencia y se conecta el QID. La opción de usarlo como escudo solo rellena un `logo` vacío; conserva cualquier imagen elegida manualmente. Rechaza una identidad distinta a la ya conectada, un archivo diferente al revisado o un escudo sin licencia identificada. Repetir la importación actualiza el mismo recurso.

El catálogo público sirve esas referencias desde PostgreSQL. `GET /public/crests/` devuelve la atribución de los escudos seleccionados, incluidos los servidos desde el volumen local, sin consultar proveedores por cada tarjeta o visita. Se conserva el contorno y la transparencia del archivo; no se descarga al repositorio. Los SVG locales se limpian de contenido activo. Si falta el archivo o no carga, la interfaz muestra las iniciales.

### Contrato de imágenes

- `GET /providers/wikidata/preview/{qid}/media?purpose=crest`: únicamente un escudo `P154`; `purpose=image` también permite fotografía `P18`.
- La respuesta incluye `entity_name`, `property`, `filename`, `original_url`, `thumbnail_url`, `author`, `credit`, `license`, `license_url`, `source_url` y `can_use_as_logo`.
- `POST /providers/wikidata/import-media/{entity_type}/{local_id}/{qid}?use_as_logo=true&preview_filename=...`: confirma el archivo revisado para `team` (club o selección), `competition` o `confederation`. Sin `use_as_logo`, mantiene la importación de recursos generales.
- `GET /public/crests/`: lista pública de `MediaAssetRead` con `tipo=escudo`, licencia, fecha de verificación y URL coincidente con el escudo elegido en la entidad. Los recursos guardados pero no elegidos no aparecen.

En la herramienta manual los metadatos de Commons se piden por archivo y se reutilizan 24 horas en una caché de memoria limitada a 128 recursos por proceso. La automatización consulta metadatos en lotes acotados y descarga archivos validados al volumen compartido de medios, con índice de 24 horas y nombres por contenido. Los reintentos de la cola respetan cuotas y pausas; la herramienta de vista previa devuelve el error sin repetir peticiones. Arrancar Docker conserva el modo persistido: si estaba en automático, recupera las tareas; una instalación nueva comienza pausada.

Las URL de imágenes aceptadas pertenecen a los dominios HTTPS de archivos de Wikimedia; el texto de autoría se entrega sin HTML y los enlaces no admiten esquemas ejecutables. Configura `WIKIDATA_USER_AGENT` con el nombre de la instancia y una URL o correo de contacto real cuando la despliegues.

Referencias:

- <https://www.wikidata.org/wiki/Wikidata:Data_access>
- <https://www.mediawiki.org/wiki/API:Imageinfo>
- <https://www.wikidata.org/wiki/Property:P154>
- <https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia>
- <https://www.mediawiki.org/wiki/API:Etiquette>
- <https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy>

## MediaAsset

Todo asset externo que se quiera convertir en parte estable del producto debería poder responder:

- ¿a qué entidad pertenece?
- ¿qué tipo de recurso es?
- ¿de dónde salió?
- ¿cuál es la URL original?
- ¿quién es el autor?
- ¿qué licencia tiene?
- ¿cómo debe acreditarse?
- ¿cuándo se verificó?

Tener una URL pública no implica permiso de redistribución. La licencia se verifica por recurso.

## Estrategia de caché

La importación abierta conserva lotes durante 24 horas. Las actualizaciones programadas separan los tipos de dato:

- identidad de equipos/competiciones: caché larga
- calendario futuro: actualización moderada
- partido finalizado: casi inmutable
- partido en vivo: intervalo corto únicamente durante su ventana activa

No se debe consultar todo el universo de un proveedor al cargar una página. La ingestión se hace por competición/temporada o por fixture según necesidad.

## Archivo abierto y trabajo automático

OpenFootball incorpora el archivo colombiano CC0 de 2023–2025 desde un repositorio y rutas permitidos. Crea ediciones Apertura/Clausura, fases publicadas, grupos, participantes y partidos conservando el texto original y su referencia. Comprueba el total declarado del archivo y rechaza formatos desconocidos. El archivo 2025 consultado tiene 33 marcadores ausentes de 200 partidos; no se rellenan con ceros. El año 2026 no está disponible en este adaptador.

La hora del archivo no demuestra una zona horaria. Solo se convierte en fecha UTC cuando se configura explícitamente `America/Bogota`; las fechas y horas originales siempre permanecen en la observación. Las coincidencias dudosas de equipos se revisan mediante vínculos, nunca por fusión automática de nombres.

El descubrimiento de API-Football prepara perfiles pausados para las ediciones publicadas elegibles; se valida acceso antes de activarlos. El catálogo de liga/equipos se reutiliza 24 horas, mientras calendario y resultados siguen su frecuencia efectiva. La cadencia puede espaciarse según proximidad de los partidos y cuota compartida. La capacidad de responder rápido desde PostgreSQL no implica que el proveedor actualice rápido sus datos.

Los endpoints antiguos de sincronización devuelven `202` con el trabajo encolado; con pausa general devuelven `409`. No ejecutan HTTP ni importaciones dentro de la petición administrativa. Los contratos y el procedimiento operativo están en [Automatización](automation.md).

Fuente del archivo: [OpenFootball South America](https://github.com/openfootball/south-america). Wikidata y Commons no requieren clave. La conexión real de API-Football fue verificada con las limitaciones de temporada descritas arriba; la aplicación sigue pudiendo funcionar sin esa credencial.
