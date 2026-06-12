from __future__ import annotations

from dharma_swarm.capital_lab.risk_governor import (
    BROKER_WRITE_AUTHORITY,
    CLEAN,
    LIVE_AUTHORITY,
    LIVE_READINESS,
    RiskGovernor,
    RiskLimits,
    run_risk_kill_switch_drills,
)


def test_governor_clean_by_default_admits_order() -> None:
    gov = RiskGovernor()
    assert gov.engaged is False
    assert gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.0) is None
    assert gov.engaged is False


def test_order_rate_control_detects_and_halts() -> None:
    gov = RiskGovernor(RiskLimits(max_orders_per_window=3, rate_window_seconds=1.0))
    # negative control: 3 within window admit cleanly
    assert gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.0) is None
    assert gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.1) is None
    assert gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.2) is None
    # 4th in window trips
    breach = gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.3)
    assert breach is not None and breach.control == "order_rate"
    assert gov.engaged is True
    # HALT enforcement: a subsequent (otherwise fine) order is blocked
    halt = gov.pre_trade_check("MSFT", "buy", 1.0, 100.0, now=5.0)
    assert halt is not None and halt.control == "governor_engaged"


def test_position_limit_detects_and_halts() -> None:
    gov = RiskGovernor(RiskLimits(max_position_per_symbol=10.0))
    gov.record_fill("AAPL", "buy", 8.0)
    assert gov.pre_trade_check("AAPL", "buy", 2.0, 100.0, now=0.0) is None  # -> 10, ok
    gov.record_fill("AAPL", "buy", 2.0)
    breach = gov.pre_trade_check("AAPL", "buy", 5.0, 100.0, now=1.0)        # -> 15 > 10
    assert breach is not None and breach.control == "position_limit"
    assert gov.engaged is True


def test_exposure_limit_uses_notional_price() -> None:
    gov = RiskGovernor(RiskLimits(max_gross_exposure=1000.0))
    # 5 shares * $100 = $500 gross, ok
    assert gov.pre_trade_check("AAPL", "buy", 5.0, 100.0, now=0.0) is None
    gov.record_fill("AAPL", "buy", 5.0)
    # +6 shares * $100 -> projected 11 * 100 = $1100 > $1000
    breach = gov.pre_trade_check("AAPL", "buy", 6.0, 100.0, now=1.0)
    assert breach is not None and breach.control == "exposure"


def test_heartbeat_staleness_detects_and_halts() -> None:
    gov = RiskGovernor(RiskLimits(heartbeat_timeout_seconds=5.0))
    gov.heartbeat(at=0.0)
    assert gov.check_environment(now=1.0) is None       # fresh
    breach = gov.check_environment(now=10.0)             # stale
    assert breach is not None and breach.control == "heartbeat"
    assert gov.engaged is True
    assert gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=10.0) is not None


def test_drawdown_detects_and_halts() -> None:
    gov = RiskGovernor(RiskLimits(max_drawdown_fraction=0.10))
    gov.update_equity(1_000_000.0)
    gov.update_equity(980_000.0)
    assert gov.check_environment(now=1.0) is None        # 2% < 10%
    gov.update_equity(850_000.0)
    breach = gov.check_environment(now=2.0)              # 15% > 10%
    assert breach is not None and breach.control == "max_loss"
    assert gov.engaged is True


def test_operator_reset_clears_engagement() -> None:
    gov = RiskGovernor(RiskLimits(max_orders_per_window=1))
    gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.0)
    gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.1)  # trips
    assert gov.engaged is True
    gov.reset("operator cleared after investigation")
    assert gov.engaged is False
    assert gov.pre_trade_check("MSFT", "buy", 1.0, 100.0, now=10.0) is None


def test_kill_switch_drills_are_real_not_hardcoded() -> None:
    """The anti-theater guarantee: every drill must pass via a real detection
    (condition_detected) AND a clean negative control AND enforced halt."""
    drills = run_risk_kill_switch_drills()
    assert set(drills) == {
        "heartbeat_kill_switch",
        "stale_data_kill_switch",
        "max_loss_or_drawdown_kill_switch",
        "order_rate_or_exposure_kill_switch",
    }
    for name, receipt in drills.items():
        assert receipt["negative_control_clean"] is True, name
        assert receipt["condition_detected"] is True, name
        assert receipt["halt_enforced"] is True, name
        assert receipt["passed"] is True, name
        # the observed value genuinely exceeds the limit (not a literal)
        assert receipt["observed"] is not None and receipt["limit"] is not None, name
        assert float(receipt["observed"]) > float(receipt["limit"]), name
        # authority invariants preserved
        assert receipt["live_readiness"] == LIVE_READINESS
        assert receipt["live_authority"] is LIVE_AUTHORITY
        assert receipt["broker_write_authority"] is BROKER_WRITE_AUTHORITY
        assert receipt["clean"] is CLEAN
