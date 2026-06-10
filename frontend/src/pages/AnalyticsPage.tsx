import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { AnalyticsSummary, TrendPoint } from "../lib/types";
import { TrendChart } from "../components/TrendChart";

const WINDOWS = [
  { label: "1h", hours: 1, bucket: 5 },
  { label: "24h", hours: 24, bucket: 60 },
  { label: "7d", hours: 168, bucket: 360 },
];

// Trends dashboard: pass-rate and latency over time plus headline summary.
// Reads from /api/analytics, which time-buckets persisted evaluations/traces.
export function AnalyticsPage() {
  const [windowIdx, setWindowIdx] = useState(1);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [passRate, setPassRate] = useState<TrendPoint[]>([]);
  const [latency, setLatency] = useState<TrendPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  const win = WINDOWS[windowIdx];

  useEffect(() => {
    let active = true;
    Promise.all([
      api.analyticsSummary(win.hours),
      api.passRateTrend(win.hours, win.bucket),
      api.latencyTrend(win.hours, win.bucket),
    ])
      .then(([s, pr, lat]) => {
        if (!active) return;
        setSummary(s);
        setPassRate(pr);
        setLatency(lat);
        setError(null);
      })
      .catch((e) => active && setError(e instanceof Error ? e.message : "failed"));
    return () => {
      active = false;
    };
  }, [win.hours, win.bucket]);

  return (
    <section className="panel" data-testid="analytics-page">
      <div className="panel-head">
        <span className="panel-title">Analytics & Trends</span>
        <div className="window-toggle" data-testid="window-toggle">
          {WINDOWS.map((w, i) => (
            <button
              key={w.label}
              className={`chip ${i === windowIdx ? "chip-active" : ""}`}
              data-testid={`window-${w.label}`}
              onClick={() => setWindowIdx(i)}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="auth-error">{error}</div>}

      <div className="metrics" data-testid="analytics-summary">
        <div className="metric">
          <div className="metric-value">{summary?.evaluations ?? 0}</div>
          <div className="metric-label">Evaluations ({win.label})</div>
        </div>
        <div className="metric">
          <div className="metric-value">
            {summary ? `${Math.round(summary.pass_rate * 100)}%` : "—"}
          </div>
          <div className="metric-label">Pass Rate</div>
        </div>
      </div>

      <div style={{ marginTop: 18 }}>
        <TrendChart
          points={passRate}
          label="Pass rate"
          percent
          format={(v) => `${Math.round(v * 100)}%`}
          color="var(--signal)"
        />
      </div>
      <div style={{ marginTop: 18 }}>
        <TrendChart
          points={latency}
          label="Mean latency (ms)"
          format={(v) => `${v.toFixed(0)}ms`}
          color="var(--amber)"
        />
      </div>
    </section>
  );
}
