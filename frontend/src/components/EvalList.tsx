import { useState } from "react";
import type { EvalOut } from "../lib/types";
import { VerdictBadge } from "./VerdictBadge";

interface Props {
  evaluations: EvalOut[];
}

// Expandable evaluator rows. Click a row to reveal its structured findings
// (code, message, severity, evidence) — the drill-down an operator uses to
// understand *why* an evaluator failed.
export function EvalList({ evaluations }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <div className="evals" data-testid="eval-list">
      {evaluations.map((ev) => {
        const expanded = open === ev.evaluator;
        const hasDetail = ev.findings.length > 0;
        return (
          <div key={ev.evaluator} data-testid="eval-row">
            <div
              className={`eval ${hasDetail ? "eval-expand" : ""}`}
              onClick={() => hasDetail && setOpen(expanded ? null : ev.evaluator)}
            >
              <div>
                <div className="eval-name">{ev.evaluator}</div>
                <div className="eval-cat">
                  {ev.category} · conf {Math.round(ev.confidence * 100)}%
                </div>
              </div>
              <span className="eval-expl">{ev.summary}</span>
              <VerdictBadge verdict={ev.verdict} />
            </div>
            {expanded &&
              ev.findings.map((f, i) => (
                <div className={`finding ${f.severity}`} key={i} data-testid="finding">
                  <div className="finding-code">
                    {f.code} · {f.severity}
                  </div>
                  <div className="finding-msg">{f.message}</div>
                  {Object.keys(f.evidence).length > 0 && (
                    <div className="finding-evidence">
                      {JSON.stringify(f.evidence, null, 2)}
                    </div>
                  )}
                </div>
              ))}
          </div>
        );
      })}
    </div>
  );
}
