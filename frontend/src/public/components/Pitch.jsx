export function Pitch({ children, label = "ONCE / VISIÓN DE JUEGO", compact = false }) {
  return (
    <div className={`p-pitch-card ${compact ? "p-pitch-card-compact" : ""}`}>
      <svg viewBox="0 0 800 500" role="img" aria-label="Representación de una cancha de fútbol">
        <rect x="12" y="12" width="776" height="476" rx="2" />
        <line x1="400" y1="12" x2="400" y2="488" />
        <circle cx="400" cy="250" r="72" />
        <circle cx="400" cy="250" r="4" />
        <rect x="12" y="145" width="120" height="210" />
        <rect x="668" y="145" width="120" height="210" />
        <rect x="12" y="195" width="48" height="110" />
        <rect x="740" y="195" width="48" height="110" />
        <circle cx="96" cy="250" r="4" />
        <circle cx="704" cy="250" r="4" />
        <path d="M132 190a72 72 0 0 1 0 120M668 190a72 72 0 0 0 0 120" />
      </svg>
      {children}
      <span>{label}</span>
    </div>
  );
}
