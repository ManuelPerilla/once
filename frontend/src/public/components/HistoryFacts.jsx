import { useEffect, useState } from "react";
import { apiRequest } from "../../api";

function factValue(value) {
  if (typeof value === "string" || typeof value === "number")
    return String(value);
  if (value?.text) return value.text;
  if (value?.time) {
    const match = value.time.match(/^\+?(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return "Fecha por verificar";
    if (value.precision <= 9) return match[1];
    if (value.precision === 10) return `${match[2]}/${match[1]}`;
    return `${match[3]}/${match[2]}/${match[1]}`;
  }
  if (/^Q\d+$/.test(value?.id || ""))
    return (
      <a
        href={`https://www.wikidata.org/wiki/${value.id}`}
        target="_blank"
        rel="noreferrer"
      >
        Consultar entidad de referencia ↗
      </a>
    );
  return "Consultar el dato en su fuente";
}

export function HistoryFacts({ type, id, demo = false }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (demo) return;
    const controller = new AbortController();
    apiRequest(`/public/history/${type}/${id}`, { signal: controller.signal })
      .then(setResult)
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message);
      });
    return () => controller.abort();
  }, [type, id, demo]);
  return (
    <section className="p-section">
      <div className="p-section-head">
        <h2>Hechos que cuentan su historia.</h2>
      </div>
      {error ? (
        <p role="alert">{error}</p>
      ) : demo || (result && !result.facts?.length) ? (
        <p className="once-detail-note">
          Esta ficha todavía no tiene hechos históricos documentados.
        </p>
      ) : !result ? (
        <p role="status">Consultando su historia…</p>
      ) : (
        <>
          <dl className="once-history-facts">
            {result.facts.map((fact, index) => (
              <div key={`${fact.property}-${index}`}>
                <dt>{fact.label}</dt>
                <dd>{factValue(fact.value)}</dd>
              </div>
            ))}
          </dl>
          <p className="once-detail-note">
            Datos estructurados de{" "}
            <a href={result.source_url} target="_blank" rel="noreferrer">
              Wikidata
            </a>{" "}
            · {result.license}.{" "}
            {result.updated_at
              ? `Consultados el ${new Date(result.updated_at).toLocaleDateString("es-CO")}.`
              : ""}
          </p>
        </>
      )}
    </section>
  );
}
