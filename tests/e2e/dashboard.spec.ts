import { test, expect } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";

// ── Backend API smoke ──────────────────────────────────────────────────────────

test.describe("Backend API", () => {
  test("health returns ok", async ({ request }) => {
    const r = await request.get(`${BACKEND}/health`);
    expect(r.ok()).toBeTruthy();
    expect((await r.json()).status).toBe("ok");
  });

  test("jobs health returns ok", async ({ request }) => {
    const r = await request.get(`${BACKEND}/jobs/health`);
    expect(r.ok()).toBeTruthy();
  });

  test("digest returns 401 for bad token", async ({ request }) => {
    const r = await request.get(`${BACKEND}/analysis/digest?id_token=badtoken`);
    expect(r.status()).toBe(401);
  });

  test("watchlist search returns 200 or 401", async ({ request }) => {
    const r = await request.get(`${BACKEND}/watchlist/search?q=AAPL&id_token=badtoken`);
    expect([200, 401]).toContain(r.status());
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

  test("simulation autopilot portfolio requires auth", async ({ request }) => {
    const r = await request.get(`${BACKEND}/simulation/autopilot/portfolio?id_token=bad`);
    expect(r.status()).toBe(401);
  });

  test("simulation copilot portfolio requires auth", async ({ request }) => {
    const r = await request.get(`${BACKEND}/simulation/copilot/portfolio?id_token=bad`);
    expect(r.status()).toBe(401);
  });

  test("simulation invalid mode returns 400", async ({ request }) => {
    const r = await request.get(`${BACKEND}/simulation/invalid/portfolio?id_token=bad`);
    expect([400, 401]).toContain(r.status());
  });
});

// ── Sign-in page ───────────────────────────────────────────────────────────────

test.describe("Sign-in page", () => {
  test("renders with branding", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByText("FinanceCompanion")).toBeVisible();
  });

  test("shows Google sign-in button", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByRole("button", { name: /sign in with google/i })).toBeVisible();
  });

  test("shows busy professionals tagline", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByText(/busy professionals/i)).toBeVisible();
  });

  test("Google button is enabled", async ({ page }) => {
    await page.goto("/signin");
    await expect(page.getByRole("button", { name: /sign in with google/i })).toBeEnabled();
  });

  test("responsive on mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/signin");
    await expect(page.getByText("FinanceCompanion")).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in with google/i })).toBeVisible();
  });

  test("responsive on tablet viewport", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/signin");
    await expect(page.getByRole("button", { name: /sign in with google/i })).toBeVisible();
  });
});

// ── Auth redirects ─────────────────────────────────────────────────────────────

test.describe("Auth redirects", () => {
  test("/ redirects to /signin", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/signin/);
  });

  test("/dashboard redirects to /signin", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/signin/);
  });

  test("/chat redirects to /signin", async ({ page }) => {
    await page.goto("/chat");
    await expect(page).toHaveURL(/signin/);
  });

  test("redirect lands on sign-in page with branding", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByText("FinanceCompanion")).toBeVisible();
  });
});

// ── Preview route (no-auth UI rendering) ──────────────────────────────────────

test.describe("Preview — layout & navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/preview");
  });

  test("Stock Copilot brand is visible in top bar", async ({ page }) => {
    await expect(page.getByText("Stock Copilot")).toBeVisible();
  });

  test("all 4 nav tabs are visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "My Stocks" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Discover" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Compare", exact: true })).toBeVisible();
  });

  test("VIRTUAL BALANCE label is visible", async ({ page }) => {
    await expect(page.getByText("VIRTUAL BALANCE")).toBeVisible();
  });

  test("user initials avatar is visible", async ({ page }) => {
    await expect(page.getByText("AJ")).toBeVisible();
  });

  test("Sign out button is visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: /sign out/i })).toBeVisible();
  });

  test("clicking My Stocks tab switches view", async ({ page }) => {
    await page.getByRole("button", { name: "My Stocks" }).click();
    await expect(page.getByPlaceholder(/search ticker/i)).toBeVisible();
  });

  test("clicking Discover tab switches view", async ({ page }) => {
    await page.getByRole("button", { name: "Discover" }).click();
    await expect(page.getByText(/discover/i).first()).toBeVisible();
  });

  test("clicking Compare tab switches view", async ({ page }) => {
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(page.getByText(/autopilot/i).first()).toBeVisible();
  });

  test("clicking Dashboard tab returns to dashboard view", async ({ page }) => {
    await page.getByRole("button", { name: "My Stocks" }).click();
    await page.getByRole("button", { name: "Dashboard" }).click();
    await expect(page.getByText("Stock Copilot")).toBeVisible();
  });

  test("logo click returns to dashboard", async ({ page }) => {
    await page.getByRole("button", { name: "My Stocks" }).click();
    await page.getByText("Stock Copilot").click();
    await expect(page.getByRole("button", { name: "Dashboard" })).toBeVisible();
  });
});

