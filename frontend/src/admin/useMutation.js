import { useState } from "react";

export function useMutation(onError) {
  const [loading, setLoading] = useState(false);
  const run = async (operation) => {
    setLoading(true);
    try {
      await operation();
    } catch (error) {
      onError(error);
    } finally {
      setLoading(false);
    }
  };
  return [loading, run];
}
