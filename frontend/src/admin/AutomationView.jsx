import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../api";
import { EmptyState, Field, Icon, Modal } from "../AdminUI";
import { ModuleTabs } from "./ModuleTabs";
import { Pagination } from "../components/ui/Pagination";
import {
  automationModes,
  canRunScope,
  displayValue,
  humanDate,
  operationLabels,
  remainingBudget,
  scopeKinds,
} from "./automation";
import { ProtectedCorrections } from "./ProtectedCorrections";
import { SourceEntitySelect } from "./SourceEntitySelect";
import { AuditInbox } from "./AuditInbox";
import { StandingsAdmin } from "./StandingsAdmin";
import { AccountsView } from "./AccountsView";
import { JobOutcome } from "./JobOutcome";
import { ApiFootballSetup } from "./ApiFootballSetup";
import "./automation.css";

const tabs = [
  { id: "scopes", label: "Automatización" },
  { id: "issues", label: "Requieren atención" },
  { id: "jobs", label: "Actividad" },
  { id: "corrections", label: "Correcciones protegidas" },
  { id: "history", label: "Historial de cambios" },
  { id: "rules", label: "Reglas deportivas" },
];

function ModeSelect({ value, onChange, disabled, label }) {
  return (
    <Field label={label}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {automationModes.map(([mode, title]) => (
          <option key={mode} value={mode}>
            {title}
          </option>
        ))}
      </select>
    </Field>
  );
}

