import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { Field, Modal } from "../AdminUI";
import { Pagination } from "../components/ui/Pagination";

const roles = {
  auditor: "Auditor · consultar",
  editor: "Editor · corregir datos",
  operator: "Operador · controlar actualizaciones",
  admin: "Administrador · gestionar fuentes y personas",
};
export function AccountsView({ onError }) {
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [revision, setRevision] = useState(0);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    apiRequest(`/accounts?page=${page}&page_size=20`, {
      signal: controller.signal,
    })
      .then(setResult)
      .catch((failure) => {
        if (!controller.signal.aborted) {
          setError(failure.message);
          if (failure.status === 401) onError(failure);
        }
      });
    return () => controller.abort();
  }, [page, revision, onError]);
  const set = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  return (
    <section className="v-panel">
      <div className="once-section-title">
        <div>
          <h3>Cada persona, con su propia cuenta.</h3>
          <p>
            Las correcciones y operaciones quedarán atribuidas a quien las
            realizó.
          </p>
        </div>
        <button
          className="v-btn v-btn-dark"
          onClick={() => {
            setForm({
              username: "",
              display_name: "",
              password: "",
              role: "auditor",
              active: true,
              reason: "",
            });
            setError("");
          }}
        >
          Añadir persona
        </button>
      </div>
      {error && !form && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {!result ? (
        <p role="status">Consultando cuentas…</p>
      ) : (
        <div className="once-automation-records">
          {result.items.map((account) => (
            <article key={account.id}>
              <strong>{account.display_name || account.username}</strong>
              <p>
                {account.username} · {roles[account.role]} ·{" "}
                {account.active ? "Acceso activo" : "Acceso desactivado"}
              </p>
              <button
                className="v-text-btn"
                onClick={() => {
                  setForm({ ...account, password: "", reason: "" });
                  setError("");
                }}
              >
                Revisar acceso
              </button>
            </article>
          ))}
        </div>
      )}
      {result && (
        <Pagination
          page={page}
          pageSize={20}
          total={result.total}
          onChange={setPage}
        />
      )}
      {form && (
        <Modal
          title={
            form.id ? "Revisar acceso de la persona" : "Añadir una persona"
          }
          subtitle="Elige los permisos necesarios para su trabajo. Cada cuenta conserva su identidad en el historial."
          onClose={() => setForm(null)}
          busy={busy}
        >
          <form
            className="once-automation-form"
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              setError("");
              try {
                await apiRequest(
                  form.id ? `/accounts/${form.id}` : "/accounts",
                  {
                    method: form.id ? "PATCH" : "POST",
                    body: form.id
                      ? {
                          display_name: form.display_name,
                          role: form.role,
                          active: form.active,
                          reason: form.reason,
                          ...(form.password ? { password: form.password } : {}),
                        }
                      : {
                          username: form.username,
                          display_name: form.display_name,
                          role: form.role,
                          password: form.password,
                        },
                  },
                );
                setForm(null);
                setRevision((value) => value + 1);
                setMessage("Acceso guardado.");
              } catch (failure) {
                setError(failure.message);
                if (failure.status === 401) onError(failure);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="Nombre visible">
              <input
                required
                maxLength={100}
                value={form.display_name}
                onChange={(event) => set("display_name", event.target.value)}
              />
            </Field>
            <Field label="Nombre de usuario">
              <input
                required
                disabled={Boolean(form.id)}
                autoComplete="off"
                value={form.username}
                onChange={(event) => set("username", event.target.value)}
              />
            </Field>
            <Field label="Responsabilidad">
              <select
                value={form.role}
                onChange={(event) => set("role", event.target.value)}
              >
                {Object.entries(roles).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label={
                form.id ? "Nueva contraseña (opcional)" : "Contraseña inicial"
              }
              hint="Al menos 12 caracteres. No se guarda ni se muestra en el historial."
            >
              <input
                type="password"
                required={!form.id}
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                value={form.password}
                onChange={(event) => set("password", event.target.value)}
              />
            </Field>
            {form.id && (
              <>
                <label className="once-rule-check">
                  <input
                    type="checkbox"
                    checked={form.active}
                    onChange={(event) => set("active", event.target.checked)}
                  />
                  Permitir que esta persona inicie sesión
                </label>
                <Field label="Motivo del cambio de acceso">
                  <textarea
                    required
                    minLength={3}
                    maxLength={1000}
                    value={form.reason}
                    onChange={(event) => set("reason", event.target.value)}
                  />
                </Field>
              </>
            )}
            {error && (
              <p role="alert" className="once-automation-error">
                {error}
              </p>
            )}
            <button className="v-btn v-btn-dark" disabled={busy}>
              {busy ? "Guardando…" : "Guardar acceso"}
            </button>
          </form>
        </Modal>
      )}
    </section>
  );
}
