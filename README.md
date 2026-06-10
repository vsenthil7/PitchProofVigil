# PitchProof Vigil

**Enterprise agent-reliability platform for the 2026 World Cup fan concierge.**
Google Cloud Rapid Agent Hackathon (AT-Hack0025) · Track T1 — Arize.

Fan-facing World Cup concierge agents silently degrade during matchday traffic
spikes — hallucinated kickoff times, wrong gate numbers, broken translations.
PitchProof Vigil traces every interaction, evaluates it with an 11-evaluator
scoring engine across six categories, detects regressions against a baseline,
and **blocks any promotion that would ship a regression** — catching failures
in minutes. The agent observes *itself* via the Arize Phoenix MCP server, on
Google Cloud Gemini.

This is a full enterprise build: multi-tenant, authenticated, persisted,
observable, and resilient.

---

## Capabilities

| Area | What's built |
|---|---|
| **Eval science** | 11 evaluators (correctness, grounding, safety, quality, performance, compliance), structured findings with severity + evidence, confidence-weighted multi-category scoring, LLM-as-judge |
| **Gate** | Per-evaluator policies (enable/weight/blocking/config), weighted aggregate threshold, **baseline regression detection** |
| **Persistence** | Postgres / SQLite via SQLModel, 10-table multi-tenant schema, Alembic migrations |
| **Auth & tenancy** | bcrypt + JWT + API keys, 4-role RBAC, enforced tenant isolation |
| **Observability** | structlog JSON logs, Prometheus metrics, liveness/readiness probes |
| **Orchestration** | tool-using agent, retry + circuit breaker, token/cost accounting |
| **Frontend** | auth, tabbed control room, category charts, evaluator drill-down, policy editor, gate/baseline view, cost panel |

---

## Quick start (runs on mocks + SQLite, zero config)

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.app:app --port 8000 --reload

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**, register an organization, and you're in.

### Production (Postgres) via Docker

```bash
docker compose up --build
```

Brings up Postgres, the backend (runs Alembic migrations on boot), and the
frontend behind nginx on :8080.

---

## Going live (real services)

Set `USE_MOCKS=false` and provide credentials; each integration is independent
and degrades to a mock if absent:

- **Gemini**: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`
- **Arize Phoenix** (free, local): `docker run -p 6006:6006 arizephoenix/phoenix`, set `PHOENIX_COLLECTOR_ENDPOINT`
- **Arize AX** (optional): `ARIZE_API_KEY`, `ARIZE_SPACE_ID`

---

## Testing

```bash
# Backend — 255 tests, 100% coverage enforced
cd backend && pytest

# Frontend E2E — 20 specs (needs a browser)
cd frontend && npx playwright install chromium && npm run test:e2e
```

---

## Architecture

```
React control room (auth · console · gate · policies · stats)
        │  /api  (JWT / X-API-Key)
FastAPI (routers + deps: auth, tenant scoping, permissions)
        │
EvaluationService / GateService  (tenant-scoped units of work)
   ├─ ConciergeOrchestrator  (tools · retry · circuit breaker · cost)
   ├─ ScoringEngine          (11 evaluators · policy · baseline)
   ├─ Repositories           (tenant-scoped async data access)
   ├─ AlertingService        (log / webhook)
   └─ Observability          (structlog · Prometheus · health)
        │
Postgres / SQLite  (SQLModel + Alembic, 10 tables)
        + Arize Phoenix (tracing + MCP)  ·  Google Gemini (agent + judge)
```

See `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`, and `docs/SPRINT_TRACKER.md`.

---

## Layout

```
backend/   app/{core,agent,evaluators,db,repositories,auth,tenancy,
                observability,orchestration,alerting,datasets,api,phoenix}
           tests/  (255 tests, 100% coverage)  ·  migrations/ (Alembic)
frontend/  src/{components,pages,hooks,lib}  ·  tests/e2e/ (Playwright)
docs/      ARCHITECTURE · USER_GUIDE · SPRINT_TRACKER · screenshots
scripts/   run_e2e.sh  ·  render_mockups.py
```
