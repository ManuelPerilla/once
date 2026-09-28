# ONCE · El fútbol conectado, del dato al juego ⚽

[![Build manual](https://img.shields.io/badge/build-ejecuci%C3%B3n_manual-19324d)](.github/workflows/ci.yml)
[![Cobertura sin medir](https://img.shields.io/badge/cobertura-sin_porcentaje_medido-64748b)](TESTING.md)
[![QA local](https://img.shields.io/badge/QA-verificada_localmente-a3e635)](docs/development.md)
[![Versionado Git](https://img.shields.io/badge/versi%C3%B3n-revisi%C3%B3n_Git-19324d)](CONTRIBUTING.md)

ONCE conecta partidos, equipos, competiciones y jugadores en una experiencia de fútbol que empieza en Colombia.<br>
FastAPI y PostgreSQL convierten fuentes externas en datos locales con identidad, procedencia y correcciones auditadas.<br>
Docker mantiene el sistema transportable; los administradores revisan excepciones y los lectores exploran desde móvil o escritorio.

> **El lobby · 5 minutos.** Tu primera misión es abrir una pantalla real. La explicación de por qué existe el proyecto está en [CONTEXT.md](CONTEXT.md).

## 🎮 Una ventana al sistema

Vista ilustrada en Markdown: representa la instalación comprobada el 27-09-2026, no una captura ni un GIF real.

```text
┌─ ONCE / CENTRO DE OPERACIONES ────────────────────────┐
│ Catálogo → Calendarios → Clasificaciones → Auditoría │
│                                                     │
│  5 competiciones API · 2022–2024 · 2.890 encuentros   │
│  35 tablas publicadas · detalle en carga progresiva  │
│                                                     │
│  Fuente → Observación → Validación → Datos locales  │
│                       ↘ Revisión si hay ambigüedad  │
│                                                     │
│  [Explorar partidos]   [Controlar sincronización]    │
└─────────────────────────────────────────────────────┘
```

[**Abrir ONCE local →**](http://localhost/explore) · [Administrar](http://localhost/) · [Demo identificada](http://localhost/explore?demo=1) · [API interactiva](http://localhost/api/docs)

Esos enlaces apuntan a tu equipo y requieren el sistema encendido. La demo usa datos ficticios separados; un clon nuevo no incluye la base privada del piloto.

## 🚀 Botón de pánico: encender el estadio

Con Docker funcionando, desde la raíz y **con un `.env` ya configurado**:

```sh
docker compose up -d
```

Para una primera instalación completa:

```sh
python -m src.configure
docker compose up --build -d --wait
docker compose ps
```

El asistente necesita Python 3.12 y solicita credenciales por entrada interactiva. No sobrescribe un `.env` existente. En Linux puedes usar `python3`. Si trasladas datos existentes, entra primero a [recuperación y traslado](docs/deployment/transfer.md); arrancar la API sobre el destino crearía tablas antes de restaurar la copia.

Tu señal de victoria: `api`, `db`, `frontend` y `worker` aparecen sanos, y `http://localhost/api/health` devuelve:

```json
{"status":"ok"}
```

En Windows puedes usar [iniciar-once.cmd](iniciar-once.cmd). Si algo falla, ve a [la sala de emergencias](TROUBLESHOOTING.md); borrar el volumen no es un paso de diagnóstico.

### Compartir la partida en tu red

Con Python 3.12 y Docker funcionando, desde la raíz:

```sh
python -m scripts.network lan
```

En Windows también puedes abrir [compartir-once.cmd](compartir-once.cmd). El asistente prepara la configuración si falta, construye las imágenes con la caché disponible y muestra las direcciones de tu equipo; no necesitas fijar una IP en el proyecto. Abre la dirección mostrada, con `/explore`, desde un dispositivo de la misma red. El equipo anfitrión y Docker deben permanecer encendidos.

Usa `python -m scripts.network lan --port 8080` si necesitas otro puerto, `python -m scripts.network status` para consultar y `python -m scripts.network local` para volver al acceso exclusivo del anfitrión. La opción `--firewall` permite gestionar la regla de Windows desde una terminal administradora; no es necesaria si el acceso ya funciona. Los atajos son `make lan`, `make local` y `make network-status`, o sus equivalentes `python -m scripts.dev`.

Este modo usa HTTP local; la detección de una dirección no garantiza que el router o el firewall permitan conectarse. Clonar el código no copia los datos, y dos clones en el mismo Docker no crean volúmenes independientes por cambiar de carpeta. Consulta el [manual de red local](docs/deployment/network.md) para permisos, comprobación, vuelta atrás y traslado.

## Qué puedes hacer hoy

| Zona | Capacidad actual |
| --- | --- |
| Catálogo | Confederaciones, competiciones, equipos, temporadas, fases, estadios y jugadores |
| Exploración | Listados paginados y fichas relacionadas; estadísticas, eventos y alineaciones cuando existen |
| Organización | Participación por edición, fase y grupo; filtros con contexto |
| Fuentes | Wikidata/Commons, OpenFootball y API-Football con vínculos canónicos y procedencia |
| Automatización | Cola durable, cuotas compartidas, pausas, recuperación y avisos mediante SSE |
| Auditoría | Observaciones, correcciones protegidas, historial por campo y cuentas con roles |
| Clasificaciones | Tablas del proveedor separadas de cálculos ONCE con reglas verificadas |
| Operación | Docker, migraciones, copia/restauración de base y medios, QA aislado y CI manual |

### El marcador real de la cobertura

La cuenta gratuita comprobada en el piloto permitió **2022–2024** y rechazó 2026. Se importaron quince calendarios de Primera A, Primera B, Copa Colombia, Liga Femenina y Superliga: **2.890 partidos**. La instalación tenía 3.091 registros contando los anteriores y 35 tablas publicadas. Una tabla de Primera B 2023 permanece en revisión por identidades históricas de clubes.

El detalle se completa por tandas: el plan Free consultado acepta un partido por solicitud y limita a 100 solicitudes diarias. Al agotarse la cuota, la cola espera; la lectura local continúa. Los datos abiertos previos siguen disponibles. Ninguno de esos archivos se presenta como servicio en vivo de 2026. Consulta [operación](docs/automation.md) y [evidencia de ejecución](docs/development.md).

## 🗺️ Ocho estaciones, una ruta

| Paso | Archivo | Sales sabiendo… | Tipo principal |
| --- | --- | --- | --- |
| 1 | [CONTEXT.md](CONTEXT.md) | Qué problema resuelve ONCE y qué decisiones lo protegen | Explicación |
| 2 | [README.md](README.md) | Cómo arrancar y dónde continuar | Orientación |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | Cómo viajan los datos y dónde viven las responsabilidades | Explicación y referencia |
| 4 | [SETUP.md](SETUP.md) | Cómo instalar Docker o preparar el desarrollo manual | Tutorial y referencia |
| 5 | [TESTING.md](TESTING.md) | Qué probar, dónde hacerlo y cómo interpretar resultados | Guías y referencia |
| 6 | [DEPLOYMENT.md](DEPLOYMENT.md) | Cómo entregar, desplegar, respaldar y recuperar | Guías operativas |
| 7 | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Cómo resolver cinco fallos comunes sin destruir datos | Guías de resolución |
| 8 | [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo preparar una contribución y usar el Makefile | Guía y referencia |

Los manuales detallados de producto y fuentes continúan en [docs/README.md](docs/README.md). Las propuestas y el [archivo histórico](docs/archive/README.md) se identifican como tales; no sustituyen los procedimientos vigentes.

## Un ciclo de desarrollo corto

Con las dependencias instaladas según [SETUP](SETUP.md):

```sh
python -m scripts.dev help
python -m scripts.dev check
```

Si tienes GNU Make:

```sh
make check
```

El atajo ejecuta lint, pruebas API, unitarias del frontend y enlaces. `make ci-local` también construye imágenes y ejecuta el navegador contra QA aislado; no sustituye una comprobación de concurrencia en PostgreSQL. Los contratos están en [CONTRIBUTING](CONTRIBUTING.md).

Las medallas son etiquetas de estado documentado, no métricas en vivo. No se ha medido cobertura porcentual ni publicado una versión SemVer global. Usa `git rev-parse HEAD` para identificar la entrega. El `0.0.0` del paquete frontend no es una versión de producción del sistema.

## GitHub conserva el código; Docker conserva la operación

La CI se inicia manualmente con `workflow_dispatch`. Un commit o PR no activa trabajos ni despliega un servidor. Hay límites de tiempo, concurrencia y diagnóstico; no publicación automática de imágenes. [DEPLOYMENT](DEPLOYMENT.md) distingue ese flujo del ejemplo opcional por `push`.

Compose conserva `name: vertice`, `vertice_db`, sus volúmenes y la cookie `vertice_token` para mantener instalaciones anteriores. La carpeta y la marca son ONCE; renombrar volúmenes no forma parte del cambio de identidad visual.

Secretos, base y copias no viajan en Git. Los datos estructurados abiertos y las imágenes tienen condiciones distintas; consulta [procedencia y recursos visuales](docs/providers.md) antes de reutilizarlos.
