/**
 * E2E (#164): a reply stream that ends without the server's "done" event — a phone dropping
 * the connection — used to leave a blank bubble. The user typed "Continue", and the backend,
 * which had kept going and saved the first reply, answered the whole question a second time.
 * Now the chat fetches the saved reply instead; and a message sent while the previous reply
 * is still being written (409) is handed back for resending rather than duplicated.
 * Requires AUTH_TEST_MODE=true (frontend) and TEST_MODE=true (backend).
 */
import type { Page } from "@playwright/test";
import { test, expect } from "./fixtures";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8001";
const TEST_EMAIL = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";
const TOK = encodeURIComponent(`test-token-${TEST_EMAIL}`);
const RUN = Date.now().toString(36);

async function login(page: Page) {
  await page.goto("/signin");
  const btn = page.getByTestId("test-signin-btn");
  if (!(await btn.isVisible().catch(() => false))) test.skip(true, "AUTH_TEST_MODE not enabled");
  await btn.click();
  await page.waitForURL(/dashboard/, { timeout: 10_000 });
}

const mkConv = async (request: import("@playwright/test").APIRequestContext, title: string) =>
  (await (await request.post(`${BACKEND}/conversations?id_token=${TOK}`, { data: { title } })).json()).id as string;

/** Serves the conversation's saved messages: `before` until the stream request has been
 *  answered, `after` from then on — i.e. what the backend has persisted at each point. */
async function serveMessages(page: Page, convId: string, before: object[], after: object[], streamDone: () => boolean) {
  await page.route(`**/conversations/${convId}/messages?*`, route =>
    route.request().method() === "GET" ? route.fulfill({ json: streamDone() ? after : before }) : route.fallback());
}

test("a dropped reply stream shows the saved reply instead of a blank bubble", async ({ page, request }) => {
  const convId = await mkConv(request, `dropped ${RUN}`);
  const question = "What is EVH's real business?";
  const reply = "Evolent manages specialty care for health plans — oncology and cardiology first.";
  let answered = false;
  await login(page);
  await serveMessages(page, convId, [], [
    { id: "u1", role: "user", content: question, created_at: new Date().toISOString() },
    { id: "a1", role: "assistant", content: reply, created_at: new Date().toISOString() },
  ], () => answered);
  await page.route(`**/conversations/${convId}/messages/stream`, async route => {
    answered = true;
    // one chunk, then the connection ends — no "done" event
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: `data: ${JSON.stringify({ type: "chunk", text: "Let me dig" })}\n\n` });
  });

  await page.goto(`/chat?conv=${convId}`);
  await page.getByPlaceholder(/Ask about your stocks/).fill(question);
  await page.getByPlaceholder(/Ask about your stocks/).press("Enter");

  await expect(page.getByText(reply)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/^Error:/)).toHaveCount(0);
  await expect(page.getByText(/Connection dropped/)).toHaveCount(0);
  await expect(page.getByPlaceholder(/Ask about your stocks/)).toBeEnabled();
});

test("a message sent while the previous reply is still being written is handed back, not duplicated", async ({ page, request }) => {
  const convId = await mkConv(request, `inflight ${RUN}`);
  const previousQ = "Is VNQ rate sensitive?";
  const previousA = "Yes — REITs like VNQ move inversely to the 10-year yield.";
  let rejected = false;
  await login(page);
  await serveMessages(page, convId,
    [{ id: "u0", role: "user", content: previousQ, created_at: new Date().toISOString() }],
    [{ id: "u0", role: "user", content: previousQ, created_at: new Date().toISOString() },
     { id: "a0", role: "assistant", content: previousA, created_at: new Date().toISOString() }],
    () => rejected);
  await page.route(`**/conversations/${convId}/messages/stream`, async route => {
    rejected = true;
    await route.fulfill({ status: 409, json: { detail: "Still writing the previous answer in this chat — it'll appear in a moment." } });
  });

  await page.goto(`/chat?conv=${convId}`);
  await expect(page.getByText(previousQ)).toBeVisible();
  await page.getByPlaceholder(/Ask about your stocks/).fill("Continue");
  await page.getByPlaceholder(/Ask about your stocks/).press("Enter");

  await expect(page.getByText(previousA)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByPlaceholder(/Ask about your stocks/)).toHaveValue("Continue");
  await expect(page.getByText(/^Error:/)).toHaveCount(0);
});
