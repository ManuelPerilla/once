import { useEffect, useState } from "react";
import { apiUrl } from "../api";

export function useLiveUpdates(enabled = true) {
  const [revision, setRevision] = useState(0);
  const [connected, setConnected] = useState(false);
  const [checkedAt, setCheckedAt] = useState(null);
  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return;
    let source;
    let timer;
    const changed = () => {
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        setRevision((value) => value + 1);
        setCheckedAt(new Date());
      }, 400);
    };
    const open = () => {
      source?.close();
      if (document.hidden) {
        setConnected(false);
        return;
      }
      source = new EventSource(apiUrl("/public/changes"));
      source.onopen = () => setConnected(true);
      source.onerror = () => setConnected(false);
      source.addEventListener("change", changed);
      source.addEventListener("reset", changed);
    };
    const visible = () => {
      open();
      if (!document.hidden) changed();
    };
    open();
    document.addEventListener("visibilitychange", visible);
    return () => {
      source?.close();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [enabled]);
  return { revision, connected, checkedAt };
}
