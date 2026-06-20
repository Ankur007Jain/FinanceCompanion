import re

_SONNET = "claude-sonnet-4-6"
_HAIKU = "claude-haiku-4-5-20251001"


def _estimate_max_tokens(message: str) -> int:
    lower = message.lower()
    if any(kw in lower for kw in ("analyze", "analysis", "compare", "explain", "deep dive", "full")):
        return 6000
    if len(message.split()) < 4:
        return 1024
    return 4096


def _select_model(message: str, max_tokens: int) -> str:
    if max_tokens >= 6000:
        return _SONNET
    if re.search(r"\b(analyze|compare|recommend|explain|why|should i|entry|exit|risk)\b", message, re.IGNORECASE):
        return _SONNET
    if len(message.split()) < 4:
        return _HAIKU
    return _SONNET
