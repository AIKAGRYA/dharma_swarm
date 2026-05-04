"""Ginko Paper Trading -- simulated portfolio for strategy validation.

Paper trading with $100K initial capital. Tracks positions, P&L,
Sharpe ratio, max drawdown. Enforces telos gates:
  - AHIMSA: max 5% per position
  - REVERSIBILITY: every position requires stop_loss

Persistence:
  ~/.dharma/ginko/paper_portfolio.json  (portfolio state)
  ~/.dharma/ginko/trades.jsonl          (closed trade log)
  ~/.dharma/ginko/equity_curve.jsonl    (daily snapshots)
  ~/.dharma/ginko/CIRCUIT_BREAKER       (halt flag - requires manual removal)
"""

from __future__ import annotations

import json
import logging
import math
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GINKO_DIR = Path(os.getenv("DHARMA_HOME", Path.home() / ".dharma")) / "ginko"
CIRCUIT_BREAKER_FLAG = GINKO_DIR / "CIRCUIT_BREAKER"

AHIMSA_MAX_POSITION_PCT = 0.05  # 5% of portfolio value per position


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class Position:
    """An open paper trading position."""

    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    entry_time: str
    quantity: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Position:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Trade:
    """A closed (realized) paper trade."""

    id: str  # uuid hex
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    quantity: float
    realized_pnl: float
    signal_source: str = ""
    brier_prediction_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trade:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ExecutionError:
    """Record of an execution error."""

    timestamp: str
    error_type: str
    message: str
    symbol: str = ""
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionError:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Standalone analytics
# ---------------------------------------------------------------------------


def compute_sharpe(daily_returns: list[float], risk_free_rate: float = 0.05) -> float:
    """Compute annualized Sharpe ratio.

    Sharpe = (mean_return - rf_daily) / std_return * sqrt(252)

    Args:
        daily_returns: List of daily fractional returns (e.g. 0.01 = 1%).
        risk_free_rate: Annualized risk-free rate (default 5%).

    Returns:
        Annualized Sharpe ratio, or 0.0 if insufficient data or zero std.
    """
    if len(daily_returns) < 2:
        return 0.0

    rf_daily = risk_free_rate / 252.0
    mean_ret = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std_ret = math.sqrt(variance)

    if std_ret == 0.0:
        return 0.0

    return (mean_ret - rf_daily) / std_ret * math.sqrt(252)


def compute_max_drawdown(equity_curve: list[float]) -> float:
    """Compute maximum drawdown from peak.

    Args:
        equity_curve: List of portfolio equity values over time.

    Returns:
        Maximum drawdown as a fraction (e.g. 0.15 = 15% drawdown).
        Returns 0.0 if fewer than 2 data points or no drawdown.
    """
    if len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


# ---------------------------------------------------------------------------
# PaperPortfolio
# ---------------------------------------------------------------------------


