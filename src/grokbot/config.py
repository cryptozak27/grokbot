from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FilterConfig:
    require_metadata: bool = True
    min_name_len: int = 1
    min_unique_buyers: int = 8
    min_age_minutes: float = 1.0
    max_age_minutes: float = 180.0
    min_progress_pct: float = 5.0
    max_progress_pct: float = 85.0
    max_risk_score: float = 0.70
    min_description_len: int = 8


@dataclass
class ScoringConfig:
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "narrative_fit": 0.22,
            "virality": 0.18,
            "community": 0.14,
            "timing": 0.14,
            "organic_score": 0.18,
            "curve_health": 0.14,
        }
    )
    threshold: float = 0.62


@dataclass
class RiskConfig:
    max_position_eth: float = 0.05
    daily_loss_limit_eth: float = 0.15
    max_trades_per_day: int = 10
    max_open_positions: int = 3
    shrink_start_pct: float = 0.70
    default_size_eth: float = 0.02


@dataclass
class LlmConfig:
    base_url: str = "https://api.x.ai/v1"
    auditor_model: str = "grok-4-fast"
    narrative_model: str = "grok-4-fast"
    timing_model: str = "grok-4-fast"
    checker_model: str = "grok-4"
    temperature: float = 0.0
    timing_cache_seconds: int = 1200
    timeout_seconds: float = 45.0
    api_key: str = ""


@dataclass
class PollConfig:
    interval_seconds: float = 4.0
    lookback_blocks: int = 4000
    log_chunk_blocks: int = 1500
    min_chunk_blocks: int = 50
    trade_lookback_blocks: int = 8000


@dataclass
class AppConfig:
    execution_mode: str = "paper"
    llm: LlmConfig = field(default_factory=LlmConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    poll: PollConfig = field(default_factory=PollConfig)
    launchpads: dict[str, dict[str, Any]] = field(default_factory=dict)
    log_dir: Path = field(default_factory=lambda: ROOT / "logs")
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_paper(self) -> bool:
        return self.execution_mode.lower() != "live"


def _overlay(dc_cls, data: dict[str, Any] | None, **extra: Any):
    data = dict(data or {})
    data.update({k: v for k, v in extra.items() if v is not None})
    fields = {f.name for f in dc_cls.__dataclass_fields__.values()}
    return dc_cls(**{k: v for k, v in data.items() if k in fields})


def load_config(path: str | Path | None = None) -> AppConfig:
    load_dotenv(ROOT / ".env", override=False)
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = yaml.safe_load(cfg_path.read_text()) or {}

    mode = os.environ.get("EXECUTION_MODE", raw.get("execution_mode", "paper"))
    llm_raw = dict(raw.get("llm") or {})
    llm_raw["api_key"] = os.environ.get("GROK_API_KEY", llm_raw.get("api_key", ""))

    poll_raw = dict(raw.get("poll") or {})
    if os.environ.get("POLL_LOOKBACK_BLOCKS"):
        poll_raw["lookback_blocks"] = int(os.environ["POLL_LOOKBACK_BLOCKS"])

    launchpads = dict(raw.get("launchpads") or {})
    for key, lp in launchpads.items():
        env_name = lp.get("rpc_env")
        if env_name and os.environ.get(env_name):
            lp["rpc"] = os.environ[env_name]

    log_dir = Path(raw.get("log_dir") or (ROOT / "logs"))
    if not log_dir.is_absolute():
        log_dir = ROOT / log_dir

    return AppConfig(
        execution_mode=str(mode).lower(),
        llm=_overlay(LlmConfig, llm_raw),
        filters=_overlay(FilterConfig, raw.get("filters")),
        scoring=_overlay(ScoringConfig, raw.get("scoring")),
        risk=_overlay(RiskConfig, raw.get("risk")),
        poll=_overlay(PollConfig, poll_raw),
        launchpads=launchpads,
        log_dir=log_dir,
        raw=raw,
    )
