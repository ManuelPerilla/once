import { useEffect, useState } from "react";
import { usePagedMatches } from "../lib/usePagedMatches";
import { localDateRange } from "../lib/localDateRange";
import { Pagination } from "../components/ui/Pagination";
import { EmptyState } from "../components/ui/EmptyState";
import { Field } from "../components/ui/Field";
import { MatchRow } from "../components/football/MatchRow";
import { MatchDetailView } from "./MatchDetailView";

export function MatchesView({
  filter,
  setFilter,
  incompleteCount,
  onDelete,
  onCreate,
  context,
  updateContext,
  clearFilters,
  competitions,
  seasons,
  phases,
  teams,
  total,
  onError,
  revision = 0,
}) {
  const [selected, setSelected] = useState(null);
  const filterKey = JSON.stringify([context, filter]);
  const [pagination, setPagination] = useState({ key: filterKey, page: 1 });
  const page = pagination.key === filterKey ? pagination.page : 1;
  const setPage = (value) => setPagination({ key: filterKey, page: value });
  const result = usePagedMatches({
    publicView: false,
    page,
    revision,
    filters: {
      search: context.search,
      competition_id: context.competition,
      season_id: context.season,
      phase_id: context.phase,
      team_id: context.team,
      ...localDateRange(context.from, context.to),
      sort: context.sort,
      status: filter === "incompletos" ? "" : filter,
      attention: filter === "incompletos",
    },
  });
  useEffect(() => {
    if (result.status === 401) onError({ status: 401, message: result.error });
  }, [result.status, result.error, onError]);
  const matches = result.items;
  const ready = !result.pending;
  const filters = [
    ["", "Todos"],
    ["programado", "Programados"],
    ["en vivo", "En vivo"],
    ["finalizado", "Finalizados"],
    ["aplazado", "Aplazados"],
    ["suspendido", "Suspendidos"],
    ["cancelado", "Cancelados"],
    ...(incompleteCount ? [["incompletos", "Incompletos"]] : []),
  ];
  const availableSeasons = seasons.filter(
    (item) => String(item.competicion_id) === context.competition,
  );
  const availablePhases = phases.filter(
    (item) => String(item.temporada_id) === context.season,
  );
  const availableTeams = teams.filter(
    (item) =>
      !context.competition ||
      item.competiciones?.some(
        (competition) => String(competition.id) === context.competition,
      ) ||
      matches.some((match) =>
        [match.equipo_local_id, match.equipo_visitante_id].includes(item.id),
      ),
  );
  const select = (name, label, items, placeholder, disabled = false) => (
    <Field label={label} key={name}>
      <select
        value={context[name]}
        disabled={disabled}
        onChange={(event) => updateContext(name, event.target.value)}
      >
        <option value="">{placeholder}</option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {item.nombre}
          </option>
        ))}
      </select>
    </Field>
  );
  const invalidDates = context.from && context.to && context.from > context.to;
  return (
    <section aria-label="Registro de partidos" className="once-match-workspace">
      <div className="v-panel once-filter-panel">
        <div className="v-panel-head">
          <div>
            <h2>Encuentra un encuentro</h2>
            <p>
              Elige una competición para acotar sus temporadas. Las fechas usan
              la zona horaria de tu dispositivo e incluyen ambos días.
            </p>
          </div>
        </div>
        <div className="once-filter-grid">
          <Field label="Buscar partido">
            <input
              type="search"
              value={context.search}
              placeholder="Equipo, torneo o jornada"
              onChange={(event) => updateContext("search", event.target.value)}
            />
          </Field>
          {select(
            "competition",
            "Competición del partido",
            competitions,
            "Todas las competiciones",
          )}
          {select(
            "season",
            "Temporada del partido",
            [
              ...availableSeasons,
              { id: "unassigned", nombre: "Sin temporada asignada" },
            ],
            context.competition
              ? "Todas sus temporadas"
              : "Elige una competición",
            !context.competition,
          )}
          {select(
            "phase",
            "Fase del partido",
            availablePhases,
            context.season ? "Todas sus fases" : "Elige una temporada",
            !context.season || context.season === "unassigned",
          )}
          {select(
            "team",
            "Equipo participante",
            availableTeams,
            "Todos los equipos",
          )}
          <Field label="Desde">
            <input
              type="date"
              value={context.from}
              onChange={(event) => updateContext("from", event.target.value)}
            />
          </Field>
          <Field label="Hasta">
            <input
              type="date"
              min={context.from || undefined}
              value={context.to}
              onChange={(event) => updateContext("to", event.target.value)}
            />
          </Field>
          <Field label="Ordenar partidos">
            <select
              value={context.sort}
              onChange={(event) => updateContext("sort", event.target.value)}
            >
              <option value="recent">Últimos registrados</option>
              <option value="newest">Fecha: más recientes</option>
              <option value="oldest">Fecha: más antiguos</option>
            </select>
          </Field>
        </div>
        {invalidDates && (
          <p role="alert" className="v-info-note">
            La fecha final debe ser igual o posterior a la inicial.
          </p>
        )}
        <div className="v-match-filters">
          <div
            className="v-segments"
            role="group"
            aria-label="Estado del partido"
          >
            {filters.map(([value, label]) => (
              <button
                key={value}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <button className="v-text-btn" onClick={clearFilters}>
            Limpiar filtros de partidos
          </button>
        </div>
        <p role="status">
          {ready
            ? `${result.total} de ${total} partidos · ${matches.length} en esta página`
            : "Cargando partidos…"}
        </p>
        <p className="once-scope-note">
          “En vivo” indica el estado guardado. Revisa en Datos → Automatización
          la última comprobación de la fuente.
        </p>
      </div>
      {result.error && (
        <p role="alert" className="v-info-note">
          {result.error}
        </p>
      )}
      {matches.length ? (
        <div className="v-match-grid">
          {matches.map((match) => (
            <div key={match.id} className="once-match-entry">
              <MatchRow match={match} onDelete={() => onDelete(match.id)} />
              <div className="once-match-context">
                <span>
                  {match.temporada?.nombre || "Sin temporada"} ·{" "}
                  {match.fase?.nombre || "Sin fase"}
                </span>
                <span>
                  {match.fecha
                    ? new Date(match.fecha).toLocaleString("es", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })
                    : "Fecha pendiente"}
                </span>
                <button
                  className="v-text-btn"
                  aria-label={`Consultar partido ${match.id}`}
                  onClick={() => setSelected(match.id)}
                >
                  Consultar ficha →
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        ready && (
          <div className="v-panel">
            <EmptyState
              title="No hay partidos en esta vista"
              icon="pitch"
              action={total ? "Limpiar filtros" : "Registrar partido"}
              onAction={total ? clearFilters : onCreate}
            >
              {total
                ? "Ajusta el contexto para encontrar otros encuentros."
                : "Registra el primer encuentro o tráelo desde Datos."}
            </EmptyState>
          </div>
        )
      )}
      <Pagination
        page={page}
        pageSize={24}
        total={result.total}
        onChange={setPage}
        busy={!ready}
      />
      {selected && (
        <MatchDetailView
          id={selected}
          onClose={() => setSelected(null)}
          onError={onError}
        />
      )}
    </section>
  );
}
