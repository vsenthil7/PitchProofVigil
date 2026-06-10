import { defineConfig, devices } from "@playwright/test";

// E2E runs the real backend (uvicorn) and the built frontend (vite preview)
// together, then drives the dashboard in a real browser. The webServer block
// boots both; Playwright waits for the frontend port before starting tests.
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:4173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command:
        "cd ../backend && USE_MOCKS=true DATABASE_DSN='sqlite+aiosqlite:///./e2e_test.db' JWT_SECRET=e2e-secret python3 -m uvicorn app.api.app:app --port 8000",
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: "npm run build && npm run preview",
      port: 4173,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
