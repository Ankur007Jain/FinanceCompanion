# Verdict Trust Strategy — Building Full Confidence for Busy Professionals

**Last updated:** 2026-06-22

---

## Who We Are Serving

Doctors, nurses, engineers, teachers — people who give their days and nights to serving others. They have savings but no time to research. They don't check their finances for months. They are not day traders. They need a system they can trust completely: get introduced at a low price, get out at a higher price, and not lose sleep in between.

**The product isn't stock analysis. It's permission to stop worrying about money.**

The experience we are building toward: open the app once a day, see exactly what needs attention (usually nothing), take action if warranted, close the app, go be with your family. Real convictions based on real data — not hunches.

---

## The Problem With the Current System

The current nightly analysis outputs a verdict (BUY/SELL/WATCH/HOLD) with conviction score, bull/bear cases, and price targets. That's a Bloomberg terminal output — useful for traders, overwhelming for the target user.

**Deeper problem: we show everything equally.** A trusted advisor doesn't show you everything — they filter for you. When 12 stocks all get a row with equal visual weight, the user still has to do all the work of deciding which ones matter today. That's not advice. That's data.

When a nurse opens this app after a long shift and sees 12 verdicts, her actual questions are:

- Which one of these actually needs my attention today?
- Is now a good time to enter, or did I miss the move?
- If I buy tomorrow and don't look for 3 months, will I be okay?
- How much of my savings should I put in?
- What's the realistic worst case?
- When do I know it's time to get out?

**None of these are answered today in a way that removes the cognitive work from the user.**

---

## What Successful Systems Do

