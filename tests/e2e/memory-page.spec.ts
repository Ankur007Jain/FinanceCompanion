import { test, expect } from "./fixtures";

test.describe("Memory settings page", () => {
  test("loads and moves past the loading state", async ({ loggedInPage: page }) => {
    await page.goto("/memory");
    // Must not still say "Loading…" after a real chance to resolve — this is
    // exactly the bug being verified: a thrown fetch/json() previously left
    // setLoading(false) never called, so the page hung on this text forever.
    await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 15_000 });
    // And it must have landed on a real state — either content or the empty-state
    // message — not silently blank.
    const hasHeading = await page.getByRole("heading", { name: "Memory" }).count();
    expect(hasHeading).toBeGreaterThan(0);
  });

  test("renders real seeded global and ticker-scoped learnings", async ({ loggedInPage: page }) => {
    await page.goto("/memory");
    await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 15_000 });
    await expect(page.getByText("E2E test global learning.")).toBeVisible();
    await expect(page.getByText("E2E test ticker-scoped learning.")).toBeVisible();
    await expect(page.getByText("ZE2E", { exact: true })).toBeVisible();
  });
});
