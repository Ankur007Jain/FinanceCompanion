import { test, expect } from "@playwright/test";

test.describe("FinanceCompanion smoke", () => {
  test("sign-in page loads", async ({ page }) => {
    await page.goto("/signin");
    await expect(page).toHaveTitle(/FinanceCompanion/i);
  });

  test("sign-in button is visible", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByText("Sign in with Google")).toBeVisible();
  });

  test("unauthenticated user is redirected from dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/signin/);
  });

  test("unauthenticated user is redirected from chat", async ({ page }) => {
    await page.goto("/chat");
    await expect(page).toHaveURL(/signin/);
  });
});
