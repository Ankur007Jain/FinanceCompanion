"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

interface Analysis {
  id: string;
  ticker: string;
  verdict: string;
  current_price: number;
  day_change_pct: number;
  week_52_high: number;
  week_52_low: number;
  range_position_pct: number;
  entry_target: number | null;
  exit_target: number | null;
  reasoning: string;
  analyst_consensus: string;
  analyst_count: number;
  events_json: string;
  is_important_day: boolean;
  importance_reason: string;
  rsi: number | null;
}

interface DigestItem {
  ticker: string;
  company_name: string | null;
  is_leveraged: boolean;
  analysis: Analysis | null;
}

interface WatchlistForm {
  ticker: string;
  company_name: string;
  is_leveraged: boolean;
}

const VERDICT_COLORS: Record<string, string> = {
  BUY: "var(--t-green)",
  HOLD: "var(--t-yellow)",
  SELL: "var(--t-red)",
  WATCH: "var(--t-text-muted)",
};

function VerdictBadge({ verdict }: { verdict: string }) {
  return (
    <span
      style={{
        background: VERDICT_COLORS[verdict] + "22",
        color: VERDICT_COLORS[verdict],
        border: `1px solid ${VERDICT_COLORS[verdict]}44`,
        padding: "0.2rem 0.6rem",
        borderRadius: "0.3rem",
        fontWeight: 700,
        fontSize: "0.8rem",
        letterSpacing: "0.05em",
      }}
    >
      {verdict}
    </span>
  );
}

