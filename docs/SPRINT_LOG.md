# PitchProof Vigil - Sprint Log

Running journal of the mini-sprint loop:
build -> commit -> push -> test -> (fix -> commit -> push -> re-test)* -> green -> next.
Every entry records real, observed results. Any commit tagged [GREEN] is
submittable to the hackathon as-is.

---

## Sprint 0 - Baseline established  [GREEN, submittable]

Goal: Stand up a real test environment on this machine and measure the true
starting state before any feature work.

What happened:
- Created repo vsenthil7/PitchProofVigil (PUBLIC), imported all 9 build versions
  V01->V09 as tagged commits.
- Built a clean Python 3.12.10 venv; installed backend deps.
- Found two missing deps by RUNNING (not reading): python-multipart (SSO/SAML
  form endpoints fail import without it) and fakeredis (5 rate-limit tests +
  last coverage sliver). Added both to requirements.txt.
- arize-phoenix excluded from the local install: it pulls sqlean-py, which needs
  a C++ compiler on Windows. Tests mock Phoenix, so this is inert here; on
  Linux/Vultr it installs cleanly.

Backend test result (MEASURED): 509 passed, 100.00% coverage, ~88s.
Commit: 3f734a8 - fix(deps): python-multipart + fakeredis; harden .gitignore

---

## Sprint 0.5 - Traceability + repo relocation  [GREEN, submittable]

- Added in-repo traceability: TRACEABILITY.md + docs/SPRINT_LOG.md.
  Commit: 27f10b9
- Relocated repo into a nested PitchProofVigil/ folder so the working dir name
  matches the GitHub repo name. Layout is now:
    T1-Arize-P1-PitchProofVigil/ (container)
      PitchProofVigil/ (the git repo, attached to origin)
  Re-tested after the move: 509 passed, 100% coverage (relocation broke nothing).
  Stopped tracking tsbuildinfo (build artifact); added 7 E2E demo screenshots.
  Commit: 1fac458  <-- LAST GREEN PUSHED COMMIT

---

## Sprint 1 - Playwright E2E to all-green  [IN PROGRESS - fixes on disk, uncommitted]

Goal: Make the Playwright suite runnable cross-platform and bring it to
all-green, fixing stale assertions where the app legitimately evolved.

E2E baseline (MEASURED): 30 passed / 5 failed / 1 skipped.
The 5 failures were diagnosed against current source - they are stale tests vs.
an evolved app, plus harness issues, NOT app regressions.

Fixes made (ON DISK, NOT YET COMMITTED):
- O1  console.spec.ts: eval-row count 11 -> 15 (app grew the 4-evaluator
      red-team pack in registry.py). FIXED.
- O4  TrendChart.tsx: two charts both rendered data-testid="trend-empty",
      causing a strict-mode locator violation. Gave each a unique
      data-testid=`trend-empty-${label}`; updated the spec to target
      trend-empty-Pass rate. FIXED.
- O5  webhook-row not appearing post-create: ROOT CAUSE = the SSRF URL-safety
      guard (webhooks/url_safety.py) rejected the test URL https://hook.example
      because it does not resolve in DNS (resolve=True by default). The guard is
      correct; the test host just does not resolve. Added WEBHOOK_RESOLVE_DNS
      =false to the E2E backend env so structural checks (private-IP blocking)
      still apply but non-resolving example hosts are accepted. FIXED.
- O2  tenant-switcher disabled-state: ROOT CAUSE is NOT a UI bug. TopBar already
      disables the switcher when session.tenants.length <= 1. The /me endpoint
      returns ALL tenants for an owner ("platform owner" - INTENDED, and encoded
      in backend tests test_switch_tenant.py: "owners span all tenants"). In the
      shared E2E DB, tenants accumulate across tests, so a fresh owner sees >1.
      Correct fix = E2E DB isolation (clean DB per run), NOT changing the
      product. APPROACH SET (see harness work below).
- O3  health-fail count = 0 expected, 2 seen: NOT yet diagnosed at the source.
      The 2 fails come from HealthPage client checks; needs a clean run to see
      which two. PENDING.

Cross-platform harness work:
- Rewrote playwright.config.ts: cross-env for env vars, PW_PYTHON to pick the
  interpreter, cwd for the backend server (was Unix-only: python3 + inline
  VAR=val). Added a JSON reporter (pw-results.json) for machine-readable results.
- Added tests/e2e/global-setup.ts (ESM-safe, process.cwd()-relative) to wipe the
  E2E DB before the backend boots.

### Sprint 1 incident log (environment, not code)

- global-setup.ts first used __dirname (undefined in ESM) -> fixed to
  process.cwd().
- Set reuseExistingServer:false + BACKGROUND-launched `npx playwright test`.
  The detached run orphaned node/python webServers (ports 8000/4173). Cleanup
  hung and the MCP shell + filesystem servers disconnected. User restarted MCP
  (no in-app per-server refresh button exists yet - feedback sent).
- After restart: confirmed both MCP servers reconnected cleanly (logs at
  APPDATA/Claude/logs). Backend re-verified 509 GREEN.
- Re-ran E2E with CI=1 by mistake -> forced retries -> run exceeded the 4-min
  tool timeout repeatedly. Recovered cleanly each time with
  `taskkill /PID <runner> /T /F` (kills the Playwright process tree by
  parent/child; never touches the MCP node procs, which are the _npx cache ones).
- Single-spec run surfaced a NEW symptom: all 6 console tests failed with
  "500 ... no such table: tenants" at registration. Proven NOT an app bug:
  a direct `with TestClient(app) as c: register()` returns 201 Created (schema
  IS created by the FastAPI lifespan). The 500 came from a STALE REUSED E2E
  server (reuseExistingServer:!CI) pointing at a DB that global-setup had
  deleted out from under it.

