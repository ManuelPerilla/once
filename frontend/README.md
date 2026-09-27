# Frontend de ONCE

React 19 y Vite, servido por NGINX en Docker. El [manual de despliegue](../docs/deployment/local.md) explica el conjunto completo; [desarrollo y pruebas](../docs/development.md) concentra los comandos para evitar instrucciones duplicadas.

## Organización

| Ubicación | Responsabilidad |
| --- | --- |
| `src/App.jsx` | Carga diferida del administrador o la experiencia pública. |
| `src/Dashboard.jsx` | Puerta de sesión del administrador. |
| `src/admin/useAdminData.js` | Sesión, lecturas, recargas y cancelación de respuestas obsoletas. |
| `src/admin/AdminWorkspace.jsx` | Composición de vistas y operaciones del administrador. |
| `src/admin/forms/` | Editores y controles compartidos. |
| `src/admin/CatalogImport.jsx` | Preparar, revisar y aplicar lotes de identidades. |
| `src/public/PublicApp.jsx` | Datos públicos y fichas conectadas. |
| `src/public/routes.js` | Correspondencia entre enlaces y entidades. |
| `src/public/ExploreHome.jsx` | Portada y exploradores filtrables. |
| `src/public/components/` | Cancha, cronología, clasificación, búsqueda y conexiones. |
| `src/components/` | Elementos compartidos de interfaz y fútbol. |
| `src/styles/` | Tokens, tipografías y movimiento. |
| `src/api.js` | Peticiones del mismo origen, cookie, cancelación y errores. |

`index.css` fija el orden de las capas visuales; las mejoras ONCE conservan la base existente. `--orange` es un alias histórico del lima para compatibilidad. La marca usa azul noche, lima y blanco.

La búsqueda admite flechas, Enter y Escape; los diálogos controlan el foco. La cancha se puede pausar y respeta movimiento reducido. Las fechas introducidas con hora local se envían en UTC.

Los datos ficticios viven en `demoData.js`, se cargan solo con `?demo=1` y no escriben ni consultan la API. Las fuentes y sus licencias están en `public/fonts`; los escudos remotos tienen alternativa con iniciales.

El gestor de dependencias es npm, con `package-lock.json`. Para correr ONCE no necesitas Node en Windows: la compilación sucede dentro de Docker.
