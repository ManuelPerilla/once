# Modelo de datos implementado

Las definiciones están en [src/models.py](../src/models.py), [src/sync/models.py](../src/sync/models.py) y [src/accounts/models.py](../src/accounts/models.py). Las [migraciones](../migrations/versions) conservan los IDs existentes. El [modelo conceptual anterior](archive/data.md) es un archivo histórico.

| Entidad | Relaciones y uso |
| --- | --- |
| Confederacion | Agrupa equipos y competiciones; no representa automáticamente federaciones u organizadores |
| Competicion / Equipo | Torneos, clubes y selecciones, país y confederación opcional |
| Participacion | Matrícula general equipo–competición, conservada por compatibilidad |
| Temporada / Fase / Grupo | Edición de una competición, fases y grupos con ámbitos explícitos |
| ParticipacionTemporada | Participación en una edición, fuente y comprobación; no se infiere del catálogo actual |
| ParticipacionFase / ParticipacionGrupo | Equipos de un ámbito posterior, con procedencia |
| Estadio | Sede opcional con ubicación y coordenadas |
| Partido | Competición, edición, fase, grupo, equipos, fecha UTC, jornada publicada, marcador y estados local/original |
| EstadisticasPartido / EventoPartido / AlineacionPartido | Detalle por partido con fuente y clave estable; la ausencia en una respuesta no lo elimina |
| Jugador / JugadorEquipo | Identidad y pertenencia temporal; distinta de participar en una alineación histórica |
| ProviderMapping | Identidad externa formada por proveedor, tipo, ID y contexto, vinculada al ID local |
| ProviderSnapshot / CatalogImportBatch | Última observación por categoría y lotes revisados de datos abiertos |
| MediaAsset | URL original/local, autoría, licencia, atribución y verificación |
| EntityRevision / FieldState | Versión de ficha, autoridad, fecha de observación y protección por campo |
| AuditChange / DataIssue | Historial de cambios y decisiones, y discrepancias agrupadas para revisión |
| StandingRule / StandingAdjustment | Versiones de reglamento y ajustes deportivos con fuente y actor |
| StandingProjection / OfficialStandingSnapshot | Cálculo ONCE reproducible y tabla publicada por la fuente, conservados por separado |
| SyncControl / SyncScope | Pausa global y configuración de cada ámbito, con versiones de control |
| SyncJob / SyncBudget / SyncHeartbeat | Trabajo durable, reservas temporales, cuota y actividad del trabajador |
| SyncObservation / SyncIssue / SyncHistory / SyncNotification | Observaciones deduplicadas, incidencias operativas, ejecuciones y notificaciones confirmadas |
| AdminAccount | Personas identificadas, perfiles, hash de contraseña y versión para revocar sesiones |

## Invariantes

Los equipos de un partido deben ser distintos. Los goles pueden ser desconocidos (`null`); si existen, no pueden ser negativos. El estado distingue programado, en vivo, finalizado, aplazado, suspendido, cancelado, abandonado, adjudicado y desconocido. El código del proveedor se conserva en `estado_fuente`.

La temporada pertenece a una competición, la fase a esa temporada y el grupo a esa fase. La compatibilidad manual comprueba clubes frente a selecciones, país de torneos nacionales y confederación cuando corresponda. La identidad de temporada externa incluye al menos competición y año; el selector de consulta no sustituye la identidad de una edición local.

La fecha se guarda como instante UTC. Las tablas usan participantes explícitos, resultados finalizados con marcador conocido y reglas revisadas. Incluir resultados adjudicados requiere una opción expresa de la regla. Una tabla acumulada declara sus fases; una fase con grupos requiere seleccionar grupo. Las sanciones se registran como ajustes, sin reescribir resultados para simularlas.

Los empates no resueltos mantienen igual posición. La ordenación visual estable por nombre no se considera un desempate deportivo. Las tablas de promedios y reglamentos ajenos a las capacidades actuales requieren extensión y comprobación antes de publicarse.

## Migración, correcciones y procedencia

La migración 0005 preserva campos existentes de origen desconocido como protegidos. Los logos vacíos representan ausencia y pueden enriquecerse; un cero ya registrado no se interpreta retrospectivamente como desconocido. No se inventan participantes históricos. Los vínculos de temporada ambiguos generan una incidencia para revisión.

Los proveedores escriben diferencias autorizadas, sin revertir observaciones más recientes ni correcciones protegidas. Una corrección manual precisa actor, motivo y versión esperada. El historial registra valores anteriores/nuevos y se anexa; liberar un campo permite futuras observaciones, sin aplicar silenciosamente una propuesta antigua.

Los mappings son referencias polimórficas, no claves foráneas hacia todas las tablas. Una referencia cuyo destino desapareció se conserva como incidencia. Los detalles, matrículas temporales, reglas y ajustes tienen relaciones concretas; eliminar una identidad con historia requiere resolver esas dependencias, no borrar silenciosamente temporadas enteras. La auditoría conserva la identidad del registro incluso cuando este ya no existe.

## Retención y recuperación

Los cuerpos idénticos de una observación se deduplican; las filas de cambio canónico y el historial operativo tienen propósitos diferentes. La retención del motor no equivale a conservar eternamente cada respuesta HTTP. Los límites configurados y procedimientos de mantenimiento se describen en el [manual de automatización](automation.md).

Las copias incluyen esquema, datos, cuentas, correcciones, reglas y referencias a imágenes. El volumen de medios se respalda por separado con manifiesto común. Al restaurar, la automatización queda pausada y las reservas de procesos anteriores se invalidan. Véase [traslado y restauración](deployment/transfer.md).

Los SQL de [data/legacy](../data/legacy) no sustituyen una copia actual ni se ejecutan como migración. El arranque aplica Alembic antes de iniciar la aplicación y el trabajador.
