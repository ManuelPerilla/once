import { useCallback, useEffect, useMemo, useState } from "react";
import { apiCollection, apiRequest } from "../api";
import { createRequestGate } from "../lib/requestGate";

const catalogNames = [
  "confederaciones",
  "competiciones",
  "equipos",
  "temporadas",
  "fases",
  "estadios",
];
const empty = {
  partidos: [],
  ...Object.fromEntries(catalogNames.map((name) => [name, []])),
  catalogsReady: false,
  matchesReady: false,
  updatedAt: null,
};

async function readCatalogs(signal) {
  const lists = await Promise.all(
    catalogNames.map((name) => apiCollection(`/${name}/`, { signal })),
  );
  return Object.fromEntries(
    catalogNames.map((name, index) => [name, lists[index]]),
  );
}

export function useAdminData(notify) {
  const [status, setStatus] = useState("checking");
  const [data, setData] = useState(empty);
  const [refreshing, setRefreshing] = useState(false);
  const requests = useMemo(() => createRequestGate(), []);

  const clearSession = useCallback(() => {
    requests.cancelAll();
    setStatus("anonymous");
    setData(empty);
  }, [requests]);

  const handleApiError = useCallback(
    (error) => {
      if (error.name === "AbortError") return;
      if (error.status === 401) clearSession();
      notify(
        "error",
        error.status ? error.message : "No se pudo conectar con el servidor.",
      );
    },
    [clearSession, notify],
  );

  const acceptMatches = useCallback((partidos) => {
    setData((current) => ({
      ...current,
      partidos,
      matchesReady: true,
      updatedAt: new Date(),
    }));
  }, []);
  const acceptCatalogs = useCallback((catalogs) => {
    setData((current) => ({
      ...current,
      ...catalogs,
      catalogsReady: true,
      updatedAt: new Date(),
    }));
  }, []);

  useEffect(() => {
    const request = requests.start("session");
    apiCollection("/partidos/", { signal: request.signal })
      .then((partidos) => {
        if (!request.current()) return;
        acceptMatches(partidos);
        setStatus("authenticated");
      })
      .catch((error) => {
        if (!request.current()) return;
        if (error.status !== 401) handleApiError(error);
        setStatus("anonymous");
      });
    return () => requests.cancelAll();
  }, [requests, acceptMatches, handleApiError]);

  useEffect(() => {
    if (status !== "authenticated") return;
    const request = requests.start("catalogs");
    readCatalogs(request.signal)
      .then((catalogs) => {
        if (request.current()) acceptCatalogs(catalogs);
      })
      .catch((error) => {
        if (request.current()) handleApiError(error);
      });
  }, [status, requests, acceptCatalogs, handleApiError]);

  const refresh = async (kind) => {
    const request = requests.start(kind);
    try {
      const result =
        kind === "catalogs"
          ? await readCatalogs(request.signal)
          : await apiCollection("/partidos/", { signal: request.signal });
      if (request.current())
        (kind === "catalogs" ? acceptCatalogs : acceptMatches)(result);
    } catch (error) {
      if (request.current()) handleApiError(error);
    }
  };

  const login = async (credentials) => {
    const request = requests.start("session");
    try {
      await apiRequest("/login", {
        method: "POST",
        body: credentials,
        signal: request.signal,
      });
      const partidos = await apiCollection("/partidos/", {
        signal: request.signal,
      });
      if (request.current()) {
        acceptMatches(partidos);
        setStatus("authenticated");
      }
    } catch (error) {
      if (request.current()) handleApiError(error);
    }
  };

  const logout = async () => {
    try {
      await apiRequest("/logout", { method: "POST" });
      clearSession();
    } catch (error) {
      handleApiError(error);
    }
  };

  const refreshData = async () => {
    setRefreshing(true);
    try {
      await Promise.all([refresh("matches"), refresh("catalogs")]);
    } finally {
      setRefreshing(false);
    }
  };

  return {
    ...data,
    status,
    login,
    logout,
    refreshing,
    refreshData,
    handleApiError,
    fetchPartidos: () => refresh("matches"),
    fetchCatalogs: () => refresh("catalogs"),
  };
}
