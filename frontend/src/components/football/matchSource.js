const providers = {
  manual: "Registro manual",
  "api-football": "API-Football",
  openfootball: "Archivo abierto",
};

export function matchSourceLabel(source) {
  return providers[source?.provider] || "Origen sin confirmar";
}

export function sourceVerificationDate(source) {
  if (!source?.verified_at) return null;
  const date = new Date(source.verified_at);
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}
