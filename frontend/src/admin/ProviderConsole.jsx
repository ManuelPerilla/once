import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Icon } from "../components/ui/Icon";
import { CatalogImport } from "./CatalogImport";
import { SourceEntitySelect } from "./SourceEntitySelect";

const mappingTypes = [
  ["competition", "Competición"],
  ["season", "Temporada"],
  ["team", "Equipo o selección"],
  ["match", "Partido"],
  ["venue", "Estadio"],
  ["player", "Jugador"],
];
const mediaTypes = [
  ["confederation", "Confederación"],
  ...mappingTypes.filter(([type]) => !["match", "season"].includes(type)),
];
const crestTypes = ["confederation", "competition", "team"];
const tasks = [
  [
    "catalog",
    "plus",
    "Añadir equipos y torneos",
    "Trae información gratuita y revísala antes de guardar.",
  ],
  [
    "images",
    "shield",
    "Buscar escudos e imágenes",
    "Elige una imagen y conserva su origen y licencia.",
  ],
  [
    "preview",
    "search",
    "Consultar partidos",
    "Mira qué encuentros ofrece la fuente, sin añadirlos.",
  ],
  [
    "connections",
    "link",
    "Conectar registros",
    "Indica qué nombre de la fuente corresponde al que ya tienes.",
  ],
  [
    "matches",
    "refresh",
    "Traer partidos",
    "Añade o actualiza encuentros de una competición.",
  ],
  [
    "details",
    "pitch",
    "Completar un partido",
    "Busca alineaciones, jugadas y estadísticas.",
  ],
];
const readSources = (signal) =>
  Promise.all([
    apiRequest("/providers/api-football/status", { signal }),
    apiRequest("/providers/mappings/", { signal }),
    apiRequest("/media/", { signal }),
  ]);

