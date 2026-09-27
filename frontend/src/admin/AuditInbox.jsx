import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Field, EmptyState, Modal } from "../AdminUI";
import { Pagination } from "../components/ui/Pagination";
import { displayValue, humanDate } from "./automation";

const types = {
  team: "Equipo",
  competition: "Competición",
  confederation: "Confederación",
  match: "Partido",
  season: "Temporada",
  stage: "Fase",
  venue: "Estadio",
  player: "Jugador",
  event: "Jugada",
  lineup: "Alineación",
  statistics: "Estadísticas",
};
export function AuditInbox({
  issues = false,
  onCorrect,
  onError,
  canCorrect = false,
}) {
  const [page, setPage] = useState(1);
  const [type, setType] = useState("");
  const [status, setStatus] = useState("open");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [review, setReview] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const query = new URLSearchParams({
    page,
    page_size: 20,
    ...(type ? { entity_type: type } : {}),
    ...(issues ? { status } : {}),
  }).toString();
  useEffect(() => {
    const controller = new AbortController();
    apiRequest(`/audit/${issues ? "issues" : "changes"}?${query}`, {
      signal: controller.signal,
    })
      .then((data) => {
        setResult({ ...data, query });
        setError("");
      })
      .catch((failure) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          if (failure.status === 401) onError(failure);
        }
      });
    return () => controller.abort();
  }, [issues, query, revision, onError]);
  return (
    <section className="v-panel">
      <div className="once-module-intro">
        <h3>
          {issues
            ? "Diferencias que necesitan criterio"
            : "Qué cambió y por qué"}
        </h3>
        <p>
          {issues
            ? "Una diferencia no sustituye automáticamente tu corrección. Revisa la ficha antes de cerrar el caso."
            : "Cada cambio conserva el valor anterior, el nuevo, el origen y la persona o proceso responsable."}
        </p>
      </div>
      <div className="once-automation-fields">
        <Field label="Tipo de registro">
          <select
            value={type}
            onChange={(event) => {
              setType(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos los tipos</option>
            {Object.entries(types).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {issues && (
          <Field label="Estado de revisión">
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="open">Por revisar</option>
              <option value="resolved">Resueltos</option>
              <option value="all">Todos</option>
            </select>
          </Field>
        )}
      </div>
      {error ? (
        <p role="alert">{error}</p>
      ) : result?.query !== query ? (
        <p role="status">Consultando el historial…</p>
      ) : !result.items.length ? (
        <EmptyState
          icon="check"
          title={
            issues
              ? "No hay diferencias pendientes en esta vista"
              : "Todavía no hay cambios registrados"
          }
        >
          El archivo conservará aquí las próximas observaciones.
        </EmptyState>
      ) : (
        <div className="once-automation-records">
          {result.items.map((item) => (
            <article key={item.id}>
              <strong>
                {types[item.entity_type] || "Registro"} ·{" "}
                {item.field || "Ficha"}
              </strong>
              <p>{item.reason}</p>
              {issues ? (
                <p>
                  Propuesta de la fuente:{" "}
                  <strong>{displayValue(item.proposed)}</strong>
                </p>
              ) : (
                <p>
                  {displayValue(item.before)} →{" "}
                  <strong>{displayValue(item.after)}</strong>
                </p>
              )}
              <small>
                {item.actor || item.source} ·{" "}
                {humanDate(item.updated_at || item.created_at)}
                {item.occurrences > 1
                  ? ` · Detectado ${item.occurrences} veces`
                  : ""}
              </small>
              <div className="once-automation-actions">
                <button
                  className="v-text-btn"
                  onClick={() =>
                    onCorrect({ type: item.entity_type, id: item.entity_id })
                  }
                >
                  Revisar esta ficha →
                </button>
                {issues && canCorrect && item.status === "open" && (
                  <button
                    className="v-text-btn"
                    onClick={() => {
                      setReview(item);
                      setReason("");
                    }}
                  >
                    Cerrar revisión
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      {result && (
        <Pagination
          page={page}
          pageSize={20}
          total={result.total}
          onChange={setPage}
        />
      )}
      {review && (
        <Modal
          title="Cerrar revisión de datos"
          subtitle="Documenta tu decisión. Cerrar el caso no acepta ni publica la propuesta externa."
          busy={busy}
          onClose={() => setReview(null)}
        >
          <form
            className="once-automation-form"
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              try {
                await apiRequest(`/audit/issues/${review.id}/resolve`, {
                  method: "POST",
                  body: { reason },
                });
                setReview(null);
                setRevision((value) => value + 1);
              } catch (failure) {
                setError(failure.message);
                if (failure.status === 401) onError(failure);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="Motivo de la decisión">
              <textarea
                required
                minLength={3}
                maxLength={1000}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </Field>
            {error && <p role="alert">{error}</p>}
            <button className="v-btn v-btn-dark" disabled={busy}>
              Guardar decisión
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}
