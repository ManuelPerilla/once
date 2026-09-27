import { useEffect, useState } from "react";
import { apiCollection } from "../../api";

function webUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}

export function CrestCredits() {
  const [open, setOpen] = useState(false);
  const [assets, setAssets] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!open || assets !== null) return;
    const controller = new AbortController();
    apiCollection("/public/crests/", { signal: controller.signal })
      .then(setAssets)
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => controller.abort();
  }, [open, assets]);

  return (
    <details
      className="once-crest-credits"
      onToggle={(event) => {
        setError(false);
        setOpen(event.currentTarget.open);
      }}
    >
      <summary>Escudos y sus autores</summary>
      <p>
        Consulta el origen y las condiciones de uso de los escudos añadidos
        desde Wikimedia Commons.
      </p>
      {error ? (
        <p role="status">
          No pudimos cargar los créditos. Cierra y vuelve a abrir esta sección
          para intentarlo de nuevo.
        </p>
      ) : assets === null ? (
        <p role="status">Cargando créditos…</p>
      ) : !assets.length ? (
        <p>Aún no hay escudos importados de Wikimedia Commons en uso.</p>
      ) : (
        <ul>
          {assets.map((asset) => (
            <li key={asset.id}>
              <a
                href={webUrl(asset.source_url)}
                target="_blank"
                rel="noopener noreferrer"
              >
                {asset.remote_id || "Ver archivo original"}
              </a>
              <span>
                {asset.author || "Autor indicado en el archivo original"}
              </span>
              {asset.credit && <span>{asset.credit}</span>}
              <a
                href={webUrl(asset.license_url) || webUrl(asset.source_url)}
                target="_blank"
                rel="noopener noreferrer"
              >
                {asset.license || "Consultar condiciones de uso"}
              </a>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}
