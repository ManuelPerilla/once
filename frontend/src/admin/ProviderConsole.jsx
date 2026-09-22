import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Icon } from "../components/ui/Icon";

const mappingTypes = [
  ["competition", "Competición"],
  ["season", "Temporada"],
  ["team", "Equipo"],
  ["match", "Partido"],
  ["venue", "Estadio"],
  ["player", "Jugador"],
];

export function ProviderConsole() {
  const [status, setStatus] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [media, setMedia] = useState([]);
  const [leagueId, setLeagueId] = useState("");
  const [season, setSeason] = useState(String(new Date().getFullYear()));
  const [preview, setPreview] = useState(null);
  const [message, setMessage] = useState("");
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

  const refreshSources = async () => {
    const [providerStatus, providerMappings, mediaAssets] = await Promise.all([
      apiRequest("/providers/api-football/status"),
      apiRequest("/providers/mappings/"),
      apiRequest("/media/"),
    ]);
    setStatus(providerStatus);
    setMappings(providerMappings);
    setMedia(mediaAssets);
  };

  useEffect(() => {
    refreshSources().catch(() =>
      setMessage("No se pudo consultar el estado de las fuentes."),
    );
  }, []);

  const inspectFixtures = async (event) => {
    event.preventDefault();
    if (!leagueId || !season) return;

    setBusy(true);
    setMessage("");
    setPreview(null);
    try {
      const result = await apiRequest(
        `/providers/api-football/preview/fixtures?league_id=${encodeURIComponent(
          leagueId,
        )}&season=${encodeURIComponent(season)}`,
      );
      setPreview(result);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const createMapping = async (event) => {
    event.preventDefault();
    if (!mapping.local_id || !mapping.external_id) return;

    setBusy(true);
    setMessage("");
    try {
      await apiRequest("/providers/mappings/", {
        method: "POST",
        body: {
          provider: "api-football",
          entity_type: mapping.entity_type,
          local_id: Number(mapping.local_id),
          external_id: String(mapping.external_id).trim(),
        },
      });
      setMapping((current) => ({ ...current, local_id: "", external_id: "" }));
      await refreshSources();
      setMessage("Mapping guardado.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const syncCompetition = async (event) => {
    event.preventDefault();
    if (!competitionId || !seasonId) return;

    setBusy(true);
    setMessage("");
    setSyncResult(null);
    try {
      const result = await apiRequest(
        `/providers/api-football/sync/competition/${competitionId}/season/${seasonId}`,
        { method: "POST" },
      );
      setSyncResult({ type: "competition", ...result });
      setMessage(
        result.skipped?.length
          ? `Sync completado con ${result.skipped.length} pendiente(s) por mapear.`
          : "Sync de competición completado.",
      );
      await refreshSources();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const importWikidataMedia = async (event) => {
    event.preventDefault();
    if (!mediaImport.local_id || !mediaImport.qid) return;

    setBusy(true);
    setMessage("");
    try {
      const qid = mediaImport.qid.trim().toUpperCase();
      await apiRequest(
        `/providers/wikidata/import-media/${mediaImport.entity_type}/${mediaImport.local_id}/${encodeURIComponent(qid)}`,
        { method: "POST" },
      );
      setMediaImport((current) => ({ ...current, qid: "" }));
      await refreshSources();
      setMessage("Media importada con procedencia y licencia.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const syncMatch = async (event) => {
    event.preventDefault();
    if (!matchId) return;

    setBusy(true);
    setMessage("");
    setSyncResult(null);
    try {
      const result = await apiRequest(
        `/providers/api-football/sync/match/${matchId}`,
        { method: "POST" },
      );
      setSyncResult({ type: "match", ...result });
      setMessage("Detalle del partido sincronizado.");
      await refreshSources();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="v-source-desk" aria-label="Fuentes y sincronización">
      <div className="v-source-head">
        <div>
          <span className="v-eyebrow">04 / FUENTES Y TRAZABILIDAD</span>
          <h2>La mesa de fuentes.</h2>
          <p>
            VÉRTICE conserva sus propios IDs. Los proveedores aportan datos; no
            gobiernan el modelo.
          </p>
        </div>
        <span
          className="v-source-signal"
          data-online={status?.configured || undefined}
        >
          <i />
          {status?.configured ? "API-Football listo" : "API-Football sin configurar"}
        </span>
      </div>

      <div className="v-source-metrics">
        <article>
          <small>MAPPINGS EXTERNOS</small>
          <strong>{mappings.length}</strong>
          <span>IDs vinculados a entidades locales</span>
        </article>
        <article>
          <small>ASSETS TRAZABLES</small>
          <strong>{media.length}</strong>
          <span>Recursos con fuente y licencia</span>
        </article>
        <article>
          <small>WIKIDATA</small>
          <strong>REST</strong>
          <span>Disponible para enriquecimiento manual</span>
        </article>
      </div>

      <div className="v-source-workbench">
        <form className="v-source-preview" onSubmit={inspectFixtures}>
          <div>
            <span className="v-eyebrow">PREVIEW / SIN ESCRITURA</span>
            <strong>Inspeccionar fixtures</strong>
            <small>Comprueba cobertura antes de crear mappings o sincronizar.</small>
          </div>
          <label>
            <span>League ID</span>
            <input
              inputMode="numeric"
              value={leagueId}
              onChange={(event) => setLeagueId(event.target.value)}
              placeholder="Ej. 239"
            />
          </label>
          <label>
            <span>Temporada</span>
            <input
              inputMode="numeric"
              value={season}
              onChange={(event) => setSeason(event.target.value)}
            />
          </label>
          <button className="v-btn v-btn-dark" disabled={busy || !status?.configured}>
            {busy ? "Consultando…" : "Previsualizar"}
            <Icon name="arrow" />
          </button>
        </form>

        <form className="v-source-preview" onSubmit={createMapping}>
          <div>
            <span className="v-eyebrow">MAPPING / ID CANÓNICO</span>
            <strong>Vincular entidad externa</strong>
            <small>El ID local sigue siendo la identidad principal de VÉRTICE.</small>
          </div>
          <label>
            <span>Entidad</span>
            <select
              value={mapping.entity_type}
              onChange={(event) =>
                setMapping((current) => ({
                  ...current,
                  entity_type: event.target.value,
                }))
              }
            >
              {mappingTypes.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>ID local</span>
            <input
              inputMode="numeric"
              value={mapping.local_id}
              onChange={(event) =>
                setMapping((current) => ({ ...current, local_id: event.target.value }))
              }
              placeholder="Ej. 12"
            />
          </label>
          <label>
            <span>ID API-Football</span>
            <input
              value={mapping.external_id}
              onChange={(event) =>
                setMapping((current) => ({ ...current, external_id: event.target.value }))
              }
              placeholder="Ej. 1001"
            />
          </label>
          <button className="v-btn v-btn-dark" disabled={busy}>
            Guardar mapping <Icon name="link" />
          </button>
        </form>

        <form className="v-source-preview" onSubmit={syncCompetition}>
          <div>
            <span className="v-eyebrow">SYNC / FIXTURES</span>
            <strong>Actualizar competición</strong>
            <small>
              Requiere mappings de competición, temporada y equipos. Los equipos
              desconocidos quedan como pendientes.
            </small>
          </div>
          <label>
            <span>ID competición local</span>
            <input
              inputMode="numeric"
              value={competitionId}
              onChange={(event) => setCompetitionId(event.target.value)}
            />
          </label>
          <label>
            <span>ID temporada local</span>
            <input
              inputMode="numeric"
              value={seasonId}
              onChange={(event) => setSeasonId(event.target.value)}
            />
          </label>
          <button className="v-btn v-btn-dark" disabled={busy || !status?.configured}>
            Sincronizar fixtures <Icon name="refresh" />
          </button>
        </form>

        <form className="v-source-preview" onSubmit={importWikidataMedia}>
          <div>
            <span className="v-eyebrow">IMPORT / WIKIDATA + COMMONS</span>
            <strong>Traer imagen con licencia</strong>
            <small>
              Guarda la URL original, autoría, crédito y licencia. No descarga ni
              republica el archivo automáticamente.
            </small>
          </div>
          <label>
            <span>Entidad</span>
            <select
              value={mediaImport.entity_type}
              onChange={(event) =>
                setMediaImport((current) => ({
                  ...current,
                  entity_type: event.target.value,
                }))
              }
            >
              {mappingTypes
                .filter(([value]) => value !== "match")
                .map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
            </select>
          </label>
          <label>
            <span>ID local</span>
            <input
              inputMode="numeric"
              value={mediaImport.local_id}
              onChange={(event) =>
                setMediaImport((current) => ({
                  ...current,
                  local_id: event.target.value,
                }))
              }
              placeholder="Ej. 12"
            />
          </label>
          <label>
            <span>QID de Wikidata</span>
            <input
              value={mediaImport.qid}
              onChange={(event) =>
                setMediaImport((current) => ({
                  ...current,
                  qid: event.target.value,
                }))
              }
              placeholder="Ej. Q12345"
            />
          </label>
          <button className="v-btn v-btn-dark" disabled={busy}>
            Importar media <Icon name="globe" />
          </button>
        </form>

        <form className="v-source-preview" onSubmit={syncMatch}>
          <div>
            <span className="v-eyebrow">SYNC / MATCH DETAIL</span>
            <strong>Profundizar un partido</strong>
            <small>
              Importa eventos, alineaciones, jugadores y estadísticas en una capa
              trazable separada de los datos manuales.
            </small>
          </div>
          <label>
            <span>ID partido local</span>
            <input
              inputMode="numeric"
              value={matchId}
              onChange={(event) => setMatchId(event.target.value)}
            />
          </label>
          <button className="v-btn v-btn-dark" disabled={busy || !status?.configured}>
            Sincronizar detalle <Icon name="pitch" />
          </button>
        </form>
      </div>

      {!status?.configured && (
        <p className="v-source-note">
          Configura <code>API_FOOTBALL_KEY</code> en tu entorno para habilitar
          previews y sincronización. La clave permanece únicamente en el backend.
        </p>
      )}

      {message && (
        <p
          className={`v-source-note ${message.toLowerCase().includes("no ") ? "v-source-note-error" : ""}`}
          role="status"
        >
          {message}
        </p>
      )}

      {preview && (
        <div className="v-source-results">
          <span>
            {preview.results ?? preview.response?.length ?? 0} fixtures devueltos
          </span>
          {(preview.response || []).slice(0, 4).map((fixture) => (
            <article key={fixture.fixture?.id}>
              <small>{fixture.league?.round || fixture.league?.name || "Fixture"}</small>
              <strong>
                {fixture.teams?.home?.name || "Local"} <b>vs</b>{" "}
                {fixture.teams?.away?.name || "Visitante"}
              </strong>
              <span>{fixture.fixture?.date || "Fecha no disponible"}</span>
            </article>
          ))}
        </div>
      )}

      {syncResult?.type === "competition" && (
        <div className="v-source-results">
          <span>
            {syncResult.created} creados · {syncResult.updated} actualizados ·{" "}
            {syncResult.skipped?.length || 0} pendientes
          </span>
          {(syncResult.skipped || []).slice(0, 8).map((item) => (
            <article key={item.fixture_id || `${item.home}-${item.away}`}>
              <small>PENDIENTE / {item.reason}</small>
              <strong>{item.home || "Equipo"} <b>vs</b> {item.away || "Equipo"}</strong>
              <span>Fixture {item.fixture_id || "sin ID"}</span>
            </article>
          ))}
        </div>
      )}

      {syncResult?.type === "match" && (
        <div className="v-source-results">
          <span>Detalle normalizado</span>
          <article>
            <small>PARTIDO #{syncResult.match_id}</small>
            <strong>
              {syncResult.events} eventos · {syncResult.lineup_entries} alineaciones
            </strong>
            <span>
              {syncResult.players_touched} jugadores ·{" "}
              {syncResult.statistics ? "estadísticas importadas" : "sin estadísticas completas"}
            </span>
          </article>
        </div>
      )}
    </section>
  );
}
