"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signOut } from "next-auth/react";
import ThemeToggle from "@/app/components/ThemeToggle";
import Logo from "@/app/components/Logo";

import { API, MONO, SANS, SERIF, VERDICT_META, ExpandedDetail } from "@/app/components/StockDetail";
import type { Analysis } from "@/app/components/StockDetail";


interface DigestItem {
  ticker: string;
  company_name: string | null;
  is_leveraged: boolean;
  shares: number | null;
  avg_cost: number | null;
  analysis: Analysis | null;
  has_unread: boolean;
  change_summary: string | null;
  days_since_read: number | null;
  close_5d: number[] | null;
  analysis_disabled: boolean;
}

interface ImportPosition {
  ticker: string;
  shares: number;
  avg_cost: number | null;
  company_name: string | null;
}

function MiniRangeBar({ lo, hi, pct }: { lo?: number | null; hi?: number | null; pct: number }) {
  const clamp = Math.max(0, Math.min(100, pct));
  const dotColor = clamp < 33 ? "var(--t-green)" : clamp < 67 ? "var(--t-yellow)" : "var(--t-red)";
  const fmt = (n: number) => n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${n.toFixed(0)}`;
  return (
    <div style={{ marginTop: "0.3rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
        {lo != null && <span style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, flexShrink: 0 }}>{fmt(lo)}</span>}
        <div style={{ position: "relative", height: 3, background: "var(--t-border)", borderRadius: 99, flex: 1 }}>
          <div style={{ position: "absolute", left: 0, width: `${clamp}%`, height: "100%", background: dotColor, borderRadius: 99, opacity: 0.3 }} />
          <div style={{ position: "absolute", left: `${clamp}%`, top: "50%", transform: "translate(-50%, -50%)", width: 7, height: 7, borderRadius: "50%", background: dotColor, border: "1.5px solid var(--t-surface)" }} />
        </div>
        {hi != null && <span style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, flexShrink: 0 }}>{fmt(hi)}</span>}
        <span style={{ fontSize: "0.6rem", color: dotColor, fontFamily: MONO, fontWeight: 700, flexShrink: 0 }}>{clamp.toFixed(0)}%</span>
      </div>
    </div>
  );
}

function RsiPill({ rsi }: { rsi: number }) {
  const isOB = rsi >= 70;
  const isOS = rsi <= 30;
  const color  = isOB ? "var(--t-red)"        : isOS ? "var(--t-green)"        : "var(--t-text-secondary)";
  const bg     = isOB ? "var(--t-red-bg)"     : isOS ? "var(--t-green-bg)"     : "var(--t-surface-3)";
  const border = isOB ? "var(--t-red-border)" : isOS ? "var(--t-green-border)" : "var(--t-border)";
  const tag    = isOB ? "OB" : isOS ? "OS" : null;
  const tip    = isOB
    ? `RSI ${rsi.toFixed(0)} — Overbought. The stock has run up fast and may be due for a pullback.`
    : isOS
    ? `RSI ${rsi.toFixed(0)} — Oversold. The stock has sold off heavily and may be due for a bounce.`
    : `RSI ${rsi.toFixed(0)} — Neutral momentum (14-day). Above 70 = overbought, below 30 = oversold.`;
  return (
    <div title={tip} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 8px", borderRadius: 20, background: bg, border: `1px solid ${border}`, cursor: "default" }}>
      <span style={{ fontWeight: 700, fontSize: "0.75rem", color, fontFamily: MONO, letterSpacing: "0.02em" }}>RSI {rsi.toFixed(0)}</span>
      {tag && <span style={{ fontSize: "0.6rem", color, fontWeight: 700, fontFamily: MONO, letterSpacing: "0.06em" }}>{tag}</span>}
    </div>
  );
}

function MaBadge({ price, ma50, ma200 }: { price: number; ma50: number | null; ma200: number | null }) {
  const above50  = ma50  ? price > ma50  : null;
  const above200 = ma200 ? price > ma200 : null;
  return (
    <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
      {ma50 != null && (
        <span style={{ fontSize: "0.64rem", color: above50 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>
          {above50 ? "▲" : "▼"} MA50
        </span>
      )}
      {ma200 != null && (
        <span style={{ fontSize: "0.64rem", color: above200 ? "var(--t-green)" : "var(--t-red)", fontFamily: MONO }}>
          {above200 ? "▲" : "▼"} MA200
        </span>
      )}
    </div>
  );
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

function PortfolioStrip({ shares, avgCost, currentPrice, totalPortfolioValue, verdict, isMobile, onSold, onEdit }: {
  shares: number; avgCost: number | null; currentPrice: number | null;
  totalPortfolioValue: number; verdict: string | null; isMobile: boolean;
  onSold?: () => void; onEdit?: () => void;
}) {
  const currentValue = currentPrice != null ? shares * currentPrice : null;
  const invested = avgCost != null ? shares * avgCost : null;
  const pl = currentValue != null && invested != null ? currentValue - invested : null;
  const plPct = pl != null && invested != null && invested > 0 ? (pl / invested) * 100 : null;
  const weight = currentValue != null && totalPortfolioValue > 0 ? (currentValue / totalPortfolioValue) * 100 : null;

  const aiColor = verdict === "BUY" ? "var(--t-green)" : verdict === "SELL" ? "var(--t-red)" : "var(--t-yellow)";
  const aiLabel = verdict === "BUY" ? "AI: Hold / Add" : verdict === "SELL" ? "AI: Consider Selling" : "AI: Watch Closely";

  const fmt$ = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const fmtPct = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;

  return (
    <div onClick={e => e.stopPropagation()} style={{
      borderTop: "1px solid var(--t-border-light)", padding: "8px 20px",
      background: "var(--t-surface-2)", display: "flex", alignItems: "center",
      gap: isMobile ? "0.75rem" : "1.5rem", flexWrap: "wrap",
    }}>
      <div>
        <div style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.08em" }}>Shares</div>
        <div style={{ fontSize: "0.82rem", fontWeight: 600, fontFamily: MONO, color: "var(--t-text)" }}>
          {shares % 1 === 0 ? shares : shares.toFixed(6).replace(/\.?0+$/, "")}
          {avgCost != null && <span style={{ fontWeight: 400, color: "var(--t-text-muted)" }}> @ {fmt$(avgCost)}</span>}
        </div>
      </div>
      {currentValue != null && (
        <div>
          <div style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.08em" }}>Value</div>
          <div style={{ fontSize: "0.82rem", fontWeight: 600, fontFamily: MONO, color: "var(--t-text)" }}>{fmt$(currentValue)}</div>
        </div>
      )}
      {pl != null && plPct != null && (
        <div>
          <div style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.08em" }}>P&L</div>
          <div style={{ fontSize: "0.82rem", fontWeight: 700, fontFamily: MONO, color: pl >= 0 ? "var(--t-green)" : "var(--t-red)" }}>
            {pl >= 0 ? "+" : ""}{fmt$(pl)} <span style={{ fontSize: "0.72rem" }}>({fmtPct(plPct)})</span>
          </div>
        </div>
      )}
      {weight != null && (
        <div>
          <div style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.08em" }}>Portfolio %</div>
          <div style={{ fontSize: "0.82rem", fontWeight: 600, fontFamily: MONO, color: "var(--t-text-secondary)" }}>{weight.toFixed(1)}%</div>
        </div>
      )}
      {verdict && (
        <div style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 600, color: aiColor, flexShrink: 0 }}>{aiLabel}</div>
      )}
      <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
        <button
          onClick={e => { e.stopPropagation(); onEdit?.(); }}
          style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 600, padding: "3px 10px", borderRadius: 5, border: "1px solid var(--t-border)", background: "transparent", color: "var(--t-accent)", cursor: "pointer" }}
        >Edit ✎</button>
        <button
          onClick={e => { e.stopPropagation(); onSold?.(); }}
          style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 600, padding: "3px 10px", borderRadius: 5, border: "1px solid var(--t-border)", background: "transparent", color: "var(--t-text-muted)", cursor: "pointer" }}
        >Sold ✕</button>
      </div>
    </div>
  );
}

function PortfolioSummary({ items }: { items: DigestItem[] }) {
  const withPrice  = items.filter(d => d.shares != null && d.analysis?.current_price != null);
  const withCost   = withPrice.filter(d => d.avg_cost != null);
  const totalValue    = withPrice.reduce((s, d) => s + d.shares! * d.analysis!.current_price!, 0);
  const totalInvested = withCost.reduce((s, d) => s + d.shares! * d.avg_cost!, 0);
  const pl    = totalInvested > 0 ? totalValue - totalInvested : null;
  const plPct = pl != null && totalInvested > 0 ? (pl / totalInvested) * 100 : null;
  const fmt$  = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div style={{ background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 11, padding: "14px 20px", marginBottom: 16, display: "flex", gap: "2rem", flexWrap: "wrap", alignItems: "center" }}>
      <div>
        <div style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.1em" }}>Portfolio Value</div>
        <div style={{ fontSize: "1.4rem", fontWeight: 700, fontFamily: MONO, color: "var(--t-text)", marginTop: 2 }}>{fmt$(totalValue)}</div>
      </div>
      {totalInvested > 0 && (
        <div>
          <div style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.1em" }}>Invested</div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700, fontFamily: MONO, color: "var(--t-text-muted)", marginTop: 2 }}>{fmt$(totalInvested)}</div>
        </div>
      )}
      {pl != null && plPct != null && (
        <div>
          <div style={{ fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.1em" }}>Total P&L</div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700, fontFamily: MONO, color: pl >= 0 ? "var(--t-green)" : "var(--t-red)", marginTop: 2 }}>
            {pl >= 0 ? "+" : ""}{fmt$(Math.abs(pl))}
            <span style={{ fontSize: "0.85rem", marginLeft: "0.4rem" }}>({plPct >= 0 ? "+" : ""}{plPct.toFixed(2)}%)</span>
          </div>
        </div>
      )}
      <div style={{ marginLeft: "auto", fontSize: "0.72rem", fontFamily: MONO, color: "var(--t-text-muted)" }}>
        {items.length} position{items.length !== 1 ? "s" : ""}
        {withCost.length < items.length && ` · ${items.length - withCost.length} missing cost`}
      </div>
    </div>
  );
}

function StockRow({
  item, expanded, onToggle, onChat, onRemove, isMobile, idToken, txCacheRef,
  isPortfolio, totalPortfolioValue, onAddToPortfolio, onSold, onEdit,
}: {
  item: DigestItem; expanded: boolean; isMobile: boolean; idToken: string;
  onToggle: () => void; onChat: (ticker: string) => void; onRemove: (ticker: string) => void;
  txCacheRef: React.MutableRefObject<Record<string, Record<string, string | null>>>;
  isPortfolio?: boolean;
  totalPortfolioValue?: number;
  onAddToPortfolio?: () => void;
  onSold?: () => void;
  onEdit?: () => void;
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
    <div id={`stock-row-${item.ticker}`} style={{
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
              {vm ? <VerdictBadge vm={vm} /> : null}
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
                <span
                  title={a.rsi >= 70 ? `RSI ${a.rsi.toFixed(0)} — Overbought. The stock has run up fast and may be due for a pullback.` : a.rsi <= 30 ? `RSI ${a.rsi.toFixed(0)} — Oversold. Sold off heavily, may be due for a bounce.` : `RSI ${a.rsi.toFixed(0)} — Neutral 14-day momentum. Above 70 = overbought, below 30 = oversold.`}
                  style={{ fontSize: "0.72rem", fontFamily: MONO, color: a.rsi >= 70 ? "var(--t-red)" : a.rsi <= 30 ? "var(--t-green)" : "var(--t-text-muted)", cursor: "default" }}>
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

          {/* Row 3.5: S&P + Sector context */}
          {a && (a.sp500_day_chg != null || a.sector_day_chg != null) && (
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.3rem", flexWrap: "wrap" }}
              title="Today's performance vs the broader market and your stock's sector">
              {a.sp500_day_chg != null && (
                <span style={{ fontSize: "0.65rem", fontFamily: MONO, color: "var(--t-text-dim)" }}>
                  S&P {a.sp500_day_chg >= 0 ? "+" : ""}{a.sp500_day_chg.toFixed(1)}%
                </span>
              )}
              {a.sector_day_chg != null && a.sector_etf && (
                <span style={{ fontSize: "0.65rem", fontFamily: MONO, color: "var(--t-text-dim)" }}>
                  · {a.sector_etf} {a.sector_day_chg >= 0 ? "+" : ""}{a.sector_day_chg.toFixed(1)}%
                </span>
              )}
            </div>
          )}

          {/* Row 4: 52w mini bar (if available) */}
          {a?.range_position_pct != null && (
            <div style={{ marginTop: "0.35rem" }}>
              <MiniRangeBar lo={a.week_52_low} hi={a.week_52_high} pct={a.range_position_pct} />
            </div>
          )}

          {/* Row 5: Sparkline + Ask AI (always visible) */}
          {a && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "0.5rem" }}>
              {item.close_5d ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <Sparkline prices={item.close_5d} width={120} height={28} />
                  <span style={{ fontSize: "0.57rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.04em" }}>7d price</span>
                </div>
              ) : <span />}
              <button
                onClick={e => { e.stopPropagation(); onChat(item.ticker); }}
                style={{ fontSize: "0.7rem", fontFamily: MONO, fontWeight: 600, padding: "4px 12px", borderRadius: 6, border: "1px solid var(--t-accent)", background: "transparent", color: "var(--t-accent)", cursor: "pointer" }}
              >Ask AI →</button>
            </div>
          )}

          {!a && (
            <div style={{ marginTop: "0.5rem" }}>
              <span style={{
                fontSize: "0.65rem", fontFamily: MONO, fontWeight: 600, padding: "3px 10px", borderRadius: 20, letterSpacing: "0.04em",
                background: item.analysis_disabled ? "var(--t-yellow-bg)" : "var(--t-surface-3)",
                border: `1px solid ${item.analysis_disabled ? "var(--t-yellow-border)" : "var(--t-border)"}`,
                color: item.analysis_disabled ? "var(--t-yellow)" : "var(--t-text-muted)",
              }}>
                {item.analysis_disabled ? "Daily analysis disabled for this stock" : "Analysis runs nightly"}
              </span>
            </div>
          )}

          {a && (
            <div style={{ marginTop: "0.4rem", textAlign: "right" }}>
              <span style={{ color: "var(--t-text-dim)", fontSize: "0.68rem", transition: "transform 0.2s", transform: expanded ? "rotate(180deg)" : "rotate(0deg)", display: "inline-block" }}>▼</span>
            </div>
          )}
        </div>
      ) : (
        /* ── Desktop grid layout ── */
        /* Columns: STOCK | VERDICT | PRICE | CONVICTION | RSI/TREND | SIGNALS | ACTIONS */
        <div
          onClick={a ? onToggle : undefined}
          onMouseEnter={e => { if (a) e.currentTarget.style.background = "var(--t-surface-2)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = ""; }}
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 110px 185px 80px 100px 130px 100px",
            alignItems: "center", padding: "0.85rem 1.25rem",
            cursor: a ? "pointer" : "default", gap: "1rem",
            transition: "background 0.12s ease",
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

          {/* Verdict — solid block (or pending spanning message) */}
          {!a ? (
            <div style={{ gridColumn: "2 / 7", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                fontSize: "0.65rem", fontFamily: MONO, fontWeight: 600, padding: "3px 10px", borderRadius: 20, letterSpacing: "0.04em",
                background: item.analysis_disabled ? "var(--t-yellow-bg)" : "var(--t-surface-3)",
                border: `1px solid ${item.analysis_disabled ? "var(--t-yellow-border)" : "var(--t-border)"}`,
                color: item.analysis_disabled ? "var(--t-yellow)" : "var(--t-text-muted)",
              }}>
                {item.analysis_disabled ? "Daily analysis disabled for this stock" : "Analysis runs nightly"}
              </span>
            </div>
          ) : (
            <>
              <div>
                {vm ? <VerdictBadge vm={vm} /> : null}
              </div>

              {/* Price + change + vs S&P + 52w mini bar + MA */}
              <div>
                {a.current_price != null ? (
                  <>
                    <div style={{ fontWeight: 700, fontSize: "0.98rem", fontFamily: MONO, color: "var(--t-text)" }}>${a.current_price.toFixed(2)}</div>
                    {a.day_change_pct != null && (
                      <div style={{ fontSize: "0.72rem", color: chgColor, fontWeight: 600, fontFamily: MONO }}>
                        {a.day_change_pct >= 0 ? "▲" : "▼"} {Math.abs(a.day_change_pct).toFixed(2)}%
                      </div>
                    )}
                    {(a.sp500_day_chg != null || a.sector_day_chg != null) && (
                      <div style={{ display: "flex", gap: "0.35rem", marginTop: "0.2rem", flexWrap: "wrap" }}
                        title="Today's performance vs the broader market and your stock's sector">
                        {a.sp500_day_chg != null && (
                          <span style={{ fontSize: "0.6rem", fontFamily: MONO, color: "var(--t-text-dim)" }}>
                            S&P {a.sp500_day_chg >= 0 ? "+" : ""}{a.sp500_day_chg.toFixed(1)}%
                          </span>
                        )}
                        {a.sector_day_chg != null && a.sector_etf && (
                          <span style={{ fontSize: "0.6rem", fontFamily: MONO, color: "var(--t-text-dim)" }}>
                            · {a.sector_etf} {a.sector_day_chg >= 0 ? "+" : ""}{a.sector_day_chg.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    )}
                    {a.range_position_pct != null && <MiniRangeBar lo={a.week_52_low} hi={a.week_52_high} pct={a.range_position_pct} />}
                    {(a.ma_50 || a.ma_200) && (
                      <div style={{ marginTop: "0.15rem" }}>
                        <MaBadge price={a.current_price} ma50={a.ma_50} ma200={a.ma_200} />
                      </div>
                    )}
                  </>
                ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.82rem" }}>—</span>}
              </div>

              {/* Conviction — hero number */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
                {a.conviction_score != null ? (
                  <>
                    <span style={{ fontSize: "1.3rem", fontWeight: 700, fontFamily: MONO, color: a.conviction_score >= 70 ? "var(--t-green)" : a.conviction_score >= 45 ? "var(--t-yellow)" : "var(--t-red)", lineHeight: 1 }}>{a.conviction_score}</span>
                    <span style={{ fontSize: "0.58rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.05em" }}>/100</span>
                  </>
                ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.82rem" }}>—</span>}
              </div>

              {/* Trend — sparkline + "7d price" label + RSI pill */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 3 }}>
                {item.close_5d ? (
                  <>
                    <Sparkline prices={item.close_5d} width={88} height={30} />
                    <span style={{ fontSize: "0.58rem", color: "var(--t-text-dim)", fontFamily: MONO, letterSpacing: "0.04em" }}>7d price</span>
                  </>
                ) : (
                  a.rsi != null ? <RsiPill rsi={a.rsi} /> : <span style={{ color: "var(--t-text-muted)", fontSize: "0.78rem" }}>—</span>
                )}
                {item.close_5d && a.rsi != null && <RsiPill rsi={a.rsi} />}
              </div>

              {/* Signals — convergence score + analyst + event */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                {a.signal_convergence_score != null ? (
                  <div style={{ display: "flex", alignItems: "baseline", gap: 2 }}>
                    <span style={{ fontWeight: 700, fontSize: "1.05rem", fontFamily: MONO, color: a.signal_convergence_score >= 6 ? "var(--t-green)" : a.signal_convergence_score >= 4 ? "var(--t-yellow)" : "var(--t-red)", lineHeight: 1 }}>
                      {a.signal_convergence_score}
                    </span>
                    <span style={{ fontSize: "0.6rem", color: "var(--t-text-dim)", fontFamily: MONO }}>/10</span>
                  </div>
                ) : (
                  a.analyst_consensus ? null : <span style={{ color: "var(--t-text-muted)", fontSize: "0.78rem" }}>—</span>
                )}
                {a.analyst_consensus && (
                  <span style={{ fontSize: "0.67rem", color: "var(--t-text-muted)", fontFamily: MONO, lineHeight: 1.2 }}>
                    <span style={{ color: "var(--t-text)", fontWeight: 600 }}>{a.analyst_consensus}</span> analysts
                  </span>
                )}
                {upcomingEvent && <span style={{ fontSize: "0.67rem", color: "var(--t-yellow)", fontFamily: MONO }}>⚡ {upcomingEvent}</span>}
              </div>
            </>
          )}

          {/* Actions — Ask AI (always visible) + chevron + remove */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", justifyContent: "flex-end" }}>
            {a && (
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

      {/* ── Portfolio position strip ── */}
      {isPortfolio && item.shares != null && (
        <PortfolioStrip
          shares={item.shares}
          avgCost={item.avg_cost}
          currentPrice={a?.current_price ?? null}
          totalPortfolioValue={totalPortfolioValue ?? 0}
          verdict={a?.verdict ?? null}
          isMobile={isMobile}
          onSold={onSold}
          onEdit={onEdit}
        />
      )}

      {/* ── Watchlist: "Add to Portfolio" prompt ── */}
      {!isPortfolio && item.shares == null && (
        <div style={{ borderTop: "1px solid var(--t-border-light)", padding: "8px 20px", background: "var(--t-surface-2)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: "0.68rem", color: "var(--t-text-muted)", fontFamily: MONO }}>Watchlist only — no position</span>
          <button
            onClick={e => { e.stopPropagation(); onAddToPortfolio?.(); }}
            style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 600, padding: "3px 10px", borderRadius: 5, border: "1px solid var(--t-accent)", background: "transparent", color: "var(--t-accent)", cursor: "pointer" }}
          >+ Add Position</button>
        </div>
      )}

      {expanded && a && <ExpandedDetail a={a} isMobile={isMobile} changeSummary={item.change_summary} daysSinceRead={item.days_since_read} idToken={idToken} txCacheRef={txCacheRef} />}
    </div>
  );
}

const TABS = ["Dashboard", "Stocks", "Discover"] as const;
type Tab = typeof TABS[number];

export default function DashboardClient({ userName, idToken }: { userName: string; idToken: string }) {
  const router = useRouter();
  const [digest, setDigest] = useState<DigestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [ticker, setTicker] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  // Dashboard "view more" → switch to Stocks, expand the card, AND bring it into
  // view — with 30+ tickers the expanded card is usually below the fold, which
  // made the navigation look like a no-op.
  function jumpToStock(ticker: string) {
    setActiveTab("Stocks");
    setExpanded(ticker);
    setTimeout(() => {
      document.getElementById(`stock-row-${ticker}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 150);
  }
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<{ ticker: string; name: string; exchange: string }[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState(-1);
  const [activeTab, setActiveTab] = useState<Tab>("Stocks");
  const watchlistSectionRef = useRef<HTMLDivElement>(null);
  const [portfolioSize, setPortfolioSize] = useState<number | null>(null);
  const [showPortfolioPrompt, setShowPortfolioPrompt] = useState(false);
  const [portfolioInput, setPortfolioInput] = useState("");
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [sortMode, setSortMode] = useState<"relevance" | "verdict" | "az" | "movers">("relevance");
  // Portfolio modal state
  const [addToPortfolioTicker, setAddToPortfolioTicker] = useState<string | null>(null);
  const [portfolioShares, setPortfolioShares] = useState("");
  const [portfolioAvgCost, setPortfolioAvgCost] = useState("");
  // Import modal state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importStep, setImportStep] = useState<"upload" | "review">("upload");
  const [importPositions, setImportPositions] = useState<ImportPosition[]>([]);
  const [importLoading, setImportLoading] = useState(false);
  const [importError, setImportError] = useState("");
  // Toast notifications
  const [toast, setToast] = useState<{ message: string; visible: boolean } | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Translation cache lifted here so it survives card collapse/re-expand
  const txCacheRef = useRef<Record<string, Record<string, string | null>>>({});
  const profileMenuRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  function showToast(message: string) {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ message, visible: true });
    toastTimerRef.current = setTimeout(() => {
      setToast(prev => prev ? { ...prev, visible: false } : null);
      toastTimerRef.current = setTimeout(() => setToast(null), 400);
    }, 2500);
  }

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

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
        setHighlightedIdx(-1);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
      setIsAdmin(!!u.is_admin);
      if (u.portfolio_size) {
        setPortfolioSize(u.portfolio_size);
      } else {
        setShowPortfolioPrompt(true);
      }
    }
  }

  async function submitFeedback() {
    if (!feedbackText.trim()) return;
    const r = await fetch(`${API}/feedback?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: feedbackText.trim() }),
    });
    if (r.ok) {
      setFeedbackSent(true);
      setFeedbackText("");
      setTimeout(() => { setShowFeedbackModal(false); setFeedbackSent(false); }, 1500);
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
    setDigest(prev => {
      if (prev.some(i => i.ticker === effectiveTicker)) return prev; // already in list
      return [...prev, { ticker: effectiveTicker, company_name: savedCompany || null, is_leveraged: false, shares: null, avg_cost: null, analysis: null, has_unread: false, change_summary: null, days_since_read: null, close_5d: null, analysis_disabled: false }];
    });

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
    if (e.key === "Escape") {
      e.preventDefault();
      setShowSuggestions(false);
      setSuggestions([]);
      setHighlightedIdx(-1);
      searchInputRef.current?.blur();
      return;
    }
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
    const existing = await fetch(`${API}/conversations/by-ticker/${t}?id_token=${encodeURIComponent(idToken)}`);
    if (existing.ok) {
      const convs = await existing.json();
      if (convs.length > 0) { router.push(`/chat?conv=${convs[0].id}`); return; }
    }
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: t }),
    });
    if (r.ok) { const conv = await r.json(); router.push(`/chat?conv=${conv.id}`); }
  }

  async function handleSetPortfolio(ticker: string) {
    const shares = parseFloat(portfolioShares);
    const avgCost = portfolioAvgCost.trim() ? parseFloat(portfolioAvgCost) : null;
    if (!shares || shares <= 0) return;
    const isEditing = digest.some(d => d.ticker === ticker && d.shares != null);
    setDigest(prev => prev.map(d => d.ticker === ticker ? { ...d, shares, avg_cost: avgCost } : d));
    setAddToPortfolioTicker(null);
    setPortfolioShares("");
    setPortfolioAvgCost("");
    showToast(isEditing ? `${ticker} position updated` : `${ticker} added to My Positions`);
    try {
      const r = await fetch(`${API}/watchlist/${encodeURIComponent(ticker)}/portfolio?id_token=${encodeURIComponent(idToken)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shares, avg_cost: avgCost }),
      });
      if (!r.ok) fetchDigest(true);
    } catch { fetchDigest(true); }
  }

  async function handleSold(ticker: string) {
    setDigest(prev => prev.map(d => d.ticker === ticker ? { ...d, shares: null, avg_cost: null } : d));
    showToast(`${ticker} moved to Watchlist`);
    try {
      await fetch(`${API}/watchlist/${encodeURIComponent(ticker)}/sell?id_token=${encodeURIComponent(idToken)}`, { method: "PATCH" });
    } catch { fetchDigest(true); }
  }

  async function handleImportFile(file: File) {
    setImportLoading(true);
    setImportError("");
    const form = new FormData();
    form.append("file", file);
    try {
      const r = await fetch(`${API}/portfolio/import/preview?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST",
        body: form,
      });
      if (r.ok) {
        const { positions } = await r.json();
        setImportPositions(positions);
        setImportStep("review");
      } else {
        const d = await r.json();
        setImportError(d.detail || "Failed to parse file.");
      }
    } catch { setImportError("Network error — could not reach server."); }
    finally { setImportLoading(false); }
  }

  async function handleImportApply() {
    setImportLoading(true);
    try {
      const r = await fetch(`${API}/portfolio/import/apply?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ positions: importPositions }),
      });
      if (r.ok) {
        setShowImportModal(false);
        setImportStep("upload");
        setImportPositions([]);
        fetchDigest(true);
        showToast(`${importPositions.length} position${importPositions.length !== 1 ? "s" : ""} imported to My Positions`);
      } else {
        setImportError("Failed to save positions.");
      }
    } catch { setImportError("Network error."); }
    finally { setImportLoading(false); }
  }

  const buyCount      = digest.filter(d => d.analysis?.verdict === "BUY").length;
  const watchCount    = digest.filter(d => d.analysis?.verdict === "WATCH" || d.analysis?.verdict === "HOLD").length;
  const sellCount     = digest.filter(d => d.analysis?.verdict === "SELL").length;
  const importantItems = digest.filter(d => d.analysis?.is_important_day);
  const unreadCount      = digest.filter(d => d.has_unread).length;
  const initials = userName.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div style={{ minHeight: "100vh", background: "var(--t-bg)" }}>

      {/* ── Header ── */}
      <header style={{ position: "sticky", top: 0, zIndex: 40, background: "var(--t-surface)", borderBottom: "1px solid var(--t-border)" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", height: 60, display: "flex", alignItems: "center", gap: isMobile ? 12 : 26, padding: isMobile ? "0 16px" : "0 32px" }}>

          {/* Logo */}
          <div onClick={() => setActiveTab("Dashboard")} style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer", flexShrink: 0 }}>
            <Logo size={22} />
            <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em", color: "var(--t-text)", fontFamily: SANS }}>Finance Companion</span>
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
                    {tab === "Stocks" && unreadCount > 0 && (
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
                  {isAdmin && (
                    <button
                      onClick={() => { setShowProfileMenu(false); router.push("/admin"); }}
                      style={{
                        width: "100%", textAlign: "left", padding: "11px 16px",
                        background: "none", border: "none", cursor: "pointer",
                        fontSize: 13, color: "var(--t-text)", fontFamily: SANS,
                        display: "flex", alignItems: "center", gap: 8,
                        borderBottom: "1px solid var(--t-border-light)",
                      }}
                    >
                      Admin
                    </button>
                  )}
                  <button
                    onClick={() => { setShowProfileMenu(false); router.push("/memory"); }}
                    style={{
                      width: "100%", textAlign: "left", padding: "11px 16px",
                      background: "none", border: "none", cursor: "pointer",
                      fontSize: 13, color: "var(--t-text)", fontFamily: SANS,
                      display: "flex", alignItems: "center", gap: 8,
                      borderBottom: "1px solid var(--t-border-light)",
                    }}
                  >
                    Memory
                  </button>
                  <button
                    onClick={() => { setShowProfileMenu(false); setShowFeedbackModal(true); }}
                    style={{
                      width: "100%", textAlign: "left", padding: "11px 16px",
                      background: "none", border: "none", cursor: "pointer",
                      fontSize: 13, color: "var(--t-text)", fontFamily: SANS,
                      display: "flex", alignItems: "center", gap: 8,
                    }}
                  >
                    Send Feedback
                  </button>
                  <button
                    onClick={() => signOut({ callbackUrl: "/signin" })}
                    style={{
                      width: "100%", textAlign: "left", padding: "11px 16px",
                      background: "none", border: "none", cursor: "pointer",
                      fontSize: 13, color: "var(--t-red)", fontFamily: SANS,
                      display: "flex", alignItems: "center", gap: 8,
                      borderTop: "1px solid var(--t-border-light)",
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

      <main style={{ maxWidth: 1180, margin: "0 auto", padding: isMobile ? "16px 16px 56px" : "30px 32px 56px" }}>

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
                    <button onClick={() => jumpToStock(spotlight.ticker)}
                      style={{ flex: 1, padding: "10px 0", background: "var(--t-accent)", color: "var(--t-surface)", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 14, fontFamily: SANS }}>
                      View Full Analysis →
                    </button>
                    <button onClick={() => { setActiveTab("Stocks"); }}
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
                      <div key={item.ticker} onClick={() => jumpToStock(item.ticker)}
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
              <button onClick={() => setActiveTab("Stocks")} style={{
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

        {/* ── Stocks tab: My Positions section (portfolio — items with shares set) ── */}
        {activeTab === "Stocks" && (() => {
          const allPortfolioItems = digest.filter(d => d.shares != null);
          const allWatchlistItems = digest.filter(d => d.shares == null);

          const filterQ = ticker ? ticker.toLowerCase() : query.trim().toLowerCase();
          const matchesQuery = (d: DigestItem) => !filterQ || (ticker ? d.ticker.toLowerCase() === filterQ : d.ticker.toLowerCase().includes(filterQ) || (d.company_name || "").toLowerCase().includes(filterQ));
          const portfolioItems = allPortfolioItems.filter(matchesQuery);
          const watchlistItems = allWatchlistItems.filter(matchesQuery);

          const totalPortfolioValue = allPortfolioItems
            .filter(d => d.shares != null && d.analysis?.current_price != null)
            .reduce((s, d) => s + d.shares! * d.analysis!.current_price!, 0);

          const VERDICT_ORDER = ["BUY", "HOLD", "WATCH", "SELL"];
          const VERDICT_META_GROUP: Record<string, { label: string; color: string; bg: string; bd: string }> = {
            BUY:   { label: "Buy",   color: "var(--t-green)",       bg: "var(--t-green-bg)",    bd: "var(--t-green-mid)"      },
            HOLD:  { label: "Hold",  color: "var(--t-yellow)",      bg: "var(--t-yellow-bg)",   bd: "var(--t-yellow-border)"  },
            WATCH: { label: "Watch", color: "var(--t-text-muted)",  bg: "var(--t-surface-warm)", bd: "var(--t-border)"        },
            SELL:  { label: "Sell",  color: "var(--t-red)",         bg: "var(--t-red-bg)",      bd: "var(--t-red-border)"     },
          };
          const COL_TIPS: Record<string, string> = { "RSI / Trend": "RSI 14-day momentum. Above 70 = overbought. Below 30 = oversold." };
          const colHeaders = !isMobile && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 110px 185px 80px 100px 130px 100px", padding: "0 1.25rem", marginBottom: "0.4rem", gap: "1rem" }}>
              {["Stock", "Verdict", "Price", "Conviction", "RSI / Trend", "Signals", ""].map(h => (
                <div key={h} title={COL_TIPS[h]} style={{ fontSize: "0.63rem", color: "var(--t-text-dim)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.09em", fontFamily: MONO, cursor: COL_TIPS[h] ? "help" : "default" }}>{h}</div>
              ))}
            </div>
          );
          const sectionHeader = (label: string, count: number, color: string, bg: string, bd: string) => (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "0.68rem", fontFamily: MONO, fontWeight: 700, padding: "2px 10px", borderRadius: 20, color, background: bg, border: `1px solid ${bd}`, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
              <span style={{ fontSize: "0.68rem", color: "var(--t-text-muted)", fontFamily: MONO }}>{count} stock{count > 1 ? "s" : ""}</span>
              <div style={{ flex: 1, height: 1, background: "var(--t-border)" }} />
            </div>
          );
          const sortFlat = (items: DigestItem[]) => {
            if (sortMode === "az") return [...items].sort((a, b) => a.ticker.localeCompare(b.ticker));
            if (sortMode === "movers") return [...items].sort((a, b) => Math.abs(b.analysis?.day_change_pct ?? 0) - Math.abs(a.analysis?.day_change_pct ?? 0));
            return [...items].sort((a, b) => ((b.analysis?.signal_convergence_score ?? -1) * 100 + (b.analysis?.conviction_score ?? 0)) - ((a.analysis?.signal_convergence_score ?? -1) * 100 + (a.analysis?.conviction_score ?? 0)));
          };
          // Renders a sorted/grouped list shared by both sections — same sort modes apply to positions and watchlist alike.
          const renderSortedList = (items: DigestItem[], renderRow: (item: DigestItem) => React.ReactNode) => {
            if (sortMode === "verdict") {
              const grouped = VERDICT_ORDER.map(v => ({ verdict: v, ...VERDICT_META_GROUP[v], items: items.filter(d => d.analysis?.verdict === v) })).filter(g => g.items.length > 0);
              const pending = items.filter(d => !d.analysis);
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  {grouped.map((g, gi) => <div key={g.verdict}>{sectionHeader(g.label, g.items.length, g.color, g.bg, g.bd)}{gi === 0 && colHeaders}<div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{g.items.map(renderRow)}</div></div>)}
                  {pending.length > 0 && <div>{sectionHeader("Pending", pending.length, "var(--t-text-muted)", "var(--t-surface-3)", "var(--t-border)")}<div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{pending.map(renderRow)}</div></div>}
                </div>
              );
            }
            const sorted = sortFlat(items);
            return <div>{colHeaders}<div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>{sorted.map(renderRow)}</div></div>;
          };

          const renderPortfolioRow = (item: DigestItem) => (
            <StockRow
              key={item.ticker} item={item} idToken={idToken} txCacheRef={txCacheRef}
              expanded={expanded === item.ticker}
              isPortfolio totalPortfolioValue={totalPortfolioValue}
              onToggle={() => {
                const isExpanding = expanded !== item.ticker;
                if (!isExpanding && item.change_summary) setDigest(prev => prev.map(d => d.ticker === item.ticker ? { ...d, change_summary: null } : d));
                setExpanded(isExpanding ? item.ticker : null);
                if (isExpanding && item.has_unread) handleMarkRead(item.ticker);
              }}
              onChat={handleChat} onRemove={handleRemove} isMobile={isMobile}
              onSold={() => handleSold(item.ticker)}
              onEdit={() => {
                setAddToPortfolioTicker(item.ticker);
                setPortfolioShares(item.shares?.toString() ?? "");
                setPortfolioAvgCost(item.avg_cost?.toString() ?? "");
              }}
            />
          );

          const renderWatchRow = (item: DigestItem) => (
            <StockRow
              key={item.ticker} item={item} idToken={idToken} txCacheRef={txCacheRef}
              expanded={expanded === item.ticker}
              isPortfolio={false}
              onToggle={() => {
                const isExpanding = expanded !== item.ticker;
                if (!isExpanding && item.change_summary) setDigest(prev => prev.map(d => d.ticker === item.ticker ? { ...d, change_summary: null } : d));
                setExpanded(isExpanding ? item.ticker : null);
                if (isExpanding && item.has_unread) handleMarkRead(item.ticker);
              }}
              onChat={handleChat} onRemove={handleRemove} isMobile={isMobile}
              onAddToPortfolio={() => { setAddToPortfolioTicker(item.ticker); setPortfolioShares(""); setPortfolioAvgCost(item.analysis?.current_price?.toFixed(2) ?? ""); }}
            />
          );

          return (
          <div>
          <h1 style={{ margin: "0 0 16px", fontFamily: SERIF, fontWeight: 600, fontSize: 25, color: "var(--t-text)" }}>Stocks</h1>

          {/* ── Unified search + sort toolbar — filters/sorts both sections below ── */}
          <div style={{ position: "sticky", top: 60, zIndex: 30, background: "var(--t-bg)", margin: isMobile ? "0 -16px" : "0 -32px", padding: isMobile ? "8px 16px 12px" : "8px 32px 12px" }}>
            <form onSubmit={handleAdd} style={{ display: "flex", gap: "0.5rem", padding: "0.75rem 1rem", background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 11, alignItems: "center", flexWrap: "wrap", boxShadow: "0 2px 8px rgba(32,33,28,0.07)" }}>
              <div ref={searchContainerRef} style={{ position: "relative", flex: "1 1 260px" }}>
                <input
                  ref={searchInputRef} value={query}
                  onChange={e => handleSearchInput(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  placeholder="Search your positions & watchlist, or add a new stock (e.g. NFLX)…"
                  autoComplete="off"
                  style={{ width: "100%", padding: "0.5rem 2rem 0.5rem 0.75rem", background: "var(--t-surface-2)", border: "1px solid var(--t-border)", borderRadius: 7, color: "var(--t-text)", fontSize: "0.88rem", fontFamily: SANS, outline: "none", boxSizing: "border-box" }}
                />
                {query && (
                  <button type="button" onClick={() => { setQuery(""); setTicker(""); setCompanyName(""); setSuggestions([]); setShowSuggestions(false); setError(""); }}
                    style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--t-text-muted)", fontSize: 16, padding: "0 2px", lineHeight: 1 }}>×</button>
                )}
                {showSuggestions && suggestions.length > 0 && (
                  <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 50, background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 9, overflow: "hidden", boxShadow: "0 8px 24px rgba(32,33,28,0.1)" }}>
                    {suggestions.map((s, idx) => (
                      <div key={s.ticker} onMouseDown={() => handleSelect(s)}
                        style={{ padding: "0.6rem 0.85rem", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", borderBottom: "1px solid var(--t-border-light)", background: idx === highlightedIdx ? "var(--t-surface-alt)" : "transparent" }}
                        onMouseEnter={() => setHighlightedIdx(idx)} onMouseLeave={() => setHighlightedIdx(-1)}>
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
              <button type="submit" disabled={!ticker && !query.trim()} style={{ padding: "0.5rem 1.1rem", background: (ticker || query.trim()) ? "var(--t-accent)" : "var(--t-border)", color: (ticker || query.trim()) ? "var(--t-surface)" : "var(--t-text-muted)", border: "none", borderRadius: 7, cursor: (ticker || query.trim()) ? "pointer" : "not-allowed", fontWeight: 600, fontSize: "0.88rem", fontFamily: SANS, transition: "background 0.15s", whiteSpace: "nowrap" }}>
                + Add
              </button>
              <div style={{ display: "flex", gap: 4, background: "var(--t-surface-3)", borderRadius: 9, padding: 3 }}>
                {([
                  { key: "relevance", label: "Relevance" },
                  { key: "verdict",   label: "Verdict"   },
                  { key: "az",        label: "A–Z"       },
                  { key: "movers",    label: "Movers"    },
                ] as const).map(opt => (
                  <button key={opt.key} type="button" onClick={() => setSortMode(opt.key)} style={{
                    padding: "4px 12px", borderRadius: 6, border: "none",
                    background: sortMode === opt.key ? "var(--t-surface)" : "transparent",
                    boxShadow: sortMode === opt.key ? "0 1px 3px rgba(32,33,28,0.1)" : "none",
                    color: sortMode === opt.key ? "var(--t-text)" : "var(--t-text-muted)",
                    fontWeight: sortMode === opt.key ? 600 : 400,
                    fontSize: "0.75rem", cursor: "pointer", fontFamily: MONO,
                    transition: "all 0.15s", whiteSpace: "nowrap",
                  }}>{opt.label}</button>
                ))}
              </div>
              {error && <span style={{ color: "var(--t-red)", fontSize: "0.8rem", width: "100%" }}>{error}</span>}
            </form>
          </div>

          {/* ── My Positions section ── */}
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: "0.75rem" }}>
              <div>
                <span style={{ fontSize: 11, fontFamily: MONO, fontWeight: 700, letterSpacing: "0.09em", color: "var(--t-text-muted)", textTransform: "uppercase" }}>My Positions</span>
                <div style={{ marginTop: 3, fontSize: 13, color: "var(--t-text-muted)" }}>
                  {filterQ ? `${portfolioItems.length} of ${allPortfolioItems.length}` : allPortfolioItems.length} position{allPortfolioItems.length !== 1 ? "s" : ""} · Real holdings with P&L tracking
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  onClick={() => { setShowImportModal(true); setImportStep("upload"); setImportError(""); }}
                  style={{ fontSize: "0.8rem", fontFamily: SANS, fontWeight: 600, padding: "7px 14px", borderRadius: 7, border: "1px solid var(--t-accent)", background: "var(--t-accent-bg)", color: "var(--t-accent)", cursor: "pointer" }}
                >↑ Import PDF / CSV</button>
                <button
                  onClick={() => watchlistSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  style={{ fontSize: "0.8rem", fontFamily: SANS, padding: "7px 14px", borderRadius: 7, border: "1px solid var(--t-border)", background: "transparent", color: "var(--t-text-muted)", cursor: "pointer" }}
                >+ Add from Watchlist</button>
              </div>
            </div>

            {loading ? (
              <div style={{ textAlign: "center", padding: "3rem", color: "var(--t-text-muted)" }}>Loading…</div>
            ) : allPortfolioItems.length === 0 ? (
              <div style={{ textAlign: "center", padding: "3rem", background: "var(--t-surface)", borderRadius: 11, border: "1px solid var(--t-border)", color: "var(--t-text-muted)" }}>
                <div style={{ fontSize: "1.8rem", marginBottom: "0.75rem" }}>📂</div>
                <div style={{ fontWeight: 600, marginBottom: "0.5rem", color: "var(--t-text)", fontSize: 16 }}>No positions yet</div>
                <div style={{ fontSize: "0.82rem", marginBottom: "1.25rem" }}>Import your Robinhood statement or add shares from your Watchlist</div>
                <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
                  <button onClick={() => { setShowImportModal(true); setImportStep("upload"); setImportError(""); }}
                    style={{ padding: "8px 18px", background: "var(--t-accent)", color: "var(--t-surface)", border: "none", borderRadius: 7, cursor: "pointer", fontWeight: 600, fontSize: 13, fontFamily: SANS }}>
                    ↑ Import PDF / CSV
                  </button>
                  <button onClick={() => watchlistSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                    style={{ padding: "8px 18px", background: "none", color: "var(--t-text-muted)", border: "1px solid var(--t-border)", borderRadius: 7, cursor: "pointer", fontSize: 13, fontFamily: SANS }}>
                    Go to Watchlist
                  </button>
                </div>
              </div>
            ) : portfolioItems.length === 0 ? (
              <div style={{ textAlign: "center", padding: "2.5rem", background: "var(--t-surface)", borderRadius: 11, border: "1px solid var(--t-border)", color: "var(--t-text-muted)" }}>
                <div style={{ fontWeight: 600, color: "var(--t-text)" }}>No positions match "{query.trim()}"</div>
              </div>
            ) : (
              <>
                <PortfolioSummary items={allPortfolioItems} />
                {renderSortedList(portfolioItems, renderPortfolioRow)}
              </>
            )}
          </div>

          <div style={{ height: 1, background: "var(--t-border)", margin: "2rem 0" }} />

          {/* ── Watchlist section (tracking only — items without shares) ── */}
          <div ref={watchlistSectionRef}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: "0.75rem" }}>
              <div>
                <span style={{ fontSize: 11, fontFamily: MONO, fontWeight: 700, letterSpacing: "0.09em", color: "var(--t-text-muted)", textTransform: "uppercase" }}>Watchlist</span>
                <div style={{ marginTop: 3, fontSize: 13, color: "var(--t-text-muted)" }}>
                  {filterQ ? `${watchlistItems.length} of ${allWatchlistItems.length}` : allWatchlistItems.length} stock{allWatchlistItems.length !== 1 ? "s" : ""} · Tracking only · Updated nightly after market close
                </div>
              </div>
            </div>

            {loading ? (
              <div style={{ textAlign: "center", padding: "3rem", color: "var(--t-text-muted)" }}>Loading…</div>
            ) : allWatchlistItems.length === 0 ? (
              <div style={{ textAlign: "center", padding: "3rem", background: "var(--t-surface)", borderRadius: 11, border: "1px solid var(--t-border)", color: "var(--t-text-muted)" }}>
                <div style={{ fontSize: "1.8rem", marginBottom: "0.5rem" }}>—</div>
                <div style={{ fontWeight: 600, marginBottom: "0.35rem", color: "var(--t-text)" }}>Add your first stock to get started</div>
                <div style={{ fontSize: "0.82rem" }}>Try: NFLX, MRVL, SOXQ, SOXL</div>
              </div>
            ) : watchlistItems.length === 0 ? (
              <div style={{ textAlign: "center", padding: "2.5rem", background: "var(--t-surface)", borderRadius: 11, border: "1px solid var(--t-border)", color: "var(--t-text-muted)" }}>
                <div style={{ fontWeight: 600, marginBottom: "0.35rem", color: "var(--t-text)" }}>No stocks match "{query.trim()}"</div>
                <div style={{ fontSize: "0.82rem" }}>Hit "+ Add" to add it to your watchlist</div>
              </div>
            ) : renderSortedList(watchlistItems, renderWatchRow)}
          </div>
          </div>
          );
        })()}

        {/* ── Discover placeholder ── */}
        {activeTab === "Discover" && (
          <div style={{ display: "flex", justifyContent: "center", paddingTop: 80 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 13, padding: "40px 64px" }}>
              <div style={{ width: 44, height: 44, borderRadius: 10, background: "var(--t-accent-light)", border: "1px solid var(--t-accent-border)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22 }}>🔍</div>
              <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 20, color: "var(--t-text)" }}>Discover — coming soon</div>
              <div style={{ fontSize: 13, color: "var(--t-text-muted)", maxWidth: "30ch", lineHeight: 1.6, textAlign: "center" }}>AI-ranked picks outside your watchlist, sorted by conviction.</div>
            </div>
          </div>
        )}

        {/* ── Feedback modal ── */}
        {showFeedbackModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.45)" }}
            onClick={e => { if (e.target === e.currentTarget) { setShowFeedbackModal(false); setFeedbackText(""); setFeedbackSent(false); } }}>
            <div style={{ background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 14, padding: "28px 28px 24px", width: "min(90vw, 440px)", boxShadow: "0 20px 60px rgba(0,0,0,0.25)" }}>
              {feedbackSent ? (
                <div style={{ textAlign: "center", padding: "1rem 0" }}>
                  <div style={{ fontSize: 28, marginBottom: 10 }}>✓</div>
                  <div style={{ fontFamily: SERIF, fontWeight: 600, fontSize: 16, color: "var(--t-text)" }}>Thanks for the feedback!</div>
                </div>
              ) : (
                <>
                  <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 18, color: "var(--t-text)", marginBottom: 6 }}>Send Feedback</div>
                  <div style={{ fontSize: 13, color: "var(--t-text-muted)", marginBottom: 16 }}>Bugs, ideas, anything — goes straight to the admin.</div>
                  <textarea
                    value={feedbackText}
                    onChange={e => setFeedbackText(e.target.value)}
                    placeholder="What's on your mind?"
                    rows={5}
                    autoFocus
                    style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", background: "var(--t-surface-2)", border: "1px solid var(--t-border)", borderRadius: 8, color: "var(--t-text)", fontSize: 14, fontFamily: SANS, resize: "none", outline: "none", marginBottom: 14 }}
                  />
                  <div style={{ display: "flex", gap: 10 }}>
                    <button
                      onClick={submitFeedback}
                      disabled={!feedbackText.trim()}
                      style={{ flex: 1, padding: "10px 0", background: feedbackText.trim() ? "var(--t-accent)" : "var(--t-border)", color: feedbackText.trim() ? "var(--t-surface)" : "var(--t-text-muted)", border: "none", borderRadius: 8, cursor: feedbackText.trim() ? "pointer" : "not-allowed", fontWeight: 600, fontSize: 14, fontFamily: SANS }}
                    >
                      Submit
                    </button>
                    <button
                      onClick={() => { setShowFeedbackModal(false); setFeedbackText(""); }}
                      style={{ padding: "10px 18px", background: "none", color: "var(--t-text-muted)", border: "1px solid var(--t-border)", borderRadius: 8, cursor: "pointer", fontSize: 14, fontFamily: SANS }}
                    >
                      Cancel
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ── Add Position modal (Watchlist → My Stocks) ── */}
        {addToPortfolioTicker && (
          <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.45)" }}
            onClick={e => { if (e.target === e.currentTarget) { setAddToPortfolioTicker(null); setError(""); } }}>
            <div style={{ background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 14, padding: "28px 28px 24px", width: "min(90vw, 400px)", boxShadow: "0 20px 60px rgba(0,0,0,0.25)" }}>
              {(() => {
                const isEditMode = digest.some(d => d.ticker === addToPortfolioTicker && d.shares != null);
                return (
                  <>
                    <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 18, color: "var(--t-text)", marginBottom: 6 }}>
                      {isEditMode ? "Edit Position" : "Add Position"} — {addToPortfolioTicker}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--t-text-muted)", marginBottom: 20 }}>
                      {isEditMode ? "Update your shares and average cost." : "This moves the stock into My Positions above."}
                    </div>
                  </>
                );
              })()}
              <form onSubmit={async e => { e.preventDefault(); await handleSetPortfolio(addToPortfolioTicker); setAddToPortfolioTicker(null); }} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.07em", display: "block", marginBottom: 5 }}>
                    Shares <span style={{ color: "var(--t-red)" }}>*</span>
                  </label>
                  <input
                    type="number" step="any" min="0.000001" required
                    value={portfolioShares} onChange={e => setPortfolioShares(e.target.value)}
                    placeholder="e.g. 13.291901"
                    style={{ width: "100%", padding: "9px 12px", background: "var(--t-surface-2)", border: "1px solid var(--t-border)", borderRadius: 8, color: "var(--t-text)", fontSize: 15, fontFamily: MONO, boxSizing: "border-box", outline: "none" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase", letterSpacing: "0.07em", display: "block", marginBottom: 5 }}>
                    Avg Cost per Share <span style={{ color: "var(--t-text-dim)", fontWeight: 400 }}>(optional)</span>
                  </label>
                  <input
                    type="number" step="any" min="0"
                    value={portfolioAvgCost} onChange={e => setPortfolioAvgCost(e.target.value)}
                    placeholder="e.g. 185.50"
                    style={{ width: "100%", padding: "9px 12px", background: "var(--t-surface-2)", border: "1px solid var(--t-border)", borderRadius: 8, color: "var(--t-text)", fontSize: 15, fontFamily: MONO, boxSizing: "border-box", outline: "none" }}
                  />
                </div>
                <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                  <button type="submit" disabled={!portfolioShares.trim()} style={{ flex: 1, padding: "10px 0", background: portfolioShares.trim() ? "var(--t-accent)" : "var(--t-border)", color: portfolioShares.trim() ? "var(--t-surface)" : "var(--t-text-muted)", border: "none", borderRadius: 8, fontWeight: 700, fontSize: 14, fontFamily: SANS, cursor: portfolioShares.trim() ? "pointer" : "not-allowed" }}>
                    {digest.some(d => d.ticker === addToPortfolioTicker && d.shares != null) ? "Update Position" : "Add to My Stocks"}
                  </button>
                  <button type="button" onClick={() => { setAddToPortfolioTicker(null); setError(""); }} style={{ padding: "10px 18px", background: "none", color: "var(--t-text-muted)", border: "1px solid var(--t-border)", borderRadius: 8, cursor: "pointer", fontSize: 14, fontFamily: SANS }}>
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── Import modal (PDF / CSV broker statement) ── */}
        {showImportModal && (
          <div style={{ position: "fixed", inset: 0, zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.45)" }}
            onClick={e => { if (e.target === e.currentTarget && !importLoading) setShowImportModal(false); }}>
            <div style={{ background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 14, padding: "28px 28px 24px", width: "min(95vw, 600px)", maxHeight: "85vh", overflowY: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.25)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
                <div>
                  <div style={{ fontFamily: SERIF, fontWeight: 700, fontSize: 18, color: "var(--t-text)" }}>
                    {importStep === "upload" ? "Import from Broker" : `Review ${importPositions.length} positions`}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--t-text-muted)", marginTop: 4 }}>
                    {importStep === "upload" ? "Upload a Robinhood PDF statement or CSV export from any broker." : "Enter avg cost where missing, then apply to My Stocks."}
                  </div>
                </div>
                {!importLoading && (
                  <button onClick={() => setShowImportModal(false)} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "var(--t-text-muted)", padding: "0 4px", lineHeight: 1, marginLeft: 12, flexShrink: 0 }}>×</button>
                )}
              </div>

              {importStep === "upload" && (
                <div>
                  <label style={{
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    gap: 12, padding: "36px 24px",
                    border: "2px dashed var(--t-border)", borderRadius: 10, cursor: "pointer",
                    background: "var(--t-surface-2)", transition: "border-color 0.15s",
                  }}
                    onDragOver={e => { e.preventDefault(); }}
                    onDrop={async e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) await handleImportFile(f); }}>
                    <input type="file" accept=".pdf,.csv" style={{ display: "none" }} onChange={async e => { const f = e.target.files?.[0]; if (f) await handleImportFile(f); }} />
                    <div style={{ fontSize: 32 }}>📄</div>
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontWeight: 600, fontSize: 14, color: "var(--t-text)", marginBottom: 4 }}>Drop PDF or CSV here</div>
                      <div style={{ fontSize: 12, color: "var(--t-text-muted)" }}>or click to browse — Robinhood, Fidelity, Schwab, and more</div>
                    </div>
                    {importLoading && <div style={{ fontSize: 13, color: "var(--t-accent)", fontWeight: 600 }}>Parsing file…</div>}
                  </label>
                  {importError && <div style={{ marginTop: 12, fontSize: 13, color: "var(--t-red)", padding: "10px 14px", background: "var(--t-red-bg)", borderRadius: 8 }}>{importError}</div>}
                </div>
              )}

              {importStep === "review" && (
                <div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
                    {/* Table header */}
                    <div style={{ display: "grid", gridTemplateColumns: "80px 1fr 1fr", gap: 8, padding: "6px 10px" }}>
                      {["Ticker", "Shares", "Avg Cost / Share"].map(h => (
                        <div key={h} style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--t-text-muted)", fontFamily: MONO }}>{h}</div>
                      ))}
                    </div>
                    {importPositions.map((pos, idx) => (
                      <div key={pos.ticker} style={{ display: "grid", gridTemplateColumns: "80px 1fr 1fr", gap: 8, alignItems: "center", padding: "8px 10px", background: "var(--t-surface-2)", borderRadius: 8, border: "1px solid var(--t-border)" }}>
                        <span style={{ fontFamily: MONO, fontWeight: 700, fontSize: 14, color: "var(--t-text)" }}>{pos.ticker}</span>
                        <span style={{ fontFamily: MONO, fontSize: 14, color: "var(--t-text-secondary)" }}>{pos.shares.toFixed(6).replace(/\.?0+$/, "")}</span>
                        <input
                          type="number" step="any" min="0"
                          value={pos.avg_cost ?? ""}
                          placeholder="Enter cost…"
                          onChange={e => {
                            const val: number | null = e.target.value.trim() ? parseFloat(e.target.value) : null;
                            setImportPositions(prev => prev.map((p, i) => i === idx ? { ...p, avg_cost: val } : p));
                          }}
                          style={{ padding: "5px 9px", background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 6, color: "var(--t-text)", fontSize: 14, fontFamily: MONO, width: "100%", boxSizing: "border-box", outline: "none" }}
                        />
                      </div>
                    ))}
                  </div>
                  {importError && <div style={{ marginBottom: 12, fontSize: 13, color: "var(--t-red)", padding: "10px 14px", background: "var(--t-red-bg)", borderRadius: 8 }}>{importError}</div>}
                  <div style={{ display: "flex", gap: 10 }}>
                    <button
                      onClick={async () => { await handleImportApply(); }}
                      disabled={importLoading}
                      style={{ flex: 1, padding: "11px 0", background: importLoading ? "var(--t-border)" : "var(--t-accent)", color: importLoading ? "var(--t-text-muted)" : "var(--t-surface)", border: "none", borderRadius: 8, fontWeight: 700, fontSize: 14, fontFamily: SANS, cursor: importLoading ? "not-allowed" : "pointer" }}>
                      {importLoading ? "Saving…" : `Apply ${importPositions.length} Positions`}
                    </button>
                    <button onClick={() => { setImportStep("upload"); setImportPositions([]); setImportError(""); }} disabled={importLoading}
                      style={{ padding: "11px 18px", background: "none", color: "var(--t-text-muted)", border: "1px solid var(--t-border)", borderRadius: 8, cursor: importLoading ? "not-allowed" : "pointer", fontSize: 14, fontFamily: SANS }}>
                      Back
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

      </main>

      {/* ── Footer / legal ── */}
      <footer style={{ borderTop: "1px solid var(--t-border)", padding: "20px 32px 28px" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", fontSize: 11.5, lineHeight: 1.6, color: "var(--t-text-muted)", fontFamily: SANS }}>
          <p style={{ margin: "0 0 8px" }}>
            Finance Companion provides AI-generated market commentary for informational and educational purposes only. Nothing on this site is financial, investment, tax, or legal advice, or a recommendation to buy, hold, or sell any security. Market data and AI-generated analysis may be delayed, incomplete, or inaccurate, and involve inherent uncertainty. Past performance does not guarantee future results. You are solely responsible for your own investment decisions — consult a licensed financial advisor before acting on anything shown here.{" "}
            <Link href="/terms" target="_blank" style={{ color: "var(--t-text-muted)", textDecoration: "underline" }}>
              Full Terms &amp; Disclaimer
            </Link>
          </p>
          <p style={{ margin: 0 }}>
            © {new Date().getFullYear()} Finance Companion. All rights reserved.
          </p>
        </div>
      </footer>

      {/* ── Toast notification ── */}
      {toast && (
        <div style={{
          position: "fixed", bottom: 28, left: "50%", transform: "translateX(-50%)",
          zIndex: 400, padding: "10px 22px", borderRadius: 10,
          background: "var(--t-surface)", border: "1px solid var(--t-green-mid)",
          boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
          fontSize: 13, fontWeight: 600, color: "var(--t-green)", fontFamily: SANS,
          display: "flex", alignItems: "center", gap: 8,
          opacity: toast.visible ? 1 : 0,
          transition: "opacity 0.35s ease",
          pointerEvents: "none", whiteSpace: "nowrap",
        }}>
          <span style={{ fontSize: 15 }}>✓</span> {toast.message}
        </div>
      )}
    </div>
  );
}
