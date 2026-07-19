_SONNET = "claude-sonnet-4-6"

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

_THINKING_BUDGET_TOKENS = 3000


def _estimate_max_tokens(message: str) -> int:
    lower = message.lower()
    if any(kw in lower for kw in ("analyze", "analysis", "compare", "explain", "deep dive", "full")):
        return 6000
    if len(message.split()) < 4:
        return 1024
    return 4096


def _should_use_extended_thinking(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in _COMPLEX_DECISION_KEYWORDS)
