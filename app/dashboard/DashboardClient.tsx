"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

const MONO = "'IBM Plex Mono', monospace";
const SANS = "'IBM Plex Sans', sans-serif";
const SERIF = "'IBM Plex Serif', serif";

interface Analysis {
  id: string;
  ticker: string;
  analysis_date: string;
  verdict: string;
  current_price: number | null;
  day_change_pct: number | null;
  week_52_high: number | null;
  week_52_low: number | null;
  range_position_pct: number | null;
  ma_50: number | null;
  ma_200: number | null;
  rsi: number | null;
  analyst_consensus: string | null;
  pe_trailing: number | null;
  pe_forward: number | null;
  revenue_growth: number | null;
  profit_margin: number | null;
  debt_to_equity: number | null;
  beta: number | null;
  short_float_pct: number | null;
  inst_ownership_pct: number | null;
  sp500_52w_change: number | null;
  stock_52w_change: number | null;
  dividend_yield: number | null;
  market_cap: number | null;
  sector: string | null;
  industry: string | null;
  entry_target: number | null;
  exit_target: number | null;
  stop_loss: number | null;
  hold_period: string | null;
  reasoning: string | null;
  conviction_score: number | null;
  risk_level: string | null;
  confidence: string | null;
  bull_case: string | null;
  bear_case: string | null;
  thesis_invalidation: string | null;
  news_summary: string | null;
  ripple_analysis: string | null;
  is_important_day: boolean;
  importance_reason: string | null;
  events_json: string | null;
  entry_quality: string | null;
  hold_and_forget_rating: string | null;
  position_size_pct: string | null;
  scenario_bull: string | null;
  scenario_base: string | null;
  scenario_bear: string | null;
  scenario_bull_pct: number | null;
  scenario_base_pct: number | null;
  scenario_bear_pct: number | null;
  scenario_bull_prob: number | null;
  scenario_base_prob: number | null;
  scenario_bear_prob: number | null;
  dont_panic_note: string | null;
  signal_convergence_score: number | null;
  convergence_details: string | null;
}

interface DigestItem {
  ticker: string;
  company_name: string | null;
  is_leveraged: boolean;
  analysis: Analysis | null;
}

const VERDICT_META: Record<string, { color: string; bg: string; bd: string; label: string }> = {
  BUY:   { color: "#3F6B4F", bg: "#EAF1EC", bd: "#D6E2D7", label: "BUY"   },
  HOLD:  { color: "#97703C", bg: "#F4EEE2", bd: "#E6DBC4", label: "HOLD"  },
  SELL:  { color: "#A8554A", bg: "#F4E7E4", bd: "#E6D2CC", label: "SELL"  },
  WATCH: { color: "#9C998E", bg: "#F4F2EC", bd: "#E4E1D8", label: "WATCH" },
};

function RangeBar({ lo, hi, pct }: { lo: number; hi: number; pct: number }) {
  const clamp = Math.max(0, Math.min(100, pct));
  const dotColor = clamp < 33 ? "#3F6B4F" : clamp < 67 ? "#97703C" : "#A8554A";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", minWidth: 130 }}>
      <div style={{ position: "relative", height: 5, background: "#E4E1D8", borderRadius: 99 }}>
        <div style={{
          position: "absolute", left: 0, width: `${clamp}%`, height: "100%",
          background: dotColor, borderRadius: 99, opacity: 0.3,
        }} />
        <div style={{
          position: "absolute", left: `${clamp}%`, top: "50%",
          transform: "translate(-50%, -50%)",
          width: 10, height: 10, borderRadius: "50%",
          background: dotColor, border: "2px solid #FBFAF7", zIndex: 1,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.67rem", color: "#9C998E", fontFamily: MONO }}>
        <span>${lo.toFixed(0)}</span>
        <span style={{ color: dotColor, fontWeight: 600 }}>{clamp.toFixed(0)}%</span>
        <span>${hi.toFixed(0)}</span>
      </div>
    </div>
  );
}

function RsiPill({ rsi }: { rsi: number }) {
  const color = rsi >= 70 ? "#A8554A" : rsi <= 30 ? "#3F6B4F" : "#9C998E";
  const label = rsi >= 70 ? "OB" : rsi <= 30 ? "OS" : "";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
      <span style={{ fontWeight: 600, fontSize: "0.95rem", color, fontFamily: MONO }}>{rsi.toFixed(0)}</span>
      {label && <span style={{ fontSize: "0.62rem", color, fontWeight: 600, letterSpacing: "0.05em", fontFamily: MONO }}>{label}</span>}
    </div>
  );
}

function MaBadge({ price, ma50, ma200 }: { price: number; ma50: number | null; ma200: number | null }) {
  const above50  = ma50  ? price > ma50  : null;
  const above200 = ma200 ? price > ma200 : null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
      {ma50 != null && (
        <span style={{ fontSize: "0.68rem", color: above50 ? "#3F6B4F" : "#A8554A", fontFamily: MONO }}>
          {above50 ? "▲" : "▼"} MA50
        </span>
      )}
      {ma200 != null && (
        <span style={{ fontSize: "0.68rem", color: above200 ? "#3F6B4F" : "#A8554A", fontFamily: MONO }}>
          {above200 ? "▲" : "▼"} MA200
        </span>
      )}
    </div>
  );
}

