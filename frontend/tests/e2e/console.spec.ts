import { test, expect } from "@playwright/test";

// Console flow: asking the agent and seeing live eval verdicts, including the
// poisoned regression that produces a hard FAIL.

test.describe("Live Console", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("console-panel")).toBeVisible();
  });

  test("loads the control room shell", async ({ page }) => {
    await expect(page.getByText("PitchProof Vigil")).toBeVisible();
    await expect(page.getByTestId("mode-pills")).toBeVisible();
    await expect(page.getByTestId("pill-gemini")).toContainText("Gemini");
  });

  test("typing a clean query yields all passing verdicts", async ({ page }) => {
    await page.getByTestId("ask-input").fill("I want to buy a ticket");
    await page.getByTestId("ask-btn").click();

    await expect(page.getByTestId("ask-result")).toBeVisible();
    const rows = page.getByTestId("eval-row");
    await expect(rows).toHaveCount(3);
    await expect(page.getByTestId("verdict-pass").first()).toBeVisible();
    await expect(page.getByTestId("verdict-fail")).toHaveCount(0);
  });

  test("poisoned kickoff query is flagged as a hard FAIL", async ({ page }) => {
    await page.getByTestId("ask-input").fill("When does Spain play Germany?");
    await page.getByTestId("ask-btn").click();

    await expect(page.getByTestId("ask-result")).toBeVisible();
    await expect(page.getByTestId("answer-text")).toContainText("18:00");
    await expect(page.getByTestId("verdict-fail").first()).toBeVisible();
    await expect(page.getByTestId("eval-list")).toContainText("Kickoff mismatch");
  });

  test("quick chips run a query in one click", async ({ page }) => {
    await page.getByTestId("quick-chip").first().click();
    await expect(page.getByTestId("ask-result")).toBeVisible();
  });

  test("run button is disabled with empty input", async ({ page }) => {
    await expect(page.getByTestId("ask-btn")).toBeDisabled();
    await page.getByTestId("ask-input").fill("hello");
    await expect(page.getByTestId("ask-btn")).toBeEnabled();
  });

  test("language selector switches request language", async ({ page }) => {
    await page.getByTestId("lang-select").selectOption("es");
    await page.getByTestId("ask-input").fill("When does France play England?");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();
  });

  test("Enter key submits the query", async ({ page }) => {
    const input = page.getByTestId("ask-input");
    await input.fill("I want to buy a ticket");
    await input.press("Enter");
    await expect(page.getByTestId("ask-result")).toBeVisible();
  });
});
