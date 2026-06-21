"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

interface Message {
  role: "user" | "assistant";
  content: string;
  searching?: string;
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const readerRef = useRef<ReadableStreamDefaultReader | null>(null);
  const throttleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef("");

  useEffect(() => { loadConversations(); }, []);
  useEffect(() => {
    if (activeConvId) loadMessages(activeConvId);
    else setMessages([]);
  }, [activeConvId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function loadConversations() {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`);
    if (r.ok) setConversations(await r.json());
  }

  async function loadMessages(convId: string) {
    setMessages([]);
    const r = await fetch(`${API}/conversations/${convId}/messages?id_token=${encodeURIComponent(idToken)}`);
    if (r.ok) {
      const msgs = await r.json();
      setMessages(msgs.map((m: { role: string; content: string }) => ({ role: m.role, content: m.content })));
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

  function flushChunk() {
    if (throttleRef.current) { clearTimeout(throttleRef.current); throttleRef.current = null; }
    applyChunk(pendingRef.current);
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

  async function send() {
    if (!input.trim() || streaming) return;
    let convId = activeConvId;
    if (!convId) convId = await newConversation();
    if (!convId) return;

    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);
    setSearchingLabel("");

    setMessages(prev => [...prev, { role: "assistant", content: "" }]);

    let fullText = "";
    pendingRef.current = "";

    try {
      const res = await fetch(`${API}/conversations/${convId}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: userMsg.content, user_email: userEmail, id_token: idToken }),
      });

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
            if (event.type === "chunk") {
              fullText += event.text;
              pendingRef.current = fullText;
              if (!throttleRef.current) {
                throttleRef.current = setTimeout(() => {
                  throttleRef.current = null;
                  applyChunk(pendingRef.current);
                }, 250);
              }
            } else if (event.type === "tool_start") {
              setSearchingLabel("Searching the web…");
            } else if (event.type === "tool_result") {
              setSearchingLabel(`Found results for: ${event.query}`);
              setTimeout(() => setSearchingLabel(""), 2000);
            } else if (event.type === "title") {
              loadConversations();
            } else if (event.type === "done") {
              flushChunk();
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
    } finally {
      setStreaming(false);
      setSearchingLabel("");
      readerRef.current = null;
    }
  }

  function stopStream() {
    readerRef.current?.cancel();
    setStreaming(false);
    setSearchingLabel("");
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--t-bg)" }}>
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
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button
            onClick={() => router.push("/dashboard")}
            style={{ background: "none", border: "none", color: "var(--t-text-muted)", cursor: "pointer", fontSize: "0.9rem" }}
          >
            ← Dashboard
          </button>
          <span style={{ fontWeight: 700 }}>💬 Finance Chat</span>
        </div>
        <button
          onClick={newConversation}
          style={{
            padding: "0.4rem 0.9rem",
            background: "var(--t-primary)",
            color: "#fff",
            border: "none",
            borderRadius: "0.4rem",
            cursor: "pointer",
            fontSize: "0.85rem",
          }}
        >
          + New Chat
        </button>
      </nav>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Sidebar — conversation list */}
        <aside style={{
          width: "220px",
          flexShrink: 0,
          borderRight: "1px solid var(--t-border)",
          overflowY: "auto",
          padding: "0.75rem 0",
          display: "flex",
          flexDirection: "column",
          gap: "0.25rem",
        }}>
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveConvId(c.id)}
              style={{
                textAlign: "left",
                padding: "0.6rem 1rem",
                background: c.id === activeConvId ? "var(--t-primary-light)" : "transparent",
                color: c.id === activeConvId ? "var(--t-primary)" : "var(--t-text-muted)",
                border: "none",
                cursor: "pointer",
                fontSize: "0.82rem",
                borderRadius: "0.25rem",
                margin: "0 0.5rem",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {c.ticker ? `[${c.ticker}] ` : ""}{c.title || "New chat"}
            </button>
          ))}
        </aside>

        {/* Chat area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ flex: 1, overflowY: "auto", padding: "1.5rem" }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", color: "var(--t-text-muted)", paddingTop: "4rem" }}>
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🤖</div>
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
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                    background: "var(--t-primary)", display: "flex", alignItems: "center",
                    justifyContent: "center", marginBottom: 2,
                  }}>
                    <span style={{ fontSize: "1rem" }}>📈</span>
                  </div>
                )}
                <div
                  style={{
                    maxWidth: "78%",
                    padding: "0.75rem 1rem",
                    borderRadius: msg.role === "user" ? "1.25rem 1.25rem 0.25rem 1.25rem" : "1.25rem 1.25rem 1.25rem 0.25rem",
                    background: msg.role === "user" ? "var(--t-primary)" : "var(--t-surface)",
                    border: msg.role === "assistant" ? "1px solid var(--t-border)" : "none",
                    color: msg.role === "user" ? "#fff" : "var(--t-text)",
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
                            <span style={{ width: 3, height: 20, borderRadius: 2, background: "var(--t-primary)", flexShrink: 0, display: "inline-block" }} />
                            {children}
                          </h1>
                        ),
                        h2: ({ children }) => (
                          <h2 style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.9rem", fontWeight: 700, margin: "0.85rem 0 0.4rem", color: "var(--t-text)" }}>
                            <span style={{ width: 3, height: 16, borderRadius: 2, background: "var(--t-primary)", opacity: 0.65, flexShrink: 0, display: "inline-block" }} />
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
                            <li style={{ lineHeight: 1.65, paddingLeft: "0.25rem", color: "var(--t-primary)", marginBottom: "0.3rem" }}>
                              <span style={{ color: "var(--t-text)" }}>{children}</span>
                            </li>
                          ) : (
                            <li style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem", lineHeight: 1.65, marginBottom: "0.3rem" }}>
                              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--t-primary)", flexShrink: 0, marginTop: "0.55em" }} />
                              <span style={{ flex: 1, color: "var(--t-text)" }}>{children}</span>
                            </li>
                          );
                        },
                        blockquote: ({ children }) => (
                          <blockquote style={{ margin: "0.6rem 0", padding: "0.6rem 0.9rem", borderLeft: "3px solid var(--t-primary)", background: "var(--t-primary-light)", borderRadius: "0 0.5rem 0.5rem 0", fontSize: "0.85rem", lineHeight: 1.6 }}>
                            {children}
                          </blockquote>
                        ),
                        table: ({ children }) => (
                          <div style={{ margin: "0.6rem 0", overflowX: "auto", borderRadius: "0.5rem", border: "1px solid var(--t-border)" }}>
                            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>{children}</table>
                          </div>
                        ),
                        thead: ({ children }) => <thead style={{ background: "var(--t-primary-light)" }}>{children}</thead>,
                        tr: ({ children }) => <tr style={{ borderBottom: "1px solid var(--t-border)" }}>{children}</tr>,
                        th: ({ children }) => (
                          <th style={{ padding: "0.45rem 0.75rem", textAlign: "left", fontWeight: 600, fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--t-primary)" }}>{children}</th>
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
                            <code style={{ padding: "0.15rem 0.4rem", borderRadius: "0.3rem", background: "var(--t-primary-light)", color: "var(--t-primary)", fontSize: "0.8rem", fontFamily: "monospace" }}>{children}</code>
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
                {msg.role === "user" && (
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                    background: "var(--t-primary)", display: "flex", alignItems: "center",
                    justifyContent: "center", color: "#fff", fontWeight: 700, fontSize: "0.8rem", marginBottom: 2,
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
            <div ref={bottomRef} />
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
              placeholder="Ask about your stocks… (Enter to send, Shift+Enter for newline)"
              disabled={streaming}
              rows={2}
              style={{
                flex: 1,
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
                  background: input.trim() ? "var(--t-primary)" : "var(--t-border)",
                  color: "#fff",
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
