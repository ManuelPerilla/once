import { Pitch } from "./Pitch";

function Marker({ item, player, side, index, total, navigate }) {
  const normalized = total <= 1 ? 0.5 : index / (total - 1);
  const top = 12 + normalized * 76;
  const left = side === "home" ? 25 + (index % 3) * 8 : 75 - (index % 3) * 8;

  return (
    <button
      className="p-player-marker"
      data-side={side}
      style={{ "--marker-x": `${left}%`, "--marker-y": `${top}%` }}
      onClick={() => player && navigate("player", player.id)}
      aria-label={player ? `Ver perfil de ${player.nombre}` : "Jugador sin ficha"}
    >
      <b>{item.dorsal ?? "·"}</b>
      <span>{player?.nombre || `Jugador #${item.jugador_id}`}</span>
    </button>
  );
}

export function LineupBoard({ lineups = [], players = [], match, navigate }) {
  const starters = lineups.filter((item) => item.titular);
  if (!starters.length) return null;

  const playerById = new Map(players.map((player) => [player.id, player]));
  const home = starters
    .filter((item) => item.equipo_id === match.equipo_local_id)
    .sort((a, b) => (a.orden ?? 99) - (b.orden ?? 99));
  const away = starters
    .filter((item) => item.equipo_id === match.equipo_visitante_id)
    .sort((a, b) => (a.orden ?? 99) - (b.orden ?? 99));

  return (
    <section className="p-lineup-section">
      <div className="p-section-head">
        <div>
          <span className="p-kicker">ALINEACIONES</span>
          <h2>Los once sobre el terreno.</h2>
        </div>
        <span>{starters.length} titulares</span>
      </div>
      <Pitch label="V / STARTING XI">
        <div className="p-lineup-layer">
          {home.map((item, index) => (
            <Marker
              key={item.id}
              item={item}
              player={playerById.get(item.jugador_id)}
              side="home"
              index={index}
              total={home.length}
              navigate={navigate}
            />
          ))}
          {away.map((item, index) => (
            <Marker
              key={item.id}
              item={item}
              player={playerById.get(item.jugador_id)}
              side="away"
              index={index}
              total={away.length}
              navigate={navigate}
            />
          ))}
        </div>
      </Pitch>
    </section>
  );
}
