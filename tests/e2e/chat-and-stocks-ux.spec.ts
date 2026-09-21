/**
 * E2E: clickable tickers inside chat answers, chat-list search, inline position editing in the
 * chat stock panel, and the Stocks-page search clearing itself once the user moves on.
 * Requires AUTH_TEST_MODE=true (frontend) and TEST_MODE=true (backend).
 */
import type { Page } from "@playwright/test";
import { test, expect, ingestAnalysis } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const TEST_EMAIL = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";
const TOK = encodeURIComponent(`test-token-${TEST_EMAIL}`);

const A = "LNKA";
const B = "LNKB";
const UNTRACKED = "ZZUNT";

async function login(page: Page) {
  await page.goto("/signin");
  const btn = page.getByTestId("test-signin-btn");
  if (!(await btn.isVisible().catch(() => false))) test.skip(true, "AUTH_TEST_MODE not enabled");
  await btn.click();
  await page.waitForURL(/dashboard/, { timeout: 10_000 });
}

// Unique per run so reruns against the same database don't produce duplicate rows.
const RUN = Date.now().toString(36);
const ALPHA_TITLE = `alpha ${RUN} crypto question`;
const BETA_TITLE = `beta ${RUN} rebalance idea`;

let convA = "";
let convAlpha = "";
let convBeta = "";

test.beforeAll(async ({ request }) => {
  for (const t of [A, B]) {
    await request.post(`${BACKEND}/watchlist?id_token=${TOK}`, { data: { ticker: t, is_leveraged: false } });
    await ingestAnalysis(request, t, "HOLD", { current_price: 50 });
  }
  const mk = async (data: object) => (await (await request.post(`${BACKEND}/conversations?id_token=${TOK}`, { data })).json()).id as string;
  convA = await mk({ ticker: A, title: "links test" });
  convAlpha = await mk({ title: ALPHA_TITLE });
  convBeta = await mk({ title: BETA_TITLE });
});

test.describe("Tickers inside chat answers", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.route(`**/conversations/${convA}/messages?*`, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        json: [{
          id: "m1", role: "assistant", created_at: new Date().toISOString(),
          content: `**${A}** is a HOLD and ${B} is a HOLD too. ${UNTRACKED} isn't tracked. Price is right NOW, above the MA50.`,
        }],
      });
    });
  });

  test("tracked tickers become links, untracked / ambiguous words do not", async ({ page }) => {
    await page.goto(`/chat?conv=${convA}`);
    const links = page.getByTestId("ticker-link");
    await expect(links).toHaveCount(2);
    await expect(links.nth(0)).toHaveText(A);
    await expect(links.nth(1)).toHaveText(B);
    await expect(page.getByText(UNTRACKED, { exact: false })).toBeVisible();
  });

  test("clicking a ticker opens THAT ticker's card without leaving the conversation", async ({ page }) => {
    await page.goto(`/chat?conv=${convA}`);
    await page.getByTestId("ticker-link").nth(1).click();
    const panel = page.getByTestId("stock-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText(`${B} ·`);
    await expect(page.getByTestId("ticker-strip")).toContainText(A);
    await expect(page.getByPlaceholder(/Ask about your stocks/)).toBeVisible();
  });
});

test.describe("Chat list search", () => {
  test.beforeEach(async ({ page }) => login(page));

  test("filters by title, shows an empty state, and clears", async ({ page }) => {
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");
    const search = page.getByTestId("chat-search");
    await expect(page.getByText(ALPHA_TITLE)).toBeVisible();
    await expect(page.getByText(BETA_TITLE)).toBeVisible();

    await search.fill(`${RUN} rebal`);
    await expect(page.getByText(BETA_TITLE)).toBeVisible();
    await expect(page.getByText(ALPHA_TITLE)).not.toBeVisible();

    await search.fill("zzzz-nothing");
    await expect(page.getByTestId("chat-search-empty")).toBeVisible();

    await search.press("Escape");
    await expect(search).toHaveValue("");
    await expect(page.getByText(ALPHA_TITLE)).toBeVisible();
  });

  test("also matches on ticker", async ({ page }) => {
    await page.goto("/chat");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("chat-search").fill(A.toLowerCase());
    await expect(page.getByText(`[${A}]`).first()).toBeVisible();
    await expect(page.getByText(ALPHA_TITLE)).not.toBeVisible();
  });
});

