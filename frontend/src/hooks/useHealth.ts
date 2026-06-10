import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { HealthResponse } from "../lib/types";

// Polls /api/health so the mode pills (real vs mock) and trace count stay
// current. Exposes a manual refresh used after actions that add traces.
export function useHealth(intervalMs = 5000) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setHealth(await api.health());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "unknown error");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { health, error, refresh };
}
