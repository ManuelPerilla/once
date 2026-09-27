export const EMPTY_FILTERS = {
  search: "",
  confederation: "",
  country: "",
  competitionType: "",
  teamType: "",
  competition: "",
};

export const COMPETITION_TYPES = {
  liga_nacional: "Liga nacional",
  copa_nacional: "Copa nacional",
  internacional_clubes: "Internacional de clubes",
  internacional_selecciones: "Internacional de selecciones",
};

export function normalize(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function matchesConfederation(item, confederation) {
  if (!confederation) return true;
  if (confederation === "unassigned") return item.confederacion_id == null;
  return String(item.confederacion_id) === String(confederation);
}

function matchesGeography(item, filters) {
  return (
    matchesConfederation(item, filters.confederation) &&
    (!filters.country || normalize(item.pais) === normalize(filters.country))
  );
}

const byName = (a, b) =>
  a.nombre.localeCompare(b.nombre, "es", {
    sensitivity: "base",
    numeric: true,
  });

export function countryOptions(competitions, teams, confederation) {
  const countries = new Map();
  [...competitions, ...teams]
    .filter((item) => matchesConfederation(item, confederation))
    .forEach((item) => {
      const key = normalize(item.pais);
      if (key && !countries.has(key)) countries.set(key, item.pais.trim());
    });
  return [...countries.values()].sort((a, b) => a.localeCompare(b, "es"));
}

export function filterCatalog(competitions, teams, filters = EMPTY_FILTERS) {
  const search = normalize(filters.search);
  // Enrollment scope is independent of team geography (e.g. Colombia in a World Cup).
  const availableCompetitions = [...competitions].sort(byName);
  const selectedCompetition = availableCompetitions.find(
    (item) => String(item.id) === String(filters.competition),
  );
  return {
    availableCompetitions,
    competitions: availableCompetitions.filter(
      (item) =>
        matchesGeography(item, filters) &&
        (!filters.competitionType || item.tipo === filters.competitionType) &&
        normalize(item.nombre).includes(search),
    ),
    teams: teams
      .filter(
        (item) =>
          matchesGeography(item, filters) &&
          normalize(item.nombre).includes(search) &&
          (!filters.teamType || item.tipo === filters.teamType) &&
          (!selectedCompetition ||
            item.competiciones?.some(
              (comp) => String(comp.id) === String(selectedCompetition.id),
            )),
      )
      .sort(byName),
    // A deleted competition cannot leave an invisible, stale membership filter.
    selectedCompetition: selectedCompetition
      ? String(selectedCompetition.id)
      : "",
  };
}

export function changeFilters(filters, field, value) {
  const next = { ...filters, [field]: value };
  if (field === "confederation") next.country = "";
  return next;
}
