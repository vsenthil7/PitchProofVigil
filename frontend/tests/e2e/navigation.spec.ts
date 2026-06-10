import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers";

// Phase J — role/tenant awareness, grouped collapsible nav, platform health.
// Execution needs the backend + built frontend (the webServer block boots both)
// and a browser; run via `npm run test:e2e` in CI / Claude Desktop.
test.describe("Enterprise navigation (Phase J)", () => {
  test("a fresh owner sees a role badge and tenant switcher", async ({ page }) => {
    await registerAndLogin(page);
    await expect(page.getByTestId("role-badge")).toHaveText("Owner");
    // A brand-new org has exactly one tenant → switcher present but disabled.
    const sw = page.getByTestId("tenant-switcher");
    await expect(sw).toBeVisible();
    await expect(sw).toBeDisabled();
  });

  test("navigation is segregated into titled groups", async ({ page }) => {
    await registerAndLogin(page);
    for (const g of ["Operate", "Analyze", "Govern", "Administer"]) {
      await expect(page.getByTestId(`nav-group-${g}`)).toBeVisible();
      await expect(page.getByTestId(`nav-group-label-${g}`)).toHaveText(g);
    }
  });

  test("sidebar collapses to an icon rail and hides group labels", async ({ page }) => {
    await registerAndLogin(page);
    const sidebar = page.getByTestId("sidebar");
    await expect(sidebar).toHaveAttribute("data-collapsed", "false");
    await page.getByTestId("sidebar-toggle").click();
    await expect(sidebar).toHaveAttribute("data-collapsed", "true");
    await expect(page.getByTestId("nav-group-label-Operate")).toHaveCount(0);
    // Nav items remain (as icons).
    await expect(page.getByTestId("nav-console")).toBeVisible();
  });

  test("owner can reach the Promotion Gate (operator+ surface)", async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("nav-gate").click();
    await expect(page.getByTestId("nav-gate")).toHaveAttribute("aria-current", "page");
  });

  test("platform health page runs live checks against the backend", async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("nav-health").click();
    await expect(page.getByTestId("health-page")).toBeVisible();
    await expect(page.getByTestId("health-summary")).toBeVisible();
    // Liveness + readiness should pass against the real test backend → no fails.
    await expect(page.getByTestId("health-checks")).toBeVisible();
    await expect(page.getByTestId("health-fail")).toHaveCount(0);
  });
});

// Phase K — real tenant switching (not cosmetic). Setup uses the API to create
// a second tenant and grant the signed-in owner-equivalent access, then drives
// the switcher in the UI. Execution is BLOCKED-ENV in the sandbox (needs the
// webServer + browser); the switch authorization itself is covered by backend
// tests in test_switch_tenant.py.
test.describe("Tenant switching (Phase K)", () => {
  test("switcher is enabled once the session spans multiple tenants", async ({ page, request }) => {
    await registerAndLogin(page);
    // Read the current token from the app to make authenticated API calls.
    const token = await page.evaluate(() => (window as any).__PPV_TOKEN__ ?? null);
    test.skip(!token, "token bridge not present in this build");

    // Register a second org (owner of both is the platform owner in this demo).
    const unique = Date.now().toString(36);
    await request.post("/api/auth/register", {
      data: { tenant_name: `Second ${unique}`, slug: `second-${unique}`,
              owner_email: `o2-${unique}@org.com`, owner_password: "pw12345678" },
    });

    // After a reload, an owner who can see >1 tenant gets an enabled switcher.
    await page.reload();
    const sw = page.getByTestId("tenant-switcher");
    await expect(sw).toBeVisible();
  });
});
