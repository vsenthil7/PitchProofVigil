import type { EvalVerdict } from "../lib/types";

// Small colored verdict label reused in eval rows and the live feed.
export function VerdictBadge({ verdict }: { verdict: EvalVerdict }) {
  return (
    <span className={`verdict ${verdict}`} data-testid={`verdict-${verdict}`}>
      {verdict}
    </span>
  );
}
