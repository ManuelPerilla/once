// An isolated, explicitly labelled visual demo. Never sent to the API or database.
const competitions = [
  {
    id: 1,
    nombre: "Liga del Horizonte",
    pais: "Colombia",
    tipo: "liga_nacional",
    logo: "",
    temporadas: [],
  },
  {
    id: 2,
    nombre: "Copa del Pacífico",
    pais: "Internacional",
    tipo: "internacional_clubes",
    logo: "",
    temporadas: [],
  },
  {
    id: 3,
    nombre: "Copa Capital",
    pais: "Colombia",
    tipo: "copa_nacional",
    logo: "",
    temporadas: [],
  },
];
const teams = [
  [1, "Atlético del Norte", "Colombia"],
  [2, "Deportivo Capital", "Colombia"],
  [3, "Unión del Puerto", "Colombia"],
  [4, "Estrella del Sur", "Colombia"],
  [5, "Club Aurora", "Ecuador"],
  [6, "Sporting del Valle", "Perú"],
].map(([id, nombre, pais]) => ({
  id,
  nombre,
  pais,
  tipo: "club",
  logo: "",
  competiciones: [competitions[id > 4 ? 1 : 0]],
}));
const players = [
  {
    id: 1,
    nombre: "Tomás Rivera",
    nacionalidad: "Colombia",
    posicion: "Delantero",
  },
  {
    id: 2,
    nombre: "Mateo Sol",
    nacionalidad: "Colombia",
    posicion: "Mediocampista",
  },
  {
    id: 3,
    nombre: "Nicolás Sierra",
    nacionalidad: "Colombia",
    posicion: "Delantero",
  },
];
const fixtures = [
  [1, 1, 2, 1, "en vivo", 2, 1],
  [2, 3, 4, 1, "programado", 0, 0],
  [3, 5, 6, 2, "programado", 0, 0],
  [4, 2, 3, 3, "finalizado", 1, 1],
  [5, 4, 1, 1, "finalizado", 0, 2],
  [6, 6, 5, 2, "finalizado", 3, 1],
];
const matches = fixtures.map(
  ([
    id,
    home,
    away,
    competition,
    estado,
    marcador_local,
    marcador_visitante,
  ]) => ({
    id,
    equipo_local_id: home,
    equipo_visitante_id: away,
    competicion_id: competition,
    equipo_local: teams.find((t) => t.id === home),
    equipo_visitante: teams.find((t) => t.id === away),
    competicion: competitions.find((c) => c.id === competition),
    estado,
    marcador_local,
    marcador_visitante,
    fecha: `2026-09-${id <= 3 ? "26" : "23"}T${id <= 3 ? 17 + id : 20}:00:00-05:00`,
    jornada: "12",
    estadio: { nombre: "Estadio del Horizonte", ciudad: "Ciudad de muestra" },
    estadisticas:
      estado === "programado"
        ? []
        : [
            {
              posesion_local: 58,
              posesion_visitante: 42,
              tiros_puerta_local: 7,
              tiros_puerta_visitante: 4,
            },
          ],
    eventos:
      id === 1
        ? [
            {
              id: 1,
              tipo: "gol",
              minuto: 12,
              adicional: 0,
              equipo_id: 1,
              jugador_id: 1,
              detalle: "Abre el marcador",
            },
            {
              id: 2,
              tipo: "gol",
              minuto: 38,
              adicional: 0,
              equipo_id: 2,
              jugador_id: 3,
              detalle: "Llega el empate",
            },
            {
              id: 3,
              tipo: "tarjeta amarilla",
              minuto: 52,
              adicional: 0,
              equipo_id: 1,
              jugador_id: 2,
            },
            {
              id: 4,
              tipo: "gol",
              minuto: 67,
              adicional: 0,
              equipo_id: 1,
              jugador_id: 1,
              detalle: "El Norte vuelve a ponerse arriba",
            },
          ]
        : [],
    alineaciones: [],
  }),
);
export const demoData = { competitions, teams, players, matches };
