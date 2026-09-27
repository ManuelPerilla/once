export function routeFromPath(pathname) {
  const parts = pathname
    .replace(/^\/explore\/?/, "")
    .split("/")
    .filter(Boolean);
  if (parts[0] === "partidos" && parts[1])
    return { type: "match", id: Number(parts[1]) };
  if (parts[0] === "equipos" && parts[1])
    return { type: "team", id: Number(parts[1]) };
  if (parts[0] === "competiciones" && parts[1])
    return { type: "competition", id: Number(parts[1]) };
  if (parts[0] === "jugadores" && parts[1])
    return { type: "player", id: Number(parts[1]) };
  if (parts[0] === "partidos") return { type: "matches" };
  if (parts[0] === "equipos") return { type: "teams" };
  if (parts[0] === "competiciones") return { type: "competitions" };
  return { type: "home" };
}

export function publicPath(type, id) {
  if (type === "home") return "/explore";
  const browse = {
    matches: "partidos",
    teams: "equipos",
    competitions: "competiciones",
  };
  if (browse[type]) return `/explore/${browse[type]}`;
  const plural = {
    match: "partidos",
    team: "equipos",
    competition: "competiciones",
    player: "jugadores",
  }[type];
  return `/explore/${plural}/${id}`;
}
