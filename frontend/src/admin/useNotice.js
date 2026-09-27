import { useCallback, useEffect, useRef, useState } from "react";

export function useNotice() {
  const [message, setMessage] = useState(null);
  const timeout = useRef();
  const clear = useCallback(() => {
    clearTimeout(timeout.current);
    setMessage(null);
  }, []);
  const notify = useCallback((tipo, texto) => {
    clearTimeout(timeout.current);
    setMessage({ tipo, texto });
    timeout.current = setTimeout(() => setMessage(null), 3500);
  }, []);
  useEffect(() => () => clearTimeout(timeout.current), []);
  return { message, clear, notify };
}
