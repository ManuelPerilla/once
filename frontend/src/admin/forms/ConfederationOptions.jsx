export function ConfederationOptions({ confederaciones }) {
  return (
    <>
      <option value="">Sin confederación</option>
      {confederaciones.map((c) => (
        <option key={c.id} value={c.id}>
          {c.nombre}
        </option>
      ))}
    </>
  );
}
