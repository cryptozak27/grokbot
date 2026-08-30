from pathlib import Path

import pytest

from grokbot.adapters.base import LiveTradingDisabled
from grokbot.adapters.pons import PonsAdapter
from grokbot.execution.paper import PaperExecutor, assert_no_broadcast
from grokbot.log import JsonlLogger
from grokbot.models import Token
from grokbot.rpc import JsonRpc, RpcError


class RecordingRpc(JsonRpc):
    def __init__(self) -> None:
        super().__init__("http://127.0.0.1:1")
        self.posts: list[str] = []

    async def call(self, method: str, params=None):
        self.posts.append(method)
        self.sent_methods.append(method)
        if method.startswith("eth_send"):
            raise RpcError(f"refusing broadcast RPC method {method}")
        raise RpcError("no network in tests")


@pytest.mark.asyncio
async def test_paper_executor_never_sends_txs(good_token: Token, tmp_path: Path):
    rpc = RecordingRpc()
    adapter = PonsAdapter(
        rpc,
        {
            "chain_id": 4663,
            "factory": "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB",
            "weth": "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73",
        },
        paper=True,
    )
    logger = JsonlLogger(tmp_path / "pipeline.jsonl")
    exe = PaperExecutor(logger)
    rec = await exe.buy(adapter, good_token, 0.02, "test")
    assert rec["action"] == "buy"
    assert rec["context"]["sent"] is False
    assert rec["context"]["mode"] == "paper"
    assert "eth_send" not in "".join(rpc.sent_methods)
    assert_no_broadcast(rpc)
    line = (tmp_path / "pipeline.jsonl").read_text()
    assert '"action": "buy"' in line
    assert "sent" in line


@pytest.mark.asyncio
async def test_live_buy_raises_without_sending(good_token: Token):
    rpc = RecordingRpc()
    adapter = PonsAdapter(
        rpc,
        {
            "chain_id": 4663,
            "factory": "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB",
        },
        paper=False,
    )
    with pytest.raises(LiveTradingDisabled):
        await adapter.buy(good_token.address, 10**16)
    assert not any(m.startswith("eth_send") for m in rpc.sent_methods)


@pytest.mark.asyncio
async def test_json_rpc_refuses_eth_send():
    rpc = RecordingRpc()
    with pytest.raises(RpcError, match="refusing broadcast"):
        await rpc.call("eth_sendRawTransaction", ["0xdead"])
