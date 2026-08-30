import pytest

from grokbot.config import AppConfig, FilterConfig, LlmConfig, RiskConfig, ScoringConfig
from grokbot.models import Analysis, Socials, Token


@pytest.fixture
def app_cfg() -> AppConfig:
    return AppConfig(
        execution_mode="paper",
        llm=LlmConfig(api_key=""),
        filters=FilterConfig(
            require_metadata=True,
            min_unique_buyers=8,
            min_age_minutes=1,
            max_age_minutes=180,
            min_progress_pct=5.0,
            max_progress_pct=85.0,
            max_risk_score=0.70,
            min_description_len=8,
        ),
        scoring=ScoringConfig(threshold=0.62),
        risk=RiskConfig(),
    )


@pytest.fixture
def good_token() -> Token:
    return Token(
        chain_id=4663,
        launchpad="pons",
        address="0x1111111111111111111111111111111111111111",
        name="Test Cat",
        symbol="TCAT",
        description="A reasonably long description for the token.",
        image="ipfs://x",
        socials=Socials(twitter="https://x.com/test", website="https://example.com"),
        creator="0x2222222222222222222222222222222222222222",
        progress_pct=22.0,
        unique_buyers=18,
        age_minutes=12.0,
        has_metadata=True,
        risk_score=0.2,
        quote_token="0x0bd7d308f8e1639fab988df18a8011f41eacad73",
        pair="0x3333333333333333333333333333333333333333",
        pool="0x3333333333333333333333333333333333333333",
    )


@pytest.fixture
def healthy_analysis() -> Analysis:
    return Analysis(
        unique_buyers=18,
        unique_sellers=4,
        buy_count=30,
        sell_count=6,
        buy_quote_volume=10**18,
        sell_quote_volume=2 * 10**17,
        insider_pct=0.12,
        top5_pct=0.28,
        creator_pct=0.05,
        has_socials=True,
        curve_health=0.72,
        organic_score=0.68,
    )
