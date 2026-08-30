"""Optional single eth_getLogs against public RPCs. Skip on any failure."""

import pytest

from grokbot.abi import PONS_V1_TOKEN_LAUNCHED
from grokbot.events import INKY_LAUNCH_CREATED
from grokbot.rpc import JsonRpc, RpcError

PONS_RPC = "https://rpc.mainnet.chain.robinhood.com"
PONS_FACTORY = "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB"
INK_RPC = "https://rpc-gel.inkonchain.com"
INK_HOOK = "0x4cC8F6d5B7cE150CCC0A9B7664532B1283b96AC4"


async def _probe(url: str, address: str, topic: str) -> int:
    rpc = JsonRpc(url, timeout=12.0)
    try:
        head = await rpc.block_number()
        logs = await rpc.get_logs_chunked(
            address=address,
            topics=[topic],
            from_block=max(0, head - 200),
            to_block=head,
            chunk=100,
            min_chunk=20,
        )
        return len(logs)
    finally:
        await rpc.aclose()


@pytest.mark.asyncio
async def test_optional_pons_eth_get_logs():
    try:
        n = await _probe(PONS_RPC, PONS_FACTORY, PONS_V1_TOKEN_LAUNCHED)
    except (RpcError, Exception) as exc:
        pytest.skip(f"PONS RPC unavailable: {exc}")
    assert n >= 0


@pytest.mark.asyncio
async def test_optional_ink_eth_get_logs():
    try:
        n = await _probe(INK_RPC, INK_HOOK, INKY_LAUNCH_CREATED)
    except (RpcError, Exception) as exc:
        pytest.skip(f"Ink RPC unavailable: {exc}")
    assert n >= 0
