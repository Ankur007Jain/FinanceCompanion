"use client";
import { useEffect, useState } from "react";

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function BulbIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
      {/* bulb body */}
      <path d="M10 22h6M10.5 19.5h5M13 3a6 6 0 0 1 3.5 10.8V19h-7v-5.2A6 6 0 0 1 13 3z" />
      {/* dots around */}
      <circle cx="13" cy="0.8" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="21.5" cy="4.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="4.5" cy="4.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="24" cy="12" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="2" cy="12" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="21.5" cy="19.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="4.5" cy="19.5" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}

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
        padding: "6px 12px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: "0.4rem",
        flexShrink: 0,
        color: dark ? "var(--t-accent)" : "var(--t-text-secondary)",
        transition: "background 0.15s, border-color 0.15s, color 0.15s",
      }}
    >
      {dark ? <BulbIcon /> : <MoonIcon />}
    </button>
  );
}
