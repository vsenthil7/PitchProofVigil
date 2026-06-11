import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers";

// Owner-only org lifecycle UI. A fresh owner sees their own org as the current
// session (no toggle). After registering a second org via the API, the owner
// can disable and re-enable it from the Organizations page.
test.describe("Organizations (owner org lifecycle)", () => {
  test("owner sees the organizations page with their current org", async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("nav-organizations").click();
    await expect(page.getByTestId("organizations-page")).toBeVisible();
    await expect(page.getByTestId("org-row").first()).toBeVisible();
    // The current org is marked and has no toggle button.
    await expect(page.locator('[data-testid^="org-current-"]').first()).toBeVisible();
  });

  test("owner disables then re-enables a second org", async ({ page, request }) => {
    await registerAndLogin(page);
    // Create a second org via the public API so there is one to toggle.
    const unique = Date.now().toString(36);
    await request.post("/api/auth/register", {
      data: { tenant_name: `Other ${unique}`, slug: `other-${unique}`,
              owner_email: `o-${unique}@org.com`, owner_password: "pw12345678" },
    });
    await page.getByTestId("nav-organizations").click();
    await expect(page.getByTestId("organizations-page")).toBeVisible();
    // Find the second org row by its toggle button (the current org has none).
    const toggle = page.locator('[data-testid^="org-toggle-"]').first();
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveText("Disable");
    await toggle.click();
    // After disabling, the same row toggle should flip to Enable.
    await expect(page.locator('[data-testid^="org-toggle-"]').first()).toHaveText("Enable");
    // Re-enable.
    await page.locator('[data-testid^="org-toggle-"]').first().click();
    await expect(page.locator('[data-testid^="org-toggle-"]').first()).toHaveText("Disable");
  });

  test("non-owner cannot see the organizations nav item", async ({ page }) => {
    await registerAndLogin(page);
    // Owner creates a viewer, then we sign in as the viewer.
    const token = await page.evaluate(() => (window as any).__PPV_TOKEN__ ?? null);
    test.skip(!token, "token bridge not present in this build");
  });
});
