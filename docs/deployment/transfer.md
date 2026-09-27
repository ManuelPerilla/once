# Copias, traslado a otro equipo y restauración

El código y los datos se trasladan por separado. Copiar la carpeta del repositorio no copia el volumen de Docker.

## 1. Preparar el origen

Con PostgreSQL en marcha, desde la raíz:

```sh
python -m scripts.backup
```

Se crean un `.dump` binario de PostgreSQL y un `.json` con su SHA-256 en `.local/backups`. El script usa `pg_dump -Fc`, comprueba que PostgreSQL pueda leer el índice y no redirige binarios a través de PowerShell. Una salida con error no es una copia válida. El dump es una instantánea coherente de la base; los cambios realizados después no están incluidos.

Para guardarlos directamente en otra carpeta:

```sh
python -m scripts.backup --directory RUTA_DE_RESPALDOS
```

Conserva fuera del equipo al menos la última copia verificada y una anterior. El `.dump` y su `.json` deben viajar juntos; no edites el archivo JSON para hacer pasar una copia modificada.

## 2. Qué transferir

- Código, Dockerfiles, Compose, migraciones, dependencias fijadas, documentación y recursos de `frontend/public`.
- `.git` si quieres conservar el historial local, o un clon del repositorio cuando vuelva a estar disponible.
- El `.dump` y su `.json`, por un canal privado.
- `.env` por separado si quieres mantener las credenciales actuales; también puedes generar nuevas credenciales en el destino.

No hace falta transferir `.venv`, `frontend/node_modules`, `frontend/dist`, cachés ni contenedores. Los entornos virtuales pueden contener rutas absolutas: recréalos en el destino si vas a desarrollar fuera de Docker. `.local` contiene copias y resultados de pruebas: no se sube a GitHub. Los SQL de `data/legacy` no sustituyen la copia recién creada.

Para congelar también imágenes ya construidas puedes usar `docker save -o once-images.tar vertice-api:latest vertice-frontend:latest postgres:15-alpine` y `docker load -i once-images.tar` en el destino. Eso **no incluye la base de datos**. En un equipo con otra arquitectura conviene reconstruir las imágenes; una transferencia de imágenes no es universal entre plataformas.

## 3. Restaurar en una instalación vacía

Instala Docker/Compose y Python 3.12. Sitúa el código en la carpeta `once`. Copia o genera `.env` antes de arrancar servicios. En una base nueva, la contraseña PostgreSQL puede ser nueva porque el dump contiene datos y esquema, no exige reutilizar la contraseña anterior.

Inicia únicamente PostgreSQL:

```sh
docker compose up -d db --wait
python -m scripts.restore_backup RUTA_A_LA_COPIA.dump
docker compose up --build -d --wait
```

**No inicies la API antes de restaurar:** crearía tablas y datos iniciales. El restaurador exige el manifiesto, verifica el hash y rechaza una base que ya contenga tablas. No borra tablas ni volúmenes. La restauración se ejecuta en una sola transacción y los propietarios se adaptan al usuario local.

Si la base de destino ya contiene información, detente y crea una instalación independiente o una copia de esa base. No intentes vaciarla con este manual.

Si usaste `docker load` y no quieres recompilar, sustituye el último comando por `docker compose up --no-build -d --wait`.

## 4. Comprobar el destino

1. `docker compose ps`: los tres servicios deben estar saludables.
2. Inicia sesión con las credenciales del `.env` de destino.
3. Compara los totales de confederaciones, competiciones, equipos y partidos con el origen.
4. Abre varias fichas y comprueba fechas, matrículas y fuentes importadas.
5. Genera una nueva copia desde el destino. Conserva el origen hasta terminar estas comprobaciones.

El archivo de copia incluye `alembic_version`; el arranque aplica las migraciones pendientes del código de destino. Para una transferencia normal usa la misma versión del código primero y actualiza después de verificar.

## Ensayar sin tocar la instalación principal

Las herramientas aceptan `--compose-file RUTA` para apuntar a una instalación desechable. Debe tener un servicio `db`, usuario `postgres` y base `vertice_db`. Usa un proyecto y volumen distintos, inicia solo su base, restaura y compara. El [manual de desarrollo](../development.md) explica cómo crear un conjunto de prueba aislado.
