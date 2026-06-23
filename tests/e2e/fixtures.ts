import { test as base, expect, Page, APIRequestContext } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const JOB_SECRET = process.env.JOB_SECRET || "test-job-secret";
const ADMIN_SECRET = process.env.ADMIN_SECRET || "test-admin-secret";
const TEST_EMAIL = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";

// ── login helper ─────────────────────────────────────────────────────────────

export async function loginAsTestUser(page: Page) {
  await page.goto("/signin");
  await page.getByTestId("test-signin-btn").click();
  await page.waitForURL(/dashboard/, { timeout: 10_000 });
}

// ── backend seeding helpers ───────────────────────────────────────────────────

export async function ingestAnalysis(
  request: APIRequestContext,
  ticker: string,
  verdict: string,
  extra: Record<string, unknown> = {}
) {
  return request.post(
    `${BACKEND}/jobs/ingest-analysis?x_job_secret=${JOB_SECRET}`,
    {
      data: {
        ticker,
        analysis_date: new Date().toISOString().split("T")[0],
        verdict,
        current_price: 150.0,
        day_change_pct: 1.5,
        rsi: 45.0,
        reasoning: "E2E test analysis.",
        conviction_score: 72,
        risk_level: "MED",
        confidence: "High",
        signal_convergence_score: 5,
        entry_quality: "FAIR",
        hold_and_forget_rating: "CHECK_MONTHLY",
        position_size_pct: "5-8%",
        bull_case: "Earnings beat drives re-rating.",
        bear_case: "Macro headwinds compress margins.",
        thesis_invalidation: "Guidance cut by more than 10%.",
        news_summary: "Recent news is broadly positive.",
        ...extra,
      },
    }
  );
}

export async function ingestSnapshot(
  request: APIRequestContext,
  ticker: string
) {
  return request.post(
    `${BACKEND}/jobs/ingest-snapshot?x_job_secret=${JOB_SECRET}`,
    {
      data: {
        ticker,
        cache_date: new Date().toISOString().split("T")[0],
        info_json: JSON.stringify({ currentPrice: 150.0 }),
        history_json: "[]",
        news_json: "[]",
        calendar_json: "{}",
      },
    }
  );
}

export async function getAnalyzedToday(request: APIRequestContext): Promise<string[]> {
  const r = await request.get(
    `${BACKEND}/jobs/admin/analyzed-today?x_admin_secret=${ADMIN_SECRET}`
  );
  if (!r.ok()) return [];
  const body = await r.json();
  return body.analyzed ?? [];
}

// ── custom fixtures ───────────────────────────────────────────────────────────

type Fixtures = {
  testEmail: string;
  jobSecret: string;
  adminSecret: string;
  backend: string;
  loggedInPage: Page;
};

export const test = base.extend<Fixtures>({
  testEmail:   async ({}, use) => use(TEST_EMAIL),
  jobSecret:   async ({}, use) => use(JOB_SECRET),
  adminSecret: async ({}, use) => use(ADMIN_SECRET),
  backend:     async ({}, use) => use(BACKEND),

  loggedInPage: async ({ page }, use) => {
    await loginAsTestUser(page);
    await use(page);
  },
});

export { expect };
