import { useEffect } from "react";
import { Brand } from "./components/ui/Brand";
import { LoginView } from "./admin/LoginView";
import { AdminWorkspace } from "./admin/AdminWorkspace";
import { useAdminData } from "./admin/useAdminData";
import { useNotice } from "./admin/useNotice";

export default function Dashboard() {
  const notice = useNotice();
  const data = useAdminData(notice.notify);
  useEffect(() => {
    document.title = "ONCE · Centro de operaciones";
  }, []);
  if (data.status === "checking")
    return (
      <div className="v-loading">
        <Brand />
        <span className="v-loading-bar" />
        <p>Preparando tu espacio de trabajo…</p>
      </div>
    );
  return data.status === "authenticated" ? (
    <AdminWorkspace data={data} notice={notice} />
  ) : (
    <LoginView login={data.login} notice={notice} />
  );
}
