from __future__ import annotations

import json
import time

from grokbot.agents.llm import LlmClient, clamp01, extract_json
from grokbot.config import LlmConfig
from grokbot.models import TimingMood

SYSTEM = (
    "You are a crypto market-timing desk. Not per-token. JSON only with keys: "
    "mood (0-1), meme_season (bool), volume_regime (low|normal|high), summary (string)."
)


class TimingAgent:
    def __init__(self, client: LlmClient, cfg: LlmConfig) -> None:
        self.client = client
        self.cfg = cfg
        self._cached: TimingMood | None = None
        self._cached_at: float = 0.0

    async def run(self, *, now: float | None = None) -> TimingMood:
        now = time.time() if now is None else now
        ttl = max(900, min(1800, int(self.cfg.timing_cache_seconds)))
        if self._cached is not None and (now - self._cached_at) < ttl:
            mood = TimingMood(**{**self._cached.to_dict(), "cached": True})
            return mood
        try:
            raw = await self.client.complete(
                model=self.cfg.timing_model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": json.dumps({"ask": "current meme-season / volume mood"}),
                    },
                ],
            )
        except Exception as exc:
            mood = TimingMood(parse_error=True, summary=str(exc), mood=0.3)
            self._cached, self._cached_at = mood, now
            return mood
        parsed = extract_json(raw)
        if not parsed:
            mood = TimingMood(parse_error=True, raw=raw, mood=0.3, summary="timing_parse_error")
        else:
            mood = TimingMood(
                mood=clamp01(parsed.get("mood"), 0.5),
                meme_season=bool(parsed.get("meme_season")),
                volume_regime=str(parsed.get("volume_regime") or "unknown"),
                summary=str(parsed.get("summary") or ""),
                raw=raw,
            )
        self._cached, self._cached_at = mood, now
        return mood
