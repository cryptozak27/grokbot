"""Weighted score is CODE, not the model."""

from __future__ import annotations

from grokbot.config import ScoringConfig
from grokbot.models import Analysis, NarrativeScore, ScoreBreakdown, TimingMood

DEFAULT_WEIGHTS = {
    "narrative_fit": 0.22,
    "virality": 0.18,
    "community": 0.14,
    "timing": 0.14,
    "organic_score": 0.18,
    "curve_health": 0.14,
}


def compute_score(
    narrative: NarrativeScore,
    timing: TimingMood,
    analysis: Analysis,
    cfg: ScoringConfig | None = None,
) -> ScoreBreakdown:
    weights = dict(DEFAULT_WEIGHTS)
    threshold = 0.62
    if cfg is not None:
        weights.update(cfg.weights or {})
        threshold = cfg.threshold
    timing_component = narrative.timing * 0.5 + timing.mood * 0.5
    components = {
        "narrative_fit": _clip(narrative.narrative_fit),
        "virality": _clip(narrative.virality),
        "community": _clip(narrative.community),
        "timing": _clip(timing_component),
        "organic_score": _clip(analysis.organic_score),
        "curve_health": _clip(analysis.curve_health),
    }
    total_w = sum(weights.get(k, 0.0) for k in components) or 1.0
    total = sum(components[k] * weights.get(k, 0.0) for k in components) / total_w
    passed = total >= threshold
    return ScoreBreakdown(
        total=total,
        components=components,
        threshold=threshold,
        passed=passed,
        skipped_reason="" if passed else "score_below_threshold",
    )


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))
