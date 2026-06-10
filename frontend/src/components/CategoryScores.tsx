interface Props {
  scores: Record<string, number>;
}

function colorFor(value: number): string {
  if (value >= 0.85) return "var(--signal)";
  if (value >= 0.6) return "var(--amber)";
  return "var(--hazard)";
}

const ORDER = [
  "correctness",
  "grounding",
  "safety",
  "quality",
  "performance",
  "compliance",
  "schema",
];

// Horizontal bars showing the per-category weighted score (0..1).
export function CategoryScores({ scores }: Props) {
  const entries = Object.entries(scores).sort(
    (a, b) => ORDER.indexOf(a[0]) - ORDER.indexOf(b[0]),
  );
  if (entries.length === 0) {
    return <div className="empty">no category scores yet</div>;
  }
  return (
    <div className="cat-grid" data-testid="category-scores">
      {entries.map(([cat, val]) => (
        <div className="cat-row" key={cat} data-testid={`cat-${cat}`}>
          <span className="cat-name">{cat}</span>
          <div className="cat-track">
            <div
              className="cat-fill"
              style={{ width: `${Math.round(val * 100)}%`, background: colorFor(val) }}
            />
          </div>
          <span className="cat-val" style={{ color: colorFor(val) }}>
            {Math.round(val * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}
