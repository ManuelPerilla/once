import { EmptyState } from "../components/ui/EmptyState";
import { MatchRow } from "../components/football/MatchRow";

export function MatchesView({
  filter,
  setFilter,
  incompleteCount,
  matches,
  onDelete,
  onCreate,
}) {
  const filters = [
    ["", "Todos"],
    ["programado", "Programados"],
    ["en vivo", "En vivo"],
    ["finalizado", "Finalizados"],
    ...(incompleteCount ? [["incompletos", "Incompletos"]] : []),
  ];

  return (
    <section aria-label="Registro de partidos">
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
        <span className="v-updated" role="status">
          {matches.length} partidos
        </span>
      </div>

      {matches.length ? (
        <div className="v-match-grid">
          {matches.map((match) => (
            <MatchRow
              key={match.id}
              match={match}
              onDelete={() => onDelete(match.id)}
            />
          ))}
        </div>
      ) : (
        <div className="v-panel">
          <EmptyState
            title="No hay partidos en esta vista"
            icon="pitch"
            action="Registrar partido"
            onAction={onCreate}
          >
            Registra un encuentro o selecciona otro estado para consultar tus
            partidos.
          </EmptyState>
        </div>
      )}
    </section>
  );
}
