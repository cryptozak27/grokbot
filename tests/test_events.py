"""Fixture log parsing for PONS TokenLaunched and InkyPump events."""

from grokbot.abi import (
    PONS_V1_TOKEN_LAUNCHED,
    PONS_V1_TOKEN_LAUNCHED_SIG,
    PONS_V2_TOKEN_LAUNCHED,
    PONS_V2_TOKEN_LAUNCHED_SIG,
    UNISWAP_V3_SWAP,
    UNISWAP_V3_SWAP_SIG,
    pad32,
    topic0,
)
from grokbot.events import (
    INKY_LAUNCH_CREATED,
    INKY_LAUNCH_METADATA,
    INKY_TRADE,
    parse_inkypump_launch_created,
    parse_inkypump_launch_metadata,
    parse_inkypump_trade,
    parse_pons_token_launched,
    parse_uniswap_v3_swap,
)
from tests.helpers import addr_topic, log, static_data, string_tuple_data, uint_topic

PONS_FACTORY = "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB"
HOOK = "0x4cC8F6d5B7cE150CCC0A9B7664532B1283b96AC4"
TOKEN = "0x1111111111111111111111111111111111111111"
DEPLOYER = "0x2222222222222222222222222222222222222222"
DEX = "0x1f7d7550B1b028f7571E69A784071F0205FD2EfA"
WETH = "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73"
POOL = "0x3333333333333333333333333333333333333333"
CREATOR = "0xaAaAaAaaAaAaAaaAaAAAAAAAAaaaAaAaAaaAaaAa"
INK_TOKEN = "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"
TRADER = "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"


def test_pons_v1_topic0_matches_docs():
    assert topic0(PONS_V1_TOKEN_LAUNCHED_SIG) == PONS_V1_TOKEN_LAUNCHED
    assert topic0(UNISWAP_V3_SWAP_SIG) == UNISWAP_V3_SWAP
    assert topic0(PONS_V2_TOKEN_LAUNCHED_SIG) == PONS_V2_TOKEN_LAUNCHED


def test_parse_pons_v1_token_launched():
    data = static_data(WETH, POOL, 1, 0, 42, 100, 10**17)
    raw = log(
        PONS_FACTORY,
        [PONS_V1_TOKEN_LAUNCHED, addr_topic(TOKEN), addr_topic(DEPLOYER), addr_topic(DEX)],
        data,
        block=8991200,
        tx="0x" + "11" * 32,
    )
    ev = parse_pons_token_launched(raw)
    assert ev.version == "v1"
    assert ev.token == TOKEN.lower()
    assert ev.deployer == DEPLOYER.lower()
    assert ev.dex_factory == DEX.lower()
    assert ev.pair_token == WETH.lower()
    assert ev.pool == POOL.lower()
    assert ev.position_id == 42
    assert ev.initial_buy_amount == 10**17
    assert ev.block_number == 8991200


def test_parse_pons_v2_token_launched():
    curve = "0x4444444444444444444444444444444444444444"
    data = static_data(WETH, 3, 42 * 10**17)  # pair, launchConfigId, 4.2 ETH
    raw = log(
        "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e",
        [PONS_V2_TOKEN_LAUNCHED, addr_topic(TOKEN), addr_topic(curve), addr_topic(DEPLOYER)],
        data,
    )
    ev = parse_pons_token_launched(raw)
    assert ev.version == "v2"
    assert ev.token == TOKEN.lower()
    assert ev.curve == curve.lower()
    assert ev.deployer == DEPLOYER.lower()
    assert ev.graduation_threshold == 42 * 10**17


def test_parse_uniswap_v3_swap_buy_when_token_is_token0():
    # Use a token address < WETH so it is token0; pairSigned = amount1 > 0 => buy
    # (docs.ponsfamily.com: pairSigned = tokenIsToken0 ? amount1 : amount0)

    token0 = "0x0111111111111111111111111111111111111111"
    assert int(token0, 16) < int(WETH, 16)

    def i256(n: int) -> bytes:
        return (n & ((1 << 256) - 1)).to_bytes(32, "big")

    data = i256(-(10**18)) + i256(5 * 10**16) + pad32(1) + pad32(1) + i256(10)
    raw = log(
        POOL,
        [UNISWAP_V3_SWAP, addr_topic(DEPLOYER), addr_topic(TRADER)],
        data,
    )
    ev = parse_uniswap_v3_swap(raw)
    assert ev.recipient == TRADER.lower()
    assert ev.amount1 > 0
    assert ev.side_for_token(token0, WETH) == "buy"


def test_parse_inkypump_launch_created():
    data = static_data(INK_TOKEN, 3 * 10**18)
    raw = log(
        HOOK,
        [INKY_LAUNCH_CREATED, uint_topic(7), addr_topic(CREATOR)],
        data,
        block=9000,
    )
    ev = parse_inkypump_launch_created(raw)
    assert ev.launch_id == 7
    assert ev.creator == CREATOR.lower()
    assert ev.token == INK_TOKEN.lower()
    assert ev.target_raise == 3 * 10**18
    assert ev.block_number == 9000


def test_parse_inkypump_launch_metadata():
    data = string_tuple_data(
        ["Inky Cat", "ICAT", "cats on ink", "https://img", "t.me/x", "https://x.com/x", "https://x"]
    )
    raw = log(HOOK, [INKY_LAUNCH_METADATA, uint_topic(7)], data)
    ev = parse_inkypump_launch_metadata(raw)
    assert ev.launch_id == 7
    assert ev.name == "Inky Cat"
    assert ev.ticker == "ICAT"
    assert ev.description == "cats on ink"
    assert ev.twitter == "https://x.com/x"


def test_parse_inkypump_trade_buy():
    # tradeType=0 buy, priceAfter, marketCap, ethAmount, tokenAmount, fee, refund
    data = static_data(0, 10**16, 5 * 10**16, 10**17, 10**21, 10**15, 0)
    raw = log(HOOK, [INKY_TRADE, uint_topic(7), addr_topic(TRADER)], data)
    ev = parse_inkypump_trade(raw)
    assert ev.launch_id == 7
    assert ev.trader == TRADER.lower()
    assert ev.trade_type == 0
    assert ev.side == "buy"
    assert ev.eth_amount == 10**17
    assert ev.token_amount == 10**21
    assert ev.fee == 10**15


def test_load_json_fixtures_from_disk():
    import json
    from pathlib import Path

    root = Path(__file__).parent / "fixtures"
    v1 = json.loads((root / "pons_token_launched_v1.json").read_text())
    ev = parse_pons_token_launched(v1)
    assert ev.token.endswith("1111")
    created = json.loads((root / "inkypump_launch_created.json").read_text())
    ev2 = parse_inkypump_launch_created(created)
    assert ev2.launch_id == 7
    trade = json.loads((root / "inkypump_trade.json").read_text())
    ev3 = parse_inkypump_trade(trade)
    assert ev3.side == "buy"
    meta = json.loads((root / "inkypump_launch_metadata.json").read_text())
    ev4 = parse_inkypump_launch_metadata(meta)
    assert ev4.ticker == "ICAT"
