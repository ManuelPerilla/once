import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Field, Icon } from "../AdminUI";
import {
  accountLabel,
  coverageLabels,
  sortedSeasons,
} from "./footballConnection";
import { humanDate, remainingBudget } from "./automation";

const connectionPath = "/providers/api-football";

function CompetitionChoice({
  competition,
  allowedSeasons,
  selected,
  onSelect,
  disabled,
}) {
  const seasons = sortedSeasons(competition.seasons, allowedSeasons);
  const [year, setYear] = useState(() => seasons[0]?.year || "");
  const season = seasons.find((item) => item.year === Number(selected || year));
  const features = coverageLabels(season?.coverage);
  const name = `${competition.name} · ${competition.country || "Colombia"}`;
  return (
    <article className="once-football-choice" data-selected={Boolean(selected)}>
      <label className="once-football-check">
        <input
          type="checkbox"
          checked={Boolean(selected)}
          disabled={disabled || !seasons.length}
          onChange={(event) =>
            onSelect(event.target.checked ? Number(year) : null)
          }
        />
        <span>
          <strong>{competition.name}</strong>
          <small>{competition.country || "Colombia"}</small>
        </span>
      </label>
      <Field label={`Temporada de ${name}`}>
        <select
          value={selected || year}
          disabled={disabled || !seasons.length}
          onChange={(event) => {
            const next = Number(event.target.value);
            setYear(next);
            if (selected) onSelect(next);
          }}
        >
          {!seasons.length && (
            <option value="">
              Sin temporadas disponibles para esta cuenta
            </option>
          )}
          {seasons.map((item) => (
            <option key={item.year} value={item.year}>
              {item.year}
              {item.current ? " · Actual según la fuente" : ""}
            </option>
          ))}
        </select>
      </Field>
      <p className="once-automation-help">
        {features.length
          ? `Detalle anunciado: ${features.join(" · ")}.`
          : "La fuente no anuncia detalle adicional para esta temporada."}
      </p>
    </article>
  );
}

