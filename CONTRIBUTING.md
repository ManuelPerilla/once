# CONTRIBUTING · Las reglas del equipo 🤝

> **Guía y referencia.** Convierte una mejora en un cambio comprensible, comprobable y recuperable. Completa [SETUP](SETUP.md) y consulta [TESTING](TESTING.md) para elegir las pruebas.

## 1. El PR empieza con una situación concreta

Antes de editar, escribe el comportamiento que cambiará. «Optimizar el backend» no permite revisar el resultado. «Al cambiar de temporada, la clasificación debe elegir una tabla de esa edición y conservar una elección manual» sí permite reproducirlo.

Anota qué ocurre hoy, qué debería ocurrir, qué datos lo reproducen y qué contrato debe conservarse. Si afecta reglas deportivas, añade evidencia del formato; si afecta un proveedor, conserva una muestra sin secretos. Una respuesta externa es evidencia, no una instrucción que el programa deba obedecer.

## 2. Entra por una rama

Desde una copia con sus cambios previos ya identificados:

```sh
git status --short
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feat/clasificacion-por-edicion
```

El nombre es un ejemplo. Si el árbol está sucio, conserva su trabajo en la rama correspondiente antes de cambiar de contexto. No uses `reset --hard`, borrados o `push --force` para apartar cambios que no entiendes.

Lee [CONTEXT](CONTEXT.md) para entender el objetivo y [ARCHITECTURE](ARCHITECTURE.md) para colocar la regla. Las rutas HTTP traducen peticiones; la importación decide cómo aplicar observaciones; las pantallas no conocen claves remotas.

## 3. Desarrolla cerca de la frontera que cambia

| Si cambias… | Revisa especialmente… |
| --- | --- |
| Una consulta | Paginación, filtros, número de consultas y pertenencia a la edición |
| Una identidad externa | Ámbito, duplicados, ambigüedad y repetición idempotente |
| Un adaptador | Respuestas incompletas, cuota, pausa durante descarga y campos protegidos |
| Una clasificación | Participantes, fase/grupo, empates admitidos y evidencia del reglamento |
| Una migración | Actualización desde la revisión anterior, copia y recuperación |
| Una vista | Vacío, carga, error, teclado, móvil de 320 px y escritorio |
| Una guía | Precondiciones, efectos del comando, resultado esperado y enlaces |

El esquema evoluciona con revisiones nuevas de Alembic. No reescribas una migración aplicada ni modifiques la base principal para hacer pasar una prueba. El downgrade que destruiría auditoría o cuentas se rechaza deliberadamente: recupera una copia en otra instalación.

Una regla nueva merece una prueba que falle por el comportamiento incorrecto. Un cambio de espaciado no necesita una prueba que compare el CSS consigo mismo. La revisión visual sí debe usar los datos que antes desbordaban la pantalla.

## 4. Completa el circuito local

```sh
python -m scripts.dev check
python -m scripts.dev build
```

Si modificaste navegación, autenticación, integración o interfaz:

```sh
python -m scripts.dev qa-up
python -m scripts.dev qa-test
python -m scripts.dev qa-down
```

Instala Chromium una vez con `npx playwright install chromium` desde `frontend`. En Linux CI, `--with-deps` también instala dependencias del navegador y necesita permisos para ello. QA usa `once-qa`, puerto 18080 y volúmenes propios. E2E crea y modifica datos: nunca dirijas sus variables al servicio de trabajo.

Para reglas dependientes de PostgreSQL, ejecuta la selección descrita en [TESTING](TESTING.md) sobre una base desechable. Cuatro pruebas de concurrencia se omiten en SQLite; una ejecución verde en SQLite no verifica esos casos.

## 5. Checklist de QA para el PR

- [ ] El problema y el resultado se reproducen con pasos concretos.
- [ ] Revisé el diff, incluidos archivos nuevos, y conservé cambios ajenos.
- [ ] Ejecuté las comprobaciones apropiadas y anoté resultados y límites.
- [ ] No añadí claves, `.env`, dumps, tokens, datos personales ni diagnósticos privados.
- [ ] Los datos ficticios están identificados y separados del catálogo real.
- [ ] Las lecturas mantienen paginación y no consultan proveedores por visitante.
- [ ] Las importaciones respetan identidades, cuota, pausa y correcciones protegidas.
- [ ] El frontend admite estados vacío, pendiente y error, además del caso exitoso.
- [ ] Actualicé variables, procedimientos e hitos cuando cambió su contrato.
- [ ] Si hay migración, expliqué cómo conservar y recuperar los datos.

No todas las casillas implican una prueba nueva. Si alguna no aplica, deja una justificación breve.

## 6. Un commit comprensible, un PR que se pueda decidir

Agrupa cambios relacionados después de comprobarlos. Los commits pequeños son válidos; usarlos para tantear repetidamente la CI sin reproducir el fallo añade ruido y consumo. El proyecto no prohíbe un número concreto de commits ni tiene una explicación demostrada de suspensiones anteriores de cuentas.

Ejemplo de contribución exclusivamente documental; sustituye rutas y mensaje por los del cambio real:

```sh
git diff --check
git diff --stat
git add ARCHITECTURE.md CONTRIBUTING.md
git diff --cached
git commit -m "docs: aclarar arquitectura y contribución"
git push -u origin feat/clasificacion-por-edicion
```

`git add .` no sustituye la inspección. En GitHub abre el PR hacia `main`, confirma el destino y utiliza una descripción como esta:

