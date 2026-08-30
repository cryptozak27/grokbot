from __future__ import annotations

from grokbot.adapters.base import LaunchpadAdapter
from grokbot.models import Analysis, Token
from grokbot.rpc import RpcError


def _curve_health(token: Token, buy_vol: int, sell_vol: int) -> float:
    progress = token.progress_pct
    # Sweet spot ~10–70%. Extremes are worse.
    if progress <= 0:
        p = 0.0
    elif progress < 10:
        p = progress / 10.0 * 0.5
    elif progress <= 70:
        p = 0.5 + (70 - abs(40 - progress)) / 70.0 * 0.5
        p = min(1.0, p)
    else:
        p = max(0.0, 1.0 - (progress - 70) / 30.0)
    flow = 1.0
    if buy_vol + sell_vol > 0:
        flow = buy_vol / (buy_vol + sell_vol)
    return max(0.0, min(1.0, 0.6 * p + 0.4 * flow))


def _organic(unique_buyers: int, insider_pct: float, top5: float) -> float:
    buyer_s = min(1.0, unique_buyers / 40.0)
    insider_s = max(0.0, 1.0 - insider_pct)
    conc_s = max(0.0, 1.0 - top5)
    return max(0.0, min(1.0, 0.4 * buyer_s + 0.35 * insider_s + 0.25 * conc_s))


async def analyze(adapter: LaunchpadAdapter, token: Token) -> Analysis:
    notes: list[str] = []
    try:
        holders = await adapter.get_holders(token.address)
    except (RpcError, Exception) as exc:
        holders = []
        notes.append(f"holders_unavailable: {exc}")
    try:
        trades = await adapter.get_trades(token.address)
    except (RpcError, Exception) as exc:
        trades = []
        notes.append(f"trades_unavailable: {exc}")

    buys = [t for t in trades if t.side == "buy"]
    sells = [t for t in trades if t.side == "sell"]
    unique_buyers = len({t.trader.lower() for t in buys})
    unique_sellers = len({t.trader.lower() for t in sells})
    buy_vol = sum(t.quote_amount for t in buys)
    sell_vol = sum(t.quote_amount for t in sells)

    top5 = sum(h.pct for h in holders[:5]) if holders else 0.0
    creator = token.creator.lower() if token.creator else ""
    creator_pct = next((h.pct for h in holders if h.address.lower() == creator), 0.0)
    insider_pct = min(1.0, creator_pct + top5 * 0.5)

    if unique_buyers:
        token.unique_buyers = max(token.unique_buyers, unique_buyers)

    organic = _organic(token.unique_buyers, insider_pct, top5)
    health = _curve_health(token, buy_vol, sell_vol)
    return Analysis(
        holders=holders,
        trades=trades,
        unique_buyers=token.unique_buyers,
        unique_sellers=unique_sellers,
        buy_count=len(buys),
        sell_count=len(sells),
        buy_quote_volume=buy_vol,
        sell_quote_volume=sell_vol,
        insider_pct=insider_pct,
        top5_pct=top5,
        creator_pct=creator_pct,
        has_socials=token.socials.any(),
        curve_health=health,
        organic_score=organic,
        notes=notes,
    )