export function ApiFootballSetup({
  canConfigure,
  canOperate,
  active,
  globalMode,
  onChanged,
  onError,
}) {
  const [connection, setConnection] = useState(null);
  const [selected, setSelected] = useState({});
  const [includeDetails, setIncludeDetails] = useState(true);
  const [preparedIds, setPreparedIds] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const report = useCallback(
    (failure) => {
      setError(failure.message);
      if (failure.status === 401) onError(failure);
    },
    [onError],
  );
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    apiRequest(`${connectionPath}/connection`, { signal: controller.signal })
      .then(setConnection)
      .catch((failure) => {
        if (!controller.signal.aborted) report(failure);
      });
    return () => controller.abort();
  }, [active, report]);
  const run = async (operation, action) => {
    setBusy(operation);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (failure) {
      report(failure);
    } finally {
      setBusy("");
    }
  };
  const verified =
    connection?.state === "connected" && connection.account?.active === true;
  const allowedSeasons = connection?.account?.allowed_seasons;
  const selections = Object.entries(selected)
    .filter(([league, season]) =>
      sortedSeasons(
        connection?.competitions?.find(
          (competition) => competition.league_id === Number(league),
        )?.seasons,
        allowedSeasons,
      ).some((available) => available.year === season),
    )
    .map(([league, season]) => ({ league_id: Number(league), season }));
  const prepared =
    connection?.profiles?.filter((profile) =>
      preparedIds.includes(profile.id),
    ) || [];
  const readyIds = prepared
    .filter((profile) => profile.mode !== "automatic")
    .map((profile) => profile.id);
  return (
    <section
      className="once-football-setup v-panel"
      aria-labelledby="football-setup-title"
      aria-busy={Boolean(busy)}
    >
      <div className="once-football-heading">
        <div>
          <span className="v-eyebrow">API-FOOTBALL · COLOMBIA PRIMERO</span>
          <h3 id="football-setup-title">Conecta el juego real.</h3>
          <p>
            Comprueba tu cuenta, elige las competiciones y deja que ONCE
            organice sus actualizaciones.
          </p>
        </div>
        <span className="once-automation-pill">
          <Icon name={verified ? "check" : "link"} />
          {accountLabel(connection)}
        </span>
      </div>
      {error && (
        <p className="once-automation-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="once-automation-success" role="status">
          {message}
        </p>
      )}
      {connection?.last_error && !error && (
        <p className="once-automation-error">{connection.last_error}</p>
      )}
      {!connection?.configured && (
        <div className="once-football-guidance">
          <strong>Primero, conecta tu cuenta en este servidor.</strong>
          <p>
            La persona que despliega ONCE debe guardar la clave de API-Football
            en la configuración del servidor y reiniciar sus servicios. La clave
            no se introduce ni se muestra aquí.
          </p>
          <a
            href="https://dashboard.api-football.com/"
            target="_blank"
            rel="noreferrer"
          >
            Abrir mi cuenta de API-Football <Icon name="arrow" />
          </a>
        </div>
      )}
      {connection?.account && (
        <dl className="once-football-account">
          <div>
            <dt>Plan de la cuenta</dt>
            <dd>{connection.account.plan || "No indicado"}</dd>
          </div>
          <div>
            <dt>Consultas de la cuenta al comprobarla</dt>
            <dd>
              {remainingBudget(
                connection.account.requests_current,
                connection.account.requests_limit_day,
              )}
            </dd>
          </div>
          <div>
            <dt>Última comprobación</dt>
            <dd>{humanDate(connection.checked_at)}</dd>
          </div>
        </dl>
      )}
      {verified && (
        <div className="once-football-guidance">
          <strong>Tu suscripción está activa.</strong>
          {Array.isArray(allowedSeasons) ? (
            <p>
              {allowedSeasons.length
                ? `La fuente indica que tu cuenta permite las temporadas ${allowedSeasons.join(", ")}. Solo mostramos los años de esa lista que también figuran en cada competición.`
                : "La fuente no confirmó temporadas permitidas para esta cuenta."}
            </p>
          ) : (
            <p>
              La cuenta todavía no tiene una lista confirmada de años
              permitidos. Consulta la disponibilidad de cada temporada al
              comenzar su actualización.
            </p>
          )}
          {connection.account.current_access === false && (
            <p>
              El plan actual no permite consultar la temporada vigente
              comprobada. Puedes seguir completando el archivo histórico dentro
              de los años permitidos.
            </p>
          )}
          {connection.account.access_checked_at && (
            <small className="once-automation-help">
              Acceso comprobado:{" "}
              {humanDate(connection.account.access_checked_at)}.
            </small>
          )}
        </div>
      )}
      <div className="once-automation-actions">
        <button
          className="v-btn v-btn-dark"
          disabled={Boolean(busy) || !canConfigure || !connection?.configured}
          onClick={() =>
            run("check", async () => {
              const next = await apiRequest(`${connectionPath}/check`, {
                method: "POST",
              });
              setConnection(next);
              setSelected({});
              setPreparedIds([]);
              setMessage(
                next.state === "connected"
                  ? "Cuenta comprobada. Revisa las temporadas publicadas y elige qué traer a ONCE."
                  : "Comprobación terminada. Revisa el estado de la cuenta.",
              );
            })
          }
        >
          <Icon name="link" />
          {busy === "check"
            ? "Comprobando cuenta…"
            : "Comprobar cuenta y cobertura"}
        </button>
        <button
          className="v-text-btn"
          disabled={Boolean(busy)}
          onClick={() =>
            run("refresh", async () => {
              setConnection(await apiRequest(`${connectionPath}/connection`));
              setMessage(
                "Configuración leída. Esta consulta no consume cuota de API-Football.",
              );
            })
          }
        >
          Volver a leer configuración
        </button>
      </div>
      <p className="once-automation-help">
        Comprobar la cuenta puede realizar hasta tres consultas. Visitar esta
        pantalla no consulta API-Football. La cuota mostrada es una fotografía
        del momento indicado.
      </p>
      {(connection?.competitions?.length > 0 || verified) && (
        <div className="once-football-coverage">
          <h4>Elige las competiciones y temporadas</h4>
          <p>
            Estas temporadas figuran en el catálogo de la fuente. El acceso
            efectivo a partidos, resultados y detalles se confirma en la primera
            actualización; depende de tu plan.
          </p>
          <div className="once-football-choices">
            {(connection.competitions || []).map((competition) => (
              <CompetitionChoice
                key={`${competition.league_id}/${connection.checked_at}/${connection.account?.access_checked_at || ""}`}
                competition={competition}
                allowedSeasons={allowedSeasons}
                selected={selected[competition.league_id]}
                disabled={Boolean(busy) || !canConfigure || !verified}
                onSelect={(season) => {
                  setSelected((current) => ({
                    ...current,
                    [competition.league_id]: season,
                  }));
                  setPreparedIds([]);
                }}
              />
            ))}
          </div>
          {!connection.competitions?.length && (
            <p>
              No se publicaron competiciones colombianas en esta comprobación.
            </p>
          )}
          <label className="once-football-check once-football-detail-option">
            <input
              type="checkbox"
              checked={includeDetails}
              disabled={Boolean(busy) || !canConfigure}
              onChange={(event) => {
                setIncludeDetails(event.target.checked);
                setPreparedIds([]);
              }}
            />
            <span>
              <strong>Completar también el detalle de los partidos</strong>
              <small>
                Jugadas, alineaciones y estadísticas disponibles, por lotes y
                dentro del presupuesto de consultas.
                {connection.account?.plan?.toLowerCase() === "free" &&
                  " En el plan gratuito se completa un partido por consulta; el archivo puede requerir varios días."}
              </small>
            </span>
          </label>
          <p className="once-automation-help">
            Si la fuente anuncia clasificaciones para la temporada, ONCE también
            prepara su actualización por edición, fase y grupo.
          </p>
          <button
            className="v-btn v-btn-dark"
            disabled={
              Boolean(busy) || !canConfigure || !verified || !selections.length
            }
            onClick={() =>
              run("prepare", async () => {
                const result = await apiRequest(`${connectionPath}/prepare`, {
                  method: "POST",
                  body: { selections, include_details: includeDetails },
                });
                setConnection(result.connection);
                setPreparedIds(result.scope_ids);
                onChanged();
                setMessage(
                  `${result.scope_ids.length} tareas preparadas; ${result.created} nuevas. Las tareas nuevas quedan pausadas. Las existentes conservan su modo.`,
                );
              })
            }
          >
            {busy === "prepare"
              ? "Preparando tareas…"
              : `Preparar ${selections.length || "las"} ${selections.length === 1 ? "competición" : "competiciones"}`}
          </button>
        </div>
      )}
      {preparedIds.length > 0 && (
        <div className="once-football-guidance">
          <h4>Tu selección está preparada</h4>
          <p>{prepared.map((profile) => profile.name).join(" · ")}</p>
          <button
            className="v-btn v-btn-dark"
            disabled={Boolean(busy) || !canOperate || !readyIds.length}
            onClick={() =>
              run("activate", async () => {
                let activated = 0;
                try {
                  for (const id of readyIds) {
                    await apiRequest(`/automation/scopes/${id}`, {
                      method: "PATCH",
                      body: { mode: "automatic" },
                    });
                    activated += 1;
                  }
                } finally {
                  onChanged();
                  setMessage(
                    `${activated} tareas activadas. ${globalMode === "automatic" ? "El motor las actualizará cuando corresponda y haya cuota disponible." : "El control general sigue limitando la publicación de datos."}`,
                  );
                  setConnection(
                    await apiRequest(`${connectionPath}/connection`),
                  );
                }
              })
            }
          >
            {busy === "activate"
              ? "Activando tareas…"
              : readyIds.length
                ? "Activar estas actualizaciones"
                : "Actualizaciones activadas"}
          </button>
          {globalMode !== "automatic" && (
            <p className="once-automation-help">
              El control general está en{" "}
              {globalMode === "paused" ? "Pausado" : "Solo comprobar"}. Para
              publicar datos, elige «Automático» en el control general de abajo.
              Ese cambio también permite funcionar a las otras tareas que ya
              estén activas.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
