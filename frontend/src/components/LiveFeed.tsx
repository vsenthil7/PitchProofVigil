import type { LiveEvent } from "../lib/types";

interface Props {
  events: LiveEvent[];
  connected: boolean;
}

function severityClass(event: LiveEvent): string {
  if (event.type === "gate") return event.passed ? "ok" : "bad";
  const verdicts = event.verdicts ?? [];
  if (verdicts.includes("fail")) return "bad";
  if (verdicts.includes("warn")) return "warn";
  return "ok";
}

function describe(event: LiveEvent): string {
  if (event.type === "gate") {
    return `Gate "${event.candidate}" → ${event.passed ? "ALLOWED" : "BLOCKED"}`;
  }
  return `Trace evaluated · intent ${event.intent}`;
}

// Real-time event stream from the backend WebSocket. New ask/gate events slide
// in at the top, color-coded by severity (the "alert in minutes" story).
export function LiveFeed({ events, connected }: Props) {
  return (
    <section className="panel" data-testid="live-panel">
      <div className="panel-head">
        <span className="panel-title">Live Evaluation Feed</span>
        <span
          className={`conn ${connected ? "up" : "down"}`}
          data-testid="conn-status"
        >
          <span className="dot" />
          {connected ? "streaming" : "offline"}
        </span>
      </div>

      {events.length === 0 ? (
        <div className="empty" data-testid="feed-empty">
          awaiting evaluation events…
        </div>
      ) : (
        <div className="feed" data-testid="feed-list">
          {events.map((event, i) => (
            <div
              className={`feed-item ${severityClass(event)}`}
              key={`${event.type}-${event.trace_id ?? event.candidate}-${i}`}
              data-testid="feed-item"
            >
              <span className="feed-kind">{event.type}</span>
              <span className="feed-main">{describe(event)}</span>
              <span className="feed-score">
                {event.aggregate != null
                  ? `${(event.aggregate * 100).toFixed(0)}%`
                  : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
