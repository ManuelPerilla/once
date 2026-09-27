import { useEffect, useMemo, useState } from "react";
import { apiCollection, apiRequest } from "../api";
import { useLiveUpdates } from "../lib/useLiveUpdates";
import { Brand } from "../components/ui/Brand";
import { Crest } from "../components/ui/Crest";
import { CrestCredits } from "../components/ui/CrestCredits";
import { Icon } from "../components/ui/Icon";
import { Status } from "../components/ui/Status";
import { MatchSource } from "../components/football/MatchSource.jsx";
import { runViewTransition } from "../lib/viewTransition";
import { CompetitionFlow } from "./components/CompetitionFlow";
import { ConnectionGraph } from "./components/ConnectionGraph";
import { FormRibbon } from "./components/FormRibbon";
import { LineupBoard } from "./components/LineupBoard";
import { MatchTimeline } from "./components/MatchTimeline";
import { Pitch } from "./components/Pitch";
import { SearchBox } from "./components/SearchBox";
import { StandingsTable } from "./components/StandingsTable";
import { DetailSections } from "./components/DetailSections";
import { HistoryFacts } from "./components/HistoryFacts";
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
            ["home", "Descubrir", "home", "Descubrir"],
            ["matches", "Partidos", "pitch", "Partidos"],
            ["competitions", "Competiciones", "trophy", "Torneos"],
            ["teams", "Equipos", "shield", "Equipos"],
          ].map(([page, label, icon, compactLabel]) => (
            <button
              key={page}
              aria-label={label}
              aria-current={
                route.type === page ||
                (page === "matches" && route.type === "match") ||
                (page === "teams" && route.type === "team") ||
                (page === "competitions" && route.type === "competition")
                  ? "page"
                  : undefined
              }
              onClick={() => navigate(page)}
            >
              <Icon name={icon} />
              <span className="once-nav-wide-label">{label}</span>
              <span className="once-nav-compact-label" aria-hidden="true">
                {compactLabel}
              </span>
            </button>
          ))}
        </nav>
        <SearchBox
          teams={searchData.teams || []}
          competitions={searchData.competitions || []}
          players={searchData.players || []}
          matches={searchData.matches || []}
          remote={!demo}
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
        <div className="once-footer-credits">
          <CrestCredits />
        </div>
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
            : `${match.marcador_local ?? "—"} : ${match.marcador_visitante ?? "—"}`}
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
        <MatchSource source={match.data_source} />
      </span>
      <strong>
        {match.equipo_local?.nombre || "Por confirmar"}
        <b>
          {match.estado === "programado"
            ? "VS"
            : `${match.marcador_local ?? "—"} : ${match.marcador_visitante ?? "—"}`}
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
  const [section, setSection] = useState("summary");
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
      <button className="p-back" onClick={() => navigate("matches")}>
        <Icon name="arrow" /> Volver a partidos
      </button>
      <section className="p-match-hero">
        <span className="p-kicker">
          {match.competicion?.nombre || "PARTIDO"}
        </span>
        <MatchSource source={match.data_source} detailed />
        <Score match={match} />
        <MatchMeta match={match} />
        <span className="p-record">
          REGISTRO #{String(match.id).padStart(4, "0")}
        </span>
      </section>
      <DetailSections
        label="Secciones del partido"
        current={section}
        onChange={setSection}
        sections={[
          ["summary", "Resumen"],
          ["timeline", "Cronología", match.eventos?.length || 0],
          ["lineups", "Alineaciones", match.alineaciones?.length || 0],
          ["connections", "Conexiones"],
        ]}
      />
      {section === "connections" && (
        <>
          <section className="p-match-context">
            <Pitch />
            <div className="p-context-copy">
              <span className="p-kicker">SIGUE EL HILO</span>
              <h2>Este partido conecta.</h2>
              <div className="p-connection-list">
                {match.equipo_local && (
                  <button
                    onClick={() => navigate("team", match.equipo_local.id)}
                  >
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
                    onClick={() =>
                      navigate("competition", match.competicion.id)
                    }
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
        </>
      )}
      {section === "summary" && (
        <>
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
                            stats.tiros_puerta_local +
                              stats.tiros_puerta_visitante,
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
          <p className="once-detail-note">
            Las estadísticas corresponden únicamente a este partido. Consulta
            sus jugadas y jugadores en Cronología y Alineaciones.
          </p>
        </>
      )}
      {section === "timeline" &&
        (match.eventos?.length ? (
          <MatchTimeline
            events={match.eventos}
            players={players}
            match={match}
            navigate={navigate}
          />
        ) : (
          <EmptyPublic title="Sin jugadas registradas">
            La cronología aparecerá cuando existan eventos de este partido.
          </EmptyPublic>
        ))}
      {section === "lineups" &&
        (match.alineaciones?.some((item) => item.titular) ? (
          <LineupBoard
            lineups={match.alineaciones}
            players={players}
            match={match}
            navigate={navigate}
          />
        ) : (
          <EmptyPublic title="Alineación por confirmar">
            Todavía no hay titulares registrados para este partido.
          </EmptyPublic>
        ))}
    </main>
  );
}

