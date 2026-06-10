import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers";

test.describe("Authentication", () => {
  test("login screen renders first", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("auth-card")).toBeVisible();
    await expect(page.getByText("PitchProof Vigil")).toBeVisible();
  });

  test("can toggle to login mode and back", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("to-login").click();
    await expect(page.getByTestId("tenant-id")).toBeVisible();
    await page.getByTestId("to-register").click();
    await expect(page.getByTestId("slug")).toBeVisible();
  });

  test("register lands on the dashboard", async ({ page }) => {
    await registerAndLogin(page);
    await expect(page.getByTestId("session-bar")).toBeVisible();
    await expect(page.getByTestId("nav-console")).toBeVisible();
  });

  test("logout returns to the auth screen", async ({ page }) => {
    await registerAndLogin(page);
    await page.getByTestId("logout-btn").click();
    await expect(page.getByTestId("auth-card")).toBeVisible();
  });

  test("bad login shows an error", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("to-login").click();
    await page.getByTestId("tenant-id").fill("nonexistent");
    await page.getByTestId("email").fill("x@y.com");
    await page.getByTestId("password").fill("pw12345678");
    await page.getByTestId("auth-submit").click();
    await expect(page.getByTestId("auth-error")).toBeVisible();
  });
});
