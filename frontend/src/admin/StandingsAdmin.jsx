import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Field } from "../AdminUI";
import { SourceEntitySelect } from "./SourceEntitySelect";
import { ModuleTabs } from "./ModuleTabs";

const criteria = {
  goal_difference: "Diferencia de goles",
  goals_for: "Goles a favor",
  wins: "Partidos ganados",
  away_goals_for: "Goles como visitante",
  away_wins: "Victorias como visitante",
  head_to_head_points: "Puntos en enfrentamientos directos",
  head_to_head_goal_difference: "Diferencia de goles entre empatados",
  head_to_head_goals_for: "Goles a favor entre empatados",
};
const emptyRule = () => ({
  name: "",
  source_url: "",
  verified: false,
  config: {
    points_win: 3,
    points_draw: 1,
    points_loss: 0,
    tiebreakers: ["goal_difference", "goals_for"],
    include_awarded: false,
    included_phase_ids: null,
  },
});

export function StandingsAdmin({ onError, canCorrect = false }) {
  const [seasonId, setSeasonId] = useState("");
  const [phaseId, setPhaseId] = useState("");
  const [groupId, setGroupId] = useState("");
  const [context, setContext] = useState({ phases: [], groups: [] });
  const [rules, setRules] = useState([]);
  const [tab, setTab] = useState("rules");
  const [form, setForm] = useState(emptyRule);
  const [teamId, setTeamId] = useState("");
  const [reason, setReason] = useState("");
  const [points, setPoints] = useState(-1);
  const [source, setSource] = useState("");
  const [groupName, setGroupName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!seasonId) return;
    const controller = new AbortController();
    Promise.all([
      apiRequest(`/public/temporadas/${seasonId}/context`, {
        signal: controller.signal,
      }),
      apiRequest(`/football/reglas?season_id=${seasonId}`, {
        signal: controller.signal,
      }),
    ])
      .then(([details, versions]) => {
        setContext(details);
        setRules(versions);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          if (failure.status === 401) onError(failure);
        }
      });
    return () => controller.abort();
  }, [seasonId, revision, onError]);
  const scope = {
    temporada_id: Number(seasonId),
    fase_id: phaseId ? Number(phaseId) : null,
    grupo_id: groupId ? Number(groupId) : null,
  };
  const selectedRules = rules.filter(
    (rule) =>
      (rule.fase_id || null) === scope.fase_id &&
      (rule.grupo_id || null) === scope.grupo_id,
  );
  const setConfig = (key, value) =>
    setForm((current) => ({
      ...current,
      config: { ...current.config, [key]: value },
    }));
  const save = async (path, body, text) => {
    if (!canCorrect) {
      setError(
        "Tu cuenta tiene acceso de consulta. Solicita a una persona con permiso de edición que registre este cambio.",
      );
      return false;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiRequest(path, { method: "POST", body });
      setMessage(text);
      setRevision((value) => value + 1);
      return true;
    } catch (failure) {
      setError(failure.message);
      if (failure.status === 401) onError(failure);
      return false;
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="v-panel once-rules-admin">
      <div className="once-module-intro">
        <h3>Una tabla necesita reglas verificadas.</h3>
        <p>
          Define a qué edición, fase y grupo se aplica el reglamento. ONCE
          mantiene cada versión y conserva separada la tabla recibida de la
          fuente.
        </p>
      </div>
      <div className="once-automation-fields">
        <SourceEntitySelect
          type="season"
          label="Temporada que quieres revisar"
          value={seasonId}
          onChange={(value) => {
            setSeasonId(value);
            setPhaseId("");
            setGroupId("");
            setRules([]);
            setContext({ phases: [], groups: [] });
            setForm(emptyRule());
            setMessage("");
          }}
        />
        <Field label="Fase del reglamento">
          <select
            disabled={!seasonId}
            value={phaseId}
            onChange={(event) => {
              setPhaseId(event.target.value);
              setGroupId("");
              setForm(emptyRule());
            }}
          >
            <option value="">Toda la temporada</option>
            {context.phases.map((phase) => (
              <option key={phase.id} value={phase.id}>
                {phase.nombre}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Grupo del reglamento">
          <select
            disabled={!phaseId}
            value={groupId}
            onChange={(event) => {
              setGroupId(event.target.value);
              setForm(emptyRule());
            }}
          >
            <option value="">Todos los participantes de la fase</option>
            {context.groups
              .filter((group) => String(group.fase_id) === phaseId)
              .map((group) => (
                <option key={group.id} value={group.id}>
                  {group.nombre}
                </option>
              ))}
          </select>
        </Field>
      </div>
      {error && (
        <p role="alert" className="once-automation-error">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="once-automation-success">
          {message}
        </p>
      )}
      {seasonId && (
        <>
          <ModuleTabs
            items={[
              { id: "rules", label: "Reglamento" },
              { id: "participants", label: "Corregir participación" },
              { id: "adjustment", label: "Ajustes de puntos" },
              { id: "groups", label: "Grupos" },
            ]}
            value={tab}
            onChange={setTab}
            label="Operaciones deportivas"
            id="sport-tab"
            panelId="sport-panel"
          />
          <div
            role="tabpanel"
            id="sport-panel"
            aria-labelledby={`sport-tab-${tab}`}
          >
            {tab === "rules" && (
              <>
                {selectedRules.length > 0 && (
                  <div className="once-automation-records">
                    {selectedRules.map((rule) => (
                      <article key={rule.id}>
                        <strong>
                          {rule.name} · Versión {rule.version}
                        </strong>
                        <p>
                          {rule.verified
                            ? "Verificada por un administrador"
                            : "Pendiente de verificar"}
                        </p>
                        <a
                          href={rule.source_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Consultar reglamento
                        </a>
                        <button
                          className="v-text-btn"
                          onClick={() =>
                            setForm({
                              name: rule.name,
                              source_url: rule.source_url,
                              verified: false,
                              config: rule.config,
                            })
                          }
                        >
                          Preparar una nueva versión
                        </button>
                      </article>
                    ))}
                  </div>
                )}
                <form
                  className="once-rules-form"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    if (
                      await save(
                        "/football/reglas",
                        { ...scope, ...form },
                        "Versión de reglamento guardada. La clasificación se reconstruye cuando sus datos y reglas son suficientes.",
                      )
                    )
                      setForm(emptyRule());
                  }}
                >
                  <h3>
                    {selectedRules.length
                      ? "Nueva versión"
                      : "Primer reglamento de esta selección"}
                  </h3>
                  <Field label="Nombre del reglamento">
                    <input
                      required
                      minLength={3}
                      maxLength={200}
                      value={form.name}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      }
                      placeholder="Por ejemplo, Liga I 2026 · fase regular"
                    />
                  </Field>
                  <Field label="Enlace al reglamento o comunicación oficial">
                    <input
                      type="url"
                      required
                      value={form.source_url}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          source_url: event.target.value,
                        }))
                      }
                      placeholder="https://…"
                    />
                  </Field>
                  <div className="once-automation-fields">
                    {[
                      ["points_win", "Puntos por victoria"],
                      ["points_draw", "Puntos por empate"],
                      ["points_loss", "Puntos por derrota"],
                    ].map(([key, label]) => (
                      <Field key={key} label={label}>
                        <input
                          required
                          type="number"
                          min="0"
                          max="10"
                          value={form.config[key]}
                          onChange={(event) =>
                            setConfig(key, Number(event.target.value))
                          }
                        />
                      </Field>
                    ))}
                  </div>
                  <fieldset className="once-rule-criteria">
                    <legend>Desempates, en el orden del reglamento</legend>
                    {form.config.tiebreakers.map((criterion, index) => (
                      <div key={`${index}-${criterion}`}>
                        <span>{index + 1}.</span>
                        <select
                          aria-label={`Desempate ${index + 1}`}
                          value={criterion}
                          onChange={(event) =>
                            setConfig(
                              "tiebreakers",
                              form.config.tiebreakers.map((item, i) =>
                                i === index ? event.target.value : item,
                              ),
                            )
                          }
                        >
                          {Object.entries(criteria)
                            .filter(
                              ([value]) =>
                                value === criterion ||
                                !form.config.tiebreakers.includes(value),
                            )
                            .map(([value, label]) => (
                              <option key={value} value={value}>
                                {label}
                              </option>
                            ))}
                        </select>
                        <button
                          type="button"
                          className="v-text-btn"
                          onClick={() =>
                            setConfig(
                              "tiebreakers",
                              form.config.tiebreakers.filter(
                                (_, i) => i !== index,
                              ),
                            )
                          }
                        >
                          Quitar
                        </button>
                      </div>
                    ))}
                    {form.config.tiebreakers.length <
                      Object.keys(criteria).length && (
                      <button
                        type="button"
                        className="v-text-btn"
                        onClick={() =>
                          setConfig("tiebreakers", [
                            ...form.config.tiebreakers,
                            Object.keys(criteria).find(
                              (key) => !form.config.tiebreakers.includes(key),
                            ),
                          ])
                        }
                      >
                        Añadir siguiente desempate
                      </button>
                    )}
                  </fieldset>
                  {!phaseId && context.phases.length > 0 && (
                    <fieldset className="once-rule-criteria">
                      <legend>Fases incluidas en la clasificación</legend>
                      <p>
                        Marca las fases si esta tabla acumula resultados de una
                        selección concreta.
                      </p>
                      {context.phases.map((phase) => (
                        <label key={phase.id}>
                          <input
                            type="checkbox"
                            checked={
                              form.config.included_phase_ids?.includes(
                                phase.id,
                              ) || false
                            }
                            onChange={(event) => {
                              const ids = event.target.checked
                                ? [
                                    ...(form.config.included_phase_ids || []),
                                    phase.id,
                                  ]
                                : (form.config.included_phase_ids || []).filter(
                                    (id) => id !== phase.id,
                                  );
                              setConfig(
                                "included_phase_ids",
                                ids.length ? ids : null,
                              );
                            }}
                          />
                          {phase.nombre}
                        </label>
                      ))}
                    </fieldset>
                  )}
                  <label className="once-rule-check">
                    <input
                      type="checkbox"
                      checked={form.config.include_awarded}
                      onChange={(event) =>
                        setConfig("include_awarded", event.target.checked)
                      }
                    />
                    Incluir resultados adjudicados administrativamente
                  </label>
                  <label className="once-rule-check">
                    <input
                      type="checkbox"
                      checked={form.verified}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          verified: event.target.checked,
                        }))
                      }
                    />
                    He contrastado estos puntos, desempates y ámbito con el
                    reglamento enlazado.
                  </label>
                  <p className="once-automation-help">
                    Si hay criterios reglamentarios que no aparecen aquí, guarda
                    sin verificar y deja el cálculo pendiente. No es una tabla
                    de promedios ni una proyección en vivo.
                  </p>
                  <button
                    className="v-btn v-btn-dark"
                    disabled={busy || !canCorrect}
                  >
                    {busy ? "Guardando…" : "Guardar versión de reglamento"}
                  </button>
                </form>
              </>
            )}
            {tab === "participants" && (
              <form
                className="once-rules-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  await save(
                    `/football/temporadas/${seasonId}/participantes`,
                    {
                      equipo_id: Number(teamId),
                      fase_id: scope.fase_id,
                      grupo_id: scope.grupo_id,
                      reason,
                    },
                    "Participación registrada en el ámbito seleccionado.",
                  );
                }}
              >
                <p>
                  Usa esta corrección para una inscripción concreta que la
                  fuente no haya podido resolver. La importación automática
                  gestiona el resto.
                </p>
                <SourceEntitySelect
                  type="team"
                  label="Equipo participante"
                  value={teamId}
                  onChange={setTeamId}
                />
                <Field label="Motivo de la corrección de participación">
                  <textarea
                    required
                    minLength={3}
                    maxLength={1000}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </Field>
                <button
                  className="v-btn v-btn-dark"
                  disabled={busy || !canCorrect || !teamId}
                >
                  Guardar participación
                </button>
              </form>
            )}
            {tab === "adjustment" && (
              <form
                className="once-rules-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  if (
                    await save(
                      "/football/ajustes",
                      {
                        ...scope,
                        equipo_id: Number(teamId),
                        points: Number(points),
                        reason,
                        source_url: source,
                      },
                      "Ajuste registrado. La clasificación conservará su motivo y procedencia.",
                    )
                  )
                    setReason("");
                }}
              >
                <p>
                  Registra una sanción o restitución publicada. Usa números
                  negativos para descontar puntos y positivos para restituirlos.
                </p>
                <SourceEntitySelect
                  type="team"
                  label="Equipo afectado"
                  value={teamId}
                  onChange={setTeamId}
                />
                <Field label="Puntos del ajuste">
                  <input
                    required
                    type="number"
                    min="-100"
                    max="100"
                    value={points}
                    onChange={(event) => setPoints(event.target.value)}
                  />
                </Field>
                <Field label="Motivo del ajuste">
                  <textarea
                    required
                    minLength={3}
                    maxLength={1000}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </Field>
                <Field label="Enlace a la resolución oficial">
                  <input
                    type="url"
                    required
                    value={source}
                    onChange={(event) => setSource(event.target.value)}
                  />
                </Field>
                <button
                  className="v-btn v-btn-dark"
                  disabled={busy || !canCorrect || !teamId}
                >
                  Registrar ajuste
                </button>
              </form>
            )}
            {tab === "groups" && (
              <form
                className="once-rules-form"
                onSubmit={async (event) => {
                  event.preventDefault();
                  if (
                    await save(
                      "/football/grupos",
                      { fase_id: Number(phaseId), nombre: groupName },
                      "Grupo añadido a la fase seleccionada.",
                    )
                  )
                    setGroupName("");
                }}
              >
                <p>
                  Los grupos pertenecen a una fase. Selecciona primero la fase
                  en los filtros superiores.
                </p>
                <Field label="Nombre del grupo">
                  <input
                    required
                    maxLength={100}
                    value={groupName}
                    onChange={(event) => setGroupName(event.target.value)}
                    placeholder="Por ejemplo, Grupo A"
                  />
                </Field>
                <button
                  className="v-btn v-btn-dark"
                  disabled={busy || !canCorrect || !phaseId}
                >
                  Guardar grupo
                </button>
              </form>
            )}
          </div>
        </>
      )}
    </section>
  );
}