test.describe("Position editor in the chat stock panel", () => {
  test.beforeEach(async ({ page, request }) => {
    await request.patch(`${BACKEND}/watchlist/${A}/sell?id_token=${TOK}`);
    await login(page);
    await page.goto(`/chat?conv=${convA}`);
    await page.getByTestId("ticker-strip").click();
    await expect(page.getByTestId("position-editor")).toBeVisible();
  });

  const positionFromApi = async (request: import("@playwright/test").APIRequestContext) => {
    const items = await (await request.get(`${BACKEND}/watchlist?id_token=${TOK}`)).json();
    return items.find((i: { ticker: string }) => i.ticker === A);
  };

  test("add, update, and clear a position without leaving the chat", async ({ page, request }) => {
    const editor = page.getByTestId("position-editor");
    await expect(page.getByTestId("position-summary")).toContainText("Not in your positions");

    await page.getByTestId("position-edit").click();
    await page.getByTestId("position-shares").fill("10");
    await page.getByTestId("position-cost").fill("100");
    await page.getByTestId("position-save").click();
    await expect(page.getByTestId("position-summary")).toContainText("10 sh @ $100.00");
    await expect(page.getByTestId("position-status")).toContainText("Saved");
    await expect.poll(async () => (await positionFromApi(request)).shares).toBe(10);
    expect((await positionFromApi(request)).avg_cost).toBe(100);

    await page.getByTestId("position-edit").click();
    await page.getByTestId("position-shares").fill("12.5");
    await page.getByTestId("position-save").click();
    await expect(page.getByTestId("position-summary")).toContainText("12.5 sh");
    await expect.poll(async () => (await positionFromApi(request)).shares).toBe(12.5);

    await page.getByTestId("position-edit").click();
    await page.getByTestId("position-clear").click();
    await expect(page.getByTestId("position-summary")).toContainText("Not in your positions");
    await expect.poll(async () => (await positionFromApi(request)).shares).toBeNull();
    await expect(editor).toBeVisible();
    await expect(page.getByPlaceholder(/Ask about your stocks/)).toBeVisible();
  });

  test("rejects an empty or non-positive share count", async ({ page, request }) => {
    await page.getByTestId("position-edit").click();
    await page.getByTestId("position-save").click();
    await expect(page.getByTestId("position-error")).toBeVisible();
    await page.getByTestId("position-shares").fill("-3");
    await page.getByTestId("position-save").click();
    await expect(page.getByTestId("position-error")).toBeVisible();
    expect((await positionFromApi(request)).shares).toBeNull();
  });
});

test.describe("Stocks page search clears itself", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await expect(page.locator(`#stock-row-${A}`)).toBeVisible({ timeout: 10_000 });
  });

  const box = (page: Page) => page.getByPlaceholder(/Search your positions/);

  test("clicking a ticker row clears the search, restores the list, and keeps the row open", async ({ page }) => {
    await box(page).fill(A);
    await expect(page.locator(`#stock-row-${B}`)).toHaveCount(0);
    await page.locator(`#stock-row-${A}`).getByText(A, { exact: true }).first().click();
    await expect(box(page)).toHaveValue("");
    await expect(page.locator(`#stock-row-${B}`)).toBeVisible();
    await expect(page.locator(`#stock-row-${A}`)).toContainText("The Story");
  });

  test("clicking elsewhere clears the search", async ({ page }) => {
    await box(page).fill(A);
    await expect(page.locator(`#stock-row-${B}`)).toHaveCount(0);
    await page.getByRole("heading", { name: "Stocks" }).click();
    await expect(box(page)).toHaveValue("");
    await expect(page.locator(`#stock-row-${B}`)).toBeVisible();
  });

  test("using the toolbar itself (sort, typing) does NOT clear it", async ({ page }) => {
    await box(page).fill(A);
    await page.getByRole("button", { name: "A–Z" }).click();
    await expect(box(page)).toHaveValue(A);
    await expect(page.locator(`#stock-row-${B}`)).toHaveCount(0);
  });
});