// ── Preview — Dashboard tab ────────────────────────────────────────────────────

test.describe("Preview — Dashboard tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/preview");
  });

  test("renders greeting with user name", async ({ page }) => {
    await expect(page.getByText(/ankur/i)).toBeVisible();
  });

  test("virtual balance shows dollar amount", async ({ page }) => {
    await expect(page.getByText(/\$[0-9,]+/).first()).toBeVisible();
  });

  test("autopilot section is visible", async ({ page }) => {
    await expect(page.getByText(/autopilot/i).first()).toBeVisible();
  });

  test("copilot section is visible", async ({ page }) => {
    await expect(page.getByText(/copilot/i).first()).toBeVisible();
  });
});

// ── Preview — My Stocks tab ────────────────────────────────────────────────────

test.describe("Preview — My Stocks tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/preview");
    await page.getByRole("button", { name: "My Stocks" }).click();
  });

  test("search input is visible", async ({ page }) => {
    await expect(page.getByPlaceholder(/search ticker/i)).toBeVisible();
  });

  test("add button is disabled when input is empty", async ({ page }) => {
    const btn = page.getByRole("button", { name: /add/i });
    await expect(btn).toBeDisabled();
  });

  test("add button becomes enabled when ticker is typed", async ({ page }) => {
    await page.getByPlaceholder(/search ticker/i).fill("AAPL");
    const btn = page.getByRole("button", { name: /add/i });
    await expect(btn).toBeEnabled();
  });

  test("typing shows suggestions dropdown (or stays clean)", async ({ page }) => {
    const input = page.getByPlaceholder(/search ticker/i);
    await input.fill("APP");
    // Suggestions may or may not load (API returns 401 in preview) — just check no crash
    await page.waitForTimeout(600);
    await expect(input).toBeVisible();
  });

  test("clearing input disables add button again", async ({ page }) => {
    const input = page.getByPlaceholder(/search ticker/i);
    await input.fill("AAPL");
    await input.clear();
    const btn = page.getByRole("button", { name: /add/i });
    await expect(btn).toBeDisabled();
  });

  test("empty state shown when no stocks in watchlist", async ({ page }) => {
    // API returns 401 in preview — digest is empty, so empty state should appear
    await expect(page.getByText(/no stocks|add your first|watchlist/i).first()).toBeVisible();
  });
});

// ── Preview — Discover tab ─────────────────────────────────────────────────────

test.describe("Preview — Discover tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/preview");
    await page.getByRole("button", { name: "Discover" }).click();
  });

  test("Discover heading is visible", async ({ page }) => {
    await expect(page.getByText(/discover/i).first()).toBeVisible();
  });

  test("page renders without crashing", async ({ page }) => {
    // Since digest is empty (401 in preview), verify page doesn't error
    await expect(page).not.toHaveURL(/error/);
    await expect(page.getByText("Stock Copilot")).toBeVisible();
  });
});

// ── Preview — Compare tab ──────────────────────────────────────────────────────

test.describe("Preview — Compare tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/preview");
    await page.getByRole("button", { name: "Compare", exact: true }).click();
  });

  test("Autopilot vs Copilot heading is visible", async ({ page }) => {
    await expect(page.getByText("Autopilot vs Copilot")).toBeVisible();
  });

  test("Autopilot label is visible", async ({ page }) => {
    await expect(page.getByText("Autopilot").first()).toBeVisible();
  });

  test("Copilot label is visible", async ({ page }) => {
    await expect(page.getByText("Copilot").first()).toBeVisible();
  });

  test("timeframe buttons are visible", async ({ page }) => {
    const buttons = page.getByRole("button");
    const labels = ["1M", "3M", "1Y", "All"];
    let found = false;
    for (const label of labels) {
      if (await buttons.filter({ hasText: label }).count() > 0) {
        found = true;
        break;
      }
    }
    expect(found).toBe(true);
  });

  test("chart SVG is rendered", async ({ page }) => {
    const svg = page.locator("svg").first();
    await expect(svg).toBeVisible();
  });

  test("page renders without crashing", async ({ page }) => {
    await expect(page).not.toHaveURL(/error/);
    await expect(page.getByText("Stock Copilot")).toBeVisible();
  });
});

// ── Page metadata ──────────────────────────────────────────────────────────────

test.describe("Page metadata", () => {
  test("sign-in page has correct title", async ({ page }) => {
    await page.goto("/signin");
    await expect(page).toHaveTitle(/Stock Copilot/i);
  });

  test("preview page has correct title", async ({ page }) => {
    await page.goto("/preview");
    await expect(page).toHaveTitle(/Stock Copilot/i);
  });
});
