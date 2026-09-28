# Compartir ONCE en la red local

Este procedimiento publica la interfaz por **HTTP dentro de la LAN** y permite volver al acceso exclusivo del anfitrión. El mismo código funciona al cambiar de Wi-Fi, cable de red u ordenador: descubre direcciones candidatas al ejecutarse y no guarda una IP de la máquina en el proyecto.

Para publicar con dominio y HTTPS, utiliza [despliegue en servidor](server.md). Para llevar la base y los escudos a otro equipo, comienza por [transferencia y restauración](transfer.md): clonar el repositorio solo transporta código.

## 1. Preparar el equipo anfitrión

1. Instala **Python 3.12** y Docker Desktop en Windows/macOS, o Docker Engine con Compose en Linux. El asistente de red usa la biblioteca estándar de Python; no requiere instalar las dependencias del backend.
2. Abre Docker y espera a que su motor local esté disponible. La primera compilación necesita Internet para descargar imágenes y dependencias.
3. Abre una terminal en la raíz del proyecto, donde están `docker-compose.yml` y `compartir-once.cmd`. En Linux/macOS puedes sustituir `python` por `python3` si apunta a la versión requerida.
4. Si trasladarás datos existentes, restaura según el manual de transferencia **antes** de arrancar la API. Para una instalación nueva, continúa aquí.

El asistente necesita `VITE_API_URL=/api`, que es el valor normal del proyecto. Así, cada navegador utiliza la API del mismo equipo y puerto desde el que abrió ONCE. No escribas una IP del anfitrión en las fuentes React ni en esa variable.

## 2. Compartir

En cualquier plataforma:

```sh
python -m scripts.network lan
```

En Windows también puedes abrir [compartir-once.cmd](../../compartir-once.cmd) con doble clic. Sin argumentos ejecuta `lan` y mantiene la ventana abierta al terminar para leer las direcciones o el error. Desde PowerShell:

```powershell
.\compartir-once.cmd
```

Si todavía no existe `.env`, una ejecución interactiva abre el asistente `src.configure` para generar los secretos y solicitar las credenciales. No regenera secretos de una instalación existente. Sin terminal interactiva, o al pedir `status` o `--dry-run`, informa que falta el archivo y solicita ejecutar primero:

```sh
python -m src.configure
```

Conserva la configuración existente si ya tienes una base inicializada. Cambiar su contraseña en un archivo no cambia la contraseña que PostgreSQL tiene guardada.

El comando construye las imágenes de API y frontend utilizando la caché disponible, aplica la configuración de red y espera a que el frontend responda mediante `/api/health`. En el primer arranque levanta `db`, `api`, `worker` y `frontend`. Si ya encuentra la instalación, actualiza API y frontend con su dependencia de base de datos; no arranca ni detiene deliberadamente el trabajador existente ni cambia las pausas guardadas de sincronización.

Al terminar muestra direcciones con esta forma:

```text
En este equipo: http://localhost/
En tu red: http://IP_DEL_EQUIPO/
Explorar: http://IP_DEL_EQUIPO/explore
```

Abre **una dirección que haya mostrado tu ejecución** desde el móvil u otro ordenador conectado a la misma red. `IP_DEL_EQUIPO` es un marcador de documentación. `localhost` identifica el dispositivo que abre el navegador, por lo que no sirve para llegar al anfitrión desde otro equipo.

Cada dispositivo mantiene su propia sesión administrativa. El anfitrión y Docker deben permanecer encendidos; el comando no instala un servicio de alojamiento externo ni configura el router.

## 3. Elegir puerto, consultar y volver a acceso local

Si el puerto 80 está ocupado, elige otro puerto libre:

```sh
python -m scripts.network lan --port 8080
python -m scripts.network status
```

En ese caso, la dirección tendrá la forma `http://IP_DEL_EQUIPO:8080/explore`. Al omitir `--port`, los cambios conservan el puerto guardado en `FRONTEND_PORT`; si la variable no existe, utilizan 80.

Para dejar de publicar la interfaz en todas las conexiones del anfitrión:

```sh
python -m scripts.network local
```

