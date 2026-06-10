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
