import type { Verdict } from "../lib/types";

// Small colored verdict label reused across eval rows and panels.
export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`verdict ${verdict}`} data-testid={`verdict-${verdict}`}>
      {verdict}
    </span>
  );
}
