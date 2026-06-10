# PitchProof Vigil — Requirements ⇄ Test Traceability Matrix

**Track:** T1 · Arize · AT-Hack0025 (Google Cloud Rapid Agent Hackathon)
**Repo:** https://github.com/vsenthil7/PitchProofVigil
**Purpose:** Every requirement maps to its implementation module(s) and the tests
that prove it, across four coverage fronts: **U**nit/automation, **E**2E
(Playwright), **F**unctional, **N**egative. A requirement is *Done* only when all
applicable fronts are green at 100% coverage.

**Mode:** Mini-sprint. Each sprint is independently submittable — the build is
kept green (push only on pass) so we can submit to the hackathon at any commit.

Legend — Status: ✅ done · 🟡 in progress · 🔴 failing/blocked · ⬜ not started
Coverage fronts: U=unit · E=e2e · F=functional · N=negative · — = N/A

---

## 0. Live baseline (measured, not claimed)

| Front | Tool | Result | Coverage | Notes |
|---|---|---|---|---|
| Unit | pytest | **509 passed / 0 failed** | **100.00%** | `USE_MOCKS=true`; 88s. Real run on Python 3.12.10. |
| E2E | Playwright (chromium) | **30 passed / 5 failed / 1 skipped** | n/a | 5 failures are stale assertions vs. evolved app (see SPRINT log S1). |
| Functional | (folded into unit/api tests) | covered | 100% | API-level behaviour asserted in `tests/test_api*.py`. |
| Negative | (folded into unit tests) | covered | 100% | Error/edge paths asserted across `tests/` (auth, ratelimit, url_safety, redaction…). |

Dependency gaps found by running (now fixed in `requirements.txt`):
`python-multipart` (SSO/SAML form endpoints) and `fakeredis` (rate-limit tests).

---

## 1. Requirements matrix

### R1 — Agent: World Cup fan concierge
| ID | Requirement | Implementation | U | E | F | N | Status |
|---|---|---|---|---|---|---|---|
| R1.1 | Answer kickoff/gate/ticket/travel/translation intents | `app/agent/concierge.py`, `app/orchestration/orchestrator.py` | `test_agent.py`, `test_orchestrator.py` | `console.spec.ts` | ✅ | ✅ | ✅ |
| R1.2 | Real Gemini + deterministic mock behind one facade | `app/agent/concierge.py` | `test_agent.py` | — | ✅ | ✅ | ✅ |
| R1.3 | Tool-using orchestration with retry + circuit breaker | `app/orchestration/{orchestrator,resilience,tools}.py` | `test_orchestrator.py`, `test_resilience_cost.py` | — | ✅ | ✅ | ✅ |
| R1.4 | Token/cost accounting per interaction | `app/orchestration/cost.py` | `test_cost_budget.py` | — | ✅ | ✅ | ✅ |

### R2 — Eval science
| ID | Requirement | Implementation | U | E | F | N | Status |
|---|---|---|---|---|---|---|---|
| R2.1 | Evaluator contract: verdict+score+confidence+findings, error isolation | `app/evaluators/base.py` | `test_evaluators_base.py` | — | ✅ | ✅ | ✅ |
| R2.2 | 15-evaluator suite across 6 categories + red-team pack | `app/evaluators/**` | `test_evaluators_concrete.py`, `test_redteam_evaluators.py`, `test_safety.py` | `console.spec.ts` | ✅ | ✅ | 🟡 (E stale: expects 11 rows, app renders 15) |
| R2.3 | LLM-as-judge (single + ensemble) | `app/evaluators/{llm_judge,ensemble_judge}.py` | `test_ensemble_judge.py` | — | ✅ | ✅ | ✅ |
| R2.4 | Confidence-weighted scoring + policy resolution | `app/evaluators/scoring.py` | `test_scoring.py` | — | ✅ | ✅ | ✅ |

### R3 — Gate & baseline regression
| ID | Requirement | Implementation | U | E | F | N | Status |
|---|---|---|---|---|---|---|---|
| R3.1 | Weighted aggregate vs threshold + blocking-evaluator veto | `app/evaluators/scoring.py` | `test_scoring.py` | `gate.spec.ts` | ✅ | ✅ | ✅ |
| R3.2 | Baseline per-category regression blocks promotion | `app/evaluators/candidate_gate.py` | `test_scoring.py` (gate), `test_services.py` | `gate.spec.ts` | ✅ | ✅ | ✅ |

### R4 — Tracing & Arize/Phoenix MCP (track signature)
| ID | Requirement | Implementation | U | E | F | N | Status |
|---|---|---|---|---|---|---|---|
| R4.1 | OpenInference span tree per interaction | `app/phoenix/tracer.py` | `test_phoenix.py` | — | ✅ | ✅ | ✅ |
| R4.2 | Phoenix MCP client (mock + real surface parity) | `app/phoenix/mcp_client.py` | `test_phoenix.py` | — | ✅ | ✅ | 🟡 (live SSE transport stubbed; documented) |

