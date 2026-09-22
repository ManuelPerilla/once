import { Crest } from "../ui/Crest";
import { Icon } from "../ui/Icon";
import { Status } from "../ui/Status";

export function MatchRow({ match, onDelete }) {
  return (
    <article className="v-match-row">
      <div className="v-match-meta">
        <span>{match.competicion?.nombre || "Sin competición"}</span>
        <Status value={match.estado} />
      </div>
      <div className="v-match-teams">
        <span>
          <Crest
            small
            src={match.equipo_local?.logo}
            name={match.equipo_local?.nombre}
          />
          {match.equipo_local?.nombre || "Equipo sin asignar"}
        </span>
        <strong>
          {match.estado === "programado"
            ? "vs"
            : `${match.marcador_local} : ${match.marcador_visitante}`}
        </strong>
        <span>
          {match.equipo_visitante?.nombre || "Equipo sin asignar"}
          <Crest
            small
            src={match.equipo_visitante?.logo}
            name={match.equipo_visitante?.nombre}
          />
        </span>
      </div>
      {onDelete && (
        <div className="v-match-footer">
          <span>Registro #{match.id}</span>
          <button
            className="v-text-btn v-danger"
            onClick={onDelete}
            aria-label={`Eliminar partido ${match.id}`}
          >
            <Icon name="trash" />
            Eliminar
          </button>
        </div>
      )}
    </article>
  );
}
