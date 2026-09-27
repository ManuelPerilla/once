import { Modal, Icon, Field } from "../../AdminUI";
import { FormActions } from "./FormActions";
import { useState } from "react";

export function ConfederationForm({
  editConfId,
  formConf,
  setFormConf,
  closeForms,
  handleSubmitConf,
  competiciones,
  equipos,
  asociarHuerfano,
  loading,
  toast,
}) {
  const [filtroPais, setFiltroPais] = useState("");
  const compsHuerfanasFiltradas = competiciones.filter(
    (c) =>
      !c.confederacion_id &&
      c.pais.toLowerCase().includes(filtroPais.toLowerCase()),
  );
  const eqsHuerfanosFiltrados = equipos.filter(
    (e) =>
      !e.confederacion_id &&
      e.pais.toLowerCase().includes(filtroPais.toLowerCase()),
  );

  return (
    <Modal
      title={editConfId ? "Editar confederación" : "Nueva confederación"}
      subtitle="Organiza las entidades de tu catálogo por confederación."
      onClose={closeForms}
    >
      <form
        className="v-form"
        id="confederation-form"
        onSubmit={handleSubmitConf}
      >
        <Field label="Nombre">
          <input
            value={formConf.nombre}
            onChange={(e) =>
              setFormConf({ ...formConf, nombre: e.target.value })
            }
            placeholder="Ej. CONMEBOL"
            required
          />
        </Field>
        <Field label="URL del logo">
          <input
            type="url"
            value={formConf.logo}
            onChange={(e) => setFormConf({ ...formConf, logo: e.target.value })}
            placeholder="https://…"
            required
          />
        </Field>
        <FormActions loading={loading} onClose={closeForms} />
      </form>
      {editConfId && (
        <details className="v-associate">
          <summary>Vincular entidades sin confederación</summary>
          <p>
            Revisa cada entidad antes de vincularla. Una competición global
            puede permanecer sin confederación.
          </p>
          <Field label="Filtrar por país">
            <input
              value={filtroPais}
              onChange={(e) => setFiltroPais(e.target.value)}
            />
          </Field>
          <div className="v-associate-list">
            {[
              ...compsHuerfanasFiltradas.map((item) => ({
                ...item,
                category: "competiciones",
              })),
              ...eqsHuerfanosFiltrados.map((item) => ({
                ...item,
                category: "equipos",
              })),
            ].map((item) => (
              <div key={`${item.category}-${item.id}`}>
                <span>
                  {item.nombre} · {item.pais}
                </span>
                <button
                  className="v-text-btn"
                  onClick={() => asociarHuerfano(item.category, item.id)}
                >
                  Vincular
                  <Icon name="link" />
                </button>
              </div>
            ))}
          </div>
        </details>
      )}
      {toast}
    </Modal>
  );
}
