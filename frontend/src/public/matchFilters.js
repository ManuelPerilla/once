export function sortMatches(matches) {
  return [...matches].sort((a, b) => {
    const rank = { "en vivo": 0, programado: 1, finalizado: 2 };
    const status = (rank[a.estado] ?? 3) - (rank[b.estado] ?? 3);
    if (status) return status;
    const missingDate = a.estado === "programado" ? Infinity : -Infinity;
    const aDate = Number.isFinite(Date.parse(a.fecha))
      ? Date.parse(a.fecha)
      : missingDate;
    const bDate = Number.isFinite(Date.parse(b.fecha))
      ? Date.parse(b.fecha)
      : missingDate;
    return (
      (a.estado === "programado" ? aDate - bDate : bDate - aDate) || b.id - a.id
    );
  });
}

export function normalizeSearch(value = "") {
  return String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

export function filterMatches(
  matches,
  status = "",
  competition = "",
  { query = "", season = "" } = {},
) {
  const search = normalizeSearch(query);
  return sortMatches(matches).filter(
    (match) =>
      (!status || match.estado === status) &&
      (!competition || String(match.competicion_id) === String(competition)) &&
      (!season ||
        (season === "unassigned"
          ? !match.temporada_id
          : String(match.temporada_id) === String(season))) &&
      (!search ||
        normalizeSearch(
          `${match.equipo_local?.nombre || ""} ${match.equipo_visitante?.nombre || ""} ${match.competicion?.nombre || ""}`,
        ).includes(search)),
  );
}

export function formatMatchDate(value) {
  if (!value || Number.isNaN(Date.parse(value))) return "Fecha por confirmar";
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
