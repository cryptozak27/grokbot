from __future__ import annotations

from typing import Any

from grokbot.adapters.base import LaunchpadAdapter
from grokbot.log import JsonlLogger
from grokbot.models import IntendedTrade, Token
from grokbot.rpc import JsonRpc


class PaperExecutor:
    """Logs the intended trade. Never sends a transaction."""

    def __init__(self, logger: JsonlLogger) -> None:
        self.logger = logger
        self.intents: list[IntendedTrade] = []

    async def buy(
        self,
        adapter: LaunchpadAdapter,
        token: Token,
        size_eth: float,
        reason: str,
    ) -> dict[str, Any]:
        intent = IntendedTrade(
            token=token, side="buy", size_eth=size_eth, reason=reason, mode="paper"
        )
        self.intents.append(intent)
        rec = self.logger.write(
            "buy",
            token,
            mode="paper",
            sent=False,
            size_eth=size_eth,
            reason=reason,
            launchpad=adapter.name,
        )
        # Adapter buy is a no-op in paper and must not broadcast.
        result = await adapter.buy(token.address, int(size_eth * 10**18))
        if result.get("sent"):
            raise RuntimeError("paper adapter attempted to send a transaction")
        rec["adapter_result"] = result
        return rec

    async def close(
        self,
        adapter: LaunchpadAdapter,
        token: Token,
        size_eth: float,
        pnl_eth: float,
        reason: str,
    ) -> dict[str, Any]:
        result = await adapter.sell(token.address, 0)
        return self.logger.write(
            "close",
            token,
            mode="paper",
            sent=False,
            size_eth=size_eth,
            pnl_eth=pnl_eth,
            reason=reason,
            adapter_result=result,
        )


def assert_no_broadcast(rpc: JsonRpc) -> None:
    banned = [m for m in rpc.sent_methods if m.startswith("eth_send")]
    if banned:
        raise RuntimeError(f"broadcast RPC used in paper mode: {banned}")
