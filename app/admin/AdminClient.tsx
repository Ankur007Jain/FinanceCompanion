"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ThemeToggle from "@/app/components/ThemeToggle";
import Logo from "@/app/components/Logo";
import pkg from "../../package.json";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";
const SANS = "'IBM Plex Sans', sans-serif";
const SERIF = "'IBM Plex Serif', serif";
const MONO = "'IBM Plex Mono', monospace";

interface AdminUser {
  email: string; name: string | null; tier: string; is_admin: boolean;
  tokens_used: number; created_at: string | null; tickers: string[];
}
interface TickerControl {
  ticker: string; analysis_enabled: boolean; disabled_by: string | null; disabled_at: string | null;
}
interface FeedbackItem { id: string; user_email: string; message: string; created_at: string; }
interface NightlyCost {
  ticker: string; analysis_date: string;
  gemini_tokens_input: number | null; gemini_tokens_output: number | null; gemini_cost_usd: number | null;
  simple_fields_tokens_input: number | null; simple_fields_tokens_output: number | null; simple_fields_cost_usd: number | null;
}

const TABS = ["Users", "Tickers", "Feedback", "Costs"] as const;
type Tab = typeof TABS[number];

export default function AdminClient({ idToken }: { idToken: string }) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("Users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [tickers, setTickers] = useState<TickerControl[]>([]);
  const [feedback, setFeedback] = useState<FeedbackItem[]>([]);
  const [costs, setCosts] = useState<NightlyCost[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendVersion, setBackendVersion] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    const q = `id_token=${encodeURIComponent(idToken)}`;
    const [u, t, f, c] = await Promise.all([
      fetch(`${API}/admin/users?${q}`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/admin/tickers?${q}`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/admin/feedback?${q}`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/admin/costs?${q}`).then(r => r.ok ? r.json() : []),
    ]);
    setUsers(u); setTickers(t); setFeedback(f); setCosts(c);
    setLoading(false);
    fetch(`${API}/health`).then(r => r.ok ? r.json() : null).then(h => setBackendVersion(h?.version ?? null)).catch(() => {});
  }

  useEffect(() => { loadAll(); }, []);

  async function toggleAdmin(email: string, is_admin: boolean) {
    await fetch(`${API}/admin/users/${encodeURIComponent(email)}?id_token=${encodeURIComponent(idToken)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_admin }),
    });
    setUsers(prev => prev.map(u => u.email === email ? { ...u, is_admin } : u));
  }

  async function toggleTicker(ticker: string, analysis_enabled: boolean) {
    const r = await fetch(`${API}/admin/tickers/${encodeURIComponent(ticker)}?id_token=${encodeURIComponent(idToken)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis_enabled }),
    });
    if (r.ok) setTickers(prev => prev.map(t => t.ticker === ticker ? { ...t, analysis_enabled, disabled_by: analysis_enabled ? null : t.disabled_by, disabled_at: analysis_enabled ? null : t.disabled_at } : t));
  }

  const cardStyle: React.CSSProperties = {
    background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 11,
  };
  const thStyle: React.CSSProperties = {
    fontSize: 11, fontFamily: MONO, color: "var(--t-text-dim)", fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.06em", textAlign: "left", padding: "8px 14px",
  };
  const tdStyle: React.CSSProperties = { padding: "10px 14px", fontSize: 13, color: "var(--t-text)", borderTop: "1px solid var(--t-border-light)" };

  const totalGeminiCost = costs.reduce((s, c) => s + (c.gemini_cost_usd || 0), 0);
  const totalHaikuCost = costs.reduce((s, c) => s + (c.simple_fields_cost_usd || 0), 0);

  return (
    <div style={{ minHeight: "100vh", background: "var(--t-bg)", fontFamily: SANS }}>
      <header style={{ background: "var(--t-surface)", borderBottom: "1px solid var(--t-border)" }}>
        <div style={{ maxWidth: 1180, margin: "0 auto", height: 60, display: "flex", alignItems: "center", gap: 16, padding: "0 32px" }}>
          <div onClick={() => router.push("/dashboard")} style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer" }}>
            <Logo size={22} />
            <span style={{ fontWeight: 600, fontSize: 15, color: "var(--t-text)" }}>Finance Companion</span>
          </div>
          <span style={{ fontSize: 12, fontFamily: MONO, padding: "3px 10px", borderRadius: 20, background: "var(--t-accent-bg)", color: "var(--t-accent)", border: "1px solid var(--t-accent-border)" }}>ADMIN</span>
          <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
            <ThemeToggle />
            <button onClick={() => router.push("/dashboard")} style={{ fontSize: 13, background: "none", border: "1px solid var(--t-border)", borderRadius: 7, padding: "6px 13px", cursor: "pointer", color: "var(--t-text-secondary)" }}>
              ← Dashboard
            </button>
          </div>
        </div>
      </header>

      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "32px" }}>
        <h1 style={{ margin: "0 0 20px", fontFamily: SERIF, fontWeight: 600, fontSize: 25, color: "var(--t-text)" }}>Admin</h1>

        <div style={{ display: "flex", gap: 4, background: "var(--t-surface-3)", borderRadius: 9, padding: 3, marginBottom: 20, width: "fit-content" }}>
          {TABS.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              padding: "6px 16px", borderRadius: 6, border: "none",
              background: activeTab === tab ? "var(--t-surface)" : "transparent",
              boxShadow: activeTab === tab ? "0 1px 3px rgba(32,33,28,0.1)" : "none",
              color: activeTab === tab ? "var(--t-text)" : "var(--t-text-muted)",
              fontWeight: activeTab === tab ? 600 : 400,
              fontSize: 13, cursor: "pointer", fontFamily: SANS,
            }}>
              {tab}
              {tab === "Feedback" && feedback.length > 0 && (
                <span style={{ marginLeft: 6, fontSize: 10, fontFamily: MONO, padding: "1px 6px", borderRadius: 9, background: "var(--t-accent)", color: "var(--t-surface)" }}>{feedback.length}</span>
              )}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "3rem", color: "var(--t-text-muted)" }}>Loading…</div>
        ) : (
          <>
            {activeTab === "Users" && (
              <div style={cardStyle}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>
                    <th style={thStyle}>Email</th><th style={thStyle}>Name</th><th style={thStyle}>Tier</th>
                    <th style={thStyle}>Admin</th><th style={thStyle}>Chat tokens used</th>
                    <th style={thStyle}>Tracked stocks</th><th style={thStyle}>Joined</th>
                  </tr></thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.email}>
                        <td style={{ ...tdStyle, fontFamily: MONO }}>{u.email}</td>
                        <td style={tdStyle}>{u.name || "—"}</td>
                        <td style={tdStyle}>{u.tier}</td>
                        <td style={tdStyle}>
                          <button onClick={() => toggleAdmin(u.email, !u.is_admin)} style={{
                            fontSize: 11, fontFamily: MONO, fontWeight: 600, padding: "3px 10px", borderRadius: 20, cursor: "pointer",
                            background: u.is_admin ? "var(--t-green-bg)" : "var(--t-surface-3)",
                            color: u.is_admin ? "var(--t-green)" : "var(--t-text-muted)",
                            border: `1px solid ${u.is_admin ? "var(--t-green-border)" : "var(--t-border)"}`,
                          }}>
                            {u.is_admin ? "✓ Admin" : "Make admin"}
                          </button>
                        </td>
                        <td style={{ ...tdStyle, fontFamily: MONO }}>{u.tokens_used.toLocaleString()}</td>
                        <td style={{ ...tdStyle, maxWidth: 260 }}>{u.tickers.join(", ") || "—"}</td>
                        <td style={tdStyle}>{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === "Tickers" && (
              <div style={cardStyle}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>
                    <th style={thStyle}>Ticker</th><th style={thStyle}>Nightly analysis</th>
                    <th style={thStyle}>Disabled by</th><th style={thStyle}>Disabled at</th><th style={thStyle}></th>
                  </tr></thead>
                  <tbody>
                    {tickers.map(t => (
                      <tr key={t.ticker}>
                        <td style={{ ...tdStyle, fontFamily: MONO, fontWeight: 600 }}>{t.ticker}</td>
                        <td style={tdStyle}>
                          <span style={{
                            fontSize: 11, fontFamily: MONO, fontWeight: 600, padding: "3px 10px", borderRadius: 20,
                            background: t.analysis_enabled ? "var(--t-green-bg)" : "var(--t-red-bg)",
                            color: t.analysis_enabled ? "var(--t-green)" : "var(--t-red)",
                            border: `1px solid ${t.analysis_enabled ? "var(--t-green-border)" : "var(--t-red-border)"}`,
                          }}>
                            {t.analysis_enabled ? "Enabled" : "Disabled"}
                          </span>
                        </td>
                        <td style={tdStyle}>{t.disabled_by || "—"}</td>
                        <td style={tdStyle}>{t.disabled_at ? new Date(t.disabled_at).toLocaleString() : "—"}</td>
                        <td style={tdStyle}>
                          <button onClick={() => toggleTicker(t.ticker, !t.analysis_enabled)} style={{
                            fontSize: 12, fontFamily: SANS, padding: "5px 12px", borderRadius: 7, cursor: "pointer",
                            background: "none", border: "1px solid var(--t-border)", color: "var(--t-text-secondary)",
                          }}>
                            {t.analysis_enabled ? "Disable" : "Enable"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === "Feedback" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {feedback.length === 0 ? (
                  <div style={{ ...cardStyle, padding: "2rem", textAlign: "center", color: "var(--t-text-muted)" }}>No feedback yet.</div>
                ) : feedback.map(f => (
                  <div key={f.id} style={{ ...cardStyle, padding: "14px 18px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontFamily: MONO, fontSize: 12, color: "var(--t-accent)", fontWeight: 600 }}>{f.user_email}</span>
                      <span style={{ fontSize: 11, color: "var(--t-text-muted)" }}>{new Date(f.created_at).toLocaleString()}</span>
                    </div>
                    <div style={{ fontSize: 14, color: "var(--t-text)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{f.message}</div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "Costs" && (
              <div>
                <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
                  <div style={{ ...cardStyle, padding: "14px 20px", flex: 1 }}>
                    <div style={{ fontSize: 11, fontFamily: MONO, color: "var(--t-text-muted)", textTransform: "uppercase" }}>Gemini (Verdict B) — recent</div>
                    <div style={{ fontSize: 22, fontFamily: MONO, fontWeight: 700, color: "var(--t-text)" }}>${totalGeminiCost.toFixed(4)}</div>
                  </div>
                  <div style={{ ...cardStyle, padding: "14px 20px", flex: 1 }}>
                    <div style={{ fontSize: 11, fontFamily: MONO, color: "var(--t-text-muted)", textTransform: "uppercase" }}>Haiku (simple language) — recent</div>
                    <div style={{ fontSize: 22, fontFamily: MONO, fontWeight: 700, color: "var(--t-text)" }}>${totalHaikuCost.toFixed(4)}</div>
                  </div>
                </div>
                <p style={{ fontSize: 12, color: "var(--t-text-muted)", marginBottom: 14, lineHeight: 1.6 }}>
                  Claude's Verdict A + judge steps run as the nightly GitHub Actions agent's own reasoning, not a scripted API call — there's no usage object to report, so that cost isn't tracked here (check Anthropic Console for that).
                </p>
                <div style={cardStyle}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead><tr>
                      <th style={thStyle}>Ticker</th><th style={thStyle}>Date</th>
                      <th style={thStyle}>Gemini tokens (in/out)</th><th style={thStyle}>Gemini cost</th>
                      <th style={thStyle}>Haiku tokens (in/out)</th><th style={thStyle}>Haiku cost</th>
                    </tr></thead>
                    <tbody>
                      {costs.map((c, i) => (
                        <tr key={`${c.ticker}-${c.analysis_date}-${i}`}>
                          <td style={{ ...tdStyle, fontFamily: MONO, fontWeight: 600 }}>{c.ticker}</td>
                          <td style={tdStyle}>{c.analysis_date}</td>
                          <td style={{ ...tdStyle, fontFamily: MONO }}>{c.gemini_tokens_input ?? "—"} / {c.gemini_tokens_output ?? "—"}</td>
                          <td style={{ ...tdStyle, fontFamily: MONO }}>{c.gemini_cost_usd != null ? `$${c.gemini_cost_usd.toFixed(4)}` : "—"}</td>
                          <td style={{ ...tdStyle, fontFamily: MONO }}>{c.simple_fields_tokens_input ?? "—"} / {c.simple_fields_tokens_output ?? "—"}</td>
                          <td style={{ ...tdStyle, fontFamily: MONO }}>{c.simple_fields_cost_usd != null ? `$${c.simple_fields_cost_usd.toFixed(4)}` : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {costs.length === 0 && <div style={{ padding: "2rem", textAlign: "center", color: "var(--t-text-muted)" }}>No cost data recorded yet.</div>}
                </div>
              </div>
            )}
          </>
        )}

        <div style={{ marginTop: 32, textAlign: "center", fontSize: 11, fontFamily: MONO, color: "var(--t-text-muted)" }}>
          Frontend v{pkg.version} · Backend v{backendVersion ?? "—"}
        </div>
      </div>
    </div>
  );
}
