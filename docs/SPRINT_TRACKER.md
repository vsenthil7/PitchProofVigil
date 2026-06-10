# PitchProof Vigil — Sprint & Progress Tracker

**Project:** 003-01-01-Build-Arize-PitchProofVigil
**Source assessment:** AT-Hack0025-Assess-Claude-T1-Arize-P1-PitchProofVigil-20260601_Time1114
**Hackathon:** Google Cloud Rapid Agent Hackathon (AT-Hack0025) — Track T1 (Arize), 2026 World Cup theme
**Owner:** Engineering
**Last updated:** 2026-06-01

---

## Legend

| Status | Meaning |
|---|---|
| ✅ Done | Complete, tested, documented |
| 🟡 In progress | Actively being worked |
| ⬜ Not started | Queued |
| 🔵 Blocked | Waiting on access/dependency |

---

## Phase / Sprint Overview

| Sprint | Module | Status | Coverage | Notes |
|---|---|---|---|---|
| S0 | Repo scaffold, tracker, CI, config | ✅ Done | 100% | Mock/real switch, env schema |
| S1 | Concierge agent (Gemini + OpenInference) | ✅ Done | 100% | Poison trigger for demo |
| S2 | Phoenix integration + MCP server | ✅ Done | 100% | Tracing, datasets, self-observe |
| S3 | Eval engine (LLM-as-judge, drift, gate) | ✅ Done | 100% | 3 evaluators + gate + drift |
| S4 | Backend API (FastAPI, WebSocket, alerts) | ✅ Done | 100% | 7 routes + live feed |
| S5 | Front end (React ops dashboard) | ✅ Done | typecheck + build clean | Trace→verdict→block, live feed |
| S6 | Test suite (unit + Playwright E2E) | ✅ Done | 100% unit · 21 E2E | E2E runs in browser env (see note) |
| S7 | Docs, user guide, deploy | ✅ Done | — | Guide+screens, Compose, Dockerfiles, CI |

---

## Access / Credentials Register

| # | Access | Required? | Provisioned? | Fallback |
|---|---|---|---|---|
| 1 | Arize Phoenix (Docker/OSS) | Hard | ⬜ | Local Docker — fully real |
| 2 | Arize AX (cloud) | Optional | ⬜ | Mock online-eval |
| 3 | Google Cloud + Gemini 3 | Hard | ⬜ | Mock Gemini fixtures |
| 4 | Vertex AI Agent Builder | Optional | ⬜ | Direct Gemini SDK |
| 5 | Cloud Run deploy | Optional | ⬜ | Docker Compose local |
| 6 | Playwright Chromium download | For E2E run | ⬜ (blocked in build sandbox) | Specs written + validated; run in Claude Desktop / CI |

> **Note on E2E execution.** The 21 Playwright specs are complete and validated
> (`npx playwright test --list` enumerates all of them). They were not executed
> in the build sandbox because the Chromium download CDN is outside the network
> allowlist. Run them with `scripts/run_e2e.sh` (or `npm run test:e2e` after
> `npx playwright install chromium`) in Claude Desktop or CI, where the browser
> installs normally. The CI workflow does exactly this.

---

## Build summary (final)

- **Backend:** 17 source modules, 82 tests, **100% line coverage** (enforced).
- **Frontend:** React + TS, 6 components + 2 hooks + API client; typecheck and
  production build pass clean.
- **E2E:** 21 Playwright tests across 4 specs; doubles as screenshot generator.
- **Bugs caught & fixed during build:** (1) falsy-empty-`TraceStore` discarded a
  passed-in store via `x or Y`; (2) dead OTLP export hook wired to the wrong
  attribute; (3) ESM `__dirname` in the screenshot spec.
- **Deploy:** Dockerfiles (backend + frontend/nginx), `docker-compose.yml`,
  GitHub Actions CI (backend coverage gate, frontend build, E2E).

---

## Detailed Sprint Log

### S0 — Repo scaffold
- [x] Working directory + monorepo layout
- [x] Sprint tracker (this document)
- [x] Config module with USE_MOCKS switch
- [x] Env schema (.env.example)
- [x] CI workflow (.github/workflows/ci.yml)
- [x] README

### S1–S4 — Backend (complete)
- [x] Concierge agent (Gemini real path + deterministic mock + poison trigger)
- [x] Phoenix tracer (OpenInference spans) + MCP self-observability client
- [x] Eval engine (factual / groundedness / translation) + gate + drift
- [x] FastAPI: health, ask, traces, gate, drift + WebSocket live feed
- [x] 82 tests, 100% coverage

