import type { Cost } from "../lib/types";

// Compact token + cost readout for an agent run.
export function CostPanel({ cost }: { cost: Cost }) {
  return (
    <div className="cost-grid" data-testid="cost-panel">
      <div className="cost-cell">
        <div className="cost-num">{cost.calls}</div>
        <div className="cost-lbl">LLM Calls</div>
      </div>
      <div className="cost-cell">
        <div className="cost-num">{cost.input_tokens}</div>
        <div className="cost-lbl">Input Tok</div>
      </div>
      <div className="cost-cell">
        <div className="cost-num">{cost.output_tokens}</div>
        <div className="cost-lbl">Output Tok</div>
      </div>
      <div className="cost-cell">
        <div className="cost-num">${cost.cost_usd.toFixed(5)}</div>
        <div className="cost-lbl">Est. Cost</div>
      </div>
    </div>
  );
}
