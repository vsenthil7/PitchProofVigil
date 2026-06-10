import { test, expect } from "@playwright/test";

// Situational-awareness column: metric tiles update after actions, and the
// live WebSocket feed receives events in real time.

test.describe("Metrics & Live Feed", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("metrics")).toBeVisible();
  });

  test("metric tiles render", async ({ page }) => {
    await expect(page.getByTestId("metric-traces")).toBeVisible();
    await expect(page.getByTestId("metric-drift")).toBeVisible();
    await expect(page.getByTestId("metric-real")).toBeVisible();
  });

  test("live feed connects via websocket", async ({ page }) => {
    await expect(page.getByTestId("conn-status")).toContainText("streaming", {
      timeout: 10_000,
    });
  });

  test("asking a question pushes a trace event into the feed", async ({
    page,
  }) => {
    await expect(page.getByTestId("conn-status")).toContainText("streaming", {
      timeout: 10_000,
    });
    await page.getByTestId("ask-input").fill("I want to buy a ticket");
    await page.getByTestId("ask-btn").click();

    await expect(page.getByTestId("feed-item").first()).toBeVisible();
    await expect(page.getByTestId("feed-list")).toContainText("Trace evaluated");
  });

  test("running the gate pushes a gate event into the feed", async ({
    page,
  }) => {
    await expect(page.getByTestId("conn-status")).toContainText("streaming", {
      timeout: 10_000,
    });
    await page.getByTestId("gate-btn").click();
    await expect(page.getByTestId("feed-list")).toContainText("Gate", {
      timeout: 10_000,
    });
  });

  test("trace count increases after an ask", async ({ page }) => {
    const before = await page
      .getByTestId("metric-traces")
      .locator(".metric-value")
      .textContent();
    await page.getByTestId("ask-input").fill("I want to buy a ticket");
    await page.getByTestId("ask-btn").click();
    await expect(page.getByTestId("ask-result")).toBeVisible();
    // health polls every 5s; wait for the tile to move past its prior value.
    await expect(async () => {
      const after = await page
        .getByTestId("metric-traces")
        .locator(".metric-value")
        .textContent();
      expect(Number(after)).toBeGreaterThan(Number(before));
    }).toPass({ timeout: 8000 });
  });
});
