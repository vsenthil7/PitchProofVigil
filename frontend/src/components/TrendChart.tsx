import type { TrendPoint } from "../lib/types";

interface Props {
  points: TrendPoint[];
  label: string;
  // format the value (e.g. percent vs ms)
  format?: (v: number) => string;
  // 0..1 domain (percent) vs auto-scaled
  percent?: boolean;
  color?: string;
}

// Minimal dependency-free line chart rendered as SVG. Plots TrendPoint.value
// across buckets; percent mode pins the y-domain to 0..1.
export function TrendChart({
  points,
  label,
  format = (v) => v.toFixed(2),
  percent = false,
  color = "var(--signal)",
}: Props) {
  if (points.length === 0) {
    return (
      <div className="trend-empty" data-testid={`trend-empty-${label}`}>
        no data in this window yet
      </div>
    );
  }

  const W = 520;
  const H = 140;
  const pad = 24;
  const values = points.map((p) => p.value);
  const maxV = percent ? 1 : Math.max(...values, 0.0001);
  const minV = 0;

  const x = (i: number) =>
    pad + (i / Math.max(1, points.length - 1)) * (W - pad * 2);
  const y = (v: number) =>
    H - pad - ((v - minV) / (maxV - minV)) * (H - pad * 2);

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`)
    .join(" ");

  const last = points[points.length - 1];

  return (
    <div className="trend" data-testid={`trend-${label}`}>
      <div className="trend-head">
        <span className="trend-label">{label}</span>
        <span className="trend-current" style={{ color }}>
          {format(last.value)}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="trend-svg" preserveAspectRatio="none">
        <line x1={pad} y1={H - pad} x2={W - pad} y2={H - pad} className="trend-axis" />
        <line x1={pad} y1={pad} x2={pad} y2={H - pad} className="trend-axis" />
        <path d={path} fill="none" stroke={color} strokeWidth={2} />
        {points.map((p, i) => (
          <circle key={i} cx={x(i)} cy={y(p.value)} r={2.5} fill={color} />
        ))}
      </svg>
    </div>
  );
}
