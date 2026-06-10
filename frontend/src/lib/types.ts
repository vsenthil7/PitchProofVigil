// Types mirroring the enterprise API (schemas_v2.py).

export type Language = "en" | "es" | "fr" | "de" | "pt";
export type Role = "owner" | "admin" | "operator" | "viewer";
export type Verdict = "pass" | "warn" | "fail" | "error" | "skip";

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Finding {
  code: string;
  message: string;
  severity: string;
  evidence: Record<string, unknown>;
}

export interface EvalOut {
  evaluator: string;
  category: string;
  verdict: Verdict;
  score: number;
  confidence: number;
  summary: string;
  findings: Finding[];
  duration_ms: number;
}

export interface Cost {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface ToolCall {
  tool: string;
  ok: boolean;
  error: string | null;
}

export interface AskResponse {
  trace_id: string;
  answer: string;
  intent: string;
  model: string;
  latency_ms: number;
  aggregate_score: number;
  passed: boolean;
  reason: string;
  category_scores: Record<string, number>;
  evaluations: EvalOut[];
  cost: Cost;
  tool_calls: ToolCall[];
}

export interface GateResponse {
  decision_id: string;
  candidate: string;
  passed: boolean;
  aggregate_score: number;
  threshold: number;
  category_scores: Record<string, number>;
  baseline_deltas: Record<string, number>;
  regressions: string[];
  reason: string;
  trace_count: number;
}

export interface EvaluatorSpec {
  name: string;
  version: string;
  category: string;
  title: string;
  description: string;
  default_weight: number;
  blocking_by_default: boolean;
}

export interface EvaluatorPolicyIn {
  enabled?: boolean;
  weight?: number | null;
  blocking?: boolean | null;
  config?: Record<string, unknown>;
}

export interface Policy {
  id: string;
  name: string;
  version: number;
  threshold: number;
  fail_on_any_blocking: boolean;
  evaluator_policies: Record<string, EvaluatorPolicyIn>;
  is_active: boolean;
}

export interface Stats {
  trace_count: number;
  by_intent: Record<string, number>;
  verdict_breakdown: Record<string, number>;
  failure_rate_by_evaluator: Record<string, number>;
}

export interface TraceSummary {
  trace_id: string;
  request_text: string;
  intent: string | null;
  response_text: string | null;
  latency_ms: number;
  created_at: string;
}

export interface GateDecisionSummary {
  decision_id: string;
  candidate: string;
  passed: boolean;
  aggregate_score: number;
  category_scores: Record<string, number>;
  regressions: string[];
  reason: string;
  created_at: string;
}

export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
}

export interface Me {
  subject: string;
  kind: "user" | "api_key";
  email: string | null;
  role: Role;
  tenant_id: string;
  tenant_name: string;
  tenants: TenantSummary[];
}

export interface Session {
  token: string;
  tenantId: string;
  email: string;
  role: Role;
  tenantName: string;
  tenants: TenantSummary[];
}

// ---- Ops & analytics (F9) ----

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  target: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface Webhook {
  id: string;
  url: string;
  event_type: string;
  active: boolean;
  last_status: number | null;
}

export interface TrendPoint {
  bucket: string;
  value: number;
  count: number;
}

export interface AnalyticsSummary {
  window_hours: number;
  evaluations: number;
  pass_rate: number;
}

// ---- Pagination (Phase I) ----

export interface PageMeta {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
}

export interface Paged<T> {
  items: T[];
  page: PageMeta;
}