function ScopeForm({ scope, onClose, onSave, busy, error, providers }) {
  const [sportContext, setSportContext] = useState({ phases: [], groups: [] });
  const [contextError, setContextError] = useState("");
  const [form, setForm] = useState(() => ({
    name: scope?.name || "Catálogo colombiano",
    kind: scope?.kind || "catalog",
    provider: scope?.provider || "wikidata",
    mode: scope?.mode || "paused",
    interval_seconds: scope?.interval_seconds || 86400,
    daily_limit: scope?.daily_limit || 80,
    minute_limit: scope?.minute_limit || 3,
    selector: scope?.selector || { collection: "colombia" },
  }));
  const set = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  const selector = (key, value) =>
    set("selector", { ...form.selector, [key]: value });
  useEffect(() => {
    if (form.kind !== "standings" || !form.selector.season_id) return;
    const controller = new AbortController();
    apiRequest(`/public/temporadas/${form.selector.season_id}/context`, {
      signal: controller.signal,
    })
      .then((value) => {
        setSportContext(value);
        setContextError("");
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setContextError(failure.message);
      });
    return () => controller.abort();
  }, [form.kind, form.selector.season_id]);
  return (
    <Modal
      title={scope ? "Configurar automatización" : "Añadir una automatización"}
      subtitle="Define una tarea una vez. ONCE hará las comprobaciones y te mostrará las excepciones."
      onClose={onClose}
      busy={busy}
    >
      <form
        className="once-automation-form"
        onSubmit={(event) => {
          event.preventDefault();
          onSave(form);
        }}
      >
        <Field label="Nombre para reconocer esta tarea">
          <input
            required
            maxLength={120}
            value={form.name}
            onChange={(event) => set("name", event.target.value)}
          />
        </Field>
        <Field label="¿Qué información quieres actualizar?">
          <select
            disabled={Boolean(scope)}
            value={form.kind}
            onChange={(event) => {
              const kind = event.target.value;
              setForm((current) => ({
                ...current,
                kind,
                provider: ["catalog", "history", "media"].includes(kind)
                  ? "wikidata"
                  : kind === "archive"
                    ? "openfootball"
                    : "api-football",
                selector:
                  kind === "catalog"
                    ? { collection: "colombia" }
                    : kind === "discovery"
                      ? { country: "Colombia" }
                      : kind === "archive"
                        ? { season: 2025 }
                        : {},
              }));
            }}
          >
            {Object.entries(scopeKinds)
              .filter(
                ([value]) =>
                  !["details_batch", "standings_batch"].includes(value) ||
                  scope?.kind === value,
              )
              .filter(
                ([value]) =>
                  !providers.length ||
                  providers.some((provider) => provider.kinds.includes(value)),
              )
              .map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
          </select>
        </Field>
        {providers.find((provider) => provider.id === form.provider)
          ?.configured === false && (
          <p className="once-automation-error">
            Esta fuente necesita configuración en el despliegue. Puedes guardar
            la tarea pausada; no tendrá datos hasta conectar la fuente.
          </p>
        )}
        {form.kind === "catalog" ? (
          <p className="once-automation-help">
            Colombia primero: catálogo público de Wikidata, con nombres y
            relaciones verificables. Las coincidencias dudosas pasan a revisión.
          </p>
        ) : (
          <p className="once-automation-help">
            La disponibilidad de una temporada y su nivel de detalle dependen de
            la fuente. Crear la tarea no garantiza cobertura en directo.
          </p>
        )}
        {form.kind === "catalog" && (
          <Field label="Grupo de información">
            <select
              value={form.selector.collection || "colombia"}
              onChange={(event) => selector("collection", event.target.value)}
            >
              <option value="colombia">Fútbol colombiano</option>
              <option value="confederaciones">Confederaciones</option>
            </select>
          </Field>
        )}
        {form.kind === "discovery" && (
          <p>
            Busca las competiciones y temporadas disponibles de Colombia.
            Requiere una clave de API-Football configurada en el despliegue.
          </p>
        )}
        {form.kind === "details_batch" && (
          <p className="once-automation-help">
            Esta tarea completa los partidos de la competición y temporada que
            elegiste al conectar API-Football. Puedes ajustar aquí su
            frecuencia, presupuesto y modo de trabajo.
          </p>
        )}
        {form.kind === "standings_batch" && (
          <p className="once-automation-help">
            Actualiza las tablas publicadas de esta competición y año, separadas
            por edición, fase y grupo. Las correspondencias que no se puedan
            comprobar pasan a revisión.
          </p>
        )}
        {["fixtures", "standings"].includes(form.kind) && (
          <div className="once-automation-fields">
            <Field
              label="Competición en API-Football"
              hint="Número de la competición según el catálogo de la fuente."
            >
              <input
                required
                type="number"
                min="1"
                value={form.selector.league_id || ""}
                onChange={(event) =>
                  selector("league_id", Number(event.target.value))
                }
              />
            </Field>
            <Field label="Año de la fuente">
              <input
                required
                type="number"
                min="1900"
                max="2200"
                value={form.selector.season || ""}
                onChange={(event) =>
                  selector("season", Number(event.target.value))
                }
              />
            </Field>
          </div>
        )}
        {form.kind === "fixtures" && (
          <>
            <Field
              label="Edición dentro del año"
              hint="Opcional. Úsala si el año de la fuente contiene Apertura y Clausura."
            >
              <input
                value={form.selector.edition_name || ""}
                onChange={(event) =>
                  selector("edition_name", event.target.value)
                }
                placeholder="Por ejemplo, Apertura 2026"
              />
            </Field>
            <Field
              label="Nombre de ronda que identifica esta edición"
              hint="Debe coincidir con el comienzo del nombre de ronda publicado por la fuente; no lo deduzcas solo por las fechas."
            >
              <input
                value={form.selector.round_prefix || ""}
                onChange={(event) =>
                  selector("round_prefix", event.target.value)
                }
                placeholder="Por ejemplo, Apertura"
              />
            </Field>
          </>
        )}
        {form.kind === "standings" && (
          <>
            <SourceEntitySelect
              type="season"
              label="Temporada de ONCE"
              value={form.selector.season_id || ""}
              onChange={(value) =>
                set("selector", {
                  ...form.selector,
                  season_id: Number(value),
                  phase_id: null,
                  group_id: null,
                })
              }
            />
            <Field label="Fase de la tabla externa">
              <select
                value={form.selector.phase_id || ""}
                onChange={(event) =>
                  set("selector", {
                    ...form.selector,
                    phase_id: event.target.value
                      ? Number(event.target.value)
                      : null,
                    group_id: null,
                  })
                }
              >
                <option value="">Toda la temporada, si no tiene fases</option>
                {sportContext.phases.map((phase) => (
                  <option key={phase.id} value={phase.id}>
                    {phase.nombre}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Grupo de la tabla externa">
              <select
                value={form.selector.group_id || ""}
                disabled={!form.selector.phase_id}
                onChange={(event) =>
                  selector(
                    "group_id",
                    event.target.value ? Number(event.target.value) : null,
                  )
                }
              >
                <option value="">Toda la fase, si no tiene grupos</option>
                {sportContext.groups
                  .filter((group) => group.fase_id === form.selector.phase_id)
                  .map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.nombre}
                    </option>
                  ))}
              </select>
            </Field>
            <Field
              label="Nombre de la tabla en la fuente"
              hint="Obligatorio cuando la fuente devuelve varias tablas. Copia el nombre exacto de la tabla que corresponde a esta selección."
            >
              <input
                value={form.selector.table_name || ""}
                onChange={(event) => selector("table_name", event.target.value)}
              />
            </Field>
          </>
        )}
        {form.kind === "detail" && (
          <SourceEntitySelect
            type="match"
            label="Partido que quieres completar"
            value={form.selector.match_id || ""}
            onChange={(value) => selector("match_id", Number(value))}
          />
        )}
        {["history", "media"].includes(form.kind) && (
          <>
            <Field label="Tipo de ficha">
              <select
                value={form.selector.entity_type || ""}
                required
                onChange={(event) =>
                  set("selector", { entity_type: event.target.value })
                }
              >
                <option value="">Elige un tipo</option>
                <option value="team">Equipo</option>
                <option value="competition">Competición</option>
                <option value="confederation">Confederación</option>
              </select>
            </Field>
            {form.selector.entity_type && (
              <SourceEntitySelect
                type={form.selector.entity_type}
                label="Ficha conectada con Wikidata"
                value={form.selector.local_id || ""}
                onChange={(value) => selector("local_id", Number(value))}
              />
            )}
            <Field
              label="Código de la ficha en Wikidata"
              hint="La conexión debe corresponder a esta entidad. Ejemplo: Q615."
            >
              <input
                required
                pattern="Q[1-9][0-9]*"
                value={form.selector.qid || ""}
                onChange={(event) =>
                  selector("qid", event.target.value.trim().toUpperCase())
                }
              />
            </Field>
          </>
        )}
        {form.kind === "archive" && (
          <Field
            label="Año del archivo histórico"
            hint="Resultados históricos abiertos; no es una fuente en directo."
          >
            <select
              value={form.selector.season || 2025}
              onChange={(event) =>
                selector("season", Number(event.target.value))
              }
            >
              {[2025, 2024, 2023].map((year) => (
                <option key={year}>{year}</option>
              ))}
            </select>
          </Field>
        )}
        <ModeSelect
          value={form.mode}
          onChange={(value) => set("mode", value)}
          label="Cómo debe trabajar"
          disabled={busy}
        />
        <p className="once-automation-help">
          {automationModes.find(([mode]) => mode === form.mode)?.[2]} La pausa
          general tiene prioridad.
        </p>
        <div className="once-automation-fields">
          <Field
            label="Frecuencia máxima"
            hint="Puede espaciarse si no hay partidos próximos o queda poca cuota."
          >
            <select
              value={form.interval_seconds}
              onChange={(event) =>
                set("interval_seconds", Number(event.target.value))
              }
            >
              {[
                [60, "Cada minuto"],
                [300, "Cada 5 minutos"],
                [900, "Cada 15 minutos"],
                [3600, "Cada hora"],
                [86400, "Cada día"],
                [604800, "Cada semana"],
              ].map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Máximo de consultas al día">
            <input
              type="number"
              required
              min="1"
              max="100000"
              value={form.daily_limit}
              onChange={(event) =>
                set("daily_limit", Number(event.target.value))
              }
            />
          </Field>
          <Field label="Máximo de consultas por minuto">
            <input
              type="number"
              required
              min="1"
              max="1000"
              value={form.minute_limit}
              onChange={(event) =>
                set("minute_limit", Number(event.target.value))
              }
            />
          </Field>
        </div>
        <p className="once-automation-help">
          Cada tarea comparte la cuota de su proveedor. Un intervalo corto no
          aumenta la cuota contratada.
        </p>
        {(error || contextError) && (
          <p role="alert" className="once-automation-error">
            {error || contextError}
          </p>
        )}
        <div className="v-form-footer">
          <button
            type="button"
            className="v-btn v-btn-secondary"
            onClick={onClose}
            disabled={busy}
          >
            Cancelar
          </button>
          <button className="v-btn v-btn-dark" disabled={busy}>
            {busy ? "Guardando…" : "Guardar automatización"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ActivityList({
  view,
  revision,
  scopes,
  mutate,
  busy,
  onError,
  canOperate = false,
}) {
  const [page, setPage] = useState(1);
  const [scopeId, setScopeId] = useState("");
  const [status, setStatus] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [resolving, setResolving] = useState(null);
  const [note, setNote] = useState("");
  const resultKey = `${page}/${view}/${revision}/${scopeId}/${status}`;
  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({
      offset: String((page - 1) * 20),
      limit: "20",
    });
    if (scopeId) query.set("scope_id", scopeId);
    if (status) query.set("status", status);
    apiRequest(`/automation/${view}?${query}`, { signal: controller.signal })
      .then((value) => {
        setResult({ ...value, key: resultKey });
        setError("");
      })
      .catch((failure) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          if (failure.status === 401) onError(failure);
        }
      });
    return () => controller.abort();
  }, [page, view, revision, scopeId, status, onError, resultKey]);
  return (
    <section className="v-panel once-automation-list">
      <div className="once-automation-fields">
        <Field label="Automatización">
          <select
            value={scopeId}
            onChange={(event) => {
              setScopeId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todas las tareas</option>
            {scopes.map((scope) => (
              <option key={scope.id} value={scope.id}>
                {scope.name}
              </option>
            ))}
          </select>
        </Field>
        {view !== "history" && (
          <Field label="Estado de la actividad">
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos los estados</option>
              {(view === "issues"
                ? ["open", "resolved"]
                : ["queued", "running", "succeeded", "failed", "cancelled"]
              ).map((value) => (
                <option key={value} value={value}>
                  {operationLabels[value]}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
      {error ? (
        <p role="alert">{error}</p>
      ) : result?.key !== resultKey ? (
        <p role="status">Consultando actividad…</p>
      ) : !result.items?.length ? (
        <EmptyState
          icon="check"
          title={
            view === "issues"
              ? "Sin incidencias en esta vista"
              : "Todavía no hay actividad"
          }
        >
          {view === "issues"
            ? "Aquí aparecerán los casos que necesiten tu criterio."
            : "Cada comprobación quedará registrada al ejecutar una tarea."}
        </EmptyState>
      ) : (
        <div className="once-automation-records">
          {result.items.map((item) => (
            <article key={item.id}>
              <div>
                <strong>
                  {item.title ||
                    item.message ||
                    item.summary ||
                    scopes.find((scope) => scope.id === item.scope_id)?.name ||
                    scopeKinds[item.kind] ||
                    "Cambio registrado"}
                </strong>
                <span className="once-automation-pill">
                  {operationLabels[item.status] ||
                    item.status ||
                    operationLabels[item.action] ||
                    item.action ||
                    "Registrado"}
                </span>
              </div>
              {item.message && item.title && <p>{item.message}</p>}
              {(item.error || item.last_error) && (
                <p>{displayValue(item.error || item.last_error)}</p>
              )}
              <JobOutcome
                result={item.result}
                detail={item.detail}
                status={item.status}
              />
              {item.field && (
                <p>
                  {item.field}: {displayValue(item.old_value)} →{" "}
                  {displayValue(item.new_value)}
                </p>
              )}
              <small>
                {humanDate(
                  item.created_at || item.started_at || item.updated_at,
                )}
                {item.actor ? ` · ${item.actor}` : ""}
                {item.attempts ? ` · Intento ${item.attempts}` : ""}
              </small>
              {view === "issues" &&
                item.status !== "resolved" &&
                canOperate && (
                  <button
                    className="v-text-btn"
                    onClick={() => {
                      setResolving(item);
                      setNote("");
                    }}
                  >
                    Marcar como revisado
                  </button>
                )}
            </article>
          ))}
        </div>
      )}
      {result && (
        <Pagination
          page={page}
          pageSize={20}
          total={result.total}
          onChange={setPage}
        />
      )}
      {resolving && (
        <Modal
          title="Registrar revisión"
          subtitle="Explica qué comprobaste o corregiste. Esta acción cierra la incidencia y conserva su historial."
          onClose={() => setResolving(null)}
          busy={busy}
        >
          <form
            className="once-automation-form"
            onSubmit={async (event) => {
              event.preventDefault();
              if (
                await mutate(
                  `/automation/issues/${resolving.id}/resolve`,
                  { method: "POST", body: { note } },
                  "Revisión registrada.",
                )
              )
                setResolving(null);
            }}
          >
            <Field label="Motivo de la resolución">
              <textarea
                required
                minLength={3}
                maxLength={1000}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </Field>
            <button className="v-btn v-btn-dark" disabled={busy}>
              Guardar revisión
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}

export function AutomationView({ onError, active = true, permissions = [] }) {
  const canOperate = permissions.includes("operate");
  const canConfigure = permissions.includes("manage_sources");
  const canCorrect = permissions.includes("correct");
  const [view, setView] = useState("scopes");
  const [overview, setOverview] = useState(null);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(null);
  const [providers, setProviders] = useState([]);
  const [issueType, setIssueType] = useState("data");
  const [activityType, setActivityType] = useState("jobs");
  const [correction, setCorrection] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest("/automation/providers", { signal: controller.signal })
      .then((value) => setProviders(value.items || []))
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message);
      });
    return () => controller.abort();
  }, []);
  const correct = (record) => {
    setCorrection(record);
    setView("corrections");
  };
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    apiRequest("/automation/overview", { signal: controller.signal })
      .then(setOverview)
      .catch((failure) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          if (failure.status === 401) onError(failure);
        }
      });
    const timer = setTimeout(() => {
      if (!document.hidden) refresh();
    }, 15000);
    const visible = () => {
      if (!document.hidden) refresh();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [revision, active, onError, refresh]);
  const mutate = async (path, options, text) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiRequest(path, options);
      setMessage(text);
      refresh();
      return true;
    } catch (failure) {
      setError(failure.message);
      if (failure.status === 401) onError(failure);
      return false;
    } finally {
      setBusy(false);
    }
  };
  const scopes = overview?.scopes || [];
  const mode = overview?.global?.mode || "paused";
  return (
    <section aria-label="Automatización de datos" className="once-automation">
      <div className="once-module-intro">
        <span className="v-eyebrow">ONCE TRABAJA. TÚ SUPERVISAS.</span>
        <h2>El archivo, en movimiento.</h2>
        <p>
          Configura tus fuentes y revisa solo lo que necesita atención. Cada
          cambio conserva su origen.
        </p>
      </div>
      <ModuleTabs
        items={[
          ...tabs,
          ...(permissions.includes("manage_accounts")
            ? [{ id: "accounts", label: "Personas y permisos" }]
            : []),
        ]}
        value={view}
        onChange={setView}
        label="Control de automatización"
        id="automation-tab"
        panelId="automation-panel"
      />
      {error && !editing && (
        <p className="once-automation-error" role="alert">
          {error}{" "}
          <button className="v-text-btn" onClick={refresh}>
            Volver a consultar
          </button>
        </p>
      )}
      {message && (
        <p className="once-automation-success" role="status">
          {message}
        </p>
      )}
      <div
        role="tabpanel"
        id="automation-panel"
        aria-labelledby={`automation-tab-${view}`}
      >
        {view === "scopes" && (
          <>
            <ApiFootballSetup
              canConfigure={canConfigure}
              canOperate={canOperate}
              active={active}
              globalMode={mode}
              onChanged={refresh}
              onError={onError}
            />
            <div className="once-automation-providers">
              {providers
                .filter((provider) => provider.id !== "api-football")
                .map((provider) => (
                  <article key={provider.id}>
                    <strong>{provider.name}</strong>
                    <span className="once-automation-pill">
                      {provider.configured
                        ? "Disponible"
                        : "Pendiente de conectar"}
                    </span>
                    <p>
                      {provider.configured
                        ? provider.description
                        : "Conecta una cuenta de esta fuente en la configuración del despliegue para comprobar su cobertura. El catálogo abierto puede seguir funcionando mientras tanto."}
                    </p>
                  </article>
                ))}
            </div>
            <div className="once-automation-master v-panel">
              <div>
                <span className="v-eyebrow">CONTROL GENERAL</span>
                <h3>
                  {
                    operationLabels[
                      mode === "paused" && overview?.jobs?.running
                        ? "pausing"
                        : overview?.global?.status || mode
                    ]
                  }
                </h3>
                <p>{automationModes.find(([value]) => value === mode)?.[2]}</p>
                <p className="once-automation-help">
                  La pausa se conserva al reiniciar. La información ya guardada
                  seguirá disponible.
                </p>
              </div>
              <ModeSelect
                label="Estado general de la automatización"
                value={mode}
                disabled={busy || !overview || !canOperate}
                onChange={(next) =>
                  mutate(
                    "/automation/global",
                    { method: "PUT", body: { mode: next } },
                    next === "paused"
                      ? "Pausa solicitada. Ninguna respuesta anterior puede publicar cambios tras confirmarse la pausa."
                      : "Control general actualizado. Cada tarea conserva su propio modo.",
                  )
                }
              />
            </div>
            {overview && (
              <div className="once-automation-metrics">
                <div>
                  <Icon name="refresh" />
                  <strong>
                    {overview.worker?.healthy
                      ? "Motor disponible"
                      : "Motor sin señal reciente"}
                  </strong>
                  <small>
                    Última señal: {humanDate(overview.worker?.last_seen_at)}
                  </small>
                </div>
                <div>
                  <Icon name="clock" />
                  <strong>
                    {overview.jobs?.queued || 0} en espera ·{" "}
                    {overview.jobs?.running || 0} en curso
                  </strong>
                  <small>
                    Las tareas continúan mientras Docker esté encendido.
                  </small>
                </div>
                {(overview.budget || []).map((budget) => (
                  <div key={budget.provider}>
                    <Icon name="globe" />
                    <strong>
                      {budget.provider === "wikidata"
                        ? "Wikidata"
                        : budget.provider === "api-football"
                          ? "API-Football"
                          : budget.provider}
                    </strong>
                    <small>
                      Hoy: {remainingBudget(budget.day_used, budget.day_limit)}
                    </small>
                    <small>
                      Este minuto:{" "}
                      {remainingBudget(budget.minute_used, budget.minute_limit)}
                    </small>
                  </div>
                ))}
              </div>
            )}
            <div className="once-section-title">
              <div>
                <h3>Tus automatizaciones</h3>
                <p>
                  El modo general limita todas las tareas. Una tarea pausada
                  siempre permanece detenida.
                </p>
              </div>
              <button
                className="v-btn v-btn-dark"
                disabled={!canConfigure}
                onClick={() => {
                  setEditing({});
                  setError("");
                }}
              >
                <Icon name="plus" />
                Añadir automatización
              </button>
            </div>
            {!overview ? (
              <p role="status">Consultando el motor…</p>
            ) : !scopes.length ? (
              <div className="v-panel">
                <EmptyState
                  title="Empieza por el catálogo colombiano"
                  icon="globe"
                >
                  Añade la primera tarea con datos públicos. Puedes comprobar
                  los resultados antes de permitir cambios automáticos.
                </EmptyState>
              </div>
            ) : (
              <div className="once-automation-scopes">
                {scopes.map((scope) => (
                  <article className="v-panel" key={scope.id}>
                    <div className="once-automation-scope-title">
                      <span className="v-eyebrow">
                        {scopeKinds[scope.kind] || "Actualización de datos"}
                      </span>
                      <span className="once-automation-pill">
                        {operationLabels[scope.status] ||
                          operationLabels[scope.mode] ||
                          "En espera"}
                      </span>
                    </div>
                    <h3>{scope.name}</h3>
                    <dl>
                      <div>
                        <dt>Última comprobación</dt>
                        <dd>{humanDate(scope.last_checked_at)}</dd>
                      </div>
                      <div>
                        <dt>Último cambio</dt>
                        <dd>{humanDate(scope.last_changed_at)}</dd>
                      </div>
                      <div>
                        <dt>Próxima comprobación</dt>
                        <dd>
                          {canRunScope(mode, scope.mode)
                            ? humanDate(scope.next_run_at)
                            : "Al reanudar"}
                        </dd>
                      </div>
                    </dl>
                    {scope.open_issues > 0 && (
                      <button
                        className="v-text-btn"
                        onClick={() => {
                          setIssueType("operations");
                          setView("issues");
                        }}
                      >
                        {scope.open_issues} casos requieren atención →
                      </button>
                    )}
                    <ModeSelect
                      label={`Modo de ${scope.name}`}
                      value={scope.mode}
                      disabled={busy || !canOperate}
                      onChange={(next) =>
                        mutate(
                          `/automation/scopes/${scope.id}`,
                          { method: "PATCH", body: { mode: next } },
                          "Modo de la tarea actualizado.",
                        )
                      }
                    />
                    <div className="once-automation-actions">
                      <button
                        className="v-btn v-btn-secondary"
                        disabled={
                          busy || !canOperate || !canRunScope(mode, scope.mode)
                        }
                        onClick={() =>
                          mutate(
                            `/automation/scopes/${scope.id}/run`,
                            { method: "POST" },
                            "Comprobación añadida a la cola. Puedes seguir trabajando.",
                          )
                        }
                      >
                        Comprobar ahora
                      </button>
                      <button
                        className="v-text-btn"
                        disabled={busy || !canConfigure}
                        onClick={() => {
                          setEditing(scope);
                          setError("");
                        }}
                      >
                        Configurar
                      </button>
                    </div>
                    {!canRunScope(mode, scope.mode) && (
                      <small>
                        Reanuda el control general y esta tarea para consultar
                        la fuente.
                      </small>
                    )}
                  </article>
                ))}
              </div>
            )}
          </>
        )}
        {view === "issues" && (
          <div
            className="v-segments"
            role="group"
            aria-label="Tipo de incidencia"
          >
            <button
              aria-pressed={issueType === "data"}
              onClick={() => setIssueType("data")}
            >
              Diferencias de datos
            </button>
            <button
              aria-pressed={issueType === "operations"}
              onClick={() => setIssueType("operations")}
            >
              Problemas de actualización
            </button>
          </div>
        )}
        {view === "jobs" && (
          <div
            className="v-segments"
            role="group"
            aria-label="Tipo de actividad"
          >
            <button
              aria-pressed={activityType === "jobs"}
              onClick={() => setActivityType("jobs")}
            >
              Comprobaciones
            </button>
            <button
              aria-pressed={activityType === "history"}
              onClick={() => setActivityType("history")}
            >
              Cambios de configuración
            </button>
          </div>
        )}
        {(view === "jobs" ||
          (view === "issues" && issueType === "operations")) && (
          <ActivityList
            key={`${view}-${activityType}`}
            view={view === "jobs" ? activityType : "issues"}
            revision={revision}
            scopes={scopes}
            mutate={mutate}
            busy={busy}
            onError={onError}
            canOperate={canOperate}
          />
        )}
        {(view === "history" ||
          (view === "issues" && issueType === "data")) && (
          <AuditInbox
            key={view}
            issues={view === "issues"}
            onCorrect={correct}
            onError={onError}
            canCorrect={canCorrect}
          />
        )}
        {view === "corrections" && (
          <ProtectedCorrections
            key={`${correction?.type || "team"}-${correction?.id || ""}`}
            initial={correction}
            onError={onError}
            canCorrect={canCorrect}
          />
        )}
        {view === "rules" && (
          <StandingsAdmin onError={onError} canCorrect={canCorrect} />
        )}
        {view === "accounts" && permissions.includes("manage_accounts") && (
          <AccountsView onError={onError} />
        )}
      </div>
      {editing && (
        <ScopeForm
          scope={editing.id ? editing : null}
          onClose={() => setEditing(null)}
          busy={busy}
          error={error}
          providers={providers}
          onSave={async (body) => {
            if (
              await mutate(
                editing.id
                  ? `/automation/scopes/${editing.id}`
                  : "/automation/scopes",
                { method: editing.id ? "PATCH" : "POST", body },
                "Automatización guardada.",
              )
            )
              setEditing(null);
          }}
        />
      )}
    </section>
  );
}
