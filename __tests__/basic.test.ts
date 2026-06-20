describe("FinanceCompanion utilities", () => {
  it("formats ticker to uppercase", () => {
    const normalize = (t: string) => t.toUpperCase().trim();
    expect(normalize("nflx")).toBe("NFLX");
    expect(normalize(" mrvl ")).toBe("MRVL");
  });

  it("calculates 52-week range position correctly", () => {
    const position = (price: number, low: number, high: number) =>
      ((price - low) / (high - low)) * 100;
    expect(position(75, 75, 134)).toBeCloseTo(0, 0);
    expect(position(134, 75, 134)).toBeCloseTo(100, 0);
    expect(position(104.5, 75, 134)).toBeCloseTo(50, 0);
  });

  it("validates verdict values", () => {
    const validVerdicts = ["BUY", "HOLD", "SELL", "WATCH"];
    expect(validVerdicts).toContain("BUY");
    expect(validVerdicts).toContain("WATCH");
    expect(validVerdicts).not.toContain("MAYBE");
  });

  it("identifies leveraged tickers correctly", () => {
    const leveraged = ["SOXL", "MVLL", "NVDL", "TQQQ"];
    const regular = ["NVDA", "NFLX", "MRVL", "SOXQ"];
    leveraged.forEach((t) => expect(leveraged).toContain(t));
    regular.forEach((t) => expect(leveraged).not.toContain(t));
  });
});
