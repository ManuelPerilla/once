import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Icon } from "../components/ui/Icon";

const states = {
  new: "Nuevo",
  review: "Revisar coincidencia",
  linked: "Ya vinculado",
  blocked: "Dato incompleto",
};
const kinds = {
  confederation: "Confederación",
  competition: "Competición",
  team: "Equipo",
};

function initialChoices(rows) {
  return Object.fromEntries(
    rows.map((row) => [
      row.qid,
      row.status === "new" ? "create" : row.status === "review" ? "" : "skip",
    ]),
  );
}

export function CatalogImport({ onImported }) {
  const [collections, setCollections] = useState([]);
  const [collection, setCollection] = useState("colombia");
  const [batch, setBatch] = useState(null);
  const [choices, setChoices] = useState({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    apiRequest("/catalog/collections", { signal: controller.signal })
      .then(setCollections)
      .catch((failure) => {
        if (failure.name !== "AbortError") setError(failure.message);
      });
    return () => controller.abort();
  }, []);

  const prepare = async (event) => {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    setBatch(null);
    try {
      const data = await apiRequest(`/catalog/prepare/${collection}`, {
        method: "POST",
      });
      setBatch(data);
      setChoices(initialChoices(data.rows));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  const rows = batch?.rows || [];
  const unresolved = rows.some((row) => choices[row.qid] === "");
  const selected = rows.filter(
    (row) => choices[row.qid] && choices[row.qid] !== "skip",
  );
  const missingParent = selected.some(
    (row) =>
      row.confederation_qid &&
      rows.find((parent) => parent.qid === row.confederation_qid)?.status !==
        "linked" &&
      (!choices[row.confederation_qid] ||
        choices[row.confederation_qid] === "skip"),
  );

  const apply = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await apiRequest(`/catalog/batches/${batch.id}/apply`, {
        method: "POST",
        body: {
          decisions: rows.map((row) => ({
            qid: row.qid,
            expected_status: row.status,
            action: choices[row.qid]?.startsWith("link:")
              ? "link"
              : choices[row.qid] || "skip",
            local_id: choices[row.qid]?.startsWith("link:")
              ? Number(choices[row.qid].slice(5))
              : null,
          })),
        },
      });
      setMessage(
        `Importación completada: ${result.created} nuevos, ${result.linked} vinculados y ${result.reused} ya existentes. Tus datos anteriores se conservan.`,
      );
      setBatch(null);
      await onImported?.();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="once-import"
      aria-labelledby="catalog-import-title"
      aria-busy={busy}
    >
      <div className="once-import-heading">
        <div>
          <span className="v-eyebrow">DATOS ABIERTOS / WIKIDATA</span>
          <h3 id="catalog-import-title">Haz crecer tu catálogo.</h3>
          <p>
            Trae identidades verificables, revisa coincidencias y conecta los
            registros con ONCE.
          </p>
        </div>
        <span className="once-import-license">Gratis · CC0</span>
      </div>
      <form className="once-import-controls" onSubmit={prepare}>
        <label>
          <span>Colección de datos abiertos</span>
          <select
            value={collection}
            disabled={busy}
            onChange={(event) => {
              setCollection(event.target.value);
              setBatch(null);
              setError("");
              setMessage("");
            }}
          >
            {collections.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.count} registros
              </option>
            ))}
          </select>
        </label>
        <button
          className="v-btn v-btn-dark"
          disabled={busy || !collections.length}
        >
          {busy ? "Procesando…" : "Preparar vista previa"}
          <Icon name="arrow" />
        </button>
      </form>
      <p className="once-import-help">
        {collections.find((item) => item.id === collection)?.description} La
        vista previa guarda una copia de la fuente; el catálogo cambia al
        importar.
      </p>
      {error && (
        <p className="once-import-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="once-import-success" role="status">
          {message}
        </p>
      )}
      {batch && (
        <>
          <div className="once-import-summary" role="status">
            <strong>
              {rows.filter((row) => row.status === "new").length} nuevos
            </strong>
            <span>
              {rows.filter((row) => row.status === "review").length} por revisar
            </span>
            <span>
              {rows.filter((row) => row.status === "linked").length} vinculados
            </span>
            <small>
              {batch.cached ? "Copia local" : "Consultado en Wikidata"} ·{" "}
              {new Date(batch.fetched_at).toLocaleString("es-CO")}
            </small>
          </div>
          <div
            className="once-import-list"
            role="list"
            aria-label="Vista previa del catálogo"
          >
            {rows.map((row) => (
              <article
                className="once-import-row"
                role="listitem"
                key={row.qid}
              >
                <div>
                  <small>
                    {kinds[row.entity_type]} {row.pais ? `· ${row.pais}` : ""}
                  </small>
                  <a href={row.source_url} target="_blank" rel="noreferrer">
                    {row.nombre} ↗
                  </a>
                  {row.local_name && <span>En ONCE: {row.local_name}</span>}
                  {row.errors.map((note) => (
                    <span className="once-import-error" key={note}>
                      {note}
                    </span>
                  ))}
                </div>
                <span className="once-import-state" data-state={row.status}>
                  {states[row.status]}
                </span>
                {row.status === "linked" || row.status === "blocked" ? (
                  <small>
                    {row.status === "linked" ? "Se conserva" : "Se omite"}
                  </small>
                ) : (
                  <label>
                    <select
                      aria-label={`Acción para ${row.nombre}`}
                      value={choices[row.qid] || ""}
                      disabled={busy}
                      onChange={(event) =>
                        setChoices((current) => ({
                          ...current,
                          [row.qid]: event.target.value,
                        }))
                      }
                    >
                      <option value="" disabled>
                        Revisa antes de importar
                      </option>
                      <option value="skip">Omitir por ahora</option>
                      <option value="create">Crear registro nuevo</option>
                      {row.choices.map((item) => (
                        <option key={item.id} value={`link:${item.id}`}>
                          Vincular: {item.nombre}
                          {row.candidates.some(
                            (candidate) => candidate.id === item.id,
                          )
                            ? " · coincidencia"
                            : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </article>
            ))}
          </div>
          <div className="once-import-actions">
            <p>
              {unresolved
                ? "Decide si cada coincidencia corresponde a un registro existente."
                : missingParent
                  ? "Incluye o vincula CONMEBOL para conectar sus equipos y competiciones."
                  : "Se conservan nombres, imágenes y correcciones de los registros que vincules. Esta carga no crea partidos ni matrículas."}
            </p>
            <button
              type="button"
              className="v-btn v-btn-primary"
              onClick={apply}
              disabled={busy || unresolved || missingParent || !selected.length}
            >
              Importar {selected.length} registros <Icon name="link" />
            </button>
          </div>
        </>
      )}
    </section>
  );
}
