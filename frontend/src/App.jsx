import { lazy, Suspense } from "react";

const Dashboard = lazy(() => import("./Dashboard"));
const PublicApp = lazy(() => import("./public/PublicApp"));

function App() {
  const publicExperience =
    typeof window !== "undefined" &&
    window.location.pathname.startsWith("/explore");

  return (
    <Suspense
      fallback={
        <div className="v-loading" role="status">
          Abriendo ONCE…
        </div>
      }
    >
      {publicExperience ? <PublicApp /> : <Dashboard />}
    </Suspense>
  );
}

export default App;
