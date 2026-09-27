import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../api";
import { Icon } from "../components/ui/Icon";
import { Crest } from "../components/ui/Crest";
import { Status } from "../components/ui/Status";
import { MatchSource } from "../components/football/MatchSource.jsx";
import { TacticalScene } from "./components/TacticalScene";
import { usePagedMatches } from "../lib/usePagedMatches";
import { Pagination } from "../components/ui/Pagination";
import {
  filterMatches,
  formatMatchDate,
  normalizeSearch,
} from "./matchFilters";

const statuses = [
  ["", "Todos"],
  ["en vivo", "En juego"],
  ["programado", "Próximos"],
  ["finalizado", "Finalizados"],
];
const typeLabels = {
  club: "Clubes",
  seleccion: "Selecciones",
  liga_nacional: "Ligas nacionales",
  copa_nacional: "Copas nacionales",
  internacional_clubes: "Torneos internacionales de clubes",
  internacional_selecciones: "Torneos de selecciones",
};

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
                  ? (match.marcador_local ?? "—")
                  : (match.marcador_visitante ?? "—")}
            </b>
          </span>
        ))}
      </span>
      <MatchSource source={match.data_source} />
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
  embedded = false,
  heading = "Partidos de este archivo.",
  server = false,
  scope = {},
  revision = 0,
}) {
  const Heading = full ? "h1" : "h2";
  const [status, setStatus] = useState("");
  const [competition, setCompetition] = useState("");
  const [query, setQuery] = useState("");
  const [season, setSeason] = useState("");
  const [page, setPage] = useState(1);
  const result = usePagedMatches({
    enabled: server,
    filters: {
      ...scope,
      status,
      competition_id: competition || scope.competition_id,
      search: query,
      season_id: season || scope.season_id,
    },
    page,
    pageSize: full || embedded ? 24 : 6,
    revision,
  });
  const changeFilter = (setter, value) => {
    setter(value);
    setPage(1);
  };
  const seasons =
    competitions.find((item) => String(item.id) === competition)?.temporadas ||
    [];
  const clearFilters = () => {
    setStatus("");
    setCompetition("");
    setQuery("");
    setSeason("");
    setPage(1);
  };
  const context = useMemo(
    () => filterMatches(matches, "", competition, { query, season }),
    [matches, competition, query, season],
  );
  const localFiltered = useMemo(
    () => filterMatches(context, status),
    [context, status],
  );
  const filtered = server ? result.items : localFiltered;
  return (
    <section
      className={`once-section${embedded ? " once-section-embedded" : ""}`}
      id="encuentros"
    >
      <div className="once-section-title">
        <div>
          <span className="once-eyebrow">
            {embedded
              ? "PARTIDOS DE ESTA SELECCIÓN"
              : "01 / EL PULSO DEL JUEGO"}
          </span>
          <Heading>
            {embedded
              ? heading
              : full
                ? "El centro del partido."
                : "Cada partido cuenta."}
          </Heading>
        </div>
        {!full && !embedded && (
          <button
            className="once-text-link"
            onClick={() => navigate("matches")}
          >
            Todos los partidos <Icon name="arrow" />
          </button>
        )}
      </div>
      <div className="once-filter-bar">
        {(full || embedded) && (
          <label className="once-entity-search">
            <Icon name="search" />
            <input
              type="search"
              value={query}
              onChange={(event) => changeFilter(setQuery, event.target.value)}
              placeholder="Equipo o competición…"
              aria-label="Buscar partidos por equipo o competición"
            />
          </label>
        )}
        <div
          className="once-tabs"
          role="group"
          aria-label="Filtrar partidos por estado"
        >
          {statuses.map(([value, label]) => (
            <button
              key={value}
              aria-pressed={status === value}
              onClick={() => changeFilter(setStatus, value)}
            >
              {value === "en vivo" && <i />}
              {label}
              {!server && (
                <span>
                  {context.filter((m) => !value || m.estado === value).length}
                </span>
              )}
            </button>
          ))}
        </div>
        {(!embedded || competitions.length > 1) && (
          <label className="once-select">
            <Icon name="trophy" />
            <select
              aria-label="Filtrar por competición"
              value={competition}
              onChange={(e) => {
                setCompetition(e.target.value);
                setSeason("");
                setPage(1);
              }}
            >
              <option value="">Todas las competiciones</option>
              {competitions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </label>
        )}
        {!embedded && seasons.length > 0 && (
          <label className="once-select">
            <select
              aria-label="Filtrar partidos por temporada"
              value={season}
              onChange={(event) => changeFilter(setSeason, event.target.value)}
            >
              <option value="">Todas las temporadas</option>
              {seasons.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.nombre}
                </option>
              ))}
              <option value="unassigned">Sin temporada asignada</option>
            </select>
          </label>
        )}
      </div>
      <div className="once-filter-summary">
        <p className="once-results-count" role="status">
          {server
            ? result.pending
              ? "Consultando… "
              : `${result.total} `
            : `${filtered.length} de ${matches.length} `}
          {filtered.length === 1
            ? "encuentro disponible"
            : "encuentros disponibles"}
          {!full && !embedded && filtered.length > 6
            ? " · Mostrando los primeros 6"
            : ""}
        </p>
        {(status || competition || query || season) && filtered.length > 0 && (
          <button className="once-text-link" onClick={clearFilters}>
            Limpiar filtros <Icon name="refresh" />
          </button>
        )}
      </div>
      {server && result.error && (
        <p role="alert">No pudimos actualizar esta vista: {result.error}</p>
      )}
      {filtered.length ? (
        <div className="once-fixture-grid" key={`${status}-${competition}`}>
          {(full || embedded ? filtered : filtered.slice(0, 6)).map(
            (match, index) => (
              <FixtureCard
                key={match.id}
                match={match}
                navigate={navigate}
                index={index}
              />
            ),
          )}
        </div>
      ) : !result.pending || !server ? (
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
          {(status || competition || query || season) && (
            <button className="once-text-link" onClick={clearFilters}>
              Restablecer filtros <Icon name="refresh" />
            </button>
          )}
        </div>
      ) : (
        <p role="status">Cargando los encuentros de esta selección…</p>
      )}
      {server && (full || embedded) && (
        <Pagination
          page={page}
          pageSize={24}
          total={result.total}
          onChange={setPage}
          busy={result.pending}
        />
      )}
    </section>
  );
}

