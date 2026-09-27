import { useMemo, useState } from "react";
import { Icon } from "../components/ui/Icon";
import { Crest } from "../components/ui/Crest";
import { Status } from "../components/ui/Status";
import { TacticalScene } from "./components/TacticalScene";
import { filterMatches, formatMatchDate } from "./matchFilters";

const statuses = [
  ["", "Todos"],
  ["en vivo", "En juego"],
  ["programado", "Próximos"],
  ["finalizado", "Finalizados"],
];
const normalize = (value) =>
  String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

export function FixtureCard({ match, navigate, index = 0 }) {
  const scheduled = match.estado === "programado";
  return (
    <button
      className="once-fixture once-reveal"
      style={{ "--enter-delay": `${Math.min(index, 5) * 55}ms` }}
      onClick={() => navigate("match", match.id)}
    >
      <span className="once-fixture-top">
        <span>
          <Icon name="trophy" />
          {match.competicion?.nombre || "Competición por confirmar"}
        </span>
        <Status value={match.estado} />
      </span>
      <span className="once-fixture-teams">
        {[match.equipo_local, match.equipo_visitante].map((team, i) => (
          <span key={i}>
            <Crest small src={team?.logo} name={team?.nombre} />
            <strong>{team?.nombre || "Equipo por confirmar"}</strong>
            <b>
              {scheduled
                ? "–"
                : i === 0
                  ? match.marcador_local
                  : match.marcador_visitante}
            </b>
          </span>
        ))}
      </span>
      <span className="once-fixture-bottom">
        <span>
          <Icon name="clock" />
          {formatMatchDate(match.fecha)}
        </span>
        <Icon name="arrow" />
      </span>
    </button>
  );
}