function StockCard({ item, idToken, onChat }: { item: DigestItem; idToken: string; onChat: (ticker: string) => void }) {
  const a = item.analysis;
  const changeColor = a && a.day_change_pct >= 0 ? "var(--t-green)" : "var(--t-red)";
  const direction = a && a.day_change_pct >= 0 ? "▲" : "▼";

  let events: Array<{ date: string; description: string }> = [];
  if (a?.events_json) {
    try { events = JSON.parse(a.events_json).slice(0, 2); } catch {}
  }

  return (
    <div
      style={{
        background: "var(--t-surface)",
        border: a?.is_important_day ? "1px solid var(--t-yellow)" : "1px solid var(--t-border)",
        borderRadius: "0.75rem",
        padding: "1.25rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontWeight: 700, fontSize: "1.1rem" }}>{item.ticker}</span>
            {item.is_leveraged && (
              <span style={{ fontSize: "0.7rem", background: "#7c3aed22", color: "#a78bfa", padding: "0.1rem 0.4rem", borderRadius: "0.25rem" }}>
                LEVERAGED
              </span>
            )}
            {a?.is_important_day && <span title={a.importance_reason}>⭐</span>}
          </div>
          {item.company_name && (
            <div style={{ color: "var(--t-text-muted)", fontSize: "0.8rem" }}>{item.company_name}</div>
          )}
        </div>
        {a ? <VerdictBadge verdict={a.verdict} /> : (
          <span style={{ color: "var(--t-text-muted)", fontSize: "0.8rem" }}>No analysis yet</span>
        )}
      </div>

      {a && (
        <>
          {/* Price */}
          <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>${a.current_price?.toFixed(2)}</div>
              <div style={{ color: changeColor, fontSize: "0.85rem" }}>
                {direction} {Math.abs(a.day_change_pct || 0).toFixed(2)}%
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
              <div style={{ fontSize: "0.75rem", color: "var(--t-text-muted)" }}>52-Wk Range</div>
              <div style={{ fontSize: "0.85rem" }}>
                ${a.week_52_low?.toFixed(2)} – ${a.week_52_high?.toFixed(2)}
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--t-text-muted)" }}>
                {a.range_position_pct?.toFixed(0)}% of range
              </div>
            </div>
            {a.entry_target && (
              <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--t-text-muted)" }}>Entry / Exit</div>
                <div style={{ fontSize: "0.85rem" }}>
                  <span style={{ color: "var(--t-green)" }}>${a.entry_target?.toFixed(2)}</span>
                  {" / "}
                  <span style={{ color: "var(--t-red)" }}>${a.exit_target?.toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>

          {/* Reasoning */}
          <div style={{ fontSize: "0.85rem", color: "var(--t-text-muted)", lineHeight: 1.5 }}>
            {a.reasoning}
          </div>

          {/* Events */}
          {events.length > 0 && (
            <div style={{ fontSize: "0.8rem" }}>
              {events.map((e, i) => (
                <div key={i} style={{ color: "var(--t-yellow)", marginBottom: "0.2rem" }}>
                  ⚡ {e.date} — {e.description}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem" }}>
        <button
          onClick={() => onChat(item.ticker)}
          style={{
            flex: 1,
            padding: "0.5rem",
            background: "var(--t-primary-light)",
            color: "var(--t-primary)",
            border: "1px solid var(--t-primary)",
            borderRadius: "0.4rem",
            cursor: "pointer",
            fontSize: "0.8rem",
            fontWeight: 600,
          }}
        >
          Ask AI about {item.ticker}
        </button>
      </div>
    </div>
  );
}

export default function DashboardClient({
  userEmail, userName, idToken,
}: {
  userEmail: string; userName: string; idToken: string;
}) {
  const router = useRouter();
  const [digest, setDigest] = useState<DigestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [addForm, setAddForm] = useState<WatchlistForm>({ ticker: "", company_name: "", is_leveraged: false });
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchDigest();
  }, []);

  async function fetchDigest() {
    setLoading(true);
    try {
      const r = await fetch(`${API}/analysis/digest?id_token=${encodeURIComponent(idToken)}`);
      if (r.ok) setDigest(await r.json());
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!addForm.ticker.trim()) return;
    setAdding(true);
    setError("");
    try {
      const r = await fetch(`${API}/watchlist?id_token=${encodeURIComponent(idToken)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(addForm),
      });
      if (r.ok) {
        setAddForm({ ticker: "", company_name: "", is_leveraged: false });
        fetchDigest();
      } else {
        const data = await r.json();
        setError(data.detail || "Failed to add stock.");
      }
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(ticker: string) {
    await fetch(`${API}/watchlist/${ticker}?id_token=${encodeURIComponent(idToken)}`, { method: "DELETE" });
    fetchDigest();
  }

  async function handleChat(ticker: string) {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker }),
    });
    if (r.ok) {
      const conv = await r.json();
      router.push(`/chat?conv=${conv.id}`);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--t-bg)" }}>
      {/* Nav */}
      <nav style={{
        background: "var(--t-surface)",
        borderBottom: "1px solid var(--t-border)",
        padding: "0 1rem",
        height: "56px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}>
        <span style={{ fontWeight: 700, fontSize: "1.1rem" }}>📈 FinanceCompanion</span>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button
            onClick={() => router.push("/chat")}
            style={{
              padding: "0.4rem 0.9rem",
              background: "transparent",
              color: "var(--t-text-muted)",
              border: "1px solid var(--t-border)",
              borderRadius: "0.4rem",
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            💬 Chat
          </button>
          <span style={{ color: "var(--t-text-muted)", fontSize: "0.85rem" }}>{userName}</span>
        </div>
      </nav>

      <main style={{ maxWidth: "900px", margin: "0 auto", padding: "1.5rem 1rem" }}>
        {/* Add stock */}
        <form onSubmit={handleAdd} style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
          <input
            value={addForm.ticker}
            onChange={(e) => setAddForm({ ...addForm, ticker: e.target.value.toUpperCase() })}
            placeholder="Ticker (e.g. NFLX)"
            style={{
              flex: "1 1 120px",
              padding: "0.6rem 0.75rem",
              background: "var(--t-surface)",
              border: "1px solid var(--t-border)",
              borderRadius: "0.4rem",
              color: "var(--t-text)",
              fontSize: "0.9rem",
            }}
          />
          <input
            value={addForm.company_name}
            onChange={(e) => setAddForm({ ...addForm, company_name: e.target.value })}
            placeholder="Company name (optional)"
            style={{
              flex: "2 1 200px",
              padding: "0.6rem 0.75rem",
              background: "var(--t-surface)",
              border: "1px solid var(--t-border)",
              borderRadius: "0.4rem",
              color: "var(--t-text)",
              fontSize: "0.9rem",
            }}
          />
          <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "var(--t-text-muted)", fontSize: "0.85rem", whiteSpace: "nowrap" }}>
            <input
              type="checkbox"
              checked={addForm.is_leveraged}
              onChange={(e) => setAddForm({ ...addForm, is_leveraged: e.target.checked })}
            />
            Leveraged ETF
          </label>
          <button
            type="submit"
            disabled={adding}
            style={{
              padding: "0.6rem 1.2rem",
              background: "var(--t-primary)",
              color: "#fff",
              border: "none",
              borderRadius: "0.4rem",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "0.9rem",
            }}
          >
            {adding ? "Adding…" : "+ Add"}
          </button>
        </form>
        {error && <div style={{ color: "var(--t-red)", marginBottom: "1rem", fontSize: "0.85rem" }}>{error}</div>}

        {/* Digest */}
        {loading ? (
          <div style={{ color: "var(--t-text-muted)", textAlign: "center", padding: "3rem" }}>Loading your digest…</div>
        ) : digest.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "3rem",
            background: "var(--t-surface)", borderRadius: "0.75rem",
            border: "1px solid var(--t-border)", color: "var(--t-text-muted)",
          }}>
            <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>📋</div>
            <div>Add your first stock above to get started.</div>
            <div style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
              Try: NFLX, MRVL, SOXQ, SOXL, NVDA
            </div>
          </div>
        ) : (
          <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fill, minmax(400px, 1fr))" }}>
            {digest.map((item) => (
              <StockCard
                key={item.ticker}
                item={item}
                idToken={idToken}
                onChat={handleChat}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
