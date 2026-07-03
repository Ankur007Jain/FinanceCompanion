"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Logo from "../components/Logo";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

interface Message {
  role: "user" | "assistant";
  content: string;
  searching?: string;
  createdAt?: string;
}

function formatMessageTime(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  if (sameDay) return time;
  return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} · ${time}`;
}

interface Conversation {
  id: string;
  ticker: string | null;
  title: string | null;
}

export default function ChatClient({
  userEmail, userName, idToken,
}: {
  userEmail: string; userName: string; idToken: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(searchParams.get("conv"));
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [searchingLabel, setSearchingLabel] = useState("");
  const [isMobile, setIsMobile] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false);
  const [lastSystemPrompt, setLastSystemPrompt] = useState("");
  const [showSystemPrompt, setShowSystemPrompt] = useState(false);
  const canViewPrompt = userEmail === "ankur07jain@gmail.com";
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  // Auto-follow new content only while the user is already at (or near) the bottom —
  // if they've scrolled up to read something earlier, stop yanking them back down.
  // Reset to true whenever they send a message (they clearly want to see the reply).
  const stickToBottomRef = useRef(true);
  const readerRef = useRef<ReadableStreamDefaultReader | null>(null);
  // Watchdog — mobile browsers can silently drop or suspend a long-lived streaming
  // connection (backgrounding, screen lock, WiFi/cellular handoff) without the fetch
  // ever rejecting, leaving the UI stuck on "Analysing..." forever. Reset on every SSE
  // event received; if it fires, treat the stream as dead and surface an error.
  const watchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef("");
  // RAF throttle: accumulate chunks between frames, flush once per paint cycle instead of
  // once per network chunk — this is what actually eliminates jank, not a simulated typing
  // speed. Matches the pattern from TravelAI's useStreamingChat.
  const rafPendingRef = useRef(false);
  // Hold the first 2s of chunks before showing anything, so the response doesn't trickle in
  // one word at a time right at the start (when there's least text to make streaming feel
  // natural). If the whole reply finishes inside the buffer window, it just appears at once.
  const bufferReadyRef = useRef(false);
  const bufferTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Only scroll-to-bottom on explicit triggers (new message sent, conversation loaded,
  // response finished) — not on every streamed chunk, which would yank the view while
  // the user is reading.
  const scrollOnNextRenderRef = useRef(false);

  useEffect(() => { loadConversations(); }, []);
  useEffect(() => {
    if (activeConvId) loadMessages(activeConvId);
    else setMessages([]);
  }, [activeConvId]);
  useEffect(() => {
    const forced = scrollOnNextRenderRef.current;
    scrollOnNextRenderRef.current = false;
    if (!forced && !stickToBottomRef.current) return;
    const el = messagesContainerRef.current;
    if (!el) return;
    if (forced) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    else el.scrollTop = el.scrollHeight;
  }, [messages]);
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      stickToBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 640);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  async function loadConversations() {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`);
    if (r.ok) setConversations(await r.json());
  }

  async function loadMessages(convId: string) {
    setMessages([]);
    setLastSystemPrompt("");
    const r = await fetch(`${API}/conversations/${convId}/messages?id_token=${encodeURIComponent(idToken)}`);
    if (r.ok) {
      const msgs = await r.json();
      scrollOnNextRenderRef.current = true;
      stickToBottomRef.current = true;
      setMessages(msgs.map((m: { role: string; content: string; created_at?: string }) => ({ role: m.role, content: m.content, createdAt: m.created_at })));
    }
  }

  function applyChunk(text: string) {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant") {
        if (text.length <= last.content.length) return prev;
        const updated = [...prev];
        updated[updated.length - 1] = { ...last, content: text };
        return updated;
      }
      return [...prev, { role: "assistant" as const, content: text }];
    });
  }

  // Called on every incoming chunk. Buffers the first BUFFER_MS so the reply doesn't
  // trickle in one word at a time right when there's least text to make it feel smooth;
  // after that, applies the real accumulated text at most once per animation frame.
  const BUFFER_MS = 2000;
  function onChunkReceived() {
    if (!bufferTimerRef.current && !bufferReadyRef.current) {
      bufferTimerRef.current = setTimeout(() => {
        bufferTimerRef.current = null;
        bufferReadyRef.current = true;
        applyChunk(pendingRef.current);
      }, BUFFER_MS);
      return;
    }
    if (bufferReadyRef.current && !rafPendingRef.current) {
      rafPendingRef.current = true;
      requestAnimationFrame(() => {
        rafPendingRef.current = false;
        applyChunk(pendingRef.current);
      });
    }
  }

  function stopReveal() {
    if (bufferTimerRef.current) { clearTimeout(bufferTimerRef.current); bufferTimerRef.current = null; }
    rafPendingRef.current = false;
  }

  // Response finished (or errored) before the buffer window closed — show what we have now.
  function flushChunk() {
    if (bufferTimerRef.current) { clearTimeout(bufferTimerRef.current); bufferTimerRef.current = null; }
    bufferReadyRef.current = true;
    rafPendingRef.current = false;
    applyChunk(pendingRef.current);
  }

  function clearWatchdog() {
    if (watchdogRef.current) { clearTimeout(watchdogRef.current); watchdogRef.current = null; }
  }

  function armWatchdog() {
    clearWatchdog();
    watchdogRef.current = setTimeout(() => {
      watchdogRef.current = null;
      readerRef.current?.cancel().catch(() => {});
      flushChunk();
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant" && !last.content) {
          updated[updated.length - 1] = { ...last, content: "Error: No response — the connection may have dropped. Please try again." };
        }
        return updated;
      });
      setStreaming(false);
      setSearchingLabel("");
    }, 30000);
  }

  async function newConversation() {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (r.ok) {
      const conv = await r.json();
      setActiveConvId(conv.id);
      setMessages([]);
      loadConversations();
      return conv.id;
    }
    return null;
  }

  async function deleteConversation(convId: string) {
    const r = await fetch(`${API}/conversations/${convId}?id_token=${encodeURIComponent(idToken)}`, { method: "DELETE" });
    if (!r.ok) return;
    if (convId === activeConvId) {
      setActiveConvId(null);
      setMessages([]);
      router.replace("/chat");
    }
    setConversations(prev => prev.filter(c => c.id !== convId));
  }

  async function send() {
    if (!input.trim() || streaming) return;
    let convId = activeConvId;
    if (!convId) convId = await newConversation();
    if (!convId) return;

    const userMsg: Message = { role: "user", content: input, createdAt: new Date().toISOString() };
    scrollOnNextRenderRef.current = true;
    stickToBottomRef.current = true;
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);
    setSearchingLabel("");

    setMessages(prev => [...prev, { role: "assistant", content: "", createdAt: new Date().toISOString() }]);

    let fullText = "";
    pendingRef.current = "";
    bufferReadyRef.current = false;
    rafPendingRef.current = false;
    armWatchdog();

    try {
      const res = await fetch(`${API}/conversations/${convId}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: userMsg.content, user_email: userEmail, id_token: idToken }),
      });

      if (!res.ok) {
        // Non-2xx responses (e.g. 402 token limit reached, 401 expired session) are plain
        // JSON, not an SSE stream — reading them as one would silently discard every line
        // (nothing starts with "data: ") and leave the UI stuck on "Analysing..." forever
        // with no error ever shown.
        let detail = `Request failed (${res.status})`;
        try { detail = (await res.json())?.detail || detail; } catch {}
        throw new Error(detail);
      }
      if (!res.body) throw new Error("No stream body");
      const reader = res.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6).trim());
            armWatchdog();
            if (event.type === "chunk") {
              fullText += event.text;
              pendingRef.current = fullText;
              onChunkReceived();
            } else if (event.type === "system_prompt") {
              setLastSystemPrompt(event.text);
            } else if (event.type === "tool_start") {
              setSearchingLabel("Searching the web…");
            } else if (event.type === "tool_result") {
              setSearchingLabel(`Found results for: ${event.query}`);
              setTimeout(() => setSearchingLabel(""), 2000);
            } else if (event.type === "title") {
              loadConversations();
            } else if (event.type === "done") {
              flushChunk();
              scrollOnNextRenderRef.current = true;
              setSearchingLabel("");
            } else if (event.type === "error") {
              flushChunk();
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = { ...updated[updated.length - 1], content: `Error: ${event.message}` };
                return updated;
              });
            }
          } catch {}
        }
      }
    } catch (err) {
      stopReveal();
      const message = (err instanceof Error ? err.message : "Connection lost").replace(/\.+$/, "");
      setMessages(prev => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === "assistant") {
          updated[updated.length - 1] = { ...last, content: last.content || `Error: ${message}. Please try again.` };
        }
        return updated;
      });
    } finally {
      clearWatchdog();
      stopReveal();
      setStreaming(false);
      setSearchingLabel("");
      readerRef.current = null;
    }
  }

  function stopStream() {
    clearWatchdog();
    readerRef.current?.cancel();
    stopReveal();
    setStreaming(false);
    setSearchingLabel("");
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--t-bg)", overflow: "hidden" }}>
      {/* Nav */}
      <nav style={{
        background: "var(--t-surface)",
        borderBottom: "1px solid var(--t-border)",
        padding: "0 1rem",
        height: "56px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", minWidth: 0 }}>
          {isMobile && (
            <button
              onClick={() => setShowSidebar(true)}
              style={{ background: "none", border: "none", color: "var(--t-text-secondary)", cursor: "pointer", padding: "4px 2px", display: "flex", flexShrink: 0 }}
              aria-label="Conversations"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg>
            </button>
          )}
          <button
            onClick={() => router.push("/dashboard")}
            style={{ background: "none", border: "none", color: "var(--t-text-muted)", cursor: "pointer", fontSize: "0.9rem", flexShrink: 0 }}
          >
            ←{isMobile ? "" : " Dashboard"}
          </button>
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
            <Logo size={20} />
            {!isMobile && <span style={{ fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Finance Companion</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
          {canViewPrompt && (
            <button
              onClick={() => setShowSystemPrompt(true)}
              disabled={!lastSystemPrompt}
              title={lastSystemPrompt ? "View the system prompt sent to Claude" : "Send a message first"}
              style={{
                padding: isMobile ? "0.4rem 0.6rem" : "0.4rem 0.8rem",
                background: "none",
                color: lastSystemPrompt ? "var(--t-text-secondary)" : "var(--t-text-dim)",
                border: "1px solid var(--t-border)",
                borderRadius: "0.4rem",
                cursor: lastSystemPrompt ? "pointer" : "default",
                fontSize: "0.8rem",
              }}
            >
              🔍{isMobile ? "" : " Prompt"}
            </button>
          )}
          <button
            onClick={newConversation}
            style={{
              padding: isMobile ? "0.4rem 0.7rem" : "0.4rem 0.9rem",
              background: "var(--t-accent)",
              color: "var(--t-surface)",
              border: "none",
              borderRadius: "0.4rem",
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            + New{isMobile ? "" : " Chat"}
          </button>
        </div>
      </nav>

      {showSystemPrompt && (
        <div
          onClick={(e) => { if (e.target === e.currentTarget) setShowSystemPrompt(false); }}
          style={{ position: "fixed", inset: 0, zIndex: 200, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }}
        >
          <div style={{ background: "var(--t-surface)", border: "1px solid var(--t-border)", borderRadius: 12, width: "min(720px, 100%)", maxHeight: "85vh", display: "flex", flexDirection: "column", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
            <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--t-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontWeight: 700, fontSize: "0.95rem", color: "var(--t-text)" }}>System prompt sent to Claude</span>
              <button onClick={() => setShowSystemPrompt(false)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "var(--t-text-muted)", lineHeight: 1 }}>✕</button>
            </div>
            <pre style={{ margin: 0, padding: "1.25rem", overflow: "auto", fontSize: "0.78rem", lineHeight: 1.6, color: "var(--t-text)", whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
              {lastSystemPrompt}
            </pre>
          </div>
        </div>
      )}

      <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
        {/* Sidebar — conversation list. Fixed panel on desktop, slide-over drawer on mobile. */}
        {isMobile && showSidebar && (
          <div onClick={() => setShowSidebar(false)} style={{ position: "fixed", inset: 0, zIndex: 60, background: "rgba(32,33,28,0.35)" }} />
        )}
        <aside style={{
          width: "220px",
          flexShrink: 0,
          borderRight: "1px solid var(--t-border)",
          overflowY: "auto",
          padding: "0.75rem 0",
          display: "flex",
          flexDirection: "column",
          gap: "0.25rem",
          background: "var(--t-surface)",
          ...(isMobile ? {
            position: "fixed" as const, top: 0, bottom: 0, left: 0, zIndex: 61,
            transform: showSidebar ? "translateX(0)" : "translateX(-100%)",
            transition: "transform 0.2s ease", boxShadow: showSidebar ? "4px 0 24px rgba(32,33,28,0.14)" : "none",
            paddingTop: "0.75rem",
          } : {}),
        }}>
          {isMobile && (
            <div style={{ padding: "0 1rem 0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--t-border-light)", marginBottom: "0.5rem" }}>
              <span style={{ fontWeight: 600, fontSize: 13, color: "var(--t-text)" }}>Conversations</span>
              <button onClick={() => setShowSidebar(false)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, color: "var(--t-text-muted)", lineHeight: 1 }}>✕</button>
            </div>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              style={{
                display: "flex", alignItems: "center", gap: 2,
                margin: "0 0.5rem", borderRadius: "0.25rem",
                background: c.id === activeConvId ? "var(--t-accent-light)" : "transparent",
              }}
            >
              <button
                onClick={() => { setActiveConvId(c.id); setShowSidebar(false); }}
                style={{
                  flex: 1, minWidth: 0, textAlign: "left",
                  padding: "0.6rem 0 0.6rem 1rem",
                  background: "none",
                  color: c.id === activeConvId ? "var(--t-accent)" : "var(--t-text-muted)",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "0.82rem",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {c.ticker ? `[${c.ticker}] ` : ""}{c.title || "New chat"}
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); deleteConversation(c.id); }}
                title="Delete conversation"
                style={{
                  flexShrink: 0, background: "none", border: "none", cursor: "pointer",
                  color: "var(--t-text-muted)", fontSize: "0.9rem", lineHeight: 1,
                  padding: "0.4rem 0.7rem",
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </aside>

        {/* Chat area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
          <div ref={messagesContainerRef} style={{ flex: 1, overflowY: "auto", padding: isMobile ? "1rem" : "1.5rem" }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", color: "var(--t-text-muted)", paddingTop: "4rem" }}>
                <div style={{ display: "flex", justifyContent: "center", marginBottom: "0.75rem" }}><Logo size={40} /></div>
                <div style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Ask anything about your stocks</div>
                <div style={{ fontSize: "0.85rem" }}>
                  I already know tonight&apos;s analysis, your positions, and upcoming events.
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  marginBottom: "1.25rem",
                  display: "flex",
                  alignItems: "flex-end",
                  gap: "0.6rem",
                  justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                {msg.role === "assistant" && (
                  <div style={{ marginBottom: 2, flexShrink: 0 }}>
                    <Logo size={32} />
                  </div>
                )}
                <div style={{ display: "flex", flexDirection: "column", maxWidth: isMobile ? "88%" : "78%", alignItems: msg.role === "user" ? "flex-end" : "flex-start" }}>
                <div
                  style={{
                    padding: "0.75rem 1rem",
                    borderRadius: msg.role === "user" ? "1.25rem 1.25rem 0.25rem 1.25rem" : "1.25rem 1.25rem 1.25rem 0.25rem",
                    background: msg.role === "user" ? "var(--t-accent)" : "var(--t-surface)",
                    border: msg.role === "assistant" ? "1px solid var(--t-border)" : "none",
                    color: msg.role === "user" ? "var(--t-surface)" : "var(--t-text)",
                    fontSize: "0.875rem",
                    lineHeight: 1.65,
                    boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                  }}
                >
                  {msg.role === "user" ? (
                    <span style={{ whiteSpace: "pre-wrap" }}>{msg.content}</span>
                  ) : msg.content ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({ children }) => (
                          <h1 style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1rem", fontWeight: 700, margin: "1rem 0 0.5rem", color: "var(--t-text)" }}>
                            <span style={{ width: 3, height: 20, borderRadius: 2, background: "var(--t-accent)", flexShrink: 0, display: "inline-block" }} />
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.9rem", fontWeight: 700, margin: "0.85rem 0 0.4rem", color: "var(--t-text)" }}>
                            <span style={{ width: 3, height: 16, borderRadius: 2, background: "var(--t-accent)", opacity: 0.65, flexShrink: 0, display: "inline-block" }} />
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 style={{ fontSize: "0.875rem", fontWeight: 700, margin: "0.75rem 0 0.3rem", color: "var(--t-text)", letterSpacing: "0.02em" }}>{children}</h3>
                        ),
                        p: ({ children }) => (
                          <p style={{ margin: "0 0 0.6rem", lineHeight: 1.65, color: "var(--t-text)", opacity: 0.92 }}>{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul style={{ margin: "0 0 0.6rem", padding: 0, listStyle: "none" }}>{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol style={{ margin: "0 0 0.6rem", paddingLeft: "1.25rem" }}>{children}</ol>
                        ),
                        li: ({ children, ...props }) => {
                          const ordered = (props as { ordered?: boolean }).ordered;
                          return ordered ? (
                            <li style={{ lineHeight: 1.65, paddingLeft: "0.25rem", color: "var(--t-accent)", marginBottom: "0.3rem" }}>
                              <span style={{ color: "var(--t-text)" }}>{children}</span>
                            </li>
                          ) : (
                            <li style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", lineHeight: 1.65, marginBottom: "0.3rem" }}>
                              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--t-accent)", flexShrink: 0, marginTop: "0.55em" }} />
                              <span style={{ flex: 1, color: "var(--t-text)" }}>{children}</span>
                            </li>
                          );
                        },
                        blockquote: ({ children }) => (
                          <blockquote style={{ margin: "0.6rem 0", padding: "0.6rem 0.9rem", borderLeft: "3px solid var(--t-accent)", background: "var(--t-accent-light)", borderRadius: "0 0.5rem 0.5rem 0", fontSize: "0.85rem", lineHeight: 1.6 }}>
                            {children}
                          </blockquote>
                        ),
                        table: ({ children }) => (
                          <div style={{ margin: "0.6rem 0", overflowX: "auto", borderRadius: "0.5rem", border: "1px solid var(--t-border)" }}>
                            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>{children}</table>
                          </div>
                        ),
                        thead: ({ children }) => <thead style={{ background: "var(--t-accent-light)" }}>{children}</thead>,
                        tr: ({ children }) => <tr style={{ borderBottom: "1px solid var(--t-border)" }}>{children}</tr>,
                        th: ({ children }) => (
                          <th style={{ padding: "0.45rem 0.75rem", textAlign: "left", fontWeight: 600, fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--t-accent)" }}>{children}</th>
                        ),
                        td: ({ children }) => (
                          <td style={{ padding: "0.45rem 0.75rem", color: "var(--t-text)", opacity: 0.9 }}>{children}</td>
                        ),
                        strong: ({ children }) => (
                          <strong style={{ fontWeight: 600, color: "var(--t-text)" }}>{children}</strong>
                        ),
                        em: ({ children }) => <em style={{ fontStyle: "italic", opacity: 0.8 }}>{children}</em>,
                        hr: () => <div style={{ height: 1, background: "var(--t-border)", margin: "0.75rem 0" }} />,
                        code: ({ children, className }) => {
                          const isBlock = className?.includes("language-");
                          return isBlock ? (
                            <pre style={{ margin: "0.6rem 0", borderRadius: "0.5rem", background: "#1e293b", padding: "0.75rem 1rem", overflowX: "auto" }}>
                              <code style={{ fontSize: "0.78rem", fontFamily: "monospace", color: "#e2e8f0", lineHeight: 1.6 }}>{children}</code>
                            </pre>
                          ) : (
                            <code style={{ padding: "0.15rem 0.4rem", borderRadius: "0.3rem", background: "var(--t-accent-light)", color: "var(--t-accent)", fontSize: "0.8rem", fontFamily: "monospace" }}>{children}</code>
                          );
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--t-text-muted)", fontSize: "0.82rem" }}>
                      <span style={{ animation: "spin 1.2s linear infinite", display: "inline-block" }}>⟳</span>
                      Analysing your question…
                    </span>
                  )}
                </div>
                {msg.createdAt && (msg.content || msg.role === "user") && (
                  <span style={{ fontSize: "0.68rem", color: "var(--t-text-muted)", marginTop: 4, padding: "0 2px" }}>
                    {formatMessageTime(msg.createdAt)}
                  </span>
                )}
                </div>
                {msg.role === "user" && (
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                    background: "var(--t-accent)", display: "flex", alignItems: "center",
                    justifyContent: "center", color: "var(--t-surface)", fontWeight: 700, fontSize: "0.8rem", marginBottom: 2,
                  }}>
                    {userName?.[0]?.toUpperCase() ?? "U"}
                  </div>
                )}
              </div>
            ))}

            {searchingLabel && (
              <div style={{ color: "var(--t-text-muted)", fontSize: "0.82rem", padding: "0.5rem 0", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>🔍</span>
                {searchingLabel}
              </div>
            )}
          </div>

          {/* Input */}
          <div style={{
            borderTop: "1px solid var(--t-border)",
            padding: "1rem",
            display: "flex",
            gap: "0.5rem",
            background: "var(--t-surface)",
          }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder={isMobile ? "Ask about your stocks…" : "Ask about your stocks… (Enter to send, Shift+Enter for newline)"}
              disabled={streaming}
              rows={2}
              style={{
                flex: 1,
                minWidth: 0,
                boxSizing: "border-box",
                padding: "0.6rem 0.75rem",
                background: "var(--t-surface-2)",
                border: "1px solid var(--t-border)",
                borderRadius: "0.5rem",
                color: "var(--t-text)",
                fontSize: "0.9rem",
                resize: "none",
                outline: "none",
              }}
            />
            {streaming ? (
              <button
                onClick={stopStream}
                style={{
                  padding: "0 1.2rem",
                  background: "var(--t-red)",
                  color: "#fff",
                  border: "none",
                  borderRadius: "0.5rem",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Stop
              </button>
            ) : (
              <button
                onClick={send}
                disabled={!input.trim()}
                style={{
                  padding: "0 1.2rem",
                  background: input.trim() ? "var(--t-accent)" : "var(--t-border)",
                  color: input.trim() ? "var(--t-surface)" : "var(--t-text-muted)",
                  border: "none",
                  borderRadius: "0.5rem",
                  cursor: input.trim() ? "pointer" : "default",
                  fontWeight: 600,
                }}
              >
                Send
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
