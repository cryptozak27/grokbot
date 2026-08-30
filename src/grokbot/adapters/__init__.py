from __future__ import annotations

from grokbot.adapters.base import LaunchpadAdapter, LiveTradingDisabled, StubAdapter
from grokbot.adapters.clanker import ClankerAdapter
from grokbot.adapters.fourmeme import FourMemeAdapter
from grokbot.adapters.inkypump import InkyPumpAdapter
from grokbot.adapters.pons import PonsAdapter
from grokbot.config import AppConfig
from grokbot.rpc import JsonRpc

__all__ = [
    "LaunchpadAdapter",
    "LiveTradingDisabled",
    "StubAdapter",
    "PonsAdapter",
    "InkyPumpAdapter",
    "ClankerAdapter",
    "FourMemeAdapter",
    "build_adapters",
]


def build_adapters(cfg: AppConfig, *, enabled_only: bool = True) -> dict[str, LaunchpadAdapter]:
    adapters: dict[str, LaunchpadAdapter] = {}
    poll = {
        "lookback_blocks": cfg.poll.lookback_blocks,
        "log_chunk_blocks": cfg.poll.log_chunk_blocks,
        "min_chunk_blocks": cfg.poll.min_chunk_blocks,
        "trade_lookback_blocks": cfg.poll.trade_lookback_blocks,
    }
    paper = cfg.is_paper
    for key, lp in cfg.launchpads.items():
        if enabled_only and not lp.get("enabled", False):
            continue
        name = lp.get("name", key)
        if name == "pons":
            rpc = JsonRpc(lp["rpc"], chain_id=lp.get("chain_id"))
            adapters[name] = PonsAdapter(rpc, lp, paper=paper, poll=poll)
        elif name == "inkypump":
            rpc = JsonRpc(lp["rpc"], chain_id=lp.get("chain_id"))
            adapters[name] = InkyPumpAdapter(rpc, lp, paper=paper, poll=poll)
        elif name == "clanker":
            adapters[name] = ClankerAdapter(lp)
        elif name == "fourmeme":
            adapters[name] = FourMemeAdapter(lp)
        else:
            adapters[name] = StubAdapter(name, int(lp.get("chain_id", 0)), lp)
    return adapters
