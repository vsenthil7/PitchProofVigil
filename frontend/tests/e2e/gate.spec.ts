import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers";

test.describe("Promotion Gate", () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("nav-gate").click();
    await expect(page.getByTestId("gate-panel")).toBeVisible();
  });

  test("running the gate produces a decision with category scores", async ({ page }) => {
    await page.getByTestId("gate-btn").click();
    await expect(page.getByTestId("gate-result")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("gate-banner")).toBeVisible();
    await expect(page.getByTestId("category-scores")).toBeVisible();
  });

  test("custom candidate id echoed", async ({ page }) => {
    await page.getByTestId("candidate-input").fill("");
    await page.getByTestId("candidate-input").fill("release-99");
    await page.getByTestId("gate-btn").click();
    await expect(page.getByTestId("gate-result")).toContainText("release-99");
  });

  test("gate button disabled without candidate", async ({ page }) => {
    await page.getByTestId("candidate-input").fill("");
    await expect(page.getByTestId("gate-btn")).toBeDisabled();
  });
});

test.describe("Policy Editor", () => {
  test.beforeEach(async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("nav-policies").click();
  });

  test("lists all evaluators and saves a policy", async ({ page }) => {
    await expect(page.getByTestId("policy-editor")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("policy-row-factual_accuracy")).toBeVisible();
    await expect(page.getByTestId("policy-row-pii_leakage")).toBeVisible();
    await page.getByTestId("policy-save").click();
    await expect(page.getByTestId("policy-status")).toContainText("Saved");
  });

  test("can toggle an evaluator and adjust weight", async ({ page }) => {
    await expect(page.getByTestId("policy-editor")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("toggle-enabled-llm_judge").uncheck();
    await page.getByTestId("weight-latency_slo").fill("3");
    await page.getByTestId("policy-save").click();
    await expect(page.getByTestId("policy-status")).toContainText("v1");
  });
});
