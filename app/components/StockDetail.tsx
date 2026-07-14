"use client";
/**
 * Shared stock detail card — the expanded per-ticker view (story column, data rail,
 * fundamentals, past analyses + AI report). Rendered by the Stocks tab and the
 * chat page's slide-over panel: one source of truth so the two can never drift.
 */
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

export const MONO = "'IBM Plex Mono', monospace";
export const SANS = "'IBM Plex Sans', sans-serif";
export const SERIF = "'IBM Plex Serif', serif";

export interface Analysis {
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
  sp500_day_chg: number | null;
  sector_etf: string | null;
  sector_day_chg: number | null;
  relative_strength_1d: number | null;
  sp500_52w_change: number | null;
  stock_52w_change: number | null;
  sp500_5y_change: number | null;
  stock_5y_change: number | null;
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
  reasoning_simple: string | null;
  bull_case_simple: string | null;
  bear_case_simple: string | null;
  thesis_invalidation_simple: string | null;
  news_summary_simple: string | null;
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
  verdict_a: string | null;
  verdict_b: string | null;
  verdict_agreement: boolean | null;
  split_reason: string | null;
}

export interface StockReport {
  id: string;
  ticker: string;
  report_date: string;
  content: string;
  analyses_count: number | null;
  created_at: string;
}



export const VERDICT_META: Record<string, { color: string; bg: string; bd: string; label: string }> = {
  BUY:   { color: "var(--t-green)", bg: "var(--t-green-bg)", bd: "var(--t-green-border)", label: "BUY"   },
  HOLD:  { color: "var(--t-yellow)", bg: "var(--t-yellow-bg)", bd: "var(--t-yellow-border)", label: "HOLD"  },
  SELL:  { color: "var(--t-red)", bg: "var(--t-red-bg)", bd: "var(--t-red-border)", label: "SELL"  },
  WATCH: { color: "var(--t-text-muted)", bg: "var(--t-surface-warm)", bd: "var(--t-border)", label: "WATCH" },
};


