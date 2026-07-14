/**
 * E2E: chat ticker strip + stock detail panel (shared ExpandedDetail component),
 * and the dashboard "view more" jump-to-card fix.
 * Requires AUTH_TEST_MODE=true (frontend) and TEST_MODE=true (backend).
 */
import type { Page } from "@playwright/test";
import { test, expect, ingestAnalysis } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const TEST_EMAIL = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";
const TEST_TOKEN = `test-token-${TEST_EMAIL}`;

const TICKER = "ETCHP"; // dedicated seed for chat-panel tests

async function login(page: Page) {
  await page.goto("/signin");
  const btn = page.getByTestId("test-signin-btn");
  const isVisible = await btn.isVisible().catch(() => false);
  if (!isVisible) test.skip(true, "AUTH_TEST_MODE not enabled");
  await btn.click();
  await page.waitForURL(/dashboard/, { timeout: 10_000 });
}

async function openTickerConversation(page: Page, mobile = false) {
  await page.goto("/chat");
  await page.waitForLoadState("networkidle");
  if (mobile) await page.getByLabel("Conversations").click();
  await page.getByText(`[${TICKER}]`).first().click();
  await expect(page.getByTestId("ticker-strip")).toBeVisible({ timeout: 8_000 });
}

test.beforeAll(async ({ request }) => {
  await request.post(`${BACKEND}/watchlist?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
    data: { ticker: TICKER, is_leveraged: false },
  });
  await ingestAnalysis(request, TICKER, "BUY", {
    current_price: 123.45,
    reasoning: "Chat panel e2e story: full reasoning visible without leaving the chat.",
  });
  await request.post(`${BACKEND}/conversations?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
    data: { ticker: TICKER, title: "panel test" },
  });
});

test.describe("Chat stock panel — desktop", () => {
  test.beforeEach(async ({ page }) => login(page));

  test("ticker strip shows live analysis context", async ({ page }) => {
    await openTickerConversation(page);
    const strip = page.getByTestId("ticker-strip");
    await expect(strip).toContainText(TICKER);
    await expect(strip).toContainText("$123.45");
    await expect(strip).toContainText("BUY");
    await expect(strip).toContainText("View details");
  });

  test("strip opens side panel with the full stock card, chat stays visible", async ({ page }) => {
    await openTickerConversation(page);
    await page.getByTestId("ticker-strip").click();
    const panel = page.getByTestId("stock-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByText("The Story")).toBeVisible();
    // Simple mode may show a Haiku-rewritten version of the reasoning (generated
    // asynchronously after ingest) — switch to Technical to assert the raw text.
    await panel.getByRole("button", { name: "Technical" }).click();
    await expect(panel.getByText("Chat panel e2e story", { exact: false })).toBeVisible();
    // Chat input still usable next to the open panel
    await expect(page.getByPlaceholder(/Ask about your stocks/)).toBeVisible();
  });

  test("close button dismisses the panel", async ({ page }) => {
    await openTickerConversation(page);
    await page.getByTestId("ticker-strip").click();
    await expect(page.getByTestId("stock-panel")).toBeVisible();
    await page.getByLabel("Close details").click();
    await expect(page.getByTestId("stock-panel")).not.toBeVisible();
  });

  test("non-ticker conversations show no strip", async ({ page, request }) => {
    await request.post(`${BACKEND}/conversations?id_token=${encodeURIComponent(TEST_TOKEN)}`, {
      data: { title: "general chat" },
    });
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");
    await page.getByText("general chat").first().click();
    await page.waitForTimeout(600);
    await expect(page.getByTestId("ticker-strip")).not.toBeVisible();
  });
});

test.describe("Chat stock panel — mobile viewport", () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await page.waitForTimeout(300);
  });

  test("strip opens full-screen sheet, no horizontal overflow", async ({ page }) => {
    await openTickerConversation(page, true);
    await page.getByTestId("ticker-strip").click();
    const panel = page.getByTestId("stock-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByText("The Story")).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 20);
    // Close returns to the chat
    await page.getByLabel("Close details").click();
    await expect(page.getByPlaceholder(/Ask about your stocks/)).toBeVisible();
  });
});

test.describe("Dashboard view-more jump", () => {
  test("expanded stock row scrolls into view", async ({ page }) => {
    await login(page);
    await page.waitForLoadState("networkidle");
    // The seeded ticker's row exists on the Stocks tab with an anchor id
    const inView = await page.evaluate(async (ticker) => {
      const el = document.getElementById(`stock-row-${ticker}`);
      if (!el) return "missing";
      el.scrollIntoView({ block: "start" });
      await new Promise(r => setTimeout(r, 300));
      const r2 = el.getBoundingClientRect();
      return r2.top >= -50 && r2.top < window.innerHeight ? "in-view" : "out-of-view";
    }, TICKER);
    expect(inView).toBe("in-view");
  });
});
