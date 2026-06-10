import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Stats } from "../lib/types";

// Polls /api/stats so the dashboard tiles (trace count, verdict mix, per-
// evaluator failure rate) stay current. Exposes a manual refresh.
export function useStats(intervalMs = 6000) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStats(await api.stats());
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

  return { stats, error, refresh };
}