export function RangeBar({ lo, hi, pct }: { lo: number; hi: number; pct: number }) {
  const clamp = Math.max(0, Math.min(100, pct));
  const dotColor = clamp < 33 ? "var(--t-green)" : clamp < 67 ? "var(--t-yellow)" : "var(--t-red)";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
      <div style={{ position: "relative", height: 5, background: "var(--t-border)", borderRadius: 99 }}>
        <div style={{
          position: "absolute", left: 0, width: `${clamp}%`, height: "100%",
          background: dotColor, borderRadius: 99, opacity: 0.3,
        }} />
        <div style={{
          position: "absolute", left: `${clamp}%`, top: "50%",
          transform: "translate(-50%, -50%)",
          width: 10, height: 10, borderRadius: "50%",
          background: dotColor, border: "2px solid var(--t-surface)", zIndex: 1,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.67rem", color: "var(--t-text-muted)", fontFamily: MONO }}>
        <span>${lo.toFixed(0)}</span>
        <span style={{ color: dotColor, fontWeight: 600 }}>{clamp.toFixed(0)}%</span>
        <span>${hi.toFixed(0)}</span>
      </div>
    </div>
  );
}



export function ExpandedDetail({ a, isMobile, changeSummary, daysSinceRead, idToken, txCacheRef }: {
  a: Analysis; isMobile: boolean;
  changeSummary?: string | null; daysSinceRead?: number | null;
  idToken: string;
  txCacheRef: React.MutableRefObject<Record<string, Record<string, string | null>>>;
}) {
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [mode, setMode] = useState<"technical" | "simple">("simple");
  const [translating, setTranslating] = useState(false);

  // Seed local cache from the shared ref so re-expanding a card is free
  const [txCache, setTxCache] = useState<Record<string, Record<string, string | null>>>(() => {
    const seed: Record<string, Record<string, string | null>> = {};
    for (const [k, v] of Object.entries(txCacheRef.current)) {
      if (k.startsWith(`${a.id}:`)) seed[k.slice(a.id.length + 1)] = v;
    }
    return seed;
  });

  const txKey = `${lang}:${mode}`;
  const tx = txCache[txKey] ?? {};

  // Simple English fields are pre-generated by the nightly job — no API call needed
  useEffect(() => {
    if (a.reasoning_simple) setMode("simple"); // data is ready, just switch mode
    else applyTranslation("en", "simple");     // fallback: fetch on-demand (older analyses)
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function applyTranslation(nextLang: "en" | "hi", nextMode: "technical" | "simple") {
    const key = `${nextLang}:${nextMode}`;
    // English simple is served from DB fields — no translate call needed
    if (key === "en:simple" && a.reasoning_simple) { setLang(nextLang); setMode(nextMode); return; }
    if (key === "en:technical") { setLang(nextLang); setMode(nextMode); return; }
    if (txCache[key]) { setLang(nextLang); setMode(nextMode); return; }
    setTranslating(true);
    try {
      const r = await fetch(`${API}/translate?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: a.ticker,
          language: nextLang,
          mode: nextMode,
          fields: {
            reasoning: a.reasoning,
            bull_case: a.bull_case,
            bear_case: a.bear_case,
            thesis_invalidation: a.thesis_invalidation,
            news_summary: a.news_summary,
          },
        }),
      });
      if (r.ok) {
        const { fields } = await r.json();
        setTxCache(prev => ({ ...prev, [key]: fields }));
        txCacheRef.current[`${a.id}:${key}`] = fields; // persist across collapse/re-expand
      }
    } finally {
      setTranslating(false);
      setLang(nextLang);
      setMode(nextMode);
    }
  }

  // For English simple mode, prefer DB pre-generated fields (instant, no API call)
  const useDbSimple = lang === "en" && mode === "simple";
  const reasoning          = tx.reasoning           ?? (useDbSimple ? a.reasoning_simple          : null) ?? a.reasoning;
  const bull_case          = tx.bull_case            ?? (useDbSimple ? a.bull_case_simple           : null) ?? a.bull_case;
  const bear_case          = tx.bear_case            ?? (useDbSimple ? a.bear_case_simple           : null) ?? a.bear_case;
  const thesis_invalidation = tx.thesis_invalidation ?? (useDbSimple ? a.thesis_invalidation_simple : null) ?? a.thesis_invalidation;
  const news_summary       = tx.news_summary         ?? (useDbSimple ? a.news_summary_simple        : null) ?? a.news_summary;

  let events: Array<{ date: string; description: string }> = [];
  try { if (a.events_json) events = JSON.parse(a.events_json).slice(0, 3); } catch {}

  const secLabel: React.CSSProperties = {
    fontSize: "0.7rem", color: "var(--t-text-muted)", fontWeight: 600,
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
    GREAT: { label: "Great Entry",       color: "var(--t-green)", bg: "var(--t-green-bg)", bd: "var(--t-green-mid)" },
    FAIR:  { label: "Fair Entry",        color: "var(--t-yellow)", bg: "var(--t-yellow-bg)", bd: "var(--t-yellow-border)" },
    WAIT:  { label: "Wait for Pullback", color: "var(--t-red)", bg: "var(--t-red-bg)", bd: "var(--t-red-border)" },
  };
  const HF_META: Record<string, { label: string; color: string; bg: string; bd: string }> = {
    HOLD_AND_FORGET: { label: "Hold & Forget ✓", color: "var(--t-green)", bg: "var(--t-green-bg)", bd: "var(--t-green-mid)" },
    CHECK_MONTHLY:   { label: "Check Monthly",   color: "var(--t-yellow)", bg: "var(--t-yellow-bg)", bd: "var(--t-yellow-border)" },
    WATCH_CLOSELY:   { label: "Watch Closely",   color: "var(--t-red)", bg: "var(--t-red-bg)", bd: "var(--t-red-border)" },
  };

  const eqMeta  = a.entry_quality         ? EQ_META[a.entry_quality]                : null;
  const hfMeta  = a.hold_and_forget_rating ? HF_META[a.hold_and_forget_rating]       : null;
  const hasScenarios = a.scenario_bull_prob != null && a.scenario_base_prob != null && a.scenario_bear_prob != null;

  return (
    <div style={{ borderTop: "1px solid var(--t-border)", background: "var(--t-surface-2)", borderRadius: "0 0 11px 11px", animation: "expandDown 0.18s ease" }}>

      {/* ── What changed strip (unread delta) ── */}
      {changeSummary && (
        <div style={{ padding: "8px 20px", background: "var(--t-unread-bg)", borderBottom: "2px solid var(--t-accent)", display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.65rem", fontFamily: "monospace", fontWeight: 700, color: "var(--t-accent-dark)", textTransform: "uppercase", letterSpacing: "0.08em", flexShrink: 0 }}>
            {daysSinceRead != null ? `${daysSinceRead}d ago` : "Since last read"}
          </span>
          <span style={{ width: 1, height: 12, background: "var(--t-accent)", flexShrink: 0 }} />
          <span style={{ fontSize: "0.78rem", color: "var(--t-accent-dark)", fontFamily: "monospace", fontWeight: 600 }}>{changeSummary}</span>
        </div>
      )}

      {/* ── Conviction Hero Strip ── */}
      {(a.conviction_score != null || a.risk_level || a.hold_period || eqMeta || hfMeta) && (
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--t-border-light)", display: "flex", alignItems: "flex-start", gap: "2rem", flexWrap: "wrap", background: "var(--t-surface)" }}>
          {a.conviction_score != null && (
            <div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.25rem" }}>
                <span style={{ fontSize: "2.4rem", fontWeight: 700, fontFamily: MONO, lineHeight: 1, color: a.conviction_score >= 70 ? "var(--t-green)" : a.conviction_score >= 45 ? "var(--t-yellow)" : "var(--t-red)" }}>{a.conviction_score}</span>
                <span style={{ fontSize: "0.9rem", color: "var(--t-text-dim)", fontFamily: MONO }}>/100</span>
              </div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 3 }}>Conviction</div>
            </div>
          )}
          {a.risk_level && (
            <div>
              <div style={{ fontSize: "1rem", fontWeight: 700, fontFamily: MONO, color: a.risk_level === "LOW" ? "var(--t-green)" : a.risk_level === "MEDIUM" || a.risk_level === "MED" ? "var(--t-yellow)" : "var(--t-red)" }}>{a.risk_level}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 3 }}>Risk</div>
            </div>
          )}
          {a.hold_period && (
            <div>
              <div style={{ fontSize: "1rem", fontWeight: 600, fontFamily: SANS, color: "var(--t-text)" }}>{a.hold_period}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 3 }}>Hold Period</div>
            </div>
          )}
          {eqMeta && (
            <div>
              <div style={{ fontSize: "1rem", fontWeight: 600, fontFamily: SANS, color: eqMeta.color }}>{eqMeta.label}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 3 }}>Entry</div>
            </div>
          )}
          {hfMeta && (
            <div>
              <div style={{ fontSize: "1rem", fontWeight: 600, fontFamily: SANS, color: hfMeta.color }}>{hfMeta.label}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 3 }}>Strategy</div>
            </div>
          )}
          {a.position_size_pct && (
            <div>
              <div style={{ fontSize: "1rem", fontWeight: 700, fontFamily: MONO, color: "var(--t-accent)" }}>{a.position_size_pct}</div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 3 }}>Position Size</div>
            </div>
          )}
        </div>
      )}

      {/* ── Language / mode toggles ── */}
      <div style={{ padding: "8px 20px", borderBottom: "1px solid var(--t-border-light)", display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        {(["en", "hi"] as const).map(l => (
          <button key={l} onClick={() => applyTranslation(l, mode)} disabled={translating} style={{
            fontSize: "0.68rem", fontFamily: MONO, fontWeight: 700, padding: "2px 10px",
            borderRadius: 20, border: `1px solid ${lang === l ? "var(--t-accent)" : "var(--t-border)"}`,
            background: lang === l ? "var(--t-accent-light)" : "transparent",
            color: lang === l ? "var(--t-accent)" : "var(--t-text-muted)", cursor: "pointer",
          }}>
            {l === "en" ? "EN" : "हि"}
          </button>
        ))}
        <span style={{ width: 1, height: 14, background: "var(--t-border)", flexShrink: 0 }} />
        {(["technical", "simple"] as const).map(m => (
          <button key={m} onClick={() => applyTranslation(lang, m)} disabled={translating} style={{
            fontSize: "0.68rem", fontFamily: MONO, fontWeight: 700, padding: "2px 10px",
            borderRadius: 20, border: `1px solid ${mode === m ? "var(--t-accent)" : "var(--t-border)"}`,
            background: mode === m ? "var(--t-accent-light)" : "transparent",
            color: mode === m ? "var(--t-accent)" : "var(--t-text-muted)", cursor: "pointer",
          }}>
            {m === "technical" ? "Technical" : "Simple"}
          </button>
        ))}
        {translating && <span style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", fontFamily: MONO, marginLeft: 4 }}>translating…</span>}
      </div>

      {/* ── Signal checklist strip ── */}
      <div style={{ padding: "10px 20px", borderBottom: "1px solid var(--t-border-light)", display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px 8px" }}>
        <span style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", fontFamily: MONO, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", marginRight: 4, flexShrink: 0 }}>Analyzed</span>
        {signals.map(s => (
          <span key={s.label} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: "0.7rem", fontFamily: MONO, padding: "2px 9px", borderRadius: 20, color: s.ok ? "var(--t-green)" : "var(--t-text-dim)", background: s.ok ? "var(--t-green-bg)" : "var(--t-surface-3)", border: `1px solid ${s.ok ? "var(--t-green-mid)" : "var(--t-border)"}` }}>
            <span style={{ fontSize: "0.65rem" }}>{s.ok ? "✓" : "—"}</span>{s.label}
          </span>
        ))}
      </div>

      {/* ── 52-Week Range ── */}
      {a.week_52_low != null && a.week_52_high != null && a.range_position_pct != null && (
        <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--t-border-light)", display: "flex", alignItems: "center", gap: "2rem", flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>52-Week Range</div>
            <div style={{ width: 320 }}>
              <RangeBar lo={a.week_52_low} hi={a.week_52_high} pct={a.range_position_pct} />
            </div>
          </div>
          {(a.stock_52w_change != null || a.sp500_52w_change != null) && (
            <div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>vs S&P 500 (52w)</div>
              <div style={{ display: "flex", gap: "1rem", alignItems: "baseline" }}>
                {a.stock_52w_change != null && <span style={{ fontWeight: 700, fontSize: "1rem", color: a.stock_52w_change >= 0 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>{a.stock_52w_change >= 0 ? "+" : ""}{a.stock_52w_change.toFixed(1)}%</span>}
                {a.sp500_52w_change != null && <span style={{ fontSize: "0.75rem", color: "var(--t-text-muted)", fontFamily: MONO }}>S&P {a.sp500_52w_change >= 0 ? "+" : ""}{a.sp500_52w_change.toFixed(1)}%</span>}
              </div>
            </div>
          )}
          {(a.stock_5y_change != null || a.sp500_5y_change != null) && (
            <div>
              <div style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>vs S&P 500 (5y)</div>
              <div style={{ display: "flex", gap: "1rem", alignItems: "baseline" }}>
                {a.stock_5y_change != null && <span style={{ fontWeight: 700, fontSize: "1rem", color: a.stock_5y_change >= 0 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>{a.stock_5y_change >= 0 ? "+" : ""}{a.stock_5y_change.toFixed(1)}%</span>}
                {a.sp500_5y_change != null && <span style={{ fontSize: "0.75rem", color: "var(--t-text-muted)", fontFamily: MONO }}>S&P {a.sp500_5y_change >= 0 ? "+" : ""}{a.sp500_5y_change.toFixed(1)}%</span>}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Dual-Agent Agreement ── */}
      {a.verdict_agreement != null && (
        <div style={{ padding: "10px 20px", borderBottom: "1px solid var(--t-border-light)" }}>
          <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "8px 12px" }}>
            {a.verdict_agreement === true && (
              <span style={{ fontSize: "0.72rem", fontFamily: MONO, fontWeight: 700, padding: "4px 12px", borderRadius: 20, color: "var(--t-green)", background: "var(--t-green-bg)", border: "1px solid var(--t-green-mid)" }}>
                ✓ Both AI models agree
              </span>
            )}
            {a.verdict_agreement === false && (
              <span style={{ fontSize: "0.72rem", fontFamily: MONO, fontWeight: 700, padding: "4px 12px", borderRadius: 20, color: "var(--t-yellow)", background: "var(--t-yellow-bg)", border: "1px solid var(--t-yellow-border)" }}>
                ⚠ Split — Claude: {a.verdict_a} · Gemini: {a.verdict_b}
              </span>
            )}
          </div>
          {a.verdict_agreement === false && a.split_reason && (
            <div style={{ marginTop: "6px", fontSize: "0.7rem", color: "var(--t-yellow)", lineHeight: 1.55, fontStyle: "italic" }}>{a.split_reason}</div>
          )}
        </div>
      )}

      {/* ── Don't Panic note ── */}
      {a.dont_panic_note && (
        <div style={{ margin: "0 20px 0", padding: "12px 16px", background: "var(--t-yellow-light-bg)", border: "1px solid var(--t-yellow-border)", borderRadius: 8, marginTop: 14, marginBottom: 4 }}>
          <div style={{ fontSize: "0.68rem", color: "var(--t-yellow)", fontFamily: MONO, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 5 }}>Price Alert</div>
          <div style={{ fontSize: "0.8rem", lineHeight: 1.6, color: "var(--t-yellow-dark)" }}>{a.dont_panic_note}</div>
        </div>
      )}

      {/* ── Main content — one readable story column + a compact data rail.
             All prose lives in the story column at a comfortable reading measure (~66ch);
             all numbers live in the rail. Never interleave the two. ── */}
      <div style={{ padding: isMobile ? "0.75rem 0.75rem" : "1.25rem 1.5rem", display: "flex", flexDirection: isMobile ? "column" : "row", gap: isMobile ? "1.25rem" : "2.5rem" }}>

        {/* The Story — what's happening → why this verdict → both sides → what breaks it */}
        <div style={{ flex: 1, minWidth: 0, maxWidth: isMobile ? "100%" : "66ch", display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div>
            <div style={secLabel}>The Story</div>
            <div style={{ fontSize: isMobile ? "0.88rem" : "0.92rem", lineHeight: 1.7, color: "var(--t-text-dark)" }}>{reasoning ?? "—"}</div>
          </div>
          {(bull_case || bear_case || thesis_invalidation) && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem", borderTop: "1px solid var(--t-border-light)", paddingTop: "1rem" }}>
              {bull_case && (
                <div style={{ display: "flex", gap: "0.6rem", fontSize: "0.88rem", color: "var(--t-text-dark)", lineHeight: 1.65 }}>
                  <span style={{ color: "var(--t-green)", fontWeight: 700, flexShrink: 0 }}>Bull</span><span>{bull_case}</span>
                </div>
              )}
              {bear_case && (
                <div style={{ display: "flex", gap: "0.6rem", fontSize: "0.88rem", color: "var(--t-text-dark)", lineHeight: 1.65 }}>
                  <span style={{ color: "var(--t-red)", fontWeight: 700, flexShrink: 0 }}>Bear</span><span>{bear_case}</span>
                </div>
              )}
              {thesis_invalidation && (
                <div style={{ display: "flex", gap: "0.6rem", fontSize: "0.84rem", color: "var(--t-text-secondary)", lineHeight: 1.65 }}>
                  <span style={{ color: "var(--t-text-muted)", fontWeight: 600, flexShrink: 0, fontFamily: MONO, fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: "0.06em", paddingTop: 3 }}>Flips if</span>
                  <span>{thesis_invalidation}</span>
                </div>
              )}
            </div>
          )}
          {news_summary && (
            <div style={{ borderTop: "1px solid var(--t-border-light)", paddingTop: "1rem" }}>
              <div style={secLabel}>News</div>
              <div style={{ fontSize: "0.86rem", lineHeight: 1.65, color: "var(--t-text-dark)" }}>{news_summary}</div>
            </div>
          )}
          {a.ripple_analysis && (
            <div style={{ borderTop: "1px solid var(--t-border-light)", paddingTop: "1rem" }}>
              <div style={secLabel}>Ripple Effects</div>
              <div style={{ fontSize: "0.86rem", lineHeight: 1.65, color: "var(--t-text-dark)" }}>{a.ripple_analysis}</div>
            </div>
          )}
        </div>

        {/* Data rail — scannable numbers, no paragraphs */}
        <div style={{ width: isMobile ? "100%" : 280, flexShrink: 0, display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {hasScenarios && (
            <div>
              <div style={secLabel}>90-Day Scenarios</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {([
                  { key: "bull", label: "Bull", pct: a.scenario_bull_pct, prob: a.scenario_bull_prob, color: "var(--t-green)" },
                  { key: "base", label: "Base", pct: a.scenario_base_pct, prob: a.scenario_base_prob, color: "var(--t-accent)" },
                  { key: "bear", label: "Bear", pct: a.scenario_bear_pct, prob: a.scenario_bear_prob, color: "var(--t-red)" },
                ] as const).map(s => (
                  <div key={s.key} style={{ display: "flex", alignItems: "baseline", gap: "0.6rem", padding: "3px 0" }}>
                    <span style={{ fontSize: "0.66rem", fontFamily: MONO, fontWeight: 700, color: s.color, textTransform: "uppercase", letterSpacing: "0.06em", width: 34, flexShrink: 0 }}>{s.label}</span>
                    <span style={{ fontSize: "0.92rem", fontWeight: 700, fontFamily: MONO, color: s.color }}>
                      {s.pct != null ? (s.pct >= 0 ? "+" : "") + s.pct.toFixed(1) + "%" : "—"}
                    </span>
                    {s.prob != null && <span style={{ fontSize: "0.68rem", fontFamily: MONO, color: "var(--t-text-muted)", marginLeft: "auto" }}>{s.prob}% odds</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div>
            <div style={secLabel}>Price Targets</div>
            {(a.entry_target || a.exit_target || a.stop_loss || a.hold_period) ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap" }}>
                  {a.entry_target && <div><div style={{ fontSize: "0.68rem", color: "var(--t-text-muted)" }}>Entry</div><div style={{ fontWeight: 600, color: "var(--t-green)", fontSize: "1rem", fontFamily: MONO }}>${a.entry_target.toFixed(2)}</div></div>}
                  {a.exit_target  && <div><div style={{ fontSize: "0.68rem", color: "var(--t-text-muted)" }}>Take Profit</div><div style={{ fontWeight: 600, color: "var(--t-accent)", fontSize: "1rem", fontFamily: MONO }}>${a.exit_target.toFixed(2)}</div></div>}
                  {a.stop_loss    && <div><div style={{ fontSize: "0.68rem", color: "var(--t-text-muted)" }}>Stop Loss</div><div style={{ fontWeight: 600, color: "var(--t-red)", fontSize: "1rem", fontFamily: MONO }}>${a.stop_loss.toFixed(2)}</div></div>}
                </div>
                {a.hold_period && (
                  <div style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.25rem 0.65rem", background: "var(--t-surface-3)", border: "1px solid var(--t-border)", borderRadius: 6, width: "fit-content" }}>
                    <span style={{ fontSize: "0.68rem", color: "var(--t-text-muted)", fontFamily: MONO }}>Hold:</span>
                    <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--t-text)" }}>{a.hold_period}</span>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ fontSize: "0.82rem", color: "var(--t-text-muted)" }}>No price targets set</div>
            )}
          </div>
          {events.length > 0 && (
            <div>
              <div style={secLabel}>Upcoming Events</div>
              {events.map((e, i) => (
                <div key={i} style={{ fontSize: "0.78rem", color: "var(--t-yellow)", marginBottom: "0.25rem", display: "flex", gap: "0.4rem" }}>
                  <span>⚡</span><span>{e.date} — {e.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Full-width sections below the story/rail split ── */}
      <div style={{ padding: isMobile ? "0 0.75rem 0.75rem" : "0 1.5rem 1.25rem" }}>

        {/* Fundamentals */}
        {(a.pe_trailing || a.revenue_growth || a.profit_margin || a.beta || a.market_cap || a.sector) && (
          <div style={{ borderTop: isMobile ? "none" : "1px solid var(--t-border)", paddingTop: isMobile ? 0 : "1rem" }}>
            <div style={secLabel}>Fundamentals</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "0.75rem 1.5rem" }}>
              {a.pe_trailing     != null && <FundStat label="P/E (TTM)"       value={a.pe_trailing.toFixed(1) + "x"} />}
              {a.pe_forward      != null && <FundStat label="P/E (Fwd)"       value={a.pe_forward.toFixed(1) + "x"} />}
              {a.revenue_growth  != null && <FundStat label="Revenue Growth"  value={pct(a.revenue_growth)}  color={a.revenue_growth  >= 0 ? "var(--t-green)" : "var(--t-red)"} />}
              {a.profit_margin   != null && <FundStat label="Net Margin"      value={pct(a.profit_margin)}   color={a.profit_margin   >= 0 ? "var(--t-green)" : "var(--t-red)"} />}
              {a.debt_to_equity  != null && <FundStat label="Debt / Equity"   value={a.debt_to_equity.toFixed(1)} />}
              {a.beta            != null && <FundStat label="Beta"            value={a.beta.toFixed(2)}       color={a.beta > 1.5 ? "var(--t-yellow)" : undefined} />}
              {a.short_float_pct   != null && <FundStat label="Short Interest"  value={pct(a.short_float_pct)} color={a.short_float_pct > 0.2 ? "var(--t-red)" : undefined} />}
              {a.inst_ownership_pct != null && <FundStat label="Inst. Ownership" value={pct(a.inst_ownership_pct)} />}
              {(a.stock_52w_change != null || a.sp500_52w_change != null) && (
                <div>
                  <div style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", marginBottom: "0.2rem" }}>vs S&P 500 (52w)</div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "baseline" }}>
                    {a.stock_52w_change != null && <span style={{ fontWeight: 600, fontSize: "0.88rem", color: a.stock_52w_change >= 0 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>{pctRaw(a.stock_52w_change)}</span>}
                    {a.sp500_52w_change != null && <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)" }}>/ {pctRaw(a.sp500_52w_change)} S&P</span>}
                  </div>
                </div>
              )}
              {(a.stock_5y_change != null || a.sp500_5y_change != null) && (
                <div>
                  <div style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", marginBottom: "0.2rem" }}>vs S&P 500 (5y)</div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "baseline" }}>
                    {a.stock_5y_change != null && <span style={{ fontWeight: 600, fontSize: "0.88rem", color: a.stock_5y_change >= 0 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>{pctRaw(a.stock_5y_change)}</span>}
                    {a.sp500_5y_change != null && <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)" }}>/ {pctRaw(a.sp500_5y_change)} S&P</span>}
                  </div>
                </div>
              )}
              {a.market_cap     != null && <FundStat label="Market Cap"    value={fmtCap(a.market_cap)} />}
              {a.dividend_yield != null && a.dividend_yield > 0 && <FundStat label="Dividend Yield" value={a.dividend_yield.toFixed(1) + "%"} color="var(--t-green)" />}
            </div>
            {(a.sector || a.industry) && (
              <div style={{ marginTop: "0.6rem", fontSize: "0.72rem", color: "var(--t-text-muted)" }}>
                {[a.sector, a.industry].filter(Boolean).join(" · ")}
              </div>
            )}
          </div>
        )}

      {/* ── History + Report ── */}
      <div>
        <HistoryPanel ticker={a.ticker} idToken={idToken} currentAnalysis={a} isMobile={isMobile} txCacheRef={txCacheRef} />
      </div>

      </div>
    </div>
  );
}

export function HistoryPanel({ ticker, idToken, currentAnalysis, isMobile, txCacheRef }: {
  ticker: string; idToken: string; currentAnalysis: Analysis; isMobile: boolean;
  txCacheRef: React.MutableRefObject<Record<string, Record<string, string | null>>>;
}) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<Analysis[] | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [expandedDate, setExpandedDate] = useState<string | null>(null);
  const [report, setReport] = useState<StockReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportChecked, setReportChecked] = useState(false);

  async function loadHistory() {
    if (history) { setOpen(o => !o); return; }
    setOpen(true);
    setLoadingHistory(true);
    try {
      const r = await fetch(`${API}/analysis/${ticker}/history?id_token=${encodeURIComponent(idToken)}&days=60`);
      if (r.ok) {
        const data: Analysis[] = await r.json();
        // exclude today's analysis (already showing above)
        setHistory(data.filter(h => h.id !== currentAnalysis.id));
        // also check if today's report already exists
        checkReport();
      }
    } finally { setLoadingHistory(false); }
  }

  async function checkReport() {
    if (reportChecked) return;
    setReportChecked(true);
    try {
      const r = await fetch(`${API}/analysis/${ticker}/report?id_token=${encodeURIComponent(idToken)}`);
      if (r.ok) { const d = await r.json(); if (d) setReport(d); }
    } catch {}
  }

  async function generateReport() {
    setLoadingReport(true);
    try {
      const r = await fetch(`${API}/analysis/${ticker}/report?id_token=${encodeURIComponent(idToken)}`, { method: "POST" });
      if (r.ok) setReport(await r.json());
    } finally { setLoadingReport(false); }
  }

  const VERDICT_META: Record<string, { color: string; bg: string }> = {
    BUY:   { color: "var(--t-green)", bg: "var(--t-green-bg)" },
    HOLD:  { color: "var(--t-yellow)", bg: "var(--t-yellow-bg)" },
    WATCH: { color: "var(--t-text-muted)", bg: "var(--t-surface-3)" },
    SELL:  { color: "var(--t-red)", bg: "var(--t-red-bg)" },
  };

  return (
    <div style={{ borderTop: "1px solid var(--t-border-light)", marginTop: 0 }}>
      <button
        onClick={loadHistory}
        style={{ width: "100%", background: "none", border: "none", cursor: "pointer", padding: isMobile ? "10px 12px" : "12px 20px", display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--t-text-muted)", fontSize: "0.72rem", fontFamily: MONO, fontWeight: 600, letterSpacing: "0.06em", textAlign: "left" }}
      >
        <span style={{ transition: "transform 0.2s", transform: open ? "rotate(90deg)" : "rotate(0deg)", display: "inline-block", fontSize: "0.6rem" }}>▶</span>
        {loadingHistory ? "Loading history..." : `PAST ANALYSES${history ? ` (${history.length})` : ""}`}
      </button>

      {open && history && (
        <div style={{ padding: isMobile ? "0 8px 16px" : "0 20px 20px" }}>
          {/* Report section */}
          <div style={{ marginBottom: "1rem", padding: "12px 14px", background: "var(--t-surface-3)", borderRadius: 8, border: "1px solid var(--t-border)" }}>
            {report ? (
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem", gap: "0.75rem", flexWrap: "wrap" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.65rem", fontFamily: MONO, fontWeight: 700, color: "var(--t-text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                      AI Report · {report.analyses_count} analyses · {report.report_date}
                    </span>
                    {report.report_date !== new Date().toISOString().slice(0, 10) && (
                      <span style={{ fontSize: "0.6rem", fontFamily: MONO, padding: "1px 6px", borderRadius: 3, background: "var(--t-yellow-bg)", color: "var(--t-yellow)", fontWeight: 700 }}>STALE</span>
                    )}
                  </div>
                  <button
                    onClick={generateReport}
                    disabled={loadingReport}
                    style={{ fontSize: "0.65rem", fontFamily: MONO, fontWeight: 700, padding: "4px 10px", borderRadius: 5, border: "1px solid var(--t-border-mid)", background: "none", color: "var(--t-text-muted)", cursor: loadingReport ? "default" : "pointer", whiteSpace: "nowrap", flexShrink: 0 }}
                  >
                    {loadingReport ? "Regenerating…" : "↻ Regenerate"}
                  </button>
                </div>
                <div style={{ fontSize: "0.82rem", color: "var(--t-text)", lineHeight: 1.65, fontFamily: SANS }} className="report-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.content}</ReactMarkdown>
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", fontFamily: SANS, flex: 1 }}>
                  Generate an AI-written debrief of the past {history.length} analyses — verdict trends, what it got right, what to watch.
                </span>
                <button
                  onClick={generateReport}
                  disabled={loadingReport}
                  style={{ fontSize: "0.7rem", fontFamily: MONO, fontWeight: 700, padding: "6px 14px", borderRadius: 6, border: "1px solid var(--t-accent)", background: loadingReport ? "var(--t-surface-2)" : "var(--t-accent)", color: loadingReport ? "var(--t-text-muted)" : "#fff", cursor: loadingReport ? "default" : "pointer", whiteSpace: "nowrap", flexShrink: 0 }}
                >
                  {loadingReport ? "Generating…" : "Generate Report"}
                </button>
              </div>
            )}
          </div>

          {/* Date list */}
          {history.length === 0 ? (
            <div style={{ fontSize: "0.78rem", color: "var(--t-text-muted)", fontFamily: MONO }}>No past analyses found.</div>
          ) : history.map(h => {
            const vm = h.verdict ? VERDICT_META[h.verdict] ?? VERDICT_META.WATCH : null;
            const isExp = expandedDate === h.id;
            return (
              <div key={h.id} style={{ borderRadius: 8, border: `1px solid ${isExp ? "var(--t-accent)" : h.is_important_day ? "var(--t-yellow-border)" : "var(--t-border-light)"}`, borderLeft: h.is_important_day ? "3px solid var(--t-yellow)" : undefined, marginBottom: "0.5rem", overflow: "hidden" }}>
                {/* Compact header row */}
                <button
                  onClick={() => setExpandedDate(isExp ? null : h.id)}
                  style={{ width: "100%", background: isExp ? "var(--t-surface)" : h.is_important_day ? "var(--t-yellow-light-bg)" : "none", border: "none", cursor: "pointer", padding: "10px 14px", display: "flex", flexDirection: "column", gap: "0.35rem", textAlign: "left" }}
                >
                  {/* Row 1: date · verdict · price · change · RSI · conviction · star */}
                  <div style={{ display: "flex", alignItems: "center", gap: isMobile ? "0.4rem" : "0.75rem", width: "100%", flexWrap: isMobile ? "wrap" : "nowrap" }}>
                    <span style={{ fontSize: "0.7rem", fontFamily: MONO, color: "var(--t-text-muted)", flexShrink: 0 }}>{h.analysis_date}</span>
                    {vm && (
                      <span style={{ fontSize: "0.62rem", fontFamily: MONO, fontWeight: 700, padding: "2px 8px", borderRadius: 4, background: vm.bg, color: vm.color, flexShrink: 0 }}>{h.verdict}</span>
                    )}
                    {h.current_price != null && (
                      <span style={{ fontSize: "0.72rem", fontFamily: MONO, color: "var(--t-text)", fontWeight: 600, flexShrink: 0 }}>${h.current_price.toFixed(2)}</span>
                    )}
                    {h.day_change_pct != null && (
                      <span style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 600, color: h.day_change_pct >= 0 ? "var(--t-green)" : "var(--t-red)", flexShrink: 0 }}>
                        {h.day_change_pct >= 0 ? "+" : ""}{h.day_change_pct.toFixed(2)}%
                      </span>
                    )}
                    {h.rsi != null && (
                      <span style={{ fontSize: "0.6rem", fontFamily: MONO, padding: "1px 6px", borderRadius: 3, background: "var(--t-surface-3)", color: h.rsi >= 70 ? "var(--t-red)" : h.rsi <= 30 ? "var(--t-green)" : "var(--t-text-muted)", flexShrink: 0 }}>
                        RSI {h.rsi.toFixed(0)}
                      </span>
                    )}
                    {h.conviction_score != null && (
                      <span style={{ fontSize: "0.65rem", fontFamily: MONO, color: "var(--t-text-muted)" }}>
                        {isMobile ? h.conviction_score : `CONVICTION ${h.conviction_score}`}
                      </span>
                    )}
                    {h.is_important_day && <span style={{ fontSize: "0.7rem", flexShrink: 0 }} title={h.importance_reason ?? ""}>⭐</span>}
                    <span style={{ marginLeft: "auto", fontSize: "0.6rem", color: "var(--t-text-dim)", transition: "transform 0.15s", transform: isExp ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block", flexShrink: 0 }}>▼</span>
                  </div>
                  {/* Row 2: story beat for important days (why this day mattered), else reasoning snippet */}
                  {h.is_important_day && h.importance_reason ? (
                    <div style={{ fontSize: "0.72rem", color: "var(--t-yellow-dark)", fontFamily: SANS, lineHeight: 1.45, paddingLeft: isMobile ? 0 : 60, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                      {h.importance_reason}
                    </div>
                  ) : h.reasoning ? (
                    <div style={{ fontSize: "0.7rem", color: "var(--t-text-muted)", fontFamily: SANS, lineHeight: 1.4, paddingLeft: isMobile ? 0 : 60, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical" }}>
                      {h.reasoning}
                    </div>
                  ) : null}
                </button>

                {/* Full analysis inline */}
                {isExp && (
                  <div style={{ borderTop: "1px solid var(--t-border-light)" }}>
                    <ExpandedDetail a={h} isMobile={isMobile} idToken={idToken} txCacheRef={txCacheRef} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function FundStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", marginBottom: "0.2rem" }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: "0.88rem", color: color ?? "var(--t-text)", fontFamily: MONO }}>{value}</div>
    </div>
  );
}

export function pct(v: number) { return (v * 100).toFixed(1) + "%"; }
// For fields the backend already stores as a percentage (e.g. stock_52w_change = -47.8
// meaning -47.8%), unlike pct() above which expects a fraction like 0.058.
export function pctRaw(v: number) { return (v >= 0 ? "+" : "") + v.toFixed(1) + "%"; }

export function fmtCap(v: number) {
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9)  return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6)  return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + v.toLocaleString();
}