### S5 — Frontend (complete)
- [x] Vite + React + TS scaffold, control-room design system
- [x] TopBar, Console, GatePanel, Metrics, LiveFeed components
- [x] useHealth + useLiveFeed hooks; typed API client
- [x] Typecheck + production build pass; full-stack proxy verified

### S6 — Tests (complete)
- [x] 100% backend unit coverage
- [x] 21 Playwright E2E specs (console, gate, feed, screenshots)

### S7 — Docs & deploy (complete)
- [x] USER_GUIDE.md with 5 numbered screenshots
- [x] ARCHITECTURE.md, README.md
- [x] Dockerfiles, nginx config, docker-compose.yml
- [x] GitHub Actions CI

---

## Phase E — Enterprise Expansion (in progress)

Scope: full enterprise build, no scope reduction. Postgres + SQLModel + Alembic
persistence, multi-tenancy + auth, platform observability, agent orchestration,
plus a deepened eval science layer. Frontend extended in lockstep.

| Sprint | Module | Status | Coverage | Notes |
|---|---|---|---|---|
| E1 | Eval science (evaluator framework) | Done | 100% on app/evaluators | 11 evaluators, 6 categories |
| E2 | Persistence (Postgres/SQLModel/Alembic) | In progress | - | Async repositories + migrations |
| E3 | Auth + multi-tenancy (API keys, RBAC) | Not started | - | Tenant isolation |
| E4 | Platform observability | Not started | - | structlog, Prometheus, probes |
| E5 | Agent orchestration | Not started | - | Tools, retry, cost accounting |
| E6 | API + frontend expansion | Not started | - | Wire new capabilities through |

### E1 — Eval science (complete)
- [x] evaluators/base.py — Evaluator/Spec/Registry, EvaluationOutcome with
      findings (code/severity/evidence), confidence-weighted scoring, error
      isolation (evaluator bugs -> ERROR verdict, never crash)
- [x] 11 evaluators: factual_accuracy (time-tolerance + delta evidence),
      groundedness, hallucination_check, translation_quality,
      response_completeness, latency_slo, intent_resolution, pii_leakage,
      unsafe_content, prompt_injection_echo, llm_judge (real Gemini + mock rubric)
- [x] scoring.py — GatePolicy + per-evaluator EvaluatorPolicy, ScoringEngine
      with weighted multi-category aggregation, EvaluationReport
- [x] candidate_gate.py — golden-set evaluation + baseline regression detection
- [x] 73 tests, 100% coverage on the evaluators package

Note: the new evaluator framework supersedes the original 3-evaluator
app/evals/ package. app/evals/ is retained until E6 rewires the API onto the
new ScoringEngine, after which it will be removed.

### E2 — Persistence (complete)
- [x] db/engine.py — async engine + sessionmaker, Postgres(asyncpg)/SQLite
      (aiosqlite), transactional session scope, DSN normalization
- [x] db/models.py — 10-table multi-tenant schema: tenants, users, api_keys,
      traces, spans, evaluations, gate_policies, gate_decisions,
      golden_datasets, alerts (JSON columns portable across PG/SQLite)
- [x] repositories/ — tenant-scoped async repos with verified cross-tenant
      isolation; aggregations (verdict breakdown, per-evaluator failure rate,
      intent counts), gate-policy versioning, golden-dataset example append
- [x] Alembic async env + autogenerated initial migration (applies clean)
- [x] 40 tests, 100% coverage on app/db + app/repositories
- [x] Full suite: 175 passing

Config additions: DATABASE_DSN, DB_ECHO, JWT_SECRET, JWT_ALGORITHM,
ACCESS_TOKEN_TTL_MINUTES, API_KEY_PREFIX (defaults keep local dev zero-config
on SQLite).

### E3 — Auth + multi-tenancy (complete)
- [x] auth/security.py — bcrypt password hashing, API-key minting
      (prefix.secret, store hash only), JWT create/decode
- [x] auth/service.py — Principal + RBAC (4 roles -> permission sets),
      AuthService: register_tenant, create_user, login, create_api_key,
      principal_from_api_key/token; AuthError with HTTP status codes
- [x] Tenant isolation enforced at the repository layer (verified by test)
- [x] 21 tests, 100% coverage on app/auth
- [x] bcrypt pinned to 4.0.1 (passlib compat fix)

### E4 — Platform observability (complete)
- [x] observability/logging.py — structlog JSON logs + request-context binding
- [x] observability/metrics.py — Prometheus registry (HTTP, agent, eval, gate
      counters + latency histograms), /metrics render helper
- [x] observability/health.py — liveness + DB-backed readiness probes
- [x] 10 tests, 100% coverage on app/observability

