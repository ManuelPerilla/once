export function DetailSections({ label, sections, current, onChange }) {
  return (
    <nav className="once-detail-sections once-tabs" aria-label={label}>
      {sections.map(([value, title, count]) => (
        <button
          key={value}
          type="button"
          aria-pressed={current === value}
          onClick={() => onChange(value)}
        >
          {title}
          {count !== undefined && <span>{count}</span>}
        </button>
      ))}
    </nav>
  );
}
