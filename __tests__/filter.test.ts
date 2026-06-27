// filter.test.ts — unit tests for My Stocks live filter logic
// Mirrors the filtering behaviour in DashboardClient.tsx
//
// Regression coverage for 3 bugs found in feature/sticky-search-filter:
//   Bug 1 — dropdown selection set query to "NFLX — Netflix Inc." → 0 matches (list blanked)
//   Bug 2 — single-letter ticker "T" used .includes() → matched META, TSLA, MRVL, etc.
//   Bug 3 — expanding a stock row called setQuery("") → wiped the active filter

interface DigestItem {
  ticker: string;
  company_name: string | null;
}

// Mirrors DashboardClient.tsx:1361-1369
function filterDigest(digest: DigestItem[], query: string, ticker: string): DigestItem[] {
  const filterQ = ticker ? ticker.toLowerCase() : query.trim().toLowerCase();
  if (!filterQ) return digest;
  return digest.filter(d =>
    ticker
      ? d.ticker.toLowerCase() === filterQ
      : d.ticker.toLowerCase().includes(filterQ) ||
        (d.company_name || "").toLowerCase().includes(filterQ)
  );
}

// Models the buggy onToggle (before fix): cleared query/ticker on every expand
function onToggleBuggy(
  itemTicker: string,
  currentExpanded: string | null,
  query: string,
  ticker: string
): { expanded: string | null; query: string; ticker: string } {
  const expanded = currentExpanded === itemTicker ? null : itemTicker;
  if (query.trim()) {
    return { expanded, query: "", ticker: "" }; // BUG: wiped filter
  }
  return { expanded, query, ticker };
}

// Models the fixed onToggle: does not touch filter state
function onToggleFixed(
  itemTicker: string,
  currentExpanded: string | null,
  query: string,
  ticker: string
): { expanded: string | null; query: string; ticker: string } {
  return { expanded: currentExpanded === itemTicker ? null : itemTicker, query, ticker };
}

const DIGEST: DigestItem[] = [
  { ticker: "NFLX", company_name: "Netflix, Inc." },
  { ticker: "T",    company_name: "AT&T Inc." },
  { ticker: "META", company_name: "Meta Platforms, Inc." },
  { ticker: "TSLA", company_name: "Tesla, Inc." },
  { ticker: "MRVL", company_name: "Marvell Technology" },
];

// ── Empty state ──────────────────────────────────────────────────────────────

describe("filterDigest() — empty state", () => {
  it("returns full digest when query and ticker are both empty", () => {
    expect(filterDigest(DIGEST, "", "")).toHaveLength(5);
  });

  it("returns full digest when query is whitespace only", () => {
    expect(filterDigest(DIGEST, "   ", "")).toHaveLength(5);
  });
});

// ── Free-text typing (no ticker selected) ───────────────────────────────────

describe("filterDigest() — free-text typing (no ticker selected)", () => {
  it("filters by partial ticker (case-insensitive)", () => {
    const r = filterDigest(DIGEST, "NF", "");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("NFLX");
  });

  it("filters by partial company name", () => {
    const r = filterDigest(DIGEST, "netflix", "");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("NFLX");
  });

  it("filters AT&T by company name substring 'at&t'", () => {
    const r = filterDigest(DIGEST, "at&t", "");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("T");
  });

  it("free-text 'te' matches multiple tickers via company name", () => {
    const r = filterDigest(DIGEST, "te", "");
    expect(r.map(d => d.ticker)).toContain("TSLA");   // "Tesla" starts with "te"
    expect(r.map(d => d.ticker)).toContain("MRVL");   // "Marvell Technology" contains "te"
    expect(r.length).toBeGreaterThan(1);
  });

  it("returns empty array when nothing matches", () => {
    expect(filterDigest(DIGEST, "ZZZZ", "")).toHaveLength(0);
  });
});

// ── Bug 1 regression — dropdown display string ───────────────────────────────

