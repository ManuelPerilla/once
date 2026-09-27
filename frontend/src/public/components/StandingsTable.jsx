import { useEffect, useState } from "react";
import { apiRequest } from "../../api";
import { Crest } from "../../components/ui/Crest";
import { defaultStandingSelection } from "../standingSelection";

const pendingLabels = {
  missing_rules: "Esta selección todavía no tiene reglamento registrado.",
  unverified_rules: "El reglamento está pendiente de verificación.",
  pending: "La tabla está pendiente de cálculo o de datos suficientes.",
};

export function StandingsTable({ competition, season }) {
  const [context, setContext] = useState({ phases: [], groups: [] });
  const [selections, setSelections] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const seasonId = season?.id;
  const contextReady = context.seasonId === seasonId;
  const currentContext = contextReady ? context : { phases: [], groups: [] };
  const selection =
    selections[seasonId] || defaultStandingSelection(currentContext);
  const { phase, group, source } = selection;
  const select = (next) =>
    setSelections((previous) => ({
      ...previous,
      [seasonId]: { ...selection, ...next },
    }));
  const query = new URLSearchParams({
    ...(phase ? { phase_id: phase } : {}),
    ...(group ? { group_id: group } : {}),
  }).toString();
  const key = `${seasonId}/${query}/${attempt}`;
  useEffect(() => {
    if (!seasonId) return;
    const controller = new AbortController();
    apiRequest(`/public/temporadas/${seasonId}/context`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) setContext({ ...data, seasonId });
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message);
      });
    return () => controller.abort();
  }, [seasonId, attempt]);
  useEffect(() => {
    if (!seasonId || !contextReady) return;
    const controller = new AbortController();
    apiRequest(`/public/temporadas/${seasonId}/clasificacion?${query}`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        setResult({ ...data, key });
        setError("");
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message);
      });
    return () => controller.abort();
  }, [seasonId, query, key, contextReady]);
  const currentResult = result?.key === key ? result : null;
  const snapshot = currentResult?.[source];
  const rows = result?.key === key ? snapshot?.rows || [] : [];
  return (
    <section className="p-standings-section">
      <div className="p-section-head">
        <div>
          <span className="p-kicker">CLASIFICACIÓN</span>
          <h2>La clasificación de esta edición.</h2>
        </div>
        <span>{season?.nombre || competition.nombre}</span>
      </div>
      {!seasonId ? (
        <p className="once-detail-note">
          Selecciona una temporada. Las tablas de distintas ediciones permanecen
          separadas.
        </p>
      ) : (
        <>
          <div className="once-filter-bar">
            <label className="once-select">
              <span>Fase de la tabla</span>
              <select
                value={phase}
                disabled={!contextReady}
                onChange={(event) => {
                  select({ phase: event.target.value, group: "" });
                }}
              >
                <option value="">Toda la temporada</option>
                {currentContext.phases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label className="once-select">
              <span>Grupo de la tabla</span>
              <select
                disabled={!contextReady || !phase}
                value={group}
                onChange={(event) => select({ group: event.target.value })}
              >
                <option value="">Toda la fase</option>
                {currentContext.groups
                  .filter((item) => String(item.fase_id) === phase)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.nombre}
                    </option>
                  ))}
              </select>
            </label>
            <div
              className="once-tabs"
              role="group"
              aria-label="Origen de la clasificación"
            >
              <button
                aria-pressed={source === "calculated"}
                disabled={!contextReady}
                onClick={() => select({ source: "calculated" })}
              >
                Cálculo ONCE
              </button>
              <button
                aria-pressed={source === "official"}
                disabled={!contextReady}
                onClick={() => select({ source: "official" })}
              >
                Tabla de la fuente
              </button>
            </div>
          </div>
          <p className="once-detail-note">
            {source === "calculated"
              ? "Calculada con los resultados registrados y el reglamento verificado de esta selección."
              : "Conserva la clasificación comunicada por la fuente. Se muestra por separado del cálculo de ONCE."}
          </p>
          {currentResult?.rule && source === "calculated" && (
            <p className="once-detail-note">
              {currentResult.rule.name} · Versión {currentResult.rule.version} ·{" "}
              <a
                href={currentResult.rule.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Consultar reglamento
              </a>
            </p>
          )}
          {snapshot && (
            <p className="once-detail-note">
              Última actualización:{" "}
              {new Date(
                snapshot.updated_at || snapshot.fetched_at,
              ).toLocaleString("es-CO")}
              {snapshot.source ? ` · ${snapshot.source}` : ""}
            </p>
          )}
          {error ? (
            <p role="alert">
              {error}{" "}
              <button
                className="once-text-link"
                onClick={() => setAttempt((value) => value + 1)}
              >
                Volver a intentar
              </button>
            </p>
          ) : !contextReady || result?.key !== key ? (
            <p role="status">Consultando la clasificación…</p>
          ) : !rows.length ? (
            <p className="once-detail-note">
              {source === "calculated"
                ? pendingLabels[result.status] ||
                  "No hay participantes o resultados suficientes para esta tabla."
                : "No se ha recibido una tabla de la fuente para esta selección."}
            </p>
          ) : (
            <div
              className="p-standings"
              role="table"
              aria-label="Tabla de posiciones"
            >
              <div className="p-standing-row p-standing-head" role="row">
                <span>#</span>
                <span>Equipo</span>
                <span>PJ</span>
                <span>G</span>
                <span>E</span>
                <span>P</span>
                <span>DG</span>
                <span>PTS</span>
              </div>
              {rows.map((row) => {
                const goalDifference =
                  row.goal_difference ?? row.goals_for - row.goals_against;
                return (
                  <div
                    className="p-standing-row"
                    role="row"
                    key={row.team?.id || row.team_id}
                  >
                    <strong>{row.rank}</strong>
                    <span className="p-standing-team">
                      <Crest
                        small
                        src={row.team?.logo}
                        name={row.team?.nombre}
                      />
                      <b>{row.team?.nombre || "Equipo sin identificar"}</b>
                    </span>
                    <span>{row.played}</span>
                    <span>{row.won}</span>
                    <span>{row.drawn}</span>
                    <span>{row.lost}</span>
                    <span>
                      {goalDifference > 0 ? "+" : ""}
                      {goalDifference}
                    </span>
                    <strong>{row.points}</strong>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}
