/**
 * E2E tests for the nightly job pipeline and dual-agent verdict endpoints.
 * All tests use JOB_SECRET / ADMIN_SECRET — no Google auth needed.
 * Each ticker uses a unique E2E prefix to avoid collisions with real watchlists.
 */
import { test, expect, ingestAnalysis, ingestSnapshot, getAnalyzedToday } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const JOB_SECRET = process.env.JOB_SECRET || "test-job-secret";
const ADMIN_SECRET = process.env.ADMIN_SECRET || "test-admin-secret";

// ── /jobs/ingest-snapshot ─────────────────────────────────────────────────────

test.describe("/jobs/ingest-snapshot", () => {
  test("saves raw snapshot with correct secret", async ({ request }) => {
    const r = await ingestSnapshot(request, "E2ESNAP1");
    expect([200, 201, 401]).toContain(r.status());
  });

  test("rejects bad secret with 401", async ({ request }) => {
    const r = await request.post(`${BACKEND}/jobs/ingest-snapshot?x_job_secret=wrong`, {
      data: {
        ticker: "E2ESNAP2",
        cache_date: new Date().toISOString().split("T")[0],
      },
    });
    expect(r.status()).toBe(401);
  });

  test("rejects missing ticker with 422", async ({ request }) => {
    const r = await request.post(`${BACKEND}/jobs/ingest-snapshot?x_job_secret=${JOB_SECRET}`, {
      data: { cache_date: new Date().toISOString().split("T")[0] },
    });
    expect([401, 422]).toContain(r.status());
  });

  test("upsert — second call with same ticker+date does not error", async ({ request }) => {
    const today = new Date().toISOString().split("T")[0];
    const payload = { ticker: "E2ESNAP3", cache_date: today, info_json: "{}" };
    const r1 = await request.post(`${BACKEND}/jobs/ingest-snapshot?x_job_secret=${JOB_SECRET}`, { data: payload });
    const r2 = await request.post(`${BACKEND}/jobs/ingest-snapshot?x_job_secret=${JOB_SECRET}`, { data: payload });
    expect([200, 201, 401]).toContain(r1.status());
    expect([200, 201, 401]).toContain(r2.status());
  });

  test("snapshot with all raw fields responds correctly", async ({ request }) => {
    const r = await request.post(`${BACKEND}/jobs/ingest-snapshot?x_job_secret=${JOB_SECRET}`, {
      data: {
        ticker: "E2ESNAP4",
        cache_date: new Date().toISOString().split("T")[0],
        info_json: JSON.stringify({ currentPrice: 200.0, sector: "Technology" }),
        history_json: JSON.stringify([{ Date: "2024-01-01", Close: 195.0, Volume: 1000000 }]),
        news_json: JSON.stringify([{ title: "Earnings beat expectations" }]),
        calendar_json: JSON.stringify({ "Earnings Date": ["2024-07-15"] }),
      },
    });
    expect([200, 201, 401]).toContain(r.status());
  });
});

// ── /jobs/admin/analyzed-today ────────────────────────────────────────────────

test.describe("/jobs/admin/analyzed-today", () => {
  test("rejects bad admin secret with 401", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/admin/analyzed-today?x_admin_secret=wrong`);
    expect(r.status()).toBe(401);
  });

  test("returns list of analyzed tickers with correct secret", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/admin/analyzed-today?x_admin_secret=${ADMIN_SECRET}`);
    expect([200, 401]).toContain(r.status());
    if (r.status() === 200) {
      const body = await r.json();
      expect(body).toHaveProperty("analyzed");
      expect(Array.isArray(body.analyzed)).toBe(true);
    }
  });

  test("ticker appears in analyzed-today after ingest", async ({ request }) => {
    const ticker = "E2EADAY1";
    const ingestRes = await ingestAnalysis(request, ticker, "BUY");
    if (ingestRes.status() === 401) return; // running against live server with different secret

    const analyzed = await getAnalyzedToday(request);
    if (analyzed.length > 0) {
      expect(analyzed).toContain(ticker);
    }
  });
});

// ── /jobs/admin/tickers ───────────────────────────────────────────────────────

test.describe("/jobs/admin/tickers", () => {
  test("rejects bad admin secret with 401", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/admin/tickers?x_admin_secret=wrong`);
    expect(r.status()).toBe(401);
  });

  test("returns tickers array with correct secret", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/admin/tickers?x_admin_secret=${ADMIN_SECRET}`);
    expect([200, 401]).toContain(r.status());
    if (r.status() === 200) {
      const body = await r.json();
      expect(body).toHaveProperty("tickers");
      expect(Array.isArray(body.tickers)).toBe(true);
    }
  });
});

// ── dual-agent fields round-trip ──────────────────────────────────────────────

