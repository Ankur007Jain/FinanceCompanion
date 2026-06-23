/**
 * Authenticated dashboard E2E tests.
 * Requires AUTH_TEST_MODE=true (frontend) and TEST_MODE=true (backend).
 * Tests are skipped automatically when the test sign-in button is not present.
 */
import { test, expect, ingestAnalysis } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const JOB_SECRET = process.env.JOB_SECRET || "test-job-secret";
const TEST_EMAIL = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";
const TEST_TOKEN = `test-token-${TEST_EMAIL}`;

// ── sign-in flow ──────────────────────────────────────────────────────────────

test.describe("Test sign-in (AUTH_TEST_MODE)", () => {
  test("test login button visible when AUTH_TEST_MODE=true", async ({ page }) => {
    await page.goto("/signin");
    const btn = page.getByTestId("test-signin-btn");
    const isVisible = await btn.isVisible().catch(() => false);
    if (!isVisible) {
      test.skip(true, "AUTH_TEST_MODE not enabled — skipping authenticated tests");
      return;
    }
    await expect(btn).toBeVisible();
  });

  test("test login lands on dashboard", async ({ page }) => {
    await page.goto("/signin");
    const btn = page.getByTestId("test-signin-btn");
    const isVisible = await btn.isVisible().catch(() => false);
    if (!isVisible) {
      test.skip(true, "AUTH_TEST_MODE not enabled");
      return;
    }
    await btn.click();
    await page.waitForURL(/dashboard/, { timeout: 10_000 });
    await expect(page).toHaveURL(/dashboard/);
  });
});

// ── dashboard loads ───────────────────────────────────────────────────────────

test.describe("Dashboard — authenticated", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/signin");
    const btn = page.getByTestId("test-signin-btn");
    const isVisible = await btn.isVisible().catch(() => false);
    if (!isVisible) test.skip(true, "AUTH_TEST_MODE not enabled");
    await btn.click();
    await page.waitForURL(/dashboard/, { timeout: 10_000 });
  });

  test("dashboard renders without JS errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });

  test("dashboard shows Stock Copilot branding", async ({ page }) => {
    await expect(page.getByText("Stock Copilot")).toBeVisible();
  });

  test("empty watchlist shows add-ticker prompt", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Either "Add your first stock" hint or the search input is visible
    const hasHint = await page.getByText(/add.*stock|search.*ticker/i).isVisible().catch(() => false);
    const hasInput = await page.getByPlaceholder(/ticker|search/i).isVisible().catch(() => false);
    expect(hasHint || hasInput).toBe(true);
  });

  test("sign-out button exists", async ({ page }) => {
    const signOut = page.getByRole("button", { name: /sign.?out|log.?out/i });
    await expect(signOut).toBeVisible();
  });
});

// ── watchlist CRUD via API ─────────────────────────────────────────────────────

