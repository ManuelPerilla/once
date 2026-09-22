import { ProviderConsole } from "./ProviderConsole";
import { MatchRow } from "../components/football/MatchRow";
import { Crest } from "../components/ui/Crest";
import { EmptyState } from "../components/ui/EmptyState";
import { Icon } from "../components/ui/Icon";

export function HomeView({
  ready,
  competitions,
  teams,
  summary,
  goCatalog,
  goEnrollments,
  setMatchFilter,
  changeSection,
  openCreate,
}) {
  const metrics = [
    {
      title: "Competiciones",
      value: competitions.length,
      caption: "Ligas y copas en tu catálogo",
      icon: "trophy",
      action: () => goCatalog("competiciones"),
    },
    {
      title: "Equipos",
      value: teams.length,
      caption: "Clubes y selecciones",
      icon: "shield",
      action: () => goCatalog("equipos"),
    },
    {
      title: "Por jugar",
      value: summary.scheduled.length,
      caption: "Partidos con estado programado",
      icon: "pitch",
      action: () => {
        setMatchFilter("programado");
        changeSection("arena");
      },
    },
    {
      title: "Sin matrícula",
      value: summary.unregistered.length,
      caption: "Equipos sin competición",
      icon: "link",
      warm: true,
      action: () => goEnrollments(true),
    },
  ];

  return (
    <>
      <div className="v-score-strip">
        <div className="v-score-label">
          <span className="v-eyebrow">TU UNIVERSO</span>
          <span>
            En cifras
            <Icon name="arrow" />
          </span>
        </div>

        <div className="v-metrics">
          {metrics.map((metric, index) => (
            <button
              key={metric.title}
              className={`v-metric ${metric.warm ? "v-metric-warm" : ""}`}
              onClick={metric.action}
            >
              <span className="v-metric-top">
                <span className="v-metric-number">0{index + 1} /</span>
                {metric.title}
                <span className="v-metric-icon">
                  <Icon name={metric.icon} />
                </span>
              </span>
              <strong>{ready ? metric.value : "—"}</strong>
              <small>{metric.caption}</small>
            </button>
          ))}
        </div>
      </div>

      {!ready ? (
        <div className="v-panel">
          <EmptyState title="Cargando tu información…">
            El resumen aparecerá cuando termine la consulta del catálogo.
          </EmptyState>
        </div>
      ) : (
        <div className="v-overview">
          <div className="v-panel v-match-board">
            <div className="v-panel-head">
              <div>
                <span className="v-eyebrow">01 / REGISTRO DE PARTIDOS</span>
                <h2>El juego, en marcha.</h2>
                <p>Los últimos encuentros que registraste, de un vistazo.</p>
              </div>
              <button
                className="v-text-btn"
                onClick={() => {
                  setMatchFilter("");
                  changeSection("arena");
                }}
              >
                Ver todos
                <Icon name="arrow" />
              </button>
            </div>

            {summary.recent.length ? (
              summary.recent.map((match) => (
                <MatchRow key={match.id} match={match} />
              ))
            ) : (
              <EmptyState
                title="Tu próximo partido empieza aquí"
                icon="pitch"
                action="Registrar primer partido"
                onAction={() => {
                  changeSection("arena");
                  openCreate("partidos");
                }}
              >
                Cuando registres encuentros, podrás seguir sus estados desde este inicio.
              </EmptyState>
            )}
          </div>

          <div className="v-stack">
            <div className="v-panel v-task-board">
              <div className="v-panel-head">
                <div>
                  <span className="v-eyebrow">02 / PUESTA A PUNTO</span>
                  <h2>El siguiente movimiento.</h2>
                  <p>Lo que necesita tu atención.</p>
                </div>
                <Icon name="clock" />
              </div>

              {summary.unregistered.length > 0 && (
                <button
                  className="v-attention"
                  onClick={() => goEnrollments(true)}
                >
                  <span className="v-attention-icon">
                    <Icon name="link" />
                  </span>
                  <span>
                    <strong>
                      {summary.unregistered.length}{" "}
                      {summary.unregistered.length === 1
                        ? "equipo sin matrícula"
                        : "equipos sin matrícula"}
                    </strong>
                    <small>Revisa en qué competiciones van a participar.</small>
                  </span>
                  <Icon name="arrow" />
                </button>
              )}

              {summary.incomplete.length > 0 && (
                <button
                  className="v-attention"
                  onClick={() => {
                    setMatchFilter("incompletos");
                    changeSection("arena");
                  }}
                >
                  <span className="v-attention-icon">
                    <Icon name="alert" />
                  </span>
                  <span>
                    <strong>
                      {summary.incomplete.length}{" "}
                      {summary.incomplete.length === 1
                        ? "partido incompleto"
                        : "partidos incompletos"}
                    </strong>
                    <small>Les falta un equipo o una competición.</small>
                  </span>
                  <Icon name="arrow" />
                </button>
              )}

              {!competitions.length && (
                <button
                  className="v-attention"
                  onClick={() => {
                    goCatalog("competiciones");
                    openCreate("competiciones");
                  }}
                >
                  <span className="v-attention-icon">
                    <Icon name="trophy" />
                  </span>
                  <span>
                    <strong>Crea tu primera competición</strong>
                    <small>El punto de partida de tus próximos encuentros.</small>
                  </span>
                  <Icon name="arrow" />
                </button>
              )}

              {!teams.length && (
                <button
                  className="v-attention"
                  onClick={() => {
                    goCatalog("equipos");
                    openCreate("equipos");
                  }}
                >
                  <span className="v-attention-icon">
                    <Icon name="shield" />
                  </span>
                  <span>
                    <strong>Añade los primeros equipos</strong>
                    <small>Construye el catálogo de clubes y selecciones.</small>
                  </span>
                  <Icon name="arrow" />
                </button>
              )}

              {!summary.unregistered.length &&
                !summary.incomplete.length &&
                competitions.length > 0 &&
                teams.length > 0 && (
                  <div className="v-pending-clear">
                    <Icon name="check" />
                    Matrículas y referencias de partidos al día.
                  </div>
                )}
            </div>

            <div className="v-panel">
              <div className="v-panel-head">
                <div>
                  <span className="v-eyebrow">03 / ECOSISTEMA</span>
                  <h2>Territorio de juego.</h2>
                  <p>Equipos matriculados en cada torneo.</p>
                </div>
              </div>

              {summary.rosters.length ? (
                summary.rosters.slice(0, 3).map((competition) => (
                  <div key={competition.id} className="v-roster-row">
                    <Crest
                      small
                      src={competition.logo}
                      name={competition.nombre}
                    />
                    <div>
                      <strong>{competition.nombre}</strong>
                      <small>{competition.pais}</small>
                    </div>
                    <span>
                      {competition.teamCount}{" "}
                      {competition.teamCount === 1 ? "equipo" : "equipos"}
                    </span>
                  </div>
                ))
              ) : (
                <EmptyState title="El mapa está por comenzar" icon="globe">
                  Tus competiciones aparecerán aquí.
                </EmptyState>
              )}
            </div>
          </div>
        </div>
      )}

      <ProviderConsole />

      <div className="v-quick-actions">
        <button
          className="v-quick-action"
          onClick={() => {
            goCatalog("equipos");
            openCreate("equipos");
          }}
        >
          <Icon name="shield" />
          <span>
            <small>01 / AMPLÍA EL CATÁLOGO</small>
            <strong>Añadir equipo</strong>
            <em>Un nuevo escudo entra en juego.</em>
          </span>
          <Icon name="arrow" />
        </button>

        <button className="v-quick-action" onClick={() => goEnrollments()}>
          <Icon name="link" />
          <span>
            <small>02 / CONECTA LAS PIEZAS</small>
            <strong>Gestionar matrículas</strong>
            <em>Cada equipo, en su competición.</em>
          </span>
          <Icon name="arrow" />
        </button>

        <button
          className="v-quick-action"
          onClick={() => {
            changeSection("arena");
            openCreate("partidos");
          }}
        >
          <Icon name="pitch" />
          <span>
            <small>03 / ABRE LA CANCHA</small>
            <strong>Registrar partido</strong>
            <em>El próximo encuentro empieza aquí.</em>
          </span>
          <Icon name="arrow" />
        </button>
      </div>
    </>
  );
}
