from __future__ import annotations

from dataclasses import dataclass

from grokbot.config import RiskConfig


@dataclass
class RiskState:
    day_key: str = ""
    realized_pnl_eth: float = 0.0
    trades_today: int = 0
    open_positions: int = 0
    open_notional_eth: float = 0.0


@dataclass
class RiskDecision:
    allowed: bool
    size_eth: float
    reason: str


class RiskManager:
    def __init__(self, cfg: RiskConfig, state: RiskState | None = None) -> None:
        self.cfg = cfg
        self.state = state or RiskState()

    def size_and_gate(self, requested_eth: float | None = None) -> RiskDecision:
        cfg = self.cfg
        if self.state.trades_today >= cfg.max_trades_per_day:
            return RiskDecision(False, 0.0, "risk:max_trades_per_day")
        if self.state.open_positions >= cfg.max_open_positions:
            return RiskDecision(False, 0.0, "risk:max_open_positions")
        if self.state.realized_pnl_eth <= -abs(cfg.daily_loss_limit_eth):
            return RiskDecision(False, 0.0, "risk:daily_loss_limit")

        size = requested_eth if requested_eth is not None else cfg.default_size_eth
        size = min(size, cfg.max_position_eth)
        remaining_loss = cfg.daily_loss_limit_eth + self.state.realized_pnl_eth
        # realized_pnl is negative when losing
        loss_used = max(0.0, -self.state.realized_pnl_eth)
        if cfg.daily_loss_limit_eth > 0:
            used_pct = loss_used / cfg.daily_loss_limit_eth
            if used_pct >= cfg.shrink_start_pct:
                shrink = max(0.15, 1.0 - used_pct)
                size *= shrink
        if remaining_loss <= 0:
            return RiskDecision(False, 0.0, "risk:daily_loss_limit")
        size = min(size, remaining_loss, cfg.max_position_eth)
        if self.state.open_positions >= max(1, cfg.max_open_positions - 1):
            size *= 0.5
        size = max(0.0, size)
        if size <= 0:
            return RiskDecision(False, 0.0, "risk:size_zero")
        return RiskDecision(True, size, "ok")

    def on_fill(self, size_eth: float) -> None:
        self.state.trades_today += 1
        self.state.open_positions += 1
        self.state.open_notional_eth += size_eth

    def on_close(self, size_eth: float, pnl_eth: float) -> None:
        self.state.open_positions = max(0, self.state.open_positions - 1)
        self.state.open_notional_eth = max(0.0, self.state.open_notional_eth - size_eth)
        self.state.realized_pnl_eth += pnl_eth
