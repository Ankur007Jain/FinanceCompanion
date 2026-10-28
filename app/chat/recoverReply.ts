export type ServerMessage = { role: string; content: string; created_at?: string };

/**
 * After a reply stream ends without the server's "done" event — a phone dropping the
 * connection, a proxy cutting it, the 30s watchdog, or a 409 because the previous reply is
 * still being written — the backend usually still finishes and saves that reply. Poll the
 * conversation until a new assistant message lands, so the user sees the saved reply instead
 * of a blank bubble. The blank bubble is what led to a "Continue" that got the whole question
 * answered a second time (#164).
 */
export async function waitForSavedReply(
  fetchMessages: () => Promise<ServerMessage[] | null>,
  assistantCountBefore: number,
  {
    intervalMs = 3000,
    attempts = 30,
    sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms)),
    isCancelled = () => false,
  }: { intervalMs?: number; attempts?: number; sleep?: (ms: number) => Promise<void>; isCancelled?: () => boolean } = {},
): Promise<ServerMessage[] | null> {
  for (let i = 0; i < attempts && !isCancelled(); i++) {
    const msgs = await fetchMessages().catch(() => null);
    if (
      msgs?.length &&
      msgs[msgs.length - 1].role === "assistant" &&
      msgs.filter(m => m.role === "assistant").length > assistantCountBefore
    ) {
      return msgs;
    }
    await sleep(intervalMs);
  }
  return null;
}
