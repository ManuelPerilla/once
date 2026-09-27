import { useEffect, useState } from "react";
import { EmptyState, Field, Icon } from "../../AdminUI";
import { apiCollection } from "../../api";
import { ContextForm } from "./ContextForm";
import {
  changeContextFilter,
  contextModuleNames,
  contextOptions,
  contextRelations,
  emptyContextFilters,
  filterContext,
} from "./selectors";
import "./context.css";

const phaseTypes = {
  jornada: "Jornada",
  grupo: "Grupo",
  eliminatoria: "Eliminatoria",
  final: "Final",
  otra: "Otra fase",
};
const dateLabel = (value) =>
  value ? value.split("-").reverse().join("/") : "Sin fecha";

function ContextRecord({ module, record, relations }) {
  const season = relations.seasons.get(String(record.temporada_id));
  const competition = relations.competitions.get(
    String(
      module === "temporadas" ? record.competicion_id : season?.competicion_id,
    ),
  );
  let details;
  if (module === "temporadas")
    details = [
      ["Competición", competition?.nombre || "Competición sin referencia"],
      [
        "Periodo",
        `${dateLabel(record.fecha_inicio)} → ${dateLabel(record.fecha_fin)}`,
      ],
    ];
  if (module === "fases")
    details = [
      ["Competición", competition?.nombre || "Competición sin referencia"],
      ["Temporada", season?.nombre || "Temporada sin referencia"],
      ["Orden", record.orden],
    ];
  if (module === "estadios")
    details = [
      ["País", record.pais || "Sin país registrado"],
      ["Ciudad", record.ciudad || "Sin ciudad registrada"],
    ];
  if (module === "jugadores")
    details = [
      ["Nacionalidad", record.nacionalidad || "Sin nacionalidad registrada"],
      ["Posición", record.posicion || "Sin posición registrada"],
      ...(record.fecha_nacimiento
        ? [["Nacimiento", dateLabel(record.fecha_nacimiento)]]
        : []),
    ];
  return (
    <li className="once-context-record">
      <div className="once-context-record-title">
        <h3>{record.nombre}</h3>
        {module === "temporadas" && (
          <span
            className={`once-context-badge${record.activa ? " is-active" : ""}`}
          >
            {record.activa ? "Activa" : "Inactiva"}
          </span>
        )}
        {module === "fases" && (
          <span className="once-context-badge">
            {phaseTypes[record.tipo] || record.tipo}
          </span>
        )}
      </div>
      {module === "jugadores" &&
        record.nombre_completo &&
        record.nombre_completo !== record.nombre && (
          <p className="once-context-fullname">{record.nombre_completo}</p>
        )}
      <dl>
        {details.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </li>
  );
}

function ContextModule({ module, data, onSaved, onError }) {
  const names = contextModuleNames[module];
  const [filters, setFilters] = useState(emptyContextFilters);
  const [creating, setCreating] = useState(false);
  const [saved, setSaved] = useState("");
  const [players, setPlayers] = useState({ records: null, error: "" });
  const [retry, setRetry] = useState(0);
  const update = (name, value) =>
    setFilters((current) => changeContextFilter(current, name, value));

  useEffect(() => {
    if (module !== "jugadores") return undefined;
    const controller = new AbortController();
    apiCollection("/jugadores/", { signal: controller.signal })
      .then((records) => {
        if (!controller.signal.aborted) setPlayers({ records, error: "" });
      })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        setPlayers({
          records: null,
          error: failure.message || "No se pudieron cargar los jugadores.",
        });
        if (failure.status === 401) onError?.(failure);
      });
    return () => controller.abort();
  }, [module, retry, onError, data.updatedAt]);

  const records =
    module === "jugadores" ? players.records || [] : data[module] || [];
  const loading =
    module === "jugadores"
      ? players.records === null && !players.error
      : data.catalogsReady === false;
  const error = module === "jugadores" ? players.error : "";
  const relations = contextRelations(data);
  const visible = filterContext(module, records, filters, data);
  const seasons = (data.temporadas || []).filter(
    (season) =>
      !filters.competition ||
      String(season.competicion_id) === filters.competition,
  );
  const countries = contextOptions(
    records,
    module === "jugadores" ? "nacionalidad" : "pais",
  );
  const cities = contextOptions(
    records.filter(
      (record) => !filters.country || record.pais === filters.country,
    ),
    "ciudad",
  );
  const positions = contextOptions(records, "posicion");
  const hasFilters = Object.values(filters).some(Boolean);
  const prerequisite =
    module === "temporadas" && !(data.competiciones || []).length
      ? "Crea primero una competición para añadir sus temporadas."
      : module === "fases" && !(data.temporadas || []).length
        ? "Crea primero una temporada para añadir sus fases."
        : "";

  async function created(record) {
    setCreating(false);
    setSaved(`${record.nombre} se ha guardado.`);
    if (module === "jugadores")
      setPlayers((current) => ({
        records: [...(current.records || []), record],
        error: "",
      }));
    try {
      await onSaved?.({ module, record });
    } catch (failure) {
      setSaved(
        `${record.nombre} se ha guardado. No pudimos actualizar la lista; usa Actualizar para verla.`,
      );
      onError?.(failure);
    }
  }

  const select = (name, label, options, all, disabled = false) => (
    <Field label={label}>
      <select
        value={filters[name]}
        onChange={(event) => update(name, event.target.value)}
        disabled={disabled}
      >
        <option value="">{all}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
  const named = (items) =>
    items.map((item) => ({ value: item.id, label: item.nombre }));
  const strings = (items) => items.map((value) => ({ value, label: value }));

  return (
    <section
      className="v-panel once-context-panel"
      aria-labelledby={`context-${module}-title`}
      aria-busy={loading || undefined}
    >
      <header className="once-context-heading">
        <div>
          <h2 id={`context-${module}-title`}>{names.title}</h2>
          <p>{names.description}</p>
        </div>
        <button
          className="v-btn v-btn-primary"
          type="button"
          onClick={() => {
            setSaved("");
            setCreating(true);
          }}
          disabled={loading || !!error || !!prerequisite}
        >
          <Icon name="plus" />
          {names.create}
        </button>
      </header>
      {prerequisite && !loading && (
        <p className="once-context-help">{prerequisite}</p>
      )}
      <div
        className="once-context-filters"
        role="group"
        aria-label={`Filtrar ${names.title.toLowerCase()}`}
      >
        <Field label="Buscar por nombre">
          <input
            type="search"
            value={filters.search}
            onChange={(event) => update("search", event.target.value)}
            placeholder={`Buscar ${names.title.toLowerCase()}…`}
          />
        </Field>
        {["temporadas", "fases"].includes(module) &&
          select(
            "competition",
            "Competición",
            named(data.competiciones || []),
            "Todas las competiciones",
          )}
        {module === "temporadas" &&
          select(
            "active",
            "Estado de temporada",
            [
              { value: "true", label: "Activas" },
              { value: "false", label: "Inactivas" },
            ],
            "Todos los estados",
          )}
        {module === "fases" &&
          select(
            "season",
            "Temporada",
            seasons.map((item) => ({
              value: item.id,
              label: filters.competition
                ? item.nombre
                : `${item.nombre} · ${relations.competitions.get(String(item.competicion_id))?.nombre || "Sin competición"}`,
            })),
            "Todas las temporadas",
          )}
        {["estadios", "jugadores"].includes(module) &&
          select(
            "country",
            module === "jugadores" ? "Nacionalidad" : "País",
            strings(countries),
            module === "jugadores"
              ? "Todas las nacionalidades"
              : "Todos los países",
          )}
        {module === "estadios" &&
          select("city", "Ciudad", strings(cities), "Todas las ciudades")}
        {module === "jugadores" &&
          select(
            "position",
            "Posición",
            strings(positions),
            "Todas las posiciones",
          )}
      </div>
      <div className="once-context-summary">
        <p role="status">
          {loading
            ? "Cargando fichas…"
            : error
              ? "La lista no está disponible."
              : `${visible.length} de ${records.length} ${records.length === 1 ? names.singular : names.title.toLowerCase()}`}
        </p>
        {hasFilters && (
          <button
            className="v-btn v-btn-ghost"
            type="button"
            onClick={() => setFilters(emptyContextFilters())}
          >
            Limpiar filtros
          </button>
        )}
      </div>
      {saved && (
        <p className="once-context-success" role="status">
          {saved}
        </p>
      )}
      {error && (
        <div className="once-context-error" role="alert">
          <p>{error}</p>
          <button
            className="v-btn v-btn-secondary"
            type="button"
            onClick={() => {
              setPlayers({ records: null, error: "" });
              setRetry((value) => value + 1);
            }}
          >
            Volver a intentar
          </button>
        </div>
      )}
      {!loading &&
        !error &&
        (visible.length ? (
          <ul className="once-context-records">
            {visible.map((record) => (
              <ContextRecord
                key={record.id}
                module={module}
                record={record}
                relations={relations}
              />
            ))}
          </ul>
        ) : (
          <EmptyState
            title={
              hasFilters
                ? "No hay coincidencias"
                : `Todavía no hay ${names.title.toLowerCase()}`
            }
            action={hasFilters ? "Limpiar filtros" : undefined}
            onAction={() => setFilters(emptyContextFilters())}
          >
            {hasFilters
              ? "Prueba otro nombre o amplía los filtros para ver más fichas."
              : prerequisite || `Añade la primera ficha con «${names.create}».`}
          </EmptyState>
        ))}
      {creating && (
        <ContextForm
          module={module}
          data={data}
          filters={filters}
          onClose={() => setCreating(false)}
          onCreated={created}
          onError={onError}
        />
      )}
    </section>
  );
}

export function ContextView({
  module = "temporadas",
  data = {},
  onSaved,
  onError,
}) {
  if (!contextModuleNames[module]) return null;
  return (
    <ContextModule
      key={module}
      module={module}
      data={data}
      onSaved={onSaved}
      onError={onError}
    />
  );
}