Status after this session: 28 source modules, 3,782 LOC, 206 tests passing.
Remaining: E5 (agent orchestration: tools/retry/cost) and E6 (wire auth +
persistence + new ScoringEngine through the API, retire app/evals, extend the
React dashboard with policy editor, category charts, baseline view, drill-downs).

### E5 — Agent orchestration (complete)
- [x] orchestration/tools.py — Tool/ToolParam/ToolResult/ToolRegistry with
      param validation, error isolation, function-calling schemas
- [x] orchestration/concierge_tools.py — 5 tools: fixture_lookup, kickoff_time,
      gate_lookup, translate_phrase, ticketing_info
- [x] orchestration/resilience.py — RetryPolicy (bounded exponential backoff,
      retryable-exception filter) + CircuitBreaker (closed/open/half-open with
      cooldown); injectable clock/sleep for deterministic tests
- [x] orchestration/cost.py — per-model price book + CostLedger (token + USD)
- [x] orchestration/orchestrator.py — intent routing -> tool plan -> resilient
      invocation -> grounded answer composition -> cost summary; degrades
      gracefully when tools fail
- [x] 39 tests, 100% coverage on app/orchestration

Status after this session: 33 source modules, 4,326 LOC, 245 tests passing.
Note: the orchestrator reads authoritative fixtures (correct production path);
the poisoned mock concierge is retained for regression-detection demos.
Remaining: E6 — wire auth + persistence + ScoringEngine + orchestrator through
the FastAPI layer (auth deps, tenant-scoped routes, /metrics /health /ready),
retire app/evals, extend the React dashboard (login/tenant, policy editor,
category charts, baseline view, evaluator drill-downs, cost panel).

### E6 — Integration (complete)
Backend:
- [x] alerting/service.py — LogChannel + WebhookChannel, persisted alerts
- [x] datasets/eval_service.py — ask→persist(trace+spans)→score→persist(evals)
      →alert→metrics, tenant-scoped unit of work
- [x] datasets/gate_service.py — candidate over golden dataset / inline queries,
      auto baseline from last passing decision, persists GateDecisionRow
- [x] api/deps.py — Bearer JWT + X-API-Key auth, tenant-scoped principal,
      permission-gated dependencies, active-policy loader
- [x] api/routers_{auth,eval,gate}.py — register/login/users/api-keys, ask,
      traces, stats, gate, gate/dataset, decisions, policies, evaluators,
      datasets, /health /ready /metrics
- [x] api/app.py — factory with lifespan (schema/dispose), request
      timing+logging middleware, singletons on app.state
- [x] Retired legacy app/evals, app/core/context, old api/main+schemas
- [x] StaticPool for in-memory SQLite; .coveragerc with thread,greenlet
      concurrency so async routes are credited
- [x] 255 tests, 100% coverage across entire backend

Frontend (in lockstep):
- [x] Enterprise API client + types (auth token, ask, gate, policies, stats)
- [x] AuthProvider/useAuth (in-memory session), LoginPage (register+login)
- [x] Console: category-score bars, expandable evaluator findings, cost panel
- [x] GatePanel: baseline deltas + regression display
- [x] PolicyEditor: per-evaluator enable/blocking/weight, threshold, save
- [x] StatsPanel: tiles, per-evaluator failure rates, traffic by intent
- [x] Tabbed dashboard, session bar + logout; typecheck + build clean
- [x] 20 Playwright E2E specs rewritten for the authenticated flow
- [x] Deployment: Postgres compose, migration entrypoint, CI updated

FINAL STATE — enterprise build complete.
Backend: 5,100 LOC, 255 tests, 100% coverage.
Frontend: 1,278 LOC, builds clean, 20 E2E specs.
All six enterprise sprints (E1–E6) delivered.

---

## Phase F — Modularization & Depth (in progress)

Goal: break kitchen-sink files into proper sub-packages, and add the
enterprise breadth that's genuinely missing. No scope reduction.

| Sprint | Module | Status |
|---|---|---|
| F1 | Split routers_gate -> api/routers/{gate,policies,datasets,admin,ops} package | ✅ Done |
| F2 | Split schemas_v2 -> api/schemas/ package by domain | ✅ Done |
| F3 | Split db/models -> db/models/ package by aggregate (12 tables) | ✅ Done |
| F4 | Domain event bus + handlers (decouple alerting/metrics/audit) | ✅ Done |
| F5 | Audit log (who did what, persisted, queryable, /api/audit) | ✅ Done |
| F6 | Rate limiting (per-tenant token bucket) + pagination util | ✅ Done |
| F7 | Webhook subscriptions (model+repo+CRUD+delivery handler) | Model/repo/CRUD done; live delivery handler pending |
| F8 | Analytics/trends module (time-series eval metrics) | ✅ Done |
| F9 | Frontend: audit view, webhooks manager, analytics charts | ✅ Done |
| F10 | Alembic migration for audit_log + webhook_subscriptions | ✅ Done |