export function EntityExplorer({
  kind,
  entities,
  navigate,
  server = false,
  revision = 0,
}) {
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("");
  const [type, setType] = useState("");
  const [competition, setCompetition] = useState("");
  const [page, setPage] = useState(1);
  const [remote, setRemote] = useState({ items: [], total: 0, pending: true });
  const [facets, setFacets] = useState(null);
  const remoteQuery = new URLSearchParams({
    page,
    page_size: "24",
    search: query,
    country,
    type,
    ...(competition ? { competition_id: competition } : {}),
  }).toString();
  useEffect(() => {
    if (!server) return;
    const controller = new AbortController();
    apiRequest("/public/equipos/filters", { signal: controller.signal })
      .then(setFacets)
      .catch((error) => {
        if (!controller.signal.aborted)
          setRemote((current) => ({ ...current, error: error.message }));
      });
    return () => controller.abort();
  }, [server, revision]);
  useEffect(() => {
    if (!server) return;
    const controller = new AbortController();
    const timer = setTimeout(
      () => {
        setRemote((current) => ({ ...current, pending: true, error: "" }));
        apiRequest(`/public/equipos/page?${remoteQuery}`, {
          signal: controller.signal,
        })
          .then((result) => setRemote({ ...result, pending: false }))
          .catch((error) => {
            if (!controller.signal.aborted)
              setRemote((current) => ({
                ...current,
                pending: false,
                error: error.message,
              }));
          });
      },
      query ? 250 : 0,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [server, remoteQuery, query, revision]);
  const change = (setter, value) => {
    setter(value);
    setPage(1);
  };
  const isTeam = kind === "team";
  const types =
    facets?.types ||
    [...new Set(entities.map((item) => item.tipo).filter(Boolean))].sort();
  const competitions =
    facets?.competitions ||
    [
      ...new Map(
        entities
          .flatMap((item) => item.competiciones || [])
          .map((item) => [item.id, item]),
      ).values(),
    ].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  const countries =
    facets?.countries ||
    [...new Set(entities.map((item) => item.pais).filter(Boolean))].sort();
  const filtered = server
    ? remote.items
    : entities
        .filter(
          (item) =>
            normalizeSearch(item.nombre).includes(normalizeSearch(query)) &&
            (!country || item.pais === country) &&
            (!type || item.tipo === type) &&
            (!competition ||
              item.competiciones?.some(
                (linked) => String(linked.id) === competition,
              )),
        )
        .sort((a, b) => a.nombre.localeCompare(b.nombre, "es") || a.id - b.id);
  const clearFilters = () => {
    setQuery("");
    setCountry("");
    setType("");
    setCompetition("");
    setPage(1);
  };
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
            onChange={(e) => change(setQuery, e.target.value)}
            placeholder={isTeam ? "Buscar equipo…" : "Buscar competición…"}
            aria-label={isTeam ? "Buscar equipo" : "Buscar competición"}
          />
        </label>
        <label className="once-select">
          <Icon name="globe" />
          <select
            value={country}
            onChange={(e) => change(setCountry, e.target.value)}
            aria-label="Filtrar por país"
          >
            <option value="">Todos los países</option>
            {countries.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        {types.length > 1 && (
          <label className="once-select">
            <select
              aria-label={
                isTeam
                  ? "Filtrar equipos por tipo"
                  : "Filtrar competiciones por tipo"
              }
              value={type}
              onChange={(event) => change(setType, event.target.value)}
            >
              <option value="">
                {isTeam ? "Clubes y selecciones" : "Todos los tipos de torneo"}
              </option>
              {types.map((value) => (
                <option value={value} key={value}>
                  {typeLabels[value] || value.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        )}
        {isTeam && competitions.length > 0 && (
          <label className="once-select">
            <select
              aria-label="Filtrar equipos por competición"
              value={competition}
              onChange={(event) => change(setCompetition, event.target.value)}
            >
              <option value="">Todas sus competiciones</option>
              {competitions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nombre}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="once-filter-summary">
        <p className="once-results-count" role="status">
          {server
            ? remote.pending
              ? "Consultando… "
              : `${remote.total} `
            : `${filtered.length} de ${entities.length} `}
          {isTeam ? "equipos" : "competiciones"} · Orden alfabético
        </p>
        {(query || country || type || competition) && filtered.length > 0 && (
          <button className="once-text-link" onClick={clearFilters}>
            Limpiar filtros <Icon name="refresh" />
          </button>
        )}
      </div>
      {server && remote.error && <p role="alert">{remote.error}</p>}
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
      {!filtered.length && (!server || !remote.pending) && (
        <div className="once-empty">
          <Icon name="search" />
          <h3>No encontramos coincidencias.</h3>
          <p>
            {entities.length
              ? "Prueba otro nombre o país."
              : "El catálogo está listo para recibir sus primeros registros."}
          </p>
          {(query || country || type || competition) && (
            <button className="once-text-link" onClick={clearFilters}>
              Limpiar filtros <Icon name="refresh" />
            </button>
          )}
        </div>
      )}
      {server && (
        <Pagination
          page={page}
          pageSize={24}
          total={remote.total}
          onChange={setPage}
          busy={remote.pending}
        />
      )}
    </section>
  );
}

export function ExploreHome({
  matches,
  competitions,
  teams,
  navigate,
  demo,
  totals = {},
  revision = 0,
}) {
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
          [totals.matches ?? matches.length, "Partidos", "matches"],
          [totals.teams ?? teams.length, "Equipos", "teams"],
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
        server={!demo}
        revision={revision}
      />
      <section className="once-discover">
        <div className="once-discover-copy">
          <span className="once-eyebrow">SIGUE TU CURIOSIDAD</span>
          <h2>
            Siempre hay otra forma <em>de entrar.</em>
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
