# Screenshots

The Playwright suite (`frontend/tests/e2e/screenshots.spec.ts`) captures the
live authenticated UI into this folder when run with a browser:

```
cd frontend && npx playwright install chromium && npx playwright test screenshots
```

Captures: `01-login.png`, `02-evaluation-report.png`,
`03-promotion-gate.png`, `04-policy-editor.png`.

(The build sandbox cannot download a browser — the Chromium CDN is outside its
network allowlist — so these are generated in Claude Desktop or CI.)