### F9 notes (complete)
- TrendChart: dependency-free SVG line chart (percent + auto-scale modes).
- AnalyticsPage: summary tiles + pass-rate & latency trend charts, 1h/24h/7d
  window toggle, reads /api/analytics.
- AuditView: filterable audit trail from /api/audit.
- WebhooksManager: create/list/remove subscriptions via /api/webhooks.
- App now has 6 tabs (Console, Gate, Policies, Analytics, Audit, Webhooks);
  full-width layout for the analytical/management tabs.
- Frontend typechecks + builds clean. 29 Playwright E2E specs (was 20).

### Phase F — FINAL STATE
Backend: 62 modules, 301 tests, 100% coverage. New packages this phase:
api/routers/, api/schemas/, db/models/, events/, ratelimit/, pagination/,
analytics/ + audit/webhook repos and 2 new tables (migration-backed, 12 total).
Frontend: 6-tab control room, 9 components + 5 pages, 29 E2E specs, clean build.
No kitchen-sink files remain; every former monolith is a cohesive sub-package.
Scope was widened (events, audit, webhooks, rate limiting, pagination,
analytics), never reduced.

### F6, F8, F10 notes (complete)
- ratelimit/ package: TokenBucket + keyed RateLimiter (injectable clock).
  Wired as ASGI middleware → 429 + Retry-After on authenticated /api/ traffic.
  ppv_rate_limited_total metric. Config: RATE_LIMIT_CAPACITY / _REFILL_PER_SECOND.
- pagination/ package: PageParams (clamped) + Page (has_more/next_offset/meta).
- analytics/ package: AnalyticsService — pass_rate / category_score /
  evaluator_failure / latency trends (Python time-bucketing, dialect-agnostic)
  + summary. Exposed at /api/analytics/{summary,pass-rate,category,evaluator,latency}.
- Alembic: second revision (5f047ee6e1f2) adds audit_log + webhook_subscriptions;
  full chain upgrades to 12 tables and downgrades cleanly.
- Backend now 301 tests, 100% coverage, 40+ modules.

### F1–F5 notes (complete)
- 278 tests, 100% coverage maintained throughout the refactor.
- routers/ package: _helpers, gate, policies, datasets, admin, auth, evaluation,
  ops (+ __init__ exporting all_routers).
- schemas/ package: auth, evaluation, gate, policy, dataset, ops (+ re-export __init__).
- db/models/ package: _base, identity, tracing, evaluation, governance, ops,
  audit, webhooks (+ re-export __init__).
- events/ package: types (DomainEvent + factories), bus (async, error-isolating),
  handlers (Metrics, Audit). Bus wired into the live /api/ask flow.
- Audit log + webhook subscription tables, repositories, and /api/audit +
  /api/webhooks endpoints (RBAC-gated).

---

## Phase G — Delivery, Reliability & Depth (in progress)

Closing the F7 gap and adding the next tier. No scope reduction.

| Sprint | Module | Status |
|---|---|---|
| G1 | Webhook delivery: signed payloads, HMAC, retry, status persist | ✅ Done |
| G2 | WebhookDeliveryHandler subscribed to event bus (live dispatch) | ✅ Done |
| G3 | Split repositories/registry -> repositories/ package by aggregate | ✅ Done |
| G4 | Idempotency keys for mutating endpoints (dedupe replays) | ✅ Done |
| G5 | Notification fan-out: alerts + webhooks via one notifier | ✅ Done |
| G6 | Frontend: webhook delivery status + signing secret reveal | ✅ Done |

### Phase G — FINAL STATE
- webhooks/ package: signing (HMAC-SHA256, t=…,v1=… header, replay-window
  verify), delivery (async retry, 5xx-retries / 4xx-terminal, status persisted).
- events/handlers.py gained WebhookHandler; notifications/ assembles a bus with
  audit + metrics + webhook handlers (build_event_bus), wired into /api/ask.
- repositories/ split into identity, governance, alerts (+ traces, audit);
  registry.py is now a thin compat re-export.
- idempotency/ package + IdempotencyKeyRow; /api/datasets honors an
  Idempotency-Key header (replay returns the original 201, no double-create).
