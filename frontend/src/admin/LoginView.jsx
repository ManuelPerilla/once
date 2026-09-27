import { useState } from "react";
import { Brand, Icon, Field, SectionArt } from "../AdminUI";

export function LoginView({ login, notice }) {
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const mensajeApi = notice.message;
  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    notice.clear();
    try {
      await login(loginForm);
    } finally {
      setLoginForm((current) => ({ ...current, password: "" }));
      setLoading(false);
    }
  };
  return (
    <div className="v-login">
      <div className="v-login-scene">
        <Brand />
        <div className="v-login-copy">
          <span className="v-eyebrow">EL JUEGO EMPIEZA ANTES DEL SILBATO.</span>
          <h1>
            Detrás de
            <br />
            cada partido,
            <br />
            <em>estás tú.</em>
          </h1>
          <p>El espacio donde organizas los datos que dan vida a ONCE.</p>
        </div>
        <SectionArt variant="inicio" />
        <span className="v-login-caption">
          CATÁLOGO · MATRÍCULAS · PARTIDOS
        </span>
      </div>
      <main className="v-login-form-area">
        <div className="v-login-box">
          <Brand />
          <span className="v-login-pass">
            <Icon name="shield" /> ACCESO DE ADMINISTRACIÓN <span>01</span>
          </span>
          <span className="v-eyebrow">TU PASE A LA MESA DE CONTROL</span>
          <h2>Bienvenido de nuevo.</h2>
          <p>
            Entra a tu espacio de administración para seguir construyendo el
            juego.
          </p>
          <form onSubmit={handleLogin} className="v-form">
            <Field label="Usuario">
              <input
                autoComplete="username"
                value={loginForm.username}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, username: e.target.value })
                }
                placeholder="Tu usuario de administrador"
                required
              />
            </Field>
            <div className="v-field">
              <label htmlFor="admin-password">Contraseña</label>
              <div className="once-password-field">
                <input
                  id="admin-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={loginForm.password}
                  onChange={(e) =>
                    setLoginForm({ ...loginForm, password: e.target.value })
                  }
                  placeholder="Escribe tu contraseña"
                  required
                />
                <button
                  type="button"
                  aria-label={
                    showPassword ? "Ocultar contraseña" : "Mostrar contraseña"
                  }
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? "Ocultar" : "Mostrar"}
                </button>
              </div>
            </div>
            {mensajeApi && (
              <p role="alert" className="v-login-error">
                {mensajeApi.texto}
              </p>
            )}
            <button disabled={loading} className="v-btn v-btn-dark">
              {loading ? "Entrando…" : "Entrar al workspace"}
              <Icon name="arrow" />
            </button>
          </form>
          <p className="v-login-foot">
            Acceso reservado a la administración de ONCE.
          </p>
          <div className="once-login-links">
            <a href="/explore">
              Explorar ONCE <Icon name="arrow" />
            </a>
            <a href="/explore?demo=1">
              Probar la demostración <Icon name="arrow" />
            </a>
          </div>
        </div>
      </main>
    </div>
  );
}
