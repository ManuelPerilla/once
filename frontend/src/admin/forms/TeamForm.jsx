import { Modal, Field } from "../../AdminUI";
import { FormActions } from "./FormActions";
import { ConfederationOptions } from "./ConfederationOptions";

export function TeamForm({
  editEqId,
  formEquipo,
  setFormEquipo,
  closeForms,
  handleSubmitEquipo,
  confederaciones,
  loading,
  toast,
}) {
  return (
    <Modal
      title={editEqId ? "Editar equipo" : "Nuevo equipo"}
      subtitle="Añade sus datos básicos. Podrás matricularlo en una competición después."
      onClose={closeForms}
    >
      <form className="v-form" id="team-form" onSubmit={handleSubmitEquipo}>
        <Field label="Nombre">
          <input
            value={formEquipo.nombre}
            onChange={(e) =>
              setFormEquipo({ ...formEquipo, nombre: e.target.value })
            }
            placeholder="Ej. Deportes Tolima"
            required
          />
        </Field>
        <div className="v-form-grid">
          <Field label="Tipo de equipo">
            <select
              value={formEquipo.tipo}
              onChange={(e) =>
                setFormEquipo({ ...formEquipo, tipo: e.target.value })
              }
            >
              <option value="club">Club</option>
              <option value="seleccion">Selección</option>
            </select>
          </Field>
          <Field
            label="País"
            hint={
              formEquipo.tipo === "seleccion"
                ? "El país toma el nombre de la selección."
                : undefined
            }
          >
            <input
              value={
                formEquipo.tipo === "seleccion"
                  ? formEquipo.nombre
                  : formEquipo.pais
              }
              disabled={formEquipo.tipo === "seleccion"}
              onChange={(e) =>
                setFormEquipo({ ...formEquipo, pais: e.target.value })
              }
              required
            />
          </Field>
        </div>
        <Field label="Confederación">
          <select
            value={formEquipo.confederacion_id}
            onChange={(e) =>
              setFormEquipo({
                ...formEquipo,
                confederacion_id: e.target.value,
              })
            }
          >
            <ConfederationOptions confederaciones={confederaciones} />
          </select>
        </Field>
        <Field label="URL del escudo">
          <input
            type="url"
            value={formEquipo.logo}
            onChange={(e) =>
              setFormEquipo({ ...formEquipo, logo: e.target.value })
            }
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
