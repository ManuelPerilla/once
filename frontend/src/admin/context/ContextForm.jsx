import { useEffect, useRef, useState } from "react";
import { Field, Modal } from "../../AdminUI";
import { apiRequest } from "../../api";
import { contextModuleNames, contextPayload } from "./selectors";

function initialValues(module, filters, data) {
  const values = { nombre: "" };
  if (module === "temporadas")
    return {
      ...values,
      competicion_id: filters.competition,
      fecha_inicio: "",
      fecha_fin: "",
      activa: false,
    };
  if (module === "fases")
    return {
      ...values,
      competicion_id:
        filters.competition ||
        String(
          (data.temporadas || []).find(
            (item) => String(item.id) === filters.season,
          )?.competicion_id || "",
        ),
      temporada_id: filters.season,
      tipo: "jornada",
      orden: "0",
    };
  if (module === "estadios")
    return {
      ...values,
      ciudad: filters.city,
      pais: filters.country,
      latitud: "",
      longitud: "",
    };
  return {
    ...values,
    nombre_completo: "",
    posicion: filters.position,
    nacionalidad: filters.country,
    fecha_nacimiento: "",
  };
}

export function ContextForm({
  module,
  data,
  filters,
  onClose,
  onCreated,
  onError,
}) {
  const [values, setValues] = useState(() =>
    initialValues(module, filters, data),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  const update = (name, value) =>
    setValues((current) => ({
      ...current,
      [name]: value,
      ...(name === "competicion_id" ? { temporada_id: "" } : {}),
    }));
  const field = (name, label, props = {}) => (
    <Field label={label} key={name}>
      <input
        value={values[name] ?? ""}
        onChange={(event) => update(name, event.target.value)}
        {...props}
      />
    </Field>
  );
  const seasons = (data.temporadas || []).filter(
    (item) => String(item.competicion_id) === values.competicion_id,
  );

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setError("");
    let body;
    try {
      body = contextPayload(module, values);
    } catch (failure) {
      setError(failure.message);
      return;
    }
    setBusy(true);
    const controller = new AbortController();
    request.current = controller;
    let record;
    try {
      record = await apiRequest(`/${module}/`, {
        method: "POST",
        body,
        signal: controller.signal,
      });
    } catch (failure) {
      if (controller.signal.aborted) return;
      setError(
        failure.message ||
          "No se pudo guardar. Revisa la conexión e inténtalo de nuevo.",
      );
      setBusy(false);
      if (failure.status === 401) onError?.(failure);
      return;
    }
    if (!controller.signal.aborted) onCreated(record);
  }

  return (
    <Modal
      title={contextModuleNames[module].create}
      subtitle="Completa la ficha y revisa los datos antes de guardarlos."
      eyebrow={contextModuleNames[module].title}
      onClose={onClose}
      busy={busy}
    >
      <form className="v-form once-context-form" onSubmit={submit}>
        <fieldset disabled={busy}>
          {field("nombre", "Nombre", {
            required: true,
            maxLength: 200,
            "data-autofocus": true,
            placeholder:
              module === "temporadas"
                ? "Ej. 2026 · Apertura"
                : module === "fases"
                  ? "Ej. Jornada 1"
                  : undefined,
          })}
          {["temporadas", "fases"].includes(module) && (
            <Field label="Competición">
              <select
                value={values.competicion_id}
                onChange={(event) =>
                  update("competicion_id", event.target.value)
                }
                required
              >
                <option value="">Elige una competición</option>
                {(data.competiciones || []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nombre}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {module === "temporadas" && (
            <>
              <div className="v-form-grid">
                {field("fecha_inicio", "Fecha de inicio (opcional)", {
                  type: "date",
                })}
                {field("fecha_fin", "Fecha de fin (opcional)", {
                  type: "date",
                  min: values.fecha_inicio || undefined,
                })}
              </div>
              <label className="once-context-checkbox">
                <input
                  type="checkbox"
                  checked={values.activa}
                  onChange={(event) => update("activa", event.target.checked)}
                />
                Esta temporada está activa
              </label>
            </>
          )}
          {module === "fases" && (
            <>
              <Field
                label="Temporada"
                hint={
                  !values.competicion_id
                    ? "Primero elige la competición."
                    : !seasons.length
                      ? "Esta competición necesita una temporada antes de añadir fases."
                      : undefined
                }
              >
                <select
                  value={values.temporada_id}
                  onChange={(event) =>
                    update("temporada_id", event.target.value)
                  }
                  required
                  disabled={!values.competicion_id || !seasons.length}
                >
                  <option value="">Elige una temporada</option>
                  {seasons.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.nombre}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="v-form-grid">
                <Field label="Tipo de fase">
                  <select
                    value={values.tipo}
                    onChange={(event) => update("tipo", event.target.value)}
                  >
                    <option value="jornada">Jornada</option>
                    <option value="grupo">Grupo</option>
                    <option value="eliminatoria">Eliminatoria</option>
                    <option value="final">Final</option>
                    <option value="otra">Otra fase</option>
                  </select>
                </Field>
                {field("orden", "Orden dentro de la temporada", {
                  type: "number",
                  min: 0,
                  step: 1,
                  required: true,
                })}
              </div>
            </>
          )}
          {module === "estadios" && (
            <>
              <div className="v-form-grid">
                {field("pais", "País (opcional)", {
                  autoComplete: "country-name",
                })}
                {field("ciudad", "Ciudad (opcional)")}
              </div>
              <details className="once-context-optional">
                <summary>Ubicación exacta (opcional)</summary>
                <p>Usa coordenadas decimales si conoces la ubicación.</p>
                <div className="v-form-grid">
                  {field("latitud", "Latitud", {
                    type: "number",
                    min: -90,
                    max: 90,
                    step: "any",
                  })}
                  {field("longitud", "Longitud", {
                    type: "number",
                    min: -180,
                    max: 180,
                    step: "any",
                  })}
                </div>
              </details>
            </>
          )}
          {module === "jugadores" && (
            <>
              {field("nombre_completo", "Nombre completo (opcional)")}
              <div className="v-form-grid">
                {field("nacionalidad", "Nacionalidad (opcional)")}
                {field("posicion", "Posición (opcional)", {
                  placeholder: "Ej. Delantero",
                })}
              </div>
              {field("fecha_nacimiento", "Fecha de nacimiento (opcional)", {
                type: "date",
                max: new Date().toLocaleDateString("en-CA"),
              })}
              <p className="once-context-help">
                Esta ficha identifica al jugador. Su pertenencia a equipos
                requiere una relación deportiva independiente.
              </p>
            </>
          )}
        </fieldset>
        {error && (
          <p className="once-context-error" role="alert">
            {error}
          </p>
        )}
        <div className="once-context-actions">
          <button
            className="v-btn v-btn-secondary"
            type="button"
            disabled={busy}
            onClick={onClose}
          >
            Cancelar
          </button>
          <button
            className="v-btn v-btn-primary"
            type="submit"
            disabled={busy || (module === "fases" && !values.temporada_id)}
          >
            {busy ? "Guardando…" : "Guardar ficha"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
