// Enterprise API client. Carries the bearer token on every authenticated call
// and exposes the full surface: auth, ask, gate, policies, datasets, stats.

import type {
  AskResponse,
  EvaluatorSpec,
  GateDecisionSummary,
  GateResponse,
  Language,
  Policy,
  Role,
  Stats,
  TokenResponse,
  TraceSummary,
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
};
