import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Modal, EmptyState, MatchRow } from "../AdminUI";
import { ModuleTabs } from "./ModuleTabs";

const tabs = [
  { id: "context", label: "Ficha" },
  { id: "statistics", label: "Estadísticas" },
  { id: "events", label: "Eventos" },
  { id: "lineups", label: "Alineaciones" },
];
const sourceName = (source) =>
  source === "api-football" ? "API-Football" : source || "Origen no registrado";

export function MatchDetailView({ id, onClose, onError }) {
  const [tab, setTab] = useState("context");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    apiRequest(`/partidos/${id}`, { signal: controller.signal })
      .then((match) => {
        const names = new Map();
        for (const item of [
          ...(match.alineaciones || []),
          ...(match.eventos || []),
        ]) {
          if (item.jugador_id && item.jugador_nombre)
            names.set(item.jugador_id, item.jugador_nombre);
          if (item.asistente_id && item.asistente_nombre)
            names.set(item.asistente_id, item.asistente_nombre);
        }
        if (!controller.signal.aborted)
          setResult({
            match,
            players: [...names].map(([id, nombre]) => ({ id, nombre })),
          });
      })
      .catch((failure) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          if (failure.status === 401) onError(failure);
        }
      });
    return () => controller.abort();
  }, [id, retry, onError]);
  const match = result?.match;
  const teamName = (teamId) =>
    [match?.equipo_local, match?.equipo_visitante].find(
      (team) => team?.id === teamId,
    )?.nombre || "Equipo sin identificar";
  const playerName = (playerId) =>
    result?.players.find((player) => player.id === playerId)?.nombre ||
    (playerId ? "Jugador sin identificar" : "Jugador no indicado");
  return (
    <Modal
      title="Ficha del partido"
      subtitle="Una sola ficha, con vistas separadas para cada tipo de información."
      onClose={onClose}
      eyebrow="ONCE / CONSULTA DEL ENCUENTRO"
    >
      <div className="once-match-detail">
        {error ? (
          <div role="alert">
            <p>{error}</p>
            <button
              className="v-btn"
              onClick={() => {
                setError("");
                setRetry((value) => value + 1);
              }}
            >
              Reintentar consulta
            </button>
          </div>
        ) : !result ? (
          <p role="status">Consultando el partido…</p>
        ) : (
          <>
            <MatchRow match={match} />
            <ModuleTabs
              items={tabs}
              value={tab}
              onChange={setTab}
              label="Información del partido"
              id="detail-tab"
              panelId="detail-panel"
            />
            <div
              role="tabpanel"
              id="detail-panel"
              aria-labelledby={`detail-tab-${tab}`}
            >
              {tab === "context" && (
                <dl className="once-detail-fields">
                  {[
                    ["Competición", match.competicion?.nombre],
                    ["Temporada", match.temporada?.nombre],
                    ["Fase", match.fase?.nombre],
                    ["Estadio", match.estadio?.nombre],
                    [
                      "Fecha",
                      match.fecha
                        ? new Date(match.fecha).toLocaleString("es")
                        : null,
                    ],
                    ["Jornada", match.jornada],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value || "Sin asignar"}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {tab === "statistics" &&
                (match.estadisticas.length ? (
                  match.estadisticas.map((stats) => (
                    <section className="once-detail-record" key={stats.id}>
                      <p>Fuente: {sourceName(stats.source)}</p>
                      <dl className="once-detail-fields">
                        <div>
                          <dt>Posesión · {match.equipo_local?.nombre}</dt>
                          <dd>{stats.posesion_local}%</dd>
                        </div>
                        <div>
                          <dt>Posesión · {match.equipo_visitante?.nombre}</dt>
                          <dd>{stats.posesion_visitante}%</dd>
                        </div>
                        <div>
                          <dt>Tiros a puerta · {match.equipo_local?.nombre}</dt>
                          <dd>{stats.tiros_puerta_local}</dd>
                        </div>
                        <div>
                          <dt>
                            Tiros a puerta · {match.equipo_visitante?.nombre}
                          </dt>
                          <dd>{stats.tiros_puerta_visitante}</dd>
                        </div>
                      </dl>
                    </section>
                  ))
                ) : (
                  <EmptyState title="Sin estadísticas registradas">
                    Podrás completar este encuentro desde Datos cuando su fuente
                    esté conectada.
                  </EmptyState>
                ))}
              {tab === "events" &&
                (match.eventos.length ? (
                  [...match.eventos]
                    .sort(
                      (a, b) =>
                        a.minuto - b.minuto ||
                        a.adicional - b.adicional ||
                        a.id - b.id,
                    )
                    .map((event) => (
                      <article className="once-detail-record" key={event.id}>
                        <strong>
                          {event.minuto}
                          {event.adicional ? `+${event.adicional}` : ""}′ ·{" "}
                          {event.tipo}
                        </strong>
                        <p>
                          {teamName(event.equipo_id)} ·{" "}
                          {playerName(event.jugador_id)}
                        </p>
                        {event.asistente_id && (
                          <p>Asistente: {playerName(event.asistente_id)}</p>
                        )}
                        {event.detalle && <p>{event.detalle}</p>}
                        <small>Fuente: {sourceName(event.source)}</small>
                      </article>
                    ))
                ) : (
                  <EmptyState title="Sin eventos registrados">
                    Los goles, tarjetas y cambios pertenecen a este encuentro.
                  </EmptyState>
                ))}
              {tab === "lineups" &&
                (match.alineaciones.length ? (
                  [match.equipo_local, match.equipo_visitante]
                    .filter(Boolean)
                    .map((team) => (
                      <section className="once-detail-record" key={team.id}>
                        <h3>{team.nombre}</h3>
                        {[true, false].map((starting) => (
                          <div key={String(starting)}>
                            <h4>{starting ? "Titulares" : "Suplentes"}</h4>
                            {match.alineaciones
                              .filter(
                                (row) =>
                                  row.equipo_id === team.id &&
                                  row.titular === starting,
                              )
                              .sort(
                                (a, b) =>
                                  (a.orden ?? 999) - (b.orden ?? 999) ||
                                  a.id - b.id,
                              )
                              .map((row) => (
                                <p key={row.id}>
                                  {row.dorsal ?? "—"} ·{" "}
                                  {playerName(row.jugador_id)} ·{" "}
                                  {row.posicion || "Posición no indicada"}
                                  <small className="once-record-source">
                                    Fuente: {sourceName(row.source)}
                                  </small>
                                </p>
                              ))}
                          </div>
                        ))}
                      </section>
                    ))
                ) : (
                  <EmptyState title="Sin alineaciones registradas">
                    La alineación muestra quién participó en este partido; no es
                    la plantilla permanente del equipo.
                  </EmptyState>
                ))}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
