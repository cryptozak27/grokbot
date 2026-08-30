from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from grokbot.config import LlmConfig


class LlmClient(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict[str, str] | None = None,
    ) -> str: ...


class HttpLlmClient:
    def __init__(self, cfg: LlmConfig, client: httpx.AsyncClient | None = None) -> None:
        self.cfg = cfg
        self._client = client
        self._owns = client is None

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict[str, str] | None = None,
    ) -> str:
        if not self.cfg.api_key:
            raise RuntimeError("GROK_API_KEY is not set")
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.cfg.timeout_seconds)
        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        body = resp.json()
        return body["choices"][0]["message"]["content"]


class ScriptedLlmClient:
    """Deterministic stand-in for tests. Never touches the network."""

    def __init__(self, responses: dict[str, str] | None = None, default: str = "{}") -> None:
        self.responses = responses or {}
        self.default = default
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict[str, str] | None = None,
    ) -> str:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": response_format,
            }
        )
        role_hint = ""
        if messages:
            role_hint = messages[0].get("content", "")[:40]
        for key, value in self.responses.items():
            blob = json.dumps(messages)
            if key in blob or key in role_hint or key == model:
                return value
        return self.default


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    try:
        val = json.loads(text)
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        pass
    match = _JSON_RE.search(text)
    if not match:
        return None
    try:
        val = json.loads(match.group(0))
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        return None


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, v))
