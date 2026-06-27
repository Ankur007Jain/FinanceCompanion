"use client";
import { useEffect, useState } from "react";

const MONO = "'IBM Plex Mono', monospace";

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") setDark(true);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    if (next) {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem("theme", "light");
    }
  }

  return (
    <button
      onClick={toggle}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        background: "var(--t-surface-3)",
        border: "1px solid var(--t-border)",
        borderRadius: 20,
        padding: "3px 10px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: "0.35rem",
        fontSize: "0.7rem",
        fontFamily: MONO,
        fontWeight: 600,
        color: "var(--t-text-secondary)",
        letterSpacing: "0.04em",
        flexShrink: 0,
        transition: "background 0.15s, border-color 0.15s",
      }}
    >
      <span style={{ fontSize: "0.85rem", lineHeight: 1 }}>{dark ? "☀" : "◑"}</span>
      {dark ? "LIGHT" : "DARK"}
    </button>
  );
}
