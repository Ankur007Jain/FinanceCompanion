"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import ThemeToggle from "@/app/components/ThemeToggle";
import Logo from "@/app/components/Logo";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";
const SANS = "'IBM Plex Sans', sans-serif";
const SERIF = "'IBM Plex Serif', serif";
const MONO = "'IBM Plex Mono', monospace";

interface Learning {
  id: string;
  learning: string;
  ticker: string | null;
  created_at: string;
}

export default function MemoryClient({ idToken }: { idToken: string }) {
  const router = useRouter();
  const [learnings, setLearnings] = useState<Learning[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const r = await fetch(`${API}/learnings?id_token=${encodeURIComponent(idToken)}`);
      // A non-JSON body (e.g. an HTML error page from a gateway timeout) makes
      // .json() throw too — caught below, not just the fetch() call itself.
      setLearnings(r.ok ? await r.json() : []);
      if (!r.ok) setLoadError(`Couldn't load your memory (${r.status}).`);
    } catch {
      // Without this catch, a thrown fetch (network error, CORS, DNS) or a
      // thrown .json() parse left setLoading(false) never called — the page
      // just sat on "Loading…" forever with no way to tell what went wrong.
      setLoadError("Couldn't reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const { global, byTicker } = useMemo(() => {
    const global: Learning[] = [];
    const byTicker = new Map<string, Learning[]>();
    for (const l of learnings) {
      if (!l.ticker) {
        global.push(l);
      } else {
        if (!byTicker.has(l.ticker)) byTicker.set(l.ticker, []);
        byTicker.get(l.ticker)!.push(l);
      }
    }
    return { global, byTicker: [...byTicker.entries()].sort((a, b) => a[0].localeCompare(b[0])) };
  }, [learnings]);

  async function deleteLearning(id: string) {
    // Optimistic — remove immediately, restore on failure, matching the app's
    // established UX rule: no waiting for a network round trip before feedback.
    const prev = learnings;
    setLearnings(learnings.filter(l => l.id !== id));
    try {
      const r = await fetch(`${API}/learnings/${id}?id_token=${encodeURIComponent(idToken)}`, { method: "DELETE" });
      if (!r.ok) setLearnings(prev);
    } catch {
      setLearnings(prev);
    }
  }

  function startEdit(l: Learning) {
    setEditingId(l.id);
    setEditText(l.learning);
  }

  async function saveEdit(id: string) {
    const text = editText.trim();
    if (!text) return;
    setSavingId(id);
    try {
      const r = await fetch(`${API}/learnings/${id}?id_token=${encodeURIComponent(idToken)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ learning: text }),
      });
      if (r.ok) {
        const updated = await r.json();
        setLearnings(learnings.map(l => l.id === id ? updated : l));
        setEditingId(null);
      }
    } catch {
      // Leave editingId set — the textarea stays open with the user's text intact,
      // rather than silently discarding an edit that never actually saved.
    } finally {
      setSavingId(null);
    }
  }

  const cardStyle: React.CSSProperties = {
    background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 11,
  };

  function renderRow(l: Learning) {
    const isEditing = editingId === l.id;
    return (
      <div key={l.id} style={{ padding: "12px 16px", borderTop: "1px solid var(--t-border-light)", display: "flex", gap: 10, alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          {isEditing ? (
            <textarea
              value={editText}
              onChange={e => setEditText(e.target.value)}
              autoFocus
              rows={2}
              style={{
                width: "100%", fontSize: 13, fontFamily: SANS, color: "var(--t-text)",
                background: "var(--t-surface-3)", border: "1px solid var(--t-accent-border)",
                borderRadius: 7, padding: "8px 10px", resize: "vertical",
              }}
            />
          ) : (
            <div style={{ fontSize: 13, color: "var(--t-text)", lineHeight: 1.5 }}>{l.learning}</div>
          )}
          <div style={{ fontSize: 11, fontFamily: MONO, color: "var(--t-text-muted)", marginTop: 4 }}>
            {new Date(l.created_at).toLocaleDateString()}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          {isEditing ? (
            <>
              <button
                onClick={() => saveEdit(l.id)}
                disabled={savingId === l.id}
                style={{
                  fontSize: 12, padding: "5px 11px", borderRadius: 7, cursor: "pointer",
                  background: "var(--t-accent)", color: "var(--t-surface)", border: "none",
                }}
              >
                {savingId === l.id ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => setEditingId(null)}
                style={{
                  fontSize: 12, padding: "5px 11px", borderRadius: 7, cursor: "pointer",
                  background: "none", border: "1px solid var(--t-border)", color: "var(--t-text-secondary)",
                }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => startEdit(l)}
                style={{
                  fontSize: 12, padding: "5px 11px", borderRadius: 7, cursor: "pointer",
                  background: "none", border: "1px solid var(--t-border)", color: "var(--t-text-secondary)",
                }}
              >
                Edit
              </button>
              <button
                onClick={() => deleteLearning(l.id)}
                style={{
                  fontSize: 12, padding: "5px 11px", borderRadius: 7, cursor: "pointer",
                  background: "var(--t-red-bg)", border: "1px solid var(--t-red-border)", color: "var(--t-red)",
                }}
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--t-bg)", fontFamily: SANS }}>
      <header style={{ background: "var(--t-surface)", borderBottom: "1px solid var(--t-border)" }}>
        <div style={{ maxWidth: 900, margin: "0 auto", height: 60, display: "flex", alignItems: "center", gap: 16, padding: "0 32px" }}>
          <div onClick={() => router.push("/dashboard")} style={{ display: "flex", alignItems: "center", gap: 9, cursor: "pointer" }}>
            <Logo size={22} />
            <span style={{ fontWeight: 600, fontSize: 15, color: "var(--t-text)" }}>Finance Companion</span>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
            <ThemeToggle />
            <button onClick={() => router.push("/dashboard")} style={{ fontSize: 13, background: "none", border: "1px solid var(--t-border)", borderRadius: 7, padding: "6px 13px", cursor: "pointer", color: "var(--t-text-secondary)" }}>
              ← Dashboard
            </button>
          </div>
        </div>
      </header>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px" }}>
        <h1 style={{ margin: "0 0 6px", fontFamily: SERIF, fontWeight: 600, fontSize: 25, color: "var(--t-text)" }}>Memory</h1>
        <p style={{ margin: "0 0 24px", fontSize: 13, color: "var(--t-text-muted)", lineHeight: 1.6 }}>
          Everything the AI has been explicitly asked to remember about you — global preferences that apply
          everywhere, and notes tied to a specific stock. Edit or remove anything that's wrong or no longer applies.
        </p>

        {loading ? (
          <div style={{ textAlign: "center", padding: "3rem", color: "var(--t-text-muted)" }}>Loading…</div>
        ) : loadError ? (
          <div style={{ ...cardStyle, padding: "2rem", textAlign: "center" }}>
            <div style={{ color: "var(--t-red)", fontSize: 13, marginBottom: 12 }}>{loadError}</div>
            <button
              onClick={load}
              style={{
                fontSize: 13, padding: "7px 16px", borderRadius: 7, cursor: "pointer",
                background: "var(--t-accent)", color: "var(--t-surface)", border: "none",
              }}
            >
              Retry
            </button>
          </div>
        ) : learnings.length === 0 ? (
          <div style={{ ...cardStyle, padding: "2rem", textAlign: "center", color: "var(--t-text-muted)" }}>
            Nothing saved yet — ask Ask AI to remember something, or correct it on a specific stock, and it'll show up here.
          </div>
        ) : (
          <>
            <div style={{ fontSize: 12, fontFamily: MONO, color: "var(--t-text-dim)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
              Global — applies in every conversation
            </div>
            {global.length === 0 ? (
              <div style={{ ...cardStyle, padding: "14px 16px", marginBottom: 24, color: "var(--t-text-muted)", fontSize: 13 }}>None saved.</div>
            ) : (
              <div style={{ ...cardStyle, marginBottom: 24, overflow: "hidden" }}>
                {global.map(renderRow)}
              </div>
            )}

            {byTicker.length > 0 && (
              <>
                <div style={{ fontSize: 12, fontFamily: MONO, color: "var(--t-text-dim)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                  Ticker-specific
                </div>
                {byTicker.map(([ticker, rows]) => (
                  <div key={ticker} style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 13, fontFamily: MONO, fontWeight: 600, color: "var(--t-accent)", marginBottom: 6 }}>{ticker}</div>
                    <div style={{ ...cardStyle, overflow: "hidden" }}>
                      {rows.map(renderRow)}
                    </div>
                  </div>
                ))}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