export function MatchExplorer({
  matches,
  competitions,
  navigate,
  full = false,
}) {
  const Heading = full ? "h1" : "h2";
  const [status, setStatus] = useState("");
  const [competition, setCompetition] = useState("");
  const filtered = useMemo(
    () => filterMatches(matches, status, competition),
    [matches, status, competition],
  );
  return (
    <section className="once-section" id="encuentros">
      <div className="once-section-title">
        <div>
          <span className="once-eyebrow">01 / EL PULSO DEL JUEGO</span>
          <Heading>
            {full ? "El centro del partido." : "Cada partido cuenta."}
          </Heading>
        </div>
        {!full && (
          <button
            className="once-text-link"
            onClick={() => navigate("matches")}
          >
            Todos los partidos <Icon name="arrow" />
          </button>
        )}
      </div>
      <div className="once-filter-bar">
        <div
          className="once-tabs"
          role="group"
          aria-label="Filtrar partidos por estado"
        >
          {statuses.map(([value, label]) => (
            <button
              key={value}
              aria-pressed={status === value}
              onClick={() => setStatus(value)}
            >
              {value === "en vivo" && <i />}
              {label}
              <span>
                {
                  matches.filter(
                    (m) =>
                      (!value || m.estado === value) &&
                      (!competition ||
                        String(m.competicion_id) === competition),
                  ).length
                }
              </span>
            </button>
          ))}
        </div>
        <label className="once-select">
          <Icon name="trophy" />
          <select
            aria-label="Filtrar por competición"
            value={competition}
            onChange={(e) => setCompetition(e.target.value)}
          >
            <option value="">Todas las competiciones</option>
            {competitions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="once-results-count" role="status">
        {filtered.length}{" "}
        {filtered.length === 1
          ? "encuentro disponible"
          : "encuentros disponibles"}
        {!full && filtered.length > 6 ? " · Mostrando los primeros 6" : ""}
      </p>
      {filtered.length ? (
        <div className="once-fixture-grid" key={`${status}-${competition}`}>
          {(full ? filtered : filtered.slice(0, 6)).map((match, index) => (
            <FixtureCard
              key={match.id}
              match={match}
              navigate={navigate}
              index={index}
            />
          ))}
        </div>
      ) : (
        <div className="once-empty">
          <Icon name="pitch" />
          <h3>
            {matches.length
              ? "Aquí todavía no rueda el balón."
              : "El primer encuentro está por llegar."}
          </h3>
          <p>
            {matches.length
              ? "Prueba otro estado o competición para seguir explorando."
              : "Los partidos aparecerán cuando se añadan al archivo."}
          </p>
          {(status || competition) && (
            <button
              className="once-text-link"
              onClick={() => {
                setStatus("");
                setCompetition("");
              }}
            >
              Restablecer filtros <Icon name="refresh" />
            </button>
          )}
        </div>
      )}
    </section>
  );
}

export function EntityExplorer({ kind, entities, navigate }) {
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("");
  const isTeam = kind === "team";
  const countries = [
    ...new Set(entities.map((item) => item.pais).filter(Boolean)),
  ].sort();
  const filtered = entities.filter(
    (item) =>
      normalize(item.nombre).includes(normalize(query)) &&
      (!country || item.pais === country),
  );
  return (
    <section className="once-section">
      <div className="once-section-title">
        <div>
          <span className="once-eyebrow">
            {isTeam ? "03 / IDENTIDADES" : "02 / TERRITORIOS DEL JUEGO"}
          </span>
          <h1>
            {isTeam ? "Un escudo. Mil historias." : "Donde todo se encuentra."}
          </h1>
          <p>
            {isTeam
              ? "Descubre los equipos y los encuentros que los conectan."
              : "Ligas y copas. Explora sus equipos, temporadas y resultados."}
          </p>
        </div>
        <Icon name={isTeam ? "shield" : "trophy"} />
      </div>
      <div className="once-filter-bar">
        <label className="once-entity-search">
          <Icon name="search" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={isTeam ? "Buscar equipo…" : "Buscar competición…"}
            aria-label={isTeam ? "Buscar equipo" : "Buscar competición"}
          />
        </label>
        <label className="once-select">
          <Icon name="globe" />
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            aria-label="Filtrar por país"
          >
            <option value="">Todos los países</option>
            {countries.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="once-results-count" role="status">
        {filtered.length} {isTeam ? "equipos" : "competiciones"}
      </p>
      <div className="once-entity-grid">
        {filtered.map((entity, i) => (
          <button
            className="once-entity-card once-reveal"
            key={entity.id}
            style={{ "--enter-delay": `${Math.min(i, 5) * 45}ms` }}
            onClick={() => navigate(kind, entity.id)}
          >
            <span className="once-entity-number">
              {String(i + 1).padStart(2, "0")} /
            </span>
            <Crest src={entity.logo} name={entity.nombre} />
            <h2>{entity.nombre}</h2>
            <span>{entity.pais || "Internacional"}</span>
            <div>
              <small>
                {String(
                  entity.tipo || (isTeam ? "equipo" : "competición"),
                ).replaceAll("_", " ")}
              </small>
              <Icon name="arrow" />
            </div>
          </button>
        ))}
      </div>
      {!filtered.length && (
        <div className="once-empty">
          <Icon name="search" />
          <h3>No encontramos coincidencias.</h3>
          <p>
            {entities.length
              ? "Prueba otro nombre o país."
              : "El catálogo está listo para recibir sus primeros registros."}
          </p>
          {(query || country) && (
            <button
              className="once-text-link"
              onClick={() => {
                setQuery("");
                setCountry("");
              }}
            >
              Limpiar filtros <Icon name="refresh" />
            </button>
          )}
        </div>
      )}
    </section>
  );
}

export function ExploreHome({ matches, competitions, teams, navigate, demo }) {
  return (
    <main id="public-content" tabIndex={-1}>
      <section className="once-hero">
        <div className="once-hero-copy">
          <span className="once-eyebrow">
            <i /> UNA NUEVA FORMA DE VER EL FÚTBOL
          </span>
          <h1>
            EL JUEGO.
            <br />
            TODO
            <br />
            <em>CONECTADO.</em>
          </h1>
          <p>
            Noventa minutos son solo el principio.
            <br />
            Descubre los equipos, las historias y las conexiones que hacen
            grande al fútbol.
          </p>
          <div className="once-hero-actions">
            <button className="once-button" onClick={() => navigate("matches")}>
              Explorar partidos <Icon name="arrow" />
            </button>
            <button
              className="once-quiet-button"
              onClick={() => navigate("teams")}
            >
              Conocer los equipos <Icon name="chevron" />
            </button>
          </div>
        </div>
        <TacticalScene />
        <div className="once-hero-baseline">
          <span>EL FÚTBOL NO SE VE. SE ENTIENDE.</span>
          <span>
            <i /> {demo ? "EDICIÓN DE DEMOSTRACIÓN" : "TU ARCHIVO DE FÚTBOL"}
          </span>
          <Icon name="globe" />
        </div>
      </section>
      <div className="once-stats-strip">
        <span className="once-stats-label">
          UN JUEGO.
          <br />
          <strong>MUCHAS CONEXIONES.</strong>
        </span>
        {[
          [matches.length, "Partidos", "matches"],
          [teams.length, "Equipos", "teams"],
          [competitions.length, "Competiciones", "competitions"],
        ].map(([count, label, route]) => (
          <button key={route} onClick={() => navigate(route)}>
            <strong>{String(count).padStart(2, "0")}</strong>
            <span>{label}</span>
            <Icon name="arrow" />
          </button>
        ))}
      </div>
      <MatchExplorer
        matches={matches}
        competitions={competitions}
        navigate={navigate}
      />
      <section className="once-discover">
        <div className="once-discover-copy">
          <span className="once-eyebrow">SIGUE TU CURIOSIDAD</span>
          <h2>
            Siempre hay
            <br />
            otra forma
            <br />
            <em>de entrar.</em>
          </h2>
          <p>
            Un escudo te lleva a un equipo.
            <br />
            Un equipo, a una competición.
            <br />
            El resto lo descubres tú.
          </p>
          <span className="once-discover-symbol" aria-hidden="true">
            ↗
          </span>
        </div>
        <div className="once-discover-list">
          {[
            [
              "02",
              "competition",
              "competitions",
              "Territorios del juego.",
              "Competiciones",
              competitions,
            ],
            [
              "03",
              "team",
              "teams",
              "La identidad de cada equipo.",
              "Equipos",
              teams,
            ],
          ].map(([number, kind, page, title, label, items]) => (
            <div className="once-discover-group" key={kind}>
              <div className="once-discover-heading">
                <span>
                  {number} / {label.toUpperCase()}
                </span>
                <button
                  className="once-text-link"
                  onClick={() => navigate(page)}
                >
                  Ver todos <Icon name="arrow" />
                </button>
              </div>
              <h3>{title}</h3>
              {items.slice(0, 3).map((entity) => (
                <button
                  className="once-discover-row"
                  key={entity.id}
                  onClick={() => navigate(kind, entity.id)}
                >
                  <Crest small src={entity.logo} name={entity.nombre} />
                  <strong>{entity.nombre}</strong>
                  <small>{entity.pais || "Internacional"}</small>
                  <Icon name="arrow" />
                </button>
              ))}
              {!items.length && (
                <p className="once-results-count">
                  El archivo está por comenzar.
                </p>
              )}
            </div>
          ))}
        </div>
      </section>
      <div className="once-manifesto">
        <span>11 EN LA CANCHA. INFINITAS CONEXIONES.</span>
        <strong>
          ESTO ES <em>ONCE.</em>
        </strong>
        <button
          onClick={() => {
            window.scrollTo({
              top: 0,
              behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
                .matches
                ? "instant"
                : "smooth",
            });
          }}
          aria-label="Volver arriba"
        >
          <Icon name="arrow" />
        </button>
      </div>
    </main>
  );
}