ONCE seguirá disponible desde ese equipo por `http://localhost/`, añadiendo el puerto cuando corresponda. `status` comprueba que los contenedores pertenecen a esta instalación, compara la configuración guardada con el puerto realmente publicado por Docker y comprueba la respuesta HTTP local; no cambia el modo. No acepta opciones de modificación.

| Opción | Uso y alcance |
| --- | --- |
| `--port 8080` | Selecciona el puerto HTTP del frontend; se admiten enteros entre 1 y 65535 |
| `--dry-run` | Muestra los tres valores propuestos y las direcciones candidatas; no aplica la configuración ni modifica Docker o el firewall. Requiere `.env` existente |
| `--no-build` | Omite la construcción; úsala únicamente cuando las imágenes ya contengan el código actual |
| `--firewall` | Gestiona la regla de ONCE en Windows; requiere una terminal abierta como administrador y una solicitud explícita |

Ejemplo de vista previa:

```sh
python -m scripts.network lan --port 8080 --dry-run
```

La construcción predeterminada incorpora las fuentes actuales del frontend y de la API, incluidas las correcciones de inicio de sesión. `--no-build` reutiliza imágenes: no es un atajo para aplicar cambios de código pendientes.

## 4. Firewall de Windows, solo si hace falta

El modo normal no pide elevación ni cambia el firewall. Si el anfitrión funciona pero otro dispositivo no puede conectarse, revisa primero el puerto y que ambos estén en la misma red. Si necesitas habilitar la regla, abre PowerShell **como administrador**, sitúate en el proyecto y ejecuta:

```powershell
python -m scripts.network lan --port 8080 --firewall
```

La regla permite entrada **TCP solo al puerto seleccionado y desde `LocalSubnet`**. Se aplica a cualquier perfil de Windows (`Any`), por lo que no depende de que la conexión esté clasificada como privada. Conserva la restricción de subred, bloquea el recorrido por el borde de red y no abre PostgreSQL ni el puerto de la API.

El nombre de la regla es `ONCE-LAN-HTTP-<puerto>` y su grupo es `ONCE Local Network`. El ayudante solo administra reglas con esa identidad; si encuentra el mismo nombre fuera del grupo de ONCE o reglas duplicadas, se detiene sin sustituirlas. No desactiva el firewall ni modifica reglas ajenas. En Linux/macOS, gestiona el permiso equivalente con las herramientas del anfitrión; `--firewall` informa que esta automatización es exclusiva de Windows.

Para restringir el acceso al anfitrión y retirar la regla de ONCE del puerto seleccionado:

```powershell
python -m scripts.network local --port 8080 --firewall
```

Si cambias de puerto en una operación con `--firewall`, también retira la regla de ONCE correspondiente al puerto anterior guardado. Ejecutar `local` sin esta opción restringe el enlace de Docker a loopback, pero conserva cualquier regla de firewall creada previamente.

## 5. Qué cambia y qué conserva

| Variable administrada | `lan` | `local` |
| --- | --- | --- |
| `FRONTEND_BIND` | `0.0.0.0`: escucha en las interfaces del anfitrión | `127.0.0.1`: solo loopback |
| `FRONTEND_PORT` | Puerto seleccionado o guardado | Puerto seleccionado o guardado |
| `COOKIE_SECURE` | `false`, porque este modo usa HTTP | `false`, porque este modo usa HTTP |

El comando solo edita esas tres variables. Conserva las claves de proveedor, los secretos existentes, el catálogo y el resto del contenido de `.env`, incluidos sus comentarios. Las IPs detectadas se muestran sin guardarlas. La API sigue publicada solo en loopback y PostgreSQL permanece dentro de la red Docker.

Este modo es para HTTP local. **No lo uses para reconfigurar una instalación HTTPS de producción**, donde `COOKIE_SECURE=true` forma parte de la configuración. Los cambios de red no habilitan por sí mismos datos en vivo ni alteran las cuotas externas.

La detección devuelve IPv4 privadas RFC1918 y prioriza la ruta activa. Filtra interfaces desconectadas y adaptadores virtuales/VPN identificables; si las herramientas del sistema no están disponibles, utiliza la dirección de origen y el nombre del equipo como alternativas. Una dirección candidata **no demuestra accesibilidad desde otro dispositivo**: redes de invitados, aislamiento Wi-Fi, VPN, políticas corporativas y firewalls pueden impedirla. No depende de una IP fija ni de una respuesta de Internet para descubrir esas candidatas.

