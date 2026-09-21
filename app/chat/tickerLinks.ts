export const TICKER_HREF_PREFIX = "#ticker:";

// Symbols that are also ordinary words/terms in an answer ("MA" as in moving average,
// "NOW" as in right now). Linked only when the model bolds them or writes $SYMBOL, the
// way it formats a ticker it means — otherwise a stray "NOW" would open ServiceNow's card.
const AMBIGUOUS = new Set(["A", "I", "T", "MA", "NOW", "ALL", "IT", "ON", "ARE", "SO", "BE", "GO", "CAN", "FOR", "HAS", "ONE", "SEE", "NEW", "AI", "PE", "EPS", "RSI"]);

type MdNode = { type: string; value?: string; url?: string; children?: MdNode[] };

const SKIP_TYPES = new Set(["link", "linkReference", "inlineCode", "code", "definition", "html"]);

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function buildTickerRegex(known: Set<string>): RegExp | null {
  if (known.size === 0) return null;
  const alt = [...known].sort((a, b) => b.length - a.length).map(escapeRe).join("|");
  return new RegExp(`(?<![A-Za-z0-9])(${alt})(?![A-Za-z0-9])`, "g");
}

function splitText(value: string, re: RegExp, inStrong: boolean): MdNode[] | null {
  re.lastIndex = 0;
  const out: MdNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(value)) !== null) {
    const t = m[1];
    const explicit = inStrong || value[m.index - 1] === "$";
    if (AMBIGUOUS.has(t) && !explicit) continue;
    if (m.index > last) out.push({ type: "text", value: value.slice(last, m.index) });
    out.push({ type: "link", url: TICKER_HREF_PREFIX + t, children: [{ type: "text", value: t }] });
    last = m.index + t.length;
  }
  if (out.length === 0) return null;
  if (last < value.length) out.push({ type: "text", value: value.slice(last) });
  return out;
}

function walk(node: MdNode, re: RegExp, inStrong: boolean) {
  if (!node.children || SKIP_TYPES.has(node.type)) return;
  const strong = inStrong || node.type === "strong";
  const next: MdNode[] = [];
  for (const child of node.children) {
    if (child.type === "text" && child.value) {
      next.push(...(splitText(child.value, re, strong) ?? [child]));
    } else {
      walk(child, re, strong);
      next.push(child);
    }
  }
  node.children = next;
}

// remark plugin: turns mentions of tickers the user actually tracks into links whose
// href is "#ticker:SYMBOL" — the chat renders those as buttons that open that ticker's card.
export function remarkTickerLinks(known: Set<string>) {
  const re = buildTickerRegex(known);
  return () => (tree: MdNode) => {
    if (re) walk(tree, re, false);
  };
}

export function tickerFromHref(href?: string): string | null {
  return href && href.startsWith(TICKER_HREF_PREFIX) ? href.slice(TICKER_HREF_PREFIX.length) : null;
}
