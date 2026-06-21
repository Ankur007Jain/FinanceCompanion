// Tests for dashboard helper functions extracted from DashboardClient.tsx

function pct(v: number): string {
  return (v * 100).toFixed(1) + "%";
}

function fmtCap(v: number): string {
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9)  return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6)  return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + v.toLocaleString();
}

describe("pct()", () => {
  it("formats positive decimal as percentage", () => {
    expect(pct(0.12)).toBe("12.0%");
  });

  it("formats negative decimal as percentage", () => {
    expect(pct(-0.05)).toBe("-5.0%");
  });

  it("formats zero", () => {
    expect(pct(0)).toBe("0.0%");
  });

  it("rounds to one decimal", () => {
    expect(pct(0.1234)).toBe("12.3%");
  });

  it("formats 100% growth", () => {
    expect(pct(1.0)).toBe("100.0%");
  });

  it("formats small values like dividend yield", () => {
    expect(pct(0.008)).toBe("0.8%");
  });
});

describe("fmtCap()", () => {
  it("formats trillions", () => {
    expect(fmtCap(3_000_000_000_000)).toBe("$3.0T");
  });

  it("formats partial trillions", () => {
    expect(fmtCap(1_500_000_000_000)).toBe("$1.5T");
  });

  it("formats billions", () => {
    expect(fmtCap(500_000_000_000)).toBe("$500.0B");
  });

  it("formats sub-billion billions", () => {
    expect(fmtCap(2_300_000_000)).toBe("$2.3B");
  });

  it("formats millions", () => {
    expect(fmtCap(750_000_000)).toBe("$750.0M");
  });

  it("formats small millions", () => {
    expect(fmtCap(5_000_000)).toBe("$5.0M");
  });

  it("does not use T/B/M for values under 1M", () => {
    const result = fmtCap(500_000);
    expect(result).toMatch(/^\$/);
    expect(result).not.toMatch(/[TBM]$/);
  });
});

describe("VERDICT_META", () => {
  const VERDICT_META: Record<string, { color: string; bg: string; label: string }> = {
    BUY:   { color: "#22c55e", bg: "rgba(34,197,94,0.12)",  label: "BUY"   },
    HOLD:  { color: "#f59e0b", bg: "rgba(245,158,11,0.12)", label: "HOLD"  },
    SELL:  { color: "#ef4444", bg: "rgba(239,68,68,0.12)",  label: "SELL"  },
    WATCH: { color: "#94a3b8", bg: "rgba(148,163,184,0.1)", label: "WATCH" },
  };

  it("has all four valid verdicts", () => {
    expect(Object.keys(VERDICT_META)).toEqual(["BUY", "HOLD", "SELL", "WATCH"]);
  });

  it("BUY is green", () => {
    expect(VERDICT_META.BUY.color).toBe("#22c55e");
  });

  it("SELL is red", () => {
    expect(VERDICT_META.SELL.color).toBe("#ef4444");
  });

  it("HOLD is amber", () => {
    expect(VERDICT_META.HOLD.color).toBe("#f59e0b");
  });

  it("WATCH is muted grey", () => {
    expect(VERDICT_META.WATCH.color).toBe("#94a3b8");
  });

  it("unknown verdict returns undefined", () => {
    expect(VERDICT_META["MAYBE"]).toBeUndefined();
  });
});

describe("52-week range position", () => {
  const position = (price: number, low: number, high: number) =>
    ((price - low) / (high - low)) * 100;

  it("at 52w low = 0%", () => {
    expect(position(75, 75, 134)).toBeCloseTo(0, 0);
  });

  it("at 52w high = 100%", () => {
    expect(position(134, 75, 134)).toBeCloseTo(100, 0);
  });

  it("midpoint = 50%", () => {
    expect(position(104.5, 75, 134)).toBeCloseTo(50, 0);
  });

  it("below low gives negative (clamped in UI)", () => {
    expect(position(50, 75, 134)).toBeLessThan(0);
  });
});

describe("RSI classification", () => {
  const classify = (rsi: number) =>
    rsi >= 70 ? "Overbought" : rsi <= 30 ? "Oversold" : "Neutral";

  it("70+ is overbought", () => {
    expect(classify(70)).toBe("Overbought");
    expect(classify(85)).toBe("Overbought");
  });

  it("30 and below is oversold", () => {
    expect(classify(30)).toBe("Oversold");
    expect(classify(15)).toBe("Oversold");
  });

  it("31-69 is neutral", () => {
    expect(classify(50)).toBe("Neutral");
    expect(classify(31)).toBe("Neutral");
    expect(classify(69)).toBe("Neutral");
  });
});
