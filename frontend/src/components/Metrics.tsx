import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { DriftResponse, HealthResponse } from "../lib/types";

interface Props {
  health: HealthResponse | null;
  refreshKey: number;
}

// Three live metric tiles: total traces observed, current drift distance (with
// an alert state), and the count of integrations running against real backends.
export function Metrics({ health, refreshKey }: Props) {
  const [drift, setDrift] = useState<DriftResponse | null>(null);

  useEffect(() => {
    api
      .drift()
      .then(setDrift)
      .catch(() => setDrift(null));
  }, [refreshKey]);

  const realCount = health
    ? Object.values(health.modes).filter((m) => m === "real").length
    : 0;
  const totalIntegrations = health ? Object.keys(health.modes).length : 3;
  const alerting = drift?.alerting ?? false;

  return (
    <div className="metrics" data-testid="metrics">
      <div className="metric" data-testid="metric-traces">
        <div className="metric-value">{health?.trace_count ?? 0}</div>
        <div className="metric-label">Traces Observed</div>
      </div>
      <div
        className={`metric ${alerting ? "alert" : ""}`}
        data-testid="metric-drift"
      >
        <div className="metric-value">
          {drift ? drift.point.embedding_distance.toFixed(2) : "—"}
        </div>
        <div className="metric-label">
          Drift {alerting ? "· ALERT" : "Distance"}
        </div>
      </div>
      <div className="metric" data-testid="metric-real">
        <div className="metric-value">
          {realCount}/{totalIntegrations}
        </div>
        <div className="metric-label">Live Integrations</div>
      </div>
    </div>
  );
}
