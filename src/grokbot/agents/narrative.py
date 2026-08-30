from __future__ import annotations

import json

from grokbot.agents.llm import LlmClient, clamp01, extract_json
from grokbot.config import LlmConfig
from grokbot.models import NarrativeScore, TimingMood, Token

SYSTEM = (
    "You score memecoin narrative. JSON only, no markdown. Keys: "
    "narrative_fit, virality, community, timing (all 0-1 floats), summary (string). "
    "Temperature is 0. Be cold: copied tickers and empty bios score near 0."
)


class NarrativeAgent:
    def __init__(self, client: LlmClient, cfg: LlmConfig) -> None:
        self.client = client
        self.cfg = cfg

    async def run(self, token: Token, mood: TimingMood | None = None) -> NarrativeScore:
        payload = {
            "name": token.name,
            "symbol": token.symbol,
            "description": token.description,
            "socials": token.socials.__dict__,
            "age_minutes": token.age_minutes,
            "unique_buyers": token.unique_buyers,
            "progress_pct": token.progress_pct,
            "market_mood": mood.to_dict() if mood else None,
        }
        try:
            raw = await self.client.complete(
                model=self.cfg.narrative_model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
        except Exception as exc:
            return NarrativeScore(parse_error=True, summary=str(exc))
        parsed = extract_json(raw)
        if not parsed:
            return NarrativeScore(parse_error=True, raw=raw, summary="narrative_parse_error")
        return NarrativeScore(
            narrative_fit=clamp01(parsed.get("narrative_fit")),
            virality=clamp01(parsed.get("virality")),
            community=clamp01(parsed.get("community")),
            timing=clamp01(parsed.get("timing")),
            summary=str(parsed.get("summary") or ""),
            raw=raw,
        )
