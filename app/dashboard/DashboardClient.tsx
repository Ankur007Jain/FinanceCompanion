"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

// ── Types ──────────────────────────────────────────────────────────────────────

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
  news_summary: string | null;
  ripple_analysis: string | null;
  is_important_day: boolean;
  importance_reason: string | null;
  events_json: string | null;
}

interface DigestItem {
  ticker: string;
  company_name: string | null;
  is_leveraged: boolean;
  analysis: Analysis | null;
}

interface SimPortfolioItem {
  id: string;
  ticker: string;
  shares: number;
  entry_price: number | null;
  entry_date: string | null;
  status: string;
  virtual_cash: number;
}

interface SimTrade {
  id: string;
  ticker: string;
  action: string;
  price: number;
  shares: number;
  trade_date: string;
  reasoning: string | null;
}

type View = "dashboard" | "stocks" | "discover" | "compare" | "detail";

// ── Palette ────────────────────────────────────────────────────────────────────

const BG   = "#E8E6E0";
const SURF = "#FBFAF7";
const BRD  = "#E4E1D8";
const INK  = "#20211C";
const INK2 = "#6A685F";
const INK3 = "#9C998E";
const AUTO = "#3A5A6E";
const COPI = "#4A6B57";
const UP   = "#3F6B4F";
const DN   = "#A8554A";
const WARN = "#97703C";

// ── Helpers ────────────────────────────────────────────────────────────────────

function riskOf(item: DigestItem): "LOW" | "MED" | "HIGH" {
  if (item.is_leveraged) return "HIGH";
  const b = item.analysis?.beta;
  if (b == null) return "MED";
  return b >= 1.5 ? "HIGH" : b >= 1.0 ? "MED" : "LOW";
}

function convictionOf(verdict: string | null): number {
  if (verdict === "BUY")   return 82;
  if (verdict === "HOLD")  return 74;
  if (verdict === "SELL")  return 55;
  return 63;
}

function verdictLine(verdict: string | null): string {
  if (verdict === "BUY")   return "Buy — good time to add";
  if (verdict === "HOLD")  return "Hold — steady as it goes";
  if (verdict === "SELL")  return "Sell — time to exit";
  if (verdict === "WATCH") return "Watch — wait for a clear signal";
  return "Pending analysis";
}

const RISK_META = {
  LOW:  { c: UP,   bg: "#EAF1EC", bd: "#D6E2D7" },
  MED:  { c: WARN, bg: "#F4EEE2", bd: "#E6DBC4" },
  HIGH: { c: DN,   bg: "#F4E7E4", bd: "#E6D2CC" },
};

function riskChip(r: "LOW" | "MED" | "HIGH"): React.CSSProperties {
  const { c, bg, bd } = RISK_META[r];
  return { display: "inline-block", fontFamily: "'IBM Plex Mono',monospace", fontSize: 9.5, fontWeight: 500, letterSpacing: ".08em", color: c, background: bg, border: `1px solid ${bd}`, borderRadius: 20, padding: "4px 8px", whiteSpace: "nowrap" };
}

function fmtMoney(v: number)  { return "$" + Math.round(v).toLocaleString("en-US"); }
function fmtPrice(v: number | null) { return v == null ? "—" : "$" + v.toFixed(2); }
function fmtPct(v: number | null)   { return v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(1) + "%"; }
function fmtCap(v: number) {
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9)  return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6)  return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + v.toLocaleString();
}

function relativeDate(d: string) {
  const diff = Date.now() - new Date(d).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7)  return `${days}d ago`;
  return new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ── Atomic components ──────────────────────────────────────────────────────────

function ConvRing({ value, color = AUTO, size = 128 }: { value: number; color?: string; size?: number }) {
  const offset = Math.round(251 * (1 - value / 100));
  return (
    <svg viewBox="0 0 100 100" style={{ width: size, height: size }}>
      <circle cx="50" cy="50" r="40" fill="none" stroke="#ECEAE3" strokeWidth="8" />
      <circle cx="50" cy="50" r="40" fill="none" stroke={color} strokeWidth="8"
        strokeLinecap="round" strokeDasharray="251" strokeDashoffset={offset}
        transform="rotate(-90 50 50)" />
      <text x="50" y="49" textAnchor="middle" fontFamily="IBM Plex Mono" fontSize="27" fontWeight="600" fill={INK}>{value}</text>
      <text x="50" y="64" textAnchor="middle" fontFamily="IBM Plex Mono" fontSize="8.5" letterSpacing="1" fill={INK3}>CONVICTION</text>
    </svg>
  );
}

function MiniSpark({ up }: { up: boolean }) {
  const pts = up
    ? "0,20 16,16 32,18 48,9 64,13 80,5 96,8 112,3"
    : "0,5 16,9 32,7 48,13 64,10 80,16 96,14 112,19";
  return (
    <svg viewBox="0 0 112 24" preserveAspectRatio="none" style={{ flex: 1, height: 22 }}>
      <polyline points={pts} fill="none" stroke={up ? UP : DN} strokeWidth="1.8" />
    </svg>
  );
}

function FKV({ k, v, c }: { k: string; v: string; c?: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: INK3, marginBottom: 2 }}>{k}</div>
      <div style={{ fontWeight: 700, fontSize: 13.5, color: c ?? INK }}>{v}</div>
    </div>
  );
}

// ── Stock Detail ───────────────────────────────────────────────────────────────

