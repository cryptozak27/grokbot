from __future__ import annotations

import asyncio
from typing import Any

from grokbot.adapters.base import LaunchpadAdapter
from grokbot.agents.auditor import AuditorAgent
from grokbot.agents.checker import CheckerAgent
from grokbot.agents.llm import LlmClient
from grokbot.agents.narrative import NarrativeAgent
from grokbot.agents.timing import TimingAgent
from grokbot.analyzer import analyze
from grokbot.config import AppConfig
from grokbot.execution.paper import PaperExecutor
from grokbot.filters import cheap_filters
from grokbot.log import JsonlLogger
from grokbot.models import Token
from grokbot.risk import RiskManager
from grokbot.scoring import compute_score


class Pipeline:
    def __init__(
        self,
        cfg: AppConfig,
        adapter: LaunchpadAdapter,
        llm: LlmClient,
        logger: JsonlLogger,
        risk: RiskManager | None = None,
        executor: PaperExecutor | None = None,
    ) -> None:
        self.cfg = cfg
        self.adapter = adapter
        self.logger = logger
        self.risk = risk or RiskManager(cfg.risk)
        self.executor = executor or PaperExecutor(logger)
        self.auditor = AuditorAgent(llm, cfg.llm)
        self.narrative = NarrativeAgent(llm, cfg.llm)
        self.timing = TimingAgent(llm, cfg.llm)
        self.checker = CheckerAgent(llm, cfg.llm)

    async def process_token(self, token: Token) -> dict[str, Any]:
        ok, reason = cheap_filters(token, self.cfg.filters)
        if not ok:
            rec = self.logger.write("skip", token, reason=reason, stage="filter")
            return rec

        analysis = await analyze(self.adapter, token)
        audit = await self.auditor.run(token, analysis)
        if not audit.passed:
            return self.logger.write(
                "skip",
                token,
                reason="auditor_reject",
                stage="auditor",
                audit=audit.to_dict(),
                analysis=analysis.to_dict(),
            )

        mood = await self.timing.run()
        narrative = await self.narrative.run(token, mood)
        score = compute_score(narrative, mood, analysis, self.cfg.scoring)
        if not score.passed:
            return self.logger.write(
                "skip",
                token,
                reason=score.skipped_reason,
                stage="score",
                score=score.to_dict(),
                narrative=narrative.to_dict(),
            )

        check = await self.checker.run(token, analysis, audit, narrative, mood, score)
        if not check.approve:
            return self.logger.write(
                "skip",
                token,
                reason="checker_veto" if not check.parse_error else "checker_parse_error",
                stage="checker",
                checker=check.to_dict(),
                score=score.to_dict(),
            )

        decision = self.risk.size_and_gate(self.cfg.risk.default_size_eth)
        if not decision.allowed:
            return self.logger.write(
                "skip", token, reason=decision.reason, stage="risk", score=score.to_dict()
            )

        rec = await self.executor.buy(
            self.adapter,
            token,
            decision.size_eth,
            reason=f"score={score.total:.3f}",
        )
        self.risk.on_fill(decision.size_eth)
        rec["score"] = score.to_dict()
        rec["checker"] = check.to_dict()
        rec["audit"] = audit.to_dict()
        rec["narrative"] = narrative.to_dict()
        rec["timing"] = mood.to_dict()
        rec["analysis"] = analysis.to_dict()
        return rec

    async def run_once(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async for token in self.adapter.stream_launches():
            results.append(await self.process_token(token))
        return results

    async def run_forever(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                self.logger.write("skip", None, reason=f"poll_error: {exc}", stage="poll")
            await asyncio.sleep(self.cfg.poll.interval_seconds)
