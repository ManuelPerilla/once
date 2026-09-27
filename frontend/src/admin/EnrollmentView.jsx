import { Crest } from "../components/ui/Crest";
import { EmptyState } from "../components/ui/EmptyState";
import { Field } from "../components/ui/Field";
import { Icon } from "../components/ui/Icon";
import { ModuleTabs } from "./ModuleTabs";

export function EnrollmentView({
  form,
  setForm,
  competitions,
  availableTeams,
  loading,
  onEnroll,
  items,
  search,
  setSearch,
  onlyFree,
  setOnlyFree,
  context,
  setContext,
  total,
  mode,
  setMode,
}) {
  return (
    <div className="once-enrollment-workspace">
      <ModuleTabs
        items={[
          { id: "registry", label: "Registro de matrículas" },
          { id: "create", label: "Nueva matrícula" },
        ]}
        value={mode}
        onChange={setMode}
        label="Gestión de matrículas"
        id="enrollment-tab"
        panelId="enrollment-panel"
      />
      <p className="once-scope-note">
        Una matrícula relaciona un equipo con una competición. El modelo actual
        no la separa por temporada.
      </p>
      <div
        role="tabpanel"
        id="enrollment-panel"
        aria-labelledby={`enrollment-tab-${mode}`}
      >
        {mode === "create" ? (
          <section className="v-panel">
            <div className="v-panel-head">
              <div>
                <span className="v-eyebrow">01 / NUEVA CONEXIÓN</span>
                <h2>Nueva matrícula</h2>
                <p>Selecciona la competición y después el equipo.</p>
              </div>
              <Icon name="link" />
            </div>
            <form className="v-form" onSubmit={onEnroll}>
              <Field
                label={
                  <span className="v-step-title">
                    <span>1</span>Competición
                  </span>
                }
              >
                <select
                  id="matricula-competition"
                  value={form.competicion_id}
                  onChange={(event) =>
                    setForm({
                      competicion_id: event.target.value,
                      equipo_id: "",
                    })
                  }
                  required
                >
                  <option value="">Elige una competición</option>
                  {competitions.map((competition) => (
                    <option key={competition.id} value={competition.id}>
                      {competition.nombre}
                    </option>
                  ))}
                </select>
              </Field>

              <Field
                label={
                  <span className="v-step-title">
                    <span>2</span>Equipo compatible
                  </span>
                }
              >
                <select
                  disabled={!form.competicion_id}
                  value={form.equipo_id}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      equipo_id: event.target.value,
                    })
                  }
                  required
                >
                  <option value="">Elige un equipo</option>
                  {availableTeams.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.nombre}
                    </option>
                  ))}
                </select>
              </Field>

              <p className="v-notice">
                Solo aparecen equipos compatibles con el tipo, el país y la
                confederación del torneo.
              </p>

              {form.competicion_id && !availableTeams.length && (
                <p className="v-info-note">
                  No hay equipos disponibles. Puede que ya estén matriculados o
                  que necesites añadir un equipo compatible al catálogo.
                </p>
              )}

              <button
                disabled={loading || !form.equipo_id}
                className="v-btn v-btn-dark"
              >
                {loading ? "Guardando…" : "Confirmar matrícula"}
                <Icon name="check" />
              </button>
            </form>
          </section>
        ) : (
          <section className="v-panel">
            <div className="v-panel-head">
              <div>
                <span className="v-eyebrow">02 / PARTICIPACIÓN</span>
                <h2>Registro de matrículas</h2>
                <p role="status">
                  {items.length} de {total} equipos en esta vista.
                </p>
              </div>
            </div>

            <div className="v-filter-bar">
              <Field label="Buscar equipo">
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Nombre del equipo…"
                />
              </Field>
              <Field label="Filtrar por competición">
                <select
                  value={context.competition}
                  disabled={onlyFree}
                  onChange={(event) =>
                    setContext({ ...context, competition: event.target.value })
                  }
                >
                  <option value="">Todas las competiciones</option>
                  {competitions.map((competition) => (
                    <option key={competition.id} value={competition.id}>
                      {competition.nombre}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Tipo de participante">
                <select
                  value={context.type}
                  onChange={(event) =>
                    setContext({ ...context, type: event.target.value })
                  }
                >
                  <option value="">Clubes y selecciones</option>
                  <option value="club">Clubes</option>
                  <option value="seleccion">Selecciones</option>
                </select>
              </Field>
              <label className="v-checkbox">
                <input
                  type="checkbox"
                  checked={onlyFree}
                  onChange={(event) => {
                    setOnlyFree(event.target.checked);
                    if (event.target.checked)
                      setContext({ ...context, competition: "" });
                  }}
                />
                Solo sin matrícula
              </label>
              <button
                className="v-text-btn"
                onClick={() => {
                  setSearch("");
                  setOnlyFree(false);
                  setContext({ competition: "", type: "" });
                }}
              >
                Limpiar filtros de matrículas
              </button>
            </div>

            <div className="v-registration-list">
              {items.map((team) => (
                <article className="v-catalog-row" key={team.id}>
                  <Crest name={team.nombre} src={team.logo} />
                  <div className="v-entity-name">
                    <strong>{team.nombre}</strong>
                    <span>
                      {team.tipo === "seleccion" ? "Selección" : "Club"} ·{" "}
                      {team.pais}
                    </span>
                    <div className="v-entity-tags">
                      {team.competiciones?.length ? (
                        team.competiciones.map((competition) => (
                          <span key={competition.id}>{competition.nombre}</span>
                        ))
                      ) : (
                        <span>Sin matrícula</span>
                      )}
                    </div>
                  </div>
                </article>
              ))}
              {!items.length && (
                <EmptyState title="Sin equipos en esta vista" icon="link">
                  Ajusta la búsqueda o añade equipos desde el catálogo.
                </EmptyState>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
