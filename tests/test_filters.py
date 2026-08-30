from grokbot.config import FilterConfig
from grokbot.filters import cheap_filters
from grokbot.models import Token


def _tok(**kwargs) -> Token:
    base = dict(
        chain_id=4663,
        launchpad="pons",
        address="0x1111111111111111111111111111111111111111",
        name="Test Cat",
        symbol="TCAT",
        description="A reasonably long description.",
        has_metadata=True,
        unique_buyers=12,
        age_minutes=10,
        progress_pct=20,
        risk_score=0.2,
    )
    base.update(kwargs)
    return Token(**base)


CFG = FilterConfig()


def test_pass_healthy_token():
    ok, reason = cheap_filters(_tok(), CFG)
    assert ok and reason == "ok"


def test_reject_no_metadata():
    ok, reason = cheap_filters(_tok(has_metadata=False, name=""), CFG)
    assert not ok and "metadata" in reason or "name" in reason


def test_reject_low_buyers():
    ok, reason = cheap_filters(_tok(unique_buyers=2), CFG)
    assert not ok and reason == "filter:low_unique_buyers"


def test_reject_too_new():
    ok, reason = cheap_filters(_tok(age_minutes=0.2), CFG)
    assert not ok and reason == "filter:too_new"


def test_reject_too_old():
    ok, reason = cheap_filters(_tok(age_minutes=400), CFG)
    assert not ok and reason == "filter:too_old"


def test_reject_progress_bounds():
    ok, r1 = cheap_filters(_tok(progress_pct=1), CFG)
    ok2, r2 = cheap_filters(_tok(progress_pct=90), CFG)
    assert not ok and r1 == "filter:low_progress"
    assert not ok2 and r2 == "filter:too_graduated"


def test_reject_thin_description():
    ok, reason = cheap_filters(_tok(description="hi"), CFG)
    assert not ok and reason == "filter:thin_description"


def test_reject_high_risk():
    ok, reason = cheap_filters(_tok(risk_score=0.95), CFG)
    assert not ok and reason == "filter:risk_score"
