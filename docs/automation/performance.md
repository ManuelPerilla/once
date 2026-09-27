# Rendimiento del piloto

Medición local del 27 de septiembre de 2026, reproducible con [scripts/benchmark_automation.py](../../scripts/benchmark_automation.py). Dataset sintético: 20 competiciones, 400 equipos, 1.000 ediciones y diez eventos por partido. No son datos deportivos reales.

Se compararon lecturas sin ingesta y con diez lectores concurrentes, un auditor y un trabajador real de `SyncEngine`. La descarga se simuló con 20 ms; cada ciclo aplicó diez cambios auditados. Cada perfil ejecutó 500 solicitudes, cien por ruta. PostgreSQL corrió en Docker; las solicitudes atravesaron ASGI TestClient en Windows, **sin NGINX ni navegador**. Es una muestra corta de unos cuatro segundos por perfil, no una prueba prolongada de capacidad ni un compromiso de servicio.

| Escenario con ingesta | Partidos / eventos | p95 de las cinco rutas |
| --- | --- | --- |
| Catálogo mediano | 10.000 / 100.000 | Aproximadamente 91–111 ms |
| Catálogo grande | 100.000 / 1.000.000 | Edición 103,86 ms; detalle 110 ms; competición 130,27 ms; equipo 142,67 ms; en vivo 145,23 ms |

No hubo errores HTTP ni trabajos fallidos: se verificaron sus estados persistidos (4/4 y 5/5 finalizados). El perfil grande sin ingesta tuvo un p95 de 152,06 ms en la lista en vivo; por ello no se declara cumplido un objetivo universal inferior a 150 ms. El proveedor real, la red, NGINX, renderizado y otros procesos del equipo añaden costes que esta medición no incluye.

El artefacto original queda en `.local/benchmarks/automation-20260927.json`, fuera de Git. Incluye p50/p95/p99, tamaños, recursos PostgreSQL y tiempos del trabajador; no contiene claves. Los cambios posteriores de espera SSE, publicación sin escrituras ociosas y frecuencia de heartbeat reducen trabajo de fondo, pero no se les atribuye una mejora numérica no medida.

## Repetir de forma segura

El script **recrea tablas**. Requiere `--allow-disposable-db`, una base cuyo nombre cumpla `once_*_test`, host `localhost` o `127.0.0.1` y un puerto explícito distinto de 5432. No admite la base `vertice_db`. Prepara un PostgreSQL desechable e instala las dependencias de desarrollo antes de consultar:

```sh
python -m scripts.benchmark_automation --help
```

El destino se toma de `TEST_DATABASE_URL`; `--database-url` permite sustituirlo. Configura esa variable con credenciales exclusivas del banco de pruebas y ejecuta:

```sh
python -m scripts.benchmark_automation --allow-disposable-db --sizes 10000,100000 --readers 10 --requests-per-reader 50 --output .local/benchmarks/automation.json
```

El contenedor observado para métricas es `once-sync-qa`, configurable con `--docker-container` para otro nombre `once-…qa`. Ese contenedor debe existir previamente; el script no inicia servicios. Los perfiles crecen de 10.000 a 100.000 partidos sin reducir el conjunto entre fases. La reproducción no consulta proveedores, modifica repositorios ni genera commits.

Las pruebas de [protección del banco de carga](../../tests/test_benchmark_guard.py) comprueban el rechazo de una base de trabajo, un host remoto, el puerto habitual y la falta de autorización explícita. Nunca uses la instalación de trabajo como banco de carga.

## Lectura de los recursos

La base del perfil grande terminó en aproximadamente 220,65 MB y PostgreSQL registró cero interbloqueos. La instantánea de Docker tomada después del perfil indicó 212,9 MiB de memoria para PostgreSQL. Son medidas puntuales; no incluyen el proceso de API en Windows, toda la máquina virtual de Docker ni máximos de CPU/RAM durante el ensayo. Los contadores acumulados de `pg_stat_database`, incluidos rollbacks de lecturas cerradas, no equivalen a errores de las peticiones.

El generador confirma los estados finales de los trabajos además de contar ciclos: un intento fallido no se presenta como una escritura correcta. El informe original recibió esa comprobación inmediatamente después de la ejecución; las nuevas ejecuciones ya la incorporan automáticamente.

Antes de comprometer un tiempo de respuesta en producción faltan ensayos prolongados con tráfico representativo, interfaz y proxy reales, recursos del servidor elegido y cobertura externa disponible. Los índices y límites actuales evitan cargar todo el historial o todos los detalles al abrir una lista.
