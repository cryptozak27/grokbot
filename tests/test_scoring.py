from grokbot.config import ScoringConfig
from grokbot.models import Analysis, NarrativeScore, TimingMood
from grokbot.scoring import compute_score


def test_weighted_score_is_code_not_llm():
    narrative = NarrativeScore(narrative_fit=1, virality=1, community=1, timing=1)
    timing = TimingMood(mood=1)
    analysis = Analysis(organic_score=1, curve_health=1)
    score = compute_score(narrative, timing, analysis, ScoringConfig(threshold=0.5))
    assert score.passed
    assert abs(score.total - 1.0) < 1e-9


def test_below_threshold_skips():
    narrative = NarrativeScore(narrative_fit=0.2, virality=0.1, community=0.1, timing=0.1)
    timing = TimingMood(mood=0.2)
    analysis = Analysis(organic_score=0.2, curve_health=0.2)
    score = compute_score(narrative, timing, analysis, ScoringConfig(threshold=0.62))
    assert not score.passed
    assert score.skipped_reason == "score_below_threshold"
    assert 0 <= score.total < 0.62


def test_custom_weights():
    cfg = ScoringConfig(
        weights={
            "narrative_fit": 1.0,
            "virality": 0,
            "community": 0,
            "timing": 0,
            "organic_score": 0,
            "curve_health": 0,
        },
        threshold=0.5,
    )
    narrative = NarrativeScore(narrative_fit=0.8)
    score = compute_score(narrative, TimingMood(mood=0), Analysis(), cfg)
    assert abs(score.total - 0.8) < 1e-9
    assert score.passed
