import { useState } from "react";
import { api } from "../lib/api";
import type { GateDecision } from "../lib/types";
import { VerdictBadge } from "./VerdictBadge";

const DEFAULT_GOLDEN = [
  "When does Spain play Germany?",
  "When does France play England?",
  "What gate for Brazil section 114?",
  "I want to buy a ticket",
];

interface Props {
  onGateRun: () => void;
}

// Runs the promotion gate across a golden query set and renders the
// pass/block banner — the "block-on-regression" half of the demo loop. The
// default golden set includes the poisoned Spain–Germany query so the gate
// blocks on first run, demonstrating the safety net.
export function GatePanel({ onGateRun }: Props) {
  const [candidate, setCandidate] = useState("prompt-v2");
  const [decision, setDecision] = useState<GateDecision | null>(null);
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

  const failing = decision?.eval_results.filter((r) => r.verdict !== "pass") ?? [];

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
              <div
                className="gate-verdict-label"
                data-testid="gate-verdict-label"
              >
                {decision.passed ? "PROMOTION ALLOWED" : "PROMOTION BLOCKED"}
              </div>
              <div className="gate-reason">{decision.reason}</div>
              <div className="answer-meta" style={{ marginTop: 8 }}>
                <span>candidate: {decision.candidate}</span>
                <span>
                  aggregate: {(decision.aggregate_score * 100).toFixed(0)}%
                </span>
                <span>
                  threshold: {(decision.threshold * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>

          {failing.length > 0 && (
            <div className="evals" data-testid="gate-failing">
              {failing.map((ev) => (
                <div className="eval" key={ev.eval_id}>
                  <span className="eval-name">{ev.evaluator}</span>
                  <span className="eval-expl">{ev.explanation}</span>
                  <VerdictBadge verdict={ev.verdict} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
