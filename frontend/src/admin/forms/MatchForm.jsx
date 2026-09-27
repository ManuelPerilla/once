import { Modal, Field } from "../../AdminUI";
import { FormActions } from "./FormActions";

export function MatchForm({
  formPartido,
  setFormPartido,
  closeForms,
  handleSubmitPartido,
  competiciones,
  equipos,
  temporadas,
  fases,
  estadios,
  loading,
  toast,
}) {
  const temporadasDisponiblesParaPartido = formPartido.competicion_id
    ? temporadas.filter(
        (season) =>
          String(season.competicion_id) === String(formPartido.competicion_id),
      )
    : [];
  const fasesDisponiblesParaPartido = formPartido.temporada_id
    ? fases.filter(
        (stage) =>
          String(stage.temporada_id) === String(formPartido.temporada_id),
      )
    : [];

  // FILTRO DINÁMICO PARA PARTIDOS (La Arena)
  const equiposDisponiblesParaPartido = formPartido.competicion_id
    ? equipos.filter((eq) =>
        eq.competiciones.some(
          (c) => c.id === parseInt(formPartido.competicion_id),
        ),
      )
    : [];

  return (
    <Modal
      title="Registrar partido"
      subtitle="Primero elige la competición. Solo podrás seleccionar equipos matriculados."
      onClose={closeForms}
    >
      <form className="v-form" id="match-form" onSubmit={handleSubmitPartido}>
        <Field label="Competición">
          <select
            value={formPartido.competicion_id}
            onChange={(e) =>
              setFormPartido({
                ...formPartido,
                competicion_id: e.target.value,
                temporada_id: "",
                fase_id: "",
                equipo_local_id: "",
                equipo_visitante_id: "",
              })
            }
            required
          >
            <option value="">Selecciona una competición</option>
            {competiciones.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
        </Field>
        <div className="v-form-grid">
          <Field label="Equipo local">
            <select
              value={formPartido.equipo_local_id}
              disabled={!formPartido.competicion_id}
              onChange={(e) =>
                setFormPartido({
                  ...formPartido,
                  equipo_local_id: e.target.value,
                  equipo_visitante_id:
                    e.target.value === formPartido.equipo_visitante_id
                      ? ""
                      : formPartido.equipo_visitante_id,
                })
              }
              required
            >
              <option value="">Selecciona el local</option>
              {equiposDisponiblesParaPartido
                .filter(
                  (eq) => String(eq.id) !== formPartido.equipo_visitante_id,
                )
                .map((eq) => (
                  <option key={eq.id} value={eq.id}>
                    {eq.nombre}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="Equipo visitante">
            <select
              value={formPartido.equipo_visitante_id}
              disabled={!formPartido.competicion_id}
              onChange={(e) =>
                setFormPartido({
                  ...formPartido,
                  equipo_visitante_id: e.target.value,
                })
              }
              required
            >
              <option value="">Selecciona el visitante</option>
              {equiposDisponiblesParaPartido
                .filter((eq) => String(eq.id) !== formPartido.equipo_local_id)
                .map((eq) => (
                  <option key={eq.id} value={eq.id}>
                    {eq.nombre}
                  </option>
                ))}
            </select>
          </Field>
        </div>
        {formPartido.competicion_id &&
          equiposDisponiblesParaPartido.length < 2 && (
            <p className="v-notice">
              Necesitas al menos dos equipos matriculados en esta competición
              para registrar un partido.
            </p>
          )}
        <div className="v-form-grid">
          <Field
            label="Fecha y hora"
            hint="Se guardará con la zona horaria de tu dispositivo."
          >
            <input
              type="datetime-local"
              value={formPartido.fecha}
              onChange={(e) =>
                setFormPartido({ ...formPartido, fecha: e.target.value })
              }
            />
          </Field>
          <Field label="Jornada">
            <input
              value={formPartido.jornada}
              onChange={(e) =>
                setFormPartido({ ...formPartido, jornada: e.target.value })
              }
              placeholder="Ej. Fecha 12"
            />
          </Field>
        </div>
        <details className="once-match-options">
          <summary>
            Temporada, fase y estadio <span>Opcional</span>
          </summary>
          <div className="v-form-grid">
            <Field label="Temporada">
              <select
                disabled={!temporadasDisponiblesParaPartido.length}
                value={formPartido.temporada_id}
                onChange={(e) =>
                  setFormPartido({
                    ...formPartido,
                    temporada_id: e.target.value,
                    fase_id: "",
                  })
                }
              >
                <option value="">Sin temporada</option>
                {temporadasDisponiblesParaPartido.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nombre}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Fase">
              <select
                disabled={!fasesDisponiblesParaPartido.length}
                value={formPartido.fase_id}
                onChange={(e) =>
                  setFormPartido({
                    ...formPartido,
                    fase_id: e.target.value,
                  })
                }
              >
                <option value="">Sin fase</option>
                {fasesDisponiblesParaPartido.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nombre}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Estadio">
              <select
                value={formPartido.estadio_id}
                onChange={(e) =>
                  setFormPartido({
                    ...formPartido,
                    estadio_id: e.target.value,
                  })
                }
              >
                <option value="">Sin estadio</option>
                {estadios.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nombre}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </details>
        <Field label="Estado">
          <select
            value={formPartido.estado}
            onChange={(e) =>
              setFormPartido({ ...formPartido, estado: e.target.value })
            }
          >
            <option value="programado">Programado</option>
            <option value="en vivo">En vivo</option>
            <option value="finalizado">Finalizado</option>
          </select>
        </Field>
        <div className="v-form-grid">
          <Field label="Goles local">
            <input
              type="number"
              min="0"
              value={formPartido.marcador_local}
              onChange={(e) =>
                setFormPartido({
                  ...formPartido,
                  marcador_local: e.target.value,
                })
              }
              required
            />
          </Field>
          <Field label="Goles visitante">
            <input
              type="number"
              min="0"
              value={formPartido.marcador_visitante}
              onChange={(e) =>
                setFormPartido({
                  ...formPartido,
                  marcador_visitante: e.target.value,
                })
              }
              required
            />
          </Field>
        </div>
        <FormActions loading={loading} onClose={closeForms} />
      </form>
      {toast}
    </Modal>
  );
}
