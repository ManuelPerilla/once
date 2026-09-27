import { useEffect, useState } from "react";
import { apiCollection } from "../../api";
import { Crest } from "../../components/ui/Crest";

export function StandingsTable({ competition }) {
  const [result, setResult] = useState({ key: "", rows: [] });

  const activeSeason =
    competition.temporadas?.find((season) => season.activa) ||
    competition.temporadas?.slice().sort((a, b) => b.id - a.id)[0];
  const seasonId = activeSeason?.id;
  const requestKey = `${competition.id}/${seasonId || ""}`;
  const rows = result.key === requestKey ? result.rows : [];

  useEffect(() => {
    let current = true;
    const query = seasonId ? `?season_id=${seasonId}` : "";
    apiCollection(`/public/competiciones/${competition.id}/standings${query}`)
      .then(rows => { if (current) setResult({ key: requestKey, rows }); })
      .catch(() => { if (current) setResult({ key: requestKey, rows: [] }); });
    return () => { current = false; };
  }, [competition.id, seasonId, requestKey]);

  if (!rows.length) return null;

  return (
    <section className="p-standings-section">
      <div className="p-section-head">
        <div>
          <span className="p-kicker">CLASIFICACIÓN</span>
          <h2>La tabla del momento.</h2>
        </div>
        {activeSeason && <span>{activeSeason.nombre}</span>}
      </div>
      <div className="p-standings" role="table" aria-label="Tabla de posiciones">
        <div className="p-standing-row p-standing-head" role="row">
          <span>#</span>
          <span>Equipo</span>
          <span>PJ</span>
          <span>G</span>
          <span>E</span>
          <span>P</span>
          <span>DG</span>
          <span>PTS</span>
        </div>
        {rows.map((row) => (
          <div className="p-standing-row" role="row" key={row.team.id}>
            <strong>{row.rank}</strong>
            <span className="p-standing-team">
              <Crest small src={row.team.logo} name={row.team.nombre} />
              <b>{row.team.nombre}</b>
            </span>
            <span>{row.played}</span>
            <span>{row.won}</span>
            <span>{row.drawn}</span>
            <span>{row.lost}</span>
            <span>{row.goal_difference > 0 ? "+" : ""}{row.goal_difference}</span>
            <strong>{row.points}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
