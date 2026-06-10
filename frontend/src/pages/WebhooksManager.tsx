import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Webhook } from "../lib/types";

const EVENT_TYPES = [
  "trace_evaluated",
  "blocking_failure",
  "gate_decided",
  "regression_detected",
];

// CRUD for per-tenant webhook subscriptions. Backed by /api/webhooks
// (MANAGE_POLICIES gated on the server; viewers see read-only failures).
export function WebhooksManager() {
  const [hooks, setHooks] = useState<Webhook[]>([]);
  const [url, setUrl] = useState("");
  const [eventType, setEventType] = useState(EVENT_TYPES[2]);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api
      .listWebhooks()
      .then(setHooks)
      .catch((e) => setError(e instanceof Error ? e.message : "failed"));
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    setError(null);
    try {
      await api.createWebhook(url, eventType);
      setUrl("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "create failed");
    }
  };

  const remove = async (id: string) => {
    setError(null);
    try {
      await api.deleteWebhook(id);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "delete failed");
    }
  };

  return (
    <section className="panel" data-testid="webhooks-manager">
      <div className="panel-head">
        <span className="panel-title">Webhook Subscriptions</span>
      </div>

      <div className="console-row" style={{ marginBottom: 12 }}>
        <input
          className="input"
          data-testid="webhook-url"
          placeholder="https://your-endpoint/hook"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <select
          className="select"
          data-testid="webhook-event"
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
        >
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          data-testid="webhook-create"
          onClick={create}
          disabled={!url.trim()}
        >
          Subscribe
        </button>
      </div>

      {error && (
        <div className="auth-error" data-testid="webhook-error">
          {error}
        </div>
      )}

      {hooks.length === 0 ? (
        <div className="empty" data-testid="webhooks-empty">
          no webhook subscriptions
        </div>
      ) : (
        <div data-testid="webhook-list">
          {hooks.map((h) => (
            <div className="webhook-row" key={h.id} data-testid="webhook-row">
              <span className="webhook-event">{h.event_type}</span>
              <span className="webhook-url">{h.url}</span>
              <span className={`webhook-status ${h.active ? "on" : "off"}`}>
                {h.active ? "active" : "inactive"}
                {h.last_status != null ? ` · ${h.last_status}` : ""}
              </span>
              <button
                className="btn btn-ghost btn-small"
                data-testid={`webhook-delete-${h.id}`}
                onClick={() => remove(h.id)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