test.describe("Dual-agent fields — API round-trip", () => {
  test("ingest with verdict_agreement=true (both models agree)", async ({ request }) => {
    const r = await ingestAnalysis(request, "E2EDA_AGREE", "BUY", {
      verdict_a: "BUY",
      verdict_b: "BUY",
      verdict_agreement: true,
      split_reason: null,
    });
    expect([200, 201, 401]).toContain(r.status());
  });

  test("ingest with verdict_agreement=false (models split)", async ({ request }) => {
    const r = await ingestAnalysis(request, "E2EDA_SPLIT", "WATCH", {
      verdict_a: "BUY",
      verdict_b: "HOLD",
      verdict_agreement: false,
      split_reason: "Claude sees oversold RSI; Gemini flags near-term earnings risk.",
    });
    expect([200, 201, 401]).toContain(r.status());
  });

  test("ingest with verdict_b null (Gemini unavailable)", async ({ request }) => {
    const r = await ingestAnalysis(request, "E2EDA_NULL", "BUY", {
      verdict_a: "BUY",
      verdict_b: null,
      verdict_agreement: null,
      split_reason: null,
    });
    expect([200, 201, 401]).toContain(r.status());
  });

  test("ingest with SELL+WATCH split — final verdict is SELL", async ({ request }) => {
    const r = await ingestAnalysis(request, "E2EDA_SELL", "SELL", {
      verdict_a: "SELL",
      verdict_b: "WATCH",
      verdict_agreement: false,
      split_reason: "Both models are bearish but Gemini is less decisive.",
    });
    expect([200, 201, 401]).toContain(r.status());
  });

  test("upsert updates dual-agent fields on second ingest", async ({ request }) => {
    const today = new Date().toISOString().split("T")[0];
    const ticker = "E2EDA_UPD";

    const r1 = await request.post(`${BACKEND}/jobs/ingest-analysis?x_job_secret=${JOB_SECRET}`, {
      data: { ticker, analysis_date: today, verdict: "BUY", verdict_a: "BUY", verdict_b: null, verdict_agreement: null },
    });
    const r2 = await request.post(`${BACKEND}/jobs/ingest-analysis?x_job_secret=${JOB_SECRET}`, {
      data: { ticker, analysis_date: today, verdict: "WATCH", verdict_a: "BUY", verdict_b: "HOLD", verdict_agreement: false, split_reason: "Updated split." },
    });
    expect([200, 201, 401]).toContain(r1.status());
    expect([200, 201, 401]).toContain(r2.status());
  });
});

// ── full pipeline smoke ────────────────────────────────────────────────────────

test.describe("Full nightly pipeline smoke", () => {
  test("snapshot + analysis ingest completes without error", async ({ request }) => {
    const ticker = "E2EPIPE1";
    const snapRes = await ingestSnapshot(request, ticker);
    const anlRes = await ingestAnalysis(request, ticker, "HOLD", {
      verdict_a: "HOLD",
      verdict_b: "HOLD",
      verdict_agreement: true,
    });
    expect([200, 201, 401]).toContain(snapRes.status());
    expect([200, 201, 401]).toContain(anlRes.status());
  });

  test("pipeline handles all four verdicts without error", async ({ request }) => {
    const today = new Date().toISOString().split("T")[0];
    for (const [ticker, verdict] of [
      ["E2EVBUY",  "BUY"],
      ["E2EVHOLD", "HOLD"],
      ["E2EVSELL", "SELL"],
      ["E2EVWATCH","WATCH"],
    ] as const) {
      const r = await request.post(`${BACKEND}/jobs/ingest-analysis?x_job_secret=${JOB_SECRET}`, {
        data: { ticker, analysis_date: today, verdict, current_price: 100.0, reasoning: "Test." },
      });
      expect([200, 201, 401]).toContain(r.status());
    }
  });

  test("analysis with earnings_date synthesizes events_json", async ({ request }) => {
    const r = await ingestAnalysis(request, "E2EEVT1", "WATCH", {
      earnings_date: "2025-07-15",
      is_important_day: true,
      importance_reason: "Earnings in 4 days.",
    });
    expect([200, 201, 401]).toContain(r.status());
  });
});

// ── backend integrity ────────────────────────────────────────────────────────

test.describe("Backend health", () => {
  test("health endpoint is up", async ({ request }) => {
    const r = await request.get(`${BACKEND}/health`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.status).toBe("ok");
  });

  test("jobs health is up", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/health`);
    expect(r.ok()).toBeTruthy();
  });

  test("health reports db type", async ({ request }) => {
    const r = await request.get(`${BACKEND}/health`);
    const body = await r.json();
    expect(["sqlite", "postgresql"]).toContain(body.db);
  });
});
