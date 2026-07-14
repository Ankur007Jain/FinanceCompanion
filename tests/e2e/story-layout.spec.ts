/**
 * E2E tests for the story-first expanded card layout, fundamentals display
 * scaling, and ⭐ story beats in past analyses — desktop and mobile.
 * Requires AUTH_TEST_MODE=true (frontend) and TEST_MODE=true (backend).
 */
import type { Page } from "@playwright/test";
import { test, expect, ingestAnalysis } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const TEST_EMAIL = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";
const TEST_TOKEN = `test-token-${TEST_EMAIL}`;

const TICKER = "ETSTY"; // dedicated seed for story-layout tests

async function login(page: Page) {
  await page.goto("/signin");
  const btn = page.getByTestId("test-signin-btn");
  const isVisible = await btn.isVisible().catch(() => false);
  if (!isVisible) test.skip(true, "AUTH_TEST_MODE not enabled");
  await btn.click();
  await page.waitForURL(/dashboard/, { timeout: 10_000 });
  await page.waitForLoadState("networkidle");
}

async function expandCard(page: Page) {
  const row = page.getByText(TICKER).first();
  await row.scrollIntoViewIfNeeded();
  await row.click();
  await expect(page.getByText("The Story")).toBeVisible({ timeout: 5_000 });
}

test.beforeAll(async ({ request }) => {
  await request.post(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
    data: { ticker: TICKER, is_leveraged: false },
  });
  // Yesterday: an ⭐ important day (story beat)
  const yesterday = new Date(Date.now() - 86_400_000).toISOString().split("T")[0];
  await ingestAnalysis(request, TICKER, "WATCH", {
    analysis_date: yesterday,
    is_important_day: true,
    importance_reason: "Verdict flipped BUY to WATCH after breaking key support.",
  });
  // Today: full analysis with long-term returns + fundamentals (percent-form fields)
  await ingestAnalysis(request, TICKER, "BUY", {
    reasoning: "E2E story reasoning: the setup, the evidence, and the conclusion.",
    stock_52w_change: -47.8, sp500_52w_change: 20.1,
    stock_5y_change: -33.6, sp500_5y_change: 72.3,
    pe_trailing: 9.1, dividend_yield: 3.14,
    scenario_bull: "Re-rates to 12x forward PE.", scenario_bull_pct: 45.0, scenario_bull_prob: 20,
    scenario_base: "Stabilizes in current range.", scenario_base_pct: 2.0, scenario_base_prob: 45,
    scenario_bear: "Breaks 52-week low.", scenario_bear_pct: -18.0, scenario_bear_prob: 35,
  });
});

// ── desktop ───────────────────────────────────────────────────────────────────

test.describe("Story layout — desktop", () => {
  test.beforeEach(async ({ page }) => login(page));

  test("expanded card has a story column with prose sections in reading order", async ({ page }) => {
    await expandCard(page);
    // Simple mode may show a Haiku-rewritten version (generated asynchronously
    // after ingest) — switch to Technical to assert the raw seeded text.
    await page.getByRole("button", { name: "Technical" }).click();
    await expect(page.getByText("E2E story reasoning", { exact: false })).toBeVisible();
    // Bull/Bear prose lives under the story, not in scenario boxes
    await expect(page.getByText("Earnings beat drives re-rating.")).toBeVisible();
    await expect(page.getByText("Macro headwinds compress margins.")).toBeVisible();
    await expect(page.getByText("Guidance cut by more than 10%.")).toBeVisible();
  });

  test("90-day scenarios are numbers-only in the rail (no duplicated prose)", async ({ page }) => {
    await expandCard(page);
    await expect(page.getByText("90-Day Scenarios")).toBeVisible();
    await expect(page.getByText("+45.0%")).toBeVisible();
    await expect(page.getByText("20% odds")).toBeVisible();
    // The scenario description text must NOT render (deduped — bull_case covers it)
    await expect(page.getByText("Re-rates to 12x forward PE.")).not.toBeVisible();
  });

  test("long-term returns render at correct scale (regression: was 100x inflated)", async ({ page }) => {
    await expandCard(page);
    await expect(page.getByText("-47.8%").first()).toBeVisible();
    await expect(page.getByText("-33.6%").first()).toBeVisible();
    await expect(page.getByText("-4780")).not.toBeVisible();
    // dividend_yield comes percent-form from yfinance: 3.1%, not 314%
    await expect(page.getByText("3.1%")).toBeVisible();
    await expect(page.getByText("314.0%")).not.toBeVisible();
  });

  test("⭐ important day renders as a story beat with its reason", async ({ page }) => {
    await expandCard(page);
    const past = page.getByText(/PAST ANALYSES/).first();
    await past.scrollIntoViewIfNeeded();
    await past.click();
    await expect(
      page.getByText("Verdict flipped BUY to WATCH after breaking key support.").first()
    ).toBeVisible({ timeout: 8_000 });
  });
});

// ── mobile ────────────────────────────────────────────────────────────────────

test.describe("Story layout — mobile viewport", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await page.waitForTimeout(300); // isMobile useEffect re-render
  });

  test("expanded card shows story column and rail stacked, no horizontal overflow", async ({ page }) => {
    await expandCard(page);
    await page.getByRole("button", { name: "Technical" }).click();
    await expect(page.getByText("E2E story reasoning", { exact: false })).toBeVisible();
    await expect(page.getByText("90-Day Scenarios")).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 20);
  });

  test("fundamentals scale correctly on mobile", async ({ page }) => {
    await expandCard(page);
    await expect(page.getByText("-47.8%").first()).toBeVisible();
    await expect(page.getByText("-4780")).not.toBeVisible();
  });
});
