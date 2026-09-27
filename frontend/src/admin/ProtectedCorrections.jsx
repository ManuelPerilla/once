import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Field, Icon } from "../AdminUI";
import { SourceEntitySelect } from "./SourceEntitySelect";
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
};
const labels = {
  nombre: "Nombre",
  logo: "Imagen",
  pais: "País",
  fecha: "Fecha y hora",
  jornada: "Jornada",
  marcador_local: "Goles del local",
  marcador_visitante: "Goles del visitante",
  estado: "Estado del partido",
  fecha_inicio: "Fecha de inicio",
  fecha_fin: "Fecha de cierre",
  activa: "Temporada activa",
  tipo: "Tipo",
  orden: "Orden",
  ciudad: "Ciudad",
  latitud: "Latitud",
  longitud: "Longitud",
  nombre_completo: "Nombre completo",
  posicion: "Posición",
  nacionalidad: "Nacionalidad",
  fecha_nacimiento: "Fecha de nacimiento",
};
const numericFields = new Set([
  "marcador_local",
  "marcador_visitante",
  "orden",
  "latitud",
  "longitud",
]);
const states = [
  "programado",
  "en vivo",
  "finalizado",
  "aplazado",
  "suspendido",
  "cancelado",
  "abandonado",
  "adjudicado",
  "desconocido",
];

export function ProtectedCorrections({ onError, initial, canCorrect = false }) {
  const [type, setType] = useState(initial?.type || "team");
  const [id, setId] = useState(initial?.id ? String(initial.id) : "");
  const [recordResult, setRecord] = useState(null);
  const [fieldName, setFieldName] = useState("");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const path = `/audit/entities/${type}/${id}`;
  const recordKey = `${path}/${revision}`;
  const record = recordResult?.key === recordKey ? recordResult : null;
  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    apiRequest(path, { signal: controller.signal })
      .then((value) => {
        setRecord({ ...value, key: recordKey });
        setFieldName("");
        setReason("");
        setError("");
      })
      .catch((failure) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          if (failure.status === 401) onError(failure);
        }
      });
    return () => controller.abort();
  }, [path, id, recordKey, onError]);
  const field = record?.fields.find((item) => item.name === fieldName);
  const save = async (release = false) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next =
        fieldName === "activa"
          ? value === "true"
          : value === ""
            ? null
            : numericFields.has(fieldName) || typeof field?.value === "number"
              ? Number(value)
              : value;
      await apiRequest(`${path}/${fieldName}${release ? "/release" : ""}`, {
        method: release ? "POST" : "PATCH",
        body: {
          ...(release ? {} : { value: next }),
          reason,
          expected_version: record.version,
        },
      });
      setMessage(
        release
          ? "La fuente podrá volver a actualizar este campo en su próxima comprobación."
          : "Corrección guardada y protegida frente a actualizaciones automáticas.",
      );
      setRevision((current) => current + 1);
    } catch (failure) {
      setError(
        failure.status === 409
          ? "Otra persona o proceso modificó esta ficha. Vuelve a consultarla antes de guardar tu corrección."
          : failure.message,
      );
      if (failure.status === 401) onError(failure);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="v-panel once-corrections">
      <div className="once-module-intro">
        <h3>Corrige una vez. Conserva tu criterio.</h3>
        <p>
          Elige la ficha y un campo concreto. Tu corrección permanecerá
          protegida hasta que decidas volver a aceptar la fuente.
        </p>
      </div>
      <div className="once-automation-fields">
        <Field label="Tipo de ficha">
          <select
            value={type}
            onChange={(event) => {
              setType(event.target.value);
              setId("");
              setMessage("");
            }}
          >
            {!types[type] && (
              <option value={type}>Registro del partido seleccionado</option>
            )}
            {Object.entries(types).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {types[type] && (
          <SourceEntitySelect
            type={type}
            label="Ficha que quieres revisar"
            value={id}
            onChange={setId}
          />
        )}
      </div>
      {error && (
        <p className="once-automation-error" role="alert">
          {error}{" "}
          <button
            className="v-text-btn"
            onClick={() => setRevision((current) => current + 1)}
          >
            Volver a consultar
          </button>
        </p>
      )}
      {message && (
        <p className="once-automation-success" role="status">
          {message}
        </p>
      )}
      {id && !record && !error && <p role="status">Consultando la ficha…</p>}
      {record && (
        <>
          <h3>{record.label}</h3>
          <div className="once-correction-fields">
            {record.fields.map((item) => (
              <button
                key={item.name}
                className="once-correction-field"
                aria-pressed={fieldName === item.name}
                onClick={() => {
                  setFieldName(item.name);
                  setValue(item.value == null ? "" : String(item.value));
                  setReason("");
                }}
              >
                <span>{labels[item.name] || item.name}</span>
                <strong>{displayValue(item.value)}</strong>
                <small>
                  <Icon name={item.protected ? "shield" : "globe"} />
                  {item.protected
                    ? "Corrección protegida"
                    : "Puede actualizarse desde la fuente"}
                </small>
              </button>
            ))}
          </div>
          {field && (
            <form
              className="once-correction-editor"
              onSubmit={(event) => {
                event.preventDefault();
                save();
              }}
            >
              <Field
                label={`Nuevo valor: ${labels[fieldName] || fieldName}`}
                hint="Un campo vacío guarda ausencia de dato cuando el campo lo permite."
              >
                {fieldName === "estado" ? (
                  <select
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                  >
                    {states.map((state) => (
                      <option key={state}>{state}</option>
                    ))}
                  </select>
                ) : fieldName === "activa" ? (
                  <select
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                  >
                    <option value="true">Sí</option>
                    <option value="false">No</option>
                  </select>
                ) : (
                  <input
                    type={
                      numericFields.has(fieldName) ||
                      typeof field?.value === "number"
                        ? "number"
                        : "text"
                    }
                    step={numericFields.has(fieldName) ? "any" : undefined}
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                  />
                )}
              </Field>
              <Field label="Motivo de la corrección">
                <textarea
                  required
                  minLength={3}
                  maxLength={1000}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Qué verificaste y por qué debe cambiar"
                />
              </Field>
              <div className="once-automation-actions">
                <button
                  className="v-btn v-btn-dark"
                  disabled={busy || !canCorrect}
                >
                  {busy ? "Guardando…" : "Guardar y proteger"}
                </button>
                {field.protected && (
                  <button
                    type="button"
                    className="v-btn v-btn-secondary"
                    disabled={busy || !canCorrect || reason.trim().length < 3}
                    onClick={() => save(true)}
                  >
                    Volver a aceptar la fuente
                  </button>
                )}
              </div>
            </form>
          )}
          <h3>Historial de esta ficha</h3>
          {!record.history?.length ? (
            <p>No hay cambios auditados en esta ficha.</p>
          ) : (
            <div className="once-automation-records">
              {record.history.map((change) => (
                <article key={change.id}>
                  <strong>
                    {labels[change.field] || change.field || "Cambio de ficha"}
                  </strong>
                  <p>
                    {displayValue(change.before)} → {displayValue(change.after)}
                  </p>
                  <p>{change.reason}</p>
                  <small>
                    {change.actor || "Proceso automático"} ·{" "}
                    {humanDate(change.created_at)}
                  </small>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
