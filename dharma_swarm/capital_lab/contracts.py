"""Typed inter-layer contracts for the capital_lab fund spine.

The institutional amateur/professional divide is separation of concerns over
typed objects: a layer emits one of these frozen contracts and must NOT know how
the next layer works. The pipeline is

    Universe -> Insight -> PortfolioTarget -> RiskAdjustedTarget -> Order

(the QuantConnect-LEAN / NautilusTrader reference pattern). An alpha agent emits
Insights and cannot size; an execution agent consumes Orders and cannot know
which signal produced them. This module has no internal dependencies: it is the
base of the capital_lab DAG.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_payload(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"  # explicit abstain / no-trade — a first-class output


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class TradingState(str, Enum):
    """Canonical kill-switch substrate (Nautilus RiskEngine pattern). ACTIVE:
    normal. REDUCING: only risk-reducing orders accepted. HALTED: blocked."""

    ACTIVE = "active"
    REDUCING = "reducing"
    HALTED = "halted"


# -- Layer 1: Data / Ingestion -------------------------------------------------
@dataclass(frozen=True)
class Universe:
    """The tradable set knowable at a point in time. ``as_of`` is the knowledge
    timestamp; a backtest must never see a Universe with a future ``as_of``."""

    as_of: str
    security_ids: tuple[str, ...]
    source: str = "capital_lab"

    def __post_init__(self) -> None:
        if not self.security_ids:
            raise ValueError("Universe must be non-empty")
        if len(set(self.security_ids)) != len(self.security_ids):
            raise ValueError("Universe security_ids must be unique")

    @property
    def content_hash(self) -> str:
        return _sha256_payload({"as_of": self.as_of, "ids": sorted(self.security_ids)})

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["content_hash"] = self.content_hash
        return payload


# -- Layer 2: Research / Alpha -------------------------------------------------
@dataclass(frozen=True)
class Insight:
    """An alpha forecast for one symbol. Carries ``confidence`` and a PIT
    ``knowledge_ts`` so downstream leakage gates can verify it was knowable. The
    alpha layer emits ONLY this — never a size, weight, or order."""

    symbol: str
    direction: Direction
    magnitude: float
    confidence: float
    horizon_days: int
    source_agent: str
    generated_at: str = field(default_factory=_utc_now)
    knowledge_ts: str | None = None

    def __post_init__(self) -> None:
        if self.magnitude < 0:
            raise ValueError("magnitude must be >= 0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.horizon_days <= 0:
            raise ValueError("horizon_days must be positive")

    @property
    def is_actionable(self) -> bool:
        return self.direction is not Direction.FLAT and self.magnitude > 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["direction"] = self.direction.value
        return payload


# -- Layer 3: Portfolio Construction ------------------------------------------
@dataclass(frozen=True)
class PortfolioTarget:
    """A desired exposure (signed weight, long +, short -) for one symbol,
    produced by the construction layer from one or more Insights. Carries no
    order semantics."""

    symbol: str
    target_weight: float
    source_insight_ids: tuple[str, ...] = ()
    generated_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not -1.0 <= self.target_weight <= 1.0:
            raise ValueError("target_weight must be in [-1, 1]")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# -- Layer 4: Risk Management --------------------------------------------------
@dataclass(frozen=True)
class RiskAdjustedTarget:
    """A PortfolioTarget after the risk layer has validated/clamped it. The risk
    layer may approve, reduce, or block; it records why. This is the only object
    the execution layer is allowed to turn into an Order."""

    symbol: str
    requested_weight: float
    approved_weight: float
    approved: bool
    trading_state: TradingState
    clamps: tuple[str, ...] = ()
    breaches: tuple[str, ...] = ()
    generated_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if self.approved and abs(self.approved_weight) > abs(self.requested_weight) + 1e-9:
            raise ValueError("approved_weight cannot exceed requested_weight in magnitude")
        if not self.approved and self.approved_weight != 0.0:
            raise ValueError("a non-approved target must have approved_weight 0.0")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trading_state"] = self.trading_state.value
        return payload


# -- Layer 5: Execution --------------------------------------------------------
@dataclass(frozen=True)
class Order:
    """A concrete order intent — the execution layer's input. ``client_order_id``
    is the deterministic idempotency key. Bridges to the broker-paper membrane's
    ``OrderIntent`` via ``to_membrane_intent`` (kept out of this base module to
    preserve a dependency-free contract layer)."""

    client_order_id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: float
    limit_price: float | None = None
    source: str = "capital_lab"

    def __post_init__(self) -> None:
        if not self.client_order_id.strip():
            raise ValueError("client_order_id is required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit order requires a limit_price")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["side"] = self.side.value
        payload["order_type"] = self.order_type.value
        return payload