function TaskHeading({ step, title, children }) {
  return (
    <div className="once-task-heading">
      <span className="v-eyebrow">{step}</span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function ProviderConsole({ onImported, onAutomation }) {
  const [task, setTask] = useState("catalog");
  const [status, setStatus] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [media, setMedia] = useState([]);
  const [leagueId, setLeagueId] = useState("");
  const [previewCompetition, setPreviewCompetition] = useState("");
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [preview, setPreview] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mapping, setMapping] = useState({
    entity_type: "competition",
    local_id: "",
    external_id: "",
  });
  const [competitionId, setCompetitionId] = useState("");
  const [seasonId, setSeasonId] = useState("");
  const [matchId, setMatchId] = useState("");
  const [syncResult, setSyncResult] = useState(null);
  const [mediaImport, setMediaImport] = useState({
    entity_type: "team",
    local_id: "",
    qid: "",
  });
  const [mediaPreview, setMediaPreview] = useState(null);
  const [useAsLogo, setUseAsLogo] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  const acceptSources = ([providerStatus, providerMappings, mediaAssets]) => {
    setStatus(providerStatus);
    setMappings(providerMappings);
    setMedia(mediaAssets);
  };
  const refreshSources = async () => acceptSources(await readSources());
  const refreshCatalog = async () => {
    await refreshSources();
    setRefreshKey((value) => value + 1);
    await onImported?.();
  };

  useEffect(() => {
    const controller = new AbortController();
    readSources(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) acceptSources(result);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "No pudimos comprobar las conexiones. Vuelve a abrir este panel para intentarlo de nuevo.",
          );
      });
    return () => controller.abort();
  }, []);

  const runTask = async (operation) => {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await operation();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };
  const inspectFixtures = (event) => {
    event.preventDefault();
    if (!leagueId || !season) return;
    setPreview(null);
    runTask(async () => {
      setPreview(
        await apiRequest(
          `/providers/api-football/preview/fixtures?league_id=${encodeURIComponent(leagueId)}&season=${encodeURIComponent(season)}`,
        ),
      );
      setMessage(
        "Consulta lista. Todavía no se ha añadido ningún partido a ONCE.",
      );
    });
  };
  const createMapping = (event) => {
    event.preventDefault();
    if (!mapping.local_id || !mapping.external_id.trim()) return;
    runTask(async () => {
      await apiRequest("/providers/mappings/", {
        method: "POST",
        body: {
          provider: "api-football",
          entity_type: mapping.entity_type,
          local_id: Number(mapping.local_id),
          external_id: mapping.external_id.trim(),
        },
      });
      setMapping((current) => ({ ...current, local_id: "", external_id: "" }));
      await refreshSources();
      setMessage(
        "Conexión guardada. ONCE ya sabe que ambos registros representan lo mismo.",
      );
    });
  };
  const syncCompetition = (event) => {
    event.preventDefault();
    if (!competitionId || !seasonId) return;
    setSyncResult(null);
    runTask(async () => {
      const result = await apiRequest(
        `/providers/api-football/sync/competition/${competitionId}/season/${seasonId}`,
        { method: "POST" },
      );
      setSyncResult({ type: "competition", ...result });
      setMessage(
        result.job_id || result.status === "queued"
          ? "Comprobación en cola. Sigue su progreso en Automatización."
          : result.skipped?.length
            ? `Partidos actualizados. Quedan ${result.skipped.length} encuentros por revisar: primero conecta sus equipos con los de la fuente.`
            : "Los partidos de la competición están actualizados.",
      );
      await refreshSources();
      await onImported?.();
    });
  };
  const updateMedia = (changes) => {
    setMediaImport((current) => ({ ...current, ...changes }));
    setMediaPreview(null);
    setMessage("");
    setError("");
  };
  const isCrest = crestTypes.includes(mediaImport.entity_type);
  const inspectMedia = (event) => {
    event.preventDefault();
    if (!mediaImport.local_id || !mediaImport.qid.trim()) return;
    setMediaPreview(null);
    runTask(async () => {
      const qid = mediaImport.qid
        .trim()
        .replace(/^https:\/\/www\.wikidata\.org\/wiki\//i, "")
        .toUpperCase();
      if (!/^Q[1-9]\d*$/.test(qid))
        throw new Error(
          "Escribe un código como Q615, o pega el enlace de una ficha de Wikidata.",
        );
      const result = await apiRequest(
        `/providers/wikidata/preview/${qid}/media?purpose=${isCrest ? "crest" : "image"}`,
      );
      setMediaImport((current) => ({ ...current, qid }));
      setMediaPreview(result);
    });
  };
  const importWikidataMedia = () => {
    if (!mediaPreview) return;
    runTask(async () => {
      const params = new URLSearchParams({
        use_as_logo: String(isCrest && useAsLogo),
        preview_filename: mediaPreview.filename,
      });
      await apiRequest(
        `/providers/wikidata/import-media/${mediaImport.entity_type}/${mediaImport.local_id}/${encodeURIComponent(mediaImport.qid)}?${params}`,
        { method: "POST" },
      );
      setMediaPreview(null);
      await refreshCatalog();
      setMessage(
        isCrest && useAsLogo
          ? "Escudo guardado con su fuente y licencia. Se muestra si el registro aún no tenía uno; los escudos que añadiste se conservan."
          : "Imagen guardada junto con su fuente y licencia.",
      );
    });
  };
  const syncMatch = (event) => {
    event.preventDefault();
    if (!matchId) return;
    setSyncResult(null);
    runTask(async () => {
      const result = await apiRequest(
        `/providers/api-football/sync/match/${matchId}`,
        { method: "POST" },
      );
      setSyncResult({ type: "match", ...result });
      setMessage(
        result.job_id || result.status === "queued"
          ? "Detalle en cola. Sigue su progreso en Automatización."
          : "La información disponible del partido está guardada.",
      );
      await refreshSources();
      await onImported?.();
    });
  };
  const providerTasks = ["preview", "matches", "details"];
  const linkedCompetitions = mappings.filter(
    (item) =>
      item.provider === "api-football" && item.entity_type === "competition",
  );
  const linkedMatches = mappings
    .filter(
      (item) =>
        item.provider === "api-football" && item.entity_type === "match",
    )
    .map((item) => item.local_id);
  const linkedSeasons = mappings
    .filter(
      (item) =>
        item.provider === "api-football" && item.entity_type === "season",
    )
    .map((item) => item.local_id);

  return (
    <section className="v-source-desk" aria-labelledby="sources-title">
      <div className="v-source-head">
        <div>
          <span className="v-eyebrow">TU CATÁLOGO, MÁS COMPLETO</span>
          <h2 id="sources-title">Menos trabajo manual.</h2>
          <p>
            Elige lo que necesitas. Te acompañamos paso a paso para traer
            información a ONCE.
          </p>
        </div>
        <span
          className="v-source-signal"
          data-online={status?.configured || undefined}
        >
          <i />
          {status?.configured
            ? "Credencial de partidos configurada"
            : "Datos gratuitos disponibles"}
        </span>
      </div>
      {onAutomation && (
        <p className="v-source-note">
          Para comprobar tu cuenta, elegir las temporadas colombianas y dejar
          sus actualizaciones funcionando, abre{" "}
          <button className="v-text-btn" onClick={onAutomation}>
            la conexión de API-Football
          </button>
          . Aquí puedes resolver conexiones puntuales entre registros.
        </p>
      )}
      <div
        className="once-source-tasks"
        role="group"
        aria-label="¿Qué necesitas hacer?"
      >
        {tasks.map(([value, icon, label, description]) => (
          <button
            type="button"
            key={value}
            aria-pressed={task === value}
            aria-controls="source-task-panel"
            disabled={busy}
            onClick={() => {
              setTask(value);
              setMessage("");
              setError("");
            }}
          >
            <Icon name={icon} />
            <span>
              <strong>{label}</strong>
              <small>{description}</small>
            </span>
            <Icon name="chevron" />
          </button>
        ))}
      </div>
      <div
        id="source-task-panel"
        className="once-source-task-panel"
        aria-busy={busy}
      >
        <div hidden={task !== "catalog"}>
          <CatalogImport onImported={refreshCatalog} onBusyChange={setBusy} />
        </div>
        {providerTasks.includes(task) && !status?.configured && (
          <p className="v-source-note" role="status">
            {status === null
              ? "Comprobando la conexión para consultar partidos…"
              : "Esta función necesita una conexión con API-Football. Pide a quien administra la instalación que la active. Mientras tanto, puedes añadir equipos y buscar escudos gratis."}
          </p>
        )}
        {task === "preview" && (
          <form className="v-source-preview" onSubmit={inspectFixtures}>
            <TaskHeading
              step="SOLO CONSULTA"
              title="Mira qué partidos hay disponibles"
            >
              Consulta los encuentros de un año antes de decidir qué traer a
              ONCE. Esta búsqueda no cambia tu catálogo.
            </TaskHeading>
            <SourceEntitySelect
              type="competition"
              label="Competición conectada"
              value={previewCompetition}
              disabled={busy}
              allowIds={linkedCompetitions.map((item) => item.local_id)}
              refreshKey={refreshKey}
              emptyMessage="Aún no tienes competiciones conectadas. Puedes usar su número en la fuente más abajo."
              required={false}
              onChange={(value) => {
                setPreviewCompetition(value);
                setLeagueId(
                  linkedCompetitions.find(
                    (item) => String(item.local_id) === value,
                  )?.external_id || "",
                );
              }}
            />
            <details className="once-source-help">
              <summary>Consultar otra competición</summary>
              <p>
                Si todavía no está conectada, copia su número desde
                API-Football. Quien configura esa fuente puede proporcionártelo.
              </p>
              <label>
                <span>Número de competición en API-Football</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={leagueId}
                  onChange={(event) => {
                    setLeagueId(event.target.value);
                    setPreviewCompetition("");
                  }}
                  placeholder="Ej. 239"
                  disabled={busy}
                />
              </label>
            </details>
            <label>
              <span>Año de la temporada</span>
              <input
                type="number"
                min="1800"
                max="2200"
                value={season}
                onChange={(event) => setSeason(event.target.value)}
                required
                disabled={busy}
              />
            </label>
            <button
              className="v-btn v-btn-dark"
              disabled={busy || !status?.configured || !leagueId}
            >
              {busy ? "Buscando partidos…" : "Consultar sin guardar"}
              <Icon name="search" />
            </button>
          </form>
        )}
        {task === "connections" && (
          <form className="v-source-preview" onSubmit={createMapping}>
            <TaskHeading
              step="EVITA DUPLICADOS"
              title="Conecta lo que ya tienes"
            >
              Elige un registro de ONCE y el número que le corresponde en
              API-Football. Por ejemplo: tu equipo «Deportes Tolima» y ese mismo
              equipo en la fuente.
            </TaskHeading>
            <label>
              <span>¿Qué quieres conectar?</span>
              <select
                value={mapping.entity_type}
                disabled={busy}
                onChange={(event) =>
                  setMapping({
                    entity_type: event.target.value,
                    local_id: "",
                    external_id: "",
                  })
                }
              >
                {mappingTypes.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <SourceEntitySelect
              type={mapping.entity_type}
              label="Nombre en ONCE"
              value={mapping.local_id}
              disabled={busy}
              refreshKey={refreshKey}
              onChange={(value) =>
                setMapping((current) => ({ ...current, local_id: value }))
              }
            />
            <label>
              <span>
                {mapping.entity_type === "season"
                  ? "Año de la temporada en API-Football"
                  : "Número del registro en API-Football"}
              </span>
              <input
                value={mapping.external_id}
                required
                disabled={busy}
                onChange={(event) =>
                  setMapping((current) => ({
                    ...current,
                    external_id: event.target.value,
                  }))
                }
                placeholder={
                  mapping.entity_type === "season"
                    ? "Ej. 2026"
                    : "Copia el número de la fuente"
                }
              />
              <small>
                Debe corresponder al mismo{" "}
                {mapping.entity_type === "season" ? "año" : "registro"}. Esta
                conexión conserva la información que ya escribiste en ONCE.
              </small>
            </label>
            <details className="once-source-help">
              <summary>¿Dónde encuentro ese número?</summary>
              <p>
                Está en la ficha o consulta del registro en API-Football. Si no
                lo conoces, pide ayuda a quien conectó la fuente; no escribas un
                número al azar.
              </p>
            </details>
            <button
              className="v-btn v-btn-dark"
              disabled={
                busy || !mapping.local_id || !mapping.external_id.trim()
              }
            >
              {busy ? "Guardando conexión…" : "Guardar conexión"}
              <Icon name="link" />
            </button>
          </form>
        )}
        {task === "matches" && (
          <form className="v-source-preview" onSubmit={syncCompetition}>
            <TaskHeading
              step="GUARDAR EN ONCE"
              title="Trae los partidos de una competición"
            >
              Añade encuentros nuevos y actualiza los que ya llegaron de esta
              fuente. Primero deben estar conectados la competición, su
              temporada y sus equipos.
            </TaskHeading>
            <SourceEntitySelect
              type="competition"
              label="Competición"
              value={competitionId}
              disabled={busy}
              refreshKey={refreshKey}
              allowIds={linkedCompetitions.map((item) => item.local_id)}
              emptyMessage="Primero conecta una competición en «Conectar registros»."
              onChange={(value) => {
                setCompetitionId(value);
                setSeasonId("");
              }}
            />
            <SourceEntitySelect
              type="season"
              label="Temporada de esa competición"
              value={seasonId}
              disabled={busy || !competitionId}
              refreshKey={refreshKey}
              competitionId={competitionId}
              allowIds={linkedSeasons}
              emptyMessage="No hay temporadas conectadas para esta competición. Revisa «Conectar registros»."
              onChange={setSeasonId}
            />
            <p className="once-import-help">
              Si falta conectar algún equipo, sus partidos quedarán pendientes y
              verás cuáles son. Los equipos no se crearán por sorpresa.
            </p>
            <button
              className="v-btn v-btn-dark"
              disabled={
                busy || !status?.configured || !competitionId || !seasonId
              }
            >
              {busy ? "Actualizando partidos…" : "Traer y actualizar partidos"}
              <Icon name="refresh" />
            </button>
          </form>
        )}
        {task === "images" && (
          <form className="v-source-preview" onSubmit={inspectMedia}>
            <TaskHeading
              step="ELIGE · REVISA · GUARDA"
              title="Dale identidad a cada ficha"
            >
              Busca escudos de equipos, selecciones, torneos o confederaciones.
              Verás la imagen y su licencia antes de guardarla.
            </TaskHeading>
            <label>
              <span>¿Qué imagen necesitas?</span>
              <select
                value={mediaImport.entity_type}
                disabled={busy}
                onChange={(event) =>
                  updateMedia({
                    entity_type: event.target.value,
                    local_id: "",
                    qid: "",
                  })
                }
              >
                {mediaTypes.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <SourceEntitySelect
              type={mediaImport.entity_type}
              label="Nombre en tu catálogo"
              value={mediaImport.local_id}
              disabled={busy}
              refreshKey={refreshKey}
              onChange={(value) =>
                updateMedia({
                  local_id: value,
                  qid:
                    mappings.find(
                      (item) =>
                        item.provider === "wikidata" &&
                        item.entity_type === mediaImport.entity_type &&
                        String(item.local_id) === value,
                    )?.external_id || "",
                })
              }
            />
            <label>
              <span>Ficha de Wikidata</span>
              <input
                value={mediaImport.qid}
                disabled={busy}
                required
                onChange={(event) => updateMedia({ qid: event.target.value })}
                placeholder="Pega el enlace o un código como Q615"
                aria-describedby="media-source-help"
              />
              <small id="media-source-help">
                La completamos si este nombre ya está conectado. Revisa que
                corresponda al equipo o torneo que elegiste.
              </small>
            </label>
            <details className="once-source-help">
              <summary>¿Cómo encuentro la ficha?</summary>
              <p>
                Busca el nombre en{" "}
                <a
                  href="https://www.wikidata.org/wiki/Special:Search"
                  target="_blank"
                  rel="noreferrer"
                >
                  Wikidata
                </a>
                , abre el resultado correcto y copia su enlace. Las imágenes
                proceden de Wikimedia Commons; algunos nombres todavía no tienen
                un escudo disponible.
              </p>
            </details>
            <button
              className="v-btn v-btn-dark"
              disabled={
                busy || !mediaImport.local_id || !mediaImport.qid.trim()
              }
            >
              {busy ? "Consultando imagen…" : "Buscar imagen para revisar"}
              <Icon name="search" />
            </button>
            {mediaPreview && (
              <div className="once-media-review">
                <img
                  src={mediaPreview.thumbnail_url || mediaPreview.original_url}
                  alt={`Imagen encontrada de ${mediaPreview.entity_name || "la ficha seleccionada"}`}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                />
                <div>
                  <h4>{mediaPreview.entity_name || "Imagen encontrada"}</h4>
                  <p>
                    Comprueba que es la identidad correcta antes de guardar.
                  </p>
                  <dl>
                    <div>
                      <dt>Autor</dt>
                      <dd>
                        {mediaPreview.author || "No indicado por la fuente"}
                      </dd>
                    </div>
                    <div>
                      <dt>Licencia</dt>
                      <dd>
                        <a
                          href={
                            mediaPreview.license_url || mediaPreview.source_url
                          }
                          target="_blank"
                          rel="noreferrer"
                        >
                          {mediaPreview.license === "Public domain"
                            ? "Dominio público"
                            : mediaPreview.license || "Consultar condiciones"}
                        </a>
                      </dd>
                    </div>
                    {mediaPreview.credit && (
                      <div>
                        <dt>Crédito</dt>
                        <dd>{mediaPreview.credit}</dd>
                      </div>
                    )}
                  </dl>
                  <a
                    href={mediaPreview.source_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Ver archivo y condiciones en Commons ↗
                  </a>
                </div>
                {isCrest && (
                  <label className="once-source-check">
                    <input
                      type="checkbox"
                      checked={useAsLogo}
                      disabled={busy || !mediaPreview.can_use_as_logo}
                      onChange={(event) => setUseAsLogo(event.target.checked)}
                    />
                    <span>Usar como escudo si aún no tiene uno</span>
                  </label>
                )}
                {isCrest && !mediaPreview.can_use_as_logo && (
                  <p className="v-source-note">
                    No podemos usarla como escudo porque falta confirmar su
                    licencia o su tipo de imagen.
                  </p>
                )}
                <button
                  type="button"
                  className="v-btn v-btn-primary"
                  onClick={importWikidataMedia}
                  disabled={
                    busy ||
                    (isCrest && useAsLogo && !mediaPreview.can_use_as_logo)
                  }
                >
                  {busy ? "Guardando imagen…" : "Guardar esta imagen"}
                  <Icon name="check" />
                </button>
              </div>
            )}
          </form>
        )}
        {task === "details" && (
          <form className="v-source-preview" onSubmit={syncMatch}>
            <TaskHeading
              step="MÁS ALLÁ DEL MARCADOR"
              title="Completa la historia del partido"
            >
              Trae las jugadas, alineaciones, jugadores y estadísticas
              disponibles. La información de la fuente se conserva separada de
              tus anotaciones manuales.
            </TaskHeading>
            <SourceEntitySelect
              type="match"
              label="Partido conectado"
              value={matchId}
              disabled={busy}
              refreshKey={refreshKey}
              allowIds={linkedMatches}
              emptyMessage="Aún no hay partidos conectados. Tráelos desde una competición o conecta uno en «Conectar registros»."
              onChange={setMatchId}
            />
            <button
              className="v-btn v-btn-dark"
              disabled={busy || !status?.configured || !matchId}
            >
              {busy
                ? "Buscando información…"
                : "Completar información del partido"}
              <Icon name="pitch" />
            </button>
          </form>
        )}
        {error && (
          <p className="v-source-note v-source-note-error" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="v-source-note" role="status">
            {message}
            {(syncResult?.job_id || syncResult?.status === "queued") &&
              onAutomation && (
                <button className="v-text-btn" onClick={onAutomation}>
                  Ver actividad de automatización →
                </button>
              )}
          </p>
        )}
        {task === "preview" && preview && (
          <div className="v-source-results">
            <span>
              {preview.results ?? preview.response?.length ?? 0} partidos
              encontrados · se muestran hasta 4 ejemplos
            </span>
            {(preview.response || []).slice(0, 4).map((fixture) => (
              <article key={fixture.fixture?.id}>
                <small>
                  {fixture.league?.round || fixture.league?.name || "Partido"}
                </small>
                <strong>
                  {fixture.teams?.home?.name || "Local"} <b>vs</b>{" "}
                  {fixture.teams?.away?.name || "Visitante"}
                </strong>
                <span>
                  {fixture.fixture?.date
                    ? new Date(fixture.fixture.date).toLocaleString("es-CO")
                    : "Fecha por confirmar"}
                </span>
              </article>
            ))}
          </div>
        )}
        {task === "matches" &&
          syncResult?.type === "competition" &&
          !syncResult.job_id &&
          syncResult.status !== "queued" && (
            <div className="v-source-results">
              <span>
                {syncResult.created} partidos nuevos · {syncResult.updated}{" "}
                actualizados · {syncResult.skipped?.length || 0} por revisar
              </span>
              {(syncResult.skipped || []).slice(0, 8).map((item) => (
                <article key={item.fixture_id || `${item.home}-${item.away}`}>
                  <small>Pendiente de conexión</small>
                  <strong>
                    {item.home || "Equipo"} <b>vs</b> {item.away || "Equipo"}
                  </strong>
                  <details>
                    <summary>Ver motivo de la fuente</summary>
                    <p>{item.reason}</p>
                  </details>
                </article>
              ))}
            </div>
          )}
        {task === "details" &&
          syncResult?.type === "match" &&
          !syncResult.job_id &&
          syncResult.status !== "queued" && (
            <div className="v-source-results">
              <span>Información guardada</span>
              <article>
                <strong>
                  {syncResult.events} jugadas · {syncResult.lineup_entries}{" "}
                  participaciones en la alineación
                </strong>
                <span>
                  {syncResult.players_touched} jugadores ·{" "}
                  {syncResult.statistics
                    ? "estadísticas disponibles"
                    : "la fuente aún no ofrece estadísticas completas"}
                </span>
              </article>
            </div>
          )}
      </div>
      <div className="v-source-metrics">
        <article>
          <small>REGISTROS CONECTADOS</small>
          <strong>{mappings.length}</strong>
          <span>Nombres reconocidos en las fuentes</span>
        </article>
        <article>
          <small>IMÁGENES GUARDADAS</small>
          <strong>{media.length}</strong>
          <span>Con su información de procedencia</span>
        </article>
        <article>
          <small>INFORMACIÓN GRATUITA</small>
          <strong>Wikidata</strong>
          <span>Datos abiertos; cada imagen conserva su propia licencia</span>
        </article>
      </div>
    </section>
  );
}
