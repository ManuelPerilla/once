# Desarrollo y verificación

El camino principal de ejecución es Docker. Los asistentes en `scripts` resuelven la raíz a partir de su propia ubicación, por lo que siguen funcionando al renombrar la carpeta.

## API: pruebas y calidad

Sin instalar dependencias Python en el anfitrión:

```sh
docker build --target test -t once-api-tests .
docker run --rm --network none once-api-tests
docker run --rm --network none once-api-tests python -m ruff check src tests scripts
docker run --rm --network none once-api-tests python -m ruff format --check src tests scripts
```

La imagen normal no contiene pytest ni Ruff. El objetivo `test` incluye herramientas y pruebas; usa SQLite en memoria de forma predeterminada. Las pruebas validan autenticación, relaciones, reglas de participación, importación atómica, procedencia y consultas por lotes.

Para desarrollo Python local:

```sh
python -m venv .venv
```

Activa `.venv` según tu sistema (`.venv\Scripts\Activate.ps1` en PowerShell; `source .venv/bin/activate` en Unix), y ejecuta:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python -m scripts.check_links
```

`TEST_DATABASE_URL` puede apuntar a PostgreSQL **desechable**. La suite elimina y crea tablas: nunca uses la base de trabajo. `python -m scripts.migration_smoke` también requiere una base desechable y comprueba adopción, actualización y reversión de esquema. El flujo de CI proporciona esa base cuando se ejecuta manualmente; consulta el [manual de GitHub](deployment/github.md).

## Frontend

Con Node 24, desde `frontend`:

```sh
npm ci
npm test
npm run lint
npm run build
npm run dev
```

Vite reenvía `/api` a `http://127.0.0.1:8000`; `API_PROXY_TARGET` permite cambiarlo. El lock vigente es `package-lock.json`: no mezcles gestores ni generes un segundo lock. Las [responsabilidades del frontend](../frontend/README.md) explican qué editar.

## Navegador contra Docker aislado

Desde la raíz, compila las imágenes y crea la configuración local de pruebas:

```sh
docker compose build
python -m scripts.prepare_qa
docker compose -f .local/compose.qa.json up -d --wait
```

El generador crea el proyecto `once-qa`, con su propio volumen y puerto `18080`. Si existe una configuración anterior, la conserva, incluidos su nombre y secretos; no la sobrescribe mientras una base pueda depender de ellos.

En PowerShell, desde `frontend`:

```powershell
$env:SMOKE_BASE_URL = 'http://127.0.0.1:18080'
$env:SMOKE_DISPOSABLE = '1'
$env:SMOKE_USERNAME = 'once_test'
$env:SMOKE_PASSWORD = 'once-disposable-test'
npx playwright install chromium
npm run test:e2e
```

En Linux/macOS exporta las mismas variables antes de ejecutar las pruebas. Esa contraseña es exclusiva del conjunto desechable. Los recorridos prueban login, edición, matrículas, partidos, sesión, tamaños de pantalla, navegación y demo. Para probar también una importación real desde Wikidata, define `CATALOG_LIVE_TEST=1`; requiere conexión y disponibilidad de la fuente.

Al terminar, desde la raíz:

```sh
docker compose -f .local/compose.qa.json down --volumes
```

La eliminación de volumen en ese comando es exclusiva del archivo QA. No la ejecutes con el Compose de trabajo.

## Verificación de la reorganización (27 de septiembre de 2026)

Se comprobaron las mismas 45 rutas OpenAPI, 87 pruebas de API tanto en SQLite como en PostgreSQL, 27 pruebas unitarias del frontend y 9 recorridos de navegador. La importación real desde Wikidata y el cierre de sesión durante una recarga retrasada están incluidos. Ruff y Oxlint no presentan errores ni advertencias del código; el cliente de pruebas de Starlette emite dos avisos de deprecación de sus dependencias, pendientes de una actualización coordinada.

También se ensayaron las migraciones y una copia/restauración real en PostgreSQL aislado, comparando los recuentos con el origen y verificando que se rechace una base de destino con tablas. Este registro describe una ejecución concreta; no sustituye las pruebas al modificar el proyecto.

## Al modificar una funcionalidad

Mantén URLs, errores, contratos y migraciones compatibles salvo cambio explícito. Coloca las reglas reutilizables fuera de los handlers HTTP; los componentes no deben conocer secretos ni proveedores remotos. Añade una prueba cuando exista una regla, regresión o condición de carrera relevante, y ejecuta el recorrido afectado en el conjunto desechable antes de actualizar la instalación de trabajo.

Los modelos no se cambian editando los SQL históricos. Añade una revisión Alembic y compruébala sobre una copia desechable. Un cambio de carpeta, marca o documentación no exige migrar las identidades internas de Docker.
