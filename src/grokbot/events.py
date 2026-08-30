"""Parse launchpad logs into structured records. Fixtures drive tests; live RPC is optional."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from grokbot.abi import (
    INKY_LAUNCH_CREATED_SIG,
    INKY_LAUNCH_FINALIZED_SIG,
    INKY_LAUNCH_METADATA_SIG,
    INKY_TRADE_SIG_CANON,
    PONS_V1_TOKEN_LAUNCHED,
    PONS_V1_TOKEN_LAUNCHED_SIG,
    PONS_V2_CURVE_BUY,
    PONS_V2_CURVE_SELL,
    PONS_V2_TOKEN_LAUNCHED,
    PONS_V2_TOKEN_LAUNCHED_SIG,
    UNISWAP_V3_SWAP,
    UNISWAP_V3_SWAP_SIG,
    decode_abi_strings,
    decode_address,
    decode_int256,
    decode_uint,
    hex_to_bytes,
    topic0,
    topic_address,
    topic_uint,
    words,
)

INKY_LAUNCH_CREATED = topic0(INKY_LAUNCH_CREATED_SIG)
INKY_LAUNCH_METADATA = topic0(INKY_LAUNCH_METADATA_SIG)
INKY_TRADE = topic0(INKY_TRADE_SIG_CANON)
INKY_LAUNCH_FINALIZED = topic0(INKY_LAUNCH_FINALIZED_SIG)
PONS_V1_TOKEN_LAUNCHED_COMPUTED = topic0(PONS_V1_TOKEN_LAUNCHED_SIG)
PONS_V2_TOKEN_LAUNCHED_COMPUTED = topic0(PONS_V2_TOKEN_LAUNCHED_SIG)
UNISWAP_V3_SWAP_COMPUTED = topic0(UNISWAP_V3_SWAP_SIG)


def _topics(log: dict[str, Any]) -> list[str]:
    return [t.lower() if isinstance(t, str) else t for t in (log.get("topics") or [])]


def _data_bytes(log: dict[str, Any]) -> bytes:
    return hex_to_bytes(log.get("data") or "0x")


def _block(log: dict[str, Any]) -> int:
    v = log.get("blockNumber") or 0
    if isinstance(v, str):
        return int(v, 16) if v.startswith("0x") else int(v)
    return int(v)


def _tx(log: dict[str, Any]) -> str:
    return (log.get("transactionHash") or "").lower()


def _addr(log: dict[str, Any]) -> str:
    return decode_address(log.get("address") or "0x0")


@dataclass
class PonsLaunch:
    version: str  # v1 | v2
    token: str
    deployer: str
    pair_token: str
    pool: str = ""
    curve: str = ""
    dex_factory: str = ""
    dex_id: int = 0
    launch_config_id: int = 0
    position_id: int = 0
    restrictions_end_block: int = 0
    initial_buy_amount: int = 0
    graduation_threshold: int = 0
    factory: str = ""
    block_number: int = 0
    tx_hash: str = ""


def parse_pons_token_launched(log: dict[str, Any]) -> PonsLaunch:
    topics = _topics(log)
    if not topics:
        raise ValueError("TokenLaunched log missing topics")
    t0 = topics[0]
    data = words(_data_bytes(log))
    factory = _addr(log)
    if t0 == PONS_V1_TOKEN_LAUNCHED:
        # indexed: token, deployer, dexFactory
        # data: pairToken, pool, dexId, launchConfigId, positionId, restrictionsEndBlock, initialBuyAmount
        if len(topics) < 4 or len(data) < 7:
            raise ValueError("malformed PONS V1 TokenLaunched")
        return PonsLaunch(
            version="v1",
            token=topic_address(topics[1]),
            deployer=topic_address(topics[2]),
            dex_factory=topic_address(topics[3]),
            pair_token=decode_address(data[0]),
            pool=decode_address(data[1]),
            dex_id=decode_uint(data[2]),
            launch_config_id=decode_uint(data[3]),
            position_id=decode_uint(data[4]),
            restrictions_end_block=decode_uint(data[5]),
            initial_buy_amount=decode_uint(data[6]),
            factory=factory,
            block_number=_block(log),
            tx_hash=_tx(log),
        )
    if t0 == PONS_V2_TOKEN_LAUNCHED:
        # indexed: token, curve, deployer
        # data: pairToken, launchConfigId, graduationThreshold
        if len(topics) < 4 or len(data) < 3:
            raise ValueError("malformed PONS V2 TokenLaunched")
        return PonsLaunch(
            version="v2",
            token=topic_address(topics[1]),
            curve=topic_address(topics[2]),
            deployer=topic_address(topics[3]),
            pair_token=decode_address(data[0]),
            launch_config_id=decode_uint(data[1]),
            graduation_threshold=decode_uint(data[2]),
            pool=topic_address(topics[2]),  # curve is the pre-graduation venue
            factory=factory,
            block_number=_block(log),
            tx_hash=_tx(log),
        )
    raise ValueError(f"unknown TokenLaunched topic0 {t0}")


@dataclass
class UniswapV3Swap:
    sender: str
    recipient: str
    amount0: int
    amount1: int
    sqrt_price_x96: int
    liquidity: int
    tick: int
    pool: str
    block_number: int
    tx_hash: str

    def side_for_token(self, token: str, pair_token: str) -> str:
        token_is_token0 = int(token, 16) < int(pair_token, 16)
        pair_signed = self.amount1 if token_is_token0 else self.amount0
        return "buy" if pair_signed > 0 else "sell"


def parse_uniswap_v3_swap(log: dict[str, Any]) -> UniswapV3Swap:
    topics = _topics(log)
    data = words(_data_bytes(log))
    if not topics or topics[0] != UNISWAP_V3_SWAP:
        raise ValueError("not a Uniswap V3 Swap log")
    if len(topics) < 3 or len(data) < 5:
        raise ValueError("malformed Swap")
    return UniswapV3Swap(
        sender=topic_address(topics[1]),
        recipient=topic_address(topics[2]),
        amount0=decode_int256(data[0]),
        amount1=decode_int256(data[1]),
        sqrt_price_x96=decode_uint(data[2]),
        liquidity=decode_uint(data[3]),
        tick=decode_int256(data[4]),
        pool=_addr(log),
        block_number=_block(log),
        tx_hash=_tx(log),
    )


@dataclass
class InkyLaunchCreated:
    launch_id: int
    creator: str
    token: str
    target_raise: int
    hook: str
    block_number: int
    tx_hash: str


def parse_inkypump_launch_created(log: dict[str, Any]) -> InkyLaunchCreated:
    topics = _topics(log)
    data = words(_data_bytes(log))
    if not topics or topics[0] != INKY_LAUNCH_CREATED:
        raise ValueError("not an InkyPump LaunchCreated log")
    if len(topics) < 3 or len(data) < 2:
        raise ValueError("malformed LaunchCreated")
    return InkyLaunchCreated(
        launch_id=topic_uint(topics[1]),
        creator=topic_address(topics[2]),
        token=decode_address(data[0]),
        target_raise=decode_uint(data[1]),
        hook=_addr(log),
        block_number=_block(log),
        tx_hash=_tx(log),
    )


@dataclass
class InkyLaunchMetadata:
    launch_id: int
    name: str
    ticker: str
    description: str
    image_url: str
    telegram: str
    twitter: str
    website: str
    hook: str
    block_number: int
    tx_hash: str


def parse_inkypump_launch_metadata(log: dict[str, Any]) -> InkyLaunchMetadata:
    topics = _topics(log)
    raw = _data_bytes(log)
    if not topics or topics[0] != INKY_LAUNCH_METADATA:
        raise ValueError("not an InkyPump LaunchMetadata log")
    launch_id = topic_uint(topics[1]) if len(topics) > 1 else 0
    strings = decode_abi_strings(raw, 7)
    strings += [""] * (7 - len(strings))
    return InkyLaunchMetadata(
        launch_id=launch_id,
        name=strings[0],
        ticker=strings[1],
        description=strings[2],
        image_url=strings[3],
        telegram=strings[4],
        twitter=strings[5],
        website=strings[6],
        hook=_addr(log),
        block_number=_block(log),
        tx_hash=_tx(log),
    )


@dataclass
class InkyTrade:
    launch_id: int
    trader: str
    trade_type: int  # 0 = buy, 1 = sell (enum TradeType in docs)
    price_after: int
    market_cap: int
    eth_amount: int
    token_amount: int
    fee: int
    refund: int
    hook: str
    block_number: int
    tx_hash: str

    @property
    def side(self) -> str:
        return "buy" if self.trade_type == 0 else "sell"


def parse_inkypump_trade(log: dict[str, Any]) -> InkyTrade:
    topics = _topics(log)
    data = words(_data_bytes(log))
    if not topics or topics[0] != INKY_TRADE:
        raise ValueError("not an InkyPump Trade log")
    if len(topics) < 3 or len(data) < 7:
        raise ValueError("malformed Trade")
    # non-indexed: uint8 tradeType, (priceAfter, marketCap), (ethAmount, tokenAmount, fee), refund
    return InkyTrade(
        launch_id=topic_uint(topics[1]),
        trader=topic_address(topics[2]),
        trade_type=decode_uint(data[0]),
        price_after=decode_uint(data[1]),
        market_cap=decode_uint(data[2]),
        eth_amount=decode_uint(data[3]),
        token_amount=decode_uint(data[4]),
        fee=decode_uint(data[5]),
        refund=decode_uint(data[6]),
        hook=_addr(log),
        block_number=_block(log),
        tx_hash=_tx(log),
    )


@dataclass
class CurveTrade:
    side: str
    trader: str
    quote_amount: int
    token_amount: int
    fee: int
    tax: int
    curve: str
    block_number: int
    tx_hash: str


def parse_pons_v2_curve_trade(log: dict[str, Any]) -> CurveTrade:
    topics = _topics(log)
    data = words(_data_bytes(log))
    t0 = topics[0] if topics else ""
    if t0 == PONS_V2_CURVE_BUY:
        # CurveBuy(address indexed buyer, address indexed recipient, uint256 quoteIn, uint256 tokensOut, uint256 fee, uint256 tax)
        return CurveTrade(
            side="buy",
            trader=topic_address(topics[1]) if len(topics) > 1 else "0x0",
            quote_amount=decode_uint(data[0]) if data else 0,
            token_amount=decode_uint(data[1]) if len(data) > 1 else 0,
            fee=decode_uint(data[2]) if len(data) > 2 else 0,
            tax=decode_uint(data[3]) if len(data) > 3 else 0,
            curve=_addr(log),
            block_number=_block(log),
            tx_hash=_tx(log),
        )
    if t0 == PONS_V2_CURVE_SELL:
        return CurveTrade(
            side="sell",
            trader=topic_address(topics[1]) if len(topics) > 1 else "0x0",
            token_amount=decode_uint(data[0]) if data else 0,
            quote_amount=decode_uint(data[1]) if len(data) > 1 else 0,
            fee=decode_uint(data[2]) if len(data) > 2 else 0,
            tax=decode_uint(data[3]) if len(data) > 3 else 0,
            curve=_addr(log),
            block_number=_block(log),
            tx_hash=_tx(log),
        )
    raise ValueError("not a PONS V2 curve trade")