function StockDetailView({ item, onBack, onChat }: { item: DigestItem; onBack: () => void; onChat: () => void }) {
  const a = item.analysis;
  const risk = riskOf(item);
  const conv = convictionOf(a?.verdict ?? null);
  const rColor = RISK_META[risk].c;
  const dayUp = (a?.day_change_pct ?? 0) >= 0;

  const bullets = a?.reasoning
    ? a.reasoning.split(/[.!](?:\s+|$)/).filter(s => s.trim().length > 15).slice(0, 3).map(s => s.trim())
    : ["Analysis will appear after the next nightly run."];

  const inds = [
    { k: "Trend", v: a?.ma_50 && a.current_price ? (a.current_price > a.ma_50 ? "Above MA50" : "Below MA50") : "—", s: a?.ma_50 ? `MA50 $${a.ma_50.toFixed(0)}` : "No data", c: a?.ma_50 && a?.current_price ? (a.current_price > a.ma_50 ? UP : DN) : INK3 },
    { k: "RSI", v: a?.rsi != null ? a.rsi.toFixed(0) : "—", s: a?.rsi != null ? (a.rsi >= 70 ? "Overbought" : a.rsi <= 30 ? "Oversold" : "Neutral") : "No data", c: a?.rsi != null ? (a.rsi >= 70 ? DN : a.rsi <= 30 ? UP : INK) : INK3 },
    { k: "52w Range", v: a?.range_position_pct != null ? a.range_position_pct.toFixed(0) + "%" : "—", s: a?.week_52_low && a?.week_52_high ? `$${a.week_52_low.toFixed(0)} – $${a.week_52_high.toFixed(0)}` : "No data", c: a?.range_position_pct != null ? (a.range_position_pct < 33 ? UP : a.range_position_pct > 66 ? DN : WARN) : INK3 },
    { k: "Analyst View", v: a?.analyst_consensus ?? "—", s: a?.pe_trailing ? `P/E ${a.pe_trailing.toFixed(1)}x` : "No P/E data", c: a?.analyst_consensus === "BUY" ? UP : a?.analyst_consensus === "SELL" ? DN : INK },
  ];

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "24px 32px 56px" }}>
      <button onClick={onBack} style={{ font: "500 12.5px 'IBM Plex Sans'", color: INK2, background: "none", border: "none", cursor: "pointer", padding: "6px 0", marginBottom: 8 }}>← Back</button>

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20, marginBottom: 18 }}>
        <div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <span style={{ font: "600 24px/1 'IBM Plex Mono',monospace" }}>{item.ticker}</span>
            <span style={{ fontSize: 15, color: INK2 }}>{item.company_name ?? item.ticker}</span>
          </div>
          {a && (
            <div style={{ marginTop: 9, display: "flex", alignItems: "baseline", gap: 10 }}>
              <span style={{ font: "500 19px/1 'IBM Plex Mono',monospace" }}>{fmtPrice(a.current_price)}</span>
              <span style={{ font: "500 14px 'IBM Plex Mono',monospace", color: dayUp ? UP : DN }}>{fmtPct(a.day_change_pct)}</span>
            </div>
          )}
        </div>
        <button onClick={onChat} style={{ font: "500 13px 'IBM Plex Sans'", color: SURF, background: AUTO, border: "1px solid #34505F", borderRadius: 8, padding: "9px 16px", cursor: "pointer" }}>
          Ask AI →
        </button>
      </div>

      {/* Verdict banner */}
      <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 13, padding: "24px 26px", display: "grid", gridTemplateColumns: "1fr 150px", gap: 24, alignItems: "center" }}>
        <div>
          <div style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".13em", textTransform: "uppercase", color: INK3 }}>The verdict</div>
          <div style={{ marginTop: 12, fontFamily: "'IBM Plex Serif',serif", fontWeight: 600, fontSize: 25, letterSpacing: "-.01em" }}>{verdictLine(a?.verdict ?? null)}</div>
          {a?.reasoning && <div style={{ marginTop: 9, fontSize: 14.5, color: "#3A3833", maxWidth: "48ch", lineHeight: 1.5 }}>{a.reasoning.slice(0, 200)}{a.reasoning.length > 200 ? "…" : ""}</div>}
          <div style={{ marginTop: 14 }}><span style={riskChip(risk)}>{risk} RISK</span></div>
        </div>
        <div style={{ display: "flex", justifyContent: "center" }}>
          <ConvRing value={conv} color={rColor} size={130} />
        </div>
      </div>

      {/* Why */}
      <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "18px 22px", marginTop: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 11 }}>Why we think so</div>
        {bullets.map((w, i) => (
          <div key={i} style={{ display: "flex", gap: 11, padding: "6px 0", fontSize: 13.5, color: "#3A3833" }}>
            <span style={{ color: AUTO, fontWeight: 600 }}>—</span><span>{w}</span>
          </div>
        ))}
      </div>

      {/* 4 indicator cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginTop: 16 }}>
        {inds.map(ind => (
          <div key={ind.k} style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 10, padding: "14px 15px" }}>
            <div style={{ font: "600 9.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: INK3 }}>{ind.k}</div>
            <div style={{ marginTop: 9, fontSize: 15, fontWeight: 600, color: ind.c }}>{ind.v}</div>
            <div style={{ marginTop: 5, fontSize: 11.5, color: INK3, lineHeight: 1.4 }}>{ind.s}</div>
          </div>
        ))}
      </div>

      {/* Price targets */}
      {(a?.entry_target || a?.exit_target || a?.stop_loss) && (
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "16px 20px", marginTop: 16 }}>
          <div style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: INK3, marginBottom: 12 }}>Price targets</div>
          <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
            {a?.entry_target && <FKV k="Entry" v={`$${a.entry_target.toFixed(2)}`} c={UP} />}
            {a?.exit_target  && <FKV k="Take Profit" v={`$${a.exit_target.toFixed(2)}`} c={AUTO} />}
            {a?.stop_loss    && <FKV k="Stop Loss" v={`$${a.stop_loss.toFixed(2)}`} c={DN} />}
            {a?.hold_period  && <FKV k="Hold Period" v={a.hold_period} />}
          </div>
        </div>
      )}

      {/* Autopilot vs Copilot stance */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 16 }}>
        <div style={{ background: "#F5F8FA", border: "1px solid #D7E1E8", borderRadius: 11, padding: "16px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: AUTO, display: "inline-block" }} />
            <span style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", color: AUTO }}>AUTOPILOT</span>
          </div>
          <div style={{ marginTop: 10, fontSize: 14, fontWeight: 600, color: "#2E4757" }}>
            {a?.verdict === "BUY" ? "Buying — high conviction" : a?.verdict === "SELL" ? "Sold — reducing exposure" : "Core hold — no change"}
          </div>
          <div style={{ marginTop: 5, fontSize: 12.5, color: "#43586A" }}>Decided on latest nightly run.</div>
        </div>
        <div style={{ background: "#F4F8F4", border: "1px solid #D6E2D7", borderRadius: 11, padding: "16px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: COPI, display: "inline-block" }} />
            <span style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", color: COPI }}>COPILOT</span>
          </div>
          <div style={{ marginTop: 10, fontSize: 14, fontWeight: 600, color: "#3E5645" }}>
            {a?.verdict === "BUY" ? "Suggestion pending your approval" : a?.verdict === "SELL" ? "Suggesting exit" : "No action — holding"}
          </div>
          <div style={{ marginTop: 5, fontSize: 12.5, color: "#46604D" }}>You decide when to act.</div>
        </div>
      </div>

      {/* Fundamentals */}
      {(a?.pe_trailing || a?.revenue_growth || a?.beta || a?.market_cap) && (
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "16px 20px", marginTop: 16 }}>
          <div style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: INK3, marginBottom: 12 }}>Fundamentals</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(130px,1fr))", gap: "10px 20px" }}>
            {a?.pe_trailing != null && <FKV k="P/E (TTM)" v={a.pe_trailing.toFixed(1) + "x"} />}
            {a?.pe_forward  != null && <FKV k="P/E (Fwd)" v={a.pe_forward.toFixed(1) + "x"} />}
            {a?.revenue_growth != null && <FKV k="Rev Growth" v={(a.revenue_growth * 100).toFixed(1) + "%"} c={a.revenue_growth >= 0 ? UP : DN} />}
            {a?.profit_margin  != null && <FKV k="Net Margin" v={(a.profit_margin * 100).toFixed(1) + "%"} c={a.profit_margin >= 0 ? UP : DN} />}
            {a?.beta       != null && <FKV k="Beta" v={a.beta.toFixed(2)} c={a.beta > 1.5 ? WARN : undefined} />}
            {a?.market_cap != null && <FKV k="Mkt Cap" v={fmtCap(a.market_cap)} />}
            {a?.dividend_yield != null && a.dividend_yield > 0 && <FKV k="Dividend" v={(a.dividend_yield * 100).toFixed(2) + "%"} c={UP} />}
          </div>
          {(a?.sector || a?.industry) && <div style={{ marginTop: 8, fontSize: 11.5, color: INK3 }}>{[a?.sector, a?.industry].filter(Boolean).join(" · ")}</div>}
        </div>
      )}

      {/* News + Ripple */}
      {(a?.news_summary || a?.ripple_analysis) && (
        <div style={{ display: "grid", gridTemplateColumns: a?.news_summary && a?.ripple_analysis ? "1fr 1fr" : "1fr", gap: 12, marginTop: 16 }}>
          {a?.news_summary && (
            <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "16px 18px" }}>
              <div style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: INK3, marginBottom: 8 }}>Recent news</div>
              <div style={{ fontSize: 13, lineHeight: 1.55, color: INK }}>{a.news_summary}</div>
            </div>
          )}
          {a?.ripple_analysis && (
            <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "16px 18px" }}>
              <div style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", textTransform: "uppercase", color: INK3, marginBottom: 8 }}>Ripple effects</div>
              <div style={{ fontSize: 13, lineHeight: 1.55, color: INK }}>{a.ripple_analysis}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── My Stocks view ─────────────────────────────────────────────────────────────