- Alembic: 3rd revision (idempotency_keys); chain upgrades to 13 tables and
  downgrades to base cleanly.
- Frontend: webhooks manager gained a signing-secret field, an HMAC hint, and a
  color-coded delivery-status badge per subscription.

Backend now 70 modules, 317 tests, 100% coverage, 13 tables.
Frontend: 6 tabs, 29 Playwright specs, clean build.
Webhook delivery is now genuinely live end-to-end (the F7 gap is closed).

---

## Phase H — Secrets, Crypto & Final Modularization (in progress)

Addresses the self-flagged plaintext-secret gap and finishes splitting the
last oversized files. No scope reduction.

| Sprint | Module | Status |
|---|---|---|
| H1 | crypto/ package: Fernet envelope encryption + key provider | ✅ Done |
| H2 | Encrypt webhook secrets at rest (transparent encrypt/decrypt) | ✅ Done |
| H3 | Secret redaction in logs + API responses (never echo secrets) | ✅ Done |
| H4 | Split evaluators/correctness into correctness/ sub-package | ✅ Done |
| H5 | Split datasets/eval_service into datasets/ workflow modules | ✅ Done |
| H6 | Frontend: secret-write-only UX + encryption-status surface | ✅ Done |

### Phase H — FINAL STATE
- crypto/ package: KeyProvider (MultiFernet key ring, env ENCRYPTION_KEYS,
  derived dev key) + FieldCipher (versioned enc:v1: prefix, legacy-plaintext
  tolerance, rotate()) + redaction (recursive secret masking). Full rotation
  lifecycle tested: encrypt old -> decrypt on 2-key ring -> re-encrypt ->
  read on new-key-only ring.
- Webhook secrets encrypted at rest: ciphertext in the column (verified by
  raw-column inspection), decrypted transparently on read, plaintext only
  in-memory for signing. SQLAlchemy identity-map overwrite bug fixed via expunge.
- Redaction applied to audit payloads; WebhookOut never returns the secret;
  /api/security/status reports encryption posture (no secrets).
- evaluators/correctness/ sub-package (factual, grounding, hallucination,
  _shared); datasets/mapping.py extracted from eval_service. No kitchen-sink
  files remain.
- Frontend: encryption-status banner (ok/warn for ephemeral dev key) on the
  webhooks tab; secret field is write-only (clears on submit, never echoed).

Backend now 77 modules, 336 tests, 100% coverage, 13 tables.
Frontend: 6 tabs, 29 Playwright specs, clean build.
Self-flagged plaintext-secret gap from Phase G is closed.

---

## Phase I — Review Hardening (in progress)

Self-review (reviewer hat) found real gaps. Fixing them, not adding surface.

| Sprint | Finding → Fix | Status |
|---|---|---|
| I1 | Pagination module was dead code → wire Page/PageParams into all list endpoints | ✅ Done |
| I2 | List endpoints had unbounded limit → clamp + offset + page metadata | ✅ Done |
| I3 | Webhook URL had no SSRF guard → url_safety validator (block internal/metadata) | ✅ Done |
| I4 | No global exception handler → error envelope + request_id, stack traces never leak | ✅ Done |
| I5 | request_id not surfaced → X-Request-ID response header + in error body | ✅ Done |
| I6 | Frontend: paginated lists (load-more) + request-id surfaced on errors | ✅ Done |

### Phase I — FINAL STATE
- webhooks/url_safety.py: SSRF guard. Blocks non-https (configurable),
  loopback/link-local/RFC-1918/reserved/metadata hostnames, literal private
  IPs, and DNS-rebinding (resolves host, re-checks). Wired into webhook create
  (422 on unsafe). Fixed a real bug: UnsafeWebhookURL (a ValueError subclass)
  was being swallowed by the literal-IP except clause.
- pagination now LIVE: /api/traces and /api/audit return {items, page:{total,
  limit, offset, has_more, next_offset}} with clamped limit (<=200) + offset.
  AuditRepository gained offset+count.
- api/errors.py: global handlers for HTTPException / RequestValidationError /
  Exception. Uniform {"error":{code,message,request_id[,details]}} envelope;
  500s are opaque (real error logged server-side, never leaked).
- request_id: generated (or taken from inbound X-Request-ID) per request, bound
  to logs, stored on request.state, echoed in X-Request-ID header on every
  response and in error bodies.
- Frontend: jsonOrThrow parses the error envelope and appends the request id to
  error messages; AuditView paginates with a Load-more button.

Backend now ~82 modules, 362 tests, 100% coverage, 13 tables.
Frontend: 6 tabs, 30 Playwright specs, clean build.
All five reviewer findings closed.