## 6. Guardas y recuperación

- Exige un motor Docker local. Rechaza contextos remotos o TCP para no modificar otra máquina mientras anuncia direcciones de este equipo.
- Rechaza `COMPOSE_FILE`, `COMPOSE_PROJECT_NAME` y `COMPOSE_PROFILES` con valor tanto en la terminal como en `.env`; utiliza explícitamente el Compose base del proyecto. También rechaza valores de red del proceso que contradigan el modo solicitado y un `VITE_API_URL` distinto de `/api`.
- Comprueba que los contenedores de la identidad Compose pertenezcan a esta carpeta, también al consultar `status`. Un segundo clon que apunte a la misma instalación se detiene antes de modificarla o presentar su puerto como propio.
- Rechaza valores multilínea o comillas sin cerrar en `.env` antes de editarlo, sin revelar su contenido. Conserva ese archivo: el asistente no intenta normalizar secretos ni interpretar como variables las líneas dentro de un valor multilínea. Ese formato requiere configurar la red manualmente con revisión del archivo completo.
- Serializa operaciones de red y evita sobrescribir `.env` si cambió durante la ejecución o es un enlace simbólico.
- Si falla el arranque o la comprobación HTTP después del cambio, restaura el archivo anterior e intenta recuperar la configuración previa de una instalación existente. El mensaje indica si volvió a responder; no promete una reversión completa de Docker.

Si la recuperación no termina, conserva el mensaje y revisa:

```sh
docker compose ps
docker compose logs --tail 80 api frontend
```

Con la configuración restaurada, `docker compose up -d --wait` permite intentar el arranque del conjunto; también arranca el trabajador, por lo que revisa antes el estado de sincronización que deseas mantener. Si falla únicamente la gestión del firewall, ONCE puede estar respondiendo con la nueva configuración: el comando lo indica y devuelve error para que completes ese permiso por separado.

Si `status` detecta diferencia entre `.env` y Docker, vuelve a aplicar `lan` o `local` desde la carpeta correcta. Para un error por puerto ocupado, repite con otro `--port`. Si funciona en el anfitrión y no desde fuera, verifica la dirección mostrada, el puerto, la conexión a la misma red y las políticas de aislamiento; una respuesta local correcta no verifica ese recorrido.

## 7. Clones, traslado y atajos

En otra máquina, clona el código, instala Python y Docker y repite el procedimiento: la IP se descubre allí. Si necesitas los mismos datos, sigue [transferencia](transfer.md) para restaurar PostgreSQL, medios y configuración por un canal privado. Git no contiene la base, los medios privados ni `.env`.

**Dos carpetas clonadas en un mismo motor Docker no equivalen a dos bases independientes.** El Compose conserva `name: vertice` y los volúmenes de la instalación histórica. El asistente rechaza la colisión de carpeta; no uses cambios de nombre u overrides improvisados para eludirla. Una segunda instalación exige diseñar explícitamente otra identidad Compose, otros volúmenes y otros puertos fuera de este asistente.

| Comando directo | Atajo Python | GNU Make opcional |
| --- | --- | --- |
| `python -m scripts.network lan` | `python -m scripts.dev lan` | `make lan` |
| `python -m scripts.network local` | `python -m scripts.dev local` | `make local` |
| `python -m scripts.network status` | `python -m scripts.dev network-status` | `make network-status` |

Los atajos aceptan los mismos argumentos de cambio: `python -m scripts.dev lan --port 8080` o `make lan ARGS="--port 8080"`. En Windows, `compartir-once.cmd lan --port 8080` y `compartir-once.cmd status` devuelven el código de salida sin pausar; la pausa solo se añade al invocarlo sin argumentos. Una operación correcta devuelve 0; los fallos operativos devuelven 1 y un uso inválido de argumentos puede devolver 2.

[Instalación completa](../../SETUP.md) · [Despliegue local](local.md) · [Servidor HTTPS](server.md) · [Diagnóstico general](../../TROUBLESHOOTING.md)
