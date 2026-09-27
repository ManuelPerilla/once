# Integridad del dominio, clasificaciones y auditoría

Estado: implementado; las pruebas unitarias y de API de este módulo pasan en SQLite y PostgreSQL 15. La disponibilidad de una fuente y la revisión de un reglamento concreto son condiciones adicionales para activar una competición.

## Identidades y participación

Los IDs canónicos existentes se conservan. `ProviderMapping.external_scope` forma parte de la identidad externa junto a proveedor, tipo e ID. Una temporada anual de API-Football utiliza `league:<id externo>`; las ediciones locales requieren además una correspondencia de fase/ronda comprobada. El año por sí solo no identifica una temporada entre ligas.

La relación heredada `Participacion` sigue describiendo la matrícula general. `ParticipacionTemporada` exige edición y procedencia; `ParticipacionFase` y `ParticipacionGrupo` delimitan tablas posteriores. No se copian las matrículas actuales a temporadas históricas durante la migración.

Un marcador desconocido se representa con `null`; cero significa cero real. Los estados incluyen programado, en vivo, finalizado, aplazado, suspendido, cancelado, abandonado, adjudicado y desconocido. `estado_fuente` conserva la señal original. La base rechaza goles negativos y partidos de un equipo contra sí mismo.

## Cambios automáticos y correcciones

`src.audit.service.apply_source_changes` compara diferencias dentro de la transacción del llamador. Mantiene una versión de ficha, autoridad por campo y fecha de observación. Una respuesta antigua no revierte otra nueva; una fuente diferente o una corrección protegida generan una incidencia en lugar de sobrescribir datos. Repetir el mismo valor no agrega otro cambio al historial.

`correct_field` exige usuario, motivo y versión esperada. Si otra persona cambió la ficha, devuelve conflicto y exige releerla. Una corrección protege solo el campo afectado. `release_field` vuelve a aceptar futuras observaciones; no aplica automáticamente una propuesta antigua.

Las incidencias repetidas se agrupan por causa/campo/fuente. Resolver una incidencia registra la decisión y no acepta su propuesta. La misma propuesta no vuelve a abrirla; un valor externo diferente sí puede abrir otra revisión. Esto permite rechazar de forma estable un valor erróneo.

La migración 0005 protege todos los campos existentes de origen desconocido y los detalles manuales sin fuente. No cambia sus valores. Las temporadas cuyo vínculo de competición externa no es inequívoco quedan identificadas con un contexto heredado y una incidencia.

Los registros `AuditChange` son de solo anexado mediante el servicio ORM y, en instalaciones migradas de PostgreSQL, un disparador que rechaza UPDATE/DELETE. El administrador propietario de la base puede modificar su estructura: esto no representa almacenamiento WORM ni una certificación de auditoría. Las copias verificadas siguen siendo necesarias.

### API para revisión

- `GET /audit/entities/{tipo}/{id}`: ficha, versión, campos corregibles, protección, fuente y últimos 50 cambios.
- `PATCH /audit/entities/{tipo}/{id}/{campo}`: `{value, reason, expected_version}`.
- `POST /audit/entities/{tipo}/{id}/{campo}/release`: `{reason, expected_version}`.
- `GET /audit/changes`: historial paginado, filtrable por tipo e ID.
- `GET /audit/issues`: incidencias paginadas, filtrables por estado y entidad.
- `POST /audit/issues/{id}/resolve`: `{reason}`; registra revisión sin cambiar el dato canónico.

Los cambios de relaciones e identidades requieren sus operaciones específicas; el editor de campos no permite cambiar libremente claves externas.

Los vínculos de proveedor creados desde administración y los recursos visuales importados registran actor, motivo y versión de la ficha. Repetir una importación idéntica no duplica el historial; cambiar licencia o atribución sí conserva el valor anterior. `DELETE /providers/mappings/{id}` elimina únicamente el vínculo externo, exige la sincronización global pausada y conserva la entidad canónica con su historial. Estas operaciones requieren el permiso de gestión de fuentes.

## Clasificaciones

Las tablas calculadas se conservan como proyecciones por edición, fase y grupo. Cada proyección identifica la versión del reglamento y una huella de sus entradas. Repetir un cálculo sin cambios conserva la proyección. Las reconstrucciones de una edición se serializan para que dos correcciones simultáneas no publiquen una tabla que omita una de ellas.

