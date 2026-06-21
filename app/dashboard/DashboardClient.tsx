"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "next-auth/react";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

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

const VERDICT_META: Record<string, { color: string; bg: string; label: string }> = {
  BUY:   { color: "#22c55e", bg: "rgba(34,197,94,0.12)",  label: "BUY"   },
  HOLD:  { color: "#f59e0b", bg: "rgba(245,158,11,0.12)", label: "HOLD"  },
  SELL:  { color: "#ef4444", bg: "rgba(239,68,68,0.12)",  label: "SELL"  },
  WATCH: { color: "#94a3b8", bg: "rgba(148,163,184,0.1)", label: "WATCH" },
};

function RangeBar({ lo, hi, pct }: { lo: number; hi: number; pct: number }) {
  const clamp = Math.max(0, Math.min(100, pct));
  const dotColor = clamp < 33 ? "#22c55e" : clamp < 67 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", minWidth: 130 }}>
      <div style={{ position: "relative", height: 5, background: "var(--t-border)", borderRadius: 99 }}>
        <div style={{
          position: "absolute", left: 0, width: `${clamp}%`, height: "100%",
          background: dotColor, borderRadius: 99, opacity: 0.25,
        }} />
        <div style={{
          position: "absolute", left: `${clamp}%`, top: "50%",
          transform: "translate(-50%, -50%)",
          width: 11, height: 11, borderRadius: "50%",
          background: dotColor, border: "2px solid var(--t-bg)", zIndex: 1,
          boxShadow: `0 0 6px ${dotColor}88`,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "var(--t-text-muted)" }}>
        <span>${lo.toFixed(0)}</span>
        <span style={{ color: dotColor, fontWeight: 600 }}>{clamp.toFixed(0)}% of range</span>
        <span>${hi.toFixed(0)}</span>
      </div>
    </div>
  );
}

function RsiPill({ rsi }: { rsi: number }) {
  const color = rsi >= 70 ? "#ef4444" : rsi <= 30 ? "#22c55e" : "#94a3b8";
  const label = rsi >= 70 ? "Overbought" : rsi <= 30 ? "Oversold" : "Neutral";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
      <span style={{ fontWeight: 700, fontSize: "0.95rem", color }}>{rsi.toFixed(0)}</span>
      <span style={{ fontSize: "0.65rem", color, opacity: 0.8 }}>{label}</span>
    </div>
  );
}

function MaBadge({ price, ma50, ma200 }: { price: number; ma50: number | null; ma200: number | null }) {
  const above50  = ma50  ? price > ma50  : null;
  const above200 = ma200 ? price > ma200 : null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
      {ma50 != null && (
        <span style={{ fontSize: "0.68rem", color: above50 ? "#22c55e" : "#ef4444" }}>
          {above50 ? "▲" : "▼"} MA50 ${ma50.toFixed(0)}
        </span>
      )}
      {ma200 != null && (
        <span style={{ fontSize: "0.68rem", color: above200 ? "#22c55e" : "#ef4444" }}>
          {above200 ? "▲" : "▼"} MA200 ${ma200.toFixed(0)}
        </span>
      )}
    </div>
  );
}

