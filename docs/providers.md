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
- cada sincronización es explícita
- los recursos visuales externos deben conservar fuente y licencia en `MediaAsset`

## API-Football

Integración inicial: `api-football`.

Configuración opcional:

```env
API_FOOTBALL_KEY=
```

La clave permanece en el backend. El administrador consulta el estado del proveedor y puede previsualizar fixtures por `league_id` y temporada.

La integración usa la API v3 de API-Football. En su documentación actual:

- `/leagues` expone cobertura por competición y temporada
- `/fixtures?league=...&season=...` entrega calendario/resultados
- `/fixtures/rounds` entrega rondas
- `/teams` entrega equipos y estadios asociados
- fixtures detallados pueden incluir eventos, alineaciones y estadísticas según cobertura
- la autenticación se realiza con el header `x-apisports-key`

Referencia: <https://www.api-football.com/>

### Sincronización de fixtures

Para sincronizar una temporada deben existir mappings de:

1. competición local → league ID
2. temporada local → año del proveedor
3. cada equipo participante → team ID

Cuando los mappings existen, la sincronización puede crear o actualizar partidos. También puede crear un estadio cuando el fixture trae un venue identificable y guardar su mapping.

Si falta el mapping de uno de los equipos, el fixture se reporta como `team_mapping_missing` y no se crea.

Cada fixture sincronizado conserva además un snapshot normalizado del payload original. Esto permite auditar qué respondió el proveedor sin convertir ese JSON en la fuente canónica del dominio.

### Profundización de un partido

Una vez que un partido tiene mapping de fixture, la sincronización explícita de detalle consulta tres superficies separadas de API-Football:

- eventos del partido
- alineaciones
- estadísticas por equipo

Los jugadores desconocidos se crean con ID interno propio y reciben un `ProviderMapping` de tipo `player`. Las alineaciones también actualizan la relación jugador-equipo cuando es posible.

Los registros importados llevan `source=api-football`. Al repetir un sync, ONCE reemplaza únicamente las filas pertenecientes a esa fuente y conserva eventos, alineaciones o estadísticas creadas manualmente.

Los payloads de eventos, alineaciones y estadísticas quedan guardados en `ProviderSnapshot` como última observación recibida para ese partido.

## Wikidata y Wikimedia Commons

Wikidata se usa como fuente de enriquecimiento y referencias, no como fuente de resultados en vivo.

ONCE consulta entidades conocidas mediante la interfaz `Special:EntityData/QID.json` e identifica sus peticiones con un User-Agent configurable:

```env
WIKIDATA_USER_AGENT=ONCE/0.2 (personal local football catalog)
```

Cuando una entidad tiene imagen principal (`P18`), el backend puede resolver el archivo correspondiente en Wikimedia Commons y leer sus metadatos de licencia, autoría, crédito, dimensiones y MIME. El import crea o actualiza un `MediaAsset` y vincula el QID mediante `ProviderMapping`.

El proceso no descarga ni republica automáticamente la imagen: conserva la URL original y la procedencia para que cada uso visual pueda respetar la licencia concreta del recurso.

Referencias:

- <https://www.wikidata.org/wiki/Wikidata:Data_access>
- <https://www.mediawiki.org/wiki/API:Imageinfo>

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

La importación abierta ya conserva lotes durante 24 horas. Para futuras actualizaciones programadas, las frecuencias propuestas dependen del tipo de dato:

- identidad de equipos/competiciones: caché larga
- calendario futuro: actualización moderada
- partido finalizado: casi inmutable
- partido en vivo: intervalo corto únicamente durante su ventana activa

No se debe consultar todo el universo de un proveedor al cargar una página. La ingestión se hace por competición/temporada o por fixture según necesidad.
