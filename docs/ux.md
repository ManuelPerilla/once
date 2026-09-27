# Experiencia y diseño

ONCE tiene dos públicos diferentes. Esta distinción guía el diseño: el administrador organiza el fútbol; el producto público permite explorarlo.

## El administrador actual

El concepto es una mesa de control con lenguaje de publicación deportiva. La complejidad está en la composición y los detalles, no en los pasos necesarios para completar una tarea.

La cabecera identifica el entorno de administración. Cinco espacios permanecen a mano: Inicio, Catálogo, Matrículas, Partidos y Datos. En escritorio comparten un panel lateral con su pie, que se desplaza como una sola pieza; en pantallas bajas el panel admite desplazamiento interno. En móvil forman una barra flotante inferior con espacio reservado para no tapar el contenido.

### Inicio

Primero presenta el estado del espacio de trabajo: competiciones, equipos, partidos programados y equipos sin matrícula. Cada cifra lleva a la vista correspondiente.

Después aparecen los últimos partidos registrados, las referencias que necesitan revisión y la participación por competición. Si todavía no hay datos, se explica cómo empezar. No se muestran porcentajes de crecimiento, tendencias ni actividad ficticia.

“Últimos registrados” no significa “más recientes en el calendario”. Los partidos ya admiten fecha y hora; esa lista se ordena por registro, no por calendario. “En vivo” tampoco significa que haya una actualización automática: es el estado almacenado.

### Traer información sin aprender términos técnicos

Dentro de **Datos → Traer información**, la sección **Menos trabajo manual** agrupa seis tareas: añadir equipos y torneos, buscar escudos e imágenes, consultar partidos, conectar registros, traer partidos y completar un partido. Solo presenta un formulario a la vez. Cada tarea explica qué consulta, qué guarda y qué necesita antes de empezar.

Los registros de ONCE se eligen por nombre. Los números externos se explican junto a ejemplos y ayudas; el administrador no debe memorizar IDs internos. La importación del catálogo mantiene los pasos elegir → revisar → guardar y conserva las decisiones al consultar otra tarea. Durante una operación en curso se bloquea el cambio de tarea.

Los escudos se revisan junto a su autor, fuente y licencia antes de confirmar. La ficha de Wikidata se propone cuando ya está conectada. Una foto no se usa como escudo; un escudo existente no se reemplaza automáticamente. Si la fuente no tiene uno, se conservan las iniciales. Los detalles y las limitaciones están en [proveedores](providers.md).

### Catálogo

Competiciones, equipos, confederaciones, temporadas, fases, estadios, jugadores y plantillas tienen vistas independientes en el catálogo. Las primeras tres identidades disponen de edición; temporadas, fases, estadios y jugadores permiten crear y consultar. Plantillas ofrece consulta de vínculos guardados, sin editor manual. La búsqueda ignora acentos y mayúsculas. Los filtros se combinan, muestran el número de resultados y pueden limpiarse. Las identidades conservan filtros propios al cambiar de módulo. El país de un equipo no filtra el ámbito de sus competiciones: permite encontrar, por ejemplo, selecciones colombianas inscritas en un torneo mundial.

Los clubes y las selecciones se distinguen. Una matrícula representa participación real, no solo compatibilidad geográfica. Las competiciones globales deben seguir siendo accesibles aunque no tengan confederación asignada.

Crear y editar abre un diálogo. El listado sigue siendo el lugar al que volver después de guardar. La eliminación requiere confirmación y no comparte el énfasis de las acciones habituales.

### Matrículas y partidos

El registro de matrículas y su formulario se muestran en pestañas separadas. El registro se puede filtrar por equipo, competición, tipo y ausencia de matrícula. El modelo actual relaciona equipo y competición sin distinguir temporada. La matrícula se hace en dos pasos: elegir la competición y después un equipo compatible que aún no esté inscrito. Si no hay opciones, se explica por qué puede ocurrir.

Para un partido, ambos equipos deben estar matriculados y no pueden ser el mismo. Las reglas las comprueba también la API, no solo el formulario.

Los partidos tienen filtros por nombre, competición, temporada, fase, equipo, estado y rango de fechas. Cambiar de competición limpia temporada, fase y equipo; cambiar de temporada limpia fase. Las fechas se interpretan en la zona horaria del navegador. La ficha separa contexto, estadísticas, eventos y alineaciones; los jugadores se presentan por nombre.

