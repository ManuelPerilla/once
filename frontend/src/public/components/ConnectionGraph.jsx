import { Crest } from "../../components/ui/Crest";
import { Icon } from "../../components/ui/Icon";

export function ConnectionGraph({ match, navigate }) {
  const nodes = [
    match.equipo_local && {
      key: "home",
      label: "LOCAL",
      title: match.equipo_local.nombre,
      type: "team",
      id: match.equipo_local.id,
      crest: match.equipo_local,
    },
    match.competicion && {
      key: "competition",
      label: "COMPETICIÓN",
      title: match.competicion.nombre,
      type: "competition",
      id: match.competicion.id,
      icon: "trophy",
    },
    match.equipo_visitante && {
      key: "away",
      label: "VISITANTE",
      title: match.equipo_visitante.nombre,
      type: "team",
      id: match.equipo_visitante.id,
      crest: match.equipo_visitante,
    },
  ].filter(Boolean);

  if (!nodes.length) return null;

  return (
    <section className="p-connection-graph-section">
      <div className="p-section-head">
        <div>
          <span className="p-kicker">GRAFO / CONTEXTO</span>
          <h2>Un partido no está solo.</h2>
        </div>
        <span>{nodes.length} conexiones directas</span>
      </div>

      <div className="p-connection-graph">
        <svg
          className="p-connection-lines"
          viewBox="0 0 1000 430"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d="M500 215 C410 180 290 105 170 95" />
          <path d="M500 215 C500 155 500 100 500 65" />
          <path d="M500 215 C590 180 710 105 830 95" />
          <circle cx="500" cy="215" r="7" />
          <circle cx="170" cy="95" r="5" />
          <circle cx="500" cy="65" r="5" />
          <circle cx="830" cy="95" r="5" />
        </svg>

        <div className="p-connection-center">
          <small>PARTIDO</small>
          <strong>#{String(match.id).padStart(4, "0")}</strong>
          <span>
            {match.estado === "programado"
              ? "VS"
              : `${match.marcador_local} : ${match.marcador_visitante}`}
          </span>
        </div>

        {nodes.map((node) => (
          <button
            key={node.key}
            className={`p-connection-node p-connection-node-${node.key}`}
            onClick={() => navigate(node.type, node.id)}
          >
            <span className="p-connection-node-symbol">
              {node.crest ? (
                <Crest small src={node.crest.logo} name={node.crest.nombre} />
              ) : (
                <Icon name={node.icon} />
              )}
            </span>
            <span>
              <small>{node.label}</small>
              <strong>{node.title}</strong>
            </span>
            <Icon name="arrow" />
          </button>
        ))}
      </div>
    </section>
  );
}
