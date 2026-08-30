"""Clanker on Base — stub only (interface + config). No fake live data."""

from grokbot.adapters.base import StubAdapter


class ClankerAdapter(StubAdapter):
    def __init__(self, config: dict) -> None:
        super().__init__(name="clanker", chain_id=int(config.get("chain_id", 8453)), config=config)