Los marcadores tienen jerarquía propia. Un encuentro programado muestra “vs”, no un 0–0 que pueda confundirse con un resultado.

### Control de datos

**Datos → Control de datos** separa incidencias, importaciones, conexiones, observaciones e imágenes. Las lecturas están paginadas, indican fuente y fecha cuando existen, y no modifican registros ni consultan proveedores. El inventario y los límites de trazabilidad se pueden desplegar a petición. No se presenta como una auditoría completa: todavía falta un historial durable de cambios manuales con autores y valores anteriores. Consulta el [alcance del control](control-datos.md) y el [manual de administración](administracion.md).

## Identidad visual

Barlow Condensed da carácter a titulares y cifras; DM Sans sostiene las tareas y la lectura. Las fuentes se sirven desde el proyecto.

El azul noche identifica el espacio, el fondo claro deja respirar la información y el lima señala las acciones principales. Las líneas, números de archivo y pequeños rótulos remiten a una ficha técnica de fútbol. No llevan información imprescindible por sí solos.

Las superficies usan esquinas suaves de 12–36 píxeles, sombras discretas y acciones en forma de píldora. El cuerpo de lectura y los campos usan 16 píxeles; las ayudas y etiquetas, 12–14. Los escudos remotos se muestran sin fondo ni borde añadido, conservando su proporción y transparencia; los archivos que ya incluyen un fondo opaco conservan ese fondo. El pie permite consultar los créditos de los escudos importados que están en uso.

La ilustración principal es una cancha táctica en SVG/CSS. La portada permite pausar su animación. Los recursos decorativos anteriores se conservan en el proyecto; ningún botón ni dato depende de texto dibujado en una imagen.

## Accesibilidad y móvil

Las acciones tienen nombres explícitos. Los campos conservan etiquetas y ayudas asociadas. El teclado puede recorrer los tabs, abrir los formularios y cerrarlos con Escape. Los diálogos nativos contienen el foco mientras están abiertos y bloquean el scroll del fondo.

En móvil, las columnas se apilan, los filtros usan el ancho disponible y las acciones de cada registro tienen su propio espacio. La información no depende de hover ni exclusivamente del color. Las animaciones se reducen cuando el sistema lo solicita.

Los controles principales disponen de al menos 44 píxeles de altura. Los formularios móviles se abren como una hoja inferior, con texto de 16 píxeles en los campos. Cambiar de sección vuelve al inicio y mueve el foco al contenido. Las barras flotantes respetan el área segura del dispositivo y las notificaciones se colocan por encima de ellas.

Antes de dar una pantalla por terminada, hay que verla con nombres largos, logos que no cargan, listas vacías, filtros sin coincidencias y errores de servidor. También probarla con teclado y sin desbordamiento horizontal.

## La experiencia pública

La primera superficie pública vive en `/explore`. La entrada responde a la idea original: un partido es una puerta hacia el resto del fútbol.

La portada destaca encuentros reales almacenados y ofrece acceso a equipos y competiciones. El detalle de partido conserva el marcador como centro y añade contexto progresivamente cuando existe: fecha, temporada, fase, jornada, estadio, estadísticas, timeline de eventos y alineaciones.

La cancha, el timeline, la forma reciente y otros elementos se dibujan con HTML/CSS/SVG. Las transiciones deben reforzar continuidad entre entidades, no ocultar esperas ni convertir cada navegación en un espectáculo.

Las fichas públicas dividen los detalles en secciones seleccionables. La competición comparte una temporada entre partidos, fases y clasificación; los partidos sin temporada tienen una vista propia. La clasificación se calcula con resultados guardados y no incorpora ajustes disciplinarios oficiales. La búsqueda global agrupa los resultados por tipo de entidad.

Los perfiles de equipo muestran encuentros relacionados y forma reciente calculada solo con partidos finalizados. Las competiciones muestran sus ediciones. Los jugadores aparecen cuando alineaciones o eventos proporcionan contexto suficiente.

La interfaz sigue la misma regla que el administrador: ausencia de datos no se reemplaza por métricas ficticias.