### R5 — Enterprise spine
| ID | Requirement | Implementation | U | E | F | N | Status |
|---|---|---|---|---|---|---|---|
| R5.1 | Auth: bcrypt + JWT + API keys, 4-role RBAC | `app/auth/**` | `test_auth_*.py` | `auth.spec.ts` | ✅ | ✅ | ✅ |
| R5.2 | Multi-tenant isolation | `app/tenancy/`, `app/repositories/**` | `test_switch_tenant.py`, `test_repositories.py` | `navigation.spec.ts` | ✅ | ✅ | 🟡 (E: tenant-switcher disabled-state assertion stale) |
| R5.3 | Persistence: 10-table schema + Alembic | `app/db/**`, `migrations/**` | `test_db_engine.py`, `test_models.py` | — | ✅ | ✅ | ✅ |
| R5.4 | Field crypto + redaction | `app/crypto/**` | `test_crypto.py`, `test_redaction.py` | — | ✅ | ✅ | ✅ |
| R5.5 | Idempotency keys | `app/idempotency/` | `test_idempotency.py` | — | ✅ | ✅ | ✅ |
| R5.6 | Rate limiting (in-proc + Redis) | `app/ratelimit/**` | `test_ratelimit.py`, `test_api_ratelimit.py` | — | ✅ | ✅ | ✅ |
| R5.7 | Webhooks + SSRF URL safety + signing | `app/webhooks/**` | `test_webhooks.py`, `test_url_safety.py`, `test_audit_webhooks.py` | `analytics.spec.ts` | ✅ | ✅ | 🟡 (E: webhook-row not appearing post-create) |
| R5.8 | SSO / SAML | `app/auth/sso/**`, `app/api/routers/sso.py` | `test_sso.py` | — | ✅ | ✅ | ✅ |
| R5.9 | GDPR erasure | `app/compliance/**` | `test_gdpr_erasure.py`, `test_compliance.py` | — | ✅ | ✅ | ✅ |
| R5.10 | Events bus + alerting (PagerDuty/Slack) | `app/events/**`, `app/alerting/**` | `test_events.py`, `test_alerting.py` | — | ✅ | ✅ | ✅ |

### R6 — Observability
| ID | Requirement | Implementation | U | E | F | N | Status |
|---|---|---|---|---|---|---|---|
| R6.1 | Liveness/readiness probes (db, encryption, migrations, phoenix) | `app/observability/health.py` | `test_observability.py` | `navigation.spec.ts` | ✅ | ✅ | 🟡 (E: health-fail count assertion stale vs warn states) |
| R6.2 | structlog JSON logs + request context | `app/observability/logging.py` | `test_observability.py` | — | ✅ | ✅ | ✅ |
| R6.3 | Prometheus metrics | `app/observability/metrics.py` | `test_observability.py` | — | ✅ | ✅ | ✅ |
| R6.4 | Analytics / trends | `app/analytics/trends.py` | `test_analytics.py` | `analytics.spec.ts` | ✅ | ✅ | 🟡 (E: trend-empty strict-mode dup) |

### R7 — SDK & CI
| ID | Requirement | Implementation | U | E | F | N | Status |
|---|---|---|---|---|---|---|---|
| R7.1 | Python client + CLI for the gate | `sdk/pitchproof_vigil/**` | `sdk/tests/test_*.py` | — | ✅ | ✅ | ✅ |
| R7.2 | GitHub Action wrapper | `sdk/github-action/action.yml` | (structural) | — | ✅ | — | ✅ |

---

## 2. Open items (drive the sprint backlog)

| # | Item | Front | Owner sprint |
|---|---|---|---|
| O1 | `console.spec.ts`: eval-row count 11→15 (app grew red-team pack) | E2E | S1 |
| O2 | `navigation.spec.ts`: tenant-switcher disabled-state assertion vs current single-tenant behaviour | E2E | S1 |
| O3 | `navigation.spec.ts`: health-fail count vs legitimate warn/degraded states in mock mode | E2E | S1 |
| O4 | `analytics.spec.ts`: `trend-empty` strict-mode duplicate locator | E2E | S1 |
| O5 | `analytics.spec.ts`: webhook-row not visible after create (timing or data-testid drift) | E2E | S1 |
| O6 | Wire live Phoenix MCP SSE transport (currently stubbed) | U/Integration | later (needs live Phoenix) |
| O7 | Full Docker stack stand-up on Linux (Vultr) — `arize-phoenix` installs cleanly there | Infra | S-deploy |

---

*Updated each sprint. See `docs/SPRINT_LOG.md` for the running build→test→fix→push journal.*