function MyStocksView({
  digest, loading, onOpen, onRemove,
  query, onQueryChange, suggestions, showSuggestions, onBlurSuggestions, onFocusSuggestions,
  onSelectSuggestion, onAddSubmit, adding, addError, canAdd,
}: {
  digest: DigestItem[];
  loading: boolean;
  onOpen: (t: string) => void;
  onRemove: (t: string) => void;
  query: string;
  onQueryChange: (v: string) => void;
  suggestions: { ticker: string; name: string; exchange: string }[];
  showSuggestions: boolean;
  onBlurSuggestions: () => void;
  onFocusSuggestions: () => void;
  onSelectSuggestion: (s: { ticker: string; name: string }) => void;
  onAddSubmit: (e: React.SyntheticEvent<HTMLFormElement>) => void;
  adding: boolean;
  addError: string;
  canAdd: boolean;
}) {
  const buys  = digest.filter(d => d.analysis?.verdict === "BUY").length;
  const sells = digest.filter(d => d.analysis?.verdict === "SELL").length;

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "30px 32px 56px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: "'IBM Plex Serif',serif", fontWeight: 600, fontSize: 25 }}>My stocks</h1>
          <div style={{ marginTop: 5, fontSize: 13, color: INK3 }}>
            {digest.length} holdings
            {buys  > 0 && <> · <span style={{ color: UP,  fontFamily: "'IBM Plex Mono',monospace" }}>{buys} buy</span></>}
            {sells > 0 && <> · <span style={{ color: DN,  fontFamily: "'IBM Plex Mono',monospace" }}>{sells} sell</span></>}
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "3rem", color: INK3 }}>Loading…</div>
      ) : digest.length === 0 ? (
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "3rem", textAlign: "center", color: INK3 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Add your first stock to get started</div>
          <div style={{ fontSize: 12 }}>Try: NFLX, AAPL, COST, MRVL</div>
        </div>
      ) : (
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1.5fr .65fr 1fr 1.5fr .55fr 1fr .9fr 40px", gap: 12, padding: "11px 20px", font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", color: INK3, background: "#F6F4EE", borderBottom: `1px solid ${BRD}` }}>
            <span>STOCK</span>
            <span>VERDICT</span>
            <span style={{ textAlign: "right" }}>PRICE</span>
            <span>52-WEEK RANGE</span>
            <span style={{ textAlign: "center" }}>RSI</span>
            <span>TREND</span>
            <span>SIGNAL</span>
            <span />
          </div>
          {digest.map((item, i) => {
            const a = item.analysis;
            const risk = riskOf(item);
            const conv = convictionOf(a?.verdict ?? null);
            const dayUp = (a?.day_change_pct ?? 0) >= 0;
            const rsi = a?.rsi ?? null;
            const rsiColor = rsi == null ? INK3 : rsi >= 70 ? DN : rsi <= 30 ? UP : INK;
            const aboveMA50 = a?.ma_50 != null && a?.current_price != null && a.current_price > a.ma_50;
            const hasTrend = a?.ma_50 != null && a?.current_price != null;
            const rangePct = a?.range_position_pct;
            const verdictColor = a?.verdict === "BUY" ? UP : a?.verdict === "SELL" ? DN : a?.verdict === "HOLD" ? AUTO : WARN;
            const verdictBg   = a?.verdict === "BUY" ? "#EAF1EC" : a?.verdict === "SELL" ? "#F4E7E4" : a?.verdict === "HOLD" ? "#E8EEF2" : "#F4EEE2";
            const verdictBd   = a?.verdict === "BUY" ? "#D6E2D7" : a?.verdict === "SELL" ? "#E6D2CC" : a?.verdict === "HOLD" ? "#CDD8E0" : "#E6DBC4";
            return (
              <div key={item.ticker}
                style={{ display: "grid", gridTemplateColumns: "1.5fr .65fr 1fr 1.5fr .55fr 1fr .9fr 40px", gap: 12, padding: "14px 20px", borderTop: i === 0 ? "none" : "1px solid #EDEAE1", alignItems: "center", cursor: "pointer" }}
                onClick={() => onOpen(item.ticker)}
                onMouseOver={e => (e.currentTarget.style.background = "#FCFCFA")}
                onMouseOut={e  => (e.currentTarget.style.background = "transparent")}
              >
                {/* Stock */}
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ font: "600 13.5px/1 'IBM Plex Mono',monospace" }}>{item.ticker}</span>
                    {a?.is_important_day && <span title={a.importance_reason ?? ""} style={{ fontSize: 11 }}>⭐</span>}
                    {item.is_leveraged && <span style={{ fontSize: 9, padding: "2px 5px", background: "rgba(124,58,237,.15)", color: "#a78bfa", borderRadius: 4, fontWeight: 700 }}>3X</span>}
                  </div>
                  <div style={{ fontSize: 11, color: INK3, marginTop: 3 }}>{item.company_name ?? "—"}</div>
                </div>

                {/* Verdict badge */}
                <span style={{ display: "inline-block", fontFamily: "'IBM Plex Mono',monospace", fontSize: 9.5, fontWeight: 700, letterSpacing: ".08em", color: verdictColor, background: verdictBg, border: `1px solid ${verdictBd}`, borderRadius: 20, padding: "4px 8px", whiteSpace: "nowrap" }}>
                  {a?.verdict ?? "—"}
                </span>

                {/* Price + day% */}
                <div style={{ textAlign: "right" }}>
                  <div style={{ font: "500 13px/1 'IBM Plex Mono',monospace" }}>{fmtPrice(a?.current_price ?? null)}</div>
                  <div style={{ font: "500 11px/1 'IBM Plex Mono',monospace", color: dayUp ? UP : DN, marginTop: 4 }}>{fmtPct(a?.day_change_pct ?? null)}</div>
                </div>

                {/* 52-Week Range */}
                <div>
                  {a?.week_52_low != null && a?.week_52_high != null ? (
                    <>
                      <div style={{ display: "flex", justifyContent: "space-between", font: "400 10px/1 'IBM Plex Mono',monospace", color: INK3, marginBottom: 5 }}>
                        <span>{fmtPrice(a.week_52_low)}</span>
                        <span>{fmtPrice(a.week_52_high)}</span>
                      </div>
                      <div style={{ height: 4, background: "#EDEAE1", borderRadius: 4, position: "relative" }}>
                        <div style={{ position: "absolute", top: -2, left: `${Math.max(0, Math.min(100, rangePct ?? 50))}%`, transform: "translateX(-50%)", width: 8, height: 8, borderRadius: "50%", background: AUTO, border: `1.5px solid ${SURF}` }} />
                      </div>
                    </>
                  ) : (
                    <span style={{ fontSize: 11, color: INK3 }}>—</span>
                  )}
                </div>

                {/* RSI */}
                <div style={{ textAlign: "center" }}>
                  <div style={{ font: "600 13px/1 'IBM Plex Mono',monospace", color: rsiColor }}>{rsi != null ? rsi.toFixed(0) : "—"}</div>
                  {rsi != null && <div style={{ fontSize: 9, color: rsiColor, marginTop: 3 }}>{rsi >= 70 ? "OB" : rsi <= 30 ? "OS" : ""}</div>}
                </div>

                {/* Trend */}
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  {hasTrend ? (
                    <>
                      <span style={{ fontSize: 12, color: aboveMA50 ? UP : DN }}>{aboveMA50 ? "↑" : "↓"}</span>
                      <span style={{ fontSize: 11, color: aboveMA50 ? UP : DN, fontFamily: "'IBM Plex Mono',monospace" }}>{aboveMA50 ? "Above" : "Below"} MA50</span>
                    </>
                  ) : (
                    <span style={{ fontSize: 11, color: INK3 }}>—</span>
                  )}
                </div>

                {/* Signal = conviction + risk */}
                <div style={{ display: "flex", flexDirection: "column", gap: 5, alignItems: "flex-start" }}>
                  <span style={{ font: "600 12px/1 'IBM Plex Mono',monospace", color: conv >= 78 ? UP : conv >= 70 ? INK : WARN }}>{conv}/100</span>
                  <span style={riskChip(risk)}>{risk}</span>
                </div>

                {/* Remove */}
                <button
                  onClick={e => { e.stopPropagation(); onRemove(item.ticker); }}
                  title="Remove from watchlist"
                  style={{ background: "none", border: "none", cursor: "pointer", color: INK3, fontSize: 13, padding: 4, borderRadius: 4, opacity: 0.5 }}
                  onMouseOver={e => { e.currentTarget.style.color = DN; e.currentTarget.style.opacity = "1"; }}
                  onMouseOut={e  => { e.currentTarget.style.color = INK3; e.currentTarget.style.opacity = "0.5"; }}
                >✕</button>
              </div>
            );
          })}
        </div>
      )}

      {/* Add stock form */}
      <form onSubmit={onAddSubmit} style={{ display: "flex", gap: 8, marginTop: 16, padding: "14px 16px", background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: "1 1 260px" }}>
          <input
            value={query}
            onChange={e => onQueryChange(e.target.value)}
            onBlur={() => setTimeout(onBlurSuggestions, 150)}
            onFocus={onFocusSuggestions}
            placeholder="Search ticker or company name…"
            autoComplete="off"
            style={{ width: "100%", padding: "8px 12px", background: BG, border: `1px solid ${BRD}`, borderRadius: 7, color: INK, fontSize: 14, fontFamily: "'IBM Plex Sans',sans-serif", boxSizing: "border-box" }}
          />
          {showSuggestions && suggestions.length > 0 && (
            <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 50, background: SURF, border: `1px solid ${BRD}`, borderRadius: 8, overflow: "hidden", boxShadow: "0 8px 24px rgba(0,0,0,.12)" }}>
              {suggestions.map(s => (
                <div key={s.ticker} onMouseDown={() => onSelectSuggestion(s)}
                  style={{ padding: "10px 14px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${BRD}` }}
                  onMouseOver={e => (e.currentTarget.style.background = BG)}
                  onMouseOut={e  => (e.currentTarget.style.background = "transparent")}
                >
                  <div>
                    <span style={{ fontWeight: 700, fontSize: 13, color: INK, fontFamily: "'IBM Plex Mono',monospace" }}>{s.ticker}</span>
                    <span style={{ marginLeft: 8, fontSize: 12, color: INK2 }}>{s.name}</span>
                  </div>
                  <span style={{ fontSize: 11, color: INK3 }}>{s.exchange}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <button type="submit" disabled={adding || !canAdd} style={{ padding: "8px 18px", background: AUTO, color: SURF, border: "none", borderRadius: 7, cursor: canAdd && !adding ? "pointer" : "not-allowed", fontWeight: 600, fontSize: 13, fontFamily: "'IBM Plex Sans',sans-serif", opacity: canAdd && !adding ? 1 : 0.45 }}>
          {adding ? "Adding…" : "+ Add to watchlist"}
        </button>
        {addError && <span style={{ color: DN, fontSize: 12, width: "100%" }}>{addError}</span>}
      </form>
    </div>
  );
}

// ── Discover view ──────────────────────────────────────────────────────────────

function DiscoverView({ digest, onOpen }: { digest: DigestItem[]; onOpen: (t: string) => void }) {
  const picks = [...digest]
    .filter(d => d.analysis?.verdict === "BUY" || d.analysis?.verdict === "HOLD")
    .sort((a, b) => convictionOf(b.analysis?.verdict ?? null) - convictionOf(a.analysis?.verdict ?? null));

  if (picks.length === 0) {
    return (
      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "30px 32px 56px" }}>
        <h1 style={{ margin: 0, fontFamily: "'IBM Plex Serif',serif", fontWeight: 600, fontSize: 25 }}>Discover</h1>
        <div style={{ marginTop: 20, background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "3rem", textAlign: "center", color: INK3 }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>No high-conviction picks yet</div>
          <div style={{ fontSize: 12 }}>Add stocks to your watchlist and run the nightly analysis to see picks here.</div>
        </div>
      </div>
    );
  }

  const hero = picks[0];
  const heroConv = convictionOf(hero.analysis?.verdict ?? null);
  const heroRisk = riskOf(hero);
  const grid = picks.slice(1, 7);

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "30px 32px 56px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: "'IBM Plex Serif',serif", fontWeight: 600, fontSize: 25 }}>Discover</h1>
          <div style={{ marginTop: 5, fontSize: 13, color: INK3 }}>High-conviction ideas from your watchlist, explained in plain words.</div>
        </div>
      </div>

      {/* Hero card */}
      <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 13, padding: "26px 28px", display: "grid", gridTemplateColumns: "1fr 220px", gap: 28, alignItems: "center" }}>
        <div>
          <div style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".13em", textTransform: "uppercase", color: INK3 }}>Top conviction this week</div>
          <div style={{ marginTop: 13, display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span style={{ font: "600 26px/1 'IBM Plex Mono',monospace" }}>{hero.ticker}</span>
            <span style={{ fontSize: 15, color: INK2 }}>{hero.company_name ?? ""}</span>
            <span style={riskChip(heroRisk)}>{heroRisk} RISK</span>
          </div>
          <div style={{ marginTop: 12, fontFamily: "'IBM Plex Serif',serif", fontWeight: 600, fontSize: 21, letterSpacing: "-.01em" }}>{verdictLine(hero.analysis?.verdict ?? null)}</div>
          {hero.analysis?.reasoning && (
            <div style={{ marginTop: 8, fontSize: 14, color: "#3A3833", maxWidth: "52ch", lineHeight: 1.5 }}>
              {hero.analysis.reasoning.slice(0, 220)}{hero.analysis.reasoning.length > 220 ? "…" : ""}
            </div>
          )}
          <div style={{ marginTop: 20, display: "flex", gap: 10 }}>
            <button onClick={() => onOpen(hero.ticker)} style={{ font: "500 13px 'IBM Plex Sans'", color: SURF, background: AUTO, border: "1px solid #34505F", borderRadius: 8, padding: "9px 17px", cursor: "pointer" }}>
              See full analysis →
            </button>
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "center" }}>
          <ConvRing value={heroConv} color={RISK_META[heroRisk].c} size={128} />
        </div>
      </div>

      {/* Pick grid */}
      {grid.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginTop: 16 }}>
          {grid.map(item => {
            const conv = convictionOf(item.analysis?.verdict ?? null);
            const risk = riskOf(item);
            const up   = (item.analysis?.day_change_pct ?? 0) >= 0;
            return (
              <div key={item.ticker}
                onClick={() => onOpen(item.ticker)}
                style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "17px 18px", cursor: "pointer", display: "flex", flexDirection: "column", gap: 10 }}
                onMouseOver={e => (e.currentTarget.style.borderColor = "#C9C5BA")}
                onMouseOut={e  => (e.currentTarget.style.borderColor = BRD)}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <span style={{ font: "600 15px/1 'IBM Plex Mono',monospace" }}>{item.ticker}</span>
                    <span style={{ fontSize: 12, color: INK3, marginLeft: 6 }}>{item.company_name ?? ""}</span>
                  </div>
                  <span style={{ font: "600 15px/1 'IBM Plex Mono',monospace", color: conv >= 78 ? UP : conv >= 70 ? INK : WARN }}>{conv}</span>
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: INK }}>{verdictLine(item.analysis?.verdict ?? null)}</div>
                {item.analysis?.reasoning && (
                  <div style={{ fontSize: 12.5, color: INK2, lineHeight: 1.45, flex: 1 }}>
                    {item.analysis.reasoning.slice(0, 110)}{item.analysis.reasoning.length > 110 ? "…" : ""}
                  </div>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={riskChip(risk)}>{risk}</span>
                  <MiniSpark up={up} />
                  <span style={{ fontSize: 12, color: AUTO, fontWeight: 600 }}>Analysis →</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Compare view ───────────────────────────────────────────────────────────────

function CompareView({ autoTrades, copilotTrades, digest, onOpen }: {
  autoTrades: SimTrade[];
  copilotTrades: SimTrade[];
  digest: DigestItem[];
  onOpen: (t: string) => void;
}) {
  const [tf, setTf] = useState("All");

  const allTrades = [
    ...autoTrades.map(t => ({ ...t, mode: "AUTO" as const })),
    ...copilotTrades.map(t => ({ ...t, mode: "COPI" as const })),
  ].sort((a, b) => new Date(b.trade_date).getTime() - new Date(a.trade_date).getTime());

  const autoRemaining   = autoTrades.length > 0 ? 10000 : 10000;
  const copilotRemaining = copilotTrades.length > 0 ? 10000 : 10000;

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "30px 32px 56px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: "'IBM Plex Serif',serif", fontWeight: 600, fontSize: 25 }}>Autopilot vs Copilot</h1>
          <div style={{ marginTop: 5, fontSize: 13, color: INK3 }}>Both started at $10,000. Same prices, real AI decisions.</div>
        </div>
        <div style={{ display: "flex", border: "1px solid #DAD7CE", borderRadius: 8, overflow: "hidden", background: SURF }}>
          {["1M", "3M", "1Y", "All"].map((label, idx) => (
            <button key={label} onClick={() => setTf(label)} style={{
              font: "500 12px 'IBM Plex Mono',monospace", color: tf === label ? INK : INK2,
              background: tf === label ? "#ECEAE3" : "none", fontWeight: tf === label ? 600 : 500,
              padding: "7px 13px", border: "none", borderRight: idx < 3 ? `1px solid ${BRD}` : "none", cursor: "pointer",
            }}>{label}</button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 13, padding: "20px 22px" }}>
        <div style={{ display: "flex", gap: 24, marginBottom: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}><span style={{ width: 16, height: 3, background: AUTO, borderRadius: 2, display: "inline-block" }} /><span style={{ fontSize: 12.5, color: "#3A3833" }}>Autopilot</span></div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}><span style={{ width: 16, height: 3, background: COPI, borderRadius: 2, display: "inline-block" }} /><span style={{ fontSize: 12.5, color: "#3A3833" }}>Copilot</span></div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}><span style={{ width: 16, height: 0, borderTop: "2px dashed #9C998E", display: "inline-block" }} /><span style={{ fontSize: 12.5, color: "#3A3833" }}>Your picks</span></div>
        </div>
        <svg viewBox="0 0 980 300" preserveAspectRatio="none" style={{ width: "100%", height: 280, display: "block" }}>
          {[40, 110, 180, 250].map(y => <line key={y} x1="0" y1={y} x2="980" y2={y} stroke="#EDEAE1" strokeWidth="1" />)}
          <path d="M0,250 L245,232 L490,200 L735,148 L980,100 L980,300 L0,300 Z" fill={AUTO + "18"} />
          <polyline points="0,250 245,232 490,200 735,148 980,100" fill="none" stroke={AUTO} strokeWidth="2.4" />
          <polyline points="0,250 245,238 490,218 735,178 980,140" fill="none" stroke={COPI} strokeWidth="2.4" />
          <polyline points="0,250 245,244 490,234 735,218 980,196" fill="none" stroke="#9C998E" strokeWidth="1.8" strokeDasharray="6 5" />
        </svg>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, font: "500 10.5px 'IBM Plex Mono',monospace", color: INK3 }}>
          <span>Start</span><span>Q1</span><span>Q2</span><span>Q3</span><span>Now</span>
        </div>
      </div>

      {/* Stat row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginTop: 16 }}>
        <div style={{ background: "#F5F8FA", border: "1px solid #D7E1E8", borderRadius: 11, padding: "15px 18px" }}>
          <div style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".12em", color: AUTO }}>AUTOPILOT</div>
          <div style={{ marginTop: 9, font: "600 21px/1 'IBM Plex Mono',monospace" }}>{fmtMoney(autoRemaining)}</div>
          <div style={{ marginTop: 7, fontSize: 12, color: "#43586A" }}>{autoTrades.length > 0 ? `${autoTrades.length} move${autoTrades.length > 1 ? "s" : ""} made` : "No trades yet"}</div>
        </div>
        <div style={{ background: "#F4F8F4", border: "1px solid #D6E2D7", borderRadius: 11, padding: "15px 18px" }}>
          <div style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".12em", color: COPI }}>COPILOT</div>
          <div style={{ marginTop: 9, font: "600 21px/1 'IBM Plex Mono',monospace" }}>{fmtMoney(copilotRemaining)}</div>
          <div style={{ marginTop: 7, fontSize: 12, color: "#3E5645" }}>{copilotTrades.length > 0 ? `You acted on ${copilotTrades.length} suggestion${copilotTrades.length > 1 ? "s" : ""}` : "No decisions yet"}</div>
        </div>
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "15px 18px" }}>
          <div style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".12em", color: INK3 }}>YOUR PICKS</div>
          <div style={{ marginTop: 9, font: "600 21px/1 'IBM Plex Mono',monospace" }}>{digest.length} stocks</div>
          <div style={{ marginTop: 7, fontSize: 12, color: INK2 }}>The baseline both AIs track</div>
        </div>
      </div>

      {/* Trade ledger */}
      <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, marginTop: 16, padding: "6px 4px 8px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px 12px" }}>
          <span style={{ fontSize: 15, fontWeight: 600 }}>Every AI move</span>
        </div>
        {allTrades.length === 0 ? (
          <div style={{ padding: "16px 18px", borderTop: "1px solid #EDEAE1", fontSize: 13, color: INK3 }}>No simulation trades yet — analysis runs nightly.</div>
        ) : allTrades.slice(0, 20).map(t => {
          const isBuy  = t.action === "BUY";
          const mC  = t.mode === "AUTO" ? AUTO : COPI;
          const mBg = t.mode === "AUTO" ? "#EAF0F3" : "#EAF1EC";
          const mBd = t.mode === "AUTO" ? "#D7E1E8" : "#D6E2D7";
          return (
            <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 13, padding: "12px 18px", borderTop: "1px solid #EDEAE1" }}>
              <span style={{ font: "600 9px/1 'IBM Plex Mono',monospace", letterSpacing: ".06em", color: mC, background: mBg, border: `1px solid ${mBd}`, borderRadius: 5, padding: "4px 6px", width: 40, textAlign: "center" as const }}>{t.mode}</span>
              <span style={{ fontSize: 10, color: isBuy ? UP : DN, width: 12 }}>{isBuy ? "▲" : "▼"}</span>
              <span onClick={() => onOpen(t.ticker)} style={{ font: "500 12.5px 'IBM Plex Mono',monospace", width: 54, cursor: "pointer", color: AUTO }}>{t.ticker}</span>
              <span style={{ flex: 1, fontSize: 12.5, color: INK2 }}>{isBuy ? "Bought" : "Sold"} {t.shares.toFixed(2)} sh @ ${t.price.toFixed(2)}</span>
              {t.reasoning && <span style={{ fontSize: 11, color: INK3, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.reasoning.slice(0, 60)}</span>}
              <span style={{ fontSize: 11, color: INK3, fontFamily: "'IBM Plex Mono',monospace", flexShrink: 0 }}>{relativeDate(t.trade_date)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Dashboard view ─────────────────────────────────────────────────────────────

function DashboardView({ digest, autoPortfolio, copilotPortfolio, autoTrades, copilotTrades, userName, onOpen, onApprove, onSkip, onGoCompare }: {
  digest: DigestItem[];
  autoPortfolio: SimPortfolioItem[];
  copilotPortfolio: SimPortfolioItem[];
  autoTrades: SimTrade[];
  copilotTrades: SimTrade[];
  userName: string;
  onOpen: (t: string) => void;
  onApprove: (t: string, analysisId: string) => void;
  onSkip: (t: string, analysisId: string) => void;
  onGoCompare: () => void;
}) {
  const h = new Date().getHours();
  const greeting = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  const attention = digest.filter(d => d.analysis && (d.analysis.verdict === "BUY" || d.analysis.verdict === "SELL")).slice(0, 3);
  const recentTrades = autoTrades.slice(0, 4);
  const autoBalance   = autoPortfolio[0]?.virtual_cash ?? 10000;
  const copilotBalance = copilotPortfolio[0]?.virtual_cash ?? 10000;
  const buys  = digest.filter(d => d.analysis?.verdict === "BUY").length;
  const sells = digest.filter(d => d.analysis?.verdict === "SELL").length;

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "30px 32px 56px" }}>
      {/* Greeting */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 22 }}>
        <div>
          <h1 style={{ margin: 0, fontFamily: "'IBM Plex Serif',serif", fontWeight: 600, fontSize: 25, letterSpacing: "-.01em" }}>{greeting}, {userName.split(" ")[0]}</h1>
          <div style={{ marginTop: 5, fontSize: 13, color: INK3 }}>{today}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, font: "500 11.5px/1 'IBM Plex Mono',monospace", color: INK2 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: AUTO, display: "inline-block" }} />AUTOPILOT ON</span>
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: COPI, display: "inline-block" }} />COPILOT ON</span>
        </div>
      </div>

      {/* 3 status cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }}>
        {/* Your portfolio */}
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "18px 20px" }}>
          <div style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".13em", textTransform: "uppercase", color: INK3 }}>Your portfolio</div>
          <div style={{ marginTop: 12, font: "600 27px/1 'IBM Plex Mono',monospace", letterSpacing: "-.02em" }}>{digest.length} stocks</div>
          <div style={{ marginTop: 7, fontSize: 12.5 }}>
            {buys  > 0 && <span style={{ color: UP,  fontFamily: "'IBM Plex Mono'" }}>{buys} buy{buys  > 1 ? "s" : ""} </span>}
            {sells > 0 && <span style={{ color: DN,  fontFamily: "'IBM Plex Mono'" }}>{sells} sell{sells > 1 ? "s" : ""} </span>}
            {buys === 0 && sells === 0 && <span style={{ color: INK3 }}>No signals today</span>}
          </div>
          <svg viewBox="0 0 220 34" preserveAspectRatio="none" style={{ width: "100%", height: 34, marginTop: 12, display: "block" }}>
            <polyline points="0,26 31,23 62,25 93,18 124,21 155,14 186,17 220,10" fill="none" stroke="#9C998E" strokeWidth="1.6" />
          </svg>
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #EDEAE1", fontSize: 12.5, color: INK2 }}>
            {attention.length > 0 ? `${attention.length} stock${attention.length > 1 ? "s" : ""} need your attention.` : "All clear — nothing needs you today."}
          </div>
        </div>

        {/* Autopilot */}
        <div style={{ background: "#F5F8FA", border: "1px solid #D7E1E8", borderRadius: 11, padding: "18px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: AUTO, display: "inline-block" }} />
            <span style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".13em", textTransform: "uppercase", color: AUTO }}>Autopilot</span>
          </div>
          <div style={{ marginTop: 12, font: "600 27px/1 'IBM Plex Mono',monospace", letterSpacing: "-.02em" }}>{fmtMoney(autoBalance)}</div>
          <div style={{ marginTop: 7, fontSize: 12.5, color: INK3 }}>virtual cash remaining</div>
          <svg viewBox="0 0 220 34" preserveAspectRatio="none" style={{ width: "100%", height: 34, marginTop: 12, display: "block" }}>
            <polyline points="0,28 31,22 62,25 93,13 124,19 155,9 186,7 220,8" fill="none" stroke={AUTO} strokeWidth="1.8" />
          </svg>
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #DDE6EB", fontSize: 12.5, color: "#43586A" }}>
            {autoTrades.length > 0 ? `${autoTrades.length} move${autoTrades.length > 1 ? "s" : ""} made so far.` : "Trading on its own — watching your watchlist."}
          </div>
        </div>

        {/* Copilot */}
        <div style={{ background: "#F4F8F4", border: "1px solid #D6E2D7", borderRadius: 11, padding: "18px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: COPI, display: "inline-block" }} />
            <span style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".13em", textTransform: "uppercase", color: COPI }}>Copilot</span>
          </div>
          <div style={{ marginTop: 12, font: "600 27px/1 'IBM Plex Mono',monospace", letterSpacing: "-.02em" }}>{fmtMoney(copilotBalance)}</div>
          <div style={{ marginTop: 7, fontSize: 12.5, color: INK3 }}>virtual cash · you decide</div>
          <svg viewBox="0 0 220 34" preserveAspectRatio="none" style={{ width: "100%", height: 34, marginTop: 12, display: "block" }}>
            <polyline points="0,28 31,24 62,26 93,17 124,21 155,14 186,13 220,11" fill="none" stroke={COPI} strokeWidth="1.8" />
          </svg>
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #DBE6DC", fontSize: 12.5, color: "#3E5645" }}>
            {attention.length > 0 ? <><b style={{ fontWeight: 600 }}>{attention.length} suggestion{attention.length > 1 ? "s" : ""}</b> waiting for your call.</> : "No pending suggestions."}
          </div>
        </div>
      </div>

      {/* Attention + Activity */}
      <div style={{ display: "grid", gridTemplateColumns: "1.45fr 1fr", gap: 16, marginTop: 16 }}>
        {/* Needs attention */}
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "6px 4px 8px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "13px 18px 11px" }}>
            <span style={{ fontSize: 15, fontWeight: 600 }}>Needs your attention</span>
            <span style={{ font: "600 10px/1 'IBM Plex Mono',monospace", letterSpacing: ".1em", color: COPI, background: "#EAF1EC", border: "1px solid #D6E2D7", borderRadius: 20, padding: "4px 9px" }}>COPILOT · {attention.length}</span>
          </div>
          {attention.length === 0 ? (
            <div style={{ padding: "16px 18px", borderTop: "1px solid #EDEAE1", fontSize: 13, color: INK3 }}>All clear — no action needed today.</div>
          ) : attention.map(item => {
            const a = item.analysis!;
            return (
              <div key={item.ticker} style={{ display: "flex", alignItems: "center", gap: 13, padding: "13px 18px", borderTop: "1px solid #EDEAE1" }}>
                <div onClick={() => onOpen(item.ticker)} style={{ cursor: "pointer", width: 58, flexShrink: 0 }}>
                  <div style={{ font: "600 13px/1 'IBM Plex Mono',monospace" }}>{item.ticker}</div>
                  <div style={{ fontSize: 10.5, color: INK3, marginTop: 3 }}>{(item.company_name ?? item.ticker).split(" ")[0]}</div>
                </div>
                <div style={{ flex: 1, fontSize: 13, color: "#3A3833" }}>{a.verdict === "BUY" ? "Buy — strong conviction" : "Sell — exit suggested"}</div>
                <span style={riskChip(riskOf(item))}>{riskOf(item)}</span>
                <div style={{ display: "flex", gap: 7, flexShrink: 0 }}>
                  <button onClick={() => onApprove(item.ticker, a.id)} style={{ font: "500 11.5px 'IBM Plex Sans'", color: SURF, background: AUTO, border: "1px solid #34505F", borderRadius: 7, padding: "6px 13px", cursor: "pointer" }}>Approve</button>
                  <button onClick={() => onSkip(item.ticker, a.id)} style={{ font: "500 11.5px 'IBM Plex Sans'", color: INK2, background: "none", border: "1px solid #DAD7CE", borderRadius: 7, padding: "6px 12px", cursor: "pointer" }}>Skip</button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Autopilot activity */}
        <div style={{ background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "6px 4px 4px" }}>
          <div style={{ padding: "13px 18px 11px", fontSize: 15, fontWeight: 600 }}>Autopilot this week</div>
          {recentTrades.length === 0 ? (
            <div style={{ padding: "16px 18px", borderTop: "1px solid #EDEAE1", fontSize: 13, color: INK3 }}>No moves yet — autopilot is watching your stocks.</div>
          ) : recentTrades.map(t => (
            <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 18px", borderTop: "1px solid #EDEAE1" }}>
              <span style={{ fontSize: 10, color: t.action === "BUY" ? UP : DN }}>{t.action === "BUY" ? "▲" : "▼"}</span>
              <span style={{ fontSize: 13, color: "#3A3833" }}>{t.action === "BUY" ? "Bought" : "Sold"}</span>
              <span onClick={() => onOpen(t.ticker)} style={{ font: "500 12.5px 'IBM Plex Mono',monospace", cursor: "pointer", color: AUTO }}>{t.ticker}</span>
              <span style={{ marginLeft: "auto", fontSize: 11, color: INK3, fontFamily: "'IBM Plex Mono',monospace" }}>{relativeDate(t.trade_date)}</span>
            </div>
          ))}
          <div style={{ padding: "12px 18px", borderTop: "1px solid #EDEAE1", fontSize: 12, color: "#43586A" }}>
            {autoTrades.length > 0 ? `${autoTrades.length} total move${autoTrades.length > 1 ? "s" : ""} on autopilot.` : "Add stocks to get started."}
          </div>
        </div>
      </div>

      {/* Compare teaser */}
      <button onClick={onGoCompare} style={{ width: "100%", textAlign: "left", marginTop: 16, background: SURF, border: `1px solid ${BRD}`, borderRadius: 11, padding: "15px 20px", display: "flex", alignItems: "center", gap: 14, cursor: "pointer", fontFamily: "'IBM Plex Sans',sans-serif" }}>
        <span style={{ font: "600 10.5px/1 'IBM Plex Mono',monospace", letterSpacing: ".12em", color: INK3, flexShrink: 0 }}>HEAD-TO-HEAD</span>
        <span style={{ fontSize: 14, color: "#3A3833" }}>Compare autopilot vs copilot — see every decision and how it played out.</span>
        <span style={{ marginLeft: "auto", fontSize: 13, color: AUTO, fontWeight: 600, flexShrink: 0 }}>See the comparison →</span>
      </button>
    </div>
  );
}

// ── Top bar ────────────────────────────────────────────────────────────────────

function TopBar({ activeView, onTab, userName, autoPortfolio, copilotPortfolio }: {
  activeView: View;
  onTab: (v: View) => void;
  userName: string;
  autoPortfolio: SimPortfolioItem[];
  copilotPortfolio: SimPortfolioItem[];
}) {
  const autoBalance    = autoPortfolio[0]?.virtual_cash    ?? 10000;
  const copilotBalance = copilotPortfolio[0]?.virtual_cash ?? 10000;
  const initials = userName.split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase() || "?";

  const tabs: [Exclude<View, "detail">, string][] = [
    ["dashboard", "Dashboard"], ["stocks", "My Stocks"], ["discover", "Discover"], ["compare", "Compare"],
  ];

  return (
    <header style={{ position: "sticky", top: 0, zIndex: 40, background: SURF, borderBottom: "1px solid #E0DDD3" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", height: 60, display: "flex", alignItems: "center", gap: 26, padding: "0 32px" }}>
        <div onClick={() => onTab("dashboard")} style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer", flexShrink: 0 }}>
          <span style={{ width: 22, height: 22, borderRadius: 5, background: AUTO, display: "flex", alignItems: "center", justifyContent: "center", color: SURF, font: "600 12px/1 'IBM Plex Mono',monospace" }}>◆</span>
          <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-.01em" }}>Stock Copilot</span>
        </div>
        <nav style={{ display: "flex", gap: 2, height: "100%" }}>
          {tabs.map(([id, label]) => (
            <button key={id} onClick={() => onTab(id)} style={{
              fontFamily: "'IBM Plex Sans',sans-serif", fontSize: 14, padding: "0 14px", height: 60, border: "none",
              borderBottom: activeView === id ? `2px solid ${AUTO}` : "2px solid transparent",
              background: "none", cursor: "pointer",
              color: activeView === id ? INK : INK2,
              fontWeight: activeView === id ? 600 : 500,
            }}>{label}</button>
          ))}
        </nav>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.15 }}>
            <span style={{ font: "500 9px/1 'IBM Plex Mono',monospace", letterSpacing: ".12em", color: INK3 }}>VIRTUAL BALANCE</span>
            <span style={{ font: "500 14px/1 'IBM Plex Mono',monospace", marginTop: 3 }}>{fmtMoney(autoBalance + copilotBalance)}</span>
          </div>
          <span title={userName} style={{ width: 32, height: 32, borderRadius: "50%", background: "#ECEAE3", border: `1px solid ${BRD}`, display: "flex", alignItems: "center", justifyContent: "center", font: "600 12px 'IBM Plex Sans',sans-serif", color: INK2, flexShrink: 0 }}>{initials}</span>
          <button onClick={() => signOut({ callbackUrl: "/signin" })} style={{ font: "500 11.5px 'IBM Plex Sans',sans-serif", color: INK2, background: "none", border: "1px solid #DAD7CE", borderRadius: 7, padding: "5px 10px", cursor: "pointer" }}>Sign out</button>
        </div>
      </div>
    </header>
  );
}

// ── Main export ────────────────────────────────────────────────────────────────

export default function DashboardClient({ userName, idToken }: { userName: string; idToken: string }) {
  const router = useRouter();
  const [view, setView]                   = useState<View>("dashboard");
  const [prevView, setPrevView]           = useState<View>("dashboard");
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  const [digest, setDigest]               = useState<DigestItem[]>([]);
  const [loading, setLoading]             = useState(true);
  const [autoPortfolio, setAutoPortfolio] = useState<SimPortfolioItem[]>([]);
  const [copilotPortfolio, setCopilotPortfolio] = useState<SimPortfolioItem[]>([]);
  const [autoTrades, setAutoTrades]       = useState<SimTrade[]>([]);
  const [copilotTrades, setCopilotTrades] = useState<SimTrade[]>([]);

  const [ticker, setTicker]               = useState("");
  const [companyName, setCompanyName]     = useState("");
  const [query, setQuery]                 = useState("");
  const [suggestions, setSuggestions]     = useState<{ ticker: string; name: string; exchange: string }[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [adding, setAdding]               = useState(false);
  const [addError, setAddError]           = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { fetchAll(); }, []);

  async function fetchAll() {
    setLoading(true);
    const p = encodeURIComponent(idToken);
    try {
      const [dR, aP, cP, aT, cT] = await Promise.all([
        fetch(`${API}/analysis/digest?id_token=${p}`),
        fetch(`${API}/simulation/autopilot/portfolio?id_token=${p}`),
        fetch(`${API}/simulation/copilot/portfolio?id_token=${p}`),
        fetch(`${API}/simulation/autopilot/trades?id_token=${p}`),
        fetch(`${API}/simulation/copilot/trades?id_token=${p}`),
      ]);
      if (dR.ok) setDigest(await dR.json());
      if (aP.ok) setAutoPortfolio(await aP.json());
      if (cP.ok) setCopilotPortfolio(await cP.json());
      if (aT.ok) setAutoTrades(await aT.json());
      if (cT.ok) setCopilotTrades(await cT.json());
    } finally { setLoading(false); }
  }

  function openDetail(t: string) {
    setPrevView(view === "detail" ? prevView : view);
    setSelectedTicker(t);
    setView("detail");
  }

  function goTab(v: View) {
    if (v !== "detail") setPrevView(v);
    setView(v);
  }

  async function handleChat(t: string) {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ticker: t }),
    });
    if (r.ok) { const conv = await r.json(); router.push(`/chat?conv=${conv.id}`); }
  }

  async function handleRemove(t: string) {
    try {
      const r = await fetch(`${API}/watchlist/${encodeURIComponent(t)}?id_token=${encodeURIComponent(idToken)}`, { method: "DELETE" });
      if (r.ok) fetchAll();
    } catch {}
  }

  async function handleApprove(t: string, analysisId: string) {
    await fetch(`${API}/simulation/copilot/decide?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId, ticker: t, decision: "approve" }),
    });
    fetchAll();
  }

  async function handleSkip(t: string, analysisId: string) {
    await fetch(`${API}/simulation/copilot/decide?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_id: analysisId, ticker: t, decision: "skip" }),
    });
    fetchAll();
  }

  function handleSearchInput(val: string) {
    setQuery(val); setTicker(""); setCompanyName(""); setAddError("");
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!val.trim()) { setSuggestions([]); setShowSuggestions(false); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/watchlist/search?q=${encodeURIComponent(val)}&id_token=${encodeURIComponent(idToken)}`);
        if (r.ok) { setSuggestions(await r.json()); setShowSuggestions(true); }
      } catch {}
    }, 300);
  }

  function handleSelectSuggestion(s: { ticker: string; name: string }) {
    setTicker(s.ticker); setCompanyName(s.name);
    setQuery(`${s.ticker} — ${s.name}`);
    setSuggestions([]); setShowSuggestions(false);
  }

  async function handleAddSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    // Accept suggestion-selected ticker OR raw typed text (first word, uppercased)
    const effectiveTicker = ticker.trim() || query.trim().split(/[\s—\-–]/)[0].trim().toUpperCase();
    if (!effectiveTicker) return;
    setAdding(true); setAddError("");
    try {
      const r = await fetch(`${API}/watchlist?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: effectiveTicker, company_name: companyName || null }),
      });
      if (r.ok) { setTicker(""); setCompanyName(""); setQuery(""); fetchAll(); }
      else { const d = await r.json(); setAddError(d.detail || "Failed to add."); }
    } finally { setAdding(false); }
  }

  const canAdd = !!(ticker.trim() || query.trim());

  const activeTabView: View = view === "detail" ? prevView : view;

  const selectedItem: DigestItem = selectedTicker
    ? (digest.find(d => d.ticker === selectedTicker) ?? { ticker: selectedTicker, company_name: null, is_leveraged: false, analysis: null })
    : { ticker: "", company_name: null, is_leveraged: false, analysis: null };

  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: "'IBM Plex Sans',system-ui,sans-serif", color: INK, display: "flex", flexDirection: "column" }}>
      <TopBar
        activeView={activeTabView} onTab={goTab} userName={userName}
        autoPortfolio={autoPortfolio} copilotPortfolio={copilotPortfolio}
      />
      <main style={{ flex: 1 }}>
        {view === "dashboard" && (
          <DashboardView
            digest={digest} autoPortfolio={autoPortfolio} copilotPortfolio={copilotPortfolio}
            autoTrades={autoTrades} copilotTrades={copilotTrades}
            userName={userName} onOpen={openDetail}
            onApprove={handleApprove} onSkip={handleSkip} onGoCompare={() => goTab("compare")}
          />
        )}
        {view === "stocks" && (
          <MyStocksView
            digest={digest} loading={loading} onOpen={openDetail} onRemove={handleRemove}
            query={query} onQueryChange={handleSearchInput}
            suggestions={suggestions} showSuggestions={showSuggestions}
            onBlurSuggestions={() => setShowSuggestions(false)}
            onFocusSuggestions={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            onSelectSuggestion={handleSelectSuggestion}
            onAddSubmit={handleAddSubmit} adding={adding} addError={addError} canAdd={canAdd}
          />
        )}
        {view === "discover" && (
          <DiscoverView digest={digest} onOpen={openDetail} />
        )}
        {view === "compare" && (
          <CompareView autoTrades={autoTrades} copilotTrades={copilotTrades} digest={digest} onOpen={openDetail} />
        )}
        {view === "detail" && selectedTicker && (
          <StockDetailView
            item={selectedItem}
            onBack={() => setView(prevView)}
            onChat={() => handleChat(selectedItem.ticker)}
          />
        )}
      </main>
    </div>
  );
}
