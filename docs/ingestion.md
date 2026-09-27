# Alimentar ONCE con datos abiertos

## Decisión inicial

Empezamos sin coste de suscripción, con catálogos pequeños que se puedan comprobar y ampliar. La identidad local pertenece a ONCE: los conectores traducen observaciones externas al dominio. Los nombres comerciales, traducciones y cambios de proveedor no cambian el ID de un equipo.

El flujo es: **fuente → lote conservado → normalización → revisión de identidades → transacción → catálogo → API pública**. La página pública consulta PostgreSQL; no hace consultas a Wikidata por cada visita.

## Implementado

- Colección de las seis confederaciones continentales.
- Colección inicial de Colombia: CONMEBOL, Primera A, Primera B, Copa Colombia y 17 clubes. Es una selección de identidades, no una lista completa ni una clasificación de participantes actuales.
- Una petición `wbgetentities` por colección, con hasta 50 entidades y sus declaraciones. Se conservan referencias, revisión de origen, fecha de consulta y licencia CC0 de los datos estructurados.
- Caché persistente de 24 horas en PostgreSQL, que sobrevive al reinicio de Docker. Una nueva vista previa recalcula coincidencias con el catálogo actual sin volver a pedir datos a la fuente durante ese plazo.
- Comprobación de identidad, vínculo al fútbol y país esperado. Los datos incompletos quedan bloqueados.
- Comparación de nombres y alias, incluyendo acentos y sufijos comerciales. Las coincidencias aproximadas son sugerencias para revisión, nunca fusiones automáticas.
- Creación o vínculo de entidades con IDs internos, `ProviderMapping` y `ProviderSnapshot`. Los nombres, imágenes y correcciones de los registros existentes se conservan.
- Aplicación atómica e idempotente: un conflicto revierte todo el lote. Las importaciones se serializan mediante un bloqueo transaccional en PostgreSQL; si cambian las coincidencias hay que revisar otra vez.
- Gestión explícita de 429/maxlag: se comunica la limitación y no se lanza una cascada de reintentos. El botón de preparación hace una consulta interactiva acotada; siguiendo la [política de MediaWiki](https://www.mediawiki.org/wiki/Manual:Maxlag_parameter), omite `maxlag`. El cliente conserva `maxlag=5` por defecto para tareas no interactivas. Ambas modalidades respetan los errores 429.
- Panel en **Administrador → Datos → Traer información → Añadir equipos y torneos**.

No hace falta una clave de API ni una cuenta de Wikidata. La importación no crea temporadas, matrículas, resultados, plantillas ni clasificaciones. Las imágenes tienen licencias separadas y conservan el flujo específico de Commons.

### Escudos sin sustituir correcciones locales

Después de crear o conectar las fichas, **Buscar escudos e imágenes** usa sus identidades de Wikidata para consultar Wikimedia Commons. El administrador ve el escudo y su licencia antes de guardarlo. Las selecciones usan la misma entidad `team` que los clubes: no se infiere su escudo a partir de la bandera del país.

Los escudos se identifican por `P154`, se guardan con autoría y procedencia en `MediaAsset` y solo completan imágenes ausentes. Una fotografía `P18` no se usa como escudo. No se amplía el lote de identidades con imágenes sin revisar ni se ejecutan consultas externas en las páginas públicas. La atribución pública se obtiene en una consulta local para todo el catálogo visual. Consulta [el contrato y las condiciones por archivo](providers.md#escudos-con-revisión-antes-de-publicar).

### Separación del código

| Pieza | Responsabilidad |
| --- | --- |
| `src/providers/wikidata.py` | Transporte y validación de la respuesta externa |
| `src/catalog/collections.py` | Descubrimiento acotado: QIDs y clasificación revisada de las colecciones |
| `src/catalog/service.py` | Normalización, candidatos, dependencias y transacción |
| `src/catalog/schemas.py` | Contrato de las decisiones del operador |
| `src/catalog/routes.py` | Autenticación y traducción de errores a HTTP |
| `CatalogImportBatch` | Respuesta conservada y último resultado de aplicación |
| `frontend/src/admin/CatalogImport.jsx` | Revisión y selección de la importación |

Las colecciones contienen identificadores revisados, no copias permanentes de nombres, escudos o resultados. Para ampliar países se incorporan colecciones y reglas verificadas. El descubrimiento automático de entidades arbitrarias por SPARQL es una fase posterior: requiere resolver categorías, clubes desaparecidos, filiales, fútbol femenino y entidades ambiguas.

### API

Todos los endpoints requieren sesión administrativa:

- `GET /catalog/collections`: colecciones disponibles, sin consultas externas.
- `POST /catalog/prepare/{collection}`: obtiene o reutiliza el lote y devuelve el plan. Conserva el lote, pero no modifica el catálogo deportivo.
- `POST /catalog/batches/{id}/apply`: aplica únicamente las decisiones recibidas contra las observaciones guardadas. Los lotes caducan a las 24 horas; no se vuelve a consultar internet durante la aplicación.

Una decisión contiene el QID, la acción (`create`, `link`, `skip`), el estado observado en la vista previa y, para vincular, el ID local. Un vínculo puede elegirse entre las entidades compatibles; no se permite asignar dos identidades a un mismo registro en el lote ni sustituir otro QID ya vinculado. Los QIDs conocidos se reutilizan al repetir la operación.

## Siguientes etapas propuestas

1. **Modelo temporal:** añadir participación por temporada sin inventar a qué edición pertenecen las matrículas antiguas. Mantener diferenciados competición, edición, fase y jornada. Las plantillas también necesitan intervalos y contexto de temporada.
2. **Organización deportiva:** separar federación, confederación y país; una ubicación geográfica no determina por sí sola elegibilidad. Los torneos mundiales no pertenecen a una confederación continental. La semilla nueva ya corrige esa relación del Mundial; las bases existentes requieren revisión explícita de sus datos.
3. **Más fuentes abiertas:** evaluar cobertura y licencia por competición y temporada, no solo por proveedor. Calendarios oficiales estructurados o archivos abiertos se incorporarán con su propio adaptador. Una tabla visible en internet no implica permiso de reutilización.
4. **Actualización en segundo plano:** cuando los lotes lo necesiten, añadir un worker en Compose, trabajos persistidos en PostgreSQL, límites por fuente, reintentos con `Retry-After`, checkpoints y presupuesto de consultas. No ejecutar sincronizaciones dentro del arranque de cada réplica de la API.
5. **Procedencia por campo:** gestionar quién aporta cada nombre, fecha o relación, conservar correcciones editoriales y revisar contradicciones. Una fuente no debe sobrescribir campos propiedad de otra sin una regla explícita.
6. **Operación:** medir antigüedad y cobertura de datos, pendientes, conflictos y coste de importación; definir retención de lotes y copias de seguridad al crecer.

No incorporamos un motor de grafos, Redis ni microservicios para este primer catálogo. Las relaciones actuales caben en PostgreSQL y el servicio de importación está separado para poder evolucionar.

## Fuentes consultadas

- [Wikidata: acceso a datos y buenas prácticas](https://www.wikidata.org/wiki/Wikidata:Data_access/en): datos estructurados CC0, acceso por lotes, User-Agent, maxlag y límites.
- [Wikidata: descargas](https://www.wikidata.org/wiki/Wikidata:Database_download): los volcados masivos tienen sentido a otra escala; no son necesarios para estos catálogos.
- [API-Football: cobertura](https://www.api-football.com/coverage): integración existente y opcional; la cobertura depende de temporada y encuentro.
- [API-Football: condiciones](https://www.api-football.com/terms): límites de redistribución y derechos que se deben comprobar antes de un uso comercial.

La presencia de una afirmación en Wikidata no garantiza que esté completa o actualizada. Esta primera carga incorpora identidades revisables y conserva el contenido de origen para poder corregirlas.

## Verificación

`tests/test_catalog_import.py` comprueba autenticación, caché, procedencia, vínculos, conservación de campos manuales, duplicados, datos incompletos, caducidad, cambios desde la vista previa y reversión de errores. Usa respuestas controladas y no depende de internet.

`tests/test_wikidata_media.py` verifica la prioridad de los escudos sobre fotografías, la caché, las URL y licencias, los límites del proveedor, la confirmación del archivo revisado, la conservación de imágenes manuales y la atribución pública solo de recursos seleccionados.

`frontend/e2e/catalog.spec.js` prueba la pantalla con Wikidata real y PostgreSQL detrás de NGINX. Es optativa: requiere `CATALOG_LIVE_TEST=1` además de las variables `SMOKE_*` de una instancia desechable. No debe apuntar a la base de trabajo. Las pruebas de migración comprueban también la creación de la tabla de lotes desde una instalación legacy.
