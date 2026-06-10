import { defineConfig, devices } from "@playwright/test";

// E2E boots the real backend (uvicorn) + built frontend (vite preview),
// then drives the dashboard in a real browser. Cross-platform via cross-env
// and PW_PYTHON (defaults to "python") so it runs on Windows, Linux, macOS.
const PY = process.env.PW_PYTHON || "python";

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
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `cross-env USE_MOCKS=true DATABASE_DSN=sqlite+aiosqlite:///./e2e_test.db JWT_SECRET=e2e-secret ${PY} -m uvicorn app.api.app:app --port 8000`,
      cwd: "../backend",
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run build && npm run preview",
      port: 4173,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
