import { normalize } from "../catalogFilters.js";

export const EMPTY_MATCH_FILTERS = {
  search: "",
  competition: "",
  season: "",
  phase: "",
  team: "",
  from: "",
  to: "",
  sort: "recent",
};

export function changeMatchContext(filters, field, value) {
  const next = { ...filters, [field]: value };
  if (field === "competition") {
    next.season = "";
    next.phase = "";
    next.team = "";
  }
  if (field === "season") next.phase = "";
  return next;
}

export function localDate(value) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function filterMatches(matches, filters, status = "") {
  const search = normalize(filters.search);
  return matches
    .filter((match) => {
      const day = localDate(match.fecha);
      return (
        (!status ||
          (status === "incompletos"
            ? !match.competicion ||
              !match.equipo_local ||
              !match.equipo_visitante
            : match.estado === status)) &&
        (!filters.competition ||
          String(match.competicion_id) === filters.competition) &&
        (!filters.season ||
          (filters.season === "unassigned"
            ? !match.temporada_id
            : String(match.temporada_id) === filters.season)) &&
        (!filters.phase || String(match.fase_id) === filters.phase) &&
        (!filters.team ||
          [match.equipo_local_id, match.equipo_visitante_id].some(
            (id) => String(id) === filters.team,
          )) &&
        (!filters.from || (day && day >= filters.from)) &&
        (!filters.to || (day && day <= filters.to)) &&
        (!search ||
          normalize(
            [
              match.equipo_local?.nombre,
              match.equipo_visitante?.nombre,
              match.competicion?.nombre,
              match.jornada,
            ].join(" "),
          ).includes(search))
      );
    })
    .sort((a, b) => {
      if (filters.sort === "recent") return b.id - a.id;
      const left = a.fecha ? new Date(a.fecha).getTime() : null;
      const right = b.fecha ? new Date(b.fecha).getTime() : null;
      if (left === null || right === null)
        return left === right ? b.id - a.id : left === null ? 1 : -1;
      return (
        (filters.sort === "oldest" ? left - right : right - left) || b.id - a.id
      );
    });
}

export function filterEnrollments(
  teams,
  { search = "", competition = "", state = "", type = "" },
) {
  return teams
    .filter(
      (team) =>
        normalize(team.nombre).includes(normalize(search)) &&
        (!type || team.tipo === type) &&
        (!state ||
          (state === "free"
            ? !team.competiciones?.length
            : Boolean(team.competiciones?.length))) &&
        (!competition ||
          team.competiciones?.some((item) => String(item.id) === competition)),
    )
    .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
}
