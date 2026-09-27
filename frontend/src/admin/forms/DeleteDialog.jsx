import { Modal, Icon } from "../../AdminUI";

export function DeleteDialog({
  pendingDelete,
  deleting,
  setPendingDelete,
  setMensajeApi,
  deleteEntity,
  toast,
}) {
  return (
    <Modal
      title={pendingDelete.title}
      subtitle="Revisa el impacto antes de confirmar."
      eyebrow="ONCE / CONFIRMACIÓN DE BORRADO"
      busy={deleting}
      onClose={() => {
        if (!deleting) {
          setPendingDelete(null);
          setMensajeApi(null);
        }
      }}
    >
      <div className="v-confirm-body">
        <div className="v-confirm-entity">
          <Icon name="trash" />
          <strong>{pendingDelete.name}</strong>
        </div>
        <p>{pendingDelete.impact}</p>
        <p className="v-confirm-warning">
          Esta acción no se puede deshacer desde el panel.
        </p>
        <div className="v-form-footer">
          <button
            data-autofocus
            type="button"
            className="v-btn v-btn-secondary"
            disabled={deleting}
            onClick={() => {
              setPendingDelete(null);
              setMensajeApi(null);
            }}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="v-btn v-btn-danger"
            disabled={deleting}
            onClick={() => deleteEntity(pendingDelete.path)}
          >
            {deleting ? "Eliminando…" : "Eliminar registro"}
            <Icon name="trash" />
          </button>
        </div>
      </div>
      {toast}
    </Modal>
  );
}
