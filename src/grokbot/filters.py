from __future__ import annotations

from grokbot.config import FilterConfig
from grokbot.models import Token


def cheap_filters(token: Token, cfg: FilterConfig) -> tuple[bool, str]:
    """Stage 1: cheap metadata / buyers / age / progress / risk. Fail closed on missing data."""
    if cfg.require_metadata and not token.has_metadata:
        return False, "filter:no_metadata"
    if len(token.name or "") < cfg.min_name_len or not token.symbol:
        return False, "filter:name_symbol"
    if cfg.min_description_len and len(token.description or "") < cfg.min_description_len:
        return False, "filter:thin_description"
    if token.unique_buyers < cfg.min_unique_buyers:
        return False, "filter:low_unique_buyers"
    if token.age_minutes < cfg.min_age_minutes:
        return False, "filter:too_new"
    if token.age_minutes > cfg.max_age_minutes:
        return False, "filter:too_old"
    if token.progress_pct < cfg.min_progress_pct:
        return False, "filter:low_progress"
    if token.progress_pct > cfg.max_progress_pct:
        return False, "filter:too_graduated"
    if token.risk_score > cfg.max_risk_score:
        return False, "filter:risk_score"
    return True, "ok"