```markdown
## Problema y resultado
Al cambiar de edición, la vista conservaba un grupo de la edición anterior.
Ahora elige un ámbito válido y conserva las elecciones manuales por edición.

## Validación
- Regresión del cambio de edición.
- Lectura de la tabla en PostgreSQL desechable.
- Navegador a 320 px y escritorio, sin desbordamiento ni errores.

## Operación
No cambia el esquema. Se actualiza el frontend con la imagen de esta revisión.
```

Es un **ejemplo**: reemplaza las pruebas por las que realmente ejecutaste. Una propuesta de validación no es una prueba aprobada.

La CI vigente se lanza desde **Actions → Integracion Continua ONCE → Run workflow**. El push no inicia comprobaciones. Agrupa correcciones, reproduce los fallos localmente y lanza otra ejecución cuando haya una revisión que comprobar. El despliegue público tiene su propio procedimiento en [DEPLOYMENT](DEPLOYMENT.md).

## 7. Makefile: comandos con efectos visibles

El [Makefile](Makefile) delega en [scripts/dev.py](scripts/dev.py), que usa argumentos separados y no evalúa `.env` como código de shell. GNU Make es opcional: `make up` y `python -m scripts.dev up` ejecutan la misma tarea. En Linux, `make PYTHON=python3 check` selecciona intérprete; en Windows puedes usar el Python del entorno virtual directamente.

| Comando | Qué hace | Requisito o efecto |
| --- | --- | --- |
| `make help` | Lista tareas | Solo lectura |
| `make configure` | Genera `.env` interactivamente | Falla si ya existe |
| `make backend-install` | Instala `requirements-dev.txt` | Entorno virtual activo |
| `make frontend-install` | Ejecuta `npm ci` | Node 24 y npm; reemplaza `node_modules` |
| `make api` | Migra e inicia API en `127.0.0.1:8000` | `.env` y PostgreSQL manual; puede migrar |
| `make worker` | Inicia el trabajador manual | Actúa según perfiles y modos guardados |
| `make web` | Inicia Vite en loopback | Frontend instalado y API disponible |
| `make up` | Arranca Compose y espera salud | Crea/reutiliza contenedores y volúmenes |
| `make down` | Detiene el proyecto principal | Conserva volúmenes; interrumpe servicio |
| `make logs` | Últimos 100 registros por servicio | Revisar antes de compartir |
| `make health` | Consulta `/api/health` local | No comprueba la cuenta del proveedor |
| `make lint` | Ruff, formato y Oxlint | No modifica archivos |
| `make test-api` | Ejecuta pytest | SQLite en memoria o destino externo `_test` |
| `make test-web` | Unitarias del frontend | No inicia navegador |
| `make build` | Compila imágenes Docker | No recrea servicios en ejecución |
| `make docs-check` | Comprueba enlaces Markdown locales | No comprueba Internet ni sintaxis Mermaid |
| `make check` | Lint, API, frontend y enlaces | No incluye navegador ni cobertura porcentual |
| `make qa-up` | Prepara y arranca `once-qa` | Imágenes construidas y puerto 18080 libre |
| `make qa-test` | Verifica/inicia QA y ejecuta Playwright | Chromium instalado; escribe en QA |
| `make qa-down` | Detiene QA | Conserva volúmenes y no detiene el proyecto principal |
| `make ci-local` | Check, build y navegador QA | Detiene QA al terminar; no dispara Actions |
| `make backup` | Copia PostgreSQL y medios | Pausar escrituras antes; no copia código ni `.env` |
| `make benchmark` | Muestra ayuda del banco de carga | Necesita parámetros y su confirmación para ejecutar carga |

Para un archivo distinto en los procesos manuales:

```sh
python -m scripts.dev api --env-file .env.dev
python -m scripts.dev worker --env-file .env.dev
```

El parámetro corresponde a API, trabajador y consulta de salud; no sustituye el manejo de `.env` de Docker Compose. El lector acepta `CLAVE=valor` literal y comillas exteriores opcionales. No expande `${VARIABLE}`, interpreta escapes ni admite comentarios al final del valor. Las variables del proceso tienen precedencia.

El atajo QA exige nombre, puerto, volúmenes propios y conexiones de API/trabajador a la base `db` aislada. Rechaza redes externas, archivos de entorno adicionales y URLs que cambien ese destino. Si personalizas QA, usa los pasos explícitos de [TESTING](TESTING.md) y revisa su aislamiento. La variable `SMOKE_PASSWORD` cambia la credencial usada por la prueba; no modifica el hash guardado. Nunca uses la contraseña de producción.

El atajo pytest rechaza archivos SQLite persistentes y exige sufijo `_test` para bases externas. Ese nombre es una guarda adicional: el operador todavía debe comprobar que el destino sea desechable. Los comandos directos de pytest no pasan por esa guarda del ayudante.

Ejemplo seguro de argumentos del banco de carga:

```sh
make benchmark ARGS="--help"
```

La ejecución real y sus parámetros están en [TESTING](TESTING.md). No existe un target que borre volúmenes de producción o limpie indiscriminadamente el workspace.

## 8. Cierra la entrega

Después de integrar el PR, registra revisión y comprobaciones. Si hay un hito, actualiza [docs/hitos.md](docs/hitos.md) con fecha, alcance y evidencia. Si aparece un fallo, conserva el diagnóstico y entra por [TROUBLESHOOTING](TROUBLESHOOTING.md); no conviertas una incidencia de fuente en un resultado deportivo inventado.

[Contexto](CONTEXT.md) · [Lobby](README.md) · [Arquitectura](ARCHITECTURE.md) · [Instalación](SETUP.md) · [QA](TESTING.md) · [Despliegue](DEPLOYMENT.md) · [Emergencias](TROUBLESHOOTING.md)