### Lessons / rules for next E2E attempt
1. Never background-launch a long Playwright run in this env; never set
   reuseExistingServer:false with a detached launch (orphans servers).
2. Never set CI=1 locally (forces retries -> 2x runtime -> tool timeout).
3. Run ONE spec at a time (~30-60s, under the 4-min tool window).
4. Fix the DB race deterministically: do NOT wipe a shared DB while a server may
   reuse it. Instead give the backend a UNIQUE DB filename per server boot, OR
   guarantee no pre-running server. Keep reuseExistingServer:!process.env.CI.
5. Recovery if a run wedges: taskkill /PID <playwright-runner-pid> /T /F.

Current state at end of session: backend 509 GREEN; E2E fixes O1/O4/O5 on disk,
O2 approach set, O3 pending; all uncommitted. Ports clean, MCP healthy.

NEXT: implement per-boot unique E2E DB; run the 5 affected specs one at a time;
get green; commit + push Sprint 1.

---

## Planned sprints (backlog)

| Sprint | Goal | Status |
|--------|------|--------|
| S0    | Baseline: env + 509 green + traceability | DONE (1fac458) |
| S1    | Playwright E2E to all-green (O1-O5) | IN PROGRESS |
| S2    | LIVE Google Cloud: GOOGLE_CLOUD_PROJECT=sinuous-country-499022-a5, ADC, USE_MOCKS=false; verify gcloud token; live Gemini smoke | NEXT |
| S3    | LIVE local Phoenix (Docker :6006) + Phoenix MCP server; wire stubbed SSE transport (O6) | TODO |
| S4    | Outbound API audit trail: log every Google/Phoenix/Arize call (service/endpoint/status/latency, NEVER secrets); surface in AuditView | TODO (user asked) |
| S5    | Demo seed script + one-command live-demo mode (real services, seeded fixtures) | TODO (user asked) |
| S6    | Postgres for tests + runtime (not only SQLite); run suite on Postgres; Alembic verified | TODO (user asked; deferred so it does not distract S1) |
| S7    | Full Docker compose stand-up locally (Postgres+backend+frontend+Phoenix) | TODO |
| S8    | Vultr deploy for public demo URL (Linux: arize-phoenix installs cleanly) | TODO |
| S9    | Functional + negative coverage audit to 100% on all four fronts; final submission zip | TODO |

Coverage fronts tracked per requirement: Unit / E2E / Functional / Negative.

---

## External services & EXACT env vars (from backend/app/core/config.py)

| Service | Vars | Required? |
|---------|------|-----------|
| Vertex AI / Gemini | GOOGLE_CLOUD_PROJECT, GOOGLE_APPLICATION_CREDENTIALS, GEMINI_MODEL (default gemini-2.0-flash) | live agent |
| Local Phoenix | PHOENIX_COLLECTOR_ENDPOINT (default http://localhost:6006), PHOENIX_API_KEY | yes (Docker, free) |
| Arize AX cloud | ARIZE_API_KEY, ARIZE_SPACE_ID | OPTIONAL - degrades to mock; NOT required |
| Redis | REDIS_URL | optional (in-proc fallback) |
| Global switch | USE_MOCKS (true=mock, false=real) | - |

Live-access notes:
- GOOGLE_CLOUD_PROJECT=sinuous-country-499022-a5 matches the code's exact var.
- Leave GOOGLE_APPLICATION_CREDENTIALS UNSET to use ADC - correct.
- Arize CLOUD account NOT needed - track uses LOCAL Phoenix.

---

(new sprints appended here)


## Sprint 1 CLOSED + Org-lifecycle feature  [GREEN, submittable]

RESOLVED the E2E saboteur that broke every run this session: globalSetup was
wiping e2e_test.db AFTER the backend webServer created the schema (race), leaving
the running server on an empty DB -> 500 no-such-table. Fix: moved the DB wipe
INTO the backend webServer command (python -c remove && uvicorn), strictly
sequential. Also: backend webServer url:/health readiness (not port), and
reuseExistingServer:false for backend only.

O1-O5 all fixed and GREEN:
- O1 eval-row 15 (red-team pack)
- O2 tenant-switcher test now respects platform-owner-sees-all design (disabled
     iff <=1 option), not a brittle assume-1-tenant.
- O3 health-fail: /health and /ready were not proxied (only /api was). Added
     both to vite proxy (dev + preview).
- O4 trend-empty unique per-label testid.
- O5 webhook delete: list() now returns ACTIVE webhooks only, so deactivate
     (delete) empties the list. Backend delete is soft (deactivate) by design.

NEW FEATURE - Organization lifecycle (owner-only):
- Backend (commit 1a422b9): PATCH /api/auth/tenants/{id}/active; disabled orgs
     block login (403) and tenant-switch; cannot disable own active org (409);
     is_active surfaced in /me and /tenants. 11 tests.
- Frontend (commit aa8606f): OrganizationsPage (Administer nav, owner-only),
     list orgs with active/disabled status + Disable/Enable, current-session
     org guarded. API client setTenantActive. 3 E2E tests (2 run, 1 skip).

VERIFIED GREEN TOGETHER:
- Backend: 520 passed, 100.00% coverage
- E2E: 37 passed, 2 skipped, 0 failed

Commits: 1a422b9 (backend feat), aa8606f (frontend UI + E2E harness fix).

| Sprint | Status |
|--------|--------|
| S0 baseline | DONE (1fac458) |
| S1 E2E all-green | DONE (aa8606f) |
| Org-lifecycle feature | DONE (1a422b9 + aa8606f) |
| S2 live Google Cloud | NEXT |
| S5 demo seed + one-click demo login | planned |
