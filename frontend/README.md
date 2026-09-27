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
| `src/admin/ProviderConsole.jsx` | Tareas guiadas para consultar, conectar e importar información e imágenes. |
| `src/admin/DataWorkspace.jsx` y `ControlView.jsx` | Separar operaciones de importación y revisión local de calidad y procedencia. |
| `src/admin/ModuleTabs.jsx` y `catalogModules.js` | Navegación por módulos y selección accesible con teclado. |
| `src/admin/context/` | Temporadas, fases, estadios y jugadores con filtros propios y creación explícita. |
| `src/admin/RostersView.jsx` | Consulta paginada de vínculos entre jugadores y equipos. |
| `src/admin/organization.js` | Filtros de partidos y matrículas sin dependencias visuales. |
| `src/admin/MatchDetailView.jsx` | Contexto, estadísticas, eventos y alineaciones en vistas separadas. |
| `src/admin/SourceEntitySelect.jsx` | Elegir registros por nombre, con carga cancelable y filtros de participación. |
| `src/public/PublicApp.jsx` | Datos públicos y fichas conectadas. |
| `src/public/routes.js` | Correspondencia entre enlaces y entidades. |
| `src/public/ExploreHome.jsx` | Portada y exploradores filtrables. |
| `src/public/components/` | Cancha, cronología, clasificación, búsqueda y conexiones. |
| `src/components/` | Elementos compartidos de interfaz y fútbol. |
| `src/styles/` | Tokens, tipografías y movimiento. |
| `src/api.js` | Peticiones del mismo origen, cookie, cancelación y errores. |

`index.css` fija el orden de las capas visuales; `styles/surfaces.css` reúne el acabado compartido de escudos y créditos. `--orange` es un alias histórico del lima para compatibilidad. La marca usa azul noche, lima y blanco; radios y sombras comunes se definen en `styles/tokens.css`.

La búsqueda admite flechas, Enter y Escape; los diálogos controlan el foco. La cancha se puede pausar y respeta movimiento reducido. Las fechas introducidas con hora local se envían en UTC.

Los datos ficticios viven en `demoData.js`, se cargan solo con `?demo=1` y no escriben ni consultan la API al explorar la demo. Abrir explícitamente los créditos de escudos consulta los créditos guardados en la instalación. Las fuentes y sus licencias están en `public/fonts`; los escudos remotos conservan su silueta y tienen alternativa con iniciales.

El gestor de dependencias es npm, con `package-lock.json`. Para correr ONCE no necesitas Node en Windows: la compilación sucede dentro de Docker.
