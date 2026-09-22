import Dashboard from "./Dashboard";
import PublicApp from "./public/PublicApp";

function App() {
  const publicExperience =
    typeof window !== "undefined" &&
    window.location.pathname.startsWith("/explore");

  return publicExperience ? <PublicApp /> : <Dashboard />;
}

export default App;