function ExpandedDetail({ a, onChat }: { a: Analysis; onChat: () => void }) {
  let events: Array<{ date: string; description: string }> = [];
  try { if (a.events_json) events = JSON.parse(a.events_json).slice(0, 3); } catch {}

  const secLabel: React.CSSProperties = {
    fontSize: "0.7rem", color: "#9C998E", fontWeight: 600,
    letterSpacing: "0.09em", textTransform: "uppercase",
    marginBottom: "0.5rem", fontFamily: MONO,
  };

  const signals = [
    { label: "Price & RSI",     ok: a.rsi != null || a.current_price != null },
    { label: "Analyst Ratings", ok: a.analyst_consensus != null },
    { label: "News Sentiment",  ok: a.news_summary != null },
    { label: "Events Calendar", ok: events.length > 0 },
    { label: "Ripple Effects",  ok: a.ripple_analysis != null },
    { label: "Cross-Validated", ok: a.analyst_consensus != null && a.current_price != null },
  ];

  const EQ_META: Record<string, { label: string; color: string; bg: string; bd: string }> = {
    GREAT: { label: "Great Entry",       color: "#3F6B4F", bg: "#EAF1EC", bd: "#C8DDD0" },
    FAIR:  { label: "Fair Entry",        color: "#97703C", bg: "#F4EEE2", bd: "#E6DBC4" },
    WAIT:  { label: "Wait for Pullback", color: "#A8554A", bg: "#F4E7E4", bd: "#E6D2CC" },
  };
  const HF_META: Record<string, { label: string; color: string; bg: string; bd: string }> = {
    HOLD_AND_FORGET: { label: "Hold & Forget ✓", color: "#3F6B4F", bg: "#EAF1EC", bd: "#C8DDD0" },
    CHECK_MONTHLY:   { label: "Check Monthly",   color: "#97703C", bg: "#F4EEE2", bd: "#E6DBC4" },
    WATCH_CLOSELY:   { label: "Watch Closely",   color: "#A8554A", bg: "#F4E7E4", bd: "#E6D2CC" },
  };

  const eqMeta  = a.entry_quality         ? EQ_META[a.entry_quality]                : null;
  const hfMeta  = a.hold_and_forget_rating ? HF_META[a.hold_and_forget_rating]       : null;
  const hasScenarios = a.scenario_bull_prob != null && a.scenario_base_prob != null && a.scenario_bear_prob != null;

  return (
    <div style={{ borderTop: "1px solid #E4E1D8", background: "#F6F4EE", borderRadius: "0 0 11px 11px" }}>

      {/* ── Signal checklist strip ── */}
      <div style={{ padding: "10px 20px", borderBottom: "1px solid #EDEAE1", display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px 8px" }}>
        <span style={{ fontSize: "0.65rem", color: "#9C998E", fontFamily: MONO, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", marginRight: 4, flexShrink: 0 }}>Analyzed</span>
        {signals.map(s => (
          <span key={s.label} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: "0.7rem", fontFamily: MONO, padding: "2px 9px", borderRadius: 20, color: s.ok ? "#3F6B4F" : "#B0ADA6", background: s.ok ? "#EAF1EC" : "#EDEAE1", border: `1px solid ${s.ok ? "#C8DDD0" : "#E4E1D8"}` }}>
            <span style={{ fontSize: "0.65rem" }}>{s.ok ? "✓" : "—"}</span>{s.label}
          </span>
        ))}
      </div>

      {/* ── Trust badges: Entry Quality · Hold & Forget · Position Size ── */}
      {(eqMeta || hfMeta || a.position_size_pct) && (
        <div style={{ padding: "12px 20px", borderBottom: "1px solid #EDEAE1", display: "flex", alignItems: "center", flexWrap: "wrap", gap: "8px 12px" }}>
          {eqMeta && (
            <span style={{ fontSize: "0.72rem", fontFamily: MONO, fontWeight: 700, padding: "4px 12px", borderRadius: 20, color: eqMeta.color, background: eqMeta.bg, border: `1px solid ${eqMeta.bd}` }}>
              Entry: {eqMeta.label}
            </span>
          )}
          {hfMeta && (
            <span style={{ fontSize: "0.72rem", fontFamily: MONO, fontWeight: 700, padding: "4px 12px", borderRadius: 20, color: hfMeta.color, background: hfMeta.bg, border: `1px solid ${hfMeta.bd}` }}>
              {hfMeta.label}
            </span>
          )}
          {a.position_size_pct && (
            <span style={{ fontSize: "0.72rem", fontFamily: MONO, padding: "4px 12px", borderRadius: 20, color: "#3A5A6E", background: "#E8EFF4", border: "1px solid #C8D8E4" }}>
              Suggested: <strong>{a.position_size_pct}</strong> of portfolio
            </span>
          )}
        </div>
      )}

      {/* ── Don't Panic note ── */}
      {a.dont_panic_note && (
        <div style={{ margin: "0 20px 0", padding: "12px 16px", background: "#FDF6EC", border: "1px solid #E6DBC4", borderRadius: 8, marginTop: 14, marginBottom: 4 }}>
          <div style={{ fontSize: "0.68rem", color: "#97703C", fontFamily: MONO, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 5 }}>Price Alert</div>
          <div style={{ fontSize: "0.8rem", lineHeight: 1.6, color: "#5A4420" }}>{a.dont_panic_note}</div>
        </div>
      )}

      {/* ── 90-Day Scenarios ── */}
      {hasScenarios && (
        <div style={{ padding: "14px 20px", borderBottom: "1px solid #EDEAE1" }}>
          <div style={{ ...secLabel, marginBottom: "0.75rem" }}>90-Day Scenarios</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
            {([
              { key: "bull", label: "Bull", pct: a.scenario_bull_pct, prob: a.scenario_bull_prob, text: a.scenario_bull, color: "#3F6B4F", bg: "#EAF1EC", bd: "#C8DDD0" },
              { key: "base", label: "Base", pct: a.scenario_base_pct, prob: a.scenario_base_prob, text: a.scenario_base, color: "#3A5A6E", bg: "#E8EFF4", bd: "#C8D8E4" },
              { key: "bear", label: "Bear", pct: a.scenario_bear_pct, prob: a.scenario_bear_prob, text: a.scenario_bear, color: "#A8554A", bg: "#F4E7E4", bd: "#E6D2CC" },
            ] as const).map(s => (
              <div key={s.key} style={{ background: s.bg, border: `1px solid ${s.bd}`, borderRadius: 8, padding: "10px 12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
                  <span style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 700, color: s.color, textTransform: "uppercase", letterSpacing: "0.06em" }}>{s.label}</span>
                  <span style={{ fontSize: "0.68rem", fontFamily: MONO, color: "#9C998E" }}>{s.prob}%</span>
                </div>
                <div style={{ fontSize: "1.05rem", fontWeight: 700, fontFamily: MONO, color: s.color, marginBottom: 5 }}>
                  {s.pct != null ? (s.pct >= 0 ? "+" : "") + s.pct.toFixed(1) + "%" : "—"}
                </div>
                {s.text && <div style={{ fontSize: "0.72rem", lineHeight: 1.5, color: "#3A3833" }}>{s.text}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Main 3-col grid ── */}
      <div style={{ padding: "1.25rem 1.5rem", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1.5rem" }}>

        {/* Conviction + bull/bear */}
        {(a.conviction_score != null || a.bull_case || a.bear_case) && (
          <div style={{ gridColumn: "1 / -1", display: "flex", gap: "1.5rem", alignItems: "flex-start", flexWrap: "wrap" }}>
            {a.conviction_score != null && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, minWidth: 90 }}>
                <span style={{ fontSize: "1.6rem", fontWeight: 600, fontFamily: MONO, color: a.conviction_score >= 70 ? "#3F6B4F" : a.conviction_score >= 50 ? "#97703C" : "#A8554A" }}>
                  {a.conviction_score}<span style={{ fontSize: "0.8rem", color: "#9C998E" }}>/100</span>
                </span>
                <span style={{ ...secLabel, marginBottom: 0 }}>Conviction</span>
                <div style={{ display: "flex", gap: 6 }}>
                  {a.risk_level && <span style={{ fontSize: "0.62rem", fontFamily: MONO, fontWeight: 600, padding: "2px 7px", borderRadius: 20, color: a.risk_level === "LOW" ? "#3F6B4F" : a.risk_level === "MED" ? "#97703C" : "#A8554A", background: a.risk_level === "LOW" ? "#EAF1EC" : a.risk_level === "MED" ? "#F4EEE2" : "#F4E7E4", border: `1px solid ${a.risk_level === "LOW" ? "#D6E2D7" : a.risk_level === "MED" ? "#E6DBC4" : "#E6D2CC"}` }}>{a.risk_level} RISK</span>}
                  {a.confidence && <span style={{ fontSize: "0.62rem", fontFamily: MONO, color: "#9C998E" }}>{a.confidence} conf.</span>}
                </div>
              </div>
            )}
            <div style={{ flex: 1, minWidth: 240, display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              {a.bull_case && (
                <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem", color: "#3A3833", lineHeight: 1.5 }}>
                  <span style={{ color: "#3F6B4F", fontWeight: 700, flexShrink: 0 }}>Bull</span><span>{a.bull_case}</span>
                </div>
              )}
              {a.bear_case && (
                <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem", color: "#3A3833", lineHeight: 1.5 }}>
                  <span style={{ color: "#A8554A", fontWeight: 700, flexShrink: 0 }}>Bear</span><span>{a.bear_case}</span>
                </div>
              )}
              {a.thesis_invalidation && (
                <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.78rem", color: "#6A685F", lineHeight: 1.5 }}>
                  <span style={{ color: "#9C998E", fontWeight: 600, flexShrink: 0, fontFamily: MONO, fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: "0.06em", paddingTop: 2 }}>Flips if</span>
                  <span>{a.thesis_invalidation}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Price Targets + Events */}
        <div>
          <div style={secLabel}>Price Targets</div>
          {(a.entry_target || a.exit_target || a.stop_loss || a.hold_period) ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap" }}>
                {a.entry_target && <div><div style={{ fontSize: "0.68rem", color: "#9C998E" }}>Entry</div><div style={{ fontWeight: 600, color: "#3F6B4F", fontSize: "1rem", fontFamily: MONO }}>${a.entry_target.toFixed(2)}</div></div>}
                {a.exit_target  && <div><div style={{ fontSize: "0.68rem", color: "#9C998E" }}>Take Profit</div><div style={{ fontWeight: 600, color: "#3A5A6E", fontSize: "1rem", fontFamily: MONO }}>${a.exit_target.toFixed(2)}</div></div>}
                {a.stop_loss    && <div><div style={{ fontSize: "0.68rem", color: "#9C998E" }}>Stop Loss</div><div style={{ fontWeight: 600, color: "#A8554A", fontSize: "1rem", fontFamily: MONO }}>${a.stop_loss.toFixed(2)}</div></div>}
              </div>
              {a.hold_period && (
                <div style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.25rem 0.65rem", background: "#ECEAE3", border: "1px solid #E4E1D8", borderRadius: 6, width: "fit-content" }}>
                  <span style={{ fontSize: "0.68rem", color: "#9C998E", fontFamily: MONO }}>Hold:</span>
                  <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#20211C" }}>{a.hold_period}</span>
                </div>
              )}
            </div>
          ) : (
            <div style={{ fontSize: "0.82rem", color: "#9C998E" }}>No price targets set</div>
          )}
          {events.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <div style={{ ...secLabel, marginTop: "0.5rem" }}>Upcoming Events</div>
              {events.map((e, i) => (
                <div key={i} style={{ fontSize: "0.78rem", color: "#97703C", marginBottom: "0.25rem", display: "flex", gap: "0.4rem" }}>
                  <span>⚡</span><span>{e.date} — {e.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Reasoning */}
        <div>
          <div style={secLabel}>AI Reasoning</div>
          <div style={{ fontSize: "0.8rem", lineHeight: 1.65, color: "#3A3833" }}>{a.reasoning ?? "—"}</div>
        </div>

        {/* News + Ripple + Chat */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {a.news_summary && (
            <div>
              <div style={secLabel}>News</div>
              <div style={{ fontSize: "0.78rem", lineHeight: 1.6, color: "#3A3833" }}>{a.news_summary}</div>
            </div>
          )}
          {a.ripple_analysis && (
            <div>
              <div style={secLabel}>Ripple Effects</div>
              <div style={{ fontSize: "0.78rem", lineHeight: 1.6, color: "#3A3833" }}>{a.ripple_analysis}</div>
            </div>
          )}
          <button onClick={onChat} style={{ marginTop: "auto", padding: "0.5rem 1rem", background: "#3A5A6E", color: "#FBFAF7", border: "none", borderRadius: 7, cursor: "pointer", fontWeight: 600, fontSize: "0.82rem", alignSelf: "flex-start", fontFamily: SANS }}>
            Ask AI about this →
          </button>
        </div>

        {/* Fundamentals */}
        {(a.pe_trailing || a.revenue_growth || a.profit_margin || a.beta || a.market_cap || a.sector) && (
          <div style={{ gridColumn: "1 / -1", borderTop: "1px solid #E4E1D8", paddingTop: "1rem" }}>
            <div style={secLabel}>Fundamentals</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "0.75rem 1.5rem" }}>
              {a.pe_trailing     != null && <FundStat label="P/E (TTM)"       value={a.pe_trailing.toFixed(1) + "x"} />}
              {a.pe_forward      != null && <FundStat label="P/E (Fwd)"       value={a.pe_forward.toFixed(1) + "x"} />}
              {a.revenue_growth  != null && <FundStat label="Revenue Growth"  value={pct(a.revenue_growth)}  color={a.revenue_growth  >= 0 ? "#3F6B4F" : "#A8554A"} />}
              {a.profit_margin   != null && <FundStat label="Net Margin"      value={pct(a.profit_margin)}   color={a.profit_margin   >= 0 ? "#3F6B4F" : "#A8554A"} />}
              {a.debt_to_equity  != null && <FundStat label="Debt / Equity"   value={a.debt_to_equity.toFixed(1)} />}
              {a.beta            != null && <FundStat label="Beta"            value={a.beta.toFixed(2)}       color={a.beta > 1.5 ? "#97703C" : undefined} />}
              {a.short_float_pct   != null && <FundStat label="Short Interest"  value={pct(a.short_float_pct)} color={a.short_float_pct > 0.2 ? "#A8554A" : undefined} />}
              {a.inst_ownership_pct != null && <FundStat label="Inst. Ownership" value={pct(a.inst_ownership_pct)} />}
              {(a.stock_52w_change != null || a.sp500_52w_change != null) && (
                <div>
                  <div style={{ fontSize: "0.65rem", color: "#9C998E", marginBottom: "0.2rem" }}>vs S&P 500 (52w)</div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "baseline" }}>
                    {a.stock_52w_change != null && <span style={{ fontWeight: 600, fontSize: "0.88rem", color: a.stock_52w_change >= 0 ? "#3F6B4F" : "#A8554A", fontFamily: MONO }}>{pct(a.stock_52w_change)}</span>}
                    {a.sp500_52w_change != null && <span style={{ fontSize: "0.72rem", color: "#9C998E" }}>/ {pct(a.sp500_52w_change)} S&P</span>}
                  </div>
                </div>
              )}
              {a.market_cap     != null && <FundStat label="Market Cap"    value={fmtCap(a.market_cap)} />}
              {a.dividend_yield != null && a.dividend_yield > 0 && <FundStat label="Dividend Yield" value={pct(a.dividend_yield)} color="#3F6B4F" />}
            </div>
            {(a.sector || a.industry) && (
              <div style={{ marginTop: "0.6rem", fontSize: "0.72rem", color: "#9C998E" }}>
                {[a.sector, a.industry].filter(Boolean).join(" · ")}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function FundStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: "0.65rem", color: "#9C998E", marginBottom: "0.2rem" }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: "0.88rem", color: color ?? "#20211C", fontFamily: MONO }}>{value}</div>
    </div>
  );
}

function pct(v: number) { return (v * 100).toFixed(1) + "%"; }

function fmtCap(v: number) {
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9)  return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6)  return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + v.toLocaleString();
}

function analysisAge(dateStr: string): string {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const d = new Date(dateStr + "T00:00:00"); d.setHours(0, 0, 0, 0);
  const days = Math.round((today.getTime() - d.getTime()) / 86400000);
  if (days <= 0) return "";
  if (days === 1) return "1d ago";
  if (days < 7) return `${days}d ago`;
  return "1w+ ago";
}

function VerdictBadge({ vm }: { vm: { color: string; bg: string; bd: string; label: string } }) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      padding: "0.3rem 0.7rem", background: vm.bg, color: vm.color,
      border: `1px solid ${vm.bd}`, borderRadius: 20,
      fontWeight: 700, fontSize: "0.75rem", letterSpacing: "0.06em",
      fontFamily: MONO, whiteSpace: "nowrap",
    }}>
      {vm.label}
    </div>
  );
}

function StockRow({
  item, expanded, onToggle, onChat, onRemove, isMobile,
}: {
  item: DigestItem; expanded: boolean; isMobile: boolean;
  onToggle: () => void; onChat: (ticker: string) => void; onRemove: (ticker: string) => void;
}) {
  const a = item.analysis;
  const vm = a?.verdict ? VERDICT_META[a.verdict] ?? VERDICT_META.WATCH : null;
  const chgColor = (a?.day_change_pct ?? 0) >= 0 ? "#3F6B4F" : "#A8554A";
  const age = a?.analysis_date ? analysisAge(a.analysis_date) : "";

  const upcomingEvent = (() => {
    try {
      if (!a?.events_json) return null;
      const evts = JSON.parse(a.events_json);
      return evts?.length ? evts[0].date : null;
    } catch { return null; }
  })();

  return (
    <div style={{
      background: "#FBFAF7",
      border: expanded ? "1px solid #3A5A6E" : "1px solid #E4E1D8",
      borderRadius: 11, overflow: "hidden", transition: "border-color 0.15s",
    }}>
      {isMobile ? (
        /* ── Mobile card layout ── */
        <div onClick={a ? onToggle : undefined} style={{ padding: "0.9rem 1rem", cursor: a ? "pointer" : "default" }}>
          {/* Row 1: Ticker + Verdict + Remove */}
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "0.5rem" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                <span style={{ fontWeight: 700, fontSize: "1rem", fontFamily: MONO, color: "#20211C" }}>{item.ticker}</span>
                {a?.is_important_day && <span title={a.importance_reason ?? ""} style={{ fontSize: "0.78rem" }}>⭐</span>}
                {item.is_leveraged && (
                  <span style={{ fontSize: "0.6rem", padding: "0.1rem 0.35rem", background: "#EAF0F3", color: "#3A5A6E", border: "1px solid #D7E1E8", borderRadius: 4, fontWeight: 700, fontFamily: MONO }}>3X</span>
                )}
                {age && (
                  <span style={{ fontSize: "0.6rem", padding: "0.1rem 0.35rem", background: "#EDE9DF", color: "#9C998E", borderRadius: 4, fontFamily: MONO }}>{age}</span>
                )}
              </div>
              {item.company_name && (
                <div style={{ fontSize: "0.72rem", color: "#9C998E", marginTop: "0.15rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.company_name}
                </div>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>
              {vm ? <VerdictBadge vm={vm} /> : <span style={{ fontSize: "0.78rem", color: "#9C998E" }}>Pending</span>}
              <button
                onClick={e => { e.stopPropagation(); onRemove(item.ticker); }}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#CBCAC2", fontSize: "0.82rem", padding: "0.2rem 0.3rem", lineHeight: 1 }}
              >✕</button>
            </div>
          </div>

          {/* Row 2: Price + change | RSI + Trend */}
          {a && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "0.6rem", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                {a.current_price != null && (
                  <>
                    <span style={{ fontWeight: 700, fontSize: "1.05rem", fontFamily: MONO, color: "#20211C" }}>${a.current_price.toFixed(2)}</span>
                    {a.day_change_pct != null && (
                      <span style={{ fontSize: "0.78rem", color: chgColor, fontWeight: 600, fontFamily: MONO }}>
                        {a.day_change_pct >= 0 ? "▲" : "▼"}{Math.abs(a.day_change_pct).toFixed(2)}%
                      </span>
                    )}
                  </>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                {a.rsi != null && <RsiPill rsi={a.rsi} />}
                {a.current_price != null && <MaBadge price={a.current_price} ma50={a.ma_50} ma200={a.ma_200} />}
              </div>
            </div>
          )}

          {/* Row 3: 52-week range + analyst + event */}
          {a && (
            <div style={{ marginTop: "0.55rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {a.week_52_low != null && a.week_52_high != null && a.range_position_pct != null && (
                <RangeBar lo={a.week_52_low} hi={a.week_52_high} pct={a.range_position_pct} />
              )}
              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                {a.analyst_consensus && (
                  <span style={{ fontSize: "0.7rem", color: "#9C998E" }}>
                    Analysts: <span style={{ color: "#20211C", fontWeight: 600 }}>{a.analyst_consensus}</span>
                  </span>
                )}
                {upcomingEvent && (
                  <span style={{ fontSize: "0.7rem", color: "#97703C" }}>⚡ {upcomingEvent}</span>
                )}
              </div>
            </div>
          )}

          {!a && <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#9C998E" }}>No analysis yet</div>}

          {a && (
            <div style={{ marginTop: "0.5rem", textAlign: "right" }}>
              <span style={{ color: "#9C998E", fontSize: "0.68rem", transition: "transform 0.2s", transform: expanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block" }}>▼</span>
            </div>
          )}
        </div>
      ) : (
        /* ── Desktop grid layout ── */
        <div
          onClick={a ? onToggle : undefined}
          style={{
            display: "grid",
            gridTemplateColumns: "200px 100px 120px 180px 70px 100px 1fr 48px",
            alignItems: "center", padding: "0.9rem 1.25rem",
            cursor: a ? "pointer" : "default", gap: "1rem",
          }}
        >
          {/* Stock */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{ fontWeight: 600, fontSize: "0.95rem", fontFamily: MONO, color: "#20211C" }}>{item.ticker}</span>
              {a?.is_important_day && <span title={a.importance_reason ?? ""} style={{ fontSize: "0.75rem" }}>⭐</span>}
              {item.is_leveraged && (
                <span style={{ fontSize: "0.6rem", padding: "0.1rem 0.35rem", background: "#EAF0F3", color: "#3A5A6E", border: "1px solid #D7E1E8", borderRadius: 4, fontWeight: 700, fontFamily: MONO }}>3X</span>
              )}
            </div>
            {item.company_name && (
              <div style={{ fontSize: "0.72rem", color: "#9C998E", marginTop: "0.15rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {item.company_name}
              </div>
            )}
            {age && (
              <div style={{ marginTop: "0.2rem" }}>
                <span style={{ fontSize: "0.62rem", padding: "0.1rem 0.4rem", background: "#EDE9DF", color: "#9C998E", borderRadius: 4, fontFamily: MONO }}>{age}</span>
              </div>
            )}
          </div>

          {/* Verdict */}
          {vm ? <VerdictBadge vm={vm} /> : <span style={{ fontSize: "0.78rem", color: "#9C998E" }}>Pending</span>}

          {/* Price */}
          <div>
            {a?.current_price != null ? (
              <>
                <div style={{ fontWeight: 600, fontSize: "0.95rem", fontFamily: MONO, color: "#20211C" }}>${a.current_price.toFixed(2)}</div>
                {a.day_change_pct != null && (
                  <div style={{ fontSize: "0.72rem", color: chgColor, fontWeight: 600, fontFamily: MONO }}>
                    {a.day_change_pct >= 0 ? "▲" : "▼"} {Math.abs(a.day_change_pct).toFixed(2)}%
                  </div>
                )}
              </>
            ) : <span style={{ color: "#9C998E", fontSize: "0.82rem" }}>—</span>}
          </div>

          {/* 52-Week Range */}
          {a?.week_52_low != null && a?.week_52_high != null && a?.range_position_pct != null
            ? <RangeBar lo={a.week_52_low} hi={a.week_52_high} pct={a.range_position_pct} />
            : <span style={{ color: "#9C998E", fontSize: "0.78rem" }}>—</span>}

          {/* RSI */}
          {a?.rsi != null ? <RsiPill rsi={a.rsi} /> : <span style={{ color: "#9C998E", fontSize: "0.78rem" }}>—</span>}

          {/* Trend */}
          {a?.current_price != null
            ? <MaBadge price={a.current_price} ma50={a.ma_50} ma200={a.ma_200} />
            : <span style={{ color: "#9C998E", fontSize: "0.78rem" }}>—</span>}

          {/* Signal */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            {a?.analyst_consensus && (
              <span style={{ fontSize: "0.7rem", color: "#9C998E" }}>
                Analysts: <span style={{ color: "#20211C", fontWeight: 600 }}>{a.analyst_consensus}</span>
              </span>
            )}
            {upcomingEvent && <span style={{ fontSize: "0.7rem", color: "#97703C" }}>⚡ {upcomingEvent}</span>}
            {!a && <span style={{ fontSize: "0.75rem", color: "#9C998E" }}>No analysis yet</span>}
          </div>

          {/* Expand + Remove */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", justifyContent: "flex-end" }}>
            {a && (
              <span style={{ color: "#9C998E", fontSize: "0.72rem", transition: "transform 0.2s", transform: expanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block" }}>▼</span>
            )}
            <button
              onClick={e => { e.stopPropagation(); onRemove(item.ticker); }}
              title="Remove from watchlist"
              style={{ background: "none", border: "none", cursor: "pointer", color: "#9C998E", fontSize: "0.82rem", padding: "0.2rem 0.3rem", borderRadius: 4, lineHeight: 1, opacity: 0.5 }}
              onMouseOver={e => { e.currentTarget.style.color = "#A8554A"; e.currentTarget.style.opacity = "1"; }}
              onMouseOut={e => { e.currentTarget.style.color = "#9C998E"; e.currentTarget.style.opacity = "0.5"; }}
            >✕</button>
          </div>
        </div>
      )}

      {expanded && a && <ExpandedDetail a={a} onChat={() => onChat(item.ticker)} />}
    </div>
  );
}

const TABS = ["Dashboard", "My Stocks", "Discover", "Compare"] as const;
type Tab = typeof TABS[number];

export default function DashboardClient({ userName, idToken }: { userName: string; idToken: string }) {
  const router = useRouter();
  const [digest, setDigest] = useState<DigestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<{ ticker: string; name: string; exchange: string }[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState(-1);
  const [activeTab, setActiveTab] = useState<Tab>("My Stocks");
  const [portfolioSize, setPortfolioSize] = useState<number | null>(null);
  const [showPortfolioPrompt, setShowPortfolioPrompt] = useState(false);
  const [portfolioInput, setPortfolioInput] = useState("");
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [sortMode, setSortMode] = useState<"relevance" | "verdict" | "az" | "movers">("relevance");
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  useEffect(() => { fetchDigest(); fetchUser(); }, []);

  useEffect(() => {
    if (!showProfileMenu) return;
    function handleClick(e: MouseEvent) {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) {
        setShowProfileMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showProfileMenu]);

  async function fetchDigest(silent = false) {
    if (!silent) setLoading(true);
    try {
      const r = await fetch(`${API}/analysis/digest?id_token=${encodeURIComponent(idToken)}`);
      if (r.ok) setDigest(await r.json());
    } finally { if (!silent) setLoading(false); }
  }

  async function fetchUser() {
    const r = await fetch(`${API}/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: idToken }),
    });
    if (r.ok) {
      const u = await r.json();
      if (u.portfolio_size) {
        setPortfolioSize(u.portfolio_size);
      } else {
        setShowPortfolioPrompt(true);
      }
    }
  }

  async function savePortfolioSize() {
    const val = parseFloat(portfolioInput.replace(/[^0-9.]/g, ""));
    if (!val || val <= 0) return;
    const r = await fetch(`${API}/auth/me?id_token=${encodeURIComponent(idToken)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ portfolio_size: val }),
    });
    if (r.ok) {
      setPortfolioSize(val);
      setShowPortfolioPrompt(false);
    }
  }

  async function handleAdd(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    // Allow direct-typed ticker even if user didn't select from dropdown
    const effectiveTicker = ticker.trim() || query.trim().toUpperCase().split(/\s/)[0];
    if (!effectiveTicker) return;
    setAdding(true); setError(""); setShowSuggestions(false);
    try {
      const r = await fetch(`${API}/watchlist?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: effectiveTicker, company_name: companyName || null }),
      });
      if (r.ok) {
        setTicker(""); setCompanyName(""); setQuery(""); setSuggestions([]);
        // Optimistic insert — shows the row immediately as pending, then silent refresh fills in analysis
        setDigest(prev => [...prev, { ticker: effectiveTicker, company_name: companyName || null, is_leveraged: false, analysis: null }]);
        fetchDigest(true);
      } else { const d = await r.json(); setError(d.detail || "Failed to add."); }
    } finally { setAdding(false); }
  }

  function handleSearchInput(val: string) {
    setQuery(val); setTicker(""); setCompanyName(""); setError(""); setHighlightedIdx(-1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (val.trim().length < 1) { setSuggestions([]); setShowSuggestions(false); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/watchlist/search?q=${encodeURIComponent(val)}&id_token=${encodeURIComponent(idToken)}`);
        if (r.ok) { setSuggestions(await r.json()); setShowSuggestions(true); }
      } catch { /* ignore */ }
    }, 300);
  }

  function handleSelect(s: { ticker: string; name: string }) {
    setTicker(s.ticker); setCompanyName(s.name);
    setQuery(`${s.ticker} — ${s.name}`);
    setSuggestions([]); setShowSuggestions(false); setHighlightedIdx(-1);
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIdx(i => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIdx(i => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      const idx = highlightedIdx >= 0 ? highlightedIdx : 0;
      if (suggestions[idx]) { e.preventDefault(); handleSelect(suggestions[idx]); }
    } else if (e.key === "Escape") {
      setShowSuggestions(false); setHighlightedIdx(-1);
    }
  }

  async function handleRemove(t: string) {
    setDigest(prev => prev.filter(d => d.ticker !== t)); // optimistic remove
    try {
      const r = await fetch(`${API}/watchlist/${encodeURIComponent(t)}?id_token=${encodeURIComponent(idToken)}`, { method: "DELETE" });
      if (!r.ok) fetchDigest(true); // revert on failure
    } catch { fetchDigest(true); }
  }

  async function handleChat(t: string) {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: t }),
    });
    if (r.ok) { const conv = await r.json(); router.push(`/chat?conv=${conv.id}`); }
  }

  const buyCount      = digest.filter(d => d.analysis?.verdict === "BUY").length;
  const watchCount    = digest.filter(d => d.analysis?.verdict === "WATCH" || d.analysis?.verdict === "HOLD").length;
  const sellCount     = digest.filter(d => d.analysis?.verdict === "SELL").length;
  const importantItems = digest.filter(d => d.analysis?.is_important_day);
  const initials = userName.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div style={{ minHeight: "100vh", background: "#E8E6E0" }}>

      {/* ── Header ── */}
      <header style={{ position: "sticky", top: 0, zIndex: 40, background: "#FBFAF7", borderBottom: "1px solid #E0DDD3" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", height: 60, display: "flex", alignItems: "center", gap: 26, padding: "0 32px" }}>

          {/* Logo */}
          <div onClick={() => setActiveTab("Dashboard")} style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer", flexShrink: 0 }}>
            <span style={{ width: 22, height: 22, borderRadius: 5, background: "#3A5A6E", display: "flex", alignItems: "center", justifyContent: "center", color: "#FBFAF7", fontSize: 12, fontWeight: 600, fontFamily: MONO }}>✦</span>
            <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em", color: "#20211C", fontFamily: SANS }}>Stock Copilot</span>
          </div>

          {/* Nav tabs */}
          <nav style={{ display: "flex", gap: 2, height: "100%" }}>
            {TABS.map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} style={{
                fontSize: 14, fontFamily: SANS,
                color: activeTab === tab ? "#20211C" : "#6A685F",
                fontWeight: activeTab === tab ? 600 : 500,
                padding: "0 14px", height: 60, border: "none",
                borderBottom: activeTab === tab ? "2px solid #3A5A6E" : "2px solid transparent",
                background: "none", cursor: "pointer", transition: "color 0.15s",
                whiteSpace: "nowrap",
              }}>
                {tab}
              </button>
            ))}
          </nav>

          {/* Right side */}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
            <button onClick={() => router.push("/chat")} style={{
              fontSize: 13, fontFamily: SANS, color: "#6A685F",
              background: "none", border: "1px solid #E4E1D8",
              borderRadius: 7, padding: "6px 13px", cursor: "pointer",
            }}>
              Chat →
            </button>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.15 }}>
              <span style={{ fontSize: 9, letterSpacing: "0.12em", color: "#9C998E", fontFamily: MONO, fontWeight: 500 }}>VIRTUAL BALANCE</span>
              <span style={{ fontSize: 14, fontFamily: MONO, fontWeight: 500, color: "#20211C", marginTop: 3 }}>$20,000</span>
            </div>
            <div ref={profileMenuRef} style={{ position: "relative" }}>
              <div
                onClick={() => setShowProfileMenu(v => !v)}
                style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: showProfileMenu ? "#D8D5CC" : "#ECEAE3",
                  border: "1px solid #E0DDD3",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 12, fontWeight: 600, color: "#6A685F",
                  cursor: "pointer", userSelect: "none", fontFamily: SANS,
                  transition: "background 0.15s",
                }}
              >
                {initials}
              </div>
              {showProfileMenu && (
                <div style={{
                  position: "absolute", top: "calc(100% + 8px)", right: 0,
                  minWidth: 180, background: "#FBFAF7",
                  border: "1px solid #E4E1D8", borderRadius: 10,
                  boxShadow: "0 8px 24px rgba(32,33,28,0.12)",
                  zIndex: 100, overflow: "hidden",
                }}>
                  <div style={{ padding: "12px 16px 10px", borderBottom: "1px solid #EDEAE1" }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#20211C", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{userName}</div>
                  </div>
                  <button
                    onClick={() => signOut({ callbackUrl: "/signin" })}
                    style={{
                      width: "100%", textAlign: "left", padding: "11px 16px",
                      background: "none", border: "none", cursor: "pointer",
                      fontSize: 13, color: "#A8554A", fontFamily: SANS,
                      display: "flex", alignItems: "center", gap: 8,
                    }}
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1180, margin: "0 auto", padding: "30px 32px 56px" }}>

        {/* ── Dashboard tab ── */}
        {activeTab === "Dashboard" && (() => {
          // Spotlight: highest convergence BUY/SELL, min score 5
          const spotlight = digest
            .filter(d => d.analysis && (d.analysis.verdict === "BUY" || d.analysis.verdict === "SELL") && (d.analysis.signal_convergence_score ?? 0) >= 5)
            .sort((a, b) => ((b.analysis?.signal_convergence_score ?? 0) - (a.analysis?.signal_convergence_score ?? 0)) || ((b.analysis?.conviction_score ?? 0) - (a.analysis?.conviction_score ?? 0)))
          [0] ?? null;

          const allClear = !loading && digest.length > 0 && !spotlight;
          const vm = spotlight?.analysis?.verdict ? VERDICT_META[spotlight.analysis.verdict] ?? VERDICT_META.WATCH : null;
          const sa = spotlight?.analysis ?? null;

          // Share count helper
          const shareCount = (a: Analysis | null) => {
            if (!a || !portfolioSize || !a.position_size_pct || !a.entry_target) return null;
            const match = a.position_size_pct.match(/(\d+)/);
            if (!match) return null;
            const pct = parseInt(match[1]) / 100;
            const dollars = portfolioSize * pct;
            const shares = Math.floor(dollars / a.entry_target);
            return { dollars: Math.round(dollars), shares };
          };

          return (
            <div>
              <div style={{ marginBottom: 24 }}>
                <h1 style={{ margin: 0, fontFamily: SERIF, fontWeight: 600, fontSize: 25, letterSpacing: "-0.01em", color: "#20211C" }}>
                  Good morning, {userName.split(" ")[0]}
                </h1>
                <div style={{ marginTop: 5, fontSize: 13, color: "#9C998E" }}>Updated nightly after market close · {digest.length} stock{digest.length !== 1 ? "s" : ""} tracked</div>
              </div>

              {/* Portfolio size prompt */}
              {showPortfolioPrompt && (
                <div style={{ background: "#E8EFF4", border: "1px solid #C8D8E4", borderRadius: 11, padding: "18px 20px", marginBottom: 16 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: "#20211C", marginBottom: 6 }}>One quick question to personalise your advice</div>
                  <div style={{ fontSize: 13, color: "#6A685F", marginBottom: 14 }}>What is your approximate investing portfolio size? This lets us suggest exact share counts — no account linking needed.</div>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    {["$5,000", "$10,000", "$25,000", "$50,000", "$100,000+"].map(opt => (
                      <button key={opt} onClick={() => setPortfolioInput(opt.replace(/[^0-9]/g, ""))}
                        style={{ padding: "6px 14px", borderRadius: 20, border: `1px solid ${portfolioInput === opt.replace(/[^0-9]/g, "") ? "#3A5A6E" : "#C8D8E4"}`, background: portfolioInput === opt.replace(/[^0-9]/g, "") ? "#3A5A6E" : "white", color: portfolioInput === opt.replace(/[^0-9]/g, "") ? "white" : "#3A5A6E", cursor: "pointer", fontSize: 13, fontFamily: MONO }}>
                        {opt}
                      </button>
                    ))}
                    <button onClick={savePortfolioSize} disabled={!portfolioInput}
                      style={{ padding: "6px 18px", borderRadius: 20, background: portfolioInput ? "#3A5A6E" : "#E4E1D8", color: portfolioInput ? "white" : "#9C998E", border: "none", cursor: portfolioInput ? "pointer" : "default", fontSize: 13, fontWeight: 600, fontFamily: SANS }}>
                      Save
                    </button>
                    <button onClick={() => setShowPortfolioPrompt(false)} style={{ background: "none", border: "none", fontSize: 12, color: "#9C998E", cursor: "pointer" }}>Skip</button>
                  </div>
                </div>
              )}

              {/* ── Spotlight card ── */}
              {spotlight && sa && vm && (
                <div style={{ background: "#FBFAF7", border: "2px solid #3A5A6E", borderRadius: 13, marginBottom: 16, overflow: "hidden" }}>
                  {/* Header */}
                  <div style={{ background: "#3A5A6E", padding: "12px 20px", display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: 13, color: "#FBFAF7", fontWeight: 700, letterSpacing: "0.04em" }}>⚡ Today's Opportunity</span>
                    <span style={{ marginLeft: "auto", fontSize: 11, color: "rgba(251,250,247,0.7)", fontFamily: MONO }}>
                      {sa.signal_convergence_score}/7 signals · conviction {sa.conviction_score}/100
                    </span>
                  </div>

                  {/* Ticker + verdict */}
                  <div style={{ padding: "16px 20px 0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                      <span style={{ fontFamily: MONO, fontWeight: 700, fontSize: 22, color: "#20211C" }}>{spotlight.ticker}</span>
                      {spotlight.company_name && <span style={{ fontSize: 13, color: "#6A685F" }}>{spotlight.company_name}</span>}
                      <span style={{ padding: "3px 12px", borderRadius: 20, fontSize: 12, fontFamily: MONO, fontWeight: 700, color: vm.color, background: vm.bg, border: `1px solid ${vm.bd}`, marginLeft: "auto" }}>
                        {vm.label}
                      </span>
                    </div>

                    {/* Trust badges */}
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                      {sa.entry_quality && (
                        <span style={{ fontSize: 12, fontFamily: MONO, padding: "3px 10px", borderRadius: 20, color: sa.entry_quality === "GREAT" ? "#3F6B4F" : sa.entry_quality === "FAIR" ? "#97703C" : "#A8554A", background: sa.entry_quality === "GREAT" ? "#EAF1EC" : sa.entry_quality === "FAIR" ? "#F4EEE2" : "#F4E7E4", border: `1px solid ${sa.entry_quality === "GREAT" ? "#C8DDD0" : sa.entry_quality === "FAIR" ? "#E6DBC4" : "#E6D2CC"}` }}>
                          Entry: {sa.entry_quality === "GREAT" ? "Great" : sa.entry_quality === "FAIR" ? "Fair" : "Wait"}
                        </span>
                      )}
                      {sa.hold_and_forget_rating === "HOLD_AND_FORGET" && (
                        <span style={{ fontSize: 12, fontFamily: MONO, padding: "3px 10px", borderRadius: 20, color: "#3F6B4F", background: "#EAF1EC", border: "1px solid #C8DDD0" }}>Hold & Forget ✓</span>
                      )}
                      {sa.position_size_pct && (
                        <span style={{ fontSize: 12, fontFamily: MONO, padding: "3px 10px", borderRadius: 20, color: "#3A5A6E", background: "#E8EFF4", border: "1px solid #C8D8E4" }}>
                          {sa.position_size_pct} of portfolio
                        </span>
                      )}
                    </div>

                    {/* Why now — convergence signals */}
                    {sa.convergence_details && (() => {
                      try {
                        const details: Record<string, boolean> = JSON.parse(sa.convergence_details);
                        const fired = Object.entries(details).filter(([, v]) => v);
                        const SIGNAL_LABELS: Record<string, string> = {
                          oversold_rsi: "Oversold (RSI < 42)",
                          near_52w_low: "Near 52-week low",
                          analyst_upside_15pct: "15%+ analyst upside",
                          no_binary_risk: "No earnings risk (21+ days)",
                          positive_fcf: "Positive free cash flow",
                          institutional_backing: "Institutions buying (40%+)",
                          price_stabilizing: "Price stabilizing near MA200",
                        };
                        return (
                          <div style={{ marginBottom: 14 }}>
                            <div style={{ fontSize: 11, fontFamily: MONO, color: "#9C998E", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>Why now</div>
                            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              {fired.map(([k]) => (
                                <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#3A3833" }}>
                                  <span style={{ color: "#3F6B4F", fontWeight: 700, fontSize: 12 }}>✓</span>
                                  {SIGNAL_LABELS[k] ?? k}
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      } catch { return null; }
                    })()}

                    {/* Scenarios */}
                    {sa.scenario_bull_prob != null && (
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 14 }}>
                        {([
                          { label: "Bull", pct: sa.scenario_bull_pct, prob: sa.scenario_bull_prob, color: "#3F6B4F", bg: "#EAF1EC", bd: "#C8DDD0" },
                          { label: "Base", pct: sa.scenario_base_pct, prob: sa.scenario_base_prob, color: "#3A5A6E", bg: "#E8EFF4", bd: "#C8D8E4" },
                          { label: "Bear", pct: sa.scenario_bear_pct, prob: sa.scenario_bear_prob, color: "#A8554A", bg: "#F4E7E4", bd: "#E6D2CC" },
                        ] as const).map(s => (
                          <div key={s.label} style={{ background: s.bg, border: `1px solid ${s.bd}`, borderRadius: 8, padding: "8px 10px", textAlign: "center" }}>
                            <div style={{ fontSize: 10, fontFamily: MONO, color: s.color, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>{s.label} · {s.prob}%</div>
                            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: MONO, color: s.color, marginTop: 2 }}>
                              {s.pct != null ? (s.pct >= 0 ? "+" : "") + s.pct.toFixed(1) + "%" : "—"}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Action line */}
                    <div style={{ background: "#F0EDE6", borderRadius: 8, padding: "12px 14px", marginBottom: 16, display: "flex", flexWrap: "wrap", gap: "10px 24px", alignItems: "center" }}>
                      {sa.entry_target && <div><div style={{ fontSize: 10, color: "#9C998E", fontFamily: MONO }}>Buy ≤</div><div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "#3F6B4F" }}>${sa.entry_target.toFixed(2)}</div></div>}
                      {sa.stop_loss    && <div><div style={{ fontSize: 10, color: "#9C998E", fontFamily: MONO }}>Stop</div><div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "#A8554A" }}>${sa.stop_loss.toFixed(2)}</div></div>}
                      {sa.exit_target  && <div><div style={{ fontSize: 10, color: "#9C998E", fontFamily: MONO }}>Target</div><div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "#3A5A6E" }}>${sa.exit_target.toFixed(2)}</div></div>}
                      {sa.hold_period  && <div><div style={{ fontSize: 10, color: "#9C998E", fontFamily: MONO }}>Hold</div><div style={{ fontSize: 13, fontWeight: 600, color: "#20211C" }}>{sa.hold_period}</div></div>}
                      {(() => { const sc = shareCount(sa); return sc ? (
                        <div style={{ marginLeft: "auto" }}>
                          <div style={{ fontSize: 10, color: "#9C998E", fontFamily: MONO }}>~Shares</div>
                          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "#20211C" }}>{sc.shares} <span style={{ fontSize: 11, color: "#9C998E", fontWeight: 400 }}>(${sc.dollars.toLocaleString()})</span></div>
                        </div>
                      ) : null; })()}
                    </div>
                  </div>

                  {/* Footer */}
                  <div style={{ padding: "0 20px 16px", display: "flex", gap: 10 }}>
                    <button onClick={() => { setActiveTab("My Stocks"); setExpanded(spotlight.ticker); }}
                      style={{ flex: 1, padding: "10px 0", background: "#3A5A6E", color: "#FBFAF7", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 14, fontFamily: SANS }}>
                      View Full Analysis →
                    </button>
                    <button onClick={() => { setActiveTab("My Stocks"); }}
                      style={{ padding: "10px 18px", background: "none", color: "#9C998E", border: "1px solid #E4E1D8", borderRadius: 8, cursor: "pointer", fontSize: 13, fontFamily: SANS }}>
                      Skip
                    </button>
                  </div>
                </div>
              )}

              {/* ── All Clear card ── */}
              {allClear && (
                <div style={{ background: "#F4F8F4", border: "1px solid #D6E2D7", borderRadius: 13, padding: "28px 24px", marginBottom: 16, textAlign: "center" }}>
                  <div style={{ fontSize: 28, marginBottom: 10 }}>✓</div>
                  <div style={{ fontSize: 18, fontWeight: 600, color: "#3F6B4F", marginBottom: 8, fontFamily: SERIF }}>All Clear — Nothing to do today</div>
                  <div style={{ fontSize: 13, color: "#6A685F", lineHeight: 1.6 }}>
                    Your {digest.length} stock{digest.length !== 1 ? "s" : ""} are being watched. No high-conviction opportunities cleared the threshold today.<br />
                    Come back tomorrow — the nightly agent runs after market close.
                  </div>
                </div>
              )}

              {/* Important flags */}
              {importantItems.length > 0 && (
                <div style={{ background: "#FBFAF7", border: "1px solid #E4E1D8", borderRadius: 11, padding: "6px 4px 8px", marginBottom: 16 }}>
                  <div style={{ padding: "13px 18px 11px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 15, fontWeight: 600, color: "#20211C" }}>Important signals today</span>
                    <span style={{ fontSize: 10, color: "#9C998E", fontFamily: MONO, letterSpacing: "0.08em" }}>{importantItems.length} FLAG{importantItems.length > 1 ? "S" : ""}</span>
                  </div>
                  {importantItems.map(item => {
                    const ivm = item.analysis?.verdict ? VERDICT_META[item.analysis.verdict] ?? VERDICT_META.WATCH : null;
                    return (
                      <div key={item.ticker} onClick={() => { setActiveTab("My Stocks"); setExpanded(item.ticker); }}
                        style={{ display: "flex", alignItems: "center", gap: 13, padding: "12px 18px", borderTop: "1px solid #EDEAE1", cursor: "pointer" }}>
                        <span style={{ fontFamily: MONO, fontWeight: 600, fontSize: 13, width: 60, color: "#20211C" }}>{item.ticker}</span>
                        {ivm && <span style={{ fontSize: 10, padding: "3px 9px", background: ivm.bg, color: ivm.color, border: `1px solid ${ivm.bd}`, borderRadius: 20, fontFamily: MONO, fontWeight: 700 }}>{ivm.label}</span>}
                        <span style={{ flex: 1, fontSize: 13, color: "#6A685F" }}>{item.analysis?.importance_reason ?? "—"}</span>
                        <span style={{ fontSize: 12, color: "#3A5A6E", fontWeight: 600 }}>View →</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* My Stocks teaser */}
              <button onClick={() => setActiveTab("My Stocks")} style={{
                width: "100%", textAlign: "left", background: "#FBFAF7",
                border: "1px solid #E4E1D8", borderRadius: 11, padding: "15px 20px",
                display: "flex", alignItems: "center", gap: 14, cursor: "pointer", fontFamily: SANS,
              }}>
                <span style={{ fontSize: 10, fontFamily: MONO, letterSpacing: "0.12em", color: "#9C998E" }}>MY STOCKS</span>
                <span style={{ fontSize: 14, color: "#20211C" }}>
                  Tracking <b style={{ fontFamily: MONO }}>{digest.length}</b> stock{digest.length !== 1 ? "s" : ""} · {buyCount} buy · {watchCount} hold/watch · {sellCount} sell
                </span>
                <span style={{ marginLeft: "auto", fontSize: 13, color: "#3A5A6E", fontWeight: 600, whiteSpace: "nowrap" }}>See full table →</span>
              </button>
            </div>
          );
        })()}

        {/* ── My Stocks tab ── */}
        {activeTab === "My Stocks" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22, flexWrap: "wrap", gap: "0.75rem" }}>
              <div>
                <h1 style={{ margin: 0, fontFamily: SERIF, fontWeight: 600, fontSize: 25, color: "#20211C" }}>My Stocks</h1>
                <div style={{ marginTop: 5, fontSize: 13, color: "#9C998E" }}>
                  {digest.length} stock{digest.length !== 1 ? "s" : ""} · Updated nightly after market close
                </div>
              </div>
              {/* Sort/group control */}
              {digest.length > 0 && (
                <div style={{ display: "flex", gap: 4, background: "#ECEAE3", borderRadius: 9, padding: 3 }}>
                  {([
                    { key: "relevance", label: "Relevance" },
                    { key: "verdict",   label: "Verdict"   },
                    { key: "az",        label: "A–Z"       },
                    { key: "movers",    label: "Movers"    },
                  ] as const).map(opt => (
                    <button key={opt.key} onClick={() => setSortMode(opt.key)} style={{
                      padding: "4px 12px", borderRadius: 6, border: "none",
                      background: sortMode === opt.key ? "#FBFAF7" : "transparent",
                      boxShadow: sortMode === opt.key ? "0 1px 3px rgba(32,33,28,0.1)" : "none",
                      color: sortMode === opt.key ? "#20211C" : "#9C998E",
                      fontWeight: sortMode === opt.key ? 600 : 400,
                      fontSize: "0.75rem", cursor: "pointer", fontFamily: MONO,
                      transition: "all 0.15s", whiteSpace: "nowrap",
                    }}>
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {loading ? (
              <div style={{ textAlign: "center", padding: "3rem", color: "#9C998E" }}>Loading your digest…</div>
            ) : digest.length === 0 ? (
              <div style={{ textAlign: "center", padding: "3rem", background: "#FBFAF7", borderRadius: 11, border: "1px solid #E4E1D8", color: "#9C998E" }}>
                <div style={{ fontSize: "1.8rem", marginBottom: "0.5rem" }}>—</div>
                <div style={{ fontWeight: 600, marginBottom: "0.35rem", color: "#20211C" }}>Add your first stock to get started</div>
                <div style={{ fontSize: "0.82rem" }}>Try: NFLX, MRVL, SOXQ, SOXL</div>
              </div>
            ) : (() => {
              const VERDICT_ORDER = ["BUY", "HOLD", "WATCH", "SELL"];
              const VERDICT_META_GROUP: Record<string, { label: string; color: string; bg: string; bd: string }> = {
                BUY:   { label: "Buy",   color: "#3F6B4F", bg: "#EAF1EC", bd: "#C8DDD0" },
                HOLD:  { label: "Hold",  color: "#97703C", bg: "#F4EEE2", bd: "#E6DBC4" },
                WATCH: { label: "Watch", color: "#9C998E", bg: "#F4F2EC", bd: "#E4E1D8" },
                SELL:  { label: "Sell",  color: "#A8554A", bg: "#F4E7E4", bd: "#E6D2CC" },
              };

              const colHeaders = !isMobile && (
                <div style={{ display: "grid", gridTemplateColumns: "200px 100px 120px 180px 70px 100px 1fr 48px", padding: "0 1.25rem", marginBottom: "0.4rem", gap: "1rem" }}>
                  {["Stock", "Verdict", "Price", "52-Week Range", "RSI", "Trend", "Signal", ""].map(h => (
                    <div key={h} style={{ fontSize: "0.67rem", color: "#9C998E", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.09em", fontFamily: MONO }}>{h}</div>
                  ))}
                </div>
              );

              const renderRow = (item: DigestItem) => (
                <StockRow
                  key={item.ticker} item={item}
                  expanded={expanded === item.ticker}
                  onToggle={() => setExpanded(expanded === item.ticker ? null : item.ticker)}
                  onChat={handleChat} onRemove={handleRemove}
                  isMobile={isMobile}
                />
              );

              const sectionHeader = (label: string, count: number, color: string, bg: string, bd: string) => (
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <span style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 700, padding: "2px 10px", borderRadius: 20, color, background: bg, border: `1px solid ${bd}`, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
                  <span style={{ fontSize: "0.68rem", color: "#9C998E", fontFamily: MONO }}>{count} stock{count > 1 ? "s" : ""}</span>
                  <div style={{ flex: 1, height: 1, background: "#E4E1D8" }} />
                </div>
              );

              // ── Relevance: flat list sorted by convergence_score desc, then conviction_score desc ──
              if (sortMode === "relevance") {
                const sorted = [...digest].sort((a, b) => {
                  const scoreA = (a.analysis?.signal_convergence_score ?? -1) * 100 + (a.analysis?.conviction_score ?? 0);
                  const scoreB = (b.analysis?.signal_convergence_score ?? -1) * 100 + (b.analysis?.conviction_score ?? 0);
                  return scoreB - scoreA;
                });
                return (
                  <div>
                    {colHeaders}
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                      {sorted.map(renderRow)}
                    </div>
                  </div>
                );
              }

              // ── Verdict: grouped by BUY / HOLD / WATCH / SELL / Pending ──
              if (sortMode === "verdict") {
                const grouped = VERDICT_ORDER.map(v => ({
                  verdict: v, ...VERDICT_META_GROUP[v],
                  items: digest.filter(d => d.analysis?.verdict === v),
                })).filter(g => g.items.length > 0);
                const pending = digest.filter(d => !d.analysis);
                return (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    {grouped.map((g, gi) => (
                      <div key={g.verdict}>
                        {sectionHeader(g.label, g.items.length, g.color, g.bg, g.bd)}
                        {gi === 0 && colHeaders}
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{g.items.map(renderRow)}</div>
                      </div>
                    ))}
                    {pending.length > 0 && (
                      <div>
                        {sectionHeader("Pending", pending.length, "#9C998E", "#ECEAE3", "#E4E1D8")}
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{pending.map(renderRow)}</div>
                      </div>
                    )}
                  </div>
                );
              }

              // ── A–Z: flat alphabetical ──
              if (sortMode === "az") {
                const sorted = [...digest].sort((a, b) => a.ticker.localeCompare(b.ticker));
                return (
                  <div>
                    {colHeaders}
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{sorted.map(renderRow)}</div>
                  </div>
                );
              }

              // ── Movers: sorted by abs(day_change_pct) desc ──
              const sorted = [...digest].sort((a, b) => Math.abs(b.analysis?.day_change_pct ?? 0) - Math.abs(a.analysis?.day_change_pct ?? 0));
              return (
                <div>
                  {colHeaders}
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{sorted.map(renderRow)}</div>
                </div>
              );
            })()}

            {/* Add stock form */}
            <form onSubmit={handleAdd} style={{
              display: "flex", gap: "0.5rem", marginTop: "1.5rem",
              padding: "1rem 1.25rem", background: "#FBFAF7",
              border: "1px solid #E4E1D8", borderRadius: 11,
              alignItems: "center", flexWrap: "wrap",
            }}>
              <div style={{ position: "relative", flex: "1 1 260px" }}>
                <input
                  value={query}
                  onChange={e => handleSearchInput(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  onBlur={() => setTimeout(() => { setShowSuggestions(false); setHighlightedIdx(-1); }, 200)}
                  onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                  placeholder="Type ticker (e.g. NFLX) or search by name…"
                  autoComplete="off"
                  style={{
                    width: "100%", padding: "0.5rem 0.75rem", background: "#F6F4EE",
                    border: "1px solid #E4E1D8", borderRadius: 7,
                    color: "#20211C", fontSize: "0.88rem", fontFamily: SANS,
                    outline: "none",
                  }}
                />
                {showSuggestions && suggestions.length > 0 && (
                  <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 50, background: "#FBFAF7", border: "1px solid #E4E1D8", borderRadius: 9, overflow: "hidden", boxShadow: "0 8px 24px rgba(32,33,28,0.1)" }}>
                    {suggestions.map((s, idx) => (
                      <div key={s.ticker} onMouseDown={() => handleSelect(s)}
                        style={{ padding: "0.6rem 0.85rem", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", borderBottom: "1px solid #EDEAE1", background: idx === highlightedIdx ? "#F0EDE6" : "transparent" }}
                        onMouseEnter={() => setHighlightedIdx(idx)}
                        onMouseLeave={() => setHighlightedIdx(-1)}>
                        <div>
                          <span style={{ fontWeight: 600, fontSize: "0.88rem", color: "#20211C", fontFamily: MONO }}>{s.ticker}</span>
                          <span style={{ marginLeft: "0.5rem", fontSize: "0.82rem", color: "#6A685F" }}>{s.name}</span>
                        </div>
                        <span style={{ fontSize: "0.75rem", color: "#9C998E", flexShrink: 0 }}>{s.exchange}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button type="submit" disabled={adding || (!ticker && !query.trim())} style={{
                padding: "0.5rem 1.1rem",
                background: (ticker || query.trim()) ? "#3A5A6E" : "#E4E1D8",
                color: (ticker || query.trim()) ? "#FBFAF7" : "#9C998E",
                border: "none", borderRadius: 7,
                cursor: (ticker || query.trim()) ? "pointer" : "not-allowed",
                fontWeight: 600, fontSize: "0.88rem", fontFamily: SANS,
                transition: "background 0.15s",
              }}>
                {adding ? "Adding…" : "+ Add"}
              </button>
              {error && <span style={{ color: "#A8554A", fontSize: "0.8rem", width: "100%" }}>{error}</span>}
            </form>
          </div>
        )}

        {/* ── Discover + Compare placeholders ── */}
        {(activeTab === "Discover" || activeTab === "Compare") && (
          <div style={{ display: "flex", justifyContent: "center", paddingTop: 80 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, background: "#FBFAF7", border: "1px solid #E4E1D8", borderRadius: 13, padding: "40px 64px" }}>
              <div style={{ width: 44, height: 44, borderRadius: 10, background: "#EAF0F3", border: "1px solid #D7E1E8", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>
                {activeTab === "Discover" ? "🔍" : "📊"}
              </div>
              <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 20, color: "#20211C" }}>
                {activeTab} — coming soon
              </div>
              <div style={{ fontSize: 13, color: "#9C998E", maxWidth: "30ch", lineHeight: 1.6, textAlign: "center" }}>
                {activeTab === "Discover"
                  ? "AI-ranked picks outside your watchlist, sorted by conviction."
                  : "Autopilot vs Copilot head-to-head performance tracking."}
              </div>
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