class PaperPortfolio:
    """Simulated paper trading portfolio with telos gate enforcement.

    Tracks open positions, closed trades, cash balance, and equity curve.
    Persists state to disk after every mutation.

    Telos gates:
        AHIMSA -- no single position may exceed 5% of total portfolio value.
        REVERSIBILITY -- every position must have a stop_loss > 0.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        portfolio_path: Path | None = None,
        daily_loss_limit: float = 0.05,   # 5% daily loss limit (default)
        position_size_limit: float = 0.05,  # 5% per position (default, mirrors AHIMSA)
    ) -> None:
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.execution_errors: list[ExecutionError] = []

        # limits
        self.daily_loss_limit = daily_loss_limit
        self.position_size_limit = position_size_limit

        self._portfolio_path = portfolio_path or GINKO_DIR / "paper_portfolio.json"
        if portfolio_path:
            parent = portfolio_path.parent
        else:
            parent = GINKO_DIR
        self._trades_path = parent / "trades.jsonl"
        self._equity_path = parent / "equity_curve.jsonl"
        self._errors_path = parent / "execution_errors.jsonl"

        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_position(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        stop_loss: float | None,
        take_profit: float = 0.0,
        signal_source: str = "",
        brier_prediction_id: str = "",
    ) -> Position:
        """Open a paper position.

        AHIMSA gate: position value must be <= 5% of total portfolio value.
        REVERSIBILITY gate: stop_loss must be > 0.
        """
        if direction not in ("long", "short"):
            raise ValueError(f"direction must be 'long' or 'short', got '{direction}'")
        if quantity <= 0:
            raise ValueError(f"quantity must be > 0, got {quantity}")
        if price <= 0:
            raise ValueError(f"price must be > 0, got {price}")

        if stop_loss is None or stop_loss <= 0:
            logger.warning(
                "REVERSIBILITY GATE: stop_loss required for %s (got %s)",
                symbol,
                stop_loss,
            )
            raise ValueError(
                f"REVERSIBILITY GATE: stop_loss required for {symbol} (must be > 0)"
            )

        if symbol in self.positions:
            raise ValueError(
                f"Position already open for {symbol}. Close it before opening a new one."
            )

        position_value = price * quantity
        portfolio_value = self._compute_portfolio_value()
        base_value = max(portfolio_value, self.initial_capital * 0.01)
        position_pct = position_value / base_value

        # Use the configurable limit if set, otherwise default constant
        limit = self.position_size_limit if hasattr(self, "position_size_limit") else AHIMSA_MAX_POSITION_PCT
        if position_pct > limit:
            logger.warning(
                "AHIMSA GATE: %s position %.1f%% exceeds limit "
                "(value=$%.2f, portfolio=$%.2f)",
                symbol,
                position_pct * 100,
                position_value,
                base_value,
            )
            raise ValueError(
                f"AHIMSA GATE: position {position_pct:.1%} exceeds {limit:.0%} limit"
            )

        cost = position_value
        if cost > self.cash:
            raise ValueError(f"Insufficient cash: need ${cost:,.2f}, have ${self.cash:,.2f}")

        now = _utc_now().isoformat()
        pos = Position(
            symbol=symbol,
            direction=direction,
            entry_price=price,
            entry_time=now,
            quantity=quantity,
            current_price=price,
            unrealized_pnl=0.0,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        self.cash -= cost
        self.positions[symbol] = pos
        self._save()
        logger.info(
            "Opened %s %s: %.4f @ $%.2f (stop=%.2f, tp=%.2f)",
            direction,
            symbol,
            quantity,
            price,
            stop_loss,
            take_profit,
        )
        return pos

    def close_position(self, symbol: str, price: float, reason: str = "") -> Trade:
        """Close an existing position at given price."""
        if symbol not in self.positions:
            raise ValueError(f"No open position for {symbol}")
        if price <= 0:
            raise ValueError(f"price must be > 0, got {price}")

        pos = self.positions[symbol]
        if pos.direction == "long":
            realized_pnl = (price - pos.entry_price) * pos.quantity
        else:
            realized_pnl = (pos.entry_price - price) * pos.quantity

        original_cost = pos.entry_price * pos.quantity
        self.cash += original_cost + realized_pnl

        now = _utc_now().isoformat()
        trade = Trade(
            id=uuid.uuid4().hex,
            symbol=symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=price,
            entry_time=pos.entry_time,
            exit_time=now,
            quantity=pos.quantity,
            realized_pnl=realized_pnl,
        )
        del self.positions[symbol]
        self.trades.append(trade)

        self._save_trade(trade)
        self._save()
        logger.info(
            "Closed %s %s @ $%.2f -> P&L: $%.2f (%s)",
            trade.direction,
            symbol,
            price,
            realized_pnl,
            reason or "manual",
        )
        return trade

    def mark_to_market(self, prices: dict[str, float]) -> dict[str, Any]:
        """Update current prices and unrealized P&L for all positions."""
        position_details: list[dict[str, Any]] = []

        for symbol, pos in self.positions.items():
            if symbol in prices:
                pos.current_price = prices[symbol]

            if pos.direction == "long":
                pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.quantity
            else:
                pos.unrealized_pnl = (pos.entry_price - pos.current_price) * pos.quantity

            position_details.append({
                "symbol": symbol,
                "direction": pos.direction,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "quantity": pos.quantity,
                "unrealized_pnl": round(pos.unrealized_pnl, 2),
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
            })

        positions_value = self._compute_positions_value()
        total_value = self.cash + positions_value

        self.daily_equity_snapshot()

        self._save()
        return {
            "total_value": round(total_value, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(positions_value, 2),
            "unrealized_pnl": round(sum(p.unrealized_pnl for p in self.positions.values()), 2),
            "positions": position_details,
        }

    def daily_equity_snapshot(self) -> dict[str, Any]:
        """Append a portfolio equity snapshot to ``equity_curve.jsonl``."""
        positions_value = self._compute_positions_value()
        total_value = self.cash + positions_value
        prior_entries = self._load_equity_curve()
        prior_value = (
            float(prior_entries[-1].get("total_value", self.initial_capital))
            if prior_entries
            else self.initial_capital
        )
        daily_return = (
            (total_value / prior_value) - 1.0
            if prior_value
            else 0.0
        )
        snapshot = {
            "timestamp": _utc_now().isoformat(),
            "total_value": total_value,
            "cash": self.cash,
            "positions_value": positions_value,
            "daily_return": daily_return,
        }
        self._equity_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._equity_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot) + "\n")
        return snapshot

    def get_portfolio_stats(self) -> dict[str, Any]:
        """Compute comprehensive portfolio statistics."""
        positions_value = self._compute_positions_value()
        total_value = self.cash + positions_value
        total_pnl = total_value - self.initial_capital
        total_pnl_pct = (total_value / self.initial_capital - 1) * 100 if self.initial_capital > 0 else 0.0

        equity_entries = self._load_equity_curve()
        daily_returns: list[float] = []
        equity_values: list[float] = []
        for entry in equity_entries:
            dr = entry.get("daily_return")
            if dr is not None:
                daily_returns.append(dr)
            tv = entry.get("total_value")
            if tv is not None:
                equity_values.append(tv)

        sharpe = compute_sharpe(daily_returns)
        max_dd = compute_max_drawdown(equity_values) if equity_values else 0.0

        winning = [t for t in self.trades if t.realized_pnl > 0]
        losing = [t for t in self.trades if t.realized_pnl < 0]
        trade_count = len(self.trades)

        win_rate = len(winning) / trade_count if trade_count > 0 else 0.0
        avg_win = sum(t.realized_pnl for t in winning) / len(winning) if winning else 0.0
        avg_loss = (
            abs(sum(t.realized_pnl for t in losing) / len(losing)) if losing else 0.0
        )

        return {
            "total_value": round(total_value, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(positions_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 4),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "win_rate": round(win_rate, 4),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "trade_count": trade_count,
            "open_positions": len(self.positions),
        }

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def circuit_breaker(self) -> bool:
        """Check risk limits and set a circuit‑breaker flag if violated.

        Conditions:
        1. Cumulative loss > 20% of initial capital.
        2. Any single‑day loss > daily_loss_limit (default 5%).
        3. Unresolved execution errors in the last 24 h.

        Returns:
            True if the circuit breaker was triggered, False otherwise.
        """
        # 1. cumulative loss
        total_value = self.cash + self._compute_positions_value()
        cumulative_loss = self.initial_capital - total_value
        if cumulative_loss > 0.20 * self.initial_capital:
            self._trigger_circuit("cumulative loss >20%")
            return True

        # 2. max single‑day loss
        equity_entries = self._load_equity_curve()
        max_daily_loss = 0.0
        for entry in equity_entries:
            dr = entry.get("daily_return")
            if dr is not None and dr < 0:
                loss = -dr
                if loss > max_daily_loss:
                    max_daily_loss = loss
        if max_daily_loss > self.daily_loss_limit:
            self._trigger_circuit(f"single‑day loss {max_daily_loss:.2%} exceeds limit")
            return True

        # 3. unresolved execution errors in last 24h
        now = _utc_now()
        recent_errors = [
            e for e in self.execution_errors
            if not e.resolved and now - datetime.fromisoformat(e.timestamp) < timedelta(hours=24)
        ]
        if recent_errors:
            self._trigger_circuit("unresolved execution errors in last 24h")
            return True

        # No trigger
        return False

    def _trigger_circuit(self, reason: str) -> None:
        """Write the circuit‑breaker flag file and log."""
        try:
            GINKO_DIR.mkdir(parents=True, exist_ok=True)
            CIRCUIT_BREAKER_FLAG.touch(exist_ok=True)
            logger.error("Circuit breaker triggered: %s. Flag file created at %s", reason, CIRCUIT_BREAKER_FLAG)
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to create circuit breaker flag: %s", exc)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _compute_positions_value(self) -> float:
        return sum(pos.current_price * pos.quantity for pos in self.positions.values())

    def _compute_portfolio_value(self) -> float:
        return self.cash + self._compute_positions_value()

    def _save(self) -> None:
        data = {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "positions": {sym: pos.to_dict() for sym, pos in self.positions.items()},
            "trades": [t.to_dict() for t in self.trades],
            "execution_errors": [e.to_dict() for e in self.execution_errors],
            "daily_loss_limit": self.daily_loss_limit,
            "position_size_limit": self.position_size_limit,
            "last_updated": _utc_now().isoformat(),
        }
        GINKO_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._portfolio_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        if not self._portfolio_path.is_file():
            return
        try:
            with open(self._portfolio_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.initial_capital = data.get("initial_capital", self.initial_capital)
            self.cash = data.get("cash", self.cash)
            self.positions = {
                sym: Position.from_dict(pdict) for sym, pdict in data.get("positions", {}).items()
            }
            self.trades = [Trade.from_dict(tdict) for tdict in data.get("trades", [])]
            self.execution_errors = [
                ExecutionError.from_dict(edict) for edict in data.get("execution_errors", [])
            ]
            self.daily_loss_limit = data.get("daily_loss_limit", self.daily_loss_limit)
            self.position_size_limit = data.get("position_size_limit", self.position_size_limit)
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to load portfolio state: %s", exc)

    def _save_trade(self, trade: Trade) -> None:
        GINKO_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._trades_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trade.to_dict()) + "\n")

    def _load_equity_curve(self) -> list[dict[str, Any]]:
        if not self._equity_path.is_file():
            return []
        entries = []
        try:
            with open(self._equity_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to load equity curve: %s", exc)
        return entries

    # ------------------------------------------------------------------
    # Execution error handling (simplified)
    # ------------------------------------------------------------------

    def record_execution_error(self, error_type: str, message: str, symbol: str = "") -> None:
        err = ExecutionError(
            timestamp=_utc_now().isoformat(),
            error_type=error_type,
            message=message,
            symbol=symbol,
            resolved=False,
        )
        self.execution_errors.append(err)
        self._save()

    def resolve_execution_error(self, error_id: str) -> None:
        for err in self.execution_errors:
            if err.timestamp == error_id:
                err.resolved = True
        self._save()
