import { Icon } from "../../AdminUI";
export function FormActions({ loading, onClose }) {
  return (
    <div className="v-form-footer">
      <button type="button" className="v-btn v-btn-secondary" onClick={onClose}>
        Cancelar
      </button>
      <button type="submit" className="v-btn v-btn-dark" disabled={loading}>
        {loading ? "Guardando…" : "Guardar cambios"}
        <Icon name="check" />
      </button>
    </div>
  );
}
