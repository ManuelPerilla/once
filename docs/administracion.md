# Manual de administración por módulos

Abre [ONCE local](http://localhost/) e inicia sesión con el administrador configurado para tu instalación. La barra principal ofrece cinco espacios. En móvil está en la parte inferior y no cubre los controles del contenido.

## Dónde hacer cada tarea

| Espacio | Para qué sirve | Qué queda fuera |
| --- | --- | --- |
| Inicio | Consultar el resumen, pendientes y accesos a cada área. | Importar o editar dentro del resumen. |
| Catálogo | Mantener las identidades y la estructura deportiva, un módulo a la vez. | Marcadores y observaciones externas. |
| Matrículas | Consultar o registrar la participación de equipos en competiciones. | Plantillas de jugadores y alineaciones. |
| Partidos | Buscar encuentros y consultar sus fichas. | Modificar identidades del catálogo. |
| Datos | Controlar automatización, auditar, corregir, definir reglas y gestionar fuentes/cuentas. | Mezclar observaciones externas con hechos confirmados. |

## Catálogo: ocho secciones

- **Competiciones:** identidad de una liga o copa, tipo, ámbito y confederación.
- **Equipos:** clubes y selecciones. Sus matrículas se gestionan en el espacio de participación.
- **Confederaciones:** organismos que agrupan equipos y competiciones.
- **Temporadas:** ediciones de una competición, con fechas y estado.
- **Fases:** etapas de una temporada. Primero elige la competición y después su edición.
- **Estadios:** sedes, con búsqueda por nombre y filtros por país y ciudad.
- **Jugadores:** identidad personal, nacionalidad y posición.
- **Plantillas:** consulta de los vínculos jugador → equipo con fechas y dorsal. “Sin cierre registrado” significa que falta fecha final; no demuestra vigencia actual.

Las primeras tres secciones permiten crear, editar y eliminar con confirmación; se bloquea eliminar equipos o competiciones con historial de ediciones. Temporadas, fases, estadios y jugadores permiten crear y consultar. Las correcciones específicas también están disponibles en **Datos → Automatización → Correcciones protegidas**, con motivo e historial. Plantillas es de consulta.

Los filtros de competición, equipo y confederación se conservan por separado durante la sesión de trabajo. “Ver equipos” dentro de una competición abre el listado de equipos con esa matrícula seleccionada y sin heredar búsquedas incompatibles. El país del equipo y el ámbito del torneo son dimensiones diferentes: Colombia puede participar en un torneo mundial.

## Participación y contexto deportivo

Una **matrícula general** relaciona un equipo con una competición y conserva el flujo anterior. La participación de una **edición, fase o grupo** es independiente y se registra mediante importación o desde las reglas deportivas. Una matrícula general no demuestra participación en un año concreto. El registro y el formulario se presentan en pestañas distintas; “Solo sin matrícula” elimina el filtro de torneo para evitar una combinación contradictoria.

Una **alineación** pertenece a un partido. Una **plantilla** registra la pertenencia de un jugador a un equipo. Ninguna de estas dos relaciones equivale a una matrícula de equipo en una competición.

## Encontrar y revisar un partido

1. Entra en **Partidos** y elige la competición si necesitas limitar el calendario.
2. Selecciona temporada y fase. Al cambiar una selección superior se limpian sus dependencias.
3. Combina equipo, estado, búsqueda o fechas. El rango incluye los días inicial y final en la zona horaria del navegador; excluye encuentros sin fecha.
4. Abre **Consultar ficha** y elige Ficha, Estadísticas, Eventos o Alineaciones. Solo se muestra el tipo de información seleccionado.

“Sin temporada asignada” es una vista explícita dentro de una competición. “En vivo” indica el último estado recibido; su frescura depende de la fuente y la actualización habilitada. Un archivo histórico no acredita directo. “Últimos registrados” ordena por alta, mientras que los otros órdenes usan la fecha del encuentro. Un marcador desconocido se muestra como «—».

Las vistas públicas también separan la información. En una competición, partidos, fases y clasificación comparten la edición seleccionada. Los encuentros sin edición no se suman a la clasificación de una temporada.

## Traer información y revisarla

En **Datos → Traer información**, elige una tarea: añadir equipos y torneos, buscar escudos, consultar partidos, conectar registros, traer partidos o completar un partido. El flujo de catálogo conserva la revisión antes del guardado explícito. Las tareas que necesitan una conexión todavía no configurada lo explican en pantalla.

En **Datos → Control de datos**:

- **Por revisar:** abre una señal para ver qué registros la generan. No todos los avisos son errores; algunos campos son opcionales.
- **Importaciones:** consulta colecciones y el último resultado de aplicación guardado.
- **Conexiones:** revisa qué identidad externa corresponde a cada registro local.
- **Datos consultados:** consulta la última observación conservada de cada categoría.
- **Imágenes y licencias:** revisa autoría, origen y condiciones de las imágenes guardadas.

Las listas se filtran antes de paginar. La búsqueda de una sección no se aplica a las demás. La revisión no escribe en el catálogo y no pide datos a internet. Una fecha de consulta no es la fecha de creación del registro local; si falta una fecha se muestra como no registrada.

## Automatización y responsabilidades

**Datos → Automatización** reúne pausa general y por tarea, actividad, incidencias, correcciones protegidas, historial, reglas deportivas y cuentas. Los administradores configuran fuentes y revisan identidades excepcionales; el trabajador incorpora datos válidos. Operadores, editores y auditores tienen permisos distintos. Consulta el [manual de automatización](automation.md) para activar los perfiles gratuitos, entender las cuotas y recuperar una instalación.

Las tablas publicadas por una fuente se muestran separadas de las calculadas por ONCE. Una tabla calculada necesita reglas verificadas y un ámbito coherente. La ausencia de reglamento, resultados o cobertura no se presenta como clasificación oficial. La infraestructura está implementada, pero el directo colombiano requiere una fuente accesible que todavía no está configurada en este piloto gratuito.