function EntityDetail({
  entity,
  kind,
  matches,
  navigate,
  demo,
  revision = 0,
  matchTotal = 0,
}) {
  const [section, setSection] = useState("matches");
  const seasons = [...(entity?.temporadas || [])].sort(
    (a, b) => Number(b.activa) - Number(a.activa) || b.id - a.id,
  );
  const [seasonChoice, setSeasonChoice] = useState(null);
  const season = seasonChoice ?? (seasons[0] ? String(seasons[0].id) : "");
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

  const scopedMatches = related.filter(
    (match) =>
      !season ||
      (season === "unassigned"
        ? !match.temporada_id
        : String(match.temporada_id) === season),
  );
  const selectedSeason = seasons.find((item) => String(item.id) === season);
  const relatedCompetitions =
    kind === "competition"
      ? [entity]
      : [
          ...new Map(
            related
              .filter((match) => match.competicion)
              .map((match) => [match.competicion.id, match.competicion]),
          ).values(),
        ];

  return (
    <main className="p-detail" id="public-content" tabIndex={-1}>
      <button
        className="p-back"
        onClick={() => navigate(kind === "team" ? "teams" : "competitions")}
      >
        <Icon name="arrow" />{" "}
        {kind === "team" ? "Volver a equipos" : "Volver a competiciones"}
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
      {kind === "competition" && seasons.length > 0 && (
        <div className="once-detail-context">
          <label className="once-select">
            <span>Temporada</span>
            <select
              aria-label="Temporada de la competición"
              value={season}
              onChange={(event) => setSeasonChoice(event.target.value)}
            >
              {seasons.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nombre}
                  {item.activa ? " · En curso" : ""}
                </option>
              ))}
              <option value="unassigned">Sin temporada asignada</option>
            </select>
          </label>
          <p>
            Partidos, clasificación y fases comparten esta selección.{" "}
            {demo
              ? `${scopedMatches.length} de ${related.length} partidos.`
              : "Consulta el listado para ver todos los encuentros de esta edición."}
          </p>
        </div>
      )}
      <DetailSections
        label={
          kind === "team"
            ? "Secciones del equipo"
            : "Secciones de la competición"
        }
        current={section}
        onChange={setSection}
        sections={
          kind === "team"
            ? [
                ["matches", "Partidos", demo ? related.length : matchTotal],
                ["form", "Forma reciente"],
                ["history", "Historia"],
                [
                  "competitions",
                  "Competiciones",
                  entity.competiciones?.length || 0,
                ],
              ]
            : [
                [
                  "matches",
                  "Partidos",
                  demo ? scopedMatches.length : undefined,
                ],
                ["standings", "Clasificación"],
                ["history", "Historia"],
                ["phases", "Fases"],
                ["seasons", "Temporadas", seasons.length],
              ]
        }
      />

      {section === "history" && (
        <HistoryFacts type={kind} id={entity.id} demo={demo} />
      )}
      {kind === "team" && section === "form" && (
        <section className="p-form-section">
          <span className="p-kicker">FORMA RECIENTE</span>
          {!demo && (
            <p className="once-results-count">
              Resultados disponibles en los últimos 30 encuentros consultados.
            </p>
          )}
          <FormRibbon
            matches={matches}
            teamId={entity.id}
            navigate={navigate}
          />
        </section>
      )}

      {kind === "competition" &&
        section === "seasons" &&
        (seasons.length ? (
          <section className="p-season-section">
            <span className="p-kicker">EDICIONES</span>
            <div className="p-season-rail">
              {seasons.map((season) => (
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
                  <button
                    className="once-text-link"
                    onClick={() => {
                      setSeasonChoice(String(season.id));
                      setSection("matches");
                    }}
                  >
                    Ver partidos <Icon name="arrow" />
                  </button>
                </article>
              ))}
            </div>
          </section>
        ) : (
          <EmptyPublic title="Sin temporadas registradas">
            Las ediciones aparecerán cuando se añadan a esta competición.
          </EmptyPublic>
        ))}

      {kind === "competition" &&
        section === "standings" &&
        (demo ? (
          <EmptyPublic title="Clasificación no incluida en la demo">
            Esta vista se calcula con los resultados guardados en tu
            instalación.
          </EmptyPublic>
        ) : season === "unassigned" ? (
          <EmptyPublic title="Elige una temporada para ver la tabla">
            Los partidos sin temporada permanecen separados para no mezclar
            resultados de distintas ediciones.
          </EmptyPublic>
        ) : (
          <StandingsTable competition={entity} season={selectedSeason} />
        ))}
      {kind === "competition" &&
        section === "phases" &&
        (scopedMatches.some((match) => match.fase?.id) ? (
          <>
            <p className="once-results-count">
              {demo
                ? ""
                : "Vista de los últimos 30 partidos. El listado permite recorrer el archivo completo."}
            </p>
            <CompetitionFlow matches={scopedMatches} navigate={navigate} />
          </>
        ) : (
          <EmptyPublic title="Sin fases con partidos">
            Las fases aparecerán cuando haya encuentros asociados en esta
            selección.
          </EmptyPublic>
        ))}
      {kind === "team" && section === "competitions" && (
        <section className="p-section">
          <div className="p-section-head">
            <h2>Competiciones del equipo.</h2>
          </div>
          {entity.competiciones?.length ? (
            <div className="p-connection-list">
              {entity.competiciones.map((item) => (
                <button
                  key={item.id}
                  onClick={() => navigate("competition", item.id)}
                >
                  <Crest small src={item.logo} name={item.nombre} />
                  <span>
                    <small>COMPETICIÓN</small>
                    <strong>{item.nombre}</strong>
                  </span>
                  <Icon name="arrow" />
                </button>
              ))}
            </div>
          ) : (
            <EmptyPublic title="Sin competiciones vinculadas">
              Este equipo todavía no tiene competiciones asociadas en el
              catálogo.
            </EmptyPublic>
          )}
        </section>
      )}
      {section === "matches" && (
        <MatchExplorer
          key={season}
          matches={scopedMatches}
          competitions={relatedCompetitions}
          navigate={navigate}
          embedded
          server={!demo}
          revision={revision}
          scope={{
            ...(kind === "team"
              ? { team_id: entity.id }
              : { competition_id: entity.id }),
            ...(season ? { season_id: season } : {}),
          }}
          heading={
            kind === "team"
              ? "Los partidos del equipo."
              : "Los partidos de la competición."
          }
        />
      )}
    </main>
  );
}

