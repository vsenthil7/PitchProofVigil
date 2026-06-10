// Enterprise API client. Carries the bearer token on every authenticated call
// and exposes the full surface: auth, ask, gate, policies, datasets, stats.

import type {
  AnalyticsSummary,
  AskResponse,
  AuditEntry,
  EvaluatorSpec,
  GateDecisionSummary,
  GateResponse,
  Language,
  Policy,
  Role,
  Stats,
  TokenResponse,
  TraceSummary,
  TrendPoint,
  Webhook,
} from "./types";

let _token: string | null = null;

export function setToken(token: string | null): void {
  _token = token;
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  if (_token) h["Authorization"] = `Bearer ${_token}`;
  return h;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  // ---- Auth ----
  async register(
    tenantName: string,
    slug: string,
    email: string,
    password: string,
  ): Promise<{ tenant_id: string; owner_id: string }> {
    return jsonOrThrow(
      await fetch("/api/auth/register", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          tenant_name: tenantName,
          slug,
          owner_email: email,
          owner_password: password,
        }),
      }),
    );
  },

  async login(tenantId: string, email: string, password: string): Promise<TokenResponse> {
    return jsonOrThrow(
      await fetch("/api/auth/login", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ tenant_id: tenantId, email, password }),
      }),
    );
  },

  async createApiKey(name: string, role: Role): Promise<{ api_key: string; prefix: string }> {
    return jsonOrThrow(
      await fetch("/api/auth/api-keys", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ name, role }),
      }),
    );
  },

  // ---- Ask / evaluate ----
  async ask(text: string, language: Language = "en"): Promise<AskResponse> {
    return jsonOrThrow(
      await fetch("/api/ask", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ text, language }),
      }),
    );
  },

  async stats(): Promise<Stats> {
    return jsonOrThrow(await fetch("/api/stats", { headers: authHeaders() }));
  },

  async listTraces(limit = 50): Promise<TraceSummary[]> {
    return jsonOrThrow(await fetch(`/api/traces?limit=${limit}`, { headers: authHeaders() }));
  },

  // ---- Gate ----
  async runGate(candidate: string, queries: string[], language: Language = "en"): Promise<GateResponse> {
    return jsonOrThrow(
      await fetch("/api/gate", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ candidate, queries, language }),
      }),
    );
  },

  async listDecisions(limit = 50): Promise<GateDecisionSummary[]> {
    return jsonOrThrow(await fetch(`/api/gate/decisions?limit=${limit}`, { headers: authHeaders() }));
  },

  // ---- Policies ----
  async listEvaluators(): Promise<EvaluatorSpec[]> {
    return jsonOrThrow(await fetch("/api/policies/evaluators", { headers: authHeaders() }));
  },

  async upsertPolicy(policy: {
    name: string;
    threshold: number;
    fail_on_any_blocking: boolean;
    evaluator_policies: Record<string, unknown>;
  }): Promise<Policy> {
    return jsonOrThrow(
      await fetch("/api/policies", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(policy),
      }),
    );
  },

  async listPolicies(): Promise<Policy[]> {
    return jsonOrThrow(await fetch("/api/policies", { headers: authHeaders() }));
  },

  // ---- Health ----
  async ready(): Promise<{ ready: boolean }> {
    return jsonOrThrow(await fetch("/ready"));
  },

  async securityStatus(): Promise<{
    encryption_at_rest: boolean;
    key_ring_size: number;
    using_ephemeral_dev_key: boolean;
    rotation_supported: boolean;
  }> {
    return jsonOrThrow(await fetch("/api/security/status"));
  },

  // ---- Audit ----
  async listAudit(action?: string, limit = 100): Promise<AuditEntry[]> {
    const q = new URLSearchParams({ limit: String(limit) });
    if (action) q.set("action", action);
    return jsonOrThrow(await fetch(`/api/audit?${q}`, { headers: authHeaders() }));
  },

  // ---- Webhooks ----
  async listWebhooks(): Promise<Webhook[]> {
    return jsonOrThrow(await fetch("/api/webhooks", { headers: authHeaders() }));
  },

  async createWebhook(url: string, eventType: string, secret = ""): Promise<Webhook> {
    return jsonOrThrow(
      await fetch("/api/webhooks", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ url, event_type: eventType, secret }),
      }),
    );
  },

  async createDatasetIdempotent(
    name: string,
    examples: unknown[],
    idempotencyKey: string,
  ): Promise<unknown> {
    return jsonOrThrow(
      await fetch("/api/datasets", {
        method: "POST",
        headers: authHeaders({ "Idempotency-Key": idempotencyKey }),
        body: JSON.stringify({ name, examples }),
      }),
    );
  },

  async deleteWebhook(id: string): Promise<{ deactivated: string }> {
    return jsonOrThrow(
      await fetch(`/api/webhooks/${id}`, { method: "DELETE", headers: authHeaders() }),
    );
  },

  // ---- Analytics ----
  async analyticsSummary(windowHours = 24): Promise<AnalyticsSummary> {
    return jsonOrThrow(
      await fetch(`/api/analytics/summary?window_hours=${windowHours}`, {
        headers: authHeaders(),
      }),
    );
  },

  async passRateTrend(windowHours = 24, bucketMinutes = 60): Promise<TrendPoint[]> {
    return jsonOrThrow(
      await fetch(
        `/api/analytics/pass-rate?window_hours=${windowHours}&bucket_minutes=${bucketMinutes}`,
        { headers: authHeaders() },
      ),
    );
  },

  async latencyTrend(windowHours = 24, bucketMinutes = 60): Promise<TrendPoint[]> {
    return jsonOrThrow(
      await fetch(
        `/api/analytics/latency?window_hours=${windowHours}&bucket_minutes=${bucketMinutes}`,
        { headers: authHeaders() },
      ),
    );
  },
};
