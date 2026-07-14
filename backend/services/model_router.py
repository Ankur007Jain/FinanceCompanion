_SONNET = "claude-sonnet-4-6"


def _estimate_max_tokens(message: str) -> int:
    lower = message.lower()
    if any(kw in lower for kw in ("analyze", "analysis", "compare", "explain", "deep dive", "full")):
        return 6000
    if len(message.split()) < 4:
        return 1024
    return 4096
