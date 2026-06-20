"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

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

  useEffect(() => { loadConversations(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function loadConversations() {
    const r = await fetch(`${API}/conversations?id_token=${encodeURIComponent(idToken)}`);
    if (r.ok) setConversations(await r.json());
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
    }
  }

  async function send() {
    if (!input.trim() || streaming) return;
    if (!activeConvId) await newConversation();

    const convId = activeConvId;
    if (!convId) return;

    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);
    setSearchingLabel("");

    const assistantMsg: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMsg]);

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
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: updated[updated.length - 1].content + event.text,
                };
                return updated;
              });
            } else if (event.type === "tool_start") {
              setSearchingLabel("Searching the web…");
            } else if (event.type === "tool_result") {
              setSearchingLabel(`Found results for: ${event.query}`);
              setTimeout(() => setSearchingLabel(""), 2000);
            } else if (event.type === "title") {
              loadConversations();
            } else if (event.type === "done") {
              setSearchingLabel("");
            } else if (event.type === "error") {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  ...updated[updated.length - 1],
                  content: `Error: ${event.message}`,
                };
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
              onClick={() => { setActiveConvId(c.id); setMessages([]); }}
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
                  marginBottom: "1rem",
                  display: "flex",
                  justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "75%",
                    padding: "0.75rem 1rem",
                    borderRadius: msg.role === "user" ? "1rem 1rem 0.25rem 1rem" : "1rem 1rem 1rem 0.25rem",
                    background: msg.role === "user" ? "var(--t-primary)" : "var(--t-ai-bubble)",
                    border: msg.role === "assistant" ? "1px solid var(--t-border)" : "none",
                    color: "var(--t-text)",
                    fontSize: "0.9rem",
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {msg.content || (msg.role === "assistant" && streaming ? "▌" : "")}
                </div>
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
