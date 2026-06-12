from __future__ import annotations

import pytest

from dharma_swarm.capital_lab.contracts import (
    Direction,
    Insight,
    Order,
    OrderType,
    PortfolioTarget,
    RiskAdjustedTarget,
    Side,
    TradingState,
    Universe,
)


def test_universe_requires_unique_nonempty_ids() -> None:
    u = Universe(as_of="2026-06-06T00:00:00Z", security_ids=("AAPL", "MSFT"))
    assert len(u.content_hash) == 64
    # order-independent hash
    assert u.content_hash == Universe(
        as_of="2026-06-06T00:00:00Z", security_ids=("MSFT", "AAPL")
    ).content_hash
    with pytest.raises(ValueError):
        Universe(as_of="t", security_ids=())
    with pytest.raises(ValueError):
        Universe(as_of="t", security_ids=("AAPL", "AAPL"))


def test_insight_validation_and_actionability() -> None:
    up = Insight("AAPL", Direction.UP, magnitude=0.8, confidence=0.7,
                 horizon_days=5, source_agent="glm-5")
    assert up.is_actionable is True
    flat = Insight("AAPL", Direction.FLAT, magnitude=0.0, confidence=0.9,
                   horizon_days=5, source_agent="glm-5")
    assert flat.is_actionable is False  # explicit abstain is first-class
    assert up.to_dict()["direction"] == "up"
    for bad in (
        dict(magnitude=-0.1, confidence=0.5),
        dict(magnitude=0.5, confidence=1.5),
        dict(magnitude=0.5, confidence=0.5, horizon_days=0),
    ):
        kw = dict(magnitude=0.5, confidence=0.5, horizon_days=5)
        kw.update(bad)
        with pytest.raises(ValueError):
            Insight("AAPL", Direction.UP, source_agent="x", **kw)


def test_portfolio_target_weight_bounds() -> None:
    assert PortfolioTarget("AAPL", 0.25).target_weight == 0.25
    assert PortfolioTarget("AAPL", -0.5).target_weight == -0.5
    with pytest.raises(ValueError):
        PortfolioTarget("AAPL", 1.5)


def test_risk_adjusted_target_cannot_amplify() -> None:
    # risk may reduce, never amplify
    rat = RiskAdjustedTarget("AAPL", requested_weight=0.5, approved_weight=0.3,
                             approved=True, trading_state=TradingState.ACTIVE,
                             clamps=("exposure",))
    assert rat.to_dict()["trading_state"] == "active"
    with pytest.raises(ValueError):
        RiskAdjustedTarget("AAPL", requested_weight=0.2, approved_weight=0.5,
                           approved=True, trading_state=TradingState.ACTIVE)
    # a blocked target must carry zero approved weight
    with pytest.raises(ValueError):
        RiskAdjustedTarget("AAPL", requested_weight=0.5, approved_weight=0.5,
                           approved=False, trading_state=TradingState.HALTED)
    blocked = RiskAdjustedTarget("AAPL", requested_weight=0.5, approved_weight=0.0,
                                 approved=False, trading_state=TradingState.HALTED,
                                 breaches=("reconciliation",))
    assert blocked.approved is False


def test_order_validation() -> None:
    o = Order("cid-1", "AAPL", Side.BUY, OrderType.LIMIT, 10.0, limit_price=100.0)
    assert o.to_dict()["side"] == "buy"
    with pytest.raises(ValueError):
        Order("", "AAPL", Side.BUY, OrderType.MARKET, 1.0)
    with pytest.raises(ValueError):
        Order("cid", "AAPL", Side.BUY, OrderType.MARKET, 0.0)
    with pytest.raises(ValueError):
        Order("cid", "AAPL", Side.BUY, OrderType.LIMIT, 1.0)  # limit needs price


def test_pipeline_objects_are_frozen() -> None:
    u = Universe(as_of="t", security_ids=("AAPL",))
    with pytest.raises(Exception):
        u.as_of = "other"  # type: ignore[misc]
