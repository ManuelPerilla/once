function minuteLabel(event) {
  return event.adicional ? `${event.minuto}+${event.adicional}′` : `${event.minuto}′`;
}

const eventLabels = {
  gol: "Gol",
  "tarjeta amarilla": "Tarjeta amarilla",
  "tarjeta roja": "Tarjeta roja",
  sustitucion: "Sustitución",
  penalti: "Penalti",
  autogol: "Autogol",
};

export function MatchTimeline({ events = [], players = [], match, navigate }) {
  if (!events.length) return null;

  const playerById = new Map(players.map((player) => [player.id, player]));
  const ordered = [...events].sort(
    (a, b) => a.minuto - b.minuto || a.adicional - b.adicional || a.id - b.id,
  );

  return (
    <section className="p-timeline-section">
      <div className="p-section-head">
        <div>
          <span className="p-kicker">CRONOLOGÍA</span>
          <h2>El partido, minuto a minuto.</h2>
        </div>
        <span>{ordered.length} eventos</span>
      </div>
      <ol className="p-timeline">
        {ordered.map((event) => {
          const player = playerById.get(event.jugador_id);
          const home = event.equipo_id === match.equipo_local_id;
          return (
            <li
              key={event.id}
              className="p-timeline-event"
              data-side={home ? "home" : "away"}
            >
              <span className="p-timeline-minute">{minuteLabel(event)}</span>
              <span className="p-timeline-node" aria-hidden="true" />
              <div className="p-timeline-copy">
                <small>{eventLabels[event.tipo] || event.tipo}</small>
                {player ? (
                  <button onClick={() => navigate("player", player.id)}>
                    {player.nombre}
                  </button>
                ) : (
                  <strong>{event.detalle || "Evento registrado"}</strong>
                )}
                {player && event.detalle && <span>{event.detalle}</span>}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
