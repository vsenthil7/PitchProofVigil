import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers";

test.describe("Analytics, Audit, Webhooks", () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page);
  });

  test("analytics page shows summary and trend charts", async ({ page }) => {
    // Generate data first.
    await page.getByTestId("ask-input").fill("I want to buy a ticket");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();

    await page.getByTestId("tab-analytics").click();
    await expect(page.getByTestId("analytics-page")).toBeVisible();
    await expect(page.getByTestId("analytics-summary")).toBeVisible();
    // Pass-rate trend renders (chart or empty state).
    await expect(page.getByTestId("trend-Pass rate").or(page.getByTestId("trend-empty"))).toBeVisible();
  });

  test("analytics window toggle switches range", async ({ page }) => {
    await page.getByTestId("tab-analytics").click();
    await page.getByTestId("window-1h").click();
    await expect(page.getByTestId("window-1h")).toHaveClass(/chip-active/);
    await page.getByTestId("window-7d").click();
    await expect(page.getByTestId("window-7d")).toHaveClass(/chip-active/);
  });

  test("audit log records a blocking failure", async ({ page }) => {
    // Trigger a blocking failure (fact query with no team).
    await page.getByTestId("ask-input").fill("which gate do I use");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();

    await page.getByTestId("tab-audit").click();
    await expect(page.getByTestId("audit-view")).toBeVisible();
    await expect(page.getByTestId("audit-row").first()).toBeVisible();
  });

  test("audit filter applies", async ({ page }) => {
    await page.getByTestId("ask-input").fill("which gate do I use");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();

    await page.getByTestId("tab-audit").click();
    await page.getByTestId("audit-filter").fill("eval.blocking_failure");
    await page.getByTestId("audit-apply").click();
    await expect(page.getByTestId("audit-row").first()).toBeVisible();
  });

  test("webhooks manager creates and removes a subscription", async ({ page }) => {
    await page.getByTestId("tab-webhooks").click();
    await expect(page.getByTestId("webhooks-manager")).toBeVisible();
    await expect(page.getByTestId("webhook-hint")).toBeVisible();
    // Encryption-status banner is shown.
    await expect(page.getByTestId("security-banner")).toBeVisible();
    await page.getByTestId("webhook-url").fill("https://hook.example/ppv");
    await page.getByTestId("webhook-event").selectOption("gate_decided");
    await page.getByTestId("webhook-secret").fill("my-signing-secret");
    await page.getByTestId("webhook-create").click();
    await expect(page.getByTestId("webhook-row").first()).toBeVisible();
    // Secret field is write-only: it clears after submit and is never echoed back.
    await expect(page.getByTestId("webhook-secret")).toHaveValue("");
    // Delivery badge shows "no delivery" until an event fires.
    await expect(page.locator('[data-testid^="delivery-"]').first()).toContainText("no delivery");
    // Remove it.
    const removeBtn = page.locator('[data-testid^="webhook-delete-"]').first();
    await removeBtn.click();
    await expect(page.getByTestId("webhooks-empty")).toBeVisible();
  });

  test("create button disabled without url", async ({ page }) => {
    await page.getByTestId("tab-webhooks").click();
    await expect(page.getByTestId("webhook-create")).toBeDisabled();
  });
});
