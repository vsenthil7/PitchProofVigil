import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { AuditEntry } from "../lib/types";

// Read-only audit trail. Shows who did what and when, with a quick action
// filter. Backed by /api/audit (populated by the domain event bus).
export function AuditView() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [nextOffset, setNextOffset] = useState<number | null>(null);

  const load = (action?: string, offset = 0) => {
    api
      .listAudit(action || undefined, 25, offset)
      .then((paged) => {
        setEntries((prev) => (offset === 0 ? paged.items : [...prev, ...paged.items]));
        setNextOffset(paged.page.next_offset);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "failed"));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <section className="panel" data-testid="audit-view">
      <div className="panel-head">
        <span className="panel-title">Audit Log</span>
      </div>

      <div className="console-row" style={{ marginBottom: 12 }}>
        <input
          className="input"
          data-testid="audit-filter"
          placeholder="filter by action (e.g. gate.decided)"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(filter)}
        />
        <button className="btn btn-ghost" data-testid="audit-apply" onClick={() => load(filter, 0)}>
          Apply
        </button>
      </div>

      {error && <div className="auth-error">{error}</div>}

      {entries.length === 0 ? (
        <div className="empty" data-testid="audit-empty">
          no audit entries yet
        </div>
      ) : (
        <>
          <div className="audit-list" data-testid="audit-list">
            {entries.map((e) => (
              <div className="audit-row" key={e.id} data-testid="audit-row">
                <span className="audit-action">{e.action}</span>
                <span className="audit-target">{e.target || "—"}</span>
                <span className="audit-actor">{e.actor}</span>
                <span className="audit-time">
                  {new Date(e.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
          {nextOffset != null && (
            <button
              className="btn btn-ghost"
              data-testid="audit-load-more"
              style={{ marginTop: 12 }}
              onClick={() => load(filter, nextOffset)}
            >
              Load more
            </button>
          )}
        </>
      )}
    </section>
  );
}
