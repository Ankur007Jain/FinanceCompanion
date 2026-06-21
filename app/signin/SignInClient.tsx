"use client";
import { signIn } from "next-auth/react";

export default function SignInClient() {
  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center",
      justifyContent: "center", background: "var(--t-bg)", padding: "1rem",
    }}>
      <div style={{
        background: "var(--t-surface)", border: "1px solid var(--t-border)",
        borderRadius: "1rem", padding: "2.5rem", maxWidth: "400px",
        width: "100%", textAlign: "center",
      }}>
        <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>📈</div>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.5rem", color: "var(--t-text)" }}>
          FinanceCompanion
        </h1>
        <p style={{ color: "var(--t-text-muted)", marginBottom: "2rem", fontSize: "0.95rem" }}>
          AI-powered stock advisor for busy professionals.
          <br />
          Your trusted finance friend, always on.
        </p>
        <button
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
          style={{
            width: "100%", padding: "0.875rem", background: "var(--t-primary)",
            color: "#fff", border: "none", borderRadius: "0.5rem",
            fontSize: "1rem", fontWeight: 600, cursor: "pointer",
          }}
          onMouseOver={(e) => ((e.target as HTMLElement).style.background = "var(--t-primary-hover)")}
          onMouseOut={(e) => ((e.target as HTMLElement).style.background = "var(--t-primary)")}
        >
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
