# Despliegue de ONCE en un servidor

Este manual prepara una instalación Docker en un único servidor Linux, con un dominio y HTTPS. El repositorio conserva sus puertos en `127.0.0.1`: NGINX, instalado en el mismo servidor, recibe el tráfico exterior y lo dirige al frontend. PostgreSQL y el trabajador siguen dentro de la red privada de Compose.

El ejemplo usa `once.example.com`; reemplázalo por tu dominio real. Esta documentación no publica la instalación local ni provisiona un servidor.

## 1. Preparar el destino

Necesitas Docker Engine con Compose, Python 3.12 para los asistentes, NGINX, espacio para los volúmenes y las copias, y un dominio cuyo DNS apunte al servidor. Habilita los puertos públicos 80/443 y limita el acceso de administración del servidor. La instalación debe poder consultar por HTTPS las fuentes configuradas y sus imágenes.

Transfiere el código mediante el repositorio privado o un archivo del proyecto. Si hay datos existentes, sigue primero [transferencia y restauración](transfer.md): no arranques la API sobre una base destinada a recibir una copia, porque crearía el esquema inicial.

En una instalación nueva, ejecuta `python3 -m src.configure` desde la raíz. En el `.env` **del servidor**, conserva los secretos generados y configura:

```dotenv
FRONTEND_BIND=127.0.0.1
FRONTEND_PORT=8080
VITE_API_URL=/api
COOKIE_SECURE=true
CORS_ORIGINS=https://once.example.com
API_FOOTBALL_KEY=
```

Guarda la clave del proveedor en ese archivo privado. No la incluyas en variables `VITE_`, código, imágenes Docker, ejemplos o capturas. Limita la lectura de `.env` al usuario de despliegue (`chmod 600 .env`). El frontend y la API se presentan bajo el mismo dominio; CORS no sustituye la autenticación.

```sh
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
curl --fail http://127.0.0.1:8080/api/health
```

El Compose sigue llamándose `vertice` para conservar la identidad de sus volúmenes. No cambies ese nombre en una instalación existente. El puerto público 80 queda libre para NGINX porque el frontend usa ahora `127.0.0.1:8080`.

## 2. Preparar HTTPS

Obtén un certificado válido para el dominio mediante el gestor de certificados del servidor o un cliente ACME. Configura también su renovación y la recarga de NGINX al renovarlo. Las rutas de certificado del siguiente ejemplo deben existir antes de activarlo. Si el emisor usa un desafío HTTP, instala primero su configuración HTTP temporal; no habilites todavía el bloque TLS con archivos inexistentes.

La [documentación oficial de NGINX para HTTPS](https://nginx.org/en/docs/http/configuring_https_servers.html) explica la cadena del certificado y su clave privada. Mantén esa clave fuera del repositorio.

Guarda esta configuración dentro de los sitios habilitados de NGINX, según la distribución del servidor. El ejemplo se incluye dentro del contexto `http` del archivo principal:

```nginx
server {
    listen 80;
    server_name once.example.com;
    return 308 https://once.example.com$request_uri;
}

server {
    listen 443 ssl;
    server_name once.example.com;

    ssl_certificate /etc/letsencrypt/live/once.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/once.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Connection "";
    proxy_cache off;
    proxy_connect_timeout 5s;
    proxy_read_timeout 120s;

    # El proxy interno habla HTTP; conserva HTTPS en redirecciones de la API.
    proxy_redirect http://once.example.com/ https://once.example.com/;

    location = /api/public/changes {
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering off;
        gzip off;
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
    }
}
```

Conserva la URI completa en `proxy_pass`: el frontend interno sirve las rutas profundas, los recursos y el prefijo `/api`. La ruta de actualizaciones usa SSE; el proxy exterior y cualquier CDN intermedia deben permitir transmitirla sin almacenar ni agrupar la respuesta. [Referencia de proxy y buffering de NGINX](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering).

Valida la configuración antes de recargar el servicio:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

Estos comandos corresponden a un servidor Linux con systemd. Si el alojamiento administra NGINX o los certificados, aplica la configuración equivalente desde su panel.

## 3. Comprobar el servicio público

Desde otro equipo, abre `https://once.example.com/` e inicia sesión. Comprueba que la cookie de sesión tiene `Secure`, que cerrar sesión revoca el acceso y que los roles de auditor y operador conservan sus restricciones. La sesión segura no se conserva al entrar por HTTP local: usa el dominio HTTPS para estas pruebas.

```sh
curl --fail https://once.example.com/api/health
curl --fail 'https://once.example.com/api/public/partidos/page?page_size=5'
curl -N --max-time 20 'https://once.example.com/api/public/changes?topics=matches'
```

La última consulta debe recibir `event: ready` y después un comentario `heartbeat`, incluso cuando no haya cambios. Al llegar a los 20 segundos, curl termina por el límite de tiempo; eso es esperado en una conexión SSE abierta. Comprueba también una ruta profunda recargando el navegador y varios escudos locales.

En **Datos → Automatización**, comprueba la cuenta de API-Football y prepara únicamente competiciones y temporadas permitidas. La existencia de una clave no confirma acceso a resultados actuales. Empieza por un calendario, revisa el trabajo y sus incidencias, y activa después el detalle por lotes. Las consultas se comparten entre todos los visitantes desde PostgreSQL; cada visita no debe consultar al proveedor. Consulta el [manual de automatización](../automation.md).

## 4. Operar y actualizar

Conserva copias verificadas de la base y los medios fuera del servidor, con acceso privado. Antes de actualizar, pausa las importaciones y evita ediciones durante la copia:

```sh
python3 -m scripts.backup --include-media
docker compose up --build -d --wait
docker compose ps
```

Transfiere el `.dump`, el manifiesto `.json` y el archivo `.media.tar` al almacenamiento de respaldo. Ensaya su restauración en una instalación independiente antes de retirar una copia anterior. El [manual de transferencia](transfer.md) describe esa comprobación y el retorno a una copia; los cambios de esquema no admiten un downgrade destructivo automático.

Supervisa la salud de los cuatro servicios, el espacio de los volúmenes, la vigencia del certificado, las tareas fallidas y el presupuesto del proveedor. Los registros se consultan con `docker compose logs --tail=100 api worker`. No expongas pgAdmin ni PostgreSQL como paso de publicación.

Esta topología funciona en un solo servidor. No implementa alta disponibilidad ni recuperación automática ante la pérdida del host; ambas requieren un despliegue adicional con objetivos de disponibilidad y restauración definidos.
