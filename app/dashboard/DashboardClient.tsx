"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";
import ThemeToggle from "@/app/components/ThemeToggle";

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
  verdict_a: string | null;
  verdict_b: string | null;
  verdict_agreement: boolean | null;
  split_reason: string | null;
}

interface DigestItem {
  ticker: string;
  company_name: string | null;
  is_leveraged: boolean;
  analysis: Analysis | null;
  has_unread: boolean;
  change_summary: string | null;
  days_since_read: number | null;
  close_5d: number[] | null;
}

const VERDICT_META: Record<string, { color: string; bg: string; bd: string; label: string }> = {
  BUY:   { color: "var(--t-green)", bg: "var(--t-green-bg)", bd: "var(--t-green-border)", label: "BUY"   },
  HOLD:  { color: "var(--t-yellow)", bg: "var(--t-yellow-bg)", bd: "var(--t-yellow-border)", label: "HOLD"  },
  SELL:  { color: "var(--t-red)", bg: "var(--t-red-bg)", bd: "var(--t-red-border)", label: "SELL"  },
  WATCH: { color: "var(--t-text-muted)", bg: "var(--t-surface-warm)", bd: "var(--t-border)", label: "WATCH" },
};

function RangeBar({ lo, hi, pct }: { lo: number; hi: number; pct: number }) {
  const clamp = Math.max(0, Math.min(100, pct));
  const dotColor = clamp < 33 ? "var(--t-green)" : clamp < 67 ? "var(--t-yellow)" : "var(--t-red)";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", minWidth: 130 }}>
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

function RsiPill({ rsi }: { rsi: number }) {
  const color = rsi >= 70 ? "var(--t-red)" : rsi <= 30 ? "var(--t-green)" : "var(--t-text-muted)";
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
        <span style={{ fontSize: "0.68rem", color: above50 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>
          {above50 ? "▲" : "▼"} MA50
        </span>
      )}
      {ma200 != null && (
        <span style={{ fontSize: "0.68rem", color: above200 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>
          {above200 ? "▲" : "▼"} MA200
        </span>
      )}
    </div>
  );
}

function ExpandedDetail({ a, onChat, isMobile, changeSummary, daysSinceRead, idToken }: {
  a: Analysis; onChat: () => void; isMobile: boolean;
  changeSummary?: string | null; daysSinceRead?: number | null;
  idToken: string;
}) {
  const [lang, setLang] = useState<"en" | "hi">("en");
  const [mode, setMode] = useState<"technical" | "simple">("technical");
  const [translating, setTranslating] = useState(false);
  const [txCache, setTxCache] = useState<Record<string, Record<string, string | null>>>({});

  const txKey = `${lang}:${mode}`;
  const tx = txCache[txKey] ?? {};

  async function applyTranslation(nextLang: "en" | "hi", nextMode: "technical" | "simple") {
    const key = `${nextLang}:${nextMode}`;
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
      }
    } finally {
      setTranslating(false);
      setLang(nextLang);
      setMode(nextMode);
    }
  }

  const reasoning          = tx.reasoning          ?? a.reasoning;
  const bull_case          = tx.bull_case          ?? a.bull_case;
  const bear_case          = tx.bear_case          ?? a.bear_case;
  const thesis_invalidation = tx.thesis_invalidation ?? a.thesis_invalidation;
  const news_summary       = tx.news_summary       ?? a.news_summary;

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
    <div style={{ borderTop: "1px solid var(--t-border)", background: "var(--t-surface-2)", borderRadius: "0 0 11px 11px" }}>

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

      {/* ── 52-Week Range (moved from collapsed row — more space here) ── */}
      {a.week_52_low != null && a.week_52_high != null && a.range_position_pct != null && (
        <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--t-border-light)" }}>
          <RangeBar lo={a.week_52_low} hi={a.week_52_high} pct={a.range_position_pct} />
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

      {/* ── 90-Day Scenarios ── */}
      {hasScenarios && (
        <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--t-border-light)" }}>
          <div style={{ ...secLabel, marginBottom: "0.75rem" }}>90-Day Scenarios</div>
          <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 1fr", gap: "0.75rem" }}>
            {([
              { key: "bull", label: "Bull", pct: a.scenario_bull_pct, prob: a.scenario_bull_prob, text: a.scenario_bull, color: "var(--t-green)", bg: "var(--t-green-bg)", bd: "var(--t-green-mid)" },
              { key: "base", label: "Base", pct: a.scenario_base_pct, prob: a.scenario_base_prob, text: a.scenario_base, color: "var(--t-accent)", bg: "var(--t-accent-bg)", bd: "var(--t-accent-border)" },
              { key: "bear", label: "Bear", pct: a.scenario_bear_pct, prob: a.scenario_bear_prob, text: a.scenario_bear, color: "var(--t-red)", bg: "var(--t-red-bg)", bd: "var(--t-red-border)" },
            ] as const).map(s => (
              <div key={s.key} style={{ background: s.bg, border: `1px solid ${s.bd}`, borderRadius: 8, padding: "10px 12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
                  <span style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 700, color: s.color, textTransform: "uppercase", letterSpacing: "0.06em" }}>{s.label}</span>
                  <span style={{ fontSize: "0.68rem", fontFamily: MONO, color: "var(--t-text-muted)" }}>{s.prob}%</span>
                </div>
                <div style={{ fontSize: "1.05rem", fontWeight: 700, fontFamily: MONO, color: s.color, marginBottom: 5 }}>
                  {s.pct != null ? (s.pct >= 0 ? "+" : "") + s.pct.toFixed(1) + "%" : "—"}
                </div>
                {s.text && <div style={{ fontSize: "0.72rem", lineHeight: 1.5, color: "var(--t-text-dark)" }}>{s.text}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Main content — 3-col on desktop, stacked on mobile ── */}
      <div style={{ padding: "1.25rem 1.5rem", display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 1fr", gap: isMobile ? "1.25rem" : "1.5rem" }}>

        {/* Bull / bear / thesis — conviction lives in the hero strip above */}
        {(bull_case || bear_case || thesis_invalidation) && (
          <div style={{ gridColumn: isMobile ? "1" : "1 / -1", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            {bull_case && (
              <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem", color: "var(--t-text-dark)", lineHeight: 1.5 }}>
                <span style={{ color: "var(--t-green)", fontWeight: 700, flexShrink: 0 }}>Bull</span><span>{bull_case}</span>
              </div>
            )}
            {bear_case && (
              <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem", color: "var(--t-text-dark)", lineHeight: 1.5 }}>
                <span style={{ color: "var(--t-red)", fontWeight: 700, flexShrink: 0 }}>Bear</span><span>{bear_case}</span>
              </div>
            )}
            {thesis_invalidation && (
              <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.78rem", color: "var(--t-text-secondary)", lineHeight: 1.5 }}>
                <span style={{ color: "var(--t-text-muted)", fontWeight: 600, flexShrink: 0, fontFamily: MONO, fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: "0.06em", paddingTop: 2 }}>Flips if</span>
                <span>{thesis_invalidation}</span>
              </div>
            )}
          </div>
        )}

        {/* Price Targets + Events */}
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
          {events.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <div style={{ ...secLabel, marginTop: "0.5rem" }}>Upcoming Events</div>
              {events.map((e, i) => (
                <div key={i} style={{ fontSize: "0.78rem", color: "var(--t-yellow)", marginBottom: "0.25rem", display: "flex", gap: "0.4rem" }}>
                  <span>⚡</span><span>{e.date} — {e.description}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Reasoning */}
        <div>
          <div style={secLabel}>AI Reasoning</div>
          <div style={{ fontSize: "0.8rem", lineHeight: 1.65, color: "var(--t-text-dark)" }}>{reasoning ?? "—"}</div>
        </div>

        {/* News + Ripple + Chat */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {news_summary && (
            <div>
              <div style={secLabel}>News</div>
              <div style={{ fontSize: "0.78rem", lineHeight: 1.6, color: "var(--t-text-dark)" }}>{news_summary}</div>
            </div>
          )}
          {a.ripple_analysis && (
            <div>
              <div style={secLabel}>Ripple Effects</div>
              <div style={{ fontSize: "0.78rem", lineHeight: 1.6, color: "var(--t-text-dark)" }}>{a.ripple_analysis}</div>
            </div>
          )}
          <div />
        </div>

        {/* Ask AI — full-width CTA */}
        <div style={{ gridColumn: "1 / -1", paddingTop: "0.5rem" }}>
          <button
            onClick={onChat}
            style={{
              width: "100%", padding: "13px 20px", borderRadius: 8,
              background: "var(--t-accent)", color: "#fff", border: "none",
              fontFamily: MONO, fontWeight: 700, fontSize: "0.88rem",
              letterSpacing: "0.04em", cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem",
              transition: "opacity 0.15s",
            }}
            onMouseOver={e => { e.currentTarget.style.opacity = "0.88"; }}
            onMouseOut={e => { e.currentTarget.style.opacity = "1"; }}
          >
            Ask AI about this →
          </button>
        </div>

        {/* Fundamentals */}
        {(a.pe_trailing || a.revenue_growth || a.profit_margin || a.beta || a.market_cap || a.sector) && (
          <div style={{ gridColumn: isMobile ? "1" : "1 / -1", borderTop: isMobile ? "none" : "1px solid var(--t-border)", paddingTop: isMobile ? 0 : "1rem" }}>
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
                    {a.stock_52w_change != null && <span style={{ fontWeight: 600, fontSize: "0.88rem", color: a.stock_52w_change >= 0 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>{pct(a.stock_52w_change)}</span>}
                    {a.sp500_52w_change != null && <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)" }}>/ {pct(a.sp500_52w_change)} S&P</span>}
                  </div>
                </div>
              )}
              {a.market_cap     != null && <FundStat label="Market Cap"    value={fmtCap(a.market_cap)} />}
              {a.dividend_yield != null && a.dividend_yield > 0 && <FundStat label="Dividend Yield" value={pct(a.dividend_yield)} color="var(--t-green)" />}
            </div>
            {(a.sector || a.industry) && (
              <div style={{ marginTop: "0.6rem", fontSize: "0.72rem", color: "var(--t-text-muted)" }}>
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
      <div style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", marginBottom: "0.2rem" }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: "0.88rem", color: color ?? "var(--t-text)", fontFamily: MONO }}>{value}</div>
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
      padding: "0.3rem 0.85rem", background: vm.color, color: "#fff",
      borderRadius: 6, fontWeight: 700, fontSize: "0.78rem",
      letterSpacing: "0.08em", fontFamily: MONO, whiteSpace: "nowrap",
    }}>
      {vm.label}
    </div>
  );
}

function Sparkline({ prices, width = 88, height = 30 }: { prices: number[]; width?: number; height?: number }) {
  if (!prices || prices.length < 2) return <span style={{ color: "var(--t-text-dim)", fontSize: "0.75rem" }}>—</span>;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const pad = 3;
  const pts = prices.map((p, i) => {
    const x = (i / (prices.length - 1)) * (width - 2) + 1;
    const y = height - pad - ((p - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const isUp = prices[prices.length - 1] >= prices[0];
  const stroke = isUp ? "var(--t-green)" : "var(--t-red)";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: "block", overflow: "visible" }}>
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StockRow({
  item, expanded, onToggle, onChat, onRemove, isMobile, idToken,
}: {
  item: DigestItem; expanded: boolean; isMobile: boolean; idToken: string;
  onToggle: () => void; onChat: (ticker: string) => void; onRemove: (ticker: string) => void;
}) {
  const showUnreadDot = item.has_unread && !!item.analysis;
  const a = item.analysis;
  const vm = a?.verdict ? VERDICT_META[a.verdict] ?? VERDICT_META.WATCH : null;
  const chgColor = (a?.day_change_pct ?? 0) >= 0 ? "var(--t-green)" : "var(--t-red)";
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
      background: "var(--t-surface)",
      border: expanded ? "1px solid var(--t-accent)" : "1px solid var(--t-border)",
      borderRadius: 11, overflow: "hidden", transition: "border-color 0.15s",
    }}>
      {isMobile ? (
        /* ── Mobile card layout ── */
        <div onClick={a ? onToggle : undefined} style={{ padding: "0.85rem 1rem", cursor: a ? "pointer" : "default" }}>
          {/* Row 1: Ticker + badges + Verdict */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", minWidth: 0, flex: 1 }}>
              <span style={{ fontWeight: 700, fontSize: "1.05rem", fontFamily: MONO, color: "var(--t-text)" }}>{item.ticker}</span>
              {a?.is_important_day && <span title={a.importance_reason ?? ""} style={{ fontSize: "0.78rem" }}>⭐</span>}
              {showUnreadDot && <span style={{ fontSize: "0.52rem", fontWeight: 700, fontFamily: MONO, padding: "1px 5px", borderRadius: 10, background: "var(--t-accent)", color: "#fff", flexShrink: 0, lineHeight: "1.4" }}>NEW</span>}
              {item.is_leveraged && <span style={{ fontSize: "0.58rem", padding: "0.1rem 0.35rem", background: "var(--t-accent-light)", color: "var(--t-accent)", border: "1px solid var(--t-accent-border)", borderRadius: 4, fontWeight: 700, fontFamily: MONO }}>3X</span>}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 0 }}>
              {vm ? <VerdictBadge vm={vm} /> : <span style={{ fontSize: "0.75rem", color: "var(--t-text-muted)" }}>Pending</span>}
              <button onClick={e => { e.stopPropagation(); onRemove(item.ticker); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--t-text-dim)", fontSize: "0.82rem", padding: "0.2rem 0.3rem", lineHeight: 1, opacity: 0.4 }}>✕</button>
            </div>
          </div>

          {/* Row 2: Company + age + dual-agent agreement */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.25rem", flexWrap: "wrap" }}>
            {item.company_name && <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.company_name}</span>}
            {age && <span style={{ fontSize: "0.62rem", color: "var(--t-text-dim)", fontFamily: MONO, flexShrink: 0 }}>· {age}</span>}
            {a?.verdict_agreement === true && <span style={{ fontSize: "0.58rem", color: "var(--t-green)", fontFamily: MONO, fontWeight: 600 }}>✓ agree</span>}
            {a?.verdict_agreement === false && <span style={{ fontSize: "0.58rem", color: "var(--t-yellow)", fontFamily: MONO, fontWeight: 600 }}>⚠ split</span>}
          </div>

          {/* Row 3: Price + change · RSI · Conviction */}
          {a && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
              {a.current_price != null && (
                <>
                  <span style={{ fontWeight: 700, fontSize: "1rem", fontFamily: MONO, color: "var(--t-text)" }}>${a.current_price.toFixed(2)}</span>
                  {a.day_change_pct != null && (
                    <span style={{ fontSize: "0.75rem", color: chgColor, fontWeight: 600, fontFamily: MONO }}>
                      {a.day_change_pct >= 0 ? "▲" : "▼"}{Math.abs(a.day_change_pct).toFixed(2)}%
                    </span>
                  )}
                </>
              )}
              {a.rsi != null && (
                <span style={{ fontSize: "0.72rem", fontFamily: MONO, color: a.rsi >= 70 ? "var(--t-red)" : a.rsi <= 30 ? "var(--t-green)" : "var(--t-text-muted)" }}>
                  RSI {a.rsi.toFixed(0)}{a.rsi >= 70 ? " OB" : a.rsi <= 30 ? " OS" : ""}
                </span>
              )}
              {a.conviction_score != null && (
                <span style={{ fontSize: "0.72rem", fontFamily: MONO, color: "var(--t-text-secondary)", fontWeight: 600 }}>
                  · {a.conviction_score}/100
                </span>
              )}
              {a.current_price != null && (a.ma_50 || a.ma_200) && (
                <MaBadge price={a.current_price} ma50={a.ma_50} ma200={a.ma_200} />
              )}
              {a.analyst_consensus && (
                <span style={{ fontSize: "0.7rem", color: "var(--t-text-muted)", fontFamily: MONO }}>Analysts: <span style={{ color: "var(--t-text)", fontWeight: 600 }}>{a.analyst_consensus}</span></span>
              )}
              {upcomingEvent && <span style={{ fontSize: "0.68rem", color: "var(--t-yellow)" }}>⚡ {upcomingEvent}</span>}
            </div>
          )}

          {/* Row 4: Sparkline + Ask AI (Ask AI hidden when expanded — CTA lives in expanded panel) */}
          {a && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "0.5rem" }}>
              {item.close_5d ? <Sparkline prices={item.close_5d} width={120} height={28} /> : <span />}
              {!expanded && (
                <button
                  onClick={e => { e.stopPropagation(); onChat(item.ticker); }}
                  style={{ fontSize: "0.7rem", fontFamily: MONO, fontWeight: 600, padding: "4px 12px", borderRadius: 6, border: "1px solid var(--t-accent)", background: "transparent", color: "var(--t-accent)", cursor: "pointer" }}
                >Ask AI →</button>
              )}
            </div>
          )}

          {!a && <div style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "var(--t-text-muted)" }}>No analysis yet</div>}

          {a && (
            <div style={{ marginTop: "0.4rem", textAlign: "right" }}>
              <span style={{ color: "var(--t-text-dim)", fontSize: "0.68rem", transition: "transform 0.2s", transform: expanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block" }}>▼</span>
            </div>
          )}
        </div>
      ) : (
        /* ── Desktop grid layout ── */
        /* Columns: STOCK | VERDICT | PRICE | CONVICTION | TREND | SIGNAL | ACTIONS */
        <div
          onClick={a ? onToggle : undefined}
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 100px 130px 80px 100px 140px 120px",
            alignItems: "center", padding: "0.85rem 1.25rem",
            cursor: a ? "pointer" : "default", gap: "1rem",
          }}
        >
          {/* Stock — all inline */}
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", overflow: "hidden" }}>
              <span style={{ fontWeight: 700, fontSize: "0.98rem", fontFamily: MONO, color: "var(--t-text)", flexShrink: 0 }}>{item.ticker}</span>
              {a?.is_important_day && <span title={a.importance_reason ?? ""} style={{ fontSize: "0.75rem", flexShrink: 0 }}>⭐</span>}
              {showUnreadDot && <span style={{ fontSize: "0.52rem", fontWeight: 700, fontFamily: MONO, padding: "1px 5px", borderRadius: 10, background: "var(--t-accent)", color: "#fff", flexShrink: 0, lineHeight: "1.4" }}>NEW</span>}
              {item.is_leveraged && <span style={{ fontSize: "0.58rem", padding: "0.1rem 0.35rem", background: "var(--t-accent-light)", color: "var(--t-accent)", border: "1px solid var(--t-accent-border)", borderRadius: 4, fontWeight: 700, fontFamily: MONO, flexShrink: 0 }}>3X</span>}
              {item.company_name && <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>· {item.company_name}</span>}
              {age && <span style={{ fontSize: "0.62rem", color: "var(--t-text-dim)", fontFamily: MONO, flexShrink: 0 }}>· {age}</span>}
            </div>
            {(a?.verdict_agreement === true || a?.verdict_agreement === false) && (
              <div style={{ marginTop: "0.15rem" }}>
                {a.verdict_agreement === true && <span style={{ fontSize: "0.58rem", color: "var(--t-green)", fontFamily: MONO, fontWeight: 600 }}>✓ agree</span>}
                {a.verdict_agreement === false && <span style={{ fontSize: "0.58rem", color: "var(--t-yellow)", fontFamily: MONO, fontWeight: 600 }}>⚠ split</span>}
              </div>
            )}
          </div>

          {/* Verdict — solid block */}
          <div>
            {vm ? <VerdictBadge vm={vm} /> : <span style={{ fontSize: "0.78rem", color: "var(--t-text-muted)" }}>Pending</span>}
          </div>

          {/* Price + change */}
          <div>
            {a?.current_price != null ? (
              <>
                <div style={{ fontWeight: 700, fontSize: "0.98rem", fontFamily: MONO, color: "var(--t-text)" }}>${a.current_price.toFixed(2)}</div>
                {a.day_change_pct != null && (
                  <div style={{ fontSize: "0.72rem", color: chgColor, fontWeight: 600, fontFamily: MONO }}>
                    {a.day_change_pct >= 0 ? "▲" : "▼"} {Math.abs(a.day_change_pct).toFixed(2)}%
                  </div>
                )}
                {a.current_price != null && (a.ma_50 || a.ma_200) && (
                  <div style={{ marginTop: "0.15rem" }}>
                    <MaBadge price={a.current_price} ma50={a.ma_50} ma200={a.ma_200} />
                  </div>
                )}
              </>
            ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.82rem" }}>—</span>}
          </div>

          {/* Conviction — hero number */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
            {a?.conviction_score != null ? (
              <>
                <span style={{ fontSize: "1.3rem", fontWeight: 700, fontFamily: MONO, color: a.conviction_score >= 70 ? "var(--t-green)" : a.conviction_score >= 45 ? "var(--t-yellow)" : "var(--t-red)", lineHeight: 1 }}>{a.conviction_score}</span>
                <span style={{ fontSize: "0.58rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.05em" }}>/100</span>
              </>
            ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.82rem" }}>—</span>}
          </div>

          {/* Trend — sparkline */}
          <div style={{ display: "flex", alignItems: "center" }}>
            {item.close_5d ? <Sparkline prices={item.close_5d} width={88} height={30} /> : (
              a?.rsi != null ? <RsiPill rsi={a.rsi} /> : <span style={{ color: "var(--t-text-muted)", fontSize: "0.78rem" }}>—</span>
            )}
          </div>

          {/* Signal — RSI + analyst + event */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
            {a?.rsi != null && <RsiPill rsi={a.rsi} />}
            {a?.analyst_consensus && (
              <span style={{ fontSize: "0.68rem", color: "var(--t-text-muted)", fontFamily: MONO }}>
                Analysts: <span style={{ color: "var(--t-text)", fontWeight: 600 }}>{a.analyst_consensus}</span>
              </span>
            )}
            {upcomingEvent && <span style={{ fontSize: "0.68rem", color: "var(--t-yellow)", fontFamily: MONO }}>⚡ {upcomingEvent}</span>}
            {!a && <span style={{ fontSize: "0.75rem", color: "var(--t-text-muted)" }}>No analysis yet</span>}
          </div>

          {/* Actions — Ask AI (hidden when expanded) + chevron + remove */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", justifyContent: "flex-end" }}>
            {a && !expanded && (
              <button
                onClick={e => { e.stopPropagation(); onChat(item.ticker); }}
                style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 600, padding: "4px 10px", borderRadius: 6, border: "1px solid var(--t-accent)", background: "transparent", color: "var(--t-accent)", cursor: "pointer", whiteSpace: "nowrap" }}
              >Ask AI →</button>
            )}
            {a && (
              <span style={{ color: "var(--t-text-dim)", fontSize: "0.72rem", transition: "transform 0.2s", transform: expanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block" }}>▼</span>
            )}
            <button
              onClick={e => { e.stopPropagation(); onRemove(item.ticker); }}
              title="Remove from watchlist"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--t-text-muted)", fontSize: "0.82rem", padding: "0.2rem 0.3rem", borderRadius: 4, lineHeight: 1, opacity: 0 }}
              onMouseOver={e => { e.currentTarget.style.opacity = "1"; e.currentTarget.style.color = "var(--t-red)"; }}
              onMouseOut={e => { e.currentTarget.style.opacity = "0"; e.currentTarget.style.color = "var(--t-text-muted)"; }}
            >✕</button>
          </div>
        </div>
      )}

      {expanded && a && <ExpandedDetail a={a} onChat={() => onChat(item.ticker)} isMobile={isMobile} changeSummary={item.change_summary} daysSinceRead={item.days_since_read} idToken={idToken} />}
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
  const [showMobileMenu, setShowMobileMenu] = useState(false);
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
    const effectiveTicker = ticker.trim() || query.trim().toUpperCase().split(/\s/)[0];
    if (!effectiveTicker) return;

    // Optimistic — clear input and insert row immediately, before the network call
    const savedQuery = query; const savedTicker = ticker; const savedCompany = companyName;
    setTicker(""); setCompanyName(""); setQuery(""); setSuggestions([]); setShowSuggestions(false); setError("");
    setDigest(prev => [...prev, { ticker: effectiveTicker, company_name: savedCompany || null, is_leveraged: false, analysis: null, has_unread: false, change_summary: null, days_since_read: null, close_5d: null }]);

    try {
      const r = await fetch(`${API}/watchlist?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: effectiveTicker, company_name: savedCompany || null }),
      });
      if (r.ok) {
        fetchDigest(true); // silent refresh to pull in any existing analysis
      } else {
        // Revert on failure
        const d = await r.json();
        setDigest(prev => prev.filter(i => i.ticker !== effectiveTicker));
        setQuery(savedQuery); setTicker(savedTicker); setCompanyName(savedCompany);
        setError(d.detail || "Failed to add.");
      }
    } catch {
      setDigest(prev => prev.filter(i => i.ticker !== effectiveTicker));
      setQuery(savedQuery); setTicker(savedTicker); setCompanyName(savedCompany);
      setError("Network error — please try again.");
    }
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

  async function handleMarkRead(t: string) {
    // Optimistically clear the unread dot — keep change_summary so the delta strip stays visible
    setDigest(prev => prev.map(d => d.ticker === t ? { ...d, has_unread: false } : d));
    try {
      await fetch(`${API}/watchlist/${encodeURIComponent(t)}/read?id_token=${encodeURIComponent(idToken)}`, { method: "PATCH" });
    } catch { /* silent — next digest refresh will reconcile */ }
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
  const unreadCount   = digest.filter(d => d.has_unread).length;
  const initials = userName.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div style={{ minHeight: "100vh", background: "var(--t-bg)" }}>

      {/* ── Header ── */}
      <header style={{ position: "sticky", top: 0, zIndex: 40, background: "var(--t-surface)", borderBottom: "1px solid var(--t-border)" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", height: 60, display: "flex", alignItems: "center", gap: isMobile ? 12 : 26, padding: isMobile ? "0 16px" : "0 32px" }}>

          {/* Logo */}
          <div onClick={() => setActiveTab("Dashboard")} style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer", flexShrink: 0 }}>
            <span style={{ width: 22, height: 22, borderRadius: 5, background: "var(--t-accent)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--t-surface)", fontSize: 12, fontWeight: 600, fontFamily: MONO }}>✦</span>
            <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em", color: "var(--t-text)", fontFamily: SANS }}>Stock Copilot</span>
          </div>

          {/* Nav tabs — desktop only */}
          {!isMobile && (
            <nav style={{ display: "flex", gap: 2, height: 60 }}>
              {TABS.map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  fontSize: 14, fontFamily: SANS,
                  color: activeTab === tab ? "var(--t-text)" : "var(--t-text-secondary)",
                  fontWeight: activeTab === tab ? 600 : 500,
                  padding: "0 14px", height: 60, border: "none",
                  borderBottom: activeTab === tab ? "2px solid var(--t-accent)" : "2px solid transparent",
                  background: "none", cursor: "pointer", transition: "color 0.15s",
                  whiteSpace: "nowrap",
                }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    {tab}
                    {tab === "My Stocks" && unreadCount > 0 && (
                      <span style={{ fontSize: 10, fontWeight: 700, fontFamily: "monospace", padding: "1px 5px", borderRadius: 9, background: "var(--t-accent)", color: "var(--t-surface)", lineHeight: 1.4 }}>
                        {unreadCount}
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </nav>
          )}

          {/* Right side */}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
            <ThemeToggle />
            {!isMobile && (
              <button onClick={() => router.push("/chat")} style={{
                fontSize: 13, fontFamily: SANS, color: "var(--t-text-secondary)",
                background: "none", border: "1px solid var(--t-border)",
                borderRadius: 7, padding: "6px 13px", cursor: "pointer",
              }}>
                Chat →
              </button>
            )}
            {isMobile && (
              <button data-testid="hamburger-btn" onClick={() => setShowMobileMenu(true)} style={{
                background: "none", border: "none", cursor: "pointer",
                padding: "6px 4px", display: "flex", flexDirection: "column",
                gap: 4, color: "var(--t-text-secondary)",
              }}>
                <span style={{ display: "block", width: 18, height: 2, background: "var(--t-text-secondary)", borderRadius: 1 }} />
                <span style={{ display: "block", width: 18, height: 2, background: "var(--t-text-secondary)", borderRadius: 1 }} />
                <span style={{ display: "block", width: 18, height: 2, background: "var(--t-text-secondary)", borderRadius: 1 }} />
              </button>
            )}
            {!isMobile && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.15 }}>
                <span style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--t-text-muted)", fontFamily: MONO, fontWeight: 500 }}>VIRTUAL BALANCE</span>
                <span style={{ fontSize: 14, fontFamily: MONO, fontWeight: 500, color: "var(--t-text)", marginTop: 3 }}>$20,000</span>
              </div>
            )}
            <div ref={profileMenuRef} style={{ position: "relative" }}>
              <div
                data-testid="user-avatar-btn"
                onClick={() => setShowProfileMenu(v => !v)}
                style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: showProfileMenu ? "var(--t-border-mid)" : "var(--t-surface-3)",
                  border: "1px solid var(--t-border)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 12, fontWeight: 600, color: "var(--t-text-secondary)",
                  cursor: "pointer", userSelect: "none", fontFamily: SANS,
                  transition: "background 0.15s",
                }}
              >
                {initials}
              </div>
              {showProfileMenu && (
                <div style={{
                  position: "absolute", top: "calc(100% + 8px)", right: 0,
                  minWidth: 180, background: "var(--t-surface)",
                  border: "1px solid var(--t-border)", borderRadius: 10,
                  boxShadow: "0 8px 24px rgba(32,33,28,0.12)",
                  zIndex: 100, overflow: "hidden",
                }}>
                  <div style={{ padding: "12px 16px 10px", borderBottom: "1px solid var(--t-border-light)" }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--t-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{userName}</div>
                  </div>
                  <button
                    onClick={() => signOut({ callbackUrl: "/signin" })}
                    style={{
                      width: "100%", textAlign: "left", padding: "11px 16px",
                      background: "none", border: "none", cursor: "pointer",
                      fontSize: 13, color: "var(--t-red)", fontFamily: SANS,
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

      {/* ── Mobile side drawer ── */}
      {isMobile && showMobileMenu && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setShowMobileMenu(false)}
            style={{
              position: "fixed", inset: 0, zIndex: 50,
              background: "rgba(32,33,28,0.35)",
            }}
          />
          {/* Drawer */}
          <div style={{
            position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 51,
            width: 220, background: "var(--t-surface)",
            boxShadow: "-4px 0 24px rgba(32,33,28,0.14)",
            display: "flex", flexDirection: "column",
          }}>
            <div style={{ padding: "20px 20px 12px", borderBottom: "1px solid var(--t-border-light)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontWeight: 600, fontSize: 14, color: "var(--t-text)", fontFamily: SANS }}>Menu</span>
              <button onClick={() => setShowMobileMenu(false)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "var(--t-text-muted)", lineHeight: 1, padding: "2px 4px" }}>✕</button>
            </div>
            <nav style={{ flex: 1, padding: "8px 0" }}>
              {TABS.map(tab => (
                <button key={tab} onClick={() => { setActiveTab(tab); setShowMobileMenu(false); }} style={{
                  width: "100%", textAlign: "left",
                  padding: "13px 20px", border: "none",
                  background: activeTab === tab ? "var(--t-surface-alt)" : "none",
                  borderLeft: activeTab === tab ? "3px solid var(--t-accent)" : "3px solid transparent",
                  fontSize: 14, fontFamily: SANS,
                  color: activeTab === tab ? "var(--t-text)" : "var(--t-text-secondary)",
                  fontWeight: activeTab === tab ? 600 : 500,
                  cursor: "pointer",
                }}>
                  {tab}
                </button>
              ))}
            </nav>
            <div style={{ padding: "12px 20px 24px", borderTop: "1px solid var(--t-border-light)" }}>
              <button onClick={() => { router.push("/chat"); setShowMobileMenu(false); }} style={{
                width: "100%", padding: "10px 0", textAlign: "center",
                fontSize: 13, fontFamily: SANS, color: "var(--t-text-secondary)",
                background: "none", border: "1px solid var(--t-border)",
                borderRadius: 7, cursor: "pointer", marginBottom: 8,
              }}>
                Chat →
              </button>
            </div>
          </div>
        </>
      )}

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
                <h1 style={{ margin: 0, fontFamily: SERIF, fontWeight: 600, fontSize: 25, letterSpacing: "-0.01em", color: "var(--t-text)" }}>
                  Good morning, {userName.split(" ")[0]}
                </h1>
                <div style={{ marginTop: 5, fontSize: 13, color: "var(--t-text-muted)" }}>Updated nightly after market close · {digest.length} stock{digest.length !== 1 ? "s" : ""} tracked</div>
              </div>

              {/* Portfolio size prompt */}
              {showPortfolioPrompt && (
                <div style={{ background: "var(--t-accent-bg)", border: "1px solid var(--t-accent-border)", borderRadius: 11, padding: "18px 20px", marginBottom: 16 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: "var(--t-text)", marginBottom: 6 }}>One quick question to personalise your advice</div>
                  <div style={{ fontSize: 13, color: "var(--t-text-secondary)", marginBottom: 14 }}>What is your approximate investing portfolio size? This lets us suggest exact share counts — no account linking needed.</div>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    {["$5,000", "$10,000", "$25,000", "$50,000", "$100,000+"].map(opt => (
                      <button key={opt} onClick={() => setPortfolioInput(opt.replace(/[^0-9]/g, ""))}
                        style={{ padding: "6px 14px", borderRadius: 20, border: `1px solid ${portfolioInput === opt.replace(/[^0-9]/g, "") ? "var(--t-accent)" : "var(--t-accent-border)"}`, background: portfolioInput === opt.replace(/[^0-9]/g, "") ? "var(--t-accent)" : "white", color: portfolioInput === opt.replace(/[^0-9]/g, "") ? "white" : "var(--t-accent)", cursor: "pointer", fontSize: 13, fontFamily: MONO }}>
                        {opt}
                      </button>
                    ))}
                    <button onClick={savePortfolioSize} disabled={!portfolioInput}
                      style={{ padding: "6px 18px", borderRadius: 20, background: portfolioInput ? "var(--t-accent)" : "var(--t-border)", color: portfolioInput ? "white" : "var(--t-text-muted)", border: "none", cursor: portfolioInput ? "pointer" : "default", fontSize: 13, fontWeight: 600, fontFamily: SANS }}>
                      Save
                    </button>
                    <button onClick={() => setShowPortfolioPrompt(false)} style={{ background: "none", border: "none", fontSize: 12, color: "var(--t-text-muted)", cursor: "pointer" }}>Skip</button>
                  </div>
                </div>
              )}

              {/* ── Spotlight card ── */}
              {spotlight && sa && vm && (
                <div style={{ background: "var(--t-surface)", border: "2px solid var(--t-accent)", borderRadius: 13, marginBottom: 16, overflow: "hidden" }}>
                  {/* Header */}
                  <div style={{ background: "var(--t-accent)", padding: "12px 20px", display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: 13, color: "var(--t-surface)", fontWeight: 700, letterSpacing: "0.04em" }}>⚡ Today's Opportunity</span>
                    <span style={{ marginLeft: "auto", fontSize: 11, color: "rgba(251,250,247,0.7)", fontFamily: MONO }}>
                      {sa.signal_convergence_score}/7 signals · conviction {sa.conviction_score}/100
                    </span>
                  </div>

                  {/* Ticker + verdict */}
                  <div style={{ padding: "16px 20px 0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                      <span style={{ fontFamily: MONO, fontWeight: 700, fontSize: 22, color: "var(--t-text)" }}>{spotlight.ticker}</span>
                      {spotlight.company_name && <span style={{ fontSize: 13, color: "var(--t-text-secondary)" }}>{spotlight.company_name}</span>}
                      <span style={{ padding: "3px 12px", borderRadius: 20, fontSize: 12, fontFamily: MONO, fontWeight: 700, color: vm.color, background: vm.bg, border: `1px solid ${vm.bd}`, marginLeft: "auto" }}>
                        {vm.label}
                      </span>
                    </div>

                    {/* Trust badges */}
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
                      {sa.entry_quality && (
                        <span style={{ fontSize: 12, fontFamily: MONO, padding: "3px 10px", borderRadius: 20, color: sa.entry_quality === "GREAT" ? "var(--t-green)" : sa.entry_quality === "FAIR" ? "var(--t-yellow)" : "var(--t-red)", background: sa.entry_quality === "GREAT" ? "var(--t-green-bg)" : sa.entry_quality === "FAIR" ? "var(--t-yellow-bg)" : "var(--t-red-bg)", border: `1px solid ${sa.entry_quality === "GREAT" ? "var(--t-green-mid)" : sa.entry_quality === "FAIR" ? "var(--t-yellow-border)" : "var(--t-red-border)"}` }}>
                          Entry: {sa.entry_quality === "GREAT" ? "Great" : sa.entry_quality === "FAIR" ? "Fair" : "Wait"}
                        </span>
                      )}
                      {sa.hold_and_forget_rating === "HOLD_AND_FORGET" && (
                        <span style={{ fontSize: 12, fontFamily: MONO, padding: "3px 10px", borderRadius: 20, color: "var(--t-green)", background: "var(--t-green-bg)", border: "1px solid var(--t-green-mid)" }}>Hold & Forget ✓</span>
                      )}
                      {sa.position_size_pct && (
                        <span style={{ fontSize: 12, fontFamily: MONO, padding: "3px 10px", borderRadius: 20, color: "var(--t-accent)", background: "var(--t-accent-bg)", border: "1px solid var(--t-accent-border)" }}>
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
                            <div style={{ fontSize: 11, fontFamily: MONO, color: "var(--t-text-muted)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>Why now</div>
                            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              {fired.map(([k]) => (
                                <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--t-text-dark)" }}>
                                  <span style={{ color: "var(--t-green)", fontWeight: 700, fontSize: 12 }}>✓</span>
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
                      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 1fr", gap: 8, marginBottom: 14 }}>
                        {([
                          { label: "Bull", pct: sa.scenario_bull_pct, prob: sa.scenario_bull_prob, color: "var(--t-green)", bg: "var(--t-green-bg)", bd: "var(--t-green-mid)" },
                          { label: "Base", pct: sa.scenario_base_pct, prob: sa.scenario_base_prob, color: "var(--t-accent)", bg: "var(--t-accent-bg)", bd: "var(--t-accent-border)" },
                          { label: "Bear", pct: sa.scenario_bear_pct, prob: sa.scenario_bear_prob, color: "var(--t-red)", bg: "var(--t-red-bg)", bd: "var(--t-red-border)" },
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
                    <div style={{ background: "var(--t-surface-alt)", borderRadius: 8, padding: "12px 14px", marginBottom: 16, display: "flex", flexWrap: "wrap", gap: "10px 24px", alignItems: "center" }}>
                      {sa.entry_target && <div><div style={{ fontSize: 10, color: "var(--t-text-muted)", fontFamily: MONO }}>Buy ≤</div><div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "var(--t-green)" }}>${sa.entry_target.toFixed(2)}</div></div>}
                      {sa.stop_loss    && <div><div style={{ fontSize: 10, color: "var(--t-text-muted)", fontFamily: MONO }}>Stop</div><div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "var(--t-red)" }}>${sa.stop_loss.toFixed(2)}</div></div>}
                      {sa.exit_target  && <div><div style={{ fontSize: 10, color: "var(--t-text-muted)", fontFamily: MONO }}>Target</div><div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "var(--t-accent)" }}>${sa.exit_target.toFixed(2)}</div></div>}
                      {sa.hold_period  && <div><div style={{ fontSize: 10, color: "var(--t-text-muted)", fontFamily: MONO }}>Hold</div><div style={{ fontSize: 13, fontWeight: 600, color: "var(--t-text)" }}>{sa.hold_period}</div></div>}
                      {(() => { const sc = shareCount(sa); return sc ? (
                        <div style={{ marginLeft: "auto" }}>
                          <div style={{ fontSize: 10, color: "var(--t-text-muted)", fontFamily: MONO }}>~Shares</div>
                          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: MONO, color: "var(--t-text)" }}>{sc.shares} <span style={{ fontSize: 11, color: "var(--t-text-muted)", fontWeight: 400 }}>(${sc.dollars.toLocaleString()})</span></div>
                        </div>
                      ) : null; })()}
                    </div>
                  </div>

                  {/* Footer */}
                  <div style={{ padding: "0 20px 16px", display: "flex", gap: 10 }}>
                    <button onClick={() => { setActiveTab("My Stocks"); setExpanded(spotlight.ticker); }}
                      style={{ flex: 1, padding: "10px 0", background: "var(--t-accent)", color: "var(--t-surface)", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 14, fontFamily: SANS }}>
                      View Full Analysis →
                    </button>
                    <button onClick={() => { setActiveTab("My Stocks"); }}
                      style={{ padding: "10px 18px", background: "none", color: "var(--t-text-muted)", border: "1px solid var(--t-border)", borderRadius: 8, cursor: "pointer", fontSize: 13, fontFamily: SANS }}>
                      Skip
                    </button>
                  </div>
                </div>
              )}

              {/* ── All Clear card ── */}
              {allClear && (
                <div style={{ background: "var(--t-green-light-bg)", border: "1px solid var(--t-green-border)", borderRadius: 13, padding: "28px 24px", marginBottom: 16, textAlign: "center" }}>
                  <div style={{ fontSize: 28, marginBottom: 10 }}>✓</div>
                  <div style={{ fontSize: 18, fontWeight: 600, color: "var(--t-green)", marginBottom: 8, fontFamily: SERIF }}>All Clear — Nothing to do today</div>
                  <div style={{ fontSize: 13, color: "var(--t-text-secondary)", lineHeight: 1.6 }}>
                    Your {digest.length} stock{digest.length !== 1 ? "s" : ""} are being watched. No high-conviction opportunities cleared the threshold today.<br />
                    Come back tomorrow — the nightly agent runs after market close.
                  </div>
                </div>
              )}

              {/* Important flags */}
              {importantItems.length > 0 && (
                <div style={{ background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 11, padding: "6px 4px 8px", marginBottom: 16 }}>
                  <div style={{ padding: "13px 18px 11px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 15, fontWeight: 600, color: "var(--t-text)" }}>Important signals today</span>
                    <span style={{ fontSize: 10, color: "var(--t-text-muted)", fontFamily: MONO, letterSpacing: "0.08em" }}>{importantItems.length} FLAG{importantItems.length > 1 ? "S" : ""}</span>
                  </div>
                  {importantItems.map(item => {
                    const ivm = item.analysis?.verdict ? VERDICT_META[item.analysis.verdict] ?? VERDICT_META.WATCH : null;
                    return (
                      <div key={item.ticker} onClick={() => { setActiveTab("My Stocks"); setExpanded(item.ticker); }}
                        style={{ display: "flex", alignItems: "center", gap: 13, padding: "12px 18px", borderTop: "1px solid var(--t-border-light)", cursor: "pointer" }}>
                        <span style={{ fontFamily: MONO, fontWeight: 600, fontSize: 13, width: 60, color: "var(--t-text)" }}>{item.ticker}</span>
                        {ivm && <span style={{ fontSize: 10, padding: "3px 9px", background: ivm.bg, color: ivm.color, border: `1px solid ${ivm.bd}`, borderRadius: 20, fontFamily: MONO, fontWeight: 700 }}>{ivm.label}</span>}
                        <span style={{ flex: 1, fontSize: 13, color: "var(--t-text-secondary)" }}>{item.analysis?.importance_reason ?? "—"}</span>
                        <span style={{ fontSize: 12, color: "var(--t-accent)", fontWeight: 600 }}>View →</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* My Stocks teaser */}
              <button onClick={() => setActiveTab("My Stocks")} style={{
                width: "100%", textAlign: "left", background: "var(--t-surface)",
                border: "1px solid var(--t-border)", borderRadius: 11, padding: "15px 20px",
                display: "flex", alignItems: "center", gap: 14, cursor: "pointer", fontFamily: SANS,
              }}>
                <span style={{ fontSize: 10, fontFamily: MONO, letterSpacing: "0.12em", color: "var(--t-text-muted)" }}>MY STOCKS</span>
                <span style={{ fontSize: 14, color: "var(--t-text)" }}>
                  Tracking <b style={{ fontFamily: MONO }}>{digest.length}</b> stock{digest.length !== 1 ? "s" : ""} · {buyCount} buy · {watchCount} hold/watch · {sellCount} sell
                </span>
                <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--t-accent)", fontWeight: 600, whiteSpace: "nowrap" }}>See full table →</span>
              </button>
            </div>
          );
        })()}

        {/* ── My Stocks tab ── */}
        {activeTab === "My Stocks" && (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: "0.75rem" }}>
              <div>
                <h1 style={{ margin: 0, fontFamily: SERIF, fontWeight: 600, fontSize: 25, color: "var(--t-text)" }}>My Stocks</h1>
                <div style={{ marginTop: 5, fontSize: 13, color: "var(--t-text-muted)" }}>
                  {digest.length} stock{digest.length !== 1 ? "s" : ""} · Updated nightly after market close
                </div>
              </div>
              {/* Sort/group control */}
              {digest.length > 0 && (
                <div style={{ display: "flex", gap: 4, background: "var(--t-surface-3)", borderRadius: 9, padding: 3 }}>
                  {([
                    { key: "relevance", label: "Relevance" },
                    { key: "verdict",   label: "Verdict"   },
                    { key: "az",        label: "A–Z"       },
                    { key: "movers",    label: "Movers"    },
                  ] as const).map(opt => (
                    <button key={opt.key} onClick={() => setSortMode(opt.key)} style={{
                      padding: "4px 12px", borderRadius: 6, border: "none",
                      background: sortMode === opt.key ? "var(--t-surface)" : "transparent",
                      boxShadow: sortMode === opt.key ? "0 1px 3px rgba(32,33,28,0.1)" : "none",
                      color: sortMode === opt.key ? "var(--t-text)" : "var(--t-text-muted)",
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

            {/* ── Sticky add/search bar ── */}
            <div style={{
              position: "sticky", top: 60, zIndex: 30,
              background: "var(--t-bg)",
              margin: isMobile ? "0 -16px" : "0 -32px",
              padding: isMobile ? "8px 16px 12px" : "8px 32px 12px",
              marginBottom: 0,
            }}>
              <form onSubmit={handleAdd} style={{
                display: "flex", gap: "0.5rem",
                padding: "0.75rem 1rem", background: "var(--t-surface)",
                border: "1px solid var(--t-border)", borderRadius: 11,
                alignItems: "center", flexWrap: "wrap",
                boxShadow: "0 2px 8px rgba(32,33,28,0.07)",
              }}>
                <div style={{ position: "relative", flex: "1 1 260px" }}>
                  <input
                    value={query}
                    onChange={e => handleSearchInput(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    onBlur={() => setTimeout(() => { setShowSuggestions(false); setHighlightedIdx(-1); }, 200)}
                    onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                    placeholder="Search or add stock (e.g. NFLX)…"
                    autoComplete="off"
                    style={{
                      width: "100%", padding: "0.5rem 2rem 0.5rem 0.75rem", background: "var(--t-surface-2)",
                      border: "1px solid var(--t-border)", borderRadius: 7,
                      color: "var(--t-text)", fontSize: "0.88rem", fontFamily: SANS,
                      outline: "none", boxSizing: "border-box",
                    }}
                  />
                  {query && (
                    <button type="button" onClick={() => {
                      setQuery(""); setTicker(""); setCompanyName("");
                      setSuggestions([]); setShowSuggestions(false); setError("");
                    }} style={{
                      position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                      background: "none", border: "none", cursor: "pointer",
                      color: "var(--t-text-muted)", fontSize: 16, padding: "0 2px", lineHeight: 1,
                    }}>×</button>
                  )}
                  {showSuggestions && suggestions.length > 0 && (
                    <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 50, background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 9, overflow: "hidden", boxShadow: "0 8px 24px rgba(32,33,28,0.1)" }}>
                      {suggestions.map((s, idx) => (
                        <div key={s.ticker} onMouseDown={() => handleSelect(s)}
                          style={{ padding: "0.6rem 0.85rem", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", borderBottom: "1px solid var(--t-border-light)", background: idx === highlightedIdx ? "var(--t-surface-alt)" : "transparent" }}
                          onMouseEnter={() => setHighlightedIdx(idx)}
                          onMouseLeave={() => setHighlightedIdx(-1)}>
                          <div>
                            <span style={{ fontWeight: 600, fontSize: "0.88rem", color: "var(--t-text)", fontFamily: MONO }}>{s.ticker}</span>
                            <span style={{ marginLeft: "0.5rem", fontSize: "0.82rem", color: "var(--t-text-secondary)" }}>{s.name}</span>
                          </div>
                          <span style={{ fontSize: "0.75rem", color: "var(--t-text-muted)", flexShrink: 0 }}>{s.exchange}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <button type="submit" disabled={!ticker && !query.trim()} style={{
                  padding: "0.5rem 1.1rem",
                  background: (ticker || query.trim()) ? "var(--t-accent)" : "var(--t-border)",
                  color: (ticker || query.trim()) ? "var(--t-surface)" : "var(--t-text-muted)",
                  border: "none", borderRadius: 7,
                  cursor: (ticker || query.trim()) ? "pointer" : "not-allowed",
                  fontWeight: 600, fontSize: "0.88rem", fontFamily: SANS,
                  transition: "background 0.15s", whiteSpace: "nowrap",
                }}>
                  + Add
                </button>
                {error && <span style={{ color: "var(--t-red)", fontSize: "0.8rem", width: "100%" }}>{error}</span>}
              </form>
            </div>

            <div style={{ marginTop: 16 }}>
            {loading ? (
              <div style={{ textAlign: "center", padding: "3rem", color: "var(--t-text-muted)" }}>Loading your digest…</div>
            ) : digest.length === 0 ? (
              <div style={{ textAlign: "center", padding: "3rem", background: "var(--t-surface)", borderRadius: 11, border: "1px solid var(--t-border)", color: "var(--t-text-muted)" }}>
                <div style={{ fontSize: "1.8rem", marginBottom: "0.5rem" }}>—</div>
                <div style={{ fontWeight: 600, marginBottom: "0.35rem", color: "var(--t-text)" }}>Add your first stock to get started</div>
                <div style={{ fontSize: "0.82rem" }}>Try: NFLX, MRVL, SOXQ, SOXL</div>
              </div>
            ) : (() => {
              const filterQ = ticker ? ticker.toLowerCase() : query.trim().toLowerCase();
              const filteredDigest = filterQ
                ? digest.filter(d =>
                    ticker
                      ? d.ticker.toLowerCase() === filterQ
                      : d.ticker.toLowerCase().includes(filterQ) ||
                        (d.company_name || "").toLowerCase().includes(filterQ)
                  )
                : digest;

              const VERDICT_ORDER = ["BUY", "HOLD", "WATCH", "SELL"];
              const VERDICT_META_GROUP: Record<string, { label: string; color: string; bg: string; bd: string }> = {
                BUY:   { label: "Buy",   color: "var(--t-green)", bg: "var(--t-green-bg)", bd: "var(--t-green-mid)" },
                HOLD:  { label: "Hold",  color: "var(--t-yellow)", bg: "var(--t-yellow-bg)", bd: "var(--t-yellow-border)" },
                WATCH: { label: "Watch", color: "var(--t-text-muted)", bg: "var(--t-surface-warm)", bd: "var(--t-border)" },
                SELL:  { label: "Sell",  color: "var(--t-red)", bg: "var(--t-red-bg)", bd: "var(--t-red-border)" },
              };

              const colHeaders = !isMobile && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 100px 130px 80px 100px 140px 120px", padding: "0 1.25rem", marginBottom: "0.4rem", gap: "1rem" }}>
                  {["Stock", "Verdict", "Price", "Conviction", "Trend", "Signal", ""].map(h => (
                    <div key={h} style={{ fontSize: "0.63rem", color: "var(--t-text-dim)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.09em", fontFamily: MONO }}>{h}</div>
                  ))}
                </div>
              );

              const renderRow = (item: DigestItem) => (
                <StockRow
                  key={item.ticker} item={item} idToken={idToken}
                  expanded={expanded === item.ticker}
                  onToggle={() => {
                    const isExpanding = expanded !== item.ticker;
                    if (!isExpanding && item.change_summary) {
                      setDigest(prev => prev.map(d => d.ticker === item.ticker ? { ...d, change_summary: null } : d));
                    }
                    setExpanded(isExpanding ? item.ticker : null);
                    if (isExpanding && item.has_unread) handleMarkRead(item.ticker);
                  }}
                  onChat={handleChat} onRemove={handleRemove}
                  isMobile={isMobile}
                />
              );

              const sectionHeader = (label: string, count: number, color: string, bg: string, bd: string) => (
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <span style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 700, padding: "2px 10px", borderRadius: 20, color, background: bg, border: `1px solid ${bd}`, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
                  <span style={{ fontSize: "0.68rem", color: "var(--t-text-muted)", fontFamily: MONO }}>{count} stock{count > 1 ? "s" : ""}</span>
                  <div style={{ flex: 1, height: 1, background: "var(--t-border)" }} />
                </div>
              );

              if (filteredDigest.length === 0) {
                return (
                  <div style={{ textAlign: "center", padding: "2.5rem", background: "var(--t-surface)", borderRadius: 11, border: "1px solid var(--t-border)", color: "var(--t-text-muted)" }}>
                    <div style={{ fontWeight: 600, marginBottom: "0.35rem", color: "var(--t-text)" }}>No stocks match "{query.trim()}"</div>
                    <div style={{ fontSize: "0.82rem" }}>Hit "+ Add" to add it to your watchlist</div>
                  </div>
                );
              }

              // ── Relevance: flat list sorted by convergence_score desc, then conviction_score desc ──
              if (sortMode === "relevance") {
                const sorted = [...filteredDigest].sort((a, b) => {
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
                  items: filteredDigest.filter(d => d.analysis?.verdict === v),
                })).filter(g => g.items.length > 0);
                const pending = filteredDigest.filter(d => !d.analysis);
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
                        {sectionHeader("Pending", pending.length, "var(--t-text-muted)", "var(--t-surface-3)", "var(--t-border)")}
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{pending.map(renderRow)}</div>
                      </div>
                    )}
                  </div>
                );
              }

              // ── A–Z: flat alphabetical ──
              if (sortMode === "az") {
                const sorted = [...filteredDigest].sort((a, b) => a.ticker.localeCompare(b.ticker));
                return (
                  <div>
                    {colHeaders}
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{sorted.map(renderRow)}</div>
                  </div>
                );
              }

              // ── Movers: sorted by abs(day_change_pct) desc ──
              const sorted = [...filteredDigest].sort((a, b) => Math.abs(b.analysis?.day_change_pct ?? 0) - Math.abs(a.analysis?.day_change_pct ?? 0));
              return (
                <div>
                  {colHeaders}
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{sorted.map(renderRow)}</div>
                </div>
              );
            })()}
            </div>
          </div>
        )}

        {/* ── Discover + Compare placeholders ── */}
        {(activeTab === "Discover" || activeTab === "Compare") && (
          <div style={{ display: "flex", justifyContent: "center", paddingTop: 80 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 13, padding: "40px 64px" }}>
              <div style={{ width: 44, height: 44, borderRadius: 10, background: "var(--t-accent-light)", border: "1px solid var(--t-accent-border)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>
                {activeTab === "Discover" ? "🔍" : "📊"}
              </div>
              <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 20, color: "var(--t-text)" }}>
                {activeTab} — coming soon
              </div>
              <div style={{ fontSize: 13, color: "var(--t-text-muted)", maxWidth: "30ch", lineHeight: 1.6, textAlign: "center" }}>
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
