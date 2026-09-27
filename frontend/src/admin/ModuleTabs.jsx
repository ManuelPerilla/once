export function ModuleTabs({ items, value, onChange, label, id, panelId }) {
  return (
    <div className="once-module-tabs" role="tablist" aria-label={label}>
      {items.map((item, index) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          id={`${id}-${item.id}`}
          aria-selected={value === item.id}
          aria-controls={panelId}
          tabIndex={value === item.id ? 0 : -1}
          onClick={() => onChange(item.id)}
          onKeyDown={(event) => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
              return;
            event.preventDefault();
            const next =
              event.key === "Home"
                ? 0
                : event.key === "End"
                  ? items.length - 1
                  : (index +
                      (event.key === "ArrowRight" ? 1 : -1) +
                      items.length) %
                    items.length;
            onChange(items[next].id);
            document.getElementById(`${id}-${items[next].id}`)?.focus();
          }}
        >
          {item.label}
          {item.count !== undefined && <small>{item.count}</small>}
        </button>
      ))}
    </div>
  );
}
