// Types mirroring the backend domain models (app/core/models.py).

export type Language = "en" | "es" | "fr" | "de" | "pt" | "ar" | "ja";

export type IntentType =
  | "kickoff_time"
  | "gate_info"
  | "ticketing"
  | "travel"
  | "stadium_nav"
  | "translation"
  | "general";

export type SpanKind = "AGENT" | "LLM" | "TOOL" | "RETRIEVER" | "CHAIN";

export type EvalVerdict = "pass" | "fail" | "warn";

export interface ConciergeRequest {
  request_id: string;
  text: string;
  language: Language;
  session_id: string;
  created_at: string;
}

export interface ConciergeResponse {
  request_id: string;
  text: string;
  detected_intent: IntentType;
  language: Language;
  grounded_facts: Record<string, unknown>;
  latency_ms: number;
  model: string;
  created_at: string;
}

export interface Span {
  span_id: string;
  trace_id: string;
  parent_id: string | null;
  name: string;
  kind: SpanKind;
  start_time: string;
  end_time: string | null;
  attributes: Record<string, unknown>;
  status: string;
}

export interface Trace {
  trace_id: string;
  request: ConciergeRequest;
  response: ConciergeResponse | null;
  spans: Span[];
  created_at: string;
}

export interface EvalResult {
  eval_id: string;
  trace_id: string;
  evaluator: string;
  verdict: EvalVerdict;
  score: number;
  explanation: string;
  created_at: string;
}

export interface GateDecision {
  decision_id: string;
  candidate: string;
  passed: boolean;
  aggregate_score: number;
  threshold: number;
  eval_results: EvalResult[];
  reason: string;
  created_at: string;
}

export interface AskResponse {
  trace: Trace;
  eval_results: EvalResult[];
  aggregate_score: number;
}

export interface HealthResponse {
  status: string;
  modes: Record<string, string>;
  trace_count: number;
}

export interface DriftPoint {
  window_start: string;
  window_end: string;
  intent: IntentType;
  language: Language;
  embedding_distance: number;
  sample_count: number;
}

export interface DriftResponse {
  point: DriftPoint;
  alerting: boolean;
}

export interface LiveEvent {
  type: "trace" | "gate";
  trace_id?: string;
  intent?: string;
  aggregate?: number;
  verdicts?: EvalVerdict[];
  candidate?: string;
  passed?: boolean;
}
