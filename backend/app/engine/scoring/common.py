"""Shared helpers + return-shape for every scoring pillar.

Every pillar function returns a PillarResult. The contract that matters most:
a metric we couldn't compute is `None` with a reason, never a fabricated 0 —
the engine renormalizes weights around whatever pillars *are* available
rather than silently punishing missing data.
"""
from dataclasses import dataclass, field


@dataclass
class PillarResult:
    score: float | None       # points earned out of max_points; None = pillar entirely unavailable
    max_points: int
    available: bool
    details: dict = field(default_factory=dict)   # sub-metric values/reasons, for the score-breakdown UI
    positives: list[str] = field(default_factory=list)  # human-readable strengths this pillar found
    risks: list[str] = field(default_factory=list)      # human-readable concerns this pillar found


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def scale(value: float, lo: float, hi: float, reverse: bool = False) -> float:
    """Linearly map value in [lo, hi] to [0, 1], clamped at the ends.
    reverse=True flips so smaller value -> higher score (e.g. lower PE is better)."""
    if hi == lo:
        return 0.5
    t = clamp((value - lo) / (hi - lo))
    return 1 - t if reverse else t


def pct_growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior) * 100


def combine_components(components: list[tuple[float | None, float]], pillar_max: float) -> tuple[float | None, float]:
    """Combine (earned_points, component_max_points) pairs into a pillar score
    out of pillar_max, renormalized over only the components that were
    actually computable. Returns (score_or_None, data_coverage_fraction).
    A component pair is skipped entirely (not zeroed) when earned is None."""
    available = [(e, m) for e, m in components if e is not None]
    total_max = sum(m for _, m in components)
    if not available or total_max == 0:
        return None, 0.0
    earned_sum = sum(e for e, _ in available)
    avail_max = sum(m for _, m in available)
    coverage = avail_max / total_max
    score = (earned_sum / avail_max) * pillar_max
    return score, coverage
