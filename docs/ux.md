# Experiencia y diseño

VÉRTICE tiene dos públicos diferentes. Esta distinción guía el diseño: el administrador organiza el fútbol; el producto público permitirá explorarlo.

## El administrador actual

El concepto es una mesa de control con lenguaje de publicación deportiva. La complejidad está en la composición y los detalles, no en los pasos necesarios para completar una tarea.

La cabecera identifica el entorno de administración. Debajo, cuatro espacios numerados permanecen a mano: Inicio, Catálogo, Matrículas y Partidos. No hay un menú de herramientas ocultas.

### Inicio

Primero presenta el estado del espacio de trabajo: competiciones, equipos, partidos programados y equipos sin matrícula. Cada cifra lleva a la vista correspondiente.

Después aparecen los últimos partidos registrados, las referencias que necesitan revisión y la participación por competición. Si todavía no hay datos, se explica cómo empezar. No se muestran porcentajes de crecimiento, tendencias ni actividad ficticia.

“Últimos registrados” no significa “más recientes en el calendario”. El modelo aún no guarda fechas de encuentro. “En vivo” tampoco significa que haya una actualización automática: es el estado almacenado.

### Catálogo

Competiciones, equipos y confederaciones comparten un archivo, pero se consultan por separado. La búsqueda ignora acentos y mayúsculas. Los filtros se combinan, muestran el número de resultados y pueden limpiarse.

Los clubes y las selecciones se distinguen. Una matrícula representa participación real, no solo compatibilidad geográfica. Las competiciones globales deben seguir siendo accesibles aunque no tengan confederación asignada.

Crear y editar abre un diálogo. El listado sigue siendo el lugar al que volver después de guardar. La eliminación requiere confirmación y no comparte el énfasis de las acciones habituales.

### Matrículas y partidos

La matrícula se hace en dos pasos: elegir la competición y después un equipo compatible que aún no esté inscrito. Si no hay opciones, se explica por qué puede ocurrir.

Para un partido, ambos equipos deben estar matriculados y no pueden ser el mismo. Las reglas las comprueba también la API, no solo el formulario.

Los marcadores tienen jerarquía propia. Un encuentro programado muestra “vs”, no un 0–0 que pueda confundirse con un resultado.

## Identidad visual

Barlow Condensed da carácter a titulares y cifras; DM Sans sostiene las tareas y la lectura. Las fuentes se sirven desde el proyecto.

El verde profundo identifica el espacio, el fondo claro deja respirar la información y el naranja señala las acciones principales y la sección activa. Las líneas, números de archivo y pequeños rótulos remiten a una ficha técnica de fútbol. No llevan información imprescindible por sí solos.

Los renders son una colección de objetos del juego: estadio, trofeo y escudos, acreditaciones, balón y silbato. Comparten materiales y luz. Se sirven como WebP locales y están marcados como decorativos; ningún botón ni dato está dibujado dentro de una imagen.

## Accesibilidad y móvil

Las acciones tienen nombres explícitos. Los campos conservan etiquetas y ayudas asociadas. El teclado puede recorrer los tabs, abrir los formularios y cerrarlos con Escape. Los diálogos nativos contienen el foco mientras están abiertos y bloquean el scroll del fondo.

En móvil, las columnas se apilan, los filtros usan el ancho disponible y las acciones de cada registro tienen su propio espacio. La información no depende de hover ni exclusivamente del color. Las animaciones se reducen cuando el sistema lo solicita.

Antes de dar una pantalla por terminada, hay que verla con nombres largos, logos que no cargan, listas vacías, filtros sin coincidencias y errores de servidor. También probarla con teclado y sin desbordamiento horizontal.

## La experiencia pública

La primera superficie pública vive en `/explore`. La entrada responde a la idea original: un partido es una puerta hacia el resto del fútbol.

La portada destaca encuentros reales almacenados y ofrece acceso a equipos y competiciones. El detalle de partido conserva el marcador como centro y añade contexto progresivamente cuando existe: fecha, temporada, fase, jornada, estadio, estadísticas, timeline de eventos y alineaciones.

La cancha, el timeline, la forma reciente y otros elementos se dibujan con HTML/CSS/SVG. Las transiciones deben reforzar continuidad entre entidades, no ocultar esperas ni convertir cada navegación en un espectáculo.

Los perfiles de equipo muestran encuentros relacionados y forma reciente. Las competiciones muestran sus ediciones. Los jugadores aparecen cuando alineaciones o eventos proporcionan contexto suficiente.

La interfaz sigue la misma regla que el administrador: ausencia de datos no se reemplaza por métricas ficticias.
