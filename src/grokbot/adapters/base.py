from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from grokbot.models import Holder, PriceQuote, Progress, SwapQuote, Token, Trade


class AdapterError(RuntimeError):
    pass


class LiveTradingDisabled(AdapterError):
    """buy/sell on a live path is not implemented. Paper mode must no-op instead."""


class LaunchpadAdapter(ABC):
    """Chain-agnostic launchpad surface. Clanker / four.meme plug in here later."""

    name: str
    chain_id: int
    stub: bool = False

    @abstractmethod
    def stream_launches(self) -> AsyncIterator[Token]:
        """Poll eth_getLogs in bounded chunks. WS is optional and unused here."""

    @abstractmethod
    async def get_token(self, address: str) -> Token: ...

    @abstractmethod
    async def get_metadata(self, address: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_socials(self, address: str) -> dict[str, str]: ...

    @abstractmethod
    async def get_holders(self, address: str) -> list[Holder]: ...

    @abstractmethod
    async def get_trades(self, address: str) -> list[Trade]: ...

    @abstractmethod
    async def get_progress(self, address: str) -> Progress: ...

    @abstractmethod
    async def get_price(self, address: str) -> PriceQuote: ...

    @abstractmethod
    async def quote_buy(self, address: str, amount_wei: int) -> SwapQuote: ...

    @abstractmethod
    async def quote_sell(self, address: str, amount_tokens: int) -> SwapQuote: ...

    @abstractmethod
    async def buy(self, address: str, amount_wei: int, **kwargs: Any) -> dict[str, Any]:
        """Paper: no-op dict. Live: raise LiveTradingDisabled (never send txs)."""

    @abstractmethod
    async def sell(self, address: str, amount_tokens: int, **kwargs: Any) -> dict[str, Any]: ...


class StubAdapter(LaunchpadAdapter):
    """Interface + config only. No fake live data, no RPC traffic."""

    stub = True

    def __init__(self, name: str, chain_id: int, config: dict[str, Any]) -> None:
        self.name = name
        self.chain_id = chain_id
        self.config = config

    async def stream_launches(self) -> AsyncIterator[Token]:  # type: ignore[override]
        if False:
            yield Token(chain_id=self.chain_id, launchpad=self.name, address="")
        return
        yield  # pragma: no cover — makes this an async generator

    async def get_token(self, address: str) -> Token:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def get_metadata(self, address: str) -> dict[str, Any]:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def get_socials(self, address: str) -> dict[str, str]:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def get_holders(self, address: str) -> list[Holder]:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def get_trades(self, address: str) -> list[Trade]:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def get_progress(self, address: str) -> Progress:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def get_price(self, address: str) -> PriceQuote:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def quote_buy(self, address: str, amount_wei: int) -> SwapQuote:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def quote_sell(self, address: str, amount_tokens: int) -> SwapQuote:
        raise AdapterError(f"{self.name} adapter is a stub")

    async def buy(self, address: str, amount_wei: int, **kwargs: Any) -> dict[str, Any]:
        return {"mode": "paper", "sent": False, "adapter": self.name, "stub": True}

    async def sell(self, address: str, amount_tokens: int, **kwargs: Any) -> dict[str, Any]:
        return {"mode": "paper", "sent": False, "adapter": self.name, "stub": True}
