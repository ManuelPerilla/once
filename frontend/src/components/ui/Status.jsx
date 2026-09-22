export function Status({ value }) {
  const label =
    {
      programado: "Programado",
      "en vivo": "En vivo",
      finalizado: "Finalizado",
    }[value] || value;

  return (
    <span className={`v-status v-status-${value?.replace(" ", "-")}`}>
      <i />
      {label}
    </span>
  );
}
