import type { Stats } from "../lib/types";

interface Props {
  stats: Stats | null;
}

// Situational-awareness panel: headline tiles plus per-evaluator failure rates
// and the verdict mix — the platform's at-a-glance health.
export function StatsPanel({ stats }: Props) {
  const verdicts = stats?.verdict_breakdown ?? {};
  const totalVerdicts = Object.values(verdicts).reduce((a, b) => a + b, 0);
  const rates = Object.entries(stats?.failure_rate_by_evaluator ?? {})
    .filter(([, r]) => r > 0)
    .sort((a, b) => b[1] - a[1]);

  return (
    <section className="panel" data-testid="stats-panel">
      <div className="panel-head">
        <span className="panel-title">Platform Health</span>
      </div>

      <div className="metrics" data-testid="metrics">
        <div className="metric" data-testid="metric-traces">
          <div className="metric-value">{stats?.trace_count ?? 0}</div>
          <div className="metric-label">Traces Observed</div>
        </div>
        <div className="metric" data-testid="metric-verdicts">
          <div className="metric-value">{totalVerdicts}</div>
          <div className="metric-label">Evaluations Run</div>
        </div>
        <div
          className={`metric ${rates.length > 0 ? "alert" : ""}`}
          data-testid="metric-failing"
        >
          <div className="metric-value">{rates.length}</div>
          <div className="metric-label">Failing Evaluators</div>
        </div>
      </div>

      {rates.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <span className="panel-title">Failure Rate by Evaluator</span>
          <div className="cat-grid" style={{ marginTop: 10 }}>
            {rates.map(([ev, rate]) => (
              <div className="cat-row" key={ev} data-testid={`fail-${ev}`}>
                <span className="cat-name">{ev}</span>
                <div className="cat-track">
                  <div
                    className="cat-fill"
                    style={{ width: `${Math.round(rate * 100)}%`, background: "var(--hazard)" }}
                  />
                </div>
                <span className="cat-val" style={{ color: "var(--hazard)" }}>
                  {Math.round(rate * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {Object.keys(stats?.by_intent ?? {}).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <span className="panel-title">Traffic by Intent</span>
          <div className="cat-grid" style={{ marginTop: 10 }}>
            {Object.entries(stats!.by_intent).map(([intent, count]) => (
              <div className="cat-row" key={intent} data-testid={`intent-${intent}`}>
                <span className="cat-name">{intent}</span>
                <span />
                <span className="cat-val">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