`StandingRule` conserva versiones de reglas con nombre, enlace a la fuente, autor de la revisión y estado verificado. No se habilita el cálculo de una regla no revisada. Una tabla acumulada declara las fases incluidas; las fases con grupos exigen elegir grupo. Una tabla con participantes inconsistentes se retira de la respuesta vigente y genera una incidencia.

El motor admite puntos por victoria/empate/derrota, diferencia de goles, goles a favor, victorias, goles/victorias fuera de casa y criterios de enfrentamientos entre equipos empatados. Los empates no resueltos conservan la misma posición; el orden visual por nombre no se presenta como un desempate deportivo. Los resultados adjudicados solo cuentan si la regla lo establece. Las sanciones se agregan como ajustes con fuente y motivo; una rectificación se registra con otro ajuste compensatorio.

La tabla publicada por el proveedor se almacena separada del cálculo de ONCE. Se validan participantes, unicidad, contadores y coherencia de partidos; se conservan correcciones A→B→A como observaciones posteriores. Ninguna discrepancia modifica silenciosamente el reglamento o el cálculo local.

Las tablas de promedios y reglas ajenas al motor existente requieren implementación y pruebas específicas antes de activarse. No se infieren por año, país ni nombre de competición.

### API deportiva

- `GET /public/temporadas/{id}/context`: fases y grupos de la edición.
- `GET /public/temporadas/{id}/clasificacion?phase_id=…&group_id=…`: estado, reglamento, cálculo ONCE y tabla de la fuente separados.
- `GET /football/temporadas/{id}/participantes` y `POST` con `{equipo_id, fase_id?, grupo_id?, reason}`.
- `GET /football/reglas?season_id=…` y `POST /football/reglas` con ámbito, nombre, fuente, configuración y revisión explícita.
- `POST /football/ajustes`: ámbito, equipo, puntos, motivo y enlace a la decisión.

No hay reglamento colombiano certificado por defecto. El ejemplo genérico 3/1/0 no equivale a verificar todos los formatos, desempates, ventanas de reclasificación y modificaciones de DIMAYOR.

## Personas y permisos

La cuenta configurada en el entorno conserva permisos de administrador y sirve como acceso de recuperación. Las cuentas nominales se crean desde `POST /accounts`; sus contraseñas se almacenan con el mismo hash PBKDF2 empleado por la aplicación y nunca se devuelven en listados ni auditoría.

| Perfil | Facultades |
| --- | --- |
| Auditor | Consultar fichas, incidencias, historial y estado operativo |
| Editor | Auditar, corregir y mantener datos deportivos |
| Operador | Auditar, pausar, reanudar y ejecutar ámbitos existentes |
| Administrador | Todas las anteriores, fuentes, cuotas y gestión de personas |

La autorización se comprueba en el servidor, incluidas las rutas heredadas. Los operadores pueden cambiar el modo de un ámbito, pero no su selector ni cuotas. Las consultas externas de previsualización están reservadas a la gestión de fuentes. Desactivar una cuenta o cambiar su contraseña/perfil revoca sus sesiones anteriores mediante una versión de credencial comprobada en cada petición.

`GET /auth/session` devuelve el usuario, perfil y permisos efectivos. `GET /accounts` lista cuentas; `PATCH /accounts/{id}` cambia perfil, estado, nombre visible o contraseña con un motivo. No se borra el historial de una persona cuando deja de tener acceso.

## Migración y comprobación

Las migraciones 0005 y 0007 preservan identidades, valores heredados y acceso de recuperación. Su reversión automática se rechaza porque eliminaría protecciones, historia y cuentas: para retroceder se restaura una copia anterior verificada junto con la versión correspondiente del código.

Las pruebas de [dominio](../../tests/test_automation_domain.py), [API, cuentas y correcciones](../../tests/test_accounts_audit_api.py) y [auditoría de fuentes y recursos visuales](../../tests/test_provider_audit.py) cubren ámbitos de temporada, reintentos idempotentes, respuestas antiguas, marcadores desconocidos, reglas/fases/grupos, sanciones, separación de tablas, actor nominal, permisos y revocación. El ensayo de migración PostgreSQL se ejecutó en una base desechable con datos heredados; confirmó el contexto de temporada, las protecciones, la ausencia de matrículas inventadas y el rechazo de actualizaciones directas al historial.
