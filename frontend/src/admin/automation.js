export const automationModes = [
  [
    "paused",
    "Pausado",
    "Conserva tus datos y detiene las nuevas actualizaciones.",
  ],
  [
    "observe",
    "Solo comprobar",
    "Consulta la fuente y registra diferencias sin publicar cambios.",
  ],
  [
    "automatic",
    "Automático",
    "Publica los cambios válidos y aparta las excepciones para revisión.",
  ],
];

export const operationLabels = {
  paused: "Pausado",
  pausing: "Pausando",
  observe: "Solo comprobar",
  automatic: "Automático",
  queued: "En espera",
  running: "Actualizando",
  completed: "Completado",
  succeeded: "Completado",
  failed: "Requiere atención",
  retry: "Reintentará",
  retrying: "Reintentará",
  cancelled: "Cancelado",
  blocked: "Requiere configuración",
  pending: "Pendiente",
  open: "Por revisar",
  resolved: "Resuelto",
  healthy: "Disponible",
  stale: "Con retraso",
  idle: "En espera",
  no_coverage: "Sin cobertura",
  observed: "Comprobado",
  updating: "Actualizando",
  attention: "Requiere atención",
  waiting: "En espera",
  delayed: "Con retraso",
  checked: "Comprobado",
  done: "Completado",
  scope_created: "Automatización creada",
  scope_updated: "Configuración actualizada",
  scope_prepared: "Tarea preparada para revisión",
  provider_connection_check: "Cuenta y cobertura comprobadas",
  global_mode: "Control general actualizado",
  issue_resolved: "Revisión registrada",
};

export const scopeKinds = {
  catalog: "Equipos y competiciones",
  discovery: "Ediciones y participantes",
  fixtures: "Calendario y resultados",
  detail: "Detalle de un partido",
  details_batch: "Detalle de los partidos seleccionados",
  history: "Historia verificada",
  media: "Escudos e imágenes",
  standings: "Clasificaciones de la fuente",
  standings_batch: "Clasificaciones de la temporada",
  archive: "Archivo histórico colombiano",
};

export function humanDate(value) {
  if (!value) return "Todavía no";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Sin fecha disponible"
    : date.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

export function remainingBudget(used, limit) {
  if (limit == null) return "Sin límite configurado";
  return `${Math.max(0, limit - (used || 0))} de ${limit} disponibles`;
}

export function canRunScope(globalMode, scopeMode) {
  return (
    ["observe", "automatic"].includes(globalMode) &&
    ["observe", "automatic"].includes(scopeMode)
  );
}

export function displayValue(value) {
  if (value === null || value === undefined || value === "") return "Sin dato";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
