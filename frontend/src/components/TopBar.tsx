import type { HealthResponse } from "../lib/types";

interface Props {
  health: HealthResponse | null;
}

const INTEGRATIONS: Array<[string, string]> = [
  ["gemini", "Gemini"],
  ["phoenix", "Phoenix"],
  ["arize_ax", "Arize AX"],
];

// Top command bar: product mark, title, and one pill per integration showing
// whether it is running against the real service or a mock.
export function TopBar({ health }: Props) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark" aria-hidden>
          ◎
        </div>
        <div>
          <div className="brand-title">PitchProof Vigil</div>
          <div className="brand-sub">AGENT RELIABILITY CONTROL ROOM · T1 ARIZE</div>
        </div>
      </div>
      <div className="mode-pills" data-testid="mode-pills">
        {INTEGRATIONS.map(([key, label]) => {
          const mode = health?.modes?.[key] ?? "…";
          const cls = mode === "real" ? "real" : mode === "mock" ? "mock" : "";
          return (
            <span
              key={key}
              className={`pill ${cls}`}
              data-testid={`pill-${key}`}
              title={`${label}: ${mode}`}
            >
              <span className="dot" />
              {label} · {mode}
            </span>
          );
        })}
      </div>
    </header>
  );
}