| System | Key Trust Mechanism |
|--------|---------------------|
| **IBD (Investor's Business Daily)** | Single composite score 1–99. Busy people act on the number, not the data behind it. |
| **Motley Fool Stock Advisor** | 3–5 year horizon picks. Monthly cadence. "Best Buys Now" tells you which picks are still at a good entry today. |
| **Goldman / Morgan Stanley** | 12-month price target with Bull / Base / Bear scenarios and probabilities attached. |
| **Warren Buffett** | Doesn't say BUY — says "at what price I'd buy." Margin of safety answers "is now a good time?" |
| **Betterment / Wealthfront** | Whole product is "trust us, don't look, we'll handle it." High-signal, infrequent communication. |

**Common thread:** All reduce cognitive load. They answer "so what do I actually do?" explicitly. They are opinionated and selective — they don't show you everything, they show you what matters.

---

## Phase 1 — Already Built (PR #17)

| Feature | What It Does |
|---------|-------------|
| **Entry Quality** | GREAT / FAIR / WAIT — is now a good time to enter? |
| **Hold-and-Forget Rating** | HOLD_AND_FORGET / CHECK_MONTHLY / WATCH_CLOSELY |
| **Position Size** | Suggested % of portfolio (e.g. "5–8%") |
| **90-Day Scenarios** | Bull / Base / Bear with % return and probability |
| **Don't Panic Note** | Triggered when price drops >15% since last BUY |
| **Signal Checklist** | Visual strip showing what the AI analyzed (6 data sources) |

These answered the "what and how much" questions. What remains is the "why now" and "what needs my attention today" questions.

---

## Phase 2 — Next Sprint

### 1. Signal Convergence Score — "Not a Hunch, Real Data"

The most important missing piece. Right now the Verdict Agent can issue BUY when only 2 signals weakly agree. That's a hunch dressed up in data. We need a score that counts how many independent signals are simultaneously pointing to a genuine setup.

**The 7 convergence signals:**

| # | Signal | What It Checks | Low-Hanging-Fruit Threshold |
|---|--------|---------------|--------------------------|
| 1 | **Oversold** | RSI | < 42 |
| 2 | **Near the floor** | 52-week range position | < 35% (near lows, not highs) |
| 3 | **Analyst upside** | Current price vs mean target | > 15% upside to analyst target |
| 4 | **No binary risk** | Days to next earnings | > 21 days away |
| 5 | **Fundamentally healthy** | Free cash flow | Positive |
| 6 | **Smart money agrees** | Institutional ownership | > 40% |
| 7 | **Stabilizing** | Price vs 200-day MA | Within 10% below (oversold but not collapsing) |

**Score → Action:**
- 6–7 signals: **Strong Setup** → BUY eligible, high conviction
- 4–5 signals: **Moderate Setup** → WATCH, explain what's missing
- 0–3 signals: **Weak Setup** → WATCH only, no BUY

**Conviction floor rule:** If `signal_convergence_score < 5`, verdict must be WATCH regardless of other analysis. No weak BUYs. Fewer but stronger calls.

New DB field: `signal_convergence_score` (Integer 0–7), `convergence_details` (JSON — which signals fired)

---

### 2. The "All Clear" Message — Silence Is Not an Answer

When nothing needs action today, the app currently shows 12 rows of data and expects the user to conclude "okay, nothing today." That's still cognitive work.

A trusted advisor explicitly says: **"Your positions are fine. No action needed today."**

This single message — shown prominently when nothing is actionable — builds as much trust as a good BUY call. It tells the user the system is watching and everything is fine. They can close the app and go live their life.

**Logic:**
- No BUY or SELL verdict in the user's watchlist today → show "All Clear" card
- All-clear card includes: last checked timestamp, count of positions on track, next check time

---

### 3. Daily Spotlight — One Thing, Not Twelve

Of 12 watchlist stocks, surface the single most actionable one today at the top. Not a ranked list — a spotlight card. Ranked by: `signal_convergence_score DESC`, then `conviction_score DESC`.

**If something actionable exists:**
```
⚡ 1 Opportunity Today

NFLX — BUY  ·  Conviction 84/100  ·  Entry: GREAT
Signal convergence: 6 of 7

Why this, why now:
• Oversold (RSI 38) after 22% pullback — fundamentals unchanged
• Trading 18% below analyst mean target ($820 vs $680 now)
• Institutional ownership up 4% last quarter
• No earnings for 47 days — no binary risk
• Free cash flow: $6.2B — company is financially healthy

Action: Buy up to $680 · Stop $590 · Target $800 · Hold 60-90 days
Suggested: 6% of portfolio (~$1,200 on $20k)

[ Take Action → ]     [ Skip ]
```

**If nothing is actionable:**
```
✓ All Clear

Nothing needs your attention today.
Your 4 active positions are on track.
Analyzed at 2:14 AM · Next run tonight

Come back tomorrow.
```

---

### 4. Action Clarity — "Buy X Shares" Not "Entry Target $680"

The entry target is still cognitive work. The user has to decide how many shares. A trusted advisor removes that step.

**Requires:** user's approximate portfolio size (ask once on onboarding, store on `users` table as `portfolio_size`).

**Output:** "At your suggested 6% allocation on a $20k portfolio, that's $1,200 — roughly 1 share at $680. Buy at market open."

New `users` field: `portfolio_size` (Float, nullable — user provides voluntarily).

---

### 5. Conviction Floor Enforcement

Add to Verdict Agent system prompt:
> "If fewer than 5 convergence signals align, you MUST issue WATCH — not BUY. Do not issue BUY on weak setups. Fewer but stronger calls build more trust than frequent weak ones."

This is one prompt line. No schema change needed.

---

## Phase 3 — When We Have 60+ Days of History

### Historical Pattern Match

Once the system has accumulated enough of its own verdict history:

> "Last 4 times NFLX had RSI below 42 + earnings beat in prior quarter, it returned an average of +19% over 90 days (3 of 4 occurrences in our own data)."

Backtestable on the existing `stock_analyses` table. The data is being stored correctly now. Cannot use this feature meaningfully until ~60 days of nightly runs exist.

---

## Full Implementation Roadmap

### Phase 1 — Done ✓
- Entry quality, hold-and-forget, position size, 90-day scenarios, don't-panic note
- Signal checklist strip in expanded detail

### Phase 2 — Next (this sprint)

| Feature | Backend | Frontend | DB Change |
|---------|---------|----------|-----------|
| Signal convergence score | Verdict Agent prompt + parser | Show on spotlight card + expanded detail | `signal_convergence_score INT`, `convergence_details TEXT` |
| Conviction floor < 70 → WATCH | Verdict Agent prompt rule | No change | None |
| All-clear daily message | None (logic in frontend) | New card on Dashboard tab | None |
| Daily spotlight card | None | New top card on Dashboard | None |
| Action clarity (shares) | None | Compute from portfolio_size | `users.portfolio_size FLOAT` |
| Portfolio size onboarding | `/users/me PATCH` endpoint | One-time prompt on first open | `users.portfolio_size FLOAT` |

### Phase 3 — Later
- Historical pattern match (needs 60+ days of data)
- Weekly digest email/push notification
- Sector concentration awareness (warn if too much in one sector)

---

## The North Star Screen

**When something is actionable (opens once a day):**
```
⚡ 1 Opportunity Today

NFLX — BUY  ·  Conviction 84/100  ·  6 of 7 signals
Great Entry  ·  Hold & Forget ✓  ·  6% of portfolio

Why now: RSI 38 (oversold) · 18% analyst upside · Institutions buying
         No earnings for 47 days · FCF $6.2B positive

Bull +24% (30%)  /  Base +9% (50%)  /  Bear -11% (20%)
Buy ≤ $680  ·  Stop $590  ·  Target $800  ·  60-90 days

[ Take Action → ]     [ Skip for now ]
```

**When nothing is actionable:**
```
✓ All Clear — Nothing to do today

Your 4 positions are on track.
Analyzed tonight at 2:14 AM.

See you tomorrow.
```

That's the product. Open once a day. Know immediately. Move on.

---

## Design Principles That Must Never Break

1. **No weak BUYs.** If the signals aren't there, say WATCH. Credibility is built by not crying wolf.
2. **"Nothing to do" is a valid and valuable answer.** Silence from the advisor means noise in the user's head.
3. **Every number must come from real data.** RSI from yfinance. Analyst targets from Finnhub + yfinance cross-validated. No fabricated confidence.
4. **Plain English always.** The user is a nurse, not a quant.
5. **One primary action per day.** Not five opportunities. One. The best one.
