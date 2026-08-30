from __future__ import annotations

import json

from grokbot.agents.llm import LlmClient, extract_json
from grokbot.config import LlmConfig
from grokbot.models import (
    Analysis,
    AuditResult,
    CheckerResult,
    NarrativeScore,
    ScoreBreakdown,
    TimingMood,
    Token,
)

SYSTEM = (
    "You are an adversarial risk checker. You may ONLY look for reasons NOT to buy. "
    "JSON only: approve (bool), reasons_not_to_buy (string array). "
    "approve false is the normal outcome. On any doubt, approve false."
)


class CheckerAgent:
    def __init__(self, client: LlmClient, cfg: LlmConfig) -> None:
        self.client = client
        self.cfg = cfg

    async def run(
        self,
        token: Token,
        analysis: Analysis,
        audit: AuditResult,
        narrative: NarrativeScore,
        timing: TimingMood,
        score: ScoreBreakdown,
    ) -> CheckerResult:
        payload = {
            "token": token.to_dict(),
            "analysis": analysis.to_dict(),
            "audit": audit.to_dict(),
            "narrative": narrative.to_dict(),
            "timing": timing.to_dict(),
            "score": score.to_dict(),
        }
        try:
            raw = await self.client.complete(
                model=self.cfg.checker_model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
        except Exception as exc:
            return CheckerResult(
                approve=False, reasons_not_to_buy=[f"checker_error: {exc}"], parse_error=True
            )
        parsed = extract_json(raw)
        if not parsed:
            return CheckerResult(
                approve=False,
                reasons_not_to_buy=["checker_parse_error"],
                raw=raw,
                parse_error=True,
            )
        approve = bool(parsed.get("approve"))
        reasons = list(parsed.get("reasons_not_to_buy") or parsed.get("reasons") or [])
        if reasons and parsed.get("approve") is None:
            approve = False
        return CheckerResult(approve=approve, reasons_not_to_buy=reasons, raw=raw)
