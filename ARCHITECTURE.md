# PitchProof Vigil — Architecture

## Overview

PitchProof Vigil is a self-observing reliability layer for a World Cup fan
concierge agent. It is built as a Python (FastAPI) backend and a React +
TypeScript control-room frontend, with Arize Phoenix for tracing/evals and
Google Gemini for the agent and LLM-as-judge.

```
┌──────────────────────────────────────────────────────────────┐
│                     Control Room (React)                       │
│   Console · Promotion Gate · Metrics · Live Feed (WebSocket)   │
└───────────────────────────┬────────────────────────────────────┘
                            │  /api (REST + WS)
┌───────────────────────────▼────────────────────────────────────┐
│                       FastAPI backend                          │
│                                                                │
│  ConciergeAgent ──► Tracer ──► TraceStore ◄── PhoenixMCPClient │
│       │                │                          │            │
│   (Gemini/mock)    OpenInference            self-observability │
│                        spans                                   │
│                                                                │
│  EvalEngine (factual · groundedness · translation)            │
│       │                                                        │
│  RegressionGate ──► GateDecision      DriftDetector            │
└────────────────────────────────────────────────────────────────┘
            │                         │                  │
        Google Gemini          Arize Phoenix       Arize AX
        (Vertex AI)         (OTLP + MCP server)   (online evals)
```

## The mock/real switch

Every integration reads `Settings.integration_mode(name)` which returns
`"real"` or `"mock"`. The rule:

- `USE_MOCKS=true` → all mocks (default; zero credentials needed).
- `USE_MOCKS=false` → each integration is real **iff** its credentials exist,
  else it falls back to a mock.

This means the same code path serves local development, CI, and production. The
real implementations are lazily imported, so the mock path never needs the
heavy SDKs installed.

## Modules

| Module | Responsibility |
|---|---|
| `core/config.py` | Settings + the mock/real switch |
| `core/models.py` | Pydantic domain models shared across layers |
| `core/context.py` | Wires one shared `TraceStore` into all services |
| `agent/concierge.py` | The concierge (Gemini real + deterministic mock) |
| `agent/fixtures.py` | Authoritative World Cup ground-truth data |
| `phoenix/tracer.py` | Builds OpenInference span trees; OTLP export |
| `phoenix/mcp_client.py` | Phoenix MCP tool surface (self-observability) |
| `evals/engine.py` | Three evaluators + aggregation |
| `evals/gate.py` | Regression gate + drift detector |
| `api/main.py` | FastAPI routes + WebSocket live feed |

## The self-observability loop

The product's signature capability: the agent queries its own traces through
the Phoenix MCP server. In code, `PhoenixMCPClient` exposes `list_traces`,
`get_trace`, and `add_dataset_example` — the same tools the live Phoenix MCP
server exposes — so the agent (or an operator) can introspect production
behaviour and capture failing traces into a golden dataset for the gate.

## Why a deliberate "poison"

The mock concierge intentionally returns the wrong kickoff time (18:00 vs the
authoritative 20:00) for the Spain–Germany query. This is not a bug — it is a
built-in, controllable regression so the evaluation pipeline and the promotion
gate have a real defect to catch in demos and tests. In production, the same
evaluators run against real Gemini output.

## Data flow for one `/api/ask`

1. `ConciergeRequest` built from the HTTP body.
2. `ConciergeAgent.answer()` produces a `ConciergeResponse` (real Gemini or mock).
3. `Tracer.record()` builds a 3-span tree and stores it; exports to Phoenix in
   real mode.
4. `EvalEngine.evaluate_trace()` runs all evaluators → `EvalResult[]`.
5. Aggregate score computed; a `trace` event is broadcast over the WebSocket.
6. Response returned to the client and rendered with verdicts.

## Testing strategy

- **Backend:** 100% line coverage enforced by `--cov-fail-under=100`. Real
  integration paths are exercised by injecting fake SDK modules via
  `monkeypatch`, so even the `register()`/MCP branches are covered without
  network access.
- **Frontend E2E:** Playwright drives the real backend + built frontend through
  every user flow (ask, gate, feed, metrics) and captures documentation
  screenshots.
