import { useEffect, useRef } from "react";
import { Icon } from "./Icon";

export function Modal({
  title,
  subtitle,
  onClose,
  children,
  busy = false,
  eyebrow = "ONCE / MESA DE EDICIÓN",
}) {
  const ref = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    dialog.querySelector("[data-autofocus]")?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      dialog.close();
      document.body.style.overflow = previous;
    };
  }, []);

  return (
    <dialog
      ref={ref}
      className="v-dialog"
      aria-labelledby="editor-title"
      aria-busy={busy || undefined}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <div className="v-dialog-head">
        <div>
          <span className="v-eyebrow">{eyebrow}</span>
          <h2 id="editor-title">{title}</h2>
          <p>{subtitle}</p>
        </div>
        <button
          type="button"
          className="v-icon-btn"
          onClick={onClose}
          disabled={busy}
          aria-label="Cerrar formulario"
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
