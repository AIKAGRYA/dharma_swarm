"""Value types and validation primitives for campaign budget accounting."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

BUDGET_SCHEMA = "forge_lab.campaign_budget.v1"
BUDGET_COMPONENTS = (
    "mutation",
    "baseline_eval",
    "candidate_eval",
    "confirm_eval",
    "holdout_eval",
)
RESERVED = "reserved"
SETTLED = "settled"
CANCELLED = "cancelled"
INVALID = "invalid"


class CampaignBudgetError(RuntimeError):
    """Base class for malformed or invalid campaign accounting."""


class CampaignBudgetExceeded(CampaignBudgetError):
    """A dispatch ceiling does not fit in the remaining campaign budget."""


class CampaignBudgetSettlementError(CampaignBudgetError):
    """Observed usage exceeded the ceiling reserved before dispatch."""


class CampaignBudgetConflict(CampaignBudgetError):
    """A different process advanced the persisted budget ledger."""


def tokens(value: Any, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CampaignBudgetError(f"{name} must be a non-negative integer")
    return value


def money(value: Any, *, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CampaignBudgetError(f"{name} must be a non-negative decimal") from exc
    if not result.is_finite() or result < 0:
        raise CampaignBudgetError(f"{name} must be a non-negative decimal")
    return result


def decimal_text(value: Decimal) -> str:
    return format(value, "f")


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: str
    component: str
    max_tokens: int
    max_usd: Decimal
    status: str = RESERVED
    actual_tokens: int | None = None
    actual_usd: Decimal | None = None
    invalid_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "component": self.component,
            "max_tokens": self.max_tokens,
            "max_usd": decimal_text(self.max_usd),
            "status": self.status,
            "actual_tokens": self.actual_tokens,
            "actual_usd": None if self.actual_usd is None else decimal_text(self.actual_usd),
            "invalid_reason": self.invalid_reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BudgetReservation":
        result = cls(
            reservation_id=str(value.get("reservation_id") or ""),
            component=str(value.get("component") or ""),
            max_tokens=tokens(value.get("max_tokens"), name="max_tokens"),
            max_usd=money(value.get("max_usd", "0"), name="max_usd"),
            status=str(value.get("status") or ""),
            actual_tokens=(None if value.get("actual_tokens") is None else tokens(value.get("actual_tokens"), name="actual_tokens")),
            actual_usd=(None if value.get("actual_usd") is None else money(value.get("actual_usd"), name="actual_usd")),
            invalid_reason=(None if value.get("invalid_reason") is None else str(value.get("invalid_reason"))),
        )
        if not result.reservation_id:
            raise CampaignBudgetError("reservation_id is required")
        if result.component not in BUDGET_COMPONENTS:
            raise CampaignBudgetError(f"unknown budget component: {result.component}")
        if result.status not in {RESERVED, SETTLED, CANCELLED, INVALID}:
            raise CampaignBudgetError(f"unknown reservation status: {result.status}")
        if result.status in {SETTLED, INVALID} and (result.actual_tokens is None or result.actual_usd is None):
            raise CampaignBudgetError("settled reservations require actual usage")
        if result.status in {RESERVED, CANCELLED} and (result.actual_tokens is not None or result.actual_usd is not None):
            raise CampaignBudgetError("unsettled reservations cannot contain actual usage")
        if result.status == SETTLED and ((result.actual_tokens or 0) > result.max_tokens or (result.actual_usd or Decimal("0")) > result.max_usd):
            raise CampaignBudgetError("settled usage exceeds its reservation ceiling")
        if result.status == INVALID and not result.invalid_reason:
            raise CampaignBudgetError("invalid reservation requires invalid_reason")
        return result
