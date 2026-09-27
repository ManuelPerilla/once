export const emptyConfederation = () => ({ nombre: "", logo: "" });
export const emptyCompetition = () => ({
  ...emptyConfederation(),
  tipo: "liga_nacional",
  pais: "",
  confederacion_id: "",
});
export const emptyTeam = () => ({
  ...emptyConfederation(),
  tipo: "club",
  pais: "",
  confederacion_id: "",
});
export const emptyMatch = () => ({
  competicion_id: "",
  temporada_id: "",
  fase_id: "",
  estadio_id: "",
  fecha: "",
  jornada: "",
  equipo_local_id: "",
  equipo_visitante_id: "",
  marcador_local: "",
  marcador_visitante: "",
  estado: "programado",
});
