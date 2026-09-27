import { lazy, Suspense, useState } from "react";
import { ProviderConsole } from "./ProviderConsole";
import { ControlView } from "./ControlView";
import { ModuleTabs } from "./ModuleTabs";
const AutomationView = lazy(() =>
  import("./AutomationView").then((module) => ({
    default: module.AutomationView,
  })),
);

export function DataWorkspace({
  onImported,
  onError,
  onNavigate,
  active = true,
  permissions = [],
}) {
  const [view, setView] = useState("automation");
  return (
    <section aria-label="Gestión de datos">
      <ModuleTabs
        items={[
          { id: "automation", label: "Automatización" },
          { id: "sources", label: "Traer información" },
          { id: "control", label: "Control de datos" },
        ]}
        value={view}
        onChange={setView}
        label="Área de datos"
        id="data-tab"
        panelId="data-panel"
      />
      <div role="tabpanel" id="data-panel" aria-labelledby={`data-tab-${view}`}>
        {view === "automation" && (
          <Suspense fallback={<p role="status">Abriendo la automatización…</p>}>
            <AutomationView
              onError={onError}
              active={active}
              permissions={permissions}
            />
          </Suspense>
        )}
        {view === "sources" &&
          (permissions.includes("manage_sources") ? (
            <ProviderConsole
              onImported={onImported}
              onAutomation={() => setView("automation")}
            />
          ) : (
            <p className="v-info-note">
              Tu cuenta puede consultar los datos. La configuración de fuentes
              requiere permiso de administración.
            </p>
          ))}
        {view === "control" && (
          <ControlView onError={onError} onNavigate={onNavigate} />
        )}
      </div>
    </section>
  );
}
