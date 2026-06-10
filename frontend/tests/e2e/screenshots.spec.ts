import { test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { registerAndLogin } from "./helpers";

const here = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.resolve(here, "../../../docs/screenshots");

test.describe("Documentation screenshots", () => {
  test.use({ viewport: { width: 1320, height: 980 } });

  test("01 — login screen", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("auth-card").waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOTS, "01-login.png") });
  });

  test("02 — evaluation report", async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("ask-input").fill("When does Spain play Germany?");
    await page.getByTestId("ask-btn").click();
    await page.getByTestId("category-scores").waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOTS, "02-evaluation-report.png") });
  });

  test("03 — promotion gate with baseline", async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("tab-gate").click();
    await page.getByTestId("gate-btn").click();
    await page.getByTestId("gate-banner").waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOTS, "03-promotion-gate.png") });
  });

  test("04 — policy editor", async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("tab-policies").click();
    await page.getByTestId("policy-editor").waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOTS, "04-policy-editor.png") });
  });
});
