from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


def _to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(v) for v in obj]
    return obj


@dataclass
class Socials:
    twitter: str = ""
    telegram: str = ""
    discord: str = ""
    website: str = ""
    farcaster: str = ""

    def any(self) -> bool:
        return any([self.twitter, self.telegram, self.discord, self.website, self.farcaster])


@dataclass
class Token:
    chain_id: int
    launchpad: str
    address: str
    name: str = ""
    symbol: str = ""
    description: str = ""
    image: str = ""
    socials: Socials = field(default_factory=Socials)
    creator: str = ""
    progress_pct: float = 0.0
    unique_buyers: int = 0
    age_minutes: float = 0.0
    has_metadata: bool = False
    risk_score: float = 0.0
    quote_token: str = ""
    pair: str = ""
    pool: str = ""
    launch_id: int | None = None
    factory: str = ""
    block_number: int = 0
    tx_hash: str = ""
    timestamp: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class Holder:
    address: str
    balance: int
    pct: float = 0.0


@dataclass
class Trade:
    tx_hash: str
    block_number: int
    trader: str
    side: str  # buy | sell
    quote_amount: int = 0
    token_amount: int = 0
    timestamp: int = 0


@dataclass
class Progress:
    progress_pct: float
    paired_principal: int = 0
    threshold: int = 0
    graduated: bool = False


@dataclass
class PriceQuote:
    price_in_quote: float
    quote_token: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwapQuote:
    amount_in: int
    amount_out: int
    price_impact_pct: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Analysis:
    holders: list[Holder] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    unique_buyers: int = 0
    unique_sellers: int = 0
    buy_count: int = 0
    sell_count: int = 0
    buy_quote_volume: int = 0
    sell_quote_volume: int = 0
    insider_pct: float = 0.0
    top5_pct: float = 0.0
    creator_pct: float = 0.0
    has_socials: bool = False
    curve_health: float = 0.0
    organic_score: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class AuditResult:
    passed: bool
    wash_trading: bool = False
    coordinated_buys: bool = False
    dump_risk: float = 1.0
    reasons: list[str] = field(default_factory=list)
    raw: str = ""
    parse_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class NarrativeScore:
    narrative_fit: float = 0.0
    virality: float = 0.0
    community: float = 0.0
    timing: float = 0.0
    summary: str = ""
    raw: str = ""
    parse_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class TimingMood:
    mood: float = 0.5  # 0 risk-off … 1 meme-season
    meme_season: bool = False
    volume_regime: str = "unknown"
    summary: str = ""
    cached: bool = False
    raw: str = ""
    parse_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class CheckerResult:
    approve: bool
    reasons_not_to_buy: list[str] = field(default_factory=list)
    raw: str = ""
    parse_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class ScoreBreakdown:
    total: float
    components: dict[str, float]
    threshold: float
    passed: bool
    skipped_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class IntendedTrade:
    token: Token
    side: str
    size_eth: float
    reason: str
    mode: str = "paper"

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)
