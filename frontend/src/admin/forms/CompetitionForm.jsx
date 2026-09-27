import { Modal, Field } from "../../AdminUI";
import { FormActions } from "./FormActions";
import { ConfederationOptions } from "./ConfederationOptions";
import { COMPETITION_TYPES } from "../../catalogFilters";

export function CompetitionForm({
  editCompId,
  formComp,
  setFormComp,
  closeForms,
  handleSubmitComp,
  confederaciones,
  loading,
  toast,
}) {
  return (
    <Modal
      title={editCompId ? "Editar competición" : "Nueva competición"}
      subtitle="Define el torneo y qué tipo de equipos puede recibir."
      onClose={closeForms}
    >
      <form
        className="v-form"
        id="competition-form"
        onSubmit={handleSubmitComp}
      >
        <Field label="Nombre">
          <input
            value={formComp.nombre}
            onChange={(e) =>
              setFormComp({ ...formComp, nombre: e.target.value })
            }
            placeholder="Ej. Liga BetPlay Dimayor"
            required
          />
        </Field>
        <div className="v-form-grid">
          <Field label="Tipo de competición">
            <select
              value={formComp.tipo}
              onChange={(e) =>
                setFormComp({ ...formComp, tipo: e.target.value })
              }
            >
              {Object.entries(COMPETITION_TYPES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="País / ámbito">
            <input
              value={
                ["liga_nacional", "copa_nacional"].includes(formComp.tipo)
                  ? formComp.pais
                  : "Internacional"
              }
              disabled={
                !["liga_nacional", "copa_nacional"].includes(formComp.tipo)
              }
              onChange={(e) =>
                setFormComp({ ...formComp, pais: e.target.value })
              }
              required
            />
          </Field>
        </div>
        <Field
          label="Confederación"
          hint="Las competiciones globales pueden quedar sin confederación."
        >
          <select
            value={formComp.confederacion_id}
            onChange={(e) =>
              setFormComp({ ...formComp, confederacion_id: e.target.value })
            }
          >
            <ConfederationOptions confederaciones={confederaciones} />
          </select>
        </Field>
        <Field label="URL del logo">
          <input
            type="url"
            value={formComp.logo}
            onChange={(e) => setFormComp({ ...formComp, logo: e.target.value })}
            placeholder="https://…"
            required
          />
        </Field>
        <FormActions loading={loading} onClose={closeForms} />
      </form>
      {toast}
    </Modal>
  );
}
