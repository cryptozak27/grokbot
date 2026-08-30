from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grokbot.models import Token


class JsonlLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, action: str, token: Token | None = None, **context: Any) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "action": action,
            "token": token.to_dict() if token else None,
            "context": context,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        return rec
