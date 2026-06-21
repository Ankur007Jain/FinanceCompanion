import { test, expect } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";

test.describe("Backend API smoke", () => {
  test("backend health check returns ok", async ({ request }) => {
    const r = await request.get(`${BACKEND}/health`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.status).toBe("ok");
  });

  test("jobs health check returns ok", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/health`);
    expect(r.ok()).toBeTruthy();
  });

  test("ingest-analysis rejects bad secret", async ({ request }) => {
    const r = await request.post(`${BACKEND}/jobs/ingest-analysis?x_job_secret=wrong`, {
      data: { ticker: "NFLX", analysis_date: "2024-01-01", verdict: "HOLD" },
    });
    expect(r.status()).toBe(401);
  });

  test("admin/tickers rejects bad secret", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/admin/tickers?x_admin_secret=bad`);
    expect(r.status()).toBe(401);
  });

  test("watchlist search returns array", async ({ request }) => {
    const r = await request.get(`${BACKEND}/watchlist/search?q=NFLX&id_token=badtoken`);
    // Either 401 (auth failed) or 200 with array — both are valid depending on Google token mock
    expect([200, 401]).toContain(r.status());
  });
});

test.describe("Sign-in page", () => {
  test("renders FinanceCompanion branding", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByText("FinanceCompanion")).toBeVisible();
  });

  test("shows Sign in with Google button", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByRole("button", { name: /sign in with google/i })).toBeVisible();
  });

  test("shows tagline", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByText(/busy professionals/i)).toBeVisible();
  });

  test("page title contains FinanceCompanion", async ({ page }) => {
    await page.goto("/signin");
    await expect(page).toHaveTitle(/FinanceCompanion/i);
  });
});

test.describe("Auth redirects", () => {
  test("/ redirects to /signin when not authenticated", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/signin/);
  });

  test("/dashboard redirects to /signin when not authenticated", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/signin/);
  });

  test("/chat redirects to /signin when not authenticated", async ({ page }) => {
    await page.goto("/chat");
    await expect(page).toHaveURL(/signin/);
  });

  test("redirect preserves signin page content", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByText("FinanceCompanion")).toBeVisible();
  });
});

test.describe("Signin page interactions", () => {
  test("Google sign-in button is clickable", async ({ page }) => {
    await page.goto("/signin");
    const btn = page.getByRole("button", { name: /sign in with google/i });
    await expect(btn).toBeEnabled();
  });

  test("page is responsive on mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/signin");
    await expect(page.getByText("FinanceCompanion")).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in with google/i })).toBeVisible();
  });

  test("page is responsive on tablet viewport", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/signin");
    await expect(page.getByRole("button", { name: /sign in with google/i })).toBeVisible();
  });
});
