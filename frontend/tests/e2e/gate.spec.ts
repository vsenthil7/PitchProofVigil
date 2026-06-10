import { test, expect } from "@playwright/test";

// Promotion gate: running the golden set blocks on the poisoned regression,
// and a clean candidate name still blocks because the default golden set
// contains the poisoned query (the safety net demonstration).

test.describe("Promotion Gate", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("gate-panel")).toBeVisible();
  });

  test("default golden set blocks promotion", async ({ page }) => {
    await page.getByTestId("gate-btn").click();
    await expect(page.getByTestId("gate-result")).toBeVisible();
    await expect(page.getByTestId("gate-banner")).toHaveClass(/blocked/);
    await expect(page.getByTestId("gate-verdict-label")).toContainText(
      "PROMOTION BLOCKED",
    );
  });

  test("blocked gate lists the failing evaluator", async ({ page }) => {
    await page.getByTestId("gate-btn").click();
    await expect(page.getByTestId("gate-failing")).toBeVisible();
    await expect(page.getByTestId("gate-failing")).toContainText(
      "factual_accuracy",
    );
  });

  test("gate button disabled without a candidate id", async ({ page }) => {
    await page.getByTestId("candidate-input").fill("");
    await expect(page.getByTestId("gate-btn")).toBeDisabled();
  });

  test("custom candidate id is echoed in the result", async ({ page }) => {
    await page.getByTestId("candidate-input").fill("");
    await page.getByTestId("candidate-input").fill("release-42");
    await page.getByTestId("gate-btn").click();
    await expect(page.getByTestId("gate-result")).toContainText("release-42");
  });
});
