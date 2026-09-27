// Superseded reads must never overwrite a newer refresh or restore a closed session.
export function createRequestGate() {
  const active = new Map();
  return {
    start(key) {
      active.get(key)?.abort();
      const controller = new AbortController();
      active.set(key, controller);
      return {
        signal: controller.signal,
        current: () =>
          active.get(key) === controller && !controller.signal.aborted,
      };
    },
    cancelAll() {
      for (const controller of active.values()) controller.abort();
      active.clear();
    },
  };
}
