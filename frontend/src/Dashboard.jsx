import { useEffect, useState } from "react";
import { apiCollection, apiRequest } from "./api";
import { runViewTransition } from "./lib/viewTransition";
import {
  EMPTY_FILTERS,
  COMPETITION_TYPES,
  changeFilters,
  countryOptions,
  filterCatalog,
  normalize,
} from "./catalogFilters";
import { summarizeAdmin } from "./adminSummary";
import { workspaceNavigation, workspaceSections } from "./admin/sections";
import { EnrollmentView } from "./admin/EnrollmentView";
import { MatchesView } from "./admin/MatchesView";
import { CatalogView } from "./admin/CatalogView";
import { HomeView } from "./admin/HomeView";
import {
  Brand,
  Icon,
  Modal,
  Field,
  SectionArt,
} from "./AdminUI";
import "./admin.css";

export default function Dashboard() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [activeTab, setActiveTab] = useState("inicio");
  const changeSection = (nextTab) =>
    runViewTransition(() => setActiveTab(nextTab));

  const [catalogTab, setCatalogTab] = useState("competiciones");
  const [matchFilter, setMatchFilter] = useState("");
  const [onlyFree, setOnlyFree] = useState(false);
  const [enrollmentSearch, setEnrollmentSearch] = useState("");
  const [showMatchForm, setShowMatchForm] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [catalogsReady, setCatalogsReady] = useState(false);
  const [matchesReady, setMatchesReady] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState(null);

  const [partidos, setPartidos] = useState([]);
  const [confederaciones, setConfederaciones] = useState([]);
  const [competiciones, setCompeticiones] = useState([]);
  const [equipos, setEquipos] = useState([]);
  const [temporadas, setTemporadas] = useState([]);
  const [fases, setFases] = useState([]);
  const [estadios, setEstadios] = useState([]);

  const [loginForm, setLoginForm] = useState({ username: "", password: "" });

  // Estados para CRUD
  const [editConfId, setEditConfId] = useState(null);
  const [formConf, setFormConf] = useState({ nombre: "", logo: "" });

  const [editCompId, setEditCompId] = useState(null);
  const [formComp, setFormComp] = useState({
    nombre: "",
    logo: "",
    tipo: "liga_nacional",
    pais: "",
    confederacion_id: "",
  });

  const [editEqId, setEditEqId] = useState(null);
  const [formEquipo, setFormEquipo] = useState({
    nombre: "",
    logo: "",
    tipo: "club",
    pais: "",
    confederacion_id: "",
  });

  const [formMatricula, setFormMatricula] = useState({
    equipo_id: "",
    competicion_id: "",
  });
  const [formPartido, setFormPartido] = useState({
    competicion_id: "",
    temporada_id: "",
    fase_id: "",
    estadio_id: "",
    fecha: "",
    jornada: "",
    equipo_local_id: "",
    equipo_visitante_id: "",
    marcador_local: 0,
    marcador_visitante: 0,
    estado: "programado",
  });

  const [filtroPais, setFiltroPais] = useState("");
  const [catalogFilters, setCatalogFilters] = useState({ ...EMPTY_FILTERS });
  const [showConfForm, setShowConfForm] = useState(false);
  const [showCompForm, setShowCompForm] = useState(false);
  const [showTeamForm, setShowTeamForm] = useState(false);
  const catalog = filterCatalog(competiciones, equipos, catalogFilters);
  const countries = countryOptions(
    competiciones,
    equipos,
    catalogFilters.confederation,
  );
  const updateFilter = (field, value) =>
    setCatalogFilters((current) => changeFilters(current, field, value));
  const clearFilters = () => setCatalogFilters({ ...EMPTY_FILTERS });
  const [mensajeApi, setMensajeApi] = useState(null);
  const [loading, setLoading] = useState(false);

  const notify = (tipo, texto) => {
    setMensajeApi({ tipo, texto });
    setTimeout(() => setMensajeApi(null), 3500);
  };

  const clearSession = () => {
    setIsLoggedIn(false);
    changeSection("inicio");
    setCatalogsReady(false);
    setMatchesReady(false);
    setShowConfForm(false);
    setShowCompForm(false);
    setShowTeamForm(false);
    setShowMatchForm(false);
    setPendingDelete(null);
    clearFilters();
    setPartidos([]);
    setConfederaciones([]);
    setCompeticiones([]);
    setEquipos([]);
    setTemporadas([]);
    setFases([]);
    setEstadios([]);
    setLoginForm((form) => ({ ...form, password: "" }));
  };

  const handleApiError = (error) => {
    if (error.status === 401) clearSession();
    notify(
      "error",
      error.status ? error.message : "No se pudo conectar con el servidor.",
    );
  };

  // Solo se guardan listas válidas; un 401 vuelve al login sin romper la vista.
  const fetchPartidos = async (quiet = false) => {
    try {
      const data = await apiCollection("/partidos/");
      setPartidos(data);
      setIsLoggedIn(true);
      setMatchesReady(true);
      setUpdatedAt(new Date());
    } catch (error) {
      if (quiet && error.status === 401) clearSession();
      else handleApiError(error);
    }
  };

  const fetchCatalogs = async () => {
    try {
      const [confs, comps, eqs, seasons, stages, venues] = await Promise.all([
        apiCollection("/confederaciones/"),
        apiCollection("/competiciones/"),
        apiCollection("/equipos/"),
        apiCollection("/temporadas/"),
        apiCollection("/fases/"),
        apiCollection("/estadios/"),
      ]);
      setConfederaciones(confs);
      setCompeticiones(comps);
      setEquipos(eqs);
      setTemporadas(seasons);
      setFases(stages);
      setEstadios(venues);
      setCatalogsReady(true);
      setUpdatedAt(new Date());
    } catch (error) {
      handleApiError(error);
    }
  };

  useEffect(() => {
    if (isLoggedIn) fetchCatalogs();
  }, [isLoggedIn]);
  useEffect(() => {
    fetchPartidos(true).finally(() => setCheckingSession(false));
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMensajeApi(null);
    try {
      await apiRequest("/login", { method: "POST", body: loginForm });
      setLoginForm((form) => ({ ...form, password: "" }));
      await fetchPartidos();
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await apiRequest("/logout", { method: "POST" });
      clearSession();
      setMensajeApi(null);
    } catch (error) {
      handleApiError(error);
    }
  };

  // --- CRUD CONFEDERACIONES ---
  const handleSubmitConf = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiRequest(
        editConfId ? `/confederaciones/${editConfId}` : "/confederaciones/",
        {
          method: editConfId ? "PUT" : "POST",
          body: formConf,
        },
      );
      notify("success", "Confederación guardada");
      setFormConf({ nombre: "", logo: "" });
      setEditConfId(null);
      setShowConfForm(false);
      await fetchCatalogs();
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  };
  const handleEditConf = (c) => {
    setFormConf({ nombre: c.nombre, logo: c.logo });
    setEditConfId(c.id);
    setShowConfForm(true);
    setFiltroPais("");
  };

  const deleteEntity = async (path) => {
    setDeleting(true);
    try {
      await apiRequest(path, { method: "DELETE" });
      setPendingDelete(null);
      notify("success", "Registro eliminado");
      await Promise.all([fetchCatalogs(), fetchPartidos()]);
    } catch (error) {
      handleApiError(error);
    } finally {
      setDeleting(false);
    }
  };
  const handleEliminarConf = (id) => {
    setMensajeApi(null);
    setPendingDelete({
      title: "Eliminar confederación",
      name:
        confederaciones.find((item) => item.id === id)?.nombre ||
        `Registro #${id}`,
      impact:
        "Sus competiciones y equipos se conservarán, pero quedarán sin confederación.",
      path: `/confederaciones/${id}`,
    });
  };

  // --- CRUD COMPETICIONES ---
  const handleSubmitComp = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiRequest(
        editCompId ? `/competiciones/${editCompId}` : "/competiciones/",
        {
          method: editCompId ? "PUT" : "POST",
          body: {
            ...formComp,
            confederacion_id: parseInt(formComp.confederacion_id) || null,
          },
        },
      );
      notify("success", "Competición guardada");
      setFormComp({
        nombre: "",
        logo: "",
        tipo: "liga_nacional",
        pais: "",
        confederacion_id: "",
      });
      setEditCompId(null);
      setShowCompForm(false);
      await Promise.all([fetchCatalogs(), fetchPartidos()]);
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  };
  const handleEditComp = (c) => {
    setFormComp({
      nombre: c.nombre,
      logo: c.logo,
      tipo: c.tipo,
      pais: c.pais,
      confederacion_id: c.confederacion_id || "",
    });
    setEditCompId(c.id);
    setShowCompForm(true);
  };
  const handleEliminarComp = (id) => {
    setMensajeApi(null);
    setPendingDelete({
      title: "Eliminar competición",
      name:
        competiciones.find((item) => item.id === id)?.nombre ||
        `Registro #${id}`,
      impact:
        "Se eliminarán sus matrículas. Los equipos se conservarán y los partidos asociados quedarán sin competición.",
      path: `/competiciones/${id}`,
    });
  };

  // --- CRUD EQUIPOS ---
  const handleSubmitEquipo = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiRequest(editEqId ? `/equipos/${editEqId}` : "/equipos/", {
        method: editEqId ? "PUT" : "POST",
        body: {
          ...formEquipo,
          confederacion_id: parseInt(formEquipo.confederacion_id) || null,
        },
      });
      notify("success", "Equipo guardado");
      setFormEquipo({
        nombre: "",
        logo: "",
        tipo: "club",
        pais: "",
        confederacion_id: "",
      });
      setEditEqId(null);
      setShowTeamForm(false);
      await Promise.all([fetchCatalogs(), fetchPartidos()]);
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  };
  const handleEditEq = (eq) => {
    setFormEquipo({
      nombre: eq.nombre,
      logo: eq.logo,
      tipo: eq.tipo,
      pais: eq.pais,
      confederacion_id: eq.confederacion_id || "",
    });
    setEditEqId(eq.id);
    setShowTeamForm(true);
  };
  const handleEliminarEq = (id) => {
    setMensajeApi(null);
    setPendingDelete({
      title: "Eliminar equipo",
      name: equipos.find((item) => item.id === id)?.nombre || `Registro #${id}`,
      impact:
        "Se eliminarán sus matrículas. Sus partidos se conservarán, pero quedarán sin este equipo.",
      path: `/equipos/${id}`,
    });
  };

  const handleMatricular = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await apiRequest(
        `/equipos/${formMatricula.equipo_id}/matricular/${formMatricula.competicion_id}`,
        { method: "POST" },
      );
      notify(data.ok ? "success" : "error", data.mensaje);
      if (data.ok) {
        await fetchCatalogs();
        setFormMatricula({ equipo_id: "", competicion_id: "" });
      }
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitPartido = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiRequest("/partidos/", {
        method: "POST",
        body: {
          competicion_id: parseInt(formPartido.competicion_id),
          temporada_id: parseInt(formPartido.temporada_id) || null,
          fase_id: parseInt(formPartido.fase_id) || null,
          estadio_id: parseInt(formPartido.estadio_id) || null,
          fecha: formPartido.fecha
            ? new Date(formPartido.fecha).toISOString()
            : null,
          jornada: formPartido.jornada.trim() || null,
          equipo_local_id: parseInt(formPartido.equipo_local_id),
          equipo_visitante_id: parseInt(formPartido.equipo_visitante_id),
          marcador_local: parseInt(formPartido.marcador_local),
          marcador_visitante: parseInt(formPartido.marcador_visitante),
          estado: formPartido.estado,
        },
      });
      notify("success", "Partido registrado");
      setShowMatchForm(false);
      setFormPartido({
        competicion_id: "",
        temporada_id: "",
        fase_id: "",
        estadio_id: "",
        fecha: "",
        jornada: "",
        equipo_local_id: "",
        equipo_visitante_id: "",
        marcador_local: 0,
        marcador_visitante: 0,
        estado: "programado",
      });
      await fetchPartidos();
    } catch (error) {
      handleApiError(error);
    } finally {
      setLoading(false);
    }
  };
  const handleEliminarPartido = (id) => {
    setMensajeApi(null);
    const match = partidos.find((item) => item.id === id);
    setPendingDelete({
      title: "Eliminar partido",
      name: `${match?.equipo_local?.nombre || "Sin equipo"} / ${match?.equipo_visitante?.nombre || "Sin equipo"} · #${id}`,
      impact:
        "También se eliminarán las estadísticas de este encuentro. Los equipos y la competición se conservarán.",
      path: `/partidos/${id}`,
    });
  };

  const asociarHuerfano = async (tipo, idItem) => {
    if (!editConfId) return;
    const item =
      tipo === "competiciones"
        ? competiciones.find((c) => c.id === idItem)
        : equipos.find((e) => e.id === idItem);
    try {
      await apiRequest(`/${tipo}/${idItem}`, {
        method: "PUT",
        body: { ...item, confederacion_id: editConfId },
      });
      await fetchCatalogs();
    } catch (error) {
      handleApiError(error);
    }
  };

  const compsHuerfanasFiltradas = competiciones.filter(
    (c) =>
      !c.confederacion_id &&
      c.pais.toLowerCase().includes(filtroPais.toLowerCase()),
  );
  const eqsHuerfanosFiltrados = equipos.filter(
    (e) =>
      !e.confederacion_id &&
      e.pais.toLowerCase().includes(filtroPais.toLowerCase()),
  );

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

  // FILTRO INTELIGENTE PARA MATRÍCULAS (La Aduana Geográfica y Genética)
  const equiposDisponiblesParaMatricula = formMatricula.competicion_id
    ? equipos.filter((eq) => {
        const comp = competiciones.find(
          (c) => c.id === parseInt(formMatricula.competicion_id),
        );
        if (!comp) return false;

        // 1. Naturaleza (Selección vs Club)
        if (
          comp.tipo === "internacional_selecciones" &&
          eq.tipo !== "seleccion"
        )
          return false;
        if (
          comp.tipo !== "internacional_selecciones" &&
          eq.tipo === "seleccion"
        )
          return false;

        // 2. Geografía Local (Ligas Nacionales)
        if (
          ["liga_nacional", "copa_nacional"].includes(comp.tipo) &&
          eq.pais !== comp.pais
        )
          return false;

        // 3. Confederación Continental
        if (
          comp.confederacion_id &&
          eq.confederacion_id !== comp.confederacion_id
        )
          return false;

        return !eq.competiciones?.some((c) => c.id === comp.id);
      })
    : [];

  const summary = summarizeAdmin(competiciones, equipos, partidos);
  const ready = catalogsReady && matchesReady;
  const section = workspaceSections[activeTab];
  const closeForms = () => {
    setMensajeApi(null);
    setShowConfForm(false);
    setShowCompForm(false);
    setShowTeamForm(false);
    setShowMatchForm(false);
    setEditConfId(null);
    setEditCompId(null);
    setEditEqId(null);
  };
  const openCreate = (type) => {
    closeForms();
    if (type === "confederaciones") {
      setFormConf({ nombre: "", logo: "" });
      setShowConfForm(true);
    }
    if (type === "competiciones") {
      setFormComp({
        nombre: "",
        logo: "",
        tipo: "liga_nacional",
        pais: "",
        confederacion_id: "",
      });
      setShowCompForm(true);
    }
    if (type === "equipos") {
      setFormEquipo({
        nombre: "",
        logo: "",
        tipo: "club",
        pais: "",
        confederacion_id: "",
      });
      setShowTeamForm(true);
    }
    if (type === "partidos") {
      setFormPartido({
        competicion_id: "",
        temporada_id: "",
        fase_id: "",
        estadio_id: "",
        fecha: "",
        jornada: "",
        equipo_local_id: "",
        equipo_visitante_id: "",
        marcador_local: 0,
        marcador_visitante: 0,
        estado: "programado",
      });
      setShowMatchForm(true);
    }
  };
  const goCatalog = (type) => {
    clearFilters();
    setCatalogTab(type);
    changeSection("ecosistema");
  };
  const goEnrollments = (freeOnly = false) => {
    setOnlyFree(freeOnly);
    setEnrollmentSearch("");
    changeSection("matriculas");
  };
  const heroAction = () => {
    if (activeTab === "inicio") goCatalog("competiciones");
    else if (activeTab === "ecosistema") openCreate(catalogTab);
    else if (activeTab === "arena") openCreate("partidos");
    else document.getElementById("matricula-competition")?.focus();
  };
  const refreshData = async () => {
    setRefreshing(true);
    await Promise.all([fetchPartidos(), fetchCatalogs()]);
    setRefreshing(false);
  };
  const formOpen =
    showConfForm ||
    showCompForm ||
    showTeamForm ||
    showMatchForm ||
    Boolean(pendingDelete);
  const catalogItems =
    catalogTab === "confederaciones"
      ? confederaciones.filter((c) =>
          normalize(c.nombre).includes(normalize(catalogFilters.search)),
        )
      : catalogTab === "competiciones"
        ? catalog.competitions
        : catalog.teams;
  const catalogTotal =
    catalogTab === "confederaciones"
      ? confederaciones.length
      : catalogTab === "competiciones"
        ? competiciones.length
        : equipos.length;
  const enrollmentItems = equipos.filter(
    (eq) =>
      (!onlyFree || !eq.competiciones?.length) &&
      normalize(eq.nombre).includes(normalize(enrollmentSearch)),
  );
  const matchItems = [...partidos]
    .filter((p) =>
      matchFilter === "incompletos"
        ? summary.incomplete.some((item) => item.id === p.id)
        : !matchFilter || p.estado === matchFilter,
    )
    .sort((a, b) => b.id - a.id);
  const toast = mensajeApi && (
    <div
      role={mensajeApi.tipo === "error" ? "alert" : "status"}
      className={`v-toast ${mensajeApi.tipo === "error" ? "v-toast-error" : ""}`}
    >
      <Icon name={mensajeApi.tipo === "error" ? "alert" : "check"} />
      {mensajeApi.texto}
    </div>
  );
  const confOptions = (
    <>
      <option value="">Sin confederación</option>
      {confederaciones.map((c) => (
        <option key={c.id} value={c.id}>
          {c.nombre}
        </option>
      ))}
    </>
  );
  const formFooter = (
    <div className="v-form-footer">
      <button
        type="button"
        className="v-btn v-btn-secondary"
        onClick={closeForms}
      >
        Cancelar
      </button>
      <button type="submit" className="v-btn v-btn-dark" disabled={loading}>
        {loading ? "Guardando…" : "Guardar cambios"}
        <Icon name="check" />
      </button>
    </div>
  );

  if (checkingSession)
    return (
      <div className="v-loading">
        <Brand />
        <span className="v-loading-bar" />
        <p>Preparando tu espacio de trabajo…</p>
      </div>
    );
  if (!isLoggedIn)
    return (
      <div className="v-login">
        <div className="v-login-scene">
          <Brand />
          <div className="v-login-copy">
            <span className="v-eyebrow">
              EL JUEGO EMPIEZA ANTES DEL SILBATO.
            </span>
            <h1>
              Detrás de
              <br />
              cada partido,
              <br />
              <em>estás tú.</em>
            </h1>
            <p>El espacio donde organizas los datos que dan vida a VÉRTICE.</p>
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
              <Field label="Contraseña">
                <input
                  type="password"
                  autoComplete="current-password"
                  value={loginForm.password}
                  onChange={(e) =>
                    setLoginForm({ ...loginForm, password: e.target.value })
                  }
                  placeholder="Escribe tu contraseña"
                  required
                />
              </Field>
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
              Acceso reservado a la administración de VÉRTICE.
            </p>
          </div>
        </main>
      </div>
    );

  return (
    <div className="v-app">
      <a className="v-skip-link" href="#workspace-content">
        Saltar al contenido
      </a>
      <header className="v-masthead">
        <div className="v-masthead-inner">
          <Brand />
          <div className="v-workspace-id">
            <span>CONTROL ROOM</span>
            <small>FÚTBOL, DESDE DENTRO.</small>
          </div>
          <div className="v-top-actions">
            <span className="v-admin-tag">
              <i />
              Administración
            </span>
            <button
              className="v-icon-btn"
              disabled={refreshing}
              onClick={refreshData}
              aria-label="Actualizar datos"
              title={refreshing ? "Actualizando…" : "Actualizar datos"}
            >
              <Icon
                name="refresh"
                className={refreshing ? "v-spinning" : undefined}
              />
            </button>
            <button
              className="v-session-button"
              onClick={handleLogout}
              aria-label="Salir de la sesión"
            >
              <span className="v-avatar">AD</span>
              <span>Salir</span>
              <Icon name="logout" />
            </button>
          </div>
        </div>
      </header>
      <div className="v-navigation">
        <nav className="v-nav" aria-label="Navegación principal">
          {workspaceNavigation.map(([tab, number]) => (
            <button
              key={tab}
              aria-label={workspaceSections[tab].label}
              aria-current={activeTab === tab ? "page" : undefined}
              onClick={() => changeSection(tab)}
            >
              <small>{number}</small>
              <span>{workspaceSections[tab].label}</span>
              <Icon name="arrow" />
            </button>
          ))}
        </nav>
        <span className="v-nav-caption">
          LA TRIBUNA ES AFUERA.
          <br />
          <strong>EL CONTROL ESTÁ AQUÍ.</strong>
        </span>
      </div>
      <main
        className={`v-main v-page-${activeTab}`}
        id="workspace-content"
        tabIndex={-1}
      >
        <div className="v-content">
          <div className="v-page-intro">
            <div>
              <span className="v-section-kicker">
                {activeTab === "inicio"
                  ? "VISTA GENERAL"
                  : "ESPACIO DE TRABAJO"}
              </span>
              <h1>
                {activeTab === "inicio"
                  ? "Tu centro de operaciones"
                  : section.label}
              </h1>
              <p>
                {activeTab === "inicio"
                  ? "Una mirada al estado de tu universo futbolístico."
                  : {
                      ecosistema: "Las entidades que dan forma a VÉRTICE.",
                      matriculas:
                        "Gestiona quién participa en cada competición.",
                      arena: "Todos tus encuentros, organizados.",
                    }[activeTab]}
              </p>
            </div>
            {updatedAt && (
              <span className="v-updated">
                Última consulta ·{" "}
                {updatedAt.toLocaleTimeString("es", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
          <section
            className="v-hero"
            aria-label={`Presentación de ${section.label}`}
          >
            <div className="v-hero-copy">
              <span className="v-eyebrow">{section.eyebrow}</span>
              <h2>{section.title}</h2>
              <p>{section.description}</p>
              <button className="v-btn v-btn-primary" onClick={heroAction}>
                {section.action}
                <Icon name={section.icon === "grid" ? "arrow" : section.icon} />
              </button>
            </div>
            <SectionArt variant={activeTab} />
            <div className="v-hero-baseline" aria-hidden="true">
              <span>VÉRTICE / OPERACIONES</span>
              <span>EL FÚTBOL SE EXPLORA. AQUÍ SE ORGANIZA.</span>
              <Icon name="globe" />
            </div>
          </section>

          {activeTab === "inicio" && (
            <HomeView
              ready={ready}
              competitions={competiciones}
              teams={equipos}
              summary={summary}
              goCatalog={goCatalog}
              goEnrollments={goEnrollments}
              setMatchFilter={setMatchFilter}
              changeSection={changeSection}
              openCreate={openCreate}
            />
          )}

          {activeTab === "ecosistema" && (
            <CatalogView
              catalogTab={catalogTab}
              setCatalogTab={setCatalogTab}
              catalogsReady={catalogsReady}
              competitions={competiciones}
              teams={equipos}
              confederations={confederaciones}
              filters={catalogFilters}
              setFilters={setCatalogFilters}
              updateFilter={updateFilter}
              countries={countries}
              catalog={catalog}
              items={catalogItems}
              total={catalogTotal}
              clearFilters={clearFilters}
              openCreate={openCreate}
              closeForms={closeForms}
              onEditConfederation={handleEditConf}
              onEditCompetition={handleEditComp}
              onEditTeam={handleEditEq}
              onDeleteConfederation={handleEliminarConf}
              onDeleteCompetition={handleEliminarComp}
              onDeleteTeam={handleEliminarEq}
            />
          )}

          {activeTab === "matriculas" && (
            <EnrollmentView
              form={formMatricula}
              setForm={setFormMatricula}
              competitions={competiciones}
              availableTeams={equiposDisponiblesParaMatricula}
              loading={loading}
              onEnroll={handleMatricular}
              items={enrollmentItems}
              search={enrollmentSearch}
              setSearch={setEnrollmentSearch}
              onlyFree={onlyFree}
              setOnlyFree={setOnlyFree}
            />
          )}

          {activeTab === "arena" && (
            <MatchesView
              filter={matchFilter}
              setFilter={setMatchFilter}
              incompleteCount={summary.incomplete.length}
              matches={matchItems}
              onDelete={handleEliminarPartido}
              onCreate={() => openCreate("partidos")}
            />
          )}
          <footer className="v-footer">
            <Brand />
            <span>DISEÑADO PARA MOVER EL JUEGO.</span>
            <small>ADMINISTRACIÓN / ACCESO RESTRINGIDO</small>
          </footer>
        </div>
      </main>
      {!formOpen && toast}

      {pendingDelete && (
        <Modal
          title={pendingDelete.title}
          subtitle="Revisa el impacto antes de confirmar."
          eyebrow="VÉRTICE / CONFIRMACIÓN DE BORRADO"
          busy={deleting}
          onClose={() => {
            if (!deleting) {
              setPendingDelete(null);
              setMensajeApi(null);
            }
          }}
        >
          <div className="v-confirm-body">
            <div className="v-confirm-entity">
              <Icon name="trash" />
              <strong>{pendingDelete.name}</strong>
            </div>
            <p>{pendingDelete.impact}</p>
            <p className="v-confirm-warning">
              Esta acción no se puede deshacer desde el panel.
            </p>
            <div className="v-form-footer">
              <button
                data-autofocus
                type="button"
                className="v-btn v-btn-secondary"
                disabled={deleting}
                onClick={() => {
                  setPendingDelete(null);
                  setMensajeApi(null);
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="v-btn v-btn-danger"
                disabled={deleting}
                onClick={() => deleteEntity(pendingDelete.path)}
              >
                {deleting ? "Eliminando…" : "Eliminar registro"}
                <Icon name="trash" />
              </button>
            </div>
          </div>
          {toast}
        </Modal>
      )}

      {showConfForm && (
        <Modal
          title={editConfId ? "Editar confederación" : "Nueva confederación"}
          subtitle="Organiza las entidades de tu catálogo por confederación."
          onClose={closeForms}
        >
          <form
            className="v-form"
            id="confederation-form"
            onSubmit={handleSubmitConf}
          >
            <Field label="Nombre">
              <input
                value={formConf.nombre}
                onChange={(e) =>
                  setFormConf({ ...formConf, nombre: e.target.value })
                }
                placeholder="Ej. CONMEBOL"
                required
              />
            </Field>
            <Field label="URL del logo">
              <input
                type="url"
                value={formConf.logo}
                onChange={(e) =>
                  setFormConf({ ...formConf, logo: e.target.value })
                }
                placeholder="https://…"
                required
              />
            </Field>
            {formFooter}
          </form>
          {editConfId && (
            <details className="v-associate">
              <summary>Vincular entidades sin confederación</summary>
              <p>
                Revisa cada entidad antes de vincularla. Una competición global
                puede permanecer sin confederación.
              </p>
              <Field label="Filtrar por país">
                <input
                  value={filtroPais}
                  onChange={(e) => setFiltroPais(e.target.value)}
                />
              </Field>
              <div className="v-associate-list">
                {[
                  ...compsHuerfanasFiltradas.map((item) => ({
                    ...item,
                    category: "competiciones",
                  })),
                  ...eqsHuerfanosFiltrados.map((item) => ({
                    ...item,
                    category: "equipos",
                  })),
                ].map((item) => (
                  <div key={`${item.category}-${item.id}`}>
                    <span>
                      {item.nombre} · {item.pais}
                    </span>
                    <button
                      className="v-text-btn"
                      onClick={() => asociarHuerfano(item.category, item.id)}
                    >
                      Vincular
                      <Icon name="link" />
                    </button>
                  </div>
                ))}
              </div>
            </details>
          )}
          {toast}
        </Modal>
      )}
      {showCompForm && (
        <Modal
          title={editCompId ? "Editar competición" : "Nueva competición"}
          subtitle="Define el torneo y qué tipo de equipos puede recibir."
          onClose={closeForms}
        >
          <form
            className="v-form"
            id="competition-form"
            onSubmit={handleSubmitComp}
          >
            <Field label="Nombre">
              <input
                value={formComp.nombre}
                onChange={(e) =>
                  setFormComp({ ...formComp, nombre: e.target.value })
                }
                placeholder="Ej. Liga BetPlay Dimayor"
                required
              />
            </Field>
            <div className="v-form-grid">
              <Field label="Tipo de competición">
                <select
                  value={formComp.tipo}
                  onChange={(e) =>
                    setFormComp({ ...formComp, tipo: e.target.value })
                  }
                >
                  {Object.entries(COMPETITION_TYPES).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="País / ámbito">
                <input
                  value={
                    ["liga_nacional", "copa_nacional"].includes(formComp.tipo)
                      ? formComp.pais
                      : "Internacional"
                  }
                  disabled={
                    !["liga_nacional", "copa_nacional"].includes(formComp.tipo)
                  }
                  onChange={(e) =>
                    setFormComp({ ...formComp, pais: e.target.value })
                  }
                  required
                />
              </Field>
            </div>
            <Field
              label="Confederación"
              hint="Las competiciones globales pueden quedar sin confederación."
            >
              <select
                value={formComp.confederacion_id}
                onChange={(e) =>
                  setFormComp({ ...formComp, confederacion_id: e.target.value })
                }
              >
                {confOptions}
              </select>
            </Field>
            <Field label="URL del logo">
              <input
                type="url"
                value={formComp.logo}
                onChange={(e) =>
                  setFormComp({ ...formComp, logo: e.target.value })
                }
                placeholder="https://…"
                required
              />
            </Field>
            {formFooter}
          </form>
          {toast}
        </Modal>
      )}
      {showTeamForm && (
        <Modal
          title={editEqId ? "Editar equipo" : "Nuevo equipo"}
          subtitle="Añade sus datos básicos. Podrás matricularlo en una competición después."
          onClose={closeForms}
        >
          <form className="v-form" id="team-form" onSubmit={handleSubmitEquipo}>
            <Field label="Nombre">
              <input
                value={formEquipo.nombre}
                onChange={(e) =>
                  setFormEquipo({ ...formEquipo, nombre: e.target.value })
                }
                placeholder="Ej. Deportes Tolima"
                required
              />
            </Field>
            <div className="v-form-grid">
              <Field label="Tipo de equipo">
                <select
                  value={formEquipo.tipo}
                  onChange={(e) =>
                    setFormEquipo({ ...formEquipo, tipo: e.target.value })
                  }
                >
                  <option value="club">Club</option>
                  <option value="seleccion">Selección</option>
                </select>
              </Field>
              <Field
                label="País"
                hint={
                  formEquipo.tipo === "seleccion"
                    ? "El país toma el nombre de la selección."
                    : undefined
                }
              >
                <input
                  value={
                    formEquipo.tipo === "seleccion"
                      ? formEquipo.nombre
                      : formEquipo.pais
                  }
                  disabled={formEquipo.tipo === "seleccion"}
                  onChange={(e) =>
                    setFormEquipo({ ...formEquipo, pais: e.target.value })
                  }
                  required
                />
              </Field>
            </div>
            <Field label="Confederación">
              <select
                value={formEquipo.confederacion_id}
                onChange={(e) =>
                  setFormEquipo({
                    ...formEquipo,
                    confederacion_id: e.target.value,
                  })
                }
              >
                {confOptions}
              </select>
            </Field>
            <Field label="URL del escudo">
              <input
                type="url"
                value={formEquipo.logo}
                onChange={(e) =>
                  setFormEquipo({ ...formEquipo, logo: e.target.value })
                }
                placeholder="https://…"
                required
              />
            </Field>
            {formFooter}
          </form>
          {toast}
        </Modal>
      )}
      {showMatchForm && (
        <Modal
          title="Registrar partido"
          subtitle="Primero elige la competición. Solo podrás seleccionar equipos matriculados."
          onClose={closeForms}
        >
          <form
            className="v-form"
            id="match-form"
            onSubmit={handleSubmitPartido}
          >
            <Field label="Competición">
              <select
                value={formPartido.competicion_id}
                onChange={(e) =>
                  setFormPartido({
                    ...formPartido,
                    competicion_id: e.target.value,
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
                    .filter(
                      (eq) => String(eq.id) !== formPartido.equipo_local_id,
                    )
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
                  Necesitas al menos dos equipos matriculados en esta
                  competición para registrar un partido.
                </p>
              )}
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
            {formFooter}
          </form>
          {toast}
        </Modal>
      )}
    </div>
  );
}
