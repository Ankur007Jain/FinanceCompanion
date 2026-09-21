import { remarkTickerLinks, tickerFromHref } from "@/app/chat/tickerLinks";

type N = { type: string; value?: string; url?: string; children?: N[] };
const t = (value: string): N => ({ type: "text", value });
const run = (children: N[], known: string[]): N => {
  const tree: N = { type: "root", children: [{ type: "paragraph", children }] };
  remarkTickerLinks(new Set(known))()(tree);
  return tree.children![0];
};
const links = (p: N): string[] => {
  const out: string[] = [];
  const visit = (n: N) => { if (n.type === "link") out.push(n.url!); n.children?.forEach(visit); };
  visit(p);
  return out;
};

describe("remarkTickerLinks", () => {
  test("links tracked tickers in plain text and keeps surrounding text", () => {
    const p = run([t("META is SELL, AVGO is a HOLD.")], ["META", "AVGO"]);
    expect(links(p)).toEqual(["#ticker:META", "#ticker:AVGO"]);
    expect(p.children!.map(c => c.value ?? c.children![0].value).join("")).toBe("META is SELL, AVGO is a HOLD.");
  });

  test("does not link tickers the user doesn't track", () => {
    expect(links(run([t("NVDA and TSLA look fine")], ["META"]))).toEqual([]);
  });

  test("does not match inside longer words or alphanumerics (MA50, AVGOX, XAVGO)", () => {
    expect(links(run([t("MA50 AVGOX XAVGO")], ["MA", "AVGO"]))).toEqual([]);
  });

  test("ambiguous symbols only link when bolded or $-prefixed", () => {
    expect(links(run([t("price right NOW and above the MA")], ["NOW", "MA"]))).toEqual([]);
    expect(links(run([{ type: "strong", children: [t("NOW")] }], ["NOW"]))).toEqual(["#ticker:NOW"]);
    expect(links(run([t("watching $NOW closely")], ["NOW"]))).toEqual(["#ticker:NOW"]);
  });

  test("links inside bold and prefers the longest symbol", () => {
    const p = run([{ type: "strong", children: [t("BRK.B")] }, t(" and BRK")], ["BRK", "BRK.B"]);
    expect(links(p)).toEqual(["#ticker:BRK.B", "#ticker:BRK"]);
  });

  test("leaves existing links and code alone", () => {
    const p = run([
      { type: "link", url: "https://x.com/META", children: [t("META")] },
      { type: "inlineCode", value: "META" },
    ], ["META"]);
    expect(links(p)).toEqual(["https://x.com/META"]);
  });

  test("no tracked tickers is a no-op", () => {
    expect(links(run([t("META")], []))).toEqual([]);
  });

  test("tickerFromHref", () => {
    expect(tickerFromHref("#ticker:AVGO")).toBe("AVGO");
    expect(tickerFromHref("https://example.com")).toBeNull();
    expect(tickerFromHref(undefined)).toBeNull();
  });
});
