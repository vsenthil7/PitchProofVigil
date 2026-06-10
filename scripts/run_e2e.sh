#!/usr/bin/env bash
# Run the full Playwright E2E suite (including screenshot capture).
# Requires a Playwright browser: `npx playwright install chromium`.
set -euo pipefail
cd "$(dirname "$0")/frontend"
npx playwright install chromium
npx playwright test
echo "E2E complete. Screenshots written to docs/screenshots/."
