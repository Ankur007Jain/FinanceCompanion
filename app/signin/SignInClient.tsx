"use client";
import { signIn } from "next-auth/react";

const MONO = "'IBM Plex Mono', monospace";
const SANS = "'IBM Plex Sans', sans-serif";
const SERIF = "'IBM Plex Serif', serif";

export default function SignInClient() {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", background: "#E8E6E0", padding: "1rem",
      fontFamily: SANS,
    }}>
      <div style={{
        background: "#FBFAF7", border: "1px solid #E4E1D8",
        borderRadius: 13, padding: "2.5rem 2rem", maxWidth: 400,
        width: "100%", textAlign: "center",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 9, marginBottom: 28 }}>
          <span style={{
            width: 28, height: 28, borderRadius: 6, background: "#3A5A6E",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "#FBFAF7", fontSize: 14, fontWeight: 600, fontFamily: MONO,
          }}>✦</span>
          <span style={{ fontWeight: 600, fontSize: 18, letterSpacing: "-0.01em", color: "#20211C", fontFamily: SANS }}>Stock Copilot</span>
        </div>

        <h1 style={{ margin: "0 0 0.5rem", fontFamily: SERIF, fontWeight: 600, fontSize: "1.3rem", color: "#20211C" }}>
          Welcome back
        </h1>
        <p style={{ color: "#9C998E", marginBottom: "2rem", fontSize: "0.9rem", lineHeight: 1.6 }}>
          AI-powered stock advisor for busy professionals.
          <br />
          Your trusted finance friend, always on.
        </p>

        <button
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
          style={{
            width: "100%", padding: "0.875rem",
            background: "#3A5A6E", color: "#FBFAF7",
            border: "none", borderRadius: 8,
            fontSize: "0.95rem", fontWeight: 600,
            cursor: "pointer", fontFamily: SANS,
            transition: "background 0.15s",
          }}
          onMouseOver={e => ((e.target as HTMLElement).style.background = "#2E4A5A")}
          onMouseOut={e => ((e.target as HTMLElement).style.background = "#3A5A6E")}
        >
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
