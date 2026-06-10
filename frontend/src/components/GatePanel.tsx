import { useState } from "react";
import { api } from "../lib/api";
import type { GateResponse } from "../lib/types";
import { CategoryScores } from "./CategoryScores";

const DEFAULT_GOLDEN = [
  "When does Spain play Germany?",
  "When does France play England?",
  "What gate for Brazil section 114?",
  "I want to buy a ticket",
];

interface Props {
  onGateRun: () => void;
}

function DeltaBadge({ value }: { value: number }) {
  const cls = value > 0.001 ? "up" : value < -0.001 ? "down" : "flat";
  const sign = value > 0 ? "+" : "";
  return (
    <span className={`delta ${cls}`}>
      {sign}
      {value.toFixed(2)}
    </span>
  );
}

// Promotion gate: runs a golden set, shows pass/block with category scores,
// baseline deltas vs the last passing decision, and any regressions.
export function GatePanel({ onGateRun }: Props) {
  const [candidate, setCandidate] = useState("prompt-v2");
  const [decision, setDecision] = useState<GateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.runGate(candidate, DEFAULT_GOLDEN);
      setDecision(res);
      onGateRun();
    } catch (e) {
      setError(e instanceof Error ? e.message : "gate failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel" data-testid="gate-panel">
      <div className="panel-head">
        <span className="panel-title">Promotion Gate</span>
      </div>

      <div className="console-row">
        <input
          className="input"
          data-testid="candidate-input"
          value={candidate}
          onChange={(e) => setCandidate(e.target.value)}
          placeholder="candidate build / prompt id"
        />
        <button
          className="btn btn-primary"
          data-testid="gate-btn"
          onClick={run}
          disabled={loading || !candidate.trim()}
        >
          {loading ? "Evaluating…" : "Run Gate"}
        </button>
      </div>

      {error && (
        <div className="answer" data-testid="gate-error">
          <p className="answer-text" style={{ color: "var(--hazard)" }}>
            {error}
          </p>
        </div>
      )}

      {decision && (
        <div data-testid="gate-result">
          <div
            className={`gate-banner ${decision.passed ? "passed" : "blocked"}`}
            data-testid="gate-banner"
          >
            <div className="gate-icon">{decision.passed ? "✓" : "✕"}</div>
            <div>
              <div className="gate-verdict-label" data-testid="gate-verdict-label">
                {decision.passed ? "PROMOTION ALLOWED" : "PROMOTION BLOCKED"}
              </div>
              <div className="gate-reason">{decision.reason}</div>
              <div className="answer-meta" style={{ marginTop: 8 }}>
                <span>candidate: {decision.candidate}</span>
                <span>aggregate: {(decision.aggregate_score * 100).toFixed(0)}%</span>
                <span>threshold: {(decision.threshold * 100).toFixed(0)}%</span>
                <span>traces: {decision.trace_count}</span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 14 }}>
            <span className="panel-title">Category Scores</span>
            <div style={{ marginTop: 10 }}>
              <CategoryScores scores={decision.category_scores} />
            </div>
          </div>

          {Object.keys(decision.baseline_deltas).length > 0 && (
            <div style={{ marginTop: 16 }}>
              <span className="panel-title">Baseline Comparison</span>
              <div className="cat-grid" style={{ marginTop: 10 }}>
                {Object.entries(decision.baseline_deltas).map(([cat, d]) => (
                  <div className="cat-row" key={cat} data-testid={`delta-${cat}`}>
                    <span className="cat-name">{cat}</span>
                    <span />
                    <DeltaBadge value={d} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {decision.regressions.length > 0 && (
            <div className="regression-list" data-testid="regressions">
              <span className="panel-title">Regressions</span>
              {decision.regressions.map((r, i) => (
                <div className="regression-item" key={i}>
                  ⚠ {r}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
