// Thin API client over the FastAPI backend. Uses same-origin relative URLs so
// the Vite proxy (dev) or the reverse proxy (prod) routes to the backend.

import type {
  AskResponse,
  DriftResponse,
  GateDecision,
  HealthResponse,
  Language,
  Trace,
} from "./types";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  async health(): Promise<HealthResponse> {
    return jsonOrThrow<HealthResponse>(await fetch("/api/health"));
  },

  async ask(text: string, language: Language = "en"): Promise<AskResponse> {
    return jsonOrThrow<AskResponse>(
      await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }),
      }),
    );
  },

  async listTraces(limit = 50): Promise<Trace[]> {
    return jsonOrThrow<Trace[]>(await fetch(`/api/traces?limit=${limit}`));
  },

  async getTrace(traceId: string): Promise<Trace> {
    return jsonOrThrow<Trace>(await fetch(`/api/traces/${traceId}`));
  },

  async runGate(
    candidate: string,
    queries: string[],
    language: Language = "en",
  ): Promise<GateDecision> {
    return jsonOrThrow<GateDecision>(
      await fetch("/api/gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate, queries, language }),
      }),
    );
  },

  async drift(): Promise<DriftResponse> {
    return jsonOrThrow<DriftResponse>(await fetch("/api/drift"));
  },

  liveSocketUrl(): string {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/api/live`;
  },
};
