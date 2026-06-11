import { test, expect } from "@playwright/test";

// One-click demo: a judge can land in a populated multi-role org without
// registering. The button bootstraps the demo org server-side and signs in
// as its owner.
test.describe("One-click demo login", () => {
  test("demo button lands in the dashboard as owner", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("auth-card")).toBeVisible();
    await expect(page.getByTestId("demo-login")).toBeVisible();
    await page.getByTestId("demo-login").click();
    await expect(page.getByTestId("sidebar")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("role-badge")).toHaveText("Owner");
  });

  test("demo is repeatable (idempotent) across sessions", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("demo-login").click();
    await expect(page.getByTestId("sidebar")).toBeVisible({ timeout: 15000 });
    // Sign out and demo again -> same org, still works.
    await page.getByTestId("logout-btn").click();
    await expect(page.getByTestId("auth-card")).toBeVisible();
    await page.getByTestId("demo-login").click();
    await expect(page.getByTestId("sidebar")).toBeVisible({ timeout: 15000 });
  });
});
