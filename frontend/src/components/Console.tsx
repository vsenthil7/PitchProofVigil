import { useState } from "react";
import { api } from "../lib/api";
import type { AskResponse, Language } from "../lib/types";
import { VerdictBadge } from "./VerdictBadge";

const QUICK_QUERIES = [
  "When does Spain play Germany?",
  "When does France play England?",
  "What gate for Brazil section 114?",
  "I want to buy a ticket",
];

const LANGS: Language[] = ["en", "es", "fr", "de", "pt"];

interface Props {
  onTraceAdded: () => void;
}

// The live console: operator types a fan query, the agent answers, and the
// eval verdicts render immediately beneath — the "trace → eval verdict" half
// of the demo loop.
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
              {result.trace.response?.text}
            </p>
            <div className="answer-meta">
              <span>intent: {result.trace.response?.detected_intent}</span>
              <span>model: {result.trace.response?.model}</span>
              <span>
                latency: {result.trace.response?.latency_ms.toFixed(2)}ms
              </span>
              <span>
                score: {(result.aggregate_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>

          <div className="evals" data-testid="eval-list">
            {result.eval_results.map((ev) => (
              <div className="eval" key={ev.eval_id} data-testid="eval-row">
                <span className="eval-name">{ev.evaluator}</span>
                <span className="eval-expl">{ev.explanation}</span>
                <VerdictBadge verdict={ev.verdict} />
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
