import { useEffect, useState } from "react";
import { apiRequest } from "../api";

export function matchQuery(filters = {}, page = 1, pageSize = 24) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  for (const [name, value] of Object.entries(filters)) {
    if (
      value !== "" &&
      value !== null &&
      value !== undefined &&
      value !== false
    )
      query.set(name, String(value));
  }
  return query.toString();
}

export function usePagedMatches({
  enabled = true,
  publicView = true,
  filters = {},
  page = 1,
  pageSize = 24,
  revision = 0,
}) {
  const query = matchQuery(filters, page, pageSize);
  const [state, setState] = useState({
    items: [],
    total: 0,
    pending: true,
    error: "",
    query: "",
  });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timer = setTimeout(
      () => {
        setState((current) => ({ ...current, pending: true, error: "" }));
        apiRequest(`${publicView ? "/public" : ""}/partidos/page?${query}`, {
          signal: controller.signal,
        })
          .then((result) => {
            if (!controller.signal.aborted)
              setState({ ...result, pending: false, error: "", query });
          })
          .catch((failure) => {
            if (!controller.signal.aborted)
              setState((current) => ({
                ...current,
                pending: false,
                error: failure.message,
                status: failure.status,
                query,
              }));
          });
      },
      filters.search ? 250 : 0,
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [enabled, publicView, query, revision, filters.search]);
  return {
    ...state,
    pending: enabled && (state.pending || state.query !== query),
  };
}
