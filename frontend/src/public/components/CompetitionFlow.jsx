import { Icon } from "../../components/ui/Icon";

export function CompetitionFlow({ matches, navigate }) {
  const phased = matches.filter((match) => match.fase?.id);
  if (!phased.length) return null;

  const groups = new Map();
  phased.forEach((match) => {
    const id = match.fase.id;
    if (!groups.has(id)) {
      groups.set(id, {
        phase: match.fase,
        matches: [],
      });
    }
    groups.get(id).matches.push(match);
  });

  const stages = [...groups.values()].sort(
    (a, b) => (a.phase.orden ?? 0) - (b.phase.orden ?? 0),
  );

  return (
    <section className="p-flow-section">
      <div className="p-section-head">
        <div>
          <span className="p-kicker">ESTRUCTURA</span>
          <h2>El camino por fases.</h2>
        </div>
        <span>{stages.length} fases</span>
      </div>
      <div className="p-stage-flow">
        {stages.map(({ phase, matches: stageMatches }, stageIndex) => (
          <article className="p-stage-column" key={phase.id}>
            <header>
              <small>{String(stageIndex + 1).padStart(2, "0")}</small>
              <strong>{phase.nombre}</strong>
              <span>{phase.tipo}</span>
            </header>
            {stageMatches.map((match) => (
              <button key={match.id} onClick={() => navigate("match", match.id)}>
                <span>
                  {match.equipo_local?.nombre || "Local"}
                  <b>
                    {match.estado === "programado" ? "vs" : match.marcador_local}
                  </b>
                </span>
                <span>
                  {match.equipo_visitante?.nombre || "Visitante"}
                  <b>
                    {match.estado === "programado" ? "·" : match.marcador_visitante}
                  </b>
                </span>
                <Icon name="arrow" />
              </button>
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}
