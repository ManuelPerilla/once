const fixtureFeatures = [
  ["events", "Jugadas"],
  ["lineups", "Alineaciones"],
  ["statistics_fixtures", "Estadísticas del partido"],
  ["statistics_players", "Estadísticas de jugadores"],
];

export function coverageLabels(coverage = {}) {
  return [
    ...(coverage.standings === true ? ["Clasificaciones"] : []),
    ...fixtureFeatures
      .filter(([key]) => coverage.fixtures?.[key] === true)
      .map(([, label]) => label),
  ];
}

export function sortedSeasons(seasons = [], allowedSeasons = null) {
  const accessKnown =
    Array.isArray(allowedSeasons) &&
    allowedSeasons.every(
      (year) => Number.isInteger(year) && year >= 1900 && year <= 2200,
    );
  return seasons
    .filter(
      (season) =>
        Number.isInteger(season.year) &&
        (!accessKnown || allowedSeasons.includes(season.year)),
    )
    .toSorted((left, right) => right.year - left.year);
}

export function accountLabel(connection) {
  if (!connection) return "Consultando configuración";
  if (!connection.configured) return "Pendiente de conectar";
  if (connection.state === "error") return "La última comprobación falló";
  if (connection.state === "connected" && connection.account?.active === true)
    return "Cuenta comprobada";
  if (connection.account?.active === false) return "Cuenta sin acceso activo";
  return "Credencial configurada · falta comprobar";
}
