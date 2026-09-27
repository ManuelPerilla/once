function resultForTeam(match, teamId) {
  if (match.estado !== "finalizado") return "P";
  const home = match.equipo_local_id === teamId;
  const own = home ? match.marcador_local : match.marcador_visitante;
  const rival = home ? match.marcador_visitante : match.marcador_local;
  if (own === rival) return "E";
  return own > rival ? "V" : "D";
}

export function FormRibbon({ matches, teamId, navigate }) {
  const recent = [...matches]
    .filter(
      (match) =>
        match.estado === "finalizado" &&
        (match.equipo_local_id === teamId ||
          match.equipo_visitante_id === teamId),
    )
    .sort((a, b) => {
      if (a.fecha && b.fecha) return new Date(b.fecha) - new Date(a.fecha);
      return b.id - a.id;
    })
    .slice(0, 5);

  if (!recent.length)
    return (
      <p className="once-detail-note">
        Todavía no hay partidos finalizados para mostrar la forma reciente.
      </p>
    );

  return (
    <>
      <p className="once-detail-note">
        Últimos cinco partidos finalizados. V: victoria · E: empate · D:
        derrota.
      </p>
      <div className="p-form-ribbon" aria-label="Forma reciente">
        {recent.map((match) => {
          const result = resultForTeam(match, teamId);
          const rival =
            match.equipo_local_id === teamId
              ? match.equipo_visitante
              : match.equipo_local;
          return (
            <button
              key={match.id}
              data-result={result}
              onClick={() => navigate("match", match.id)}
              title={rival?.nombre || "Partido"}
            >
              <strong>{result}</strong>
              <small>{rival?.nombre || "Rival"}</small>
            </button>
          );
        })}
      </div>
    </>
  );
}
