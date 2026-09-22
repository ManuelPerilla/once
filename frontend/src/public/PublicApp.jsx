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
import "./public.css";

function routeFromPath(pathname) {
  const parts = pathname.replace(/^\/explore\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "partidos" && parts[1]) return { type: "match", id: Number(parts[1]) };
  if (parts[0] === "equipos" && parts[1]) return { type: "team", id: Number(parts[1]) };
  if (parts[0] === "competiciones" && parts[1]) return { type: "competition", id: Number(parts[1]) };
  if (parts[0] === "jugadores" && parts[1]) return { type: "player", id: Number(parts[1]) };
  return { type: "home" };
}

function publicPath(type, id) {
  if (type === "home") return "/explore";
  const plural = {
    match: "partidos",
    team: "equipos",
    competition: "competiciones",
    player: "jugadores",
  }[type];
  return `/explore/${plural}/${id}`;
}

function formatMatchDate(value) {
  if (!value) return null;
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function PublicShell({ children, navigate, searchData = {} }) {
  return (
    <div className="p-app">
      <header className="p-header">
        <button className="p-brand-button" onClick={() => navigate("home")}>
          <Brand />
        </button>
        <span className="p-header-line">FÚTBOL · CONTEXTO · CONEXIONES</span>
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
      {children}
      <footer className="p-footer">
        <Brand />
        <span>VÉRTICE · EL JUEGO TIENE MÁS DE UNA ENTRADA.</span>
      </footer>
    </div>
  );
}

function Score({ match }) {
  const scheduled = match.estado === "programado";
  return (
    <div className="p-score">
      <div className="p-team" data-side="home">
        <Crest src={match.equipo_local?.logo} name={match.equipo_local?.nombre} />
        <strong>{match.equipo_local?.nombre || "Equipo por confirmar"}</strong>
      </div>
      <div className="p-score-center">
        <Status value={match.estado} />
        <strong>
          {scheduled ? "VS" : `${match.marcador_local} : ${match.marcador_visitante}`}
        </strong>
      </div>
      <div className="p-team" data-side="away">
        <Crest src={match.equipo_visitante?.logo} name={match.equipo_visitante?.nombre} />
        <strong>{match.equipo_visitante?.nombre || "Equipo por confirmar"}</strong>
      </div>
    </div>
  );
}

function EmptyPublic({ title, children }) {
  return (
    <div className="p-empty">
      <span aria-hidden="true">V / 00</span>
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

function Home({ matches, competitions, teams, navigate }) {
  const featured = [...matches].sort((a, b) => {
    if (a.fecha && b.fecha) return new Date(b.fecha) - new Date(a.fecha);
    return b.id - a.id;
  })[0];

  return (
    <main>
      <section className="p-home-hero">
        <div className="p-home-copy">
          <span className="p-kicker">EL FÚTBOL NO TERMINA EN EL MARCADOR</span>
          <h1>
            Sigue
            <br />
            <em>el hilo.</em>
          </h1>
          <p>
            Entra por un partido y continúa hacia los equipos, las competiciones,
            los jugadores y las conexiones que lo explican.
          </p>
        </div>
        <div className="p-orbit" aria-hidden="true">
          <span className="p-orbit-ball" />
          <span className="p-orbit-ring p-orbit-ring-a" />
          <span className="p-orbit-ring p-orbit-ring-b" />
          <span className="p-orbit-dot p-orbit-dot-a" />
          <span className="p-orbit-dot p-orbit-dot-b" />
          <small>V / FOOTBALL GRAPH</small>
        </div>
      </section>

      <section className="p-section">
        <div className="p-section-head">
          <div>
            <span className="p-kicker">01 / ENCUENTROS</span>
            <h2>Una puerta de entrada.</h2>
          </div>
          <span>{matches.length} registrados</span>
        </div>
        {featured ? (
          <button
            className="p-featured-match"
            onClick={() => navigate("match", featured.id)}
          >
            <span className="p-featured-meta">
              {featured.competicion?.nombre || "Sin competición"}
              {featured.fecha && <small>{formatMatchDate(featured.fecha)}</small>}
            </span>
            <Score match={featured} />
            <span className="p-open">
              Abrir contexto <Icon name="arrow" />
            </span>
          </button>
        ) : (
          <EmptyPublic title="Todavía no hay partidos publicados">
            Cuando el archivo tenga encuentros, aparecerán aquí sin inventar
            actividad ni resultados.
          </EmptyPublic>
        )}

        {matches.length > 1 && (
          <div className="p-match-list">
            {[...matches]
              .sort((a, b) => b.id - a.id)
              .slice(1, 7)
              .map((match) => (
                <MatchCard key={match.id} match={match} navigate={navigate} />
              ))}
          </div>
        )}
      </section>

      <section className="p-index-grid">
        <div className="p-index-panel">
          <span className="p-kicker">02 / COMPETICIONES</span>
          <h2>Territorios del juego.</h2>
          {competitions.slice(0, 6).map((competition, index) => (
            <button
              key={competition.id}
              onClick={() => navigate("competition", competition.id)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <Crest small src={competition.logo} name={competition.nombre} />
              <strong>{competition.nombre}</strong>
              <small>{competition.pais}</small>
              <Icon name="arrow" />
            </button>
          ))}
        </div>
        <div className="p-index-panel">
          <span className="p-kicker">03 / EQUIPOS</span>
          <h2>Identidades conectadas.</h2>
          {teams.slice(0, 6).map((team, index) => (
            <button key={team.id} onClick={() => navigate("team", team.id)}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <Crest small src={team.logo} name={team.nombre} />
              <strong>{team.nombre}</strong>
              <small>{team.pais}</small>
              <Icon name="arrow" />
            </button>
          ))}
        </div>
      </section>
    </main>
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
        ? [match.estadio.nombre, match.estadio.ciudad].filter(Boolean).join(" · ")
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
      <main className="p-detail">
        <EmptyPublic title="Ese partido no está disponible">
          Puede que haya sido eliminado o que todavía no forme parte del archivo público.
        </EmptyPublic>
      </main>
    );
  }

  const stats = match.estadisticas?.[0];

  return (
    <main className="p-detail">
      <button className="p-back" onClick={() => navigate("home")}>
        <Icon name="arrow" /> Volver al archivo
      </button>
      <section className="p-match-hero">
        <span className="p-kicker">{match.competicion?.nombre || "PARTIDO"}</span>
        <Score match={match} />
        <MatchMeta match={match} />
        <span className="p-record">REGISTRO #{String(match.id).padStart(4, "0")}</span>
      </section>

      <section className="p-match-context">
        <Pitch />
        <div className="p-context-copy">
          <span className="p-kicker">SIGUE EL HILO</span>
          <h2>Este partido conecta.</h2>
          <div className="p-connection-list">
            {match.equipo_local && (
              <button onClick={() => navigate("team", match.equipo_local.id)}>
                <Crest small src={match.equipo_local.logo} name={match.equipo_local.nombre} />
                <span>
                  <small>EQUIPO LOCAL</small>
                  <strong>{match.equipo_local.nombre}</strong>
                </span>
                <Icon name="arrow" />
              </button>
            )}
            {match.competicion && (
              <button onClick={() => navigate("competition", match.competicion.id)}>
                <Icon name="trophy" />
                <span>
                  <small>COMPETICIÓN</small>
                  <strong>{match.competicion.nombre}</strong>
                </span>
                <Icon name="arrow" />
              </button>
            )}
            {match.equipo_visitante && (
              <button onClick={() => navigate("team", match.equipo_visitante.id)}>
                <Crest small src={match.equipo_visitante.logo} name={match.equipo_visitante.nombre} />
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
                      Math.max(1, stats.tiros_puerta_local + stats.tiros_puerta_visitante)) *
                      100,
                  )}%`,
                }}
              />
              <strong>{stats.tiros_puerta_visitante}</strong>
            </article>
          </div>
        ) : (
          <p className="p-data-empty">
            Este encuentro todavía no tiene estadísticas registradas. VÉRTICE
            prefiere dejar el espacio vacío antes que rellenarlo con datos dudosos.
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

function EntityDetail({ entity, kind, matches, navigate }) {
  if (!entity) {
    return (
      <main className="p-detail">
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
            match.equipo_local_id === entity.id || match.equipo_visitante_id === entity.id,
        )
      : matches.filter((match) => match.competicion_id === entity.id);

  return (
    <main className="p-detail">
      <button className="p-back" onClick={() => navigate("home")}>
        <Icon name="arrow" /> Volver al archivo
      </button>
      <section className="p-entity-hero">
        <Crest src={entity.logo} name={entity.nombre} />
        <div>
          <span className="p-kicker">{kind === "team" ? "EQUIPO" : "COMPETICIÓN"}</span>
          <h1>{entity.nombre}</h1>
          <p>
            {entity.pais || "Ámbito sin registrar"}
            {entity.tipo ? ` · ${String(entity.tipo).replaceAll("_", " ")}` : ""}
          </p>
        </div>
      </section>

      {kind === "team" && (
        <section className="p-form-section">
          <span className="p-kicker">FORMA RECIENTE</span>
          <FormRibbon matches={matches} teamId={entity.id} navigate={navigate} />
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
                <article key={season.id} data-active={season.activa || undefined}>
                  <small>{season.activa ? "EN CURSO" : "TEMPORADA"}</small>
                  <strong>{season.nombre}</strong>
                  <span>
                    {[season.fecha_inicio, season.fecha_fin].filter(Boolean).join(" → ") ||
                      "Fechas por completar"}
                  </span>
                </article>
              ))}
          </div>
        </section>
      )}

      {kind === "competition" && (
        <>
          <StandingsTable competition={entity} />
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
      <main className="p-detail">
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
      .filter((event) => event.jugador_id === player.id || event.asistente_id === player.id)
      .map((event) => ({ ...event, match })),
  );

  return (
    <main className="p-detail">
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
  const [route, setRoute] = useState(() => routeFromPath(window.location.pathname));
  const [matches, setMatches] = useState([]);
  const [competitions, setCompetitions] = useState([]);
  const [teams, setTeams] = useState([]);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    Promise.all([
      apiCollection("/public/partidos/"),
      apiCollection("/public/competiciones/"),
      apiCollection("/public/equipos/"),
      apiCollection("/public/jugadores/"),
    ])
      .then(([matchData, competitionData, teamData, playerData]) => {
        setMatches(matchData);
        setCompetitions(competitionData);
        setTeams(teamData);
        setPlayers(playerData);
      })
      .catch(() => setLoadError("No pudimos abrir el archivo público."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onPopState = () =>
      runViewTransition(() => setRoute(routeFromPath(window.location.pathname)));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (type, id) => {
    const path = publicPath(type, id);
    if (path === window.location.pathname) return;
    window.history.pushState({}, "", path);
    runViewTransition(() => setRoute(routeFromPath(path)));
    window.scrollTo({ top: 0, behavior: "auto" });
  };

  const selected = useMemo(() => {
    if (route.type === "team") return teams.find((item) => item.id === route.id);
    if (route.type === "competition") return competitions.find((item) => item.id === route.id);
    if (route.type === "player") return players.find((item) => item.id === route.id);
    return null;
  }, [route, teams, competitions, players]);

  if (loading) {
    return (
      <PublicShell navigate={navigate}>
        <main className="p-loading">
          <span className="p-loader" />
          <p>Abriendo el archivo del juego…</p>
        </main>
      </PublicShell>
    );
  }

  if (loadError) {
    return (
      <PublicShell navigate={navigate}>
        <main className="p-detail">
          <EmptyPublic title="El archivo no respondió">{loadError}</EmptyPublic>
        </main>
      </PublicShell>
    );
  }

  return (
    <PublicShell
      navigate={navigate}
      searchData={{ teams, competitions, players, matches }}
    >
      {route.type === "home" && (
        <Home
          matches={matches}
          competitions={competitions}
          teams={teams}
          navigate={navigate}
        />
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
