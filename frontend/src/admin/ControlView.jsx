import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Field, EmptyState, Icon } from "../AdminUI";
import { ModuleTabs } from "./ModuleTabs";

const views = [
  { id: "issues", label: "Por revisar" },
  { id: "imports", label: "Importaciones" },
  { id: "links", label: "Conexiones" },
  { id: "observations", label: "Datos consultados" },
  { id: "media", label: "Imágenes y licencias" },
];
const labels = {
  confederations: "Confederaciones",
  competitions: "Competiciones",
  teams: "Equipos",
  seasons: "Temporadas",
  stages: "Fases",
  venues: "Estadios",
  players: "Jugadores",
  rosters: "Vínculos de plantillas",
  enrollments: "Matrículas",
  matches: "Partidos",
  statistics: "Estadísticas",
  events: "Eventos",
  lineups: "Alineaciones",
  imports: "Importaciones",
  links: "Conexiones externas",
  observations: "Observaciones guardadas",
  media: "Imágenes",
};
const statuses = {
  recorded: "Registrado",
  review: "Por revisar",
  orphaned: "Referencia sin destino",
  prepared: "Consultado",
  applied: "Aplicado",
};
const metadataLabels = {
  external_id: "Identificador en la fuente",
  collection: "Colección",
  observed_rows: "Registros consultados",
  created: "Creados",
  linked: "Conectados",
  reused: "Reutilizados",
  skipped: "Omitidos",
  applied_at: "Última aplicación",
  license: "Licencia",
  author: "Autoría",
  credit: "Créditos",
  tipo: "Uso de la imagen",
  snapshot_type: "Tipo de consulta",
  observation_kind: "Tipo de consulta",
  import_batch_id: "Lote de consulta",
  license_url: "Condiciones de la licencia",
  image_url: "Archivo de imagen",
  verified_at: "Verificación registrada",
  local_id: "Registro local",
  status: "Estado",
};
const emptyFilters = { provider: "", entity_type: "", search: "" };
const formatDate = (value) =>
  value ? new Date(value).toLocaleString("es") : "No registrada";
const safeSource = (value) => {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
};

