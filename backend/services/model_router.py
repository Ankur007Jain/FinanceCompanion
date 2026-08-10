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


# The plain default used to be 4096 — reproduced live against a real production
# message that doesn't match the keywords below ("acc to all the scenarios predict how
# much i will have after 5 yr..."): Claude chose to run a web search before answering,
# and thinking + the unfinished search alone consumed all 4096 tokens, leaving zero
# room for the answer. Re-ran the same message at 8192/12000/16000 and actual usage
# converged to ~3900-4500 output tokens every time regardless of ceiling — so 8192
# comfortably covers a tool round-trip, and since Anthropic bills by tokens actually
# generated (not the ceiling), this costs nothing for calls that don't need it. The
# keyword check no longer changes the number, but stays as a readable marker of intent
# (explicitly "this needs room to be thorough") separate from the short-message case.
def _estimate_max_tokens(message: str) -> int:
    if len(message.split()) < 4:
        return 1024
    return 8192


def _should_use_extended_thinking(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in _COMPLEX_DECISION_KEYWORDS)
