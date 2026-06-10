# PitchProof Vigil — Sprint Log

Running journal of the mini-sprint loop:
**build → commit → push → test → (fix → commit → push → re-test)* → green → next.**
Every entry records real, observed results. Any commit tagged ✅ green is
submittable to the hackathon as-is.

---

## Sprint 0 — Baseline established (✅ green, submittable)

**Goal:** Stand up a real test environment on this machine and measure the true
starting state before any feature work.

What happened:
- Created repo `vsenthil7/PitchProofVigil` (public), imported all 9 build
  versions V01→V09 as tagged commits.
- Built a clean Python 3.12.10 venv; installed backend deps.
- Found two missing deps by *running* (not reading): `python-multipart`
  (SSO/SAML form endpoints fail import without it) and `fakeredis` (5
  rate-limit tests + last coverage sliver). Added both to `requirements.txt`.
- `arize-phoenix` excluded from the local install: it pulls `sqlean-py`, which
  needs a C++ compiler on Windows. Tests mock Phoenix, so this is inert here;
  on Linux/Vultr it installs cleanly.

**Backend test result (measured):** `509 passed`, **100.00% coverage**, 88s.
**Commit:** `3f734a8` — *fix(deps): python-multipart + fakeredis; harden .gitignore*

---

## Sprint 1 — Playwright E2E baseline + green-up (🟡 in progress)

**Goal:** Make the existing Playwright suite runnable cross-platform and bring
it to all-green, fixing stale assertions where the app legitimately evolved.

Done so far:
- Rewrote `playwright.config.ts` to be cross-platform: `cross-env` for env
  vars, `PW_PYTHON` to select the interpreter, `cwd` for the backend server.
  (Was Unix-only: hardcoded `python3` + inline `VAR=val` syntax.)
- Installed frontend deps + chromium; `npm run build` green (47 modules).

**E2E baseline (measured):** `30 passed / 5 failed / 1 skipped`.
The 5 failures are **stale tests vs. an evolved app**, not app regressions
(diagnosed against current source):

| Spec | Assertion | Reality | Verdict |
|---|---|---|---|
| `console.spec.ts:16` | `eval-row` count = 11 | app renders 15 (red-team pack added in `registry.py`) | test stale |
| `navigation.spec.ts:14` | `tenant-switcher` disabled | enabled for owner | needs decision |
| `navigation.spec.ts:49` | `health-fail` count = 0 | 2 (encryption ephemeral + phoenix mock surface as non-ok) | test stale |
| `analytics.spec.ts:19` | one `trend-empty` | two matched (strict-mode) | locator fix |
| `analytics.spec.ts:82` | `webhook-row` visible post-create | not found | investigate |

Next: work O1–O5 one at a time (fix → re-run that spec → green → next),
then a full E2E pass, then commit/push.

---

*(new sprints appended here)*