function ExpandedDetail({ a, onChat }: { a: Analysis; onChat: () => void }) {
  let events: Array<{ date: string; description: string }> = [];
  try { if (a.events_json) events = JSON.parse(a.events_json).slice(0, 3); } catch {}

  return (
    <div style={{
      borderTop: "1px solid var(--t-border)",
      padding: "1.25rem 1.5rem",
      display: "grid",
      gridTemplateColumns: "1fr 1fr 1fr",
      gap: "1.5rem",
      background: "var(--t-bg)",
    }}>
      <div>
        <div style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "0.6rem" }}>
          Price Targets
        </div>
        {(a.entry_target || a.exit_target || a.stop_loss || a.hold_period) ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
            <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
              {a.entry_target && (
                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--t-text-muted)" }}>Entry</div>
                  <div style={{ fontWeight: 700, color: "#22c55e", fontSize: "1.05rem" }}>${a.entry_target.toFixed(2)}</div>
                </div>
              )}
              {a.exit_target && (
                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--t-text-muted)" }}>Take Profit</div>
                  <div style={{ fontWeight: 700, color: "#3b82f6", fontSize: "1.05rem" }}>${a.exit_target.toFixed(2)}</div>
                </div>
              )}
              {a.stop_loss && (
                <div>
                  <div style={{ fontSize: "0.7rem", color: "var(--t-text-muted)" }}>Stop Loss</div>
                  <div style={{ fontWeight: 700, color: "#ef4444", fontSize: "1.05rem" }}>${a.stop_loss.toFixed(2)}</div>
                </div>
              )}
            </div>
            {a.hold_period && (
              <div style={{
                display: "inline-flex", alignItems: "center", gap: "0.35rem",
                padding: "0.25rem 0.6rem", background: "rgba(148,163,184,0.1)",
                borderRadius: "0.35rem", width: "fit-content",
              }}>
                <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)" }}>Hold:</span>
                <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--t-text)" }}>{a.hold_period}</span>
              </div>
            )}
          </div>
        ) : (
          <div style={{ fontSize: "0.82rem", color: "var(--t-text-muted)" }}>No price targets set</div>
        )}
        {events.length > 0 && (
          <div style={{ marginTop: "1rem" }}>
            <div style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "0.4rem" }}>
              Upcoming Events
            </div>
            {events.map((e, i) => (
              <div key={i} style={{ fontSize: "0.78rem", color: "#f59e0b", marginBottom: "0.25rem", display: "flex", gap: "0.4rem" }}>
                <span>⚡</span><span>{e.date} — {e.description}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "0.6rem" }}>
          AI Reasoning
        </div>
        <div style={{ fontSize: "0.8rem", lineHeight: 1.6, color: "var(--t-text)", opacity: 0.85 }}>
          {a.reasoning ?? "—"}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {a.news_summary && (
          <div>
            <div style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "0.4rem" }}>
              News
            </div>
            <div style={{ fontSize: "0.78rem", lineHeight: 1.55, color: "var(--t-text)", opacity: 0.8 }}>{a.news_summary}</div>
          </div>
        )}
        {a.ripple_analysis && (
          <div>
            <div style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "0.4rem" }}>
              Ripple Effects
            </div>
            <div style={{ fontSize: "0.78rem", lineHeight: 1.55, color: "var(--t-text)", opacity: 0.8 }}>{a.ripple_analysis}</div>
          </div>
        )}
        <button
          onClick={onChat}
          style={{
            marginTop: "auto", padding: "0.5rem 1rem", background: "var(--t-primary)",
            color: "#fff", border: "none", borderRadius: "0.4rem",
            cursor: "pointer", fontWeight: 600, fontSize: "0.8rem",
            alignSelf: "flex-start",
          }}
        >
          💬 Ask AI about this
        </button>
      </div>

      {/* Fundamentals — full-width row spanning all 3 columns */}
      {(a.pe_trailing || a.revenue_growth || a.profit_margin || a.beta || a.market_cap || a.sector) && (
        <div style={{ gridColumn: "1 / -1", borderTop: "1px solid var(--t-border)", paddingTop: "1rem" }}>
          <div style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: "0.75rem" }}>
            Fundamentals
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "0.75rem 1.5rem" }}>
            {a.pe_trailing != null && (
              <FundStat label="P/E (TTM)" value={a.pe_trailing.toFixed(1) + "x"} />
            )}
            {a.pe_forward != null && (
              <FundStat label="P/E (Fwd)" value={a.pe_forward.toFixed(1) + "x"} />
            )}
            {a.revenue_growth != null && (
              <FundStat label="Revenue Growth" value={pct(a.revenue_growth)} color={a.revenue_growth >= 0 ? "#22c55e" : "#ef4444"} />
            )}
            {a.profit_margin != null && (
              <FundStat label="Net Margin" value={pct(a.profit_margin)} color={a.profit_margin >= 0 ? "#22c55e" : "#ef4444"} />
            )}
            {a.debt_to_equity != null && (
              <FundStat label="Debt / Equity" value={a.debt_to_equity.toFixed(1)} />
            )}
            {a.beta != null && (
              <FundStat label="Beta" value={a.beta.toFixed(2)} color={a.beta > 1.5 ? "#f59e0b" : undefined} />
            )}
            {a.short_float_pct != null && (
              <FundStat label="Short Interest" value={pct(a.short_float_pct)} color={a.short_float_pct > 0.2 ? "#ef4444" : undefined} />
            )}
            {a.inst_ownership_pct != null && (
              <FundStat label="Inst. Ownership" value={pct(a.inst_ownership_pct)} />
            )}
            {(a.stock_52w_change != null || a.sp500_52w_change != null) && (
              <div>
                <div style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", marginBottom: "0.2rem" }}>vs S&P 500 (52w)</div>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "baseline" }}>
                  {a.stock_52w_change != null && (
                    <span style={{ fontWeight: 700, fontSize: "0.88rem", color: a.stock_52w_change >= 0 ? "#22c55e" : "#ef4444" }}>
                      {pct(a.stock_52w_change)}
                    </span>
                  )}
                  {a.sp500_52w_change != null && (
                    <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)" }}>
                      / {pct(a.sp500_52w_change)} S&P
                    </span>
                  )}
                </div>
              </div>
            )}
            {a.market_cap != null && (
              <FundStat label="Market Cap" value={fmtCap(a.market_cap)} />
            )}
            {a.dividend_yield != null && a.dividend_yield > 0 && (
              <FundStat label="Dividend Yield" value={pct(a.dividend_yield)} color="#22c55e" />
            )}
          </div>
          {(a.sector || a.industry) && (
            <div style={{ marginTop: "0.6rem", fontSize: "0.72rem", color: "var(--t-text-muted)" }}>
              {[a.sector, a.industry].filter(Boolean).join(" · ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FundStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: "0.65rem", color: "var(--t-text-muted)", marginBottom: "0.2rem" }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: "0.88rem", color: color ?? "var(--t-text)" }}>{value}</div>
    </div>
  );
}

function pct(v: number) {
  return (v * 100).toFixed(1) + "%";
}

function fmtCap(v: number) {
  if (v >= 1e12) return "$" + (v / 1e12).toFixed(1) + "T";
  if (v >= 1e9)  return "$" + (v / 1e9).toFixed(1) + "B";
  if (v >= 1e6)  return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + v.toLocaleString();
}

function StockRow({
  item, expanded, onToggle, onChat,
}: {
  item: DigestItem;
  expanded: boolean;
  onToggle: () => void;
  onChat: (ticker: string) => void;
}) {
  const a = item.analysis;
  const vm = a?.verdict ? VERDICT_META[a.verdict] ?? VERDICT_META.WATCH : null;
  const chgColor = (a?.day_change_pct ?? 0) >= 0 ? "#22c55e" : "#ef4444";

  return (
    <div style={{
      background: "var(--t-surface)",
      border: expanded ? "1px solid var(--t-primary)" : "1px solid var(--t-border)",
      borderRadius: "0.75rem",
      overflow: "hidden",
      transition: "border-color 0.15s",
    }}>
      <div
        onClick={a ? onToggle : undefined}
        style={{
          display: "grid",
          gridTemplateColumns: "200px 100px 120px 180px 70px 100px 1fr 48px",
          alignItems: "center",
          padding: "0.9rem 1.25rem",
          cursor: a ? "pointer" : "default",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem" }}>{item.ticker}</span>
            {a?.is_important_day && <span title={a.importance_reason ?? ""} style={{ fontSize: "0.85rem" }}>⭐</span>}
            {item.is_leveraged && (
              <span style={{ fontSize: "0.6rem", padding: "0.1rem 0.35rem", background: "rgba(124,58,237,0.15)", color: "#a78bfa", borderRadius: "0.25rem", fontWeight: 700 }}>3X</span>
            )}
          </div>
          {item.company_name && (
            <div style={{ fontSize: "0.72rem", color: "var(--t-text-muted)", marginTop: "0.1rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {item.company_name}
            </div>
          )}
        </div>

        {vm ? (
          <div style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            padding: "0.35rem 0.75rem",
            background: vm.bg, color: vm.color,
            border: `1px solid ${vm.color}44`,
            borderRadius: "0.4rem", fontWeight: 800,
            fontSize: "0.85rem", letterSpacing: "0.05em",
            width: "fit-content",
          }}>
            {vm.label}
          </div>
        ) : (
          <span style={{ fontSize: "0.78rem", color: "var(--t-text-muted)" }}>Pending</span>
        )}

        <div>
          {a?.current_price != null ? (
            <>
              <div style={{ fontWeight: 700, fontSize: "1rem" }}>${a.current_price.toFixed(2)}</div>
              {a.day_change_pct != null && (
                <div style={{ fontSize: "0.75rem", color: chgColor, fontWeight: 600 }}>
                  {a.day_change_pct >= 0 ? "▲" : "▼"} {Math.abs(a.day_change_pct).toFixed(2)}%
                </div>
              )}
            </>
          ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.82rem" }}>—</span>}
        </div>

        {a?.week_52_low != null && a?.week_52_high != null && a?.range_position_pct != null ? (
          <RangeBar lo={a.week_52_low} hi={a.week_52_high} pct={a.range_position_pct} />
        ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.78rem" }}>—</span>}

        {a?.rsi != null ? (
          <RsiPill rsi={a.rsi} />
        ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.78rem" }}>—</span>}

        {a?.current_price != null ? (
          <MaBadge price={a.current_price} ma50={a.ma_50} ma200={a.ma_200} />
        ) : <span style={{ color: "var(--t-text-muted)", fontSize: "0.78rem" }}>—</span>}

        <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
          {a?.analyst_consensus && (
            <span style={{ fontSize: "0.72rem", color: "var(--t-text-muted)" }}>
              Analysts: <span style={{ color: "var(--t-text)", fontWeight: 600 }}>{a.analyst_consensus}</span>
            </span>
          )}
          {(() => {
            try {
              if (!a?.events_json) return null;
              const evts = JSON.parse(a.events_json);
              if (!evts?.length) return null;
              return <span style={{ fontSize: "0.7rem", color: "#f59e0b" }}>⚡ {evts[0].date}</span>;
            } catch { return null; }
          })()}
          {!a && <span style={{ fontSize: "0.75rem", color: "var(--t-text-muted)" }}>No analysis yet</span>}
        </div>

        {a ? (
          <div style={{
            color: "var(--t-text-muted)", fontSize: "0.8rem",
            transition: "transform 0.2s",
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            ▼
          </div>
        ) : <div />}
      </div>

      {expanded && a && (
        <ExpandedDetail a={a} onChat={() => onChat(item.ticker)} />
      )}
    </div>
  );
}

export default function DashboardClient({
  userName, idToken,
}: {
  userName: string; idToken: string;
}) {
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
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { fetchDigest(); }, []);

  async function fetchDigest() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/analysis/digest?id_token=${encodeURIComponent(idToken)}`);
      if (r.ok) setDigest(await r.json());
    } finally { setLoading(false); }
  }

  async function handleAdd(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!ticker.trim()) return;
    setAdding(true); setError("");
    try {
      const r = await fetch(`${API}/watchlist?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: ticker.trim().toUpperCase(), company_name: companyName || null }),
      });
      if (r.ok) { setTicker(""); setCompanyName(""); fetchDigest(); }
      else { const d = await r.json(); setError(d.detail || "Failed to add."); }
    } finally { setAdding(false); }
  }

  function handleSearchInput(val: string) {
    setQuery(val);
    setTicker("");
    setCompanyName("");
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
    setTicker(s.ticker);
    setCompanyName(s.name);
    setQuery(`${s.ticker} — ${s.name}`);
    setSuggestions([]);
    setShowSuggestions(false);
  }

  async function handleChat(t: string) {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: t }),
    });
    if (r.ok) { const conv = await r.json(); router.push(`/chat?conv=${conv.id}`); }
  }

  const buyCount   = digest.filter(d => d.analysis?.verdict === "BUY").length;
  const watchCount = digest.filter(d => d.analysis?.verdict === "WATCH" || d.analysis?.verdict === "HOLD").length;
  const sellCount  = digest.filter(d => d.analysis?.verdict === "SELL").length;

  return (
    <div style={{ minHeight: "100vh", background: "var(--t-bg)" }}>
      <nav style={{
        background: "var(--t-surface)", borderBottom: "1px solid var(--t-border)",
        padding: "0 1.5rem", height: 56, display: "flex", alignItems: "center",
        justifyContent: "space-between", position: "sticky", top: 0, zIndex: 10,
      }}>
        <span style={{ fontWeight: 700, fontSize: "1.05rem" }}>📈 FinanceCompanion</span>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button onClick={() => router.push("/chat")} style={{
            padding: "0.35rem 0.8rem", background: "transparent", color: "var(--t-text-muted)",
            border: "1px solid var(--t-border)", borderRadius: "0.4rem", cursor: "pointer", fontSize: "0.82rem",
          }}>
            💬 Chat
          </button>
          <span style={{ color: "var(--t-text-muted)", fontSize: "0.82rem" }}>{userName}</span>
          <button onClick={() => signOut({ callbackUrl: "/signin" })} style={{
            padding: "0.35rem 0.8rem", background: "transparent", color: "var(--t-text-muted)",
            border: "1px solid var(--t-border)", borderRadius: "0.4rem", cursor: "pointer", fontSize: "0.82rem",
          }}>
            Sign out
          </button>
        </div>
      </nav>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "1.5rem 1rem" }}>
        {digest.length > 0 && (
          <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
            {[
              { label: "Buy signals",  count: buyCount,   color: "#22c55e" },
              { label: "Watch/Hold",   count: watchCount, color: "#f59e0b" },
              { label: "Sell signals", count: sellCount,  color: "#ef4444" },
            ].map(s => (
              <div key={s.label} style={{
                padding: "0.5rem 1rem", background: "var(--t-surface)",
                border: `1px solid ${s.color}33`, borderRadius: "0.5rem",
                display: "flex", alignItems: "center", gap: "0.5rem",
              }}>
                <span style={{ fontWeight: 800, fontSize: "1.2rem", color: s.color }}>{s.count}</span>
                <span style={{ fontSize: "0.78rem", color: "var(--t-text-muted)" }}>{s.label}</span>
              </div>
            ))}
            <div style={{ marginLeft: "auto", fontSize: "0.75rem", color: "var(--t-text-muted)", alignSelf: "center" }}>
              Updated nightly after market close
            </div>
          </div>
        )}

        {digest.length > 0 && (
          <div style={{
            display: "grid",
            gridTemplateColumns: "200px 100px 120px 180px 70px 100px 1fr 48px",
            padding: "0 1.25rem", marginBottom: "0.5rem", gap: "1rem",
          }}>
            {["Stock", "Verdict", "Price", "52-Week Range", "RSI", "Trend", "Signal", ""].map(h => (
              <div key={h} style={{ fontSize: "0.68rem", color: "var(--t-text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                {h}
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {loading ? (
            <div style={{ textAlign: "center", padding: "3rem", color: "var(--t-text-muted)" }}>Loading your digest…</div>
          ) : digest.length === 0 ? (
            <div style={{
              textAlign: "center", padding: "3rem", background: "var(--t-surface)",
              borderRadius: "0.75rem", border: "1px solid var(--t-border)", color: "var(--t-text-muted)",
            }}>
              <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>📋</div>
              <div style={{ fontWeight: 600, marginBottom: "0.35rem" }}>Add your first stock to get started</div>
              <div style={{ fontSize: "0.82rem" }}>Try: NFLX, MRVL, SOXQ, SOXL</div>
            </div>
          ) : (
            digest.map(item => (
              <StockRow
                key={item.ticker}
                item={item}
                expanded={expanded === item.ticker}
                onToggle={() => setExpanded(expanded === item.ticker ? null : item.ticker)}
                onChat={handleChat}
              />
            ))
          )}
        </div>

        <form onSubmit={handleAdd} style={{
          display: "flex", gap: "0.5rem", marginTop: "1.5rem",
          padding: "1rem", background: "var(--t-surface)",
          border: "1px solid var(--t-border)", borderRadius: "0.75rem",
          alignItems: "center", flexWrap: "wrap",
        }}>
          <div style={{ position: "relative", flex: "1 1 260px" }}>
            <input
              value={query}
              onChange={e => handleSearchInput(e.target.value)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
              placeholder="Search ticker or company name…"
              autoComplete="off"
              style={{
                width: "100%", padding: "0.5rem 0.75rem", background: "var(--t-bg)",
                border: "1px solid var(--t-border)", borderRadius: "0.4rem",
                color: "var(--t-text)", fontSize: "0.88rem", boxSizing: "border-box",
              }}
            />
            {showSuggestions && suggestions.length > 0 && (
              <div style={{
                position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 50,
                background: "var(--t-surface)", border: "1px solid var(--t-border)",
                borderRadius: "0.5rem", overflow: "hidden", boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
              }}>
                {suggestions.map(s => (
                  <div
                    key={s.ticker}
                    onMouseDown={() => handleSelect(s)}
                    style={{
                      padding: "0.6rem 0.85rem", cursor: "pointer", display: "flex",
                      justifyContent: "space-between", alignItems: "center", gap: "0.5rem",
                      borderBottom: "1px solid var(--t-border)",
                    }}
                    onMouseOver={e => (e.currentTarget.style.background = "var(--t-bg)")}
                    onMouseOut={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <div>
                      <span style={{ fontWeight: 700, fontSize: "0.88rem", color: "var(--t-text)" }}>{s.ticker}</span>
                      <span style={{ marginLeft: "0.5rem", fontSize: "0.82rem", color: "var(--t-text-muted)" }}>{s.name}</span>
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--t-text-muted)", flexShrink: 0 }}>{s.exchange}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button type="submit" disabled={adding || !ticker} style={{
            padding: "0.5rem 1.1rem", background: "var(--t-primary)", color: "#fff",
            border: "none", borderRadius: "0.4rem", cursor: ticker ? "pointer" : "not-allowed",
            fontWeight: 600, fontSize: "0.88rem", opacity: ticker ? 1 : 0.5,
          }}>
            {adding ? "Adding…" : "+ Add"}
          </button>
          {error && <span style={{ color: "#ef4444", fontSize: "0.8rem", width: "100%" }}>{error}</span>}
        </form>
      </main>
    </div>
  );
}
