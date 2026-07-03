"use client";
import { signIn } from "next-auth/react";
import { useState } from "react";
import Link from "next/link";
import Logo from "../components/Logo";

const MONO = "'IBM Plex Mono', monospace";
const SANS = "'IBM Plex Sans', sans-serif";
const SERIF = "'IBM Plex Serif', serif";

export default function SignInClient({
  sessionExpired,
  testMode = false,
  testEmail = "",
}: {
  sessionExpired?: boolean;
  testMode?: boolean;
  testEmail?: string;
}) {
  const [testLoading, setTestLoading] = useState(false);
  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", background: "var(--t-bg)", padding: "1rem",
      fontFamily: SANS,
    }}>
      <div style={{
        background: "var(--t-surface)", border: "1px solid #E4E1D8",
        borderRadius: 13, padding: "2.5rem 2rem", maxWidth: 400,
        width: "100%", textAlign: "center",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 9, marginBottom: 28 }}>
          <Logo size={28} />
          <span style={{ fontWeight: 600, fontSize: 18, letterSpacing: "-0.01em", color: "var(--t-text)", fontFamily: SANS }}>Finance Companion</span>
        </div>

        <h1 style={{ margin: "0 0 0.5rem", fontFamily: SERIF, fontWeight: 600, fontSize: "1.3rem", color: "var(--t-text)" }}>
          {sessionExpired ? "Session expired" : "Welcome back"}
        </h1>
        {sessionExpired && (
          <div style={{ background: "var(--t-yellow-light-bg)", border: "1px solid #EDD9B8", borderRadius: 8, padding: "0.65rem 0.9rem", marginBottom: "1rem", fontSize: "0.82rem", color: "var(--t-yellow)" }}>
            Your session timed out. Sign in again to continue — it only takes a second.
          </div>
        )}
        <p style={{ color: "var(--t-text-muted)", marginBottom: "2rem", fontSize: "0.9rem", lineHeight: 1.6 }}>
          AI-powered stock advisor for busy professionals.
          <br />
          Your trusted finance friend, always on.
        </p>

        <button
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
          style={{
            width: "100%", padding: "0.875rem",
            background: "var(--t-accent)", color: "var(--t-surface)",
            border: "none", borderRadius: 8,
            fontSize: "0.95rem", fontWeight: 600,
            cursor: "pointer", fontFamily: SANS,
            transition: "background 0.15s",
          }}
          onMouseOver={e => ((e.target as HTMLElement).style.background = "var(--t-accent-hover)")}
          onMouseOut={e => ((e.target as HTMLElement).style.background = "var(--t-accent)")}
        >
          Sign in with Google
        </button>

        {testMode && (
          <button
            data-testid="test-signin-btn"
            onClick={async () => {
              setTestLoading(true);
              await signIn("test-credentials", { email: testEmail, callbackUrl: "/dashboard" });
            }}
            disabled={testLoading}
            style={{
              marginTop: "0.75rem", width: "100%", padding: "0.7rem",
              background: "transparent", color: "var(--t-text-muted)",
              border: "1px dashed #C8C6BE", borderRadius: 8,
              fontSize: "0.82rem", cursor: "pointer", fontFamily: MONO,
            }}
          >
            {testLoading ? "Signing in…" : `⚙ Test login (${testEmail})`}
          </button>
        )}
      </div>

      <p style={{ maxWidth: 400, marginTop: "1.25rem", fontSize: "0.72rem", lineHeight: 1.6, color: "var(--t-text-muted)", textAlign: "center" }}>
        For informational and educational purposes only — not financial, investment, tax, or legal advice.
        Consult a licensed financial advisor before making investment decisions.{" "}
        <Link href="/terms" style={{ color: "var(--t-text-muted)", textDecoration: "underline" }}>
          Terms &amp; Disclaimer
        </Link>
        <br />
        © {new Date().getFullYear()} Finance Companion. All rights reserved.
      </p>
    </div>
  );
}
