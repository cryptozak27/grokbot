from grokbot.config import RiskConfig
from grokbot.risk import RiskManager, RiskState


def test_caps_trades_per_day():
    rm = RiskManager(RiskConfig(max_trades_per_day=10), RiskState(trades_today=10))
    d = rm.size_and_gate(0.02)
    assert not d.allowed and "max_trades" in d.reason


def test_caps_open_positions():
    rm = RiskManager(RiskConfig(max_open_positions=3), RiskState(open_positions=3))
    d = rm.size_and_gate(0.02)
    assert not d.allowed and "open" in d.reason


def test_daily_loss_limit():
    rm = RiskManager(RiskConfig(daily_loss_limit_eth=0.15), RiskState(realized_pnl_eth=-0.15))
    d = rm.size_and_gate(0.02)
    assert not d.allowed and "daily_loss" in d.reason


def test_shrinks_near_loss_limit():
    cfg = RiskConfig(
        max_position_eth=0.05,
        default_size_eth=0.05,
        daily_loss_limit_eth=0.10,
        shrink_start_pct=0.70,
    )
    rm = RiskManager(cfg, RiskState(realized_pnl_eth=-0.08))  # 80% of limit
    d = rm.size_and_gate(0.05)
    assert d.allowed
    assert d.size_eth < 0.05


def test_max_position_cap():
    rm = RiskManager(RiskConfig(max_position_eth=0.05, default_size_eth=0.02))
    d = rm.size_and_gate(1.0)
    assert d.allowed and d.size_eth == 0.05


def test_on_fill_and_close():
    rm = RiskManager(RiskConfig())
    rm.on_fill(0.02)
    assert rm.state.trades_today == 1 and rm.state.open_positions == 1
    rm.on_close(0.02, -0.01)
    assert rm.state.open_positions == 0
    assert rm.state.realized_pnl_eth == -0.01