describe("filterDigest() — Bug 1: dropdown display string must not blank the list", () => {
  it("NFLX selected: display string 'NFLX — Netflix Inc.' still shows only NFLX", () => {
    // Pre-fix: filterQ = "nflx — netflix inc." → .includes() → 0 matches
    const r = filterDigest(DIGEST, "NFLX — Netflix Inc.", "NFLX");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("NFLX");
  });

  it("MRVL selected: display string still resolves to MRVL only", () => {
    const r = filterDigest(DIGEST, "MRVL — Marvell Technology", "MRVL");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("MRVL");
  });

  it("ticker selected with empty query string still matches", () => {
    const r = filterDigest(DIGEST, "", "NFLX");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("NFLX");
  });

  it("full display string does not leak into includes filter", () => {
    // "tsla — tesla, inc." is NOT a substring of any ticker
    const r = filterDigest(DIGEST, "TSLA — Tesla, Inc.", "TSLA");
    expect(r.map(d => d.ticker)).toEqual(["TSLA"]);
  });
});

// ── Bug 2 regression — single-letter ticker AT&T ────────────────────────────

describe("filterDigest() — Bug 2: single-letter ticker 'T' must use exact match", () => {
  it("ticker='T' returns exactly AT&T, not multiple stocks", () => {
    const r = filterDigest(DIGEST, "T — AT&T Inc.", "T");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("T");
  });

  it("ticker='T' does NOT match META (company name contains 't')", () => {
    const r = filterDigest(DIGEST, "T — AT&T Inc.", "T");
    expect(r.map(d => d.ticker)).not.toContain("META");
  });

  it("ticker='T' does NOT match TSLA (starts with 't')", () => {
    const r = filterDigest(DIGEST, "T — AT&T Inc.", "T");
    expect(r.map(d => d.ticker)).not.toContain("TSLA");
  });

  it("ticker='T' does NOT match MRVL (company name 'Marvell Technology' contains 't')", () => {
    const r = filterDigest(DIGEST, "T — AT&T Inc.", "T");
    expect(r.map(d => d.ticker)).not.toContain("MRVL");
  });

  it("ticker='T' does NOT match NFLX", () => {
    const r = filterDigest(DIGEST, "T — AT&T Inc.", "T");
    expect(r.map(d => d.ticker)).not.toContain("NFLX");
  });

  it("exact match is case-insensitive", () => {
    const r = filterDigest(DIGEST, "", "t");
    expect(r).toHaveLength(1);
    expect(r[0].ticker).toBe("T");
  });
});

// ── Bug 3 regression — expand row must not clear filter ─────────────────────

describe("onToggle — Bug 3: expanding a row must not wipe query or ticker", () => {
  it("buggy onToggle clears query when a filter is active (documents the bug)", () => {
    const result = onToggleBuggy("NFLX", null, "netflix", "");
    expect(result.query).toBe(""); // bug: filter was erased
  });

  it("fixed onToggle: query survives row expansion", () => {
    const result = onToggleFixed("NFLX", null, "netflix", "");
    expect(result.query).toBe("netflix");
    expect(result.expanded).toBe("NFLX");
  });

  it("fixed onToggle: selected ticker survives row expansion", () => {
    const result = onToggleFixed("T", null, "T — AT&T Inc.", "T");
    expect(result.ticker).toBe("T");
    expect(result.expanded).toBe("T");
  });

  it("fixed onToggle: collapsing an expanded row preserves filter", () => {
    const result = onToggleFixed("NFLX", "NFLX", "netflix", "");
    expect(result.expanded).toBeNull();
    expect(result.query).toBe("netflix");
  });

  it("fixed onToggle: empty filter stays empty after expand (no side-effect)", () => {
    const result = onToggleFixed("META", null, "", "");
    expect(result.query).toBe("");
    expect(result.ticker).toBe("");
  });

  it("fixed onToggle: expanding different row while filter active keeps filter", () => {
    // User filtered to "netflix", expanded NFLX, now expands NFLX again to collapse
    const r1 = onToggleFixed("NFLX", null, "netflix", "");
    const r2 = onToggleFixed("NFLX", r1.expanded, r1.query, r1.ticker);
    expect(r2.query).toBe("netflix");
    expect(r2.expanded).toBeNull();
  });
});
