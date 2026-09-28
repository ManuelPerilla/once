# Hitos de ONCE

Este registro distingue entregas comprobadas de propuestas. «Verificado localmente» describe una ejecución concreta; no certifica disponibilidad futura ni reemplaza las pruebas de cambios posteriores. Ninguno de estos estados implica publicación en GitHub.

## Entregas verificadas

| Fecha | Entrega | Estado y evidencia |
| --- | --- | --- |
| 2026-09-27 | Reorganización técnica y operación con Docker | Verificada localmente. [Arquitectura](architecture.md), [despliegue](deployment/local.md), [transferencia](deployment/transfer.md) y registro de pruebas en [desarrollo](development.md) |
| 2026-09-27 | Rediseño, lenguaje administrativo y presentación de escudos | Verificado localmente. 100 pruebas de API en SQLite y otras 100 en PostgreSQL, 27 unitarias de frontend y 13 recorridos de navegador. [Registro de ejecución](development.md) y [experiencia](ux.md) |
| 2026-09-27 | Separación de módulos, filtros, plantillas y control de datos | Verificada localmente. 121 pruebas de API en SQLite y otras 121 en PostgreSQL, 38 unitarias de frontend y 19 recorridos de navegador. [Registro de ejecución](development.md), [administración](administracion.md) y [control](control-datos.md) |
| 2026-09-27 | Piloto automático colombiano y operación auditada | Desplegado en Docker local con API, trabajador, PostgreSQL y frontend sanos. Archivo 2025 importado: 200 encuentros nuevos, sin duplicar las identidades revisadas; 33 marcadores desconocidos conservados. Copia previa, migración y transferencia con medios verificadas. [Operación](automation.md), [pruebas](development.md) y [rendimiento](automation/performance.md) |
| 2026-09-27 | API-Football conectado y archivo colombiano real | Quince calendarios de 2022–2024: 2.890 encuentros importados y 35 tablas publicadas. Cuenta Free comprobada, cuota compartida, detalle progresivo y procedencia visible. Una tabla de Primera B 2023 conserva revisión de identidad. [Registro de ejecución](development.md) y [despliegue en servidor](deployment/server.md) |
| 2026-09-27 | Ocho manuales y ciclo de desarrollo reproducible | Colección Diátaxis, Makefile y ayudante multiplataforma con guardas QA. 320 pruebas Python aprobadas y cuatro omitidas por requerir PostgreSQL; 53 unitarias frontend. Arranque manual PostgreSQL, enlaces y ejemplo de pipeline comprobados. [Entrada](../README.md), [contribución](../CONTRIBUTING.md) y [registro de ejecución](development.md) |
| 2026-09-27 | Acceso LAN portable por comando | Modos compartir, local y consulta; lanzador Windows y detección de IP sin fijarla al equipo. 379 pruebas Python aprobadas, cuatro omitidas; selección de 70 aprobada también en Linux. Aplicado en Docker local conservando configuración y trabajador. [Manual de red](deployment/network.md) y [alcance de las pruebas](development.md#red-local-portable-27-de-septiembre-de-2026) |

Los resultados corresponden a cada entrega y no se suman entre sí. Las entregas de automatización y conexión incluyen el motor de sincronización automática.

## Conexión real con API-Football (27 de septiembre de 2026)

La cuenta Free se comprobó con la API real: 100 consultas diarias, acceso anunciado a 2022–2024 y rechazo de 2026. ONCE incorpora comprobación de cuenta sin exponer su clave ni datos personales, preparación de las cinco competiciones colombianas, importación de ediciones y fases, tablas oficiales separadas y enriquecimiento progresivo de partidos. La carga inicial y sus recuentos finales se registran en [desarrollo](development.md).

La prueba real obligó a distinguir capacidades por plan: Free admite el detalle de un partido por consulta y rechaza el parámetro de múltiples identificadores. Los límites se comparten con las herramientas manuales y se aplica espaciado persistente entre consultas. Esta entrega no habilita resultados actuales ni promete descargar todo el detalle histórico en un solo día. El [manual de servidor](deployment/server.md) añade HTTPS, proxy, transferencia y operación sin exponer PostgreSQL.

## Automatización: implementación del piloto

El usuario ha priorizado fútbol colombiano y presupuesto inicial de datos de cero. El [diseño del piloto](proposals/sincronizacion-colombia.md) conserva la justificación y los criterios de aceptación. Su implementación añade un trabajador durable, control de pausa, auditoría, correcciones protegidas y carga por fuentes. Los estados siguientes distinguen código disponible, pruebas ejecutadas y condiciones externas que todavía deben acreditarse.

| Hito | Estado | Evidencia y límites |
| --- | --- | --- |
| H0 · Cobertura y línea base | Fuentes gratuitas históricas verificadas | OpenFootball ofrece archivos CC0 de 2023–2025; el archivo de 2025 tiene 200 partidos y 33 resultados ausentes. API-Football Free confirmó acceso a 2022–2024 y rechazó 2026. No se presenta esa cobertura como directo actual |
| H1 · Integridad y correcciones | Implementado; pruebas de dominio | Identidades con contexto, participación por edición/fase/grupo, marcadores desconocidos, cuentas identificadas y correcciones protegidas. [Dominio y auditoría](automation/domain-and-audit.md) |
| H2 · Motor controlable | Implementado; fallos y concurrencia comprobados | Cola persistente, reservas, cuota compartida, pausa que impide publicar respuestas antiguas, recuperación y cursor posterior al commit. Pruebas SQLite y PostgreSQL, incluidas transacciones concurrentes |
| H3 · Catálogo y calendario automáticos | Importados en la instalación principal | 200 encuentros desde OpenFootball 2025 y 2.890 desde quince calendarios API-Football de 2022–2024; identidades revisadas y ediciones separadas. Las repeticiones comprobadas no duplicaron datos. El descubrimiento prepara perfiles pausados cuando falta verificar el acceso |
| H4 · Tablas colombianas | 35 tablas publicadas importadas; una pendiente de revisión | La clasificación publicada se separa del cálculo ONCE, que exige reglas verificadas por ámbito. Fases y grupos contrastados con participantes; Clausura de Primera B 2023 conserva una incidencia de identidad sin fusionar clubes |
| H5 · Actualización continua y rendimiento | Transporte y cadencia implementados; carga medida | SSE con recuperación de cursor, lecturas paginadas, caché de metadatos y frecuencia según partidos/cuota. [Ensayo de 100.000 partidos y un millón de eventos](automation/performance.md). No equivale a disponibilidad de un proveedor en directo |
| H6 · Operación transferible | Despliegue y traslado verificados | Cuatro servicios sanos en la instalación local, migración desde `0004` a `0007`, backup/restauración de PostgreSQL y medios en otro proyecto vacío. [Registro](development.md). Las instalaciones nuevas empiezan pausadas y las restauraciones invalidan trabajos anteriores |

La validación por módulos no sustituye la comprobación integrada de la entrega. Al actualizar este registro deben anotarse fecha, alcance, revisión, pruebas y límites. Un fallo de disponibilidad externa no se convierte en un resultado deportivo; la ausencia de una fuente actual no se presenta como sincronización en vivo.
