import { useEffect, useMemo, useState } from "react";
import { apiCollection } from "../api";
import { Brand } from "../components/ui/Brand";
import { Crest } from "../components/ui/Crest";
import { Icon } from "../components/ui/Icon";
import { Status } from "../components/ui/Status";
import { runViewTransition } from "../lib/viewTransition";
import { CompetitionFlow } from "./components/CompetitionFlow";
import { ConnectionGraph } from "./components/ConnectionGraph";
import { FormRibbon } from "./components/FormRibbon";
import { LineupBoard } from "./components/LineupBoard";
import { MatchTimeline } from "./components/MatchTimeline";
import { Pitch } from "./components/Pitch";
import { SearchBox } from "./components/SearchBox";
import { StandingsTable } from "./components/StandingsTable";
import { ExploreHome, MatchExplorer, EntityExplorer } from "./ExploreHome";
import { formatMatchDate } from "./matchFilters";
import { routeFromPath, publicPath } from "./routes";

function PublicShell({
  children,
  navigate,
  searchData = {},
  route = {},
  demo = false,
}) {
  return (
    <div className="p-app">
      <a className="v-skip-link" href="#public-content">
        Saltar al contenido
      </a>
      <header className="p-header">
        <button
          className="p-brand-button"
          aria-label="ONCE · Inicio"
          onClick={() => navigate("home")}
        >
          <Brand />
        </button>
        <nav className="once-public-nav" aria-label="Explorar fútbol">
          {[
            ["home", "Descubrir"],
            ["matches", "Partidos"],
            ["competitions", "Competiciones"],
            ["teams", "Equipos"],
          ].map(([page, label]) => (
            <button
              key={page}
              aria-current={route.type === page ? "page" : undefined}
              onClick={() => navigate(page)}
            >
              {label}
            </button>
          ))}
        </nav>
        <SearchBox
          teams={searchData.teams || []}
          competitions={searchData.competitions || []}
          players={searchData.players || []}
          matches={searchData.matches || []}
          navigate={navigate}
        />
        <a className="p-admin-link" href="/">
          Administración <Icon name="arrow" />
        </a>
      </header>
      {demo && (
        <div className="once-demo-banner">
          <span>
            <strong>Estás explorando una demo.</strong> Equipos y resultados
            ficticios para probar la experiencia.
          </span>
          <a href="/explore">
            Ver mis datos <Icon name="arrow" />
          </a>
        </div>
      )}
      {children}
      <footer className="p-footer">
        <Brand />
        <span>HECHO PARA QUIENES VIVEN EL JUEGO.</span>
        <a href="/">
          Centro de operaciones <Icon name="arrow" />
        </a>
      </footer>
    </div>
  );
}

function Score({ match }) {
  const scheduled = match.estado === "programado";
  return (
    <div className="p-score">
      <div className="p-team" data-side="home">
        <Crest
          src={match.equipo_local?.logo}
          name={match.equipo_local?.nombre}
        />
        <strong>{match.equipo_local?.nombre || "Equipo por confirmar"}</strong>
      </div>
      <div className="p-score-center">
        <Status value={match.estado} />
        <strong>
          {scheduled
            ? "VS"
            : `${match.marcador_local} : ${match.marcador_visitante}`}
        </strong>
      </div>
      <div className="p-team" data-side="away">
        <Crest
          src={match.equipo_visitante?.logo}
          name={match.equipo_visitante?.nombre}
        />
        <strong>
          {match.equipo_visitante?.nombre || "Equipo por confirmar"}
        </strong>
      </div>
    </div>
  );
}

