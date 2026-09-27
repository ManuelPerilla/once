import { operationLabels } from "./automation";

const metricLabels = {
  changed: "cambios publicados",
  created: "registros añadidos",
  updated: "registros actualizados",
  imported: "partidos incorporados",
  skipped: "registros pendientes",
  events: "jugadas",
  lineup_entries: "participaciones en alineaciones",
  players_touched: "jugadores",
  matches_checked: "partidos consultados para completar su detalle",
  matches_received: "partidos devueltos por la fuente",
  tables: "clasificaciones incorporadas",
};
export function JobOutcome({ result, detail, status }) {
  const note =
    typeof detail === "string" ? detail : detail?.reason || detail?.note;
  return (
    <>
      {note && <p>{note}</p>}
      {detail?.mode && (
        <p>
          Modo general: {operationLabels[detail.previous] || "Sin configurar"} →{" "}
          {operationLabels[detail.mode] || detail.mode}
        </p>
      )}
      {detail?.after?.mode && (
        <p>
          Modo de la tarea:{" "}
          {operationLabels[detail.before?.mode] || "Sin configurar"} →{" "}
          {operationLabels[detail.after.mode] || detail.after.mode}
        </p>
      )}
      {result && (
        <>
          {status === "observed" && (
            <p>
              Comprobación sin publicación de cambios.
              {result.complete === false
                ? " La respuesta de la fuente está incompleta."
                : ""}
            </p>
          )}
          {result.historical && (
            <p>
              <strong>Archivo histórico.</strong> Estos datos no corresponden a
              un seguimiento en directo.
            </p>
          )}
          {Object.entries(metricLabels).some(
            ([key]) => typeof result[key] === "number",
          ) && (
            <p>
              {Object.entries(metricLabels)
                .filter(([key]) => typeof result[key] === "number")
                .map(([key, label]) => `${result[key]} ${label}`)
                .join(" · ")}
            </p>
          )}
          {result.requires_review && (
            <p>Hay datos que requieren revisión antes de continuar.</p>
          )}
          {result.more === true && (
            <p>
              Quedan partidos por completar. ONCE continuará con el siguiente
              lote cuando haya cuota disponible.
            </p>
          )}
          {result.matches_checked === 0 && (
            <p>
              No hay partidos disponibles para este lote. Si acabas de activar
              la competición, espera a que termine la actualización del
              calendario.
            </p>
          )}
          {result.coverage && !Array.isArray(result.coverage) && (
            <p>
              {result.coverage.matches} partidos en la fuente ·{" "}
              {result.coverage.missing_results} resultados pendientes.{" "}
              {result.coverage.timezone_declared_by_source === false
                ? "La fuente no declara una zona horaria; sus fechas necesitan confirmación."
                : ""}
            </p>
          )}
          {Array.isArray(result.coverage) && (
            <details>
              <summary>
                Competiciones y temporadas que anuncia la fuente
              </summary>
              <p>
                La disponibilidad publicada todavía debe contrastarse con el
                acceso de tu cuenta.
              </p>
              {result.coverage.map((competition) => (
                <div key={competition.league_id}>
                  <strong>{competition.name}</strong>
                  <p>
                    {competition.seasons
                      .map((season) => season.year)
                      .join(" · ")}
                  </p>
                </div>
              ))}
            </details>
          )}
          {result.prepared_profiles?.length > 0 && (
            <p>
              {result.prepared_profiles.length} tareas preparadas y pausadas
              para comprobar su cobertura.
            </p>
          )}
        </>
      )}
    </>
  );
}