function PlayerDetail({
  player,
  matches,
  navigate,
  demo = false,
  summary,
  revision = 0,
}) {
  const [section, setSection] = useState("appearances");
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

      {!demo ? (
        <>
          <section className="p-player-facts">
            {[
              [summary?.appearances ?? 0, "APARICIONES REGISTRADAS"],
              [summary?.goals ?? 0, "GOLES REGISTRADOS"],
              [summary?.assists ?? 0, "ASISTENCIAS REGISTRADAS"],
            ].map(([count, label]) => (
              <article key={label}>
                <small>{label}</small>
                <strong>{count}</strong>
              </article>
            ))}
          </section>
          <p className="once-results-count">
            Cifras de los partidos y eventos guardados en ONCE. No representan
            una trayectoria completa si la fuente está incompleta.
          </p>
          <MatchExplorer
            matches={matches}
            competitions={[]}
            navigate={navigate}
            embedded
            server
            scope={{ player_id: player.id }}
            revision={revision}
            heading="Partidos conectados."
          />
        </>
      ) : (
        <>
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
          <DetailSections
            label="Secciones del jugador"
            current={section}
            onChange={setSection}
            sections={[
              ["appearances", "Apariciones", appearances.length],
              ["events", "Jugadas", events.length],
            ]}
          />
          {section === "appearances" && (
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
                    <MatchCard
                      key={match.id}
                      match={match}
                      navigate={navigate}
                    />
                  ))}
                </div>
              ) : (
                <EmptyPublic title="Sin apariciones registradas">
                  La profundidad está disponible cuando los datos también lo
                  están.
                </EmptyPublic>
              )}
            </section>
          )}
          {section === "events" && (
            <section className="p-section">
              <div className="p-section-head">
                <h2>Jugadas del jugador.</h2>
              </div>
              {events.length ? (
                <div className="once-player-events">
                  {events.map((event) => (
                    <button
                      key={`${event.match.id}-${event.id}`}
                      onClick={() => navigate("match", event.match.id)}
                    >
                      <span>
                        <small>
                          {event.match.equipo_local?.nombre} ·{" "}
                          {event.match.equipo_visitante?.nombre}
                        </small>
                        <strong>
                          {event.minuto}′ ·{" "}
                          {event.asistente_id === player.id
                            ? "Asistencia"
                            : event.tipo}
                        </strong>
                      </span>
                      <Icon name="arrow" />
                    </button>
                  ))}
                </div>
              ) : (
                <EmptyPublic title="Sin jugadas registradas">
                  Las acciones aparecerán cuando este jugador figure en los
                  eventos de un partido.
                </EmptyPublic>
              )}
            </section>
          )}
        </>
      )}
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
  const [totals, setTotals] = useState({});
  const [playerSummary, setPlayerSummary] = useState(null);
  const live = useLiveUpdates(!demo);

  useEffect(() => {
    let current = true;
    const controller = new AbortController();
    const request = demo
      ? import("./demoData").then(({ demoData: d }) => [
          d.matches,
          d.competitions,
          d.teams,
          d.players,
          { matches: d.matches.length, teams: d.teams.length },
        ])
      : (async () => {
          const options = { signal: controller.signal };
          const matchQuery = new URLSearchParams({
            page: "1",
            page_size: route.type === "home" ? "6" : "30",
            sort: "newest",
          });
          if (route.type === "team") matchQuery.set("team_id", route.id);
          if (route.type === "competition")
            matchQuery.set("competition_id", route.id);
          if (route.type === "player") matchQuery.set("player_id", route.id);
          const [matchResult, competitionData, teamResult, playerData] =
            await Promise.all([
              route.type === "match"
                ? apiRequest(`/public/partidos/${route.id}`, options).then(
                    (match) => ({ items: [match], total: 1 }),
                  )
                : ["home", "team", "competition", "player"].includes(route.type)
                  ? apiRequest(`/public/partidos/page?${matchQuery}`, options)
                  : Promise.resolve({ items: [], total: 0 }),
              apiCollection("/public/competiciones/", {
                signal: controller.signal,
              }),
              route.type === "team"
                ? apiRequest(`/public/equipos/${route.id}`, options).then(
                    (team) => ({ items: [team], total: 1 }),
                  )
                : route.type === "home"
                  ? apiRequest(
                      "/public/equipos/page?page=1&page_size=6",
                      options,
                    )
                  : Promise.resolve({ items: [], total: 0 }),
              route.type === "player"
                ? Promise.all([
                    apiRequest(`/public/jugadores/${route.id}`, options),
                    apiRequest(
                      `/public/jugadores/${route.id}/summary`,
                      options,
                    ),
                  ])
                : Promise.resolve([]),
            ]);
          return [
            matchResult.items,
            competitionData,
            teamResult.items,
            playerData.length ? [playerData[0]] : [],
            { matches: matchResult.total, teams: teamResult.total },
            playerData[1] || null,
          ];
        })();
    request
      .then(
        ([
          matchData,
          competitionData,
          teamData,
          playerData,
          counts,
          summary,
        ]) => {
          if (!current) return;
          setMatches(matchData);
          setCompetitions(competitionData);
          setTeams(teamData);
          setPlayers(playerData);
          setTotals(counts || {});
          setPlayerSummary(summary);
          setLoadError("");
        },
      )
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
  }, [demo, attempt, route.type, route.id, live.revision]);

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
    if (!demo) setLoading(true);
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
      {!demo && (
        <div className="once-live-status" role="status">
          <i data-connected={live.connected || undefined} />
          {live.connected
            ? "Conectado a tu archivo local"
            : "Actualizaciones de pantalla desconectadas"}
          <span>
            La frescura de cada dato depende de su fuente.
            {live.checkedAt
              ? ` Último cambio recibido: ${live.checkedAt.toLocaleTimeString("es-CO")}.`
              : ""}
          </span>
        </div>
      )}
      {route.type === "home" && (
        <ExploreHome
          matches={matches}
          competitions={competitions}
          teams={teams}
          navigate={navigate}
          demo={demo}
          totals={totals}
          revision={live.revision}
        />
      )}
      {route.type === "matches" && (
        <main id="public-content" tabIndex={-1}>
          <MatchExplorer
            matches={matches}
            competitions={competitions}
            navigate={navigate}
            full
            server={!demo}
            revision={live.revision}
          />
        </main>
      )}
      {route.type === "teams" && (
        <main id="public-content" tabIndex={-1}>
          <EntityExplorer
            key="teams"
            kind="team"
            entities={teams}
            server={!demo}
            revision={live.revision}
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
          key={route.id}
          match={matches.find((item) => item.id === route.id)}
          players={players}
          navigate={navigate}
        />
      )}
      {(route.type === "team" || route.type === "competition") && (
        <EntityDetail
          key={`${route.type}-${route.id}`}
          demo={demo}
          entity={selected}
          kind={route.type}
          matches={matches}
          navigate={navigate}
          revision={live.revision}
          matchTotal={totals.matches}
        />
      )}
      {route.type === "player" && (
        <PlayerDetail
          key={route.id}
          player={selected}
          matches={matches}
          navigate={navigate}
          demo={demo}
          summary={playerSummary}
          revision={live.revision}
        />
      )}
    </PublicShell>
  );
}
