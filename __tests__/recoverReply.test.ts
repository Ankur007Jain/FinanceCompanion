import { waitForSavedReply, ServerMessage } from "@/app/chat/recoverReply";

const noSleep = () => Promise.resolve();
const q: ServerMessage = { role: "user", content: "What is EVH's real business?" };
const earlier: ServerMessage[] = [{ role: "user", content: "hi" }, { role: "assistant", content: "Hey" }];

describe("waitForSavedReply", () => {
  it("returns the conversation once the dropped reply has been saved", async () => {
    const polls = [[...earlier, q], [...earlier, q], [...earlier, q, { role: "assistant", content: "Evolent manages specialty care…" }]];
    const fetchMessages = jest.fn(async () => polls.shift() ?? null);
    const saved = await waitForSavedReply(fetchMessages, 1, { sleep: noSleep });
    expect(saved?.at(-1)?.content).toBe("Evolent manages specialty care…");
    expect(fetchMessages).toHaveBeenCalledTimes(3);
  });

  it("ignores an older assistant message — only a new one counts", async () => {
    const fetchMessages = jest.fn(async () => [...earlier]);
    expect(await waitForSavedReply(fetchMessages, 1, { sleep: noSleep, attempts: 4 })).toBeNull();
    expect(fetchMessages).toHaveBeenCalledTimes(4);
  });

  it("keeps polling through failed fetches", async () => {
    let n = 0;
    const fetchMessages = jest.fn(async () => {
      n += 1;
      if (n < 3) throw new Error("offline");
      return [...earlier, q, { role: "assistant", content: "Back online" }];
    });
    expect((await waitForSavedReply(fetchMessages, 1, { sleep: noSleep }))?.at(-1)?.content).toBe("Back online");
  });

  it("stops when the user cancels", async () => {
    let cancelled = false;
    const fetchMessages = jest.fn(async () => { cancelled = true; return [...earlier, q]; });
    expect(await waitForSavedReply(fetchMessages, 1, { sleep: noSleep, isCancelled: () => cancelled })).toBeNull();
    expect(fetchMessages).toHaveBeenCalledTimes(1);
  });
});
