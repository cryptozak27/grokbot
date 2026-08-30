"""four.meme on BNB — stub only (interface + config). No fake live data."""

from grokbot.adapters.base import StubAdapter


class FourMemeAdapter(StubAdapter):
    def __init__(self, config: dict) -> None:
        super().__init__(name="fourmeme", chain_id=int(config.get("chain_id", 56)), config=config)
