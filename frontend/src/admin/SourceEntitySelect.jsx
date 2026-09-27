import { useEffect, useState } from "react";
import { apiCollection, apiRequest } from "../api";
import { Pagination } from "../components/ui/Pagination";

const paths = {
  confederation: "/confederaciones/",
  competition: "/competiciones/",
  team: "/equipos/",
  match: "/partidos/",
  season: "/temporadas/",
  venue: "/estadios/",
  player: "/jugadores/",
  stage: "/fases/",
};

function recordName(record, type) {
  if (type !== "match") return record.nombre || `Registro ${record.id}`;
  const teams = `${record.equipo_local?.nombre || "Local"} vs ${record.equipo_visitante?.nombre || "Visitante"}`;
  const date = record.fecha
    ? new Date(record.fecha).toLocaleDateString("es-CO")
    : "Sin fecha";
  return `${teams} · ${date}`;
}

export function SourceEntitySelect({
  type,
  label,
  value,
  onChange,
  disabled,
  competitionId,
  refreshKey = 0,
  emptyMessage,
  allowIds,
  required = true,
}) {
  const [result, setResult] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const paged = ["team", "match", "player"].includes(type);
  const loading = result?.type !== type || result?.refreshKey !== refreshKey;
  const records = loading ? [] : result.records;
  const error = loading ? "" : result.error;

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ page, page_size: "30", search });
    if (competitionId) query.set("competition_id", competitionId);
    const promise = paged
      ? apiRequest(`/public${paths[type]}page?${query}`, {
          signal: controller.signal,
        })
      : apiCollection(paths[type], { signal: controller.signal }).then(
          (items) => ({ items, total: items.length }),
        );
    promise
      .then(async ({ items, total }) => {
        if (
          paged &&
          value &&
          !items.some((item) => String(item.id) === String(value))
        ) {
          const selected = await apiRequest(`/public${paths[type]}${value}`, {
            signal: controller.signal,
          });
          items = [selected, ...items];
        }
        if (!controller.signal.aborted)
          setResult({ type, refreshKey, records: items, total, error: "" });
      })
      .catch((failure) => {
        if (!controller.signal.aborted)
          setResult({ type, refreshKey, records: [], error: failure.message });
      });
    return () => controller.abort();
  }, [type, refreshKey, paged, page, search, competitionId, value]);

  const options = records.filter(
    (item) =>
      (!competitionId ||
        String(item.competicion_id) === String(competitionId)) &&
      (!allowIds || allowIds.includes(item.id)),
  );

  return (
    <div className="once-entity-picker">
      {paged && (
        <label>
          <span>Buscar por nombre</span>
          <input
            type="search"
            aria-label={`Buscar: ${label}`}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Escribe un nombre para acotar la lista"
          />
        </label>
      )}
      <label>
        <span>{label}</span>
        <select
          aria-label={label}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled || loading || !options.length}
          required={required}
        >
          <option value="">
            {loading ? "Cargando nombres…" : "Elige una opción"}
          </option>
          {options.map((record) => (
            <option key={record.id} value={record.id}>
              {recordName(record, type)}
            </option>
          ))}
        </select>
        {error ? (
          <small role="alert">No pudimos cargar la lista: {error}</small>
        ) : (
          !loading &&
          !options.length && (
            <small>
              {emptyMessage ||
                "Todavía no hay registros de este tipo. Añádelos primero al catálogo."}
            </small>
          )
        )}
      </label>
      {paged && (
        <Pagination
          page={page}
          pageSize={30}
          total={result?.total || 0}
          onChange={setPage}
        />
      )}
    </div>
  );
}
