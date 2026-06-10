import type { DriftPoint } from "../lib/types";

interface Props {
  points: DriftPoint[];
  evaluator: string;
}

// Dependency-free SVG drift chart: shades the p10-p90 band and overlays the
// mean-score line, matching the project's SVG-chart convention (no recharts).
export function DriftChart({ points, evaluator }: Props) {
  if (points.length === 0) {
    return (
      <div className="drift-empty" data-testid="drift-empty">
        no drift data for {evaluator} in this window yet
      </div>
    );
  }

  const W = 520;
  const H = 200;
  const PAD = 28;
  const n = points.length;
  const xAt = (i: number) =>
    PAD + (n === 1 ? (W - 2 * PAD) / 2 : (i * (W - 2 * PAD)) / (n - 1));
  // Score domain is pinned to 0..1.
  const yAt = (v: number) => H - PAD - v * (H - 2 * PAD);

  const meanPath = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(p.mean_score).toFixed(1)}`)
    .join(" ");

  // p10-p90 band as a closed polygon (p90 forward, p10 back).
  const bandTop = points.map((p, i) => `${xAt(i).toFixed(1)},${yAt(p.p90).toFixed(1)}`);
  const bandBottom = points
    .slice()
    .reverse()
    .map((p, i) => {
      const idx = n - 1 - i;
      return `${xAt(idx).toFixed(1)},${yAt(p.p10).toFixed(1)}`;
    });
  const bandPoints = [...bandTop, ...bandBottom].join(" ");

  return (
    <div className="drift-chart" data-testid="drift-chart">
      <h3 className="drift-title">Score drift: {evaluator}</h3>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`drift for ${evaluator}`}>
        <polygon points={bandPoints} fill="var(--signal)" opacity={0.15} />
        <path d={meanPath} fill="none" stroke="var(--signal)" strokeWidth={2} />
        {points.map((p, i) => (
          <circle key={p.bucket} cx={xAt(i)} cy={yAt(p.mean_score)} r={2.5} fill="var(--signal)">
            <title>
              {new Date(p.bucket).toLocaleString()} — mean {p.mean_score.toFixed(2)} (p10{" "}
              {p.p10.toFixed(2)} / p90 {p.p90.toFixed(2)}), pass {(p.pass_rate * 100).toFixed(0)}%, n=
              {p.count}
            </title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
