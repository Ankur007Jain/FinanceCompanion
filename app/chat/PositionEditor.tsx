"use client";
import { useState } from "react";
import { MONO } from "@/app/components/StockDetail";

export interface Position {
  shares: number | null;
  avg_cost: number | null;
}

function fmtShares(n: number) {
  return n % 1 === 0 ? String(n) : n.toFixed(6).replace(/\.?0+$/, "");
}

// Inline position editor for the chat's stock panel — same PATCH /watchlist/{t}/portfolio the
// Stocks tab uses, so a position can be added/updated/cleared without leaving the conversation.
export default function PositionEditor({ ticker, position, onSave, onClear }: {
  ticker: string;
  position: Position | null;
  onSave: (shares: number, avgCost: number | null) => Promise<boolean>;
  onClear: () => Promise<boolean>;
}) {
  const held = position?.shares != null && position.shares > 0;
  const [editing, setEditing] = useState(false);
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  function open() {
    setShares(held ? fmtShares(position!.shares!) : "");
    setAvgCost(held && position!.avg_cost != null ? String(position!.avg_cost) : "");
    setError("");
    setEditing(true);
  }

  async function submit() {
    const s = parseFloat(shares);
    const c = avgCost.trim() ? parseFloat(avgCost) : null;
    if (!Number.isFinite(s) || s <= 0) { setError("Enter the number of shares (more than 0)."); return; }
    if (c !== null && (!Number.isFinite(c) || c < 0)) { setError("Average cost must be a positive number, or left blank."); return; }
    setEditing(false);
    const ok = await onSave(s, c);
    setStatus(ok ? "Saved ✓" : "Couldn't save — try again");
    setTimeout(() => setStatus(""), 2500);
  }

  async function clear() {
    setEditing(false);
    const ok = await onClear();
    setStatus(ok ? "Moved to watchlist ✓" : "Couldn't update — try again");
    setTimeout(() => setStatus(""), 2500);
  }

  const inputStyle = {
    width: "100%", boxSizing: "border-box" as const, padding: "0.4rem 0.55rem", fontSize: "0.85rem",
    fontFamily: MONO, borderRadius: "0.35rem", border: "1px solid var(--t-border)",
    background: "var(--t-bg)", color: "var(--t-text)", outline: "none",
  };
  const labelStyle = { fontSize: "0.58rem", color: "var(--t-text-muted)", fontFamily: MONO, textTransform: "uppercase" as const, letterSpacing: "0.08em", marginBottom: 3 };

  return (
    <div data-testid="position-editor" style={{ padding: "0.65rem 1rem", borderBottom: "1px solid var(--t-border)", background: "var(--t-surface)" }}>
      {!editing ? (
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          <div style={{ minWidth: 0 }}>
            <div style={labelStyle}>Your position</div>
            <div data-testid="position-summary" style={{ fontSize: "0.85rem", fontWeight: 600, fontFamily: MONO, color: "var(--t-text)" }}>
              {held ? (
                <>
                  {fmtShares(position!.shares!)} sh
                  {position!.avg_cost != null && <span style={{ fontWeight: 400, color: "var(--t-text-muted)" }}> @ ${position!.avg_cost.toFixed(2)}</span>}
                </>
              ) : (
                <span style={{ fontWeight: 400, color: "var(--t-text-muted)" }}>Not in your positions</span>
              )}
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: "0.5rem", alignItems: "center" }}>
            {status && <span data-testid="position-status" style={{ fontSize: "0.75rem", color: "var(--t-text-muted)" }}>{status}</span>}
            <button
              data-testid="position-edit"
              onClick={open}
              style={{ padding: "0.35rem 0.75rem", fontSize: "0.78rem", fontWeight: 600, borderRadius: "0.35rem", border: "1px solid var(--t-accent)", background: "transparent", color: "var(--t-accent)", cursor: "pointer" }}
            >
              {held ? "Edit position" : "Add position"}
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <div style={{ ...labelStyle, marginBottom: 6 }}>{held ? `Update ${ticker} position` : `Add ${ticker} position`}</div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <div style={{ flex: 1 }}>
              <div style={labelStyle}>Shares</div>
              <input data-testid="position-shares" autoFocus inputMode="decimal" value={shares} onChange={(e) => setShares(e.target.value)} placeholder="e.g. 10" style={inputStyle} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={labelStyle}>Avg cost ($, optional)</div>
              <input data-testid="position-cost" inputMode="decimal" value={avgCost} onChange={(e) => setAvgCost(e.target.value)} placeholder="e.g. 185.50" style={inputStyle} />
            </div>
          </div>
          {error && <div data-testid="position-error" style={{ marginTop: 6, fontSize: "0.75rem", color: "var(--t-red)" }}>{error}</div>}
          <div style={{ display: "flex", gap: "0.5rem", marginTop: 8, alignItems: "center" }}>
            <button type="submit" data-testid="position-save" style={{ padding: "0.4rem 0.9rem", fontSize: "0.8rem", fontWeight: 600, borderRadius: "0.35rem", border: "none", background: "var(--t-accent)", color: "var(--t-surface)", cursor: "pointer" }}>
              {held ? "Update" : "Save"}
            </button>
            <button type="button" onClick={() => setEditing(false)} style={{ padding: "0.4rem 0.7rem", fontSize: "0.8rem", borderRadius: "0.35rem", border: "1px solid var(--t-border)", background: "transparent", color: "var(--t-text-muted)", cursor: "pointer" }}>
              Cancel
            </button>
            {held && (
              <button type="button" data-testid="position-clear" onClick={clear} style={{ marginLeft: "auto", padding: "0.4rem 0.7rem", fontSize: "0.78rem", borderRadius: "0.35rem", border: "1px solid var(--t-red-border)", background: "transparent", color: "var(--t-red)", cursor: "pointer" }}>
                I sold it
              </button>
            )}
          </div>
        </form>
      )}
    </div>
  );
}
