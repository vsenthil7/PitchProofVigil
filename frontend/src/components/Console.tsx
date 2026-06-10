import { useState } from "react";
import { api } from "../lib/api";
import type { AskResponse, Language } from "../lib/types";
import { CategoryScores } from "./CategoryScores";
import { CostPanel } from "./CostPanel";
import { EvalList } from "./EvalList";

const QUICK_QUERIES = [
  "When does Spain play Germany?",
  "What gate for Brazil section 114?",
  "I want to buy a ticket",
  "hotel near France England match",
];

const LANGS: Language[] = ["en", "es", "fr", "de", "pt"];

interface Props {
  onTraceAdded: () => void;
}

// Live console: ask the agent, then see the answer plus the full evaluation
// report — aggregate verdict, category bars, per-evaluator drill-down, cost.
export function Console({ onTraceAdded }: Props) {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState<Language>("en");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (q?: string) => {
    const query = (q ?? text).trim();
    if (!query) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.ask(query, language);
      setResult(res);
      onTraceAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel" data-testid="console-panel">
      <div className="panel-head">
        <span className="panel-title">Live Console</span>
      </div>

      <div className="console-row">
        <input
          className="input"
          data-testid="ask-input"
          placeholder="Ask the World Cup concierge agent…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
        />
        <select
          className="select"
          data-testid="lang-select"
          value={language}
          onChange={(e) => setLanguage(e.target.value as Language)}
        >
          {LANGS.map((l) => (
            <option key={l} value={l}>
              {l.toUpperCase()}
            </option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          data-testid="ask-btn"
          onClick={() => submit()}
          disabled={loading || !text.trim()}
        >
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      <div className="quick-row">
        {QUICK_QUERIES.map((q) => (
          <button
            key={q}
            className="chip"
            data-testid="quick-chip"
            onClick={() => {
              setText(q);
              submit(q);
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {error && (
        <div className="answer" data-testid="console-error">
          <p className="answer-text" style={{ color: "var(--hazard)" }}>
            {error}
          </p>
        </div>
      )}

      {result && (
        <div data-testid="ask-result">
          <div className="answer">
            <p className="answer-text" data-testid="answer-text">
              {result.answer}
            </p>
            <div className="answer-meta">
              <span>intent: {result.intent}</span>
              <span>model: {result.model}</span>
              <span>latency: {result.latency_ms.toFixed(2)}ms</span>
              <span
                data-testid="aggregate-verdict"
                style={{ color: result.passed ? "var(--signal)" : "var(--hazard)" }}
              >
                {result.passed ? "PASS" : "BLOCK"} · {(result.aggregate_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div style={{ marginTop: 14 }}>
            <span className="panel-title">Category Scores</span>
            <div style={{ marginTop: 10 }}>
              <CategoryScores scores={result.category_scores} />
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <span className="panel-title">Evaluators ({result.evaluations.length})</span>
            <EvalList evaluations={result.evaluations} />
          </div>

          <div style={{ marginTop: 16 }}>
            <span className="panel-title">Run Cost</span>
            <div style={{ marginTop: 10 }}>
              <CostPanel cost={result.cost} />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
