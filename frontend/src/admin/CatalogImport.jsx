import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Icon } from "../components/ui/Icon";

const states = {
  new: "Listo para añadir",
  review: "¿Ya está en ONCE?",
  linked: "Ya está en ONCE",
  blocked: "Falta información",
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

export function CatalogImport({ onImported, onBusyChange }) {
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
    onBusyChange?.(true);
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
      onBusyChange?.(false);
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
    onBusyChange?.(true);
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
        `Listo: añadimos ${result.created} registros, conectamos ${result.linked} con los que ya tenías y reconocimos ${result.reused} existentes. Tus datos anteriores se conservan.`,
      );
      setBatch(null);
      await onImported?.();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
      onBusyChange?.(false);
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
          <span className="v-eyebrow">EMPIEZA AQUÍ · GRATIS</span>
          <h3 id="catalog-import-title">Añadir equipos y torneos</h3>
          <p>
            Encuentra nombres, países y confederaciones sin escribirlos uno por
            uno. Tú decides qué añadir antes de guardar.
          </p>
        </div>
        <span className="once-import-license">Fuente: Wikidata · CC0</span>
      </div>
      <ol className="once-import-steps" aria-label="Cómo añadir información">
        <li aria-current={!batch ? "step" : undefined}>
          <span>1</span> Elige un grupo
        </li>
        <li aria-current={batch ? "step" : undefined}>
          <span>2</span> Revisa los nombres
        </li>
        <li>
          <span>3</span> Guarda tu selección
        </li>
      </ol>
      <form className="once-import-controls" onSubmit={prepare}>
        <label>
          <span>¿Qué quieres añadir?</span>
          <select
            aria-describedby="catalog-collection-help"
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
                {item.name} · {item.count} nombres
              </option>
            ))}
          </select>
        </label>
        <button
          className="v-btn v-btn-dark"
          disabled={busy || !collections.length}
        >
          {busy ? "Preparando información…" : "Buscar y revisar"}
          <Icon name="arrow" />
        </button>
      </form>
      <p className="once-import-help" id="catalog-collection-help">
        {collections.find((item) => item.id === collection)?.description} Buscar
        no añade ni modifica equipos o torneos. Primero verás una lista para
        revisar.
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
              {rows.filter((row) => row.status === "linked").length} ya en ONCE
            </span>
            <small>
              {batch.cached
                ? "Última consulta guardada"
                : "Consultado en Wikidata"}{" "}
              · {new Date(batch.fetched_at).toLocaleString("es-CO")}
            </small>
          </div>
          <div
            className="once-import-list"
            role="list"
            aria-label="Información para revisar antes de guardar"
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
                    {row.status === "linked" ? "Sin cambios" : "No se añadirá"}
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
                        Elige qué hacer con este nombre
                      </option>
                      <option value="skip">No añadir por ahora</option>
                      <option value="create">Añadir como nuevo</option>
                      {row.choices.map((item) => (
                        <option key={item.id} value={`link:${item.id}`}>
                          Es el mismo que: {item.nombre}
                          {row.candidates.some(
                            (candidate) => candidate.id === item.id,
                          )
                            ? " · sugerido"
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
                ? "Hay nombres parecidos a los que ya tienes. Elige «Es el mismo que» para conectarlos sin duplicarlos, o «Añadir como nuevo» si son diferentes."
                : missingParent
                  ? "Incluye también su confederación, o elige la que ya tienes, para que los equipos y torneos queden organizados."
                  : selected.length
                    ? "Al guardar, los nuevos nombres entran al catálogo. Si conectas uno existente, se conservan tus nombres, imágenes y correcciones. Podrás organizar sus partidos después."
                    : "Todo lo encontrado ya está en ONCE o quedó sin seleccionar. No hay nada nuevo que guardar."}
            </p>
            <button
              type="button"
              className="v-btn v-btn-primary"
              onClick={apply}
              disabled={busy || unresolved || missingParent || !selected.length}
            >
              {busy ? "Guardando…" : `Guardar selección (${selected.length})`}{" "}
              <Icon name="check" />
            </button>
          </div>
        </>
      )}
    </section>
  );
}
