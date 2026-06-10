# PitchProof Vigil — User Guide

**Version 1.0** · Google Cloud Rapid Agent Hackathon (AT-Hack0025) · Track T1 — Arize

PitchProof Vigil is an agent-reliability control room for the 2026 World Cup fan
concierge. It traces every agent interaction, runs LLM-as-judge evaluations on
live spans, detects multilingual drift, and **blocks the promotion of any build
that regresses** — so silent failures are caught in minutes, not via social-media
complaints hours later.

This guide walks through installation, configuration, and day-to-day use.

---

## Contents

1. [What the product does](#1-what-the-product-does)
2. [System requirements](#2-system-requirements)
3. [Installation](#3-installation)
4. [Configuration — mock vs real](#4-configuration--mock-vs-real)
5. [Running the application](#5-running-the-application)
6. [The control room, screen by screen](#6-the-control-room-screen-by-screen)
7. [Walkthrough: catching a regression](#7-walkthrough-catching-a-regression)
8. [The promotion gate](#8-the-promotion-gate)
9. [Connecting real services](#9-connecting-real-services)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. What the product does

A World Cup fan asks the concierge agent a question — "When does Spain play
Germany?" The agent answers. Behind that single exchange, PitchProof Vigil:

1. **Traces** the interaction as OpenInference spans (agent → grounding → LLM).
2. **Evaluates** the answer with three judges: factual accuracy (against
   authoritative fixture data), groundedness (did it cite anything?), and
   translation quality (for non-English answers).
3. **Streams** the verdict to the control room in real time.
4. **Gates** any candidate prompt/build: if the golden-set evaluation contains a
   hard failure, promotion is blocked.

The distinctive piece: the agent observes *itself* through the Arize Phoenix MCP
server — it can query its own traces and run evaluations on them.

---

## 2. System requirements

| Component | Requirement |
|---|---|
| Python | 3.11+ (3.12 recommended) |
| Node.js | 20+ (22 recommended) |
| OS | macOS, Linux, or WSL2 |
| Browser (for E2E) | Chromium via `npx playwright install` |
| Optional | Docker (for self-hosted Phoenix) |

---

## 3. Installation

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

---

## 4. Configuration — mock vs real

PitchProof Vigil runs **fully on mocks out of the box** — no credentials needed.
A single switch controls everything.

```bash
cd backend
cp .env.example .env
```

The key line:

```
USE_MOCKS=true     # everything runs on deterministic mocks
USE_MOCKS=false    # use real services where credentials are present
```

When `USE_MOCKS=false`, each integration independently uses its real backend if
its credentials exist, or falls back to a mock if they don't. The control room's
top-right pills show the live mode of each integration (Gemini, Phoenix, Arize
AX) at all times.

See [section 9](#9-connecting-real-services) for wiring real services.

---

## 5. Running the application

Open two terminals.

**Terminal 1 — backend:**

```bash
cd backend
source .venv/bin/activate
uvicorn app.api.main:app --port 8000 --reload
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. The dashboard proxies all `/api` calls
(including the WebSocket) to the backend on port 8000.

---

## 6. The control room, screen by screen

When the dashboard loads, you see the control room: operator actions on the
left, situational awareness on the right.

![Control room overview](screenshots/01-control-room.png)
*Figure 1 — The control room on first load. Top-right pills show each
integration's mode (here all three are running on mocks). The left column holds
the Live Console and Promotion Gate; the right column holds metric tiles and the
Live Evaluation Feed.*

The three metric tiles report:

- **Traces Observed** — total interactions traced this session.
- **Drift Distance** — current embedding-drift measure; turns red past the alert
  threshold (0.35).
- **Live Integrations** — how many of the three integrations are on real
  backends (e.g. `0/3` on mocks, `2/3` with Gemini + Phoenix connected).

---

## 7. Walkthrough: catching a regression

This is the core demo loop.

**Step 1 — Ask a clean question.** Type *"I want to buy a ticket"* and press
**Run** (or hit Enter). The agent answers and all three evaluators pass.

![Passing evaluation](screenshots/02-passing-eval.png)
*Figure 2 — A healthy interaction. The answer appears with its intent, model,
latency and aggregate score, and every evaluator returns PASS (green). A trace
event streams into the Live Evaluation Feed on the right.*

**Step 2 — Ask the poisoned question.** Type *"When does Spain play Germany?"*
and press **Run**. The agent confidently answers **18:00** — but the
authoritative kickoff is **20:00**. The factual-accuracy judge catches it.

![Caught regression](screenshots/03-caught-regression.png)
*Figure 3 — A silent regression caught in real time. The answer looks
plausible, but `factual_accuracy` returns a hard **FAIL** with the exact
mismatch (stated 18:00 vs authoritative 20:00). The feed entry is flagged red at
67%.*

This is exactly the kind of failure that, in production, would otherwise surface
only through angry fans at the wrong stadium gate.

---

## 8. The promotion gate

The gate decides whether a candidate build or prompt may ship. It runs the full
evaluator suite across a golden query set and blocks on any hard failure.

**Step 1 —** Enter a candidate id (e.g. `prompt-v2`) and press **Run Gate**.

![Promotion blocked](screenshots/04-promotion-blocked.png)
*Figure 4 — Promotion blocked. The default golden set includes the poisoned
Spain–Germany query, so the gate returns **PROMOTION BLOCKED** with the reason
and the failing evaluator listed beneath. The aggregate (89%) clears the 85%
threshold, but a single hard failure is enough to block — quality gates fail
closed.*

A clean candidate (golden set with no regressions) returns **PROMOTION ALLOWED**
in green.

The Live Evaluation Feed records every gate run alongside ask events, giving a
single chronological stream of everything happening to the agent:

![Live feed populated](screenshots/05-live-feed.png)
*Figure 5 — The Live Evaluation Feed after several actions. Trace and gate
events are colour-coded by severity (green pass, amber warn, red fail), newest
first, so an operator sees regressions the instant they occur.*

---

## 9. Connecting real services

Set `USE_MOCKS=false` in `backend/.env`, then provide credentials for whichever
services you want live. Each is independent.

### Google Gemini (the agent + LLM judge)

```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GEMINI_MODEL=gemini-2.0-flash
```

### Arize Phoenix (tracing + MCP self-observability)

Phoenix is free and open-source. Run it locally with Docker:

```bash
docker run -p 6006:6006 arizephoenix/phoenix:latest
```

Then point the app at it and launch the MCP server:

```
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
```

```bash
npx -y @arizeai/phoenix-mcp --endpoint http://localhost:6006
```

### Arize AX (optional — production online evals)

```
ARIZE_API_KEY=your-key
ARIZE_SPACE_ID=your-space
```

As each service connects, its top-bar pill flips from amber **mock** to green
**real**, and the Live Integrations tile increments.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Feed shows "offline" | Backend not running | Start uvicorn on port 8000 |
| All pills stuck on "mock" | `USE_MOCKS=true` | Set `USE_MOCKS=false` and provide credentials |
| Gemini pill stays "mock" | No `GOOGLE_CLOUD_PROJECT` | Set the project + credentials, restart backend |
| 404 on `/api/*` | Proxy/target mismatch | Confirm backend is on :8000; check `vite.config.ts` proxy |
| Gate always blocks | Golden set has the poisoned query | Expected — demonstrates the safety net; edit the golden set in `GatePanel.tsx` to use clean queries |

---

*For architecture and developer details, see `ARCHITECTURE.md`. For sprint
history and test coverage, see `SPRINT_TRACKER.md`.*
