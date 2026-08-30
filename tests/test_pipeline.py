from pathlib import Path

import pytest

from grokbot.adapters.base import StubAdapter
from grokbot.agents.llm import ScriptedLlmClient
from grokbot.config import AppConfig
from grokbot.execution.paper import PaperExecutor
from grokbot.log import JsonlLogger
from grokbot.models import Holder, Token, Trade
from grokbot.pipeline import Pipeline
from grokbot.risk import RiskManager


class FakeAdapter(StubAdapter):
    def __init__(self, token: Token) -> None:
        super().__init__("pons", 4663, {})
        self.token = token
        self.stub = False
        self.buys = []

    async def stream_launches(self):
        yield self.token

    async def get_holders(self, address: str):
        return [Holder(address=self.token.creator, balance=1, pct=0.04)]

    async def get_trades(self, address: str):
        return [
            Trade(
                tx_hash="0x1", block_number=1, trader=f"0x{i:040x}", side="buy", quote_amount=10**16
            )
            for i in range(1, 20)
        ]

    async def buy(self, address: str, amount_wei: int, **kwargs):
        self.buys.append((address, amount_wei))
        return {"mode": "paper", "sent": False, "adapter": self.name}


PASS_JSON = """
{"passed": true, "wash_trading": false, "coordinated_buys": false, "dump_risk": 0.2,
 "reasons": [], "narrative_fit": 0.8, "virality": 0.75, "community": 0.7, "timing": 0.7,
 "mood": 0.7, "meme_season": true, "volume_regime": "high", "summary": "ok",
 "approve": true, "reasons_not_to_buy": []}
"""


@pytest.mark.asyncio
async def test_pipeline_buy_path_paper(good_token: Token, app_cfg: AppConfig, tmp_path: Path):
    adapter = FakeAdapter(good_token)
    logger = JsonlLogger(tmp_path / "pipeline.jsonl")
    llm = ScriptedLlmClient(default=PASS_JSON)
    pipe = Pipeline(app_cfg, adapter, llm, logger, RiskManager(app_cfg.risk), PaperExecutor(logger))
    recs = await pipe.run_once()
    assert recs and recs[0]["action"] == "buy"
    assert recs[0]["context"]["sent"] is False
    assert adapter.buys  # paper no-op still invoked
    assert llm.calls  # mocked, not real API
    models = {c["model"] for c in llm.calls}
    assert "grok-4-fast" in models or app_cfg.llm.auditor_model in models


@pytest.mark.asyncio
async def test_pipeline_skips_on_filter(good_token: Token, app_cfg: AppConfig, tmp_path: Path):
    good_token.unique_buyers = 0
    adapter = FakeAdapter(good_token)
    logger = JsonlLogger(tmp_path / "pipeline.jsonl")
    llm = ScriptedLlmClient(default=PASS_JSON)
    pipe = Pipeline(app_cfg, adapter, llm, logger)
    recs = await pipe.run_once()
    assert recs[0]["action"] == "skip"
    assert recs[0]["context"]["stage"] == "filter"
    assert not llm.calls  # never reached LLM


@pytest.mark.asyncio
async def test_pipeline_checker_fail_closed_skips(
    good_token: Token, app_cfg: AppConfig, tmp_path: Path
):
    adapter = FakeAdapter(good_token)
    logger = JsonlLogger(tmp_path / "pipeline.jsonl")

    class Mixed(ScriptedLlmClient):
        async def complete(self, *, model, messages, temperature=0.0, response_format=None):
            await super().complete(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )
            if model == "grok-4":
                return "<<<not json>>>"
            return PASS_JSON

    pipe = Pipeline(app_cfg, adapter, Mixed(), logger)
    recs = await pipe.run_once()
    assert recs[0]["action"] == "skip"
    assert recs[0]["context"]["reason"] == "checker_parse_error"