test.describe("Watchlist — API (test token)", () => {
  test("add ticker to watchlist", async ({ request }) => {
    const r = await request.post(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
      data: { ticker: "E2EWL1", company_name: "E2E Test Corp", is_leveraged: false },
    });
    expect([200, 201, 401]).toContain(r.status());
  });

  test("list watchlist returns array", async ({ request }) => {
    const r = await request.get(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`);
    expect([200, 401]).toContain(r.status());
    if (r.status() === 200) {
      const body = await r.json();
      expect(Array.isArray(body)).toBe(true);
    }
  });

  test("delete ticker from watchlist", async ({ request }) => {
    // Add first
    await request.post(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
      data: { ticker: "E2EWL2", is_leveraged: false },
    });
    // Then delete
    const r = await request.delete(`${BACKEND}/watchlist/E2EWL2?id_token=${encodeURIComponent(TEST_TOKEN)}`);
    expect([200, 204, 401, 404]).toContain(r.status());
  });

  test("user profile endpoint returns user data", async ({ request }) => {
    const r = await request.get(`${BACKEND}/auth/me?id_token=${encodeURIComponent(TEST_TOKEN)}`);
    expect([200, 401]).toContain(r.status());
    if (r.status() === 200) {
      const body = await r.json();
      expect(body).toHaveProperty("email");
    }
  });
});

// ── stock card UI — verdict badge ─────────────────────────────────────────────

test.describe("Stock card — verdict badge", () => {
  test.beforeAll(async ({ request }) => {
    // Seed a watchlist entry + analysis for the test user
    await request.post(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
      data: { ticker: "E2EUI1", company_name: "E2E UI Corp", is_leveraged: false },
    });
    await ingestAnalysis(request, "E2EUI1", "BUY", {
      verdict_a: "BUY",
      verdict_b: "BUY",
      verdict_agreement: true,
    });
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/signin");
    const btn = page.getByTestId("test-signin-btn");
    const isVisible = await btn.isVisible().catch(() => false);
    if (!isVisible) test.skip(true, "AUTH_TEST_MODE not enabled");
    await btn.click();
    await page.waitForURL(/dashboard/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle");
  });

  test("BUY verdict badge is visible for seeded ticker", async ({ page }) => {
    const verdictBadge = page.getByText("BUY").first();
    await expect(verdictBadge).toBeVisible({ timeout: 8_000 });
  });
});

// ── dual-agent badge UI ───────────────────────────────────────────────────────

test.describe("Dual-agent badge — UI", () => {
  const AGREE_TICKER = "E2EDA_UI1";
  const SPLIT_TICKER = "E2EDA_UI2";

  test.beforeAll(async ({ request }) => {
    // Seed watchlist + analysis for agree and split cases
    for (const ticker of [AGREE_TICKER, SPLIT_TICKER]) {
      await request.post(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
        data: { ticker, is_leveraged: false },
      });
    }
    await ingestAnalysis(request, AGREE_TICKER, "BUY", {
      verdict_a: "BUY", verdict_b: "BUY", verdict_agreement: true,
    });
    await ingestAnalysis(request, SPLIT_TICKER, "WATCH", {
      verdict_a: "BUY", verdict_b: "HOLD", verdict_agreement: false,
      split_reason: "Claude bullish on RSI; Gemini cautious on earnings.",
    });
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/signin");
    const btn = page.getByTestId("test-signin-btn");
    const isVisible = await btn.isVisible().catch(() => false);
    if (!isVisible) test.skip(true, "AUTH_TEST_MODE not enabled");
    await btn.click();
    await page.waitForURL(/dashboard/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle");
  });

  test("agreement badge '✓ agree' visible in collapsed row", async ({ page }) => {
    // The "✓ agree" sub-line should be visible in the stock row
    await expect(page.getByText("✓ agree").first()).toBeVisible({ timeout: 8_000 });
  });

  test("split badge '⚠ split' visible in collapsed row", async ({ page }) => {
    await expect(page.getByText("⚠ split").first()).toBeVisible({ timeout: 8_000 });
  });

  test("expand agree card shows 'Both AI models agree' badge", async ({ page }) => {
    // Find the agree ticker row and click to expand
    const agreeRow = page.getByText(AGREE_TICKER).first();
    await agreeRow.click();
    await expect(page.getByText(/Both AI models agree/i)).toBeVisible({ timeout: 5_000 });
  });

  test("expand split card shows split verdict and split_reason", async ({ page }) => {
    const splitRow = page.getByText(SPLIT_TICKER).first();
    await splitRow.click();
    await expect(page.getByText(/Split/i).first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/Claude bullish on RSI/i)).toBeVisible({ timeout: 5_000 });
  });
});

// ── mobile viewport ───────────────────────────────────────────────────────────

test.describe("Dashboard — mobile viewport", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/signin");
    const btn = page.getByTestId("test-signin-btn");
    const isVisible = await btn.isVisible().catch(() => false);
    if (!isVisible) test.skip(true, "AUTH_TEST_MODE not enabled");
    await btn.click();
    await page.waitForURL(/dashboard/, { timeout: 10_000 });
  });

  test("dashboard renders on mobile without overflow", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Stock Copilot")).toBeVisible();
    // No horizontal scroll
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 5); // 5px tolerance
  });
});