function EmptyPublic({ title, children }) {
  return (
    <div className="p-empty">
      <span aria-hidden="true">11 / 00</span>
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}

function MatchCard({ match, navigate }) {
  return (
    <button
      className="p-match-card"
      onClick={() => navigate("match", match.id)}
    >
      <span>
        {match.competicion?.nombre || "Sin competición"}
        {match.fecha && <small>{formatMatchDate(match.fecha)}</small>}
      </span>
      <strong>
        {match.equipo_local?.nombre || "Por confirmar"}
        <b>
          {match.estado === "programado"
            ? "VS"
            : `${match.marcador_local} : ${match.marcador_visitante}`}
        </b>
        {match.equipo_visitante?.nombre || "Por confirmar"}
      </strong>
      <Icon name="arrow" />
    </button>
  );
}

function MatchMeta({ match }) {
  const items = [
    ["FECHA", formatMatchDate(match.fecha)],
    ["TEMPORADA", match.temporada?.nombre],
    ["FASE", match.fase?.nombre],
    ["JORNADA", match.jornada],
    [
      "ESTADIO",
      match.estadio
        ? [match.estadio.nombre, match.estadio.ciudad]
            .filter(Boolean)
            .join(" · ")
        : null,
    ],
  ].filter(([, value]) => value);

  if (!items.length) return null;

  return (
    <div className="p-match-meta-strip">
      {items.map(([label, value]) => (
        <span key={label}>
          <small>{label}</small>
          <strong>{value}</strong>
        </span>
      ))}
    </div>
  );
}

function MatchDetail({ match, players, navigate }) {
  if (!match) {
    return (
      <main className="p-detail" id="public-content" tabIndex={-1}>
        <EmptyPublic title="Ese partido no está disponible">
          Puede que haya sido eliminado o que todavía no forme parte del archivo
          público.
        </EmptyPublic>
      </main>
    );
  }

  const stats = match.estadisticas?.[0];

  return (
    <main className="p-detail" id="public-content" tabIndex={-1}>
      <button className="p-back" onClick={() => navigate("home")}>
        <Icon name="arrow" /> Volver al archivo
      </button>
      <section className="p-match-hero">
        <span className="p-kicker">
          {match.competicion?.nombre || "PARTIDO"}
        </span>
        <Score match={match} />
        <MatchMeta match={match} />
        <span className="p-record">
          REGISTRO #{String(match.id).padStart(4, "0")}
        </span>
      </section>

      <section className="p-match-context">
        <Pitch />
        <div className="p-context-copy">
          <span className="p-kicker">SIGUE EL HILO</span>
          <h2>Este partido conecta.</h2>
          <div className="p-connection-list">
            {match.equipo_local && (
              <button onClick={() => navigate("team", match.equipo_local.id)}>
                <Crest
                  small
                  src={match.equipo_local.logo}
                  name={match.equipo_local.nombre}
                />
                <span>
                  <small>EQUIPO LOCAL</small>
                  <strong>{match.equipo_local.nombre}</strong>
                </span>
                <Icon name="arrow" />
              </button>
            )}
            {match.competicion && (
              <button
                onClick={() => navigate("competition", match.competicion.id)}
              >
                <Icon name="trophy" />
                <span>
                  <small>COMPETICIÓN</small>
                  <strong>{match.competicion.nombre}</strong>
                </span>
                <Icon name="arrow" />
              </button>
            )}
            {match.equipo_visitante && (
              <button
                onClick={() => navigate("team", match.equipo_visitante.id)}
              >
                <Crest
                  small
                  src={match.equipo_visitante.logo}
                  name={match.equipo_visitante.nombre}
                />
                <span>
                  <small>EQUIPO VISITANTE</small>
                  <strong>{match.equipo_visitante.nombre}</strong>
                </span>
                <Icon name="arrow" />
              </button>
            )}
          </div>
        </div>
      </section>

      <ConnectionGraph match={match} navigate={navigate} />

      <section className="p-data-panel">
        <div>
          <span className="p-kicker">DATOS DISPONIBLES</span>
          <h2>Lo que sí sabemos.</h2>
        </div>
        {stats ? (
          <div className="p-stat-grid">
            <article>
              <span>POSESIÓN</span>
              <strong>{stats.posesion_local}%</strong>
              <i style={{ "--value": `${stats.posesion_local}%` }} />
              <strong>{stats.posesion_visitante}%</strong>
            </article>
            <article>
              <span>TIROS A PUERTA</span>
              <strong>{stats.tiros_puerta_local}</strong>
              <i
                style={{
                  "--value": `${Math.round(
                    (stats.tiros_puerta_local /
                      Math.max(
                        1,
                        stats.tiros_puerta_local + stats.tiros_puerta_visitante,
                      )) *
                      100,
                  )}%`,
                }}
              />
              <strong>{stats.tiros_puerta_visitante}</strong>
            </article>
          </div>
        ) : (
          <p className="p-data-empty">
            Este encuentro todavía no tiene estadísticas registradas. ONCE
            prefiere dejar el espacio vacío antes que rellenarlo con datos
            dudosos.
          </p>
        )}
      </section>

      <MatchTimeline
        events={match.eventos}
        players={players}
        match={match}
        navigate={navigate}
      />
      <LineupBoard
        lineups={match.alineaciones}
        players={players}
        match={match}
        navigate={navigate}
      />
    </main>
  );
}

function EntityDetail({ entity, kind, matches, navigate, demo }) {
  if (!entity) {
    return (
      <main className="p-detail" id="public-content" tabIndex={-1}>
        <EmptyPublic title="No encontramos esa entidad">
          El registro solicitado no está disponible en el catálogo público.
        </EmptyPublic>
      </main>
    );
  }

  const related =
    kind === "team"
      ? matches.filter(
          (match) =>
            match.equipo_local_id === entity.id ||
            match.equipo_visitante_id === entity.id,
        )
      : matches.filter((match) => match.competicion_id === entity.id);

  return (
    <main className="p-detail" id="public-content" tabIndex={-1}>
      <button className="p-back" onClick={() => navigate("home")}>
        <Icon name="arrow" /> Volver al archivo
      </button>
      <section className="p-entity-hero">
        <Crest src={entity.logo} name={entity.nombre} />
        <div>
          <span className="p-kicker">
            {kind === "team" ? "EQUIPO" : "COMPETICIÓN"}
          </span>
          <h1>{entity.nombre}</h1>
          <p>
            {entity.pais || "Ámbito sin registrar"}
            {entity.tipo
              ? ` · ${String(entity.tipo).replaceAll("_", " ")}`
              : ""}
          </p>
        </div>
      </section>

      {kind === "team" && (
        <section className="p-form-section">
          <span className="p-kicker">FORMA RECIENTE</span>
          <FormRibbon
            matches={matches}
            teamId={entity.id}
            navigate={navigate}
          />
        </section>
      )}

      {kind === "competition" && entity.temporadas?.length > 0 && (
        <section className="p-season-section">
          <span className="p-kicker">EDICIONES</span>
          <div className="p-season-rail">
            {entity.temporadas
              .slice()
              .sort((a, b) => b.id - a.id)
              .map((season) => (
                <article
                  key={season.id}
                  data-active={season.activa || undefined}
                >
                  <small>{season.activa ? "EN CURSO" : "TEMPORADA"}</small>
                  <strong>{season.nombre}</strong>
                  <span>
                    {[season.fecha_inicio, season.fecha_fin]
                      .filter(Boolean)
                      .join(" → ") || "Fechas por completar"}
                  </span>
                </article>
              ))}
          </div>
        </section>
      )}

      {kind === "competition" && (
        <>
          {!demo && <StandingsTable competition={entity} />}
          <CompetitionFlow matches={related} navigate={navigate} />
        </>
      )}

      <section className="p-section">
        <div className="p-section-head">
          <div>
            <span className="p-kicker">PARTIDOS RELACIONADOS</span>
            <h2>El contexto disponible.</h2>
          </div>
          <span>{related.length}</span>
        </div>
        {related.length ? (
          <div className="p-match-list">
            {related.map((match) => (
              <MatchCard key={match.id} match={match} navigate={navigate} />
            ))}
          </div>
        ) : (
          <EmptyPublic title="Sin encuentros relacionados">
            Todavía no hay partidos conectados con este registro.
          </EmptyPublic>
        )}
      </section>
    </main>
  );
}

function PlayerDetail({ player, matches, navigate }) {
  if (!player) {
    return (
      <main className="p-detail" id="public-content" tabIndex={-1}>
        <EmptyPublic title="No encontramos ese jugador">
          La ficha solicitada todavía no está disponible.
        </EmptyPublic>
      </main>
    );
  }

  const appearances = matches.filter((match) =>
    match.alineaciones?.some((item) => item.jugador_id === player.id),
  );
  const events = matches.flatMap((match) =>
    (match.eventos || [])
      .filter(
        (event) =>
          event.jugador_id === player.id || event.asistente_id === player.id,
      )
      .map((event) => ({ ...event, match })),
  );

  return (
    <main className="p-detail" id="public-content" tabIndex={-1}>
      <button className="p-back" onClick={() => navigate("home")}>
        <Icon name="arrow" /> Volver al archivo
      </button>
      <section className="p-player-hero">
        <span className="p-player-monogram" aria-hidden="true">
          {player.nombre
            .split(" ")
            .slice(0, 2)
            .map((part) => part[0])
            .join("")
            .toUpperCase()}
        </span>
        <div>
          <span className="p-kicker">JUGADOR</span>
          <h1>{player.nombre}</h1>
          <p>
            {[player.posicion, player.nacionalidad, player.fecha_nacimiento]
              .filter(Boolean)
              .join(" · ") || "Ficha en construcción"}
          </p>
        </div>
      </section>

      <section className="p-player-facts">
        <article>
          <small>PARTIDOS EN ARCHIVO</small>
          <strong>{appearances.length}</strong>
        </article>
        <article>
          <small>EVENTOS REGISTRADOS</small>
          <strong>{events.length}</strong>
        </article>
      </section>

      <section className="p-section">
        <div className="p-section-head">
          <div>
            <span className="p-kicker">APARICIONES</span>
            <h2>Partidos conectados.</h2>
          </div>
          <span>{appearances.length}</span>
        </div>
        {appearances.length ? (
          <div className="p-match-list">
            {appearances.map((match) => (
              <MatchCard key={match.id} match={match} navigate={navigate} />
            ))}
          </div>
        ) : (
          <EmptyPublic title="Sin apariciones registradas">
            La profundidad está disponible cuando los datos también lo están.
          </EmptyPublic>
        )}
      </section>
    </main>
  );
}

export default function PublicApp() {
  const demo = new URLSearchParams(window.location.search).get("demo") === "1";
  const [route, setRoute] = useState(() =>
    routeFromPath(window.location.pathname),
  );
  const [matches, setMatches] = useState([]);
  const [competitions, setCompetitions] = useState([]);
  const [teams, setTeams] = useState([]);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let current = true;
    const controller = new AbortController();
    const request = demo
      ? import("./demoData").then(({ demoData: d }) => [
          d.matches,
          d.competitions,
          d.teams,
          d.players,
        ])
      : Promise.all([
          apiCollection("/public/partidos/", { signal: controller.signal }),
          apiCollection("/public/competiciones/", {
            signal: controller.signal,
          }),
          apiCollection("/public/equipos/", { signal: controller.signal }),
          apiCollection("/public/jugadores/", { signal: controller.signal }),
        ]);
    request
      .then(([matchData, competitionData, teamData, playerData]) => {
        if (!current) return;
        setMatches(matchData);
        setCompetitions(competitionData);
        setTeams(teamData);
        setPlayers(playerData);
      })
      .catch(() => {
        if (current)
          setLoadError(
            "No pudimos conectar con el servidor local. Comprueba que la API esté en marcha e inténtalo de nuevo.",
          );
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [demo, attempt]);

  useEffect(() => {
    const titles = {
      home: "El fútbol, conectado",
      matches: "Partidos",
      teams: "Equipos",
      competitions: "Competiciones",
      match: "El partido",
      team: "El equipo",
      competition: "La competición",
      player: "El jugador",
    };
    document.title = `ONCE · ${titles[route.type] || "Explorar"}${demo ? " · Demo" : ""}`;
  }, [route.type, demo]);

  useEffect(() => {
    const onPopState = () =>
      runViewTransition(() =>
        setRoute(routeFromPath(window.location.pathname)),
      );
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (type, id) => {
    const path = publicPath(type, id);
    if (path === window.location.pathname) return;
    window.history.pushState({}, "", `${path}${demo ? "?demo=1" : ""}`);
    runViewTransition(() => setRoute(routeFromPath(path)));
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  const selected = useMemo(() => {
    if (route.type === "team")
      return teams.find((item) => item.id === route.id);
    if (route.type === "competition")
      return competitions.find((item) => item.id === route.id);
    if (route.type === "player")
      return players.find((item) => item.id === route.id);
    return null;
  }, [route, teams, competitions, players]);

  if (loading) {
    return (
      <PublicShell navigate={navigate} route={route} demo={demo}>
        <main
          className="p-loading"
          id="public-content"
          tabIndex={-1}
          aria-busy="true"
        >
          <span className="p-loader" />
          <p>Abriendo el archivo del juego…</p>
        </main>
      </PublicShell>
    );
  }

  if (loadError) {
    return (
      <PublicShell navigate={navigate} route={route} demo={demo}>
        <main className="p-detail" id="public-content" tabIndex={-1}>
          <EmptyPublic title="El archivo no respondió">{loadError}</EmptyPublic>
          <div className="once-error-actions">
            <button
              className="once-button"
              onClick={() => {
                setLoading(true);
                setLoadError("");
                setAttempt((value) => value + 1);
              }}
            >
              Volver a intentar <Icon name="refresh" />
            </button>
            <a className="once-text-link" href="/explore?demo=1">
              Explorar la demostración <Icon name="arrow" />
            </a>
          </div>
        </main>
      </PublicShell>
    );
  }

  return (
    <PublicShell
      navigate={navigate}
      route={route}
      demo={demo}
      searchData={{ teams, competitions, players, matches }}
    >
      {route.type === "home" && (
        <ExploreHome
          matches={matches}
          competitions={competitions}
          teams={teams}
          navigate={navigate}
          demo={demo}
        />
      )}
      {route.type === "matches" && (
        <main id="public-content" tabIndex={-1}>
          <MatchExplorer
            matches={matches}
            competitions={competitions}
            navigate={navigate}
            full
          />
        </main>
      )}
      {route.type === "teams" && (
        <main id="public-content" tabIndex={-1}>
          <EntityExplorer
            key="teams"
            kind="team"
            entities={teams}
            navigate={navigate}
          />
        </main>
      )}
      {route.type === "competitions" && (
        <main id="public-content" tabIndex={-1}>
          <EntityExplorer
            key="competitions"
            kind="competition"
            entities={competitions}
            navigate={navigate}
          />
        </main>
      )}
      {route.type === "match" && (
        <MatchDetail
          match={matches.find((item) => item.id === route.id)}
          players={players}
          navigate={navigate}
        />
      )}
      {(route.type === "team" || route.type === "competition") && (
        <EntityDetail
          demo={demo}
          entity={selected}
          kind={route.type}
          matches={matches}
          navigate={navigate}
        />
      )}
      {route.type === "player" && (
        <PlayerDetail player={selected} matches={matches} navigate={navigate} />
      )}
    </PublicShell>
  );
}
