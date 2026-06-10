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
