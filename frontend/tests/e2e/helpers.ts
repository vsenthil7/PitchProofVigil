import { Page, expect } from "@playwright/test";

// Register a fresh tenant (unique slug) and land on the authenticated
// dashboard. Returns nothing; the page is left signed in.
export async function registerAndLogin(page: Page): Promise<void> {
  const unique = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  await page.goto("/");
  await expect(page.getByTestId("auth-card")).toBeVisible();
  await page.getByTestId("tenant-name").fill(`Org ${unique}`);
  await page.getByTestId("slug").fill(`org-${unique}`);
  await page.getByTestId("email").fill(`owner-${unique}@org.com`);
  await page.getByTestId("password").fill("pw12345678");
  await page.getByTestId("auth-submit").click();
  await expect(page.getByTestId("sidebar")).toBeVisible({ timeout: 15_000 });
}
