export function Pagination({ page, pageSize, total, onChange, busy = false }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1 && page <= 1) return null;
  return (
    <nav className="once-pagination" aria-label="Páginas de resultados">
      <button
        className="v-btn v-btn-secondary"
        disabled={busy || page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Anterior
      </button>
      <span role="status">
        Página {page} de {pages} · {total} resultados
      </span>
      <button
        className="v-btn v-btn-secondary"
        disabled={busy || page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Siguiente
      </button>
    </nav>
  );
}
