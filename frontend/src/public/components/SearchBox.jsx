import { useId, useMemo, useRef, useState } from "react";
import { Icon } from "../../components/ui/Icon";

function normalize(value = "") {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

export function SearchBox({ teams, competitions, players, matches, navigate }) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const inputRef = useRef(null);
  const resultsRef = useRef(null);
  const resultsId = useId();
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
    setExpanded(false);
  };

  return (
    <div
      className="p-search"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          setExpanded(false);
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setExpanded(false);
          inputRef.current?.focus();
        }
        if (
          (event.key === "ArrowDown" || event.key === "ArrowUp") &&
          expanded &&
          results.length
        ) {
          event.preventDefault();
          const buttons = [
            ...(resultsRef.current?.querySelectorAll("button") || []),
          ];
          const index = buttons.indexOf(document.activeElement);
          const next =
            index < 0
              ? event.key === "ArrowDown"
                ? 0
                : buttons.length - 1
              : (index + (event.key === "ArrowDown" ? 1 : buttons.length - 1)) %
                buttons.length;
          buttons[next]?.focus();
        }
      }}
    >
      <Icon name="search" />
      <input
        type="search"
        ref={inputRef}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setExpanded(true);
        }}
        onFocus={() => setExpanded(true)}
        aria-controls={
          expanded && normalized.length >= 2 ? resultsId : undefined
        }
        placeholder="Buscar en ONCE"
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
      {expanded && normalized.length >= 2 && (
        <div
          className="p-search-results"
          role="region"
          aria-label="Resultados de búsqueda"
          id={resultsId}
          ref={resultsRef}
        >
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
