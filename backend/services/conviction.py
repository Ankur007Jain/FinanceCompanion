"""Calibrate the LLM's narrative conviction against a deterministic signal score.

The LLM's raw conviction_score reflects how confident its write-up reads, not how many
real signals actually line up — the weekly scorecard found this inverted (high
conviction BUYs underperformed lower conviction BUYs). This blends the raw score with
signal_convergence_score (computed independently of the LLM, before it runs) so
conviction can't be inflated by confident prose alone.
"""

# Weight given to the LLM's narrative read vs. the deterministic signal score.
# Starting point; retune once a few weeks of post-fix scorecard data comes in.
_NARRATIVE_WEIGHT = 0.5


def calibrate_conviction(raw_conviction: int | None, convergence_score: int | None, max_convergence: int = 10) -> int | None:
    if raw_conviction is None:
        return None
    if convergence_score is None:
        return raw_conviction
    signal_component = (convergence_score / max_convergence) * 100
    blended = _NARRATIVE_WEIGHT * raw_conviction + (1 - _NARRATIVE_WEIGHT) * signal_component
    return round(max(0, min(100, blended)))
