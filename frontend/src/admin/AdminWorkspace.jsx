import { useMutation } from "./useMutation";
import { enrollmentCandidates } from "./selectors";
import {
  emptyConfederation,
  emptyCompetition,
  emptyTeam,
  emptyMatch,
} from "./forms/defaults";
import { DeleteDialog } from "./forms/DeleteDialog";
import { ConfederationForm } from "./forms/ConfederationForm";
import { CompetitionForm } from "./forms/CompetitionForm";
import { TeamForm } from "./forms/TeamForm";
import { MatchForm } from "./forms/MatchForm";
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "../api";
import { runViewTransition } from "../lib/viewTransition";
import {
  EMPTY_FILTERS,
  changeFilters,
  countryOptions,
  filterCatalog,
  normalize,
} from "../catalogFilters";
import { summarizeAdmin } from "../adminSummary";
import { workspaceNavigation, workspaceSections } from "./sections";
import { EnrollmentView } from "./EnrollmentView";
import { MatchesView } from "./MatchesView";
import { CatalogView } from "./CatalogView";
import { HomeView } from "./HomeView";
import { ModuleTabs } from "./ModuleTabs";
import { catalogModules } from "./catalogModules";
import { ContextView } from "./context/ContextView";
import { DataWorkspace } from "./DataWorkspace";
import { RostersView } from "./RostersView";
import {
  EMPTY_MATCH_FILTERS,
  changeMatchContext,
  filterEnrollments,
} from "./organization";
import { Brand, Icon, SectionArt } from "../AdminUI";
import { CrestCredits } from "../components/ui/CrestCredits";

