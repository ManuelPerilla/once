import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { EmptyState, Field } from "../AdminUI";

const emptyFilters = { search: "", equipo_id: "", estado: "" };
const dateLabel = (value) =>
  value ? value.split("-").reverse().join("/") : "No registrada";

export function RostersView({ teams, onError }) {
  const [filters, setFilters] = useState(emptyFilters);
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [response, setResponse] = useState(null);
  const query = new URLSearchParams({ page: String(page), page_size: "20" });
  for (const [key, value] of Object.entries(filters))
    if (value) query.set(key, value);
  const url = `/plantillas/?${query}`;
  const requestKey = `${url}:${revision}`;
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      apiRequest(url, { signal: controller.signal })
        .then((data) => {
          if (!controller.signal.aborted)
            setResponse({ key: requestKey, data });
        })
        .catch((error) => {
          if (!controller.signal.aborted) {
            setResponse({ key: requestKey, error: error.message });
            if (error.status === 401) onError(error);
          }
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [url, requestKey, onError]);
  const result = response?.key === requestKey ? response : null;
  const update = (key, value) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  };
  return (
    <section
      className="v-panel"
      aria-label="Pertenencia de jugadores a equipos"
    >
      <p className="once-scope-note">
        Consulta los vínculos guardados entre jugadores y equipos. “Sin cierre
        registrado” significa que no hay una fecha final; no confirma que el
        jugador siga hoy en el club. Una alineación pertenece a un partido
        concreto.
      </p>
      <div className="once-filter-grid">
        <Field label="Buscar jugador o equipo">
          <input
            type="search"
            value={filters.search}
            onChange={(event) => update("search", event.target.value)}
          />
        </Field>
        <Field label="Equipo de la plantilla">
          <select
            value={filters.equipo_id}
            onChange={(event) => update("equipo_id", event.target.value)}
          >
            <option value="">Todos los equipos</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.nombre}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Estado del vínculo">
          <select
            value={filters.estado}
            onChange={(event) => update("estado", event.target.value)}
          >
            <option value="">Todos los vínculos</option>
            <option value="active">Sin cierre registrado</option>
            <option value="closed">Con cierre registrado</option>
          </select>
        </Field>
      </div>
      <div className="v-catalog-toolbar">
        <button
          className="v-text-btn"
          onClick={() => {
            setFilters(emptyFilters);
            setPage(1);
          }}
        >
          Limpiar filtros de plantillas
        </button>
        <button
          className="v-text-btn"
          onClick={() => setRevision((value) => value + 1)}
        >
          Actualizar plantillas
        </button>
      </div>
      {!result ? (
        <p role="status">Consultando plantillas…</p>
      ) : result.error ? (
        <p role="alert">{result.error}</p>
      ) : (
        <>
          <p role="status">
            {result.data.total} vínculos · Página {page} de{" "}
            {Math.max(1, Math.ceil(result.data.total / result.data.page_size))}
          </p>
          {!result.data.items.length && (
            <EmptyState title="Sin vínculos en esta vista">
              Estas relaciones aparecen cuando una fuente conectada aporta
              información de jugadores y equipos. Todavía no hay un editor
              manual de plantillas.
            </EmptyState>
          )}
          <div className="once-control-records">
            {result.data.items.map((row) => (
              <article key={row.id} className="once-control-record">
                <h3>{row.jugador_nombre}</h3>
                <p>{row.equipo_nombre}</p>
                <dl className="once-detail-fields">
                  <div>
                    <dt>Inicio</dt>
                    <dd>{dateLabel(row.fecha_inicio)}</dd>
                  </div>
                  <div>
                    <dt>Fin</dt>
                    <dd>{dateLabel(row.fecha_fin)}</dd>
                  </div>
                  <div>
                    <dt>Dorsal</dt>
                    <dd>{row.dorsal ?? "No registrado"}</dd>
                  </div>
                  <div>
                    <dt>Estado</dt>
                    <dd>
                      {row.fecha_fin
                        ? "Con cierre registrado"
                        : "Sin cierre registrado"}
                    </dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
          <div className="once-pagination">
            <button
              className="v-btn"
              disabled={page <= 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Anterior
            </button>
            <button
              className="v-btn"
              disabled={page * result.data.page_size >= result.data.total}
              onClick={() => setPage((value) => value + 1)}
            >
              Siguiente
            </button>
          </div>
        </>
      )}
    </section>
  );
}
