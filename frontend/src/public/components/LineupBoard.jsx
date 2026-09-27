import { Crest } from "../../components/ui/Crest";
import "./LineupBoard.css";

export function LineupBoard({ lineups = [], players = [], match, navigate }) {
  const starters = lineups.filter((item) => item.titular);
  if (!starters.length) return null;
  const playerById = new Map(players.map((player) => [player.id, player]));
  const teams = [
    [match.equipo_local_id, match.equipo_local, "Local"],
    [match.equipo_visitante_id, match.equipo_visitante, "Visitante"],
  ];
  return (
    <section className="p-lineup-section">
      <div className="p-section-head">
        <div>
          <span className="p-kicker">ALINEACIONES</span>
          <h2>Titulares, equipo por equipo.</h2>
        </div>
        <span>{starters.length} titulares</span>
      </div>
      <p className="once-detail-note">
        Orden publicado por la fuente. La lista no representa posiciones
        tácticas.
      </p>
      <div className="once-lineup-grid">
        {teams.map(([teamId, team, side]) => {
          const entries = starters
            .filter((item) => item.equipo_id === teamId)
            .sort((left, right) => (left.orden ?? 99) - (right.orden ?? 99));
          return (
            <section
              className="once-lineup-team"
              key={side}
              aria-label={`Titulares de ${team?.nombre || side}`}
            >
              <header>
                <Crest small src={team?.logo} name={team?.nombre || side} />
                <div>
                  <small>{side}</small>
                  <h3>{team?.nombre || "Equipo por confirmar"}</h3>
                </div>
              </header>
              {entries.length ? (
                <ol>
                  {entries.map((item) => {
                    const player =
                      playerById.get(item.jugador_id) ||
                      (item.jugador_nombre
                        ? { id: item.jugador_id, nombre: item.jugador_nombre }
                        : null);
                    const name =
                      player?.nombre || `Jugador #${item.jugador_id}`;
                    return (
                      <li key={item.id || item.jugador_id}>
                        <button
                          type="button"
                          className="once-lineup-player"
                          disabled={!player}
                          onClick={() => navigate("player", player.id)}
                          aria-label={player ? `Ver perfil de ${name}` : name}
                        >
                          <b
                            aria-label={
                              item.dorsal == null
                                ? "Dorsal sin confirmar"
                                : `Dorsal ${item.dorsal}`
                            }
                          >
                            {item.dorsal ?? "—"}
                          </b>
                          <span>{name}</span>
                        </button>
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <p className="once-detail-note">
                  Titulares pendientes de confirmar.
                </p>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}
