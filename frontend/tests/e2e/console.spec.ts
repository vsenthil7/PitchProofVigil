import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers";

test.describe("Console", () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page);
  });

  test("clean query passes with category scores", async ({ page }) => {
    await page.getByTestId("ask-input").fill("I want to buy a ticket");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();
    await expect(page.getByTestId("category-scores")).toBeVisible();
    await expect(page.getByTestId("aggregate-verdict")).toContainText("PASS");
    // 15 evaluators run: 11 base (correctness/grounding/safety/quality + LLM judge)
    //   + 4 red-team (prompt-injection, PII, toxicity, off-topic). See backend registry.py.
    await expect(page.getByTestId("eval-row")).toHaveCount(15);
  });

  test("kickoff query returns authoritative time", async ({ page }) => {
    await page.getByTestId("ask-input").fill("When does Spain play Germany?");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("answer-text")).toContainText("20:00");
  });

  test("cost panel renders", async ({ page }) => {
    await page.getByTestId("quick-chip").first().click();
    await expect(page.getByTestId("cost-panel")).toBeVisible();
  });

  test("evaluator findings drill-down expands", async ({ page }) => {
    // A query with no team â†’ groundedness FAIL with a finding to expand.
    await page.getByTestId("ask-input").fill("which gate do I use");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();
    // Click the failing row (groundedness) to reveal findings.
    const failRow = page.getByTestId("eval-row").filter({ hasText: "groundedness" });
    await failRow.click();
    await expect(page.getByTestId("finding").first()).toBeVisible();
  });

  test("run disabled on empty input", async ({ page }) => {
    await expect(page.getByTestId("ask-btn")).toBeDisabled();
    await page.getByTestId("ask-input").fill("hi");
    await expect(page.getByTestId("ask-btn")).toBeEnabled();
  });

  test("language selector works", async ({ page }) => {
    await page.getByTestId("lang-select").selectOption("es");
    await page.getByTestId("ask-input").fill("When does France play England?");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();
  });
});
