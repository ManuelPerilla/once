import { useMemo, useState } from "react";
import { Icon } from "../../components/ui/Icon";

function normalize(value = "") {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function SearchBox({ teams, competitions, players, matches, navigate }) {
  const [query, setQuery] = useState("");
  const normalized = normalize(query.trim());

  const results = useMemo(() => {
    if (normalized.length < 2) return [];

    const entities = [
      ...teams.map((team) => ({
        type: "team",
        id: team.id,
        label: team.nombre,
        meta: `Equipo · ${team.pais || "sin país"}`,
      })),
      ...competitions.map((competition) => ({
        type: "competition",
        id: competition.id,
        label: competition.nombre,
        meta: `Competición · ${competition.pais || "Internacional"}`,
      })),
      ...players.map((player) => ({
        type: "player",
        id: player.id,
        label: player.nombre,
        meta: `Jugador · ${player.posicion || player.nacionalidad || "ficha"}`,
      })),
      ...matches.map((match) => ({
        type: "match",
        id: match.id,
        label: `${match.equipo_local?.nombre || "Local"} vs ${match.equipo_visitante?.nombre || "Visitante"}`,
        meta: match.competicion?.nombre || "Partido",
      })),
    ];

    return entities
      .filter((item) =>
        normalize(`${item.label} ${item.meta}`).includes(normalized),
      )
      .slice(0, 8);
  }, [normalized, teams, competitions, players, matches]);

  const open = (result) => {
    navigate(result.type, result.id);
    setQuery("");
  };

  return (
    <div className="p-search">
      <Icon name="search" />
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Buscar en VÉRTICE"
        aria-label="Buscar equipos, competiciones, jugadores o partidos"
      />
      {query && (
        <button
          className="p-search-clear"
          onClick={() => setQuery("")}
          aria-label="Limpiar búsqueda"
        >
          <Icon name="close" />
        </button>
      )}
      {normalized.length >= 2 && (
        <div className="p-search-results" role="listbox">
          {results.length ? (
            results.map((result) => (
              <button
                key={`${result.type}-${result.id}`}
                onClick={() => open(result)}
              >
                <span>
                  <strong>{result.label}</strong>
                  <small>{result.meta}</small>
                </span>
                <Icon name="arrow" />
              </button>
            ))
          ) : (
            <p>No hay coincidencias en el archivo actual.</p>
          )}
        </div>
      )}
    </div>
  );
}