export function ControlView({ onError, onNavigate }) {
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState("");
  const [revision, setRevision] = useState(0);
  const [view, setView] = useState("issues");
  const [issue, setIssue] = useState("");
  const [filters, setFilters] = useState(emptyFilters);
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [listError, setListError] = useState("");
  const [pending, setPending] = useState(false);
  const [recordRevision, setRecordRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest("/control/summary", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setSummary(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setSummaryError(error.message);
          if (error.status === 401) onError(error);
        }
      });
    return () => controller.abort();
  }, [revision, onError]);
  useEffect(() => {
    if (view === "issues" && !issue) return;
    const controller = new AbortController();
    const query = new URLSearchParams({ page: String(page), page_size: "20" });
    if (view === "issues") query.set("code", issue);
    else {
      query.set("kind", view);
      for (const [key, value] of Object.entries(filters))
        if (value && !(view === "imports" && key === "entity_type"))
          query.set(key, value);
    }
    const timer = setTimeout(
      () => {
        apiRequest(
          `/control/${view === "issues" ? "issues" : "records"}?${query}`,
          { signal: controller.signal },
        )
          .then((value) => {
            if (!controller.signal.aborted) {
              setResult(value);
              setPending(false);
            }
          })
          .catch((error) => {
            if (!controller.signal.aborted) {
              setListError(error.message);
              setPending(false);
              if (error.status === 401) onError(error);
            }
          });
      },
      filters.search ? 250 : 0,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [view, issue, filters, page, revision, recordRevision, onError]);
  const invalidate = () => {
    setResult(null);
    setListError("");
    setPending(true);
    setRecordRevision((value) => value + 1);
  };
  const changeView = (next) => {
    setView(next);
    setIssue("");
    setPage(1);
    setFilters(emptyFilters);
    invalidate();
  };
  const changeFilter = (field, value) => {
    setFilters((current) => ({ ...current, [field]: value }));
    setPage(1);
    invalidate();
  };
  const currentCheck = summary?.checks.find((check) => check.code === issue);
  const refresh = () => {
    setSummaryError("");
    invalidate();
    setRevision((value) => value + 1);
  };
  return (
    <section className="v-panel once-control" aria-labelledby="control-title">
      <div className="v-panel-head">
        <div>
          <span className="v-eyebrow">REVISIÓN DE LA INFORMACIÓN GUARDADA</span>
          <h2 id="control-title">Control de datos</h2>
          <p>
            Comprueba qué falta, de dónde viene cada registro y cuándo se
            consultó su fuente.
          </p>
        </div>
        <button className="v-text-btn" onClick={refresh}>
          <Icon name="refresh" />
          Actualizar revisión
        </button>
      </div>
      <p className="once-scope-note">
        Esta consulta no modifica datos ni contacta con fuentes externas. Las
        observaciones guardadas no son un historial completo de cambios.
      </p>
      {summaryError ? (
        <p role="alert">{summaryError}</p>
      ) : !summary ? (
        <p role="status">Revisando la información disponible…</p>
      ) : (
        <>
          <details className="once-control-scope">
            <summary>Qué incluye esta revisión</summary>
            <p>Consulta realizada: {formatDate(summary.checked_at)}</p>
            <ul>
              {summary.scope_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
            <dl className="once-control-inventory">
              {Object.entries(summary.counts).map(([key, value]) => (
                <div key={key}>
                  <dt>{labels[key] || key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </details>
          <ModuleTabs
            items={views}
            value={view}
            onChange={changeView}
            label="Tipo de revisión"
            id="control-tab"
            panelId="control-panel"
          />
          <div
            role="tabpanel"
            id="control-panel"
            aria-labelledby={`control-tab-${view}`}
          >
            {view === "issues" ? (
              <>
                <p>
                  Una señal por revisar no siempre es un error: algunas
                  relaciones son opcionales.
                </p>
                <div className="once-check-grid">
                  {summary.checks
                    .filter((check) => check.count > 0)
                    .map((check) => (
                      <button
                        key={check.code}
                        disabled={!check.count}
                        aria-pressed={issue === check.code}
                        onClick={() => {
                          setIssue(check.code);
                          setPage(1);
                          invalidate();
                        }}
                      >
                        <strong>{check.count}</strong>
                        <span>{check.label}</span>
                        <small>{check.description}</small>
                      </button>
                    ))}
                </div>
                {!summary.checks.some((check) => check.count > 0) && (
                  <EmptyState title="Sin señales en estas comprobaciones">
                    El alcance de esta revisión está detallado arriba; no
                    comprueba todos los posibles problemas del catálogo.
                  </EmptyState>
                )}
                <details className="once-control-scope">
                  <summary>
                    Comprobaciones sin hallazgos (
                    {summary.checks.filter((check) => !check.count).length})
                  </summary>
                  <ul>
                    {summary.checks
                      .filter((check) => !check.count)
                      .map((check) => (
                        <li key={check.code}>{check.label}</li>
                      ))}
                  </ul>
                </details>
                {currentCheck && (
                  <div className="once-review-context">
                    <h3>{currentCheck.label}</h3>
                    <p>{currentCheck.description}</p>
                    {currentCheck.module !== "control" && (
                      <button
                        className="v-text-btn"
                        onClick={() => onNavigate(currentCheck.module)}
                      >
                        Ir a{" "}
                        {labels[currentCheck.module]?.toLowerCase() ||
                          "su sección"}{" "}
                        →
                      </button>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="once-filter-grid">
                <Field label="Buscar en esta revisión">
                  <input
                    type="search"
                    value={filters.search}
                    onChange={(event) =>
                      changeFilter("search", event.target.value)
                    }
                    placeholder="Nombre o referencia de la fuente"
                  />
                </Field>
                <Field label="Fuente de los datos">
                  <select
                    value={filters.provider}
                    onChange={(event) =>
                      changeFilter("provider", event.target.value)
                    }
                  >
                    <option value="">Todas las fuentes</option>
                    {summary.providers.map((provider) => (
                      <option key={provider} value={provider}>
                        {provider}
                      </option>
                    ))}
                  </select>
                </Field>
                {view !== "imports" && (
                  <Field label="Tipo de registro">
                    <select
                      value={filters.entity_type}
                      onChange={(event) =>
                        changeFilter("entity_type", event.target.value)
                      }
                    >
                      <option value="">Todos los tipos</option>
                      {summary.entity_types.map((type) => (
                        <option key={type.value} value={type.value}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                )}
                <button
                  className="v-text-btn"
                  onClick={() => {
                    setFilters(emptyFilters);
                    setPage(1);
                    invalidate();
                  }}
                >
                  Limpiar filtros de revisión
                </button>
              </div>
            )}
            {(view !== "issues" || issue) && (
              <>
                {listError ? (
                  <div role="alert">
                    <p>{listError}</p>
                    <button className="v-text-btn" onClick={refresh}>
                      Reintentar revisión
                    </button>
                  </div>
                ) : pending ? (
                  <p role="status">Consultando registros…</p>
                ) : (
                  result && (
                    <>
                      <p role="status">
                        {result.total} registros · Página {result.page} de{" "}
                        {Math.max(
                          1,
                          Math.ceil(result.total / result.page_size),
                        )}
                      </p>
                      {!result.items.length && (
                        <EmptyState title="Sin registros en esta vista">
                          Prueba otros filtros o consulta otra sección.
                        </EmptyState>
                      )}
                      <div className="once-control-records">
                        {result.items.map((record) => (
                          <article
                            className="once-control-record"
                            key={`${record.kind}-${record.id}`}
                          >
                            <div>
                              <h3>{record.title || record.entity_name}</h3>
                              <span className="once-record-status">
                                {statuses[record.status] || record.status}
                              </span>
                            </div>
                            <p>{record.detail}</p>
                            <dl className="once-detail-fields">
                              <div>
                                <dt>Fuente</dt>
                                <dd>{record.provider || "No registrada"}</dd>
                              </div>
                              <div>
                                <dt>
                                  {["observations", "imports"].includes(
                                    record.kind,
                                  )
                                    ? "Consulta a la fuente"
                                    : "Verificación registrada"}
                                </dt>
                                <dd>{formatDate(record.recorded_at)}</dd>
                              </div>
                            </dl>
                            {record.metadata && (
                              <details>
                                <summary>Ver referencias y detalles</summary>
                                <dl className="once-detail-fields">
                                  {Object.entries(record.metadata)
                                    .filter(
                                      ([, value]) =>
                                        value != null &&
                                        typeof value !== "object",
                                    )
                                    .map(([key, value]) => (
                                      <div key={key}>
                                        <dt>{metadataLabels[key] || key}</dt>
                                        <dd>
                                          {key.endsWith("_at")
                                            ? formatDate(value)
                                            : String(value)}
                                        </dd>
                                      </div>
                                    ))}
                                </dl>
                              </details>
                            )}
                            {safeSource(record.source_url) && (
                              <a
                                className="v-text-btn"
                                href={safeSource(record.source_url)}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                Consultar fuente ↗
                              </a>
                            )}
                          </article>
                        ))}
                      </div>
                      <div
                        className="once-pagination"
                        aria-label="Paginación de revisión"
                      >
                        <button
                          className="v-btn"
                          disabled={page <= 1}
                          onClick={() => {
                            setPage((value) => value - 1);
                            invalidate();
                          }}
                        >
                          Anterior
                        </button>
                        <button
                          className="v-btn"
                          disabled={page * result.page_size >= result.total}
                          onClick={() => {
                            setPage((value) => value + 1);
                            invalidate();
                          }}
                        >
                          Siguiente
                        </button>
                      </div>
                    </>
                  )
                )}
              </>
            )}
          </div>
        </>
      )}
    </section>
  );
}
