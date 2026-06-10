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
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [security, setSecurity] = useState<{
    encryption_at_rest: boolean;
    key_ring_size: number;
    using_ephemeral_dev_key: boolean;
  } | null>(null);

  const load = () => {
    api
      .listWebhooks()
      .then(setHooks)
      .catch((e) => setError(e instanceof Error ? e.message : "failed"));
  };

  useEffect(() => {
    load();
    api.securityStatus().then(setSecurity).catch(() => setSecurity(null));
  }, []);

  const create = async () => {
    setError(null);
    try {
      await api.createWebhook(url, eventType, secret);
      setUrl("");
      setSecret("");
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

      {security && (
        <div
          className={`security-banner ${security.using_ephemeral_dev_key ? "warn" : "ok"}`}
          data-testid="security-banner"
        >
          <span className="security-icon" aria-hidden>
            {security.using_ephemeral_dev_key ? "⚠" : "🔒"}
          </span>
          <span>
            {security.encryption_at_rest
              ? `Secrets encrypted at rest (key ring: ${security.key_ring_size})`
              : "Secrets are NOT encrypted"}
            {security.using_ephemeral_dev_key
              ? " — using an ephemeral dev key; set ENCRYPTION_KEYS in production."
              : "."}
          </span>
        </div>
      )}

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
        <input
          className="input"
          data-testid="webhook-secret"
          placeholder="signing secret (optional)"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          style={{ maxWidth: 220 }}
        />
        <button
          className="btn btn-primary"
          data-testid="webhook-create"
          onClick={create}
          disabled={!url.trim()}
        >
          Subscribe
        </button>
      </div>

      <p className="hint" data-testid="webhook-hint">
        Deliveries are signed with HMAC-SHA256 (header <code>X-PPV-Signature: t=…,v1=…</code>)
        and retried up to 3× on 5xx. Verify with your secret to reject replays.
      </p>

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
          {hooks.map((h) => {
            const ok = h.last_status != null && h.last_status >= 200 && h.last_status < 300;
            const statusCls = h.last_status == null ? "pending" : ok ? "ok" : "fail";
            return (
              <div className="webhook-row" key={h.id} data-testid="webhook-row">
                <span className="webhook-event">{h.event_type}</span>
                <span className="webhook-url">{h.url}</span>
                <span className={`webhook-status ${h.active ? "on" : "off"}`}>
                  {h.active ? "active" : "inactive"}
                </span>
                <span
                  className={`delivery-badge ${statusCls}`}
                  data-testid={`delivery-${h.id}`}
                >
                  {h.last_status == null ? "no delivery" : `last ${h.last_status}`}
                </span>
                <button
                  className="btn btn-ghost btn-small"
                  data-testid={`webhook-delete-${h.id}`}
                  onClick={() => remove(h.id)}
                >
                  Remove
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
