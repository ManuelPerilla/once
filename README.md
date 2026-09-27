# ONCE

Una plataforma local para explorar el fútbol y sus conexiones: partidos, equipos, competiciones y jugadores. Marca azul noche, lima y blanco; administrador y experiencia pública con datos reales, más una demo opcional claramente identificada.

## Arrancar

Necesitas Docker con Compose. Si ya existe `.env`, conserva sus valores:

```sh
docker compose up --build -d --wait
```

En Windows puedes abrir [iniciar-once.cmd](iniciar-once.cmd). Para una instalación nueva, sigue el [manual de despliegue local](docs/deployment/local.md). Node y PostgreSQL funcionan dentro de Docker; Python 3.12 solo es necesario en el anfitrión para los asistentes y herramientas de mantenimiento.

- [Administrador](http://localhost/)
- [Explorar tus datos](http://localhost/explore)
- [Demo sin escritura de datos](http://localhost/explore?demo=1)
- [Documentación de la API](http://localhost/api/docs)

Si cambias `FRONTEND_PORT`, usa ese puerto en los enlaces. Los datos persisten en PostgreSQL cuando cierras Docker.

## Qué funciona

| Área | Alcance actual |
| --- | --- |
| Catálogo | Confederaciones, competiciones y equipos; búsqueda, filtros, edición y eliminación con confirmación. |
| Matrículas | Participación explícita de equipos; validación de país, tipo y confederación. |
| Partidos | Marcador, estado, fecha, jornada y contexto de temporada, fase y estadio. |
| Exploración | Listas y fichas conectadas; estadísticas, cronología y alineaciones cuando existen datos. |
| Datos abiertos | Importación revisada desde Wikidata: seis confederaciones y una colección inicial de Colombia. |
| Proveedores | Mappings, observaciones y medios con procedencia; API-Football opcional. |

La importación está en **Inicio → La mesa de fuentes → Haz crecer tu catálogo**. No requiere suscripción; conserva los IDs y las correcciones locales. No deduce matrículas ni inventa resultados. “En vivo” es el estado guardado; no hay un servicio automático de resultados en directo.

## Documentación y traslado

- [Índice de documentación](docs/README.md)
- [Instalar, actualizar y diagnosticar Docker](docs/deployment/local.md)
- [Copias de seguridad y traslado a otro equipo](docs/deployment/transfer.md)
- [Volver a GitHub y preparar entregas](docs/deployment/github.md)
- [Arquitectura y decisiones técnicas](docs/architecture.md)
- [Desarrollo y pruebas reproducibles](docs/development.md)
- [Modelo de datos](docs/data.md), [ingesta](docs/ingestion.md) y [proveedores](docs/providers.md)
- [Producto](docs/vision.md) y [experiencia](docs/ux.md)

La carpeta del código puede llamarse `once`. Compose conserva deliberadamente `name: vertice`, la base `vertice_db`, el volumen `vertice_postgres_data` y la cookie `vertice_token` para mantener instalaciones existentes. Cambiar la marca no exige migrar esas identidades internas. No cambies el nombre del proyecto Compose de una instalación existente sin trasladar también su volumen.

## Comprobaciones

```sh
docker build --target test -t once-api-tests .
docker run --rm --network none once-api-tests
```

En `frontend/`, con Node 24 y dependencias instaladas mediante `npm ci`:

```sh
npm test
npm run lint
npm run build
```

Las pruebas de navegador escriben datos y disponen de un [entorno Docker separado](docs/development.md). GitHub Actions conserva las comprobaciones con [ejecución manual](docs/deployment/github.md), límites de tiempo y cancelación de ejecuciones anteriores en la misma rama. Subir commits no dispara el flujo; el proyecto funciona sin una cuenta ni un repositorio remoto.
