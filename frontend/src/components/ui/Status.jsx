export function Status({ value }) {
  const label =
    {
      programado: "Programado",
      "en vivo": "En vivo",
      finalizado: "Finalizado",
      aplazado: "Aplazado",
      suspendido: "Suspendido",
      cancelado: "Cancelado",
      abandonado: "Abandonado",
      adjudicado: "Adjudicado",
      desconocido: "Por confirmar",
    }[value] || value;

  return (
    <span className={`v-status v-status-${value?.replace(" ", "-")}`}>
      <i />
      {label}
    </span>
  );
}