export function AdminWorkspace({ data, notice }) {
  const {
    partidos,
    confederaciones,
    competiciones,
    equipos,
    temporadas,
    fases,
    estadios,
    catalogsReady,
    matchesReady,
    refreshing,
    updatedAt,
    fetchCatalogs,
    fetchPartidos,
    refreshData,
    handleApiError,
  } = data;
  const { message: mensajeApi, notify, clear: setMensajeApi } = notice;
  const handleLogout = async () => {
    notice.clear();
    await data.logout();
  };
  const [activeTab, setActiveTab] = useState("inicio");
  const changeSection = (nextTab) => {
    if (nextTab === activeTab) return;
    runViewTransition(() => {
      setActiveTab(nextTab);
      window.scrollTo({ top: 0, behavior: "instant" });
      document
        .getElementById("workspace-content")
        ?.focus({ preventScroll: true });
    });
  };

  const [catalogTab, setCatalogTab] = useState("competiciones");
  const [matchFilter, setMatchFilter] = useState("");
  const [matchContext, setMatchContext] = useState({ ...EMPTY_MATCH_FILTERS });
  const [enrollmentContext, setEnrollmentContext] = useState({
    competition: "",
    type: "",
  });
  const [dataVisited, setDataVisited] = useState(false);
  const [onlyFree, setOnlyFree] = useState(false);
  const [enrollmentSearch, setEnrollmentSearch] = useState("");
  const [enrollmentMode, setEnrollmentMode] = useState("registry");
  const [showMatchForm, setShowMatchForm] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Estados para CRUD
  const [editConfId, setEditConfId] = useState(null);
  const [formConf, setFormConf] = useState(emptyConfederation());

  const [editCompId, setEditCompId] = useState(null);
  const [formComp, setFormComp] = useState(emptyCompetition());

  const [editEqId, setEditEqId] = useState(null);
  const [formEquipo, setFormEquipo] = useState(emptyTeam());

  const [formMatricula, setFormMatricula] = useState({
    equipo_id: "",
    competicion_id: "",
  });
  const [formPartido, setFormPartido] = useState(emptyMatch());

  const [filtersByModule, setFiltersByModule] = useState({});
  const catalogFilters = filtersByModule[catalogTab] || EMPTY_FILTERS;
  const setCatalogFilters = (value) =>
    setFiltersByModule((current) => ({
      ...current,
      [catalogTab]:
        typeof value === "function"
          ? value(current[catalogTab] || EMPTY_FILTERS)
          : value,
    }));
  const [showConfForm, setShowConfForm] = useState(false);
  const [showCompForm, setShowCompForm] = useState(false);
  const [showTeamForm, setShowTeamForm] = useState(false);
  const catalog = filterCatalog(competiciones, equipos, catalogFilters);
  const countries = countryOptions(
    catalogTab === "competiciones" ? competiciones : [],
    catalogTab === "equipos" ? equipos : [],
    catalogFilters.confederation,
  );
  const updateFilter = (field, value) =>
    setCatalogFilters((current) => changeFilters(current, field, value));
  const clearFilters = () => setCatalogFilters({ ...EMPTY_FILTERS });
  const [loading, runMutation] = useMutation(handleApiError);

  // --- CRUD CONFEDERACIONES ---
  const handleSubmitConf = async (e) => {
    e.preventDefault();
    await runMutation(async () => {
      await apiRequest(
        editConfId ? `/confederaciones/${editConfId}` : "/confederaciones/",
        {
          method: editConfId ? "PUT" : "POST",
          body: formConf,
        },
      );
      notify("success", "Confederación guardada");
      setFormConf(emptyConfederation());
      setEditConfId(null);
      setShowConfForm(false);
      await fetchCatalogs();
    });
  };
  const handleEditConf = (c) => {
    setFormConf({ nombre: c.nombre, logo: c.logo });
    setEditConfId(c.id);
    setShowConfForm(true);
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
    await runMutation(async () => {
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
      setFormComp(emptyCompetition());
      setEditCompId(null);
      setShowCompForm(false);
      await Promise.all([fetchCatalogs(), fetchPartidos()]);
    });
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
    await runMutation(async () => {
      await apiRequest(editEqId ? `/equipos/${editEqId}` : "/equipos/", {
        method: editEqId ? "PUT" : "POST",
        body: {
          ...formEquipo,
          confederacion_id: parseInt(formEquipo.confederacion_id) || null,
        },
      });
      notify("success", "Equipo guardado");
      setFormEquipo(emptyTeam());
      setEditEqId(null);
      setShowTeamForm(false);
      await Promise.all([fetchCatalogs(), fetchPartidos()]);
    });
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
    await runMutation(async () => {
      const data = await apiRequest(
        `/equipos/${formMatricula.equipo_id}/matricular/${formMatricula.competicion_id}`,
        { method: "POST" },
      );
      notify(data.ok ? "success" : "error", data.mensaje);
      if (data.ok) {
        await fetchCatalogs();
        setFormMatricula({ equipo_id: "", competicion_id: "" });
      }
    });
  };

  const handleSubmitPartido = async (e) => {
    e.preventDefault();
    await runMutation(async () => {
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
          marcador_local:
            formPartido.marcador_local === ""
              ? null
              : Number(formPartido.marcador_local),
          marcador_visitante:
            formPartido.marcador_visitante === ""
              ? null
              : Number(formPartido.marcador_visitante),
          estado: formPartido.estado,
        },
      });
      notify("success", "Partido registrado");
      setShowMatchForm(false);
      setFormPartido(emptyMatch());
      await fetchPartidos();
    });
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

  const equiposDisponiblesParaMatricula = enrollmentCandidates(
    equipos,
    competiciones.find(
      (c) => String(c.id) === String(formMatricula.competicion_id),
    ),
  );

  const localSummary = summarizeAdmin(competiciones, equipos, partidos);
  const summary = {
    ...localSummary,
    ...Object.fromEntries(
      ["scheduled", "live", "finished", "incomplete", "unregistered"].map(
        (key) => [
          key,
          { length: data.counts[key] ?? localSummary[key].length },
        ],
      ),
    ),
  };
  const ready = matchesReady;
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
      setFormConf(emptyConfederation());
      setShowConfForm(true);
    }
    if (type === "competiciones") {
      setFormComp(emptyCompetition());
      setShowCompForm(true);
    }
    if (type === "equipos") {
      setFormEquipo(emptyTeam());
      setShowTeamForm(true);
    }
    if (type === "partidos") {
      setFormPartido(emptyMatch());
      setShowMatchForm(true);
    }
  };
  const goCatalog = (type) => {
    setCatalogTab(type);
    changeSection("ecosistema");
  };
  const goEnrollments = (freeOnly = false) => {
    setOnlyFree(freeOnly);
    setEnrollmentSearch("");
    setEnrollmentContext({ competition: "", type: "" });
    setEnrollmentMode("registry");
    changeSection("matriculas");
  };
  const heroAction = () => {
    if (activeTab === "inicio") goCatalog("competiciones");
    else if (activeTab === "ecosistema") openCreate(catalogTab);
    else if (activeTab === "arena") openCreate("partidos");
    else setEnrollmentMode("create");
  };
  const formOpen =
    showConfForm ||
    showCompForm ||
    showTeamForm ||
    showMatchForm ||
    Boolean(pendingDelete);
  const catalogsRequested = useRef(false);
  useEffect(() => {
    if (
      (!["inicio", "datos"].includes(activeTab) || formOpen) &&
      !catalogsReady &&
      !catalogsRequested.current
    ) {
      catalogsRequested.current = true;
      fetchCatalogs().finally(() => {
        catalogsRequested.current = false;
      });
    }
  }, [activeTab, formOpen, catalogsReady, fetchCatalogs]);
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
  const enrollmentItems = filterEnrollments(equipos, {
    ...enrollmentContext,
    search: enrollmentSearch,
    state: onlyFree ? "free" : "",
  });
  const selectedCatalogModule = catalogModules.find(
    (item) => item.id === catalogTab,
  );
  const toast = mensajeApi && (
    <div
      role={mensajeApi.tipo === "error" ? "alert" : "status"}
      className={`v-toast ${mensajeApi.tipo === "error" ? "v-toast-error" : ""}`}
    >
      <Icon name={mensajeApi.tipo === "error" ? "alert" : "check"} />
      {mensajeApi.texto}
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
            <span>CENTRO DE OPERACIONES</span>
            <small>FÚTBOL, DESDE DENTRO.</small>
          </div>
          <div className="v-top-actions">
            <a href="/explore" className="once-admin-explore">
              Explorar ONCE <Icon name="arrow" />
            </a>
            <span className="v-admin-tag">
              <i />
              {data.username || "Administración"}
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
              <span className="v-avatar">
                {(data.username || "AD").slice(0, 2).toUpperCase()}
              </span>
              <span>Salir</span>
              <Icon name="logout" />
            </button>
          </div>
        </div>
      </header>
      <div className="v-navigation">
        <span className="once-sidebar-label">TU ESPACIO DE TRABAJO</span>
        <nav className="v-nav" aria-label="Navegación principal">
          {workspaceNavigation.map(([tab, number]) => (
            <button
              key={tab}
              aria-label={workspaceSections[tab].label}
              aria-current={activeTab === tab ? "page" : undefined}
              onClick={() => {
                if (tab === "datos") setDataVisited(true);
                changeSection(tab);
              }}
            >
              <Icon
                name={
                  {
                    inicio: "home",
                    ecosistema: "grid",
                    matriculas: "link",
                    arena: "pitch",
                    datos: "globe",
                  }[tab]
                }
              />
              <span>{workspaceSections[tab].label}</span>
              <small>{number}</small>
            </button>
          ))}
        </nav>
        <span className="v-nav-caption">
          <Icon name="sparkles" />
          <span>Tu espacio ONCE</span>
          <strong>
            El juego está
            <br />
            en tus manos.
          </strong>
          <a href="/explore">
            Ver la experiencia pública <Icon name="arrow" />
          </a>
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
                      ecosistema: "Las entidades que dan forma a ONCE.",
                      matriculas:
                        "Gestiona quién participa en cada competición.",
                      arena: "Todos tus encuentros, organizados.",
                      datos:
                        "Trae información, revisa su procedencia y comprueba su calidad.",
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
          {activeTab !== "datos" && (
            <section
              className="v-hero"
              aria-label={`Presentación de ${section.label}`}
            >
              <div className="v-hero-copy">
                <span className="v-eyebrow">{section.eyebrow}</span>
                <h2>{section.title}</h2>
                <p>{section.description}</p>
                {!(
                  activeTab === "ecosistema" &&
                  !["competiciones", "equipos", "confederaciones"].includes(
                    catalogTab,
                  )
                ) && (
                  <button className="v-btn v-btn-primary" onClick={heroAction}>
                    {section.action}
                    <Icon
                      name={section.icon === "grid" ? "arrow" : section.icon}
                    />
                  </button>
                )}
              </div>
              <SectionArt variant={activeTab} />
              <div className="v-hero-baseline" aria-hidden="true">
                <span>ONCE / OPERACIONES</span>
                <span>EL FÚTBOL SE EXPLORA. AQUÍ SE ORGANIZA.</span>
                <Icon name="globe" />
              </div>
            </section>
          )}

          {activeTab === "inicio" && (
            <HomeView
              ready={ready}
              competitions={competiciones}
              teams={equipos}
              summary={summary}
              counts={data.counts}
              goCatalog={goCatalog}
              goEnrollments={goEnrollments}
              setMatchFilter={(value) => {
                setMatchFilter(value);
                setMatchContext({ ...EMPTY_MATCH_FILTERS });
              }}
              changeSection={changeSection}
              openCreate={openCreate}
              goData={() => {
                setDataVisited(true);
                changeSection("datos");
              }}
            />
          )}

          {activeTab === "ecosistema" && (
            <section
              aria-label="Módulos del catálogo"
              className="once-catalog-workspace"
            >
              <ModuleTabs
                items={catalogModules}
                value={catalogTab}
                onChange={setCatalogTab}
                label="Tipo de catálogo"
                id="catalog-tab"
                panelId="catalog-module-panel"
              />
              <div
                role="tabpanel"
                id="catalog-module-panel"
                aria-labelledby={`catalog-tab-${catalogTab}`}
              >
                {[
                  "competiciones",
                  "equipos",
                  "confederaciones",
                  "plantillas",
                ].includes(catalogTab) && (
                  <div className="once-module-intro">
                    <span className="v-eyebrow">
                      CATÁLOGO / {selectedCatalogModule.label}
                    </span>
                    <h2>{selectedCatalogModule.label}</h2>
                    <p>{selectedCatalogModule.description}</p>
                  </div>
                )}
                {["competiciones", "equipos", "confederaciones"].includes(
                  catalogTab,
                ) ? (
                  <CatalogView
                    catalogTab={catalogTab}
                    setCatalogTab={setCatalogTab}
                    catalogsReady={catalogsReady}
                    competitions={competiciones}
                    teams={equipos}
                    confederations={confederaciones}
                    filters={catalogFilters}
                    setFilters={setCatalogFilters}
                    onRelated={(type, filters) => {
                      setFiltersByModule((current) => ({
                        ...current,
                        [type]: { ...EMPTY_FILTERS, ...filters },
                      }));
                      setCatalogTab(type);
                    }}
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
                ) : catalogTab === "plantillas" ? (
                  <RostersView teams={equipos} onError={handleApiError} />
                ) : (
                  <ContextView
                    key={catalogTab}
                    module={catalogTab}
                    data={data}
                    onSaved={fetchCatalogs}
                    onError={handleApiError}
                  />
                )}
              </div>
            </section>
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
              mode={enrollmentMode}
              setMode={setEnrollmentMode}
              context={enrollmentContext}
              setContext={setEnrollmentContext}
              total={equipos.length}
            />
          )}

          {activeTab === "arena" && (
            <MatchesView
              filter={matchFilter}
              setFilter={setMatchFilter}
              incompleteCount={summary.incomplete.length}
              matches={partidos}
              revision={updatedAt?.getTime() || 0}
              onDelete={handleEliminarPartido}
              onCreate={() => openCreate("partidos")}
              context={matchContext}
              updateContext={(field, value) =>
                setMatchContext((current) =>
                  changeMatchContext(current, field, value),
                )
              }
              clearFilters={() => {
                setMatchContext({ ...EMPTY_MATCH_FILTERS });
                setMatchFilter("");
              }}
              competitions={competiciones}
              seasons={temporadas}
              phases={fases}
              teams={equipos}
              total={data.counts.matches || 0}
              ready={matchesReady}
              onError={handleApiError}
            />
          )}
          {dataVisited && (
            <div hidden={activeTab !== "datos"}>
              <DataWorkspace
                active={activeTab === "datos"}
                permissions={data.permissions}
                onImported={() =>
                  Promise.all([fetchCatalogs(), fetchPartidos()])
                }
                onError={handleApiError}
                onNavigate={(module) => {
                  const target = {
                    confederations: "confederaciones",
                    competitions: "competiciones",
                    teams: "equipos",
                    seasons: "temporadas",
                    stages: "fases",
                    venues: "estadios",
                    players: "jugadores",
                  }[module];
                  if (target) goCatalog(target);
                  else if (module === "enrollments") goEnrollments();
                  else {
                    setMatchContext({ ...EMPTY_MATCH_FILTERS });
                    setMatchFilter("");
                    changeSection("arena");
                  }
                }}
              />
            </div>
          )}
          <footer className="v-footer">
            <Brand />
            <span>DISEÑADO PARA MOVER EL JUEGO.</span>
            <small>ADMINISTRACIÓN / ACCESO RESTRINGIDO</small>
            <div className="once-footer-credits">
              <CrestCredits />
            </div>
          </footer>
        </div>
      </main>
      {!formOpen && toast}

      {pendingDelete && (
        <DeleteDialog
          pendingDelete={pendingDelete}
          deleting={deleting}
          setPendingDelete={setPendingDelete}
          setMensajeApi={setMensajeApi}
          deleteEntity={deleteEntity}
          toast={toast}
        />
      )}

      {showConfForm && (
        <ConfederationForm
          editConfId={editConfId}
          formConf={formConf}
          setFormConf={setFormConf}
          closeForms={closeForms}
          handleSubmitConf={handleSubmitConf}
          competiciones={competiciones}
          equipos={equipos}
          asociarHuerfano={asociarHuerfano}
          loading={loading}
          toast={toast}
        />
      )}
      {showCompForm && (
        <CompetitionForm
          editCompId={editCompId}
          formComp={formComp}
          setFormComp={setFormComp}
          closeForms={closeForms}
          handleSubmitComp={handleSubmitComp}
          confederaciones={confederaciones}
          loading={loading}
          toast={toast}
        />
      )}
      {showTeamForm && (
        <TeamForm
          editEqId={editEqId}
          formEquipo={formEquipo}
          setFormEquipo={setFormEquipo}
          closeForms={closeForms}
          handleSubmitEquipo={handleSubmitEquipo}
          confederaciones={confederaciones}
          loading={loading}
          toast={toast}
        />
      )}
      {showMatchForm && (
        <MatchForm
          formPartido={formPartido}
          setFormPartido={setFormPartido}
          closeForms={closeForms}
          handleSubmitPartido={handleSubmitPartido}
          competiciones={competiciones}
          equipos={equipos}
          temporadas={temporadas}
          fases={fases}
          estadios={estadios}
          loading={loading}
          toast={toast}
        />
      )}
    </div>
  );
}
