from __future__ import annotations

import json

from grokbot.agents.llm import LlmClient, clamp01, extract_json
from grokbot.config import LlmConfig
from grokbot.models import Analysis, AuditResult, Token

SYSTEM = (
    "You audit memecoin launch tape for manipulation. "
    "Return JSON only with keys: passed (bool), wash_trading (bool), "
    "coordinated_buys (bool), dump_risk (0-1 float), reasons (string array). "
    "Be pessimistic. Coordinated same-size buys, wash loops, and creator dumps fail."
)


class AuditorAgent:
    def __init__(self, client: LlmClient, cfg: LlmConfig) -> None:
        self.client = client
        self.cfg = cfg

    async def run(self, token: Token, analysis: Analysis) -> AuditResult:
        payload = {
            "token": {
                "address": token.address,
                "name": token.name,
                "symbol": token.symbol,
                "creator": token.creator,
                "unique_buyers": token.unique_buyers,
                "progress_pct": token.progress_pct,
            },
            "analysis": analysis.to_dict(),
            "trades": [
                {
                    "trader": t.trader,
                    "side": t.side,
                    "quote": t.quote_amount,
                    "token": t.token_amount,
                }
                for t in analysis.trades[:80]
            ],
            "holders": [{"address": h.address, "pct": h.pct} for h in analysis.holders[:20]],
        }
        try:
            raw = await self.client.complete(
                model=self.cfg.auditor_model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
        except Exception as exc:  # parse/transport error = pessimistic reject
            return AuditResult(
                passed=False,
                dump_risk=1.0,
                reasons=[f"auditor_error: {exc}"],
                parse_error=True,
            )
        parsed = extract_json(raw)
        if not parsed:
            return AuditResult(
                passed=False,
                dump_risk=1.0,
                reasons=["auditor_parse_error"],
                raw=raw,
                parse_error=True,
            )
        passed = (
            bool(parsed.get("passed"))
            and not parsed.get("wash_trading")
            and not parsed.get("coordinated_buys")
        )
        return AuditResult(
            passed=passed,
            wash_trading=bool(parsed.get("wash_trading")),
            coordinated_buys=bool(parsed.get("coordinated_buys")),
            dump_risk=clamp01(parsed.get("dump_risk"), 1.0),
            reasons=list(parsed.get("reasons") or []),
            raw=raw,
        )
