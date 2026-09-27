# Retomar GitHub y preparar entregas

GitHub almacena código e historial; la base y los secretos se mantienen fuera del repositorio. ONCE sigue funcionando localmente aunque la cuenta no esté disponible. Este manual no publica nada automáticamente.

## Conectar una cuenta recuperada o un repositorio nuevo

Usa una cuenta y un repositorio habilitados. Si una suspensión sigue vigente, resuélvela con GitHub antes de publicar. Conserva primero una copia del proyecto y un [respaldo de PostgreSQL](transfer.md). Revisa la configuración del repositorio local:

```sh
git status
git branch --show-current
git remote -v
```

Cuando tengas la URL real del repositorio, reemplaza `URL_DEL_REPOSITORIO` en uno de estos comandos:

```sh
# Si origin ya existe:
git remote set-url origin URL_DEL_REPOSITORIO
# Si no existe:
git remote add origin URL_DEL_REPOSITORIO
```

Autentícate con el método que hayas configurado para GitHub, sin incluir tokens en la URL ni en archivos del proyecto. `git fetch origin` permite revisar el historial remoto sin sobrescribir tu trabajo. Si el repositorio remoto está vacío, puedes subir la rama local elegida; si ya tiene commits, compara e integra las diferencias antes de subir. No uses `push --force` como solución automática a historiales distintos.

Para preparar un cambio local:

```sh
git switch -c codex/descripcion-del-cambio
git diff
git add RUTAS_REVISADAS
git diff --cached
git commit -m "Describe el cambio comprobado"
git push -u origin codex/descripcion-del-cambio
```

Los nombres de rama y rutas son ejemplos que debes sustituir. Revisa especialmente `.env`, claves, dumps y datos privados antes del commit. `.gitignore` excluye los secretos y las copias normales, pero no elimina contenido que ya estuviera en el historial.

La revisión previa a publicar ONCE encontró contraseñas locales antiguas de PostgreSQL y pgAdmin en revisiones históricas de `docker-compose.yml` y `src/database.py`. No corresponden a la configuración actual. El historial se conserva; esos valores antiguos no deben reutilizarse en ninguna instalación. Las instalaciones nuevas deben generar sus propias credenciales mediante el [procedimiento de despliegue](local.md).

## Integración continua

[.github/workflows/ci.yml](../../.github/workflows/ci.yml) conserva tres comprobaciones: API sobre PostgreSQL desechable, frontend, y navegador sobre Docker. **Solo se ejecuta manualmente** mediante `workflow_dispatch`: subir commits, abrir un PR o cambiar documentación no inicia ejecuciones. No hay tareas programadas.

Antes de subir, agrupa cambios relacionados y ejecuta las [comprobaciones locales](../development.md). Después de publicar una revisión comprobada, abre **Actions → Integracion Continua ONCE → Run workflow**, selecciona la rama y lanza una ejecución. El archivo del flujo debe estar presente en la rama predeterminada para que GitHub muestre el disparo manual. Si falla, revisa el diagnóstico, reproduce y corrige el problema localmente antes de volver a lanzarlo; evita usar commits pequeños como mecanismo de prueba del CI.

El flujo solo dispone de permiso de lectura del código. Una nueva ejecución en la misma rama cancela la anterior. Los trabajos tienen límites de 15 minutos para la API, 10 para el frontend y 20 para Docker; este último empieza únicamente si pasan los dos primeros. No se reintentan automáticamente pruebas fallidas. La concurrencia limita ejecuciones redundantes, pero las cuotas y condiciones de la cuenta siguen aplicándose.

Las credenciales del flujo son temporales para bases desechables. No se deben reemplazar por las de la instalación de trabajo. Los recorridos E2E necesitan `SMOKE_DISPOSABLE=1`. La prueba externa real de Wikidata se activa con `CATALOG_LIVE_TEST=1`; por defecto las reglas de ingesta se prueban sin depender de internet.

El flujo valida código y contenedores; **no publica imágenes ni despliega un servidor**. Esa separación permite recuperar GitHub sin dar acceso automático a la base local. Los disparadores automáticos solo deben añadirse cuando exista una necesidad concreta y se hayan revisado las cuotas y el alcance de las comprobaciones.

## Entrega a otro equipo o a un servidor

1. Ejecuta las [pruebas](../development.md) y anota sus resultados y la revisión entregada.
2. Comprueba que no queden cambios locales necesarios sin incluir en la entrega.
3. Genera una copia de datos y conserva las instrucciones de [transferencia](transfer.md).
4. En el destino, utiliza la misma revisión y sigue el [despliegue local](local.md).
5. Antes de una publicación externa, concreta dominio, TLS, secretos del servidor, backups y recuperación. No expongas PostgreSQL ni subas `.env` como artefacto de CI.

Si en el futuro se automatiza la publicación, usa versiones identificables de las imágenes y conserva la imagen anterior y su copia de datos. La recuperación debe ensayarse antes de convertir un commit en un despliegue automático.
