import { test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// This spec doubles as documentation generation: it drives the dashboard
// through its key states and writes screenshots into ../../docs/screenshots,
// which the user guide references by number.

const here = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.resolve(here, "../../../docs/screenshots");

test.describe("Documentation screenshots", () => {
  test.use({ viewport: { width: 1320, height: 900 } });

  test("01 — empty control room", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("console-panel").waitFor();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(SHOTS, "01-control-room.png") });
  });

  test("02 — passing evaluation", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("ask-input").fill("I want to buy a ticket");
    await page.getByTestId("ask-btn").click();
    await page.getByTestId("ask-result").waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOTS, "02-passing-eval.png") });
  });

  test("03 — caught regression", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("ask-input").fill("When does Spain play Germany?");
    await page.getByTestId("ask-btn").click();
    await page.getByTestId("verdict-fail").first().waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOTS, "03-caught-regression.png") });
  });

  test("04 — promotion blocked", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("gate-btn").click();
    await page.getByTestId("gate-banner").waitFor();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(SHOTS, "04-promotion-blocked.png") });
  });

  test("05 — live feed populated", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("conn-status").waitFor();
    await page.getByTestId("ask-input").fill("When does France play England?");
    await page.getByTestId("ask-btn").click();
    await page.getByTestId("ask-result").waitFor();
    await page.getByTestId("gate-btn").click();
    await page.getByTestId("gate-banner").waitFor();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SHOTS, "05-live-feed.png") });
  });
});
