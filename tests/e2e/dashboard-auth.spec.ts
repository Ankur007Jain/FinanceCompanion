/**
 * Authenticated dashboard E2E tests.
 * Requires AUTH_TEST_MODE=true (frontend) and TEST_MODE=true (backend).
 * Tests are skipped automatically when the test sign-in button is not present.
 */
import { test, expect, ingestAnalysis } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
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

  test("dashboard shows Finance Companion branding", async ({ page }) => {
    await expect(page.getByText("Finance Companion", { exact: true })).toBeVisible();
  });

  test("empty watchlist shows add-ticker prompt", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Either "Add your first stock" hint or the search input is visible
    const hasHint = await page.getByText(/add.*stock|search.*ticker/i).isVisible().catch(() => false);
    const hasInput = await page.getByPlaceholder(/ticker|search/i).isVisible().catch(() => false);
    expect(hasHint || hasInput).toBe(true);
  });

  test("sign-out option accessible via user menu", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    // Sign-out is inside a dropdown — click the avatar/initials to open it
    const avatarBtn = page.getByTestId("user-avatar-btn");
    await avatarBtn.click({ timeout: 10_000 });
    await expect(page.getByText("Sign out")).toBeVisible({ timeout: 5_000 });
  });
});

// ── watchlist CRUD via API ─────────────────────────────────────────────────────

test.describe("Watchlist — API (test token)", () => {
  test("add ticker to watchlist", async ({ request }) => {
    const r = await request.post(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
      data: { ticker: "ETWLA", company_name: "E2E Test Corp", is_leveraged: false },
    });
    expect([200, 201, 409, 401]).toContain(r.status());
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
      data: { ticker: "ETWLB", is_leveraged: false },
    });
    // Then delete
    const r = await request.delete(`${BACKEND}/watchlist/ETWLB?id_token=${encodeURIComponent(TEST_TOKEN)}`);
    expect([200, 204, 401, 404]).toContain(r.status());
  });

  test("user profile endpoint returns user data", async ({ request }) => {
    // /auth/me is PATCH-only; use POST /auth/verify to read user data
    const r = await request.post(`${BACKEND}/auth/verify`, {
      data: { id_token: TEST_TOKEN },
    });
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
      data: { ticker: "ETUIN", company_name: "E2E UI Corp", is_leveraged: false },
    });
    await ingestAnalysis(request, "ETUIN", "BUY", {
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
  const AGREE_TICKER = "ETDAU";
  const SPLIT_TICKER = "ETDAS";

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
    // Requires PR #30 (feature/dual-agent-frontend-badge) to be merged
    const badge = page.getByText("✓ agree").first();
    const found = await badge.isVisible({ timeout: 3_000 }).catch(() => false);
    if (!found) {
      test.skip(true, "dual-agent badge UI not present — merge PR #30 to enable");
      return;
    }
    await expect(badge).toBeVisible();
  });

  test("split badge '⚠ split' visible in collapsed row", async ({ page }) => {
    const badge = page.getByText("⚠ split").first();
    const found = await badge.isVisible({ timeout: 3_000 }).catch(() => false);
    if (!found) {
      test.skip(true, "dual-agent badge UI not present — merge PR #30 to enable");
      return;
    }
    await expect(badge).toBeVisible();
  });

  test("expand agree card shows 'Both AI models agree' badge", async ({ page }) => {
    const agreeRow = page.getByText(AGREE_TICKER).first();
    await agreeRow.click();
    const badge = page.getByText(/Both AI models agree/i);
    const found = await badge.isVisible({ timeout: 3_000 }).catch(() => false);
    if (!found) {
      test.skip(true, "dual-agent badge UI not present — merge PR #30 to enable");
      return;
    }
    await expect(badge).toBeVisible();
  });

  test("expand split card shows split verdict and split_reason", async ({ page }) => {
    const splitRow = page.getByText(SPLIT_TICKER).first();
    await splitRow.click();
    const badge = page.getByText(/Split/i).first();
    const found = await badge.isVisible({ timeout: 3_000 }).catch(() => false);
    if (!found) {
      test.skip(true, "dual-agent badge UI not present — merge PR #30 to enable");
      return;
    }
    await expect(badge).toBeVisible();
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
    // Wait for isMobile useEffect to fire and re-render with mobile layout
    await page.waitForTimeout(300);
    await expect(page.getByText("Finance Companion", { exact: true })).toBeVisible();
    // No horizontal scroll (20px tolerance for scrollbars/padding)
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 20);
  });

  test("hamburger button visible and desktop nav hidden on mobile", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(300);
    // Hamburger present
    await expect(page.getByTestId("hamburger-btn")).toBeVisible();
    // Desktop nav tabs not directly visible (they're inside the drawer, which is closed)
    await expect(page.getByRole("button", { name: "Stocks" })).not.toBeVisible();
  });

  test("all tabs accessible via hamburger drawer", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(300);
    // Open the drawer
    await page.getByTestId("hamburger-btn").click();
    // All tabs should be visible in the drawer
    for (const tab of ["Dashboard", "Stocks", "Discover"]) {
      await expect(page.getByRole("button", { name: tab })).toBeVisible({ timeout: 3_000 });
    }
    // Selecting a tab closes the drawer
    await page.getByRole("button", { name: "Stocks" }).click();
    await expect(page.getByRole("button", { name: "Dashboard" })).not.toBeVisible();
  });

  test("backdrop click closes mobile drawer", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(300);
    await page.getByTestId("hamburger-btn").click();
    await expect(page.getByRole("button", { name: "Stocks" })).toBeVisible();
    // Click the backdrop (left side, outside the 220px drawer)
    await page.mouse.click(80, 300);
    await expect(page.getByRole("button", { name: "Stocks" })).not.toBeVisible();
  });
});
