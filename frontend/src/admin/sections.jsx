export const workspaceSections = {
  inicio: {
    label: "Inicio",
    eyebrow: "EL LADO DEL FÚTBOL QUE LO HACE POSIBLE",
    title: (
      <>
        El juego,
        <br />
        <em>en orden.</em>
      </>
    ),
    description:
      "Tú mueves las piezas. Aquí conectas competiciones, equipos y encuentros para que todo lo demás suceda.",
    action: "Explorar el catálogo",
    icon: "grid",
  },
  ecosistema: {
    label: "Catálogo",
    eyebrow: "02 / EL ARCHIVO DEL FÚTBOL",
    title: (
      <>
        El mapa
        <br />
        <em>del juego.</em>
      </>
    ),
    description:
      "Da forma a tu catálogo y encuentra lo que necesitas sin perder de vista el conjunto.",
    action: "Añadir registro",
    icon: "plus",
  },
  matriculas: {
    label: "Matrículas",
    eyebrow: "03 / CONEXIONES QUE HACEN EQUIPO",
    title: (
      <>
        Cada equipo,
        <br />
        <em>en su lugar.</em>
      </>
    ),
    description:
      "Conecta equipos y competiciones. Revisa las matrículas existentes y completa las que faltan.",
    action: "Crear matrícula",
    icon: "link",
  },
  arena: {
    label: "Partidos",
    eyebrow: "04 / DEL ENCUENTRO AL MARCADOR",
    title: (
      <>
        Que ruede
        <br />
        <em>el balón.</em>
      </>
    ),
    description:
      "Registra los partidos de tus competiciones y consulta el estado de cada encuentro.",
    action: "Registrar partido",
    icon: "plus",
  },
  datos: {
    label: "Datos",
    icon: "globe",
  },
};

export const workspaceNavigation = [
  ["inicio", "01"],
  ["ecosistema", "02"],
  ["matriculas", "03"],
  ["arena", "04"],
  ["datos", "05"],
];
