# Modelo de datos implementado

La definición vigente está en [src/models.py](../src/models.py); las revisiones están en [migrations/versions](../migrations/versions). El [modelo conceptual anterior](archive/data.md) se conserva como propuesta histórica.

| Entidad | Relaciones y uso |
| --- | --- |
| Confederacion | Agrupa equipos y competiciones; su vínculo puede estar vacío. |
| Competicion | Tiene tipo, país, equipos, temporadas y partidos. Un torneo global no requiere confederación. |
| Equipo | Club o selección; puede participar en varias competiciones. |
| Participacion | Relación equipo–competición. Actualmente no distingue temporada. |
| Temporada / Fase | La temporada pertenece a una competición; la fase pertenece a una temporada. |
| Estadio | Sede opcional con ubicación y coordenadas. |
| Partido | Local, visitante, competición, fecha UTC, jornada, marcador, estado y contexto opcional. |
| EstadisticasPartido | Posesión y tiros a puerta; procedencia opcional. |
| EventoPartido | Tipo, minuto, tiempo añadido, equipo y participantes opcionales. |
| AlineacionPartido | Jugador, equipo, posición, dorsal y condición de titular. |
| Jugador / JugadorEquipo | Identidad del jugador y modelo de pertenencia temporal; no hay editor completo de plantillas. |
| ProviderMapping | Identificador externo → ID local, con fuente y verificación. |
| ProviderSnapshot | Última observación por proveedor, entidad y tipo de dato. |
| CatalogImportBatch | Lote de importación revisable, fecha, observaciones y último resultado. |
| MediaAsset | Recurso visual con URL, autor, licencia, crédito y metadatos. |

## Reglas que se comprueban

Un club no entra en un torneo de selecciones, y una selección no entra en uno de clubes. Los torneos nacionales requieren país y solo aceptan equipos de ese país. Si el torneo tiene confederación, el equipo debe compartirla.

Para registrar un partido, ambos equipos deben existir, ser distintos, compatibles y estar matriculados. La temporada debe pertenecer al torneo y la fase a la temporada indicada. El estadio debe existir si se especifica.

Las fechas se interpretan en la zona del dispositivo al introducirlas y se almacenan como instantes UTC. Las clasificaciones usan encuentros finalizados y el filtro de temporada cuando se solicita; la matrícula sigue siendo general, por lo que no constituye aún una tabla histórica completa de participantes por edición.

## Eliminación y procedencia

Al eliminar una confederación se conservan sus equipos y competiciones sin esa asociación. Al eliminar equipos o competiciones se conservan encuentros con referencias vacías, conforme al comportamiento actual. Eliminar un partido elimina sus estadísticas, eventos y alineaciones.

Los mappings son referencias genéricas, no claves foráneas hacia varias tablas. Si una entidad vinculada desaparece, la importación la marca como conflicto para revisión. La política de retención de todos los artefactos externos todavía necesita evolucionar.

Los SQL de [data/legacy](../data/legacy) son archivos históricos. El arranque usa Alembic y el seed del código; esos SQL no se ejecutan ni reemplazan una copia actual de PostgreSQL.
