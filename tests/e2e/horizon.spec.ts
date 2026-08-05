import { test, expect, ingestAnalysis, addToWatchlist, ingestHorizon } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const JOB_SECRET = process.env.JOB_SECRET || "test-job-secret";
const ADMIN_SECRET = process.env.ADMIN_SECRET || "test-admin-secret";

// ── API contract — endpoints introduced by the horizon feature ──────────────

test.describe("/jobs/ingest-horizon", () => {
  test("rejects bad job secret", async ({ request }) => {
    const r = await request.post(`${BACKEND}/jobs/ingest-horizon?x_job_secret=wrong`, {
      data: { ticker: "ZBADH", computed_date: "2026-01-01", time_horizon_fit: "LONG_TERM_HOLD" },
    });
    expect(r.status()).toBe(401);
  });

  test("rejects missing required fields", async ({ request }) => {
    const r = await request.post(`${BACKEND}/jobs/ingest-horizon?x_job_secret=${JOB_SECRET}`, {
      data: { ticker: "ZMISSH" },  // missing computed_date, time_horizon_fit
    });
    expect(r.status()).toBe(422);
  });

  test("accepts a valid payload and reports saved", async ({ request }) => {
    const r = await ingestHorizon(request, "ZE2EH1", "LONG_TERM_HOLD", "E2E durable moat test.");
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body).toEqual({ status: "saved", ticker: "ZE2EH1" });
  });

  test("re-ingesting the same ticker updates rather than erroring", async ({ request }) => {
    await ingestHorizon(request, "ZE2EH2", "SHORT_TERM_TRADE_ONLY", "First pass.");
    const r2 = await ingestHorizon(request, "ZE2EH2", "LONG_TERM_HOLD", "Second pass.");
    expect(r2.ok()).toBeTruthy();
  });
});

test.describe("/jobs/admin/last-horizon", () => {
  test("rejects bad admin secret", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/admin/last-horizon?x_admin_secret=wrong`);
    expect(r.status()).toBe(401);
  });

  test("returns the ticker just ingested, scoped by tickers filter", async ({ request }) => {
    await ingestHorizon(request, "ZE2EH3", "AVOID", "E2E structural decline test.");
    const r = await request.get(
      `${BACKEND}/jobs/admin/last-horizon?x_admin_secret=${ADMIN_SECRET}&tickers=ZE2EH3`
    );
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.horizons.ZE2EH3.time_horizon_fit).toBe("AVOID");
  });
});

test.describe("/jobs/admin/fundamentals-history", () => {
  test("rejects bad admin secret", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/admin/fundamentals-history?x_admin_secret=wrong`);
    expect(r.status()).toBe(401);
  });

  test("returns a dated series for a ticker with ingested analyses", async ({ request }) => {
    await ingestAnalysis(request, "ZE2EH4", "HOLD", { revenue_growth: 0.12 });
    const r = await request.get(
      `${BACKEND}/jobs/admin/fundamentals-history?x_admin_secret=${ADMIN_SECRET}&tickers=ZE2EH4`
    );
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(Object.keys(body.fundamentals.ZE2EH4).length).toBeGreaterThan(0);
  });
});

// ── real authenticated UI — horizon badge actually renders ──────────────────
// Unlike the API-contract tests above, this exercises the real dashboard page
// behind the test-mode login (see fixtures.ts: loggedInPage), the same pattern
// memory-page.spec.ts uses, rather than only checking the backend accepted the data.

test.describe("Dashboard — long-term/short-term horizon badge", () => {
  test("expanding a stock with a computed horizon shows its reasoning", async ({ loggedInPage: page, request, testEmail }) => {
    const ticker = "ZHRZN";
    const reasoning = "E2E-seeded reasoning: durable moat, expanding margins.";

    await addToWatchlist(request, ticker, testEmail);
    await ingestAnalysis(request, ticker, "HOLD");
    await ingestHorizon(request, ticker, "LONG_TERM_HOLD", reasoning);

    await page.goto("/dashboard");
    await page.getByPlaceholder(/search your positions/i).fill(ticker);
    await page.getByText(ticker, { exact: true }).click();

    await expect(page.getByText(reasoning)).toBeVisible({ timeout: 15_000 });
    // "Long-Term Hold" legitimately renders in two places — the hero badge chip and
    // the "1-5yr Outlook" section header — so this checks at least one is visible
    // rather than asserting an exact single match.
    await expect(page.getByText("Long-Term Hold").first()).toBeVisible();
  });

  test("a stock with no computed horizon shows no horizon badge", async ({ loggedInPage: page, request, testEmail }) => {
    const ticker = "ZNOHZ";

    await addToWatchlist(request, ticker, testEmail);
    await ingestAnalysis(request, ticker, "HOLD");
    // Deliberately no ingestHorizon call — this ticker has never been judged.

    await page.goto("/dashboard");
    await page.getByPlaceholder(/search your positions/i).fill(ticker);
    await page.getByText(ticker, { exact: true }).click();

    // "The Story" is always present once expanded — proves the card actually opened,
    // so an absent "1-5yr Outlook" section below is a real negative, not a load failure.
    await expect(page.getByText("The Story")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("1-5yr Outlook", { exact: false })).toHaveCount(0);
  });
});
