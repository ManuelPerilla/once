// UI guidance only; the API enforces the same participation constraints.
export function enrollmentCandidates(teams, competition) {
  if (!competition) return [];
  return teams.filter((team) => {
    if (
      (competition.tipo === "internacional_selecciones") !==
      (team.tipo === "seleccion")
    )
      return false;
    if (
      ["liga_nacional", "copa_nacional"].includes(competition.tipo) &&
      team.pais !== competition.pais
    )
      return false;
    if (
      competition.confederacion_id &&
      team.confederacion_id !== competition.confederacion_id
    )
      return false;
    return !team.competiciones?.some((item) => item.id === competition.id);
  });
}
