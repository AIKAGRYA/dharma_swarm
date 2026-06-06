"""Real-time risk governor for capital_lab execution.

Unlike a drill that asserts a boolean, every control here DETECTS an adverse
condition from observed state and HALTS: once a control trips, the governor is
engaged and blocks subsequent orders until an explicit operator reset. This is
the enforcement the broker-paper membrane delegates its pre-trade and
kill-switch decisions to.

A drill is therefore a real experiment: inject the adverse condition, prove the
detector fires AND the next order is blocked, and prove a clean negative control
does NOT fire. There are no hard-coded ``engaged=True`` literals.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Deque

# Mirror of the membrane's hard authority invariants (kept local to avoid a
# circular import; the membrane imports this module, not the reverse).
LIVE_READINESS = 0
LIVE_AUTHORITY = False
BROKER_WRITE_AUTHORITY = False
CLEAN = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_payload(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RiskLimits:
    """Operator-configured risk envelope. Defaults are deliberately permissive
    so the fixture membrane does not surprise-block; real limits are set per
    fund before any live authority is requested."""

    max_orders_per_window: int = 10_000
    rate_window_seconds: float = 1.0
    max_position_per_symbol: float = 1_000_000.0
    max_gross_exposure: float = 1_000_000_000.0
    max_drawdown_fraction: float = 0.50
    heartbeat_timeout_seconds: float = 60.0
    market_data_staleness_seconds: float = 60.0


@dataclass(frozen=True)
class RiskBreach:
    control: str
    reason: str
    observed: float
    limit: float
    at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RiskHalt(Exception):
    """Raised when an order is refused because a risk control tripped."""

    def __init__(self, breach: RiskBreach) -> None:
        super().__init__(f"{breach.control}: {breach.reason}")
        self.breach = breach


class RiskGovernor:
    """Detect-and-halt risk controls for the execution membrane.

    Numeric ``now`` arguments are epoch-like seconds; an injectable ``clock``
    keeps drills and tests deterministic. Positions update on fill, not on
    submit; pre-trade checks evaluate the *projected* position/exposure.
    """

    def __init__(
        self,
        limits: RiskLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limits = limits or RiskLimits()
        self._clock = clock
        self._engaged = False
        self._breaches: list[RiskBreach] = []
        self._order_times: Deque[float] = deque()
        self._positions: dict[str, float] = {}
        self._high_water_equity: float | None = None
        self._last_equity: float | None = None
        self._last_heartbeat: float | None = None
        self._last_market_data: float | None = None

    # -- state observers ----------------------------------------------------
    @property
    def engaged(self) -> bool:
        return self._engaged

    @property
    def breaches(self) -> list[RiskBreach]:
        return list(self._breaches)

    def heartbeat(self, at: float) -> None:
        self._last_heartbeat = at

    def market_data_tick(self, at: float) -> None:
        self._last_market_data = at

    def update_equity(self, equity: float) -> None:
        self._last_equity = equity
        if self._high_water_equity is None or equity > self._high_water_equity:
            self._high_water_equity = equity

    def record_fill(self, symbol: str, side: str, quantity: float) -> None:
        signed = quantity if side.strip().lower() == "buy" else -quantity
        self._positions[symbol.strip().upper()] = (
            self._positions.get(symbol.strip().upper(), 0.0) + signed
        )

    # -- enforcement --------------------------------------------------------
    def _trip(self, breach: RiskBreach) -> RiskBreach:
        self._engaged = True
        self._breaches.append(breach)
        return breach

    def trip(self, control: str, reason: str) -> RiskBreach:
        """External trip (e.g. a reconciliation mismatch) that engages the
        governor so subsequent pre-trade checks block."""
        return self._trip(RiskBreach(control, reason, 1.0, 0.0, _utc_now()))

    def reset(self, reason: str) -> None:
        """Operator action: clear an engaged governor. Does not clear positions."""
        self._engaged = False
        self._breaches.append(
            RiskBreach("operator_reset", reason, 0.0, 0.0, _utc_now())
        )

    def check_environment(self, now: float) -> RiskBreach | None:
        """Time/state-based controls: heartbeat staleness, market-data
        staleness, drawdown. Trips the governor on first breach."""
        if self._last_heartbeat is not None:
            age = now - self._last_heartbeat
            if age > self.limits.heartbeat_timeout_seconds:
                return self._trip(
                    RiskBreach("heartbeat", "heartbeat_missing", age,
                               self.limits.heartbeat_timeout_seconds, _utc_now())
                )
        if self._last_market_data is not None:
            age = now - self._last_market_data
            if age > self.limits.market_data_staleness_seconds:
                return self._trip(
                    RiskBreach("stale_data", "market_data_stale", age,
                               self.limits.market_data_staleness_seconds, _utc_now())
                )
        if self._high_water_equity and self._last_equity is not None:
            drawdown = (self._high_water_equity - self._last_equity) / self._high_water_equity
            if drawdown > self.limits.max_drawdown_fraction:
                return self._trip(
                    RiskBreach("max_loss", "max_drawdown_exceeded", drawdown,
                               self.limits.max_drawdown_fraction, _utc_now())
                )
        return None

    def pre_trade_check(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None,
        now: float | None = None,
    ) -> RiskBreach | None:
        """Evaluate an order intent against every control. Returns the first
        breach (and latches engaged), or None if the order is admissible. On
        admission, the order is counted toward the rate window."""
        now = self._clock() if now is None else now
        if self._engaged:
            return RiskBreach("governor_engaged", "governor_already_engaged", 1.0, 0.0, _utc_now())

        env = self.check_environment(now)
        if env is not None:
            return env

        symbol = symbol.strip().upper()
        signed = quantity if side.strip().lower() == "buy" else -quantity

        # order-rate control (rolling window)
        window_start = now - self.limits.rate_window_seconds
        recent = [t for t in self._order_times if t >= window_start]
        if len(recent) + 1 > self.limits.max_orders_per_window:
            return self._trip(
                RiskBreach("order_rate", "order_rate_limit_exceeded", float(len(recent) + 1),
                           float(self.limits.max_orders_per_window), _utc_now())
            )

        # per-symbol position control (projected)
        projected = self._positions.get(symbol, 0.0) + signed
        if abs(projected) > self.limits.max_position_per_symbol:
            return self._trip(
                RiskBreach("position_limit", "max_position_per_symbol_exceeded", abs(projected),
                           self.limits.max_position_per_symbol, _utc_now())
            )

        # gross-exposure control (projected, notional if price known else qty)
        unit = price if price is not None else 1.0
        projected_positions = dict(self._positions)
        projected_positions[symbol] = projected
        gross = sum(abs(q) * unit for q in projected_positions.values())
        if gross > self.limits.max_gross_exposure:
            return self._trip(
                RiskBreach("exposure", "max_gross_exposure_exceeded", gross,
                           self.limits.max_gross_exposure, _utc_now())
            )

        self._order_times.append(now)
        self._order_times = deque(t for t in self._order_times if t >= window_start)
        return None

    def receipt(self) -> dict[str, Any]:
        payload = {
            "schema_version": "capital_lab.risk_governor.v1",
            "generated_at": _utc_now(),
            "engaged": self._engaged,
            "breach_count": len(self._breaches),
            "breaches": [b.to_dict() for b in self._breaches],
            "positions": dict(self._positions),
            "limits": asdict(self.limits),
            "live_readiness": LIVE_READINESS,
            "live_authority": LIVE_AUTHORITY,
            "broker_write_authority": BROKER_WRITE_AUTHORITY,
            "clean": CLEAN,
        }
        payload["self_hash"] = _sha256_payload(payload)
        return payload


def _drill_heartbeat() -> dict[str, Any]:
    limits = RiskLimits(heartbeat_timeout_seconds=5.0)
    gov = RiskGovernor(limits)
    gov.heartbeat(at=0.0)
    negative = gov.check_environment(now=1.0)          # age 1 < 5 -> clean
    positive = gov.check_environment(now=10.0)          # age 10 > 5 -> trip
    halt = gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=10.0)
    return _drill_receipt("heartbeat_kill_switch", "heartbeat_missing",
                          negative, positive, halt, gov)


def _drill_stale_data() -> dict[str, Any]:
    limits = RiskLimits(market_data_staleness_seconds=5.0)
    gov = RiskGovernor(limits)
    gov.market_data_tick(at=0.0)
    negative = gov.check_environment(now=2.0)
    positive = gov.check_environment(now=20.0)
    halt = gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=20.0)
    return _drill_receipt("stale_data_kill_switch", "market_data_stale",
                          negative, positive, halt, gov)


def _drill_max_loss() -> dict[str, Any]:
    limits = RiskLimits(max_drawdown_fraction=0.10)
    gov = RiskGovernor(limits)
    gov.update_equity(1_000_000.0)
    gov.update_equity(980_000.0)
    negative = gov.check_environment(now=1.0)           # 2% drawdown < 10% -> clean
    gov.update_equity(850_000.0)                         # 15% drawdown > 10%
    positive = gov.check_environment(now=2.0)
    halt = gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=2.0)
    return _drill_receipt("max_loss_or_drawdown_kill_switch", "max_drawdown_exceeded",
                          negative, positive, halt, gov)


def _drill_order_rate() -> dict[str, Any]:
    limits = RiskLimits(max_orders_per_window=3, rate_window_seconds=1.0)
    gov = RiskGovernor(limits)
    negative = None
    for i in range(3):                                   # 3 within limit -> clean
        b = gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.1 * i)
        negative = negative or b
    positive = gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.3)  # 4th -> trip
    halt = gov.pre_trade_check("AAPL", "buy", 1.0, 100.0, now=0.4)
    return _drill_receipt("order_rate_or_exposure_kill_switch", "order_rate_limit_exceeded",
                          negative, positive, halt, gov)


def _drill_receipt(
    name: str,
    expected_reason: str,
    negative: RiskBreach | None,
    positive: RiskBreach | None,
    halt: RiskBreach | None,
    gov: RiskGovernor,
) -> dict[str, Any]:
    negative_control_clean = negative is None
    detected = positive is not None and positive.reason == expected_reason
    halt_enforced = halt is not None and gov.engaged
    passed = negative_control_clean and detected and halt_enforced
    receipt = {
        "schema_version": "goal_b.kill_switch_drill.v1",
        "drill": name,
        "generated_at": _utc_now(),
        "expected_reason": expected_reason,
        "negative_control_clean": negative_control_clean,
        "condition_detected": detected,
        "halt_enforced": halt_enforced,
        "passed": passed,
        "kill_switch_engaged": gov.engaged,
        "observed": positive.observed if positive else None,
        "limit": positive.limit if positive else None,
        "live_readiness": LIVE_READINESS,
        "live_authority": LIVE_AUTHORITY,
        "broker_write_authority": BROKER_WRITE_AUTHORITY,
        "clean": CLEAN,
    }
    receipt["self_hash"] = _sha256_payload(receipt)
    return receipt


def run_risk_kill_switch_drills() -> dict[str, dict[str, Any]]:
    """Run the four environmental kill-switch drills as real experiments.

    Each drill injects an adverse condition, proves the detector fires and the
    next order is blocked, and proves a clean negative control does not fire.
    Every boolean is computed by the governor, never hard-coded."""
    return {
        "heartbeat_kill_switch": _drill_heartbeat(),
        "stale_data_kill_switch": _drill_stale_data(),
        "max_loss_or_drawdown_kill_switch": _drill_max_loss(),
        "order_rate_or_exposure_kill_switch": _drill_order_rate(),
    }
