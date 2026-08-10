# Sonnet 5 intro pricing ($2/$10 per MTok in/out) runs through Aug 31, 2026 — cheaper
# AND newer than 4.6's $3/$15. After that date it reverts to $3/$15, same as 4.6, so
# the cost argument for staying on 5 disappears (quality/recency argument still holds).
# Re-check https://docs.anthropic.com/en/docs/about-claude/pricing before/after that
# date in case pricing changed again — don't trust this comment as of-then-truth.
_SONNET = "claude-sonnet-5"

# Genuinely complex, multi-factor decisions — not just "give a long answer" (that's
# _estimate_max_tokens's job below) but "reason through several constraints before
# committing." Extended thinking gives the model room to work through that before
# answering, at real extra cost — reserved for the subset of questions where getting
# the reasoning right matters more than latency, matching this app's explicit
# priority (quality first, cost second). A heuristic, not a hard science; tune as
# real usage shows what actually needed it vs. what didn't.
_COMPLEX_DECISION_KEYWORDS = (
    "rebalance", "should i sell", "should i buy", "should i hold",
    "across my", "across all", "whole portfolio", "entire portfolio",
)

# Sonnet 5 dropped the old "type": "enabled" + budget_tokens shape (still used by
# Opus 4.5/Haiku 4.5) in favor of adaptive thinking: "type": "adaptive" plus a
# top-level output_config.effort ("low"/"medium"/"high"/"xhigh"/"max") — the model
# decides how much to think rather than us setting a token budget. Confirmed against
# a real 400 from claude-sonnet-5 ("thinking.type.enabled is not supported for this
# model") and the current API reference before fixing, not assumed from older docs.
_THINKING_EFFORT = "high"
# No manual budget to add on top of anymore, but max_tokens still needs enough
# headroom for the thinking + the final answer combined — same rough magnitude as
# the old budget_tokens(3000) + 2000 floor this replaces.
_THINKING_MIN_MAX_TOKENS = 5000


# Used to tier by message length (short message -> 1024, keyword match -> 6000, else
# 4096) on the assumption that a short message means a short, simple reply. Reproduced
# live against a real, heavily-loaded conversation (199 messages of financial planning)
# and found that assumption false: a literal "hi" in that conversation made Claude
# start a web search and burn through 2048 AND 4096 tokens of pure unprompted thinking
# with zero visible text either time — how much a message needs is a function of the
# conversation's complexity, which a per-message word count can't see. Only succeeded
# once given 8192. Since Anthropic bills by tokens actually generated, not the ceiling,
# a flat higher ceiling costs nothing for the (majority) of calls that don't need it —
# there was never a real cost argument for the old tiers, only a truncation risk.
def _estimate_max_tokens(message: str) -> int:
    return 8192


def _should_use_extended_thinking(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in _COMPLEX_DECISION_KEYWORDS)
