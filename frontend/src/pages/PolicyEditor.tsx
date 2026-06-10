import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { EvaluatorPolicyIn, EvaluatorSpec } from "../lib/types";

interface Row extends EvaluatorPolicyIn {
  name: string;
  category: string;
  title: string;
  defaultWeight: number;
}

// Policy editor: lists every registered evaluator and lets an operator toggle
// enable/blocking and tune weight, then saves a new policy version. Reads the
// evaluator catalog from the backend so it always reflects the real registry.
export function PolicyEditor() {
  const [rows, setRows] = useState<Row[]>([]);
  const [threshold, setThreshold] = useState(0.85);
  const [name, setName] = useState("production");
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listEvaluators()
      .then((specs: EvaluatorSpec[]) => {
        setRows(
          specs.map((s) => ({
            name: s.name,
            category: s.category,
            title: s.title,
            defaultWeight: s.default_weight,
            enabled: true,
            weight: s.default_weight,
            blocking: s.blocking_by_default,
            config: {},
          })),
        );
      })
      .catch(() => setStatus("Failed to load evaluators"))
      .finally(() => setLoading(false));
  }, []);

  const update = (idx: number, patch: Partial<Row>) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };

  const save = async () => {
    setStatus(null);
    try {
      const evaluator_policies: Record<string, EvaluatorPolicyIn> = {};
      for (const r of rows) {
        evaluator_policies[r.name] = {
          enabled: r.enabled,
          weight: r.weight,
          blocking: r.blocking,
          config: r.config ?? {},
        };
      }
      const saved = await api.upsertPolicy({
        name,
        threshold,
        fail_on_any_blocking: true,
        evaluator_policies,
      });
      setStatus(`Saved "${saved.name}" v${saved.version}`);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "save failed");
    }
  };

  if (loading) return <div className="empty">loading evaluators…</div>;

  return (
    <section className="panel" data-testid="policy-editor">
      <div className="panel-head">
        <span className="panel-title">Gate Policy Editor</span>
      </div>

      <div className="console-row" style={{ marginBottom: 16 }}>
        <input
          className="input"
          data-testid="policy-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="policy name"
        />
        <div className="field" style={{ margin: 0 }}>
          <input
            className="num-input"
            data-testid="policy-threshold"
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
          />
        </div>
        <button className="btn btn-primary" data-testid="policy-save" onClick={save}>
          Save Version
        </button>
      </div>

      {status && (
        <div className="auth-error" style={{ background: "rgba(44,230,155,0.1)", borderColor: "var(--signal-dim)", color: "var(--signal)" }} data-testid="policy-status">
          {status}
        </div>
      )}

      {rows.map((r, idx) => (
        <div className="policy-eval-row" key={r.name} data-testid={`policy-row-${r.name}`}>
          <div>
            <div className="policy-eval-name">{r.title}</div>
            <div className="policy-eval-meta">
              {r.name} · {r.category}
            </div>
          </div>
          <label className="policy-eval-meta">
            enabled{" "}
            <input
              type="checkbox"
              className="toggle"
              data-testid={`toggle-enabled-${r.name}`}
              checked={r.enabled ?? true}
              onChange={(e) => update(idx, { enabled: e.target.checked })}
            />
          </label>
          <label className="policy-eval-meta">
            blocking{" "}
            <input
              type="checkbox"
              className="toggle"
              data-testid={`toggle-blocking-${r.name}`}
              checked={r.blocking ?? false}
              onChange={(e) => update(idx, { blocking: e.target.checked })}
            />
          </label>
          <input
            className="num-input"
            type="number"
            min={0}
            step={0.5}
            data-testid={`weight-${r.name}`}
            value={r.weight ?? r.defaultWeight}
            onChange={(e) => update(idx, { weight: parseFloat(e.target.value) })}
          />
        </div>
      ))}
    </section>
  );
}
