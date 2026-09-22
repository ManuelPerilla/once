import {
  COMPETITION_TYPES,
  EMPTY_FILTERS,
} from "../catalogFilters";
import { Crest } from "../components/ui/Crest";
import { EmptyState } from "../components/ui/EmptyState";
import { Field } from "../components/ui/Field";
import { Icon } from "../components/ui/Icon";

const tabOrder = ["competiciones", "equipos", "confederaciones"];

export function CatalogView({
  catalogTab,
  setCatalogTab,
  catalogsReady,
  competitions,
  teams,
  confederations,
  filters,
  setFilters,
  updateFilter,
  countries,
  catalog,
  items,
  total,
  clearFilters,
  openCreate,
  closeForms,
  onEditConfederation,
  onEditCompetition,
  onEditTeam,
  onDeleteConfederation,
  onDeleteCompetition,
  onDeleteTeam,
}) {
  const changeTab = (type) => {
    setCatalogTab(type);
    clearFilters();
  };

  return (
    <section
      className="v-panel v-catalog-panel"
      aria-label="Catálogo del ecosistema"
    >
      <div className="v-tabs" role="tablist" aria-label="Tipo de catálogo">
        {[
          ["competiciones", "Competiciones", competitions.length],
          ["equipos", "Equipos", teams.length],
          ["confederaciones", "Confederaciones", confederations.length],
        ].map(([type, label, count]) => (
          <button
            role="tab"
            id={`tab-${type}`}
            aria-controls="catalog-panel"
            aria-selected={catalogTab === type}
            tabIndex={catalogTab === type ? 0 : -1}
            key={type}
            onKeyDown={(event) => {
              if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
              event.preventDefault();
              const index =
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? tabOrder.length - 1
                    : (tabOrder.indexOf(type) +
                        (event.key === "ArrowRight" ? 1 : -1) +
                        tabOrder.length) %
                      tabOrder.length;
              const next = tabOrder[index];
              changeTab(next);
              document.getElementById(`tab-${next}`)?.focus();
            }}
            onClick={() => changeTab(type)}
          >
            {label}
            <small>{catalogsReady ? count : "—"}</small>
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id="catalog-panel"
        aria-labelledby={`tab-${catalogTab}`}
      >
        <div className="v-filter-bar">
          <label className="v-field v-search">
            <span>Buscar por nombre</span>
            <input
              type="search"
              placeholder={`Buscar ${catalogTab}…`}
              value={filters.search}
              onChange={(event) => updateFilter("search", event.target.value)}
            />
          </label>

          {catalogTab !== "confederaciones" && (
            <>
              <Field label="Confederación">
                <select
                  value={filters.confederation}
                  onChange={(event) =>
                    updateFilter("confederation", event.target.value)
                  }
                >
                  <option value="">Todas las confederaciones</option>
                  {confederations.map((confederation) => (
                    <option key={confederation.id} value={confederation.id}>
                      {confederation.nombre}
                    </option>
                  ))}
                  <option value="unassigned">Sin confederación / globales</option>
                </select>
              </Field>

              <Field label="País / ámbito">
                <select
                  value={filters.country}
                  onChange={(event) => updateFilter("country", event.target.value)}
                >
                  <option value="">Todos los países y ámbitos</option>
                  {countries.map((country) => (
                    <option key={country} value={country}>{country}</option>
                  ))}
                </select>
              </Field>
            </>
          )}

          {catalogTab === "competiciones" && (
            <Field label="Tipo de competición">
              <select
                value={filters.competitionType}
                onChange={(event) =>
                  updateFilter("competitionType", event.target.value)
                }
              >
                <option value="">Todos los tipos</option>
                {Object.entries(COMPETITION_TYPES).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </Field>
          )}

          {catalogTab === "equipos" && (
            <Field label="Matriculados en">
              <select
                value={catalog.selectedCompetition}
                onChange={(event) =>
                  updateFilter("competition", event.target.value)
                }
              >
                <option value="">Cualquier matrícula</option>
                {catalog.availableCompetitions.map((competition) => (
                  <option key={competition.id} value={competition.id}>
                    {competition.nombre}
                  </option>
                ))}
              </select>
            </Field>
          )}
        </div>

        <div className="v-catalog-toolbar">
          <p role="status">
            {catalogsReady
              ? `${items.length} de ${total} ${catalogTab}`
              : "Cargando catálogo…"}
          </p>

          {catalogTab === "equipos" && (
            <div
              className="v-segments"
              role="group"
              aria-label="Tipo de equipo"
            >
              {[
                ["", "Todos"],
                ["club", "Clubes"],
                ["seleccion", "Selecciones"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  aria-pressed={filters.teamType === value}
                  onClick={() => updateFilter("teamType", value)}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          <button className="v-text-btn" onClick={clearFilters}>
            Limpiar filtros
          </button>
        </div>

        {catalogsReady && items.length === 0 && (
          <EmptyState
            title={
              total
                ? "No encontramos coincidencias"
                : "Tu catálogo está por comenzar"
            }
            action={total ? "Limpiar filtros" : "Añadir primer registro"}
            onAction={total ? clearFilters : () => openCreate(catalogTab)}
          >
            {total
              ? "Prueba con otro nombre o ajusta los filtros."
              : "Crea las entidades que organizarán tu universo futbolístico."}
          </EmptyState>
        )}

        {items.map((item) => (
          <article className="v-catalog-row" key={item.id}>
            <span className="v-record-id" aria-label={`Registro ${item.id}`}>
              #{String(item.id).padStart(3, "0")}
            </span>
            <Crest src={item.logo} name={item.nombre} />

            <div className="v-entity-name">
              <strong>{item.nombre}</strong>
              <span>
                {catalogTab === "confederaciones"
                  ? `${competitions.filter((competition) => competition.confederacion_id === item.id).length} competiciones · ${teams.filter((team) => team.confederacion_id === item.id).length} equipos`
                  : `${catalogTab === "equipos" ? (item.tipo === "seleccion" ? "Selección" : "Club") : COMPETITION_TYPES[item.tipo]} · ${item.pais} · ${confederations.find((confederation) => confederation.id === item.confederacion_id)?.nombre || "Sin confederación"}`}
              </span>

              {catalogTab === "equipos" && (
                <div className="v-entity-tags">
                  {item.competiciones?.length ? (
                    item.competiciones.map((competition) => (
                      <span key={competition.id}>{competition.nombre}</span>
                    ))
                  ) : (
                    <span>Sin matrícula</span>
                  )}
                </div>
              )}
            </div>

            <div className="v-entity-actions">
              {catalogTab === "competiciones" && (
                <button
                  className="v-text-btn"
                  onClick={() => {
                    setFilters((current) => ({
                      ...current,
                      search: "",
                      teamType: "",
                      competition: String(item.id),
                    }));
                    setCatalogTab("equipos");
                  }}
                >
                  Ver equipos
                  <Icon name="arrow" />
                </button>
              )}

              {catalogTab === "confederaciones" && (
                <button
                  className="v-text-btn"
                  onClick={() => {
                    setFilters({
                      ...EMPTY_FILTERS,
                      confederation: String(item.id),
                    });
                    setCatalogTab("competiciones");
                  }}
                >
                  Explorar
                  <Icon name="arrow" />
                </button>
              )}

              <button
                className="v-icon-btn"
                aria-label={`Editar ${item.nombre}`}
                onClick={() => {
                  closeForms();
                  (catalogTab === "confederaciones"
                    ? onEditConfederation
                    : catalogTab === "competiciones"
                      ? onEditCompetition
                      : onEditTeam)(item);
                }}
              >
                <Icon name="edit" />
              </button>

              <button
                className="v-icon-btn v-danger"
                aria-label={`Eliminar ${item.nombre}`}
                onClick={() =>
                  (catalogTab === "confederaciones"
                    ? onDeleteConfederation
                    : catalogTab === "competiciones"
                      ? onDeleteCompetition
                      : onDeleteTeam)(item.id)
                }
              >
                <Icon name="trash" />
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
