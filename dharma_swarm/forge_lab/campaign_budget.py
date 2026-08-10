"""Hard reservation and settlement accounting for a Forge Lab campaign.

Controllers reserve the declared worst-case cost *before* dispatching work.
Only a reservation that fits under the campaign cap may be dispatched; unused
capacity is released when actual provider usage is settled.  Mutation spend is
an explicit first-class component rather than an unmetered side channel.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
import uuid
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.forge_lab.ids import content_digest
from dharma_swarm.forge_lab.campaign_budget_types import (
    BUDGET_COMPONENTS,
    BUDGET_SCHEMA,
    CANCELLED,
    INVALID,
    RESERVED,
    SETTLED,
    BudgetReservation,
    CampaignBudgetConflict,
    CampaignBudgetError,
    CampaignBudgetExceeded,
    CampaignBudgetSettlementError,
    decimal_text as _decimal_text,
    money as _money,
    tokens as _tokens,
)


class CampaignBudgetLedger:
    """In-memory hard budget with deterministic evidence serialization."""

    def __init__(self, *, cap_tokens: int, cap_usd: float | str | Decimal | None = None):
        self.cap_tokens = _tokens(cap_tokens, name="cap_tokens")
        self.cap_usd = None if cap_usd is None else _money(cap_usd, name="cap_usd")
        self._reservations: dict[str, BudgetReservation] = {}
        self._invalid_reasons: list[str] = []
        self._lock = threading.RLock()
        self._persisted_digest: str | None = None

    @property
    def valid(self) -> bool:
        return not self._invalid_reasons

    @property
    def invalid_reasons(self) -> tuple[str, ...]:
        return tuple(self._invalid_reasons)

    @property
    def closeout_ready(self) -> bool:
        """True only when accounting is valid and no dispatch remains active."""
        return self.valid and self.active_reservation_count == 0

    @property
    def active_reservation_count(self) -> int:
        return sum(reservation.status == RESERVED for reservation in self._reservations.values())

    @property
    def spent_tokens(self) -> int:
        return sum(
            reservation.actual_tokens or 0
            for reservation in self._reservations.values()
            if reservation.status in {SETTLED, INVALID}
        )

    @property
    def spent_usd(self) -> Decimal:
        return sum(
            (
                reservation.actual_usd or Decimal("0")
                for reservation in self._reservations.values()
                if reservation.status in {SETTLED, INVALID}
            ),
            Decimal("0"),
        )

    @property
    def reserved_tokens(self) -> int:
        return sum(
            reservation.max_tokens
            for reservation in self._reservations.values()
            if reservation.status == RESERVED
        )

    @property
    def reserved_usd(self) -> Decimal:
        return sum(
            (
                reservation.max_usd
                for reservation in self._reservations.values()
                if reservation.status == RESERVED
            ),
            Decimal("0"),
        )

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.cap_tokens - self.spent_tokens - self.reserved_tokens)

    @property
    def remaining_usd(self) -> Decimal | None:
        if self.cap_usd is None:
            return None
        return max(Decimal("0"), self.cap_usd - self.spent_usd - self.reserved_usd)

    def reservation(self, reservation_id: str) -> BudgetReservation | None:
        return self._reservations.get(reservation_id)

    def reservations(self) -> tuple[BudgetReservation, ...]:
        return tuple(self._reservations[key] for key in sorted(self._reservations))

    def can_reserve(
        self,
        *,
        max_tokens: int,
        max_usd: float | str | Decimal = 0,
    ) -> bool:
        token_ceiling = _tokens(max_tokens, name="max_tokens")
        usd_ceiling = _money(max_usd, name="max_usd")
        return (
            self.valid
            and token_ceiling <= self.remaining_tokens
            and (self.remaining_usd is None or usd_ceiling <= self.remaining_usd)
        )

    def reserve(
        self,
        component: str,
        *,
        max_tokens: int,
        max_usd: float | str | Decimal = 0,
        operation_id: str | None = None,
    ) -> BudgetReservation:
        """Reserve a worst-case ceiling before an external operation starts.

        Supplying a stable ``operation_id`` makes retries idempotent.  Reusing
        that ID with different ceilings or a different component fails closed.
        """
        if component not in BUDGET_COMPONENTS:
            raise CampaignBudgetError(f"unknown budget component: {component}")
        token_ceiling = _tokens(max_tokens, name="max_tokens")
        usd_ceiling = _money(max_usd, name="max_usd")
        reservation_id = str(operation_id or f"res_{uuid.uuid4().hex}")
        if not reservation_id:
            raise CampaignBudgetError("operation_id must not be empty")
        with self._lock:
            existing = self._reservations.get(reservation_id)
            if existing is not None:
                if (
                    existing.component != component
                    or existing.max_tokens != token_ceiling
                    or existing.max_usd != usd_ceiling
                ):
                    raise CampaignBudgetError("operation_id was reused with different reservation terms")
                return existing
            if not self.valid:
                raise CampaignBudgetError("campaign budget is invalid; new dispatches are forbidden")
            if token_ceiling > self.remaining_tokens:
                raise CampaignBudgetExceeded(
                    f"token reservation exceeds remaining budget: requested={token_ceiling} "
                    f"remaining={self.remaining_tokens}"
                )
            remaining_usd = self.remaining_usd
            if remaining_usd is not None and usd_ceiling > remaining_usd:
                raise CampaignBudgetExceeded(
                    f"USD reservation exceeds remaining budget: requested={_decimal_text(usd_ceiling)} "
                    f"remaining={_decimal_text(remaining_usd)}"
                )
            reservation = BudgetReservation(
                reservation_id=reservation_id,
                component=component,
                max_tokens=token_ceiling,
                max_usd=usd_ceiling,
            )
            self._reservations[reservation_id] = reservation
            return reservation

    def settle(
        self,
        reservation_id: str,
        *,
        actual_tokens: int,
        actual_usd: float | str | Decimal = 0,
    ) -> BudgetReservation:
        """Settle observed usage and release any unused reservation."""
        tokens = _tokens(actual_tokens, name="actual_tokens")
        usd = _money(actual_usd, name="actual_usd")
        with self._lock:
            reservation = self._require(reservation_id)
            if reservation.status in {SETTLED, INVALID}:
                if reservation.actual_tokens == tokens and reservation.actual_usd == usd:
                    return reservation
                raise CampaignBudgetError("reservation was already settled with different usage")
            if reservation.status == CANCELLED:
                raise CampaignBudgetError("cancelled reservation cannot be settled")
            overages: list[str] = []
            if tokens > reservation.max_tokens:
                overages.append(f"tokens:{tokens}>{reservation.max_tokens}")
            if usd > reservation.max_usd:
                overages.append(f"usd:{_decimal_text(usd)}>{_decimal_text(reservation.max_usd)}")
            if overages:
                reason = "reservation_ceiling_exceeded:" + ",".join(overages)
                invalid = replace(
                    reservation,
                    status=INVALID,
                    actual_tokens=tokens,
                    actual_usd=usd,
                    invalid_reason=reason,
                )
                self._reservations[reservation_id] = invalid
                self._invalid_reasons.append(f"{reservation_id}:{reason}")
                raise CampaignBudgetSettlementError(reason)
            settled = replace(
                reservation,
                status=SETTLED,
                actual_tokens=tokens,
                actual_usd=usd,
            )
            self._reservations[reservation_id] = settled
            return settled

    def cancel(self, reservation_id: str) -> BudgetReservation:
        """Release an operation that was never dispatched or did not consume."""
        with self._lock:
            reservation = self._require(reservation_id)
            if reservation.status == CANCELLED:
                return reservation
            if reservation.status != RESERVED:
                raise CampaignBudgetError("only an active reservation can be cancelled")
            cancelled = replace(reservation, status=CANCELLED)
            self._reservations[reservation_id] = cancelled
            return cancelled

    def component_totals(self) -> dict[str, dict[str, Any]]:
        totals = {
            component: {
                "spent_tokens": 0,
                "spent_usd": Decimal("0"),
                "reserved_tokens": 0,
                "reserved_usd": Decimal("0"),
            }
            for component in BUDGET_COMPONENTS
        }
        for reservation in self._reservations.values():
            row = totals[reservation.component]
            if reservation.status == RESERVED:
                row["reserved_tokens"] += reservation.max_tokens
                row["reserved_usd"] += reservation.max_usd
            elif reservation.status in {SETTLED, INVALID}:
                row["spent_tokens"] += reservation.actual_tokens or 0
                row["spent_usd"] += reservation.actual_usd or Decimal("0")
        return {
            component: {
                "spent_tokens": row["spent_tokens"],
                "spent_usd": _decimal_text(row["spent_usd"]),
                "reserved_tokens": row["reserved_tokens"],
                "reserved_usd": _decimal_text(row["reserved_usd"]),
            }
            for component, row in totals.items()
        }

    def assert_closeout_ready(self) -> None:
        if not self.valid:
            raise CampaignBudgetError("campaign budget is invalid")
        if self.active_reservation_count:
            raise CampaignBudgetError(
                "campaign has unsettled reservations: "
                f"active_reservation_count={self.active_reservation_count}"
            )

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        with self._lock:
            return self._to_dict_unlocked(include_digest=include_digest)

    def _to_dict_unlocked(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema": BUDGET_SCHEMA,
            "cap_tokens": self.cap_tokens,
            "cap_usd": None if self.cap_usd is None else _decimal_text(self.cap_usd),
            "spent_tokens": self.spent_tokens,
            "spent_usd": _decimal_text(self.spent_usd),
            "reserved_tokens": self.reserved_tokens,
            "reserved_usd": _decimal_text(self.reserved_usd),
            "remaining_tokens": self.remaining_tokens,
            "remaining_usd": (
                None if self.remaining_usd is None else _decimal_text(self.remaining_usd)
            ),
            "valid": self.valid,
            "closeout_ready": self.closeout_ready,
            "active_reservation_count": self.active_reservation_count,
            "invalid_reasons": list(self._invalid_reasons),
            "component_totals": self.component_totals(),
            "reservations": [reservation.to_dict() for reservation in self.reservations()],
        }
        if include_digest:
            value["ledger_sha256"] = content_digest(value)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CampaignBudgetLedger":
        if value.get("schema") != BUDGET_SCHEMA:
            raise CampaignBudgetError(f"unsupported budget schema: {value.get('schema')!r}")
        claimed_digest = str(value.get("ledger_sha256") or "")
        unsigned = dict(value)
        unsigned.pop("ledger_sha256", None)
        if claimed_digest != content_digest(unsigned):
            raise CampaignBudgetError("campaign budget digest mismatch")
        ledger = cls(cap_tokens=value.get("cap_tokens"), cap_usd=value.get("cap_usd"))
        raw_reservations = value.get("reservations")
        if not isinstance(raw_reservations, list):
            raise CampaignBudgetError("reservations must be a list")
        for raw in raw_reservations:
            reservation = BudgetReservation.from_dict(raw)
            if reservation.reservation_id in ledger._reservations:
                raise CampaignBudgetError("duplicate reservation_id in budget ledger")
            ledger._reservations[reservation.reservation_id] = reservation
        raw_reasons = value.get("invalid_reasons", [])
        if not isinstance(raw_reasons, list):
            raise CampaignBudgetError("invalid_reasons must be a list")
        ledger._invalid_reasons = [str(reason) for reason in raw_reasons]
        invalid_reservations = [
            reservation.reservation_id
            for reservation in ledger._reservations.values()
            if reservation.status == INVALID
        ]
        if bool(invalid_reservations) != bool(ledger._invalid_reasons):
            raise CampaignBudgetError("invalid reservation evidence is inconsistent")
        # Recompute all derived totals rather than trusting serialized counters.
        expected = ledger.to_dict(include_digest=False)
        for field in (
            "spent_tokens",
            "spent_usd",
            "reserved_tokens",
            "reserved_usd",
            "remaining_tokens",
            "remaining_usd",
            "valid",
            "closeout_ready",
            "active_reservation_count",
            "component_totals",
        ):
            if value.get(field) != expected[field]:
                raise CampaignBudgetError(f"campaign budget derived field mismatch: {field}")
        if ledger.spent_tokens + ledger.reserved_tokens > ledger.cap_tokens and ledger.valid:
            raise CampaignBudgetError("valid ledger exceeds token cap")
        if (
            ledger.cap_usd is not None
            and ledger.spent_usd + ledger.reserved_usd > ledger.cap_usd
            and ledger.valid
        ):
            raise CampaignBudgetError("valid ledger exceeds USD cap")
        ledger._persisted_digest = claimed_digest
        return ledger

    def save(self, path: Path | str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        lock_path = target.with_name(f".{target.name}.lock")
        with self._lock, lock_path.open("a+", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            snapshot = self._to_dict_unlocked()
            current_digest: str | None = None
            if target.exists():
                try:
                    current = json.loads(target.read_text(encoding="utf-8"))
                    current_digest = str(current.get("ledger_sha256") or "")
                except (OSError, json.JSONDecodeError, AttributeError) as exc:
                    raise CampaignBudgetError(f"cannot inspect persisted campaign budget: {exc}") from exc
            if self._persisted_digest is None:
                if current_digest is not None and current_digest != snapshot["ledger_sha256"]:
                    raise CampaignBudgetConflict("campaign budget already exists with different state")
            elif current_digest != self._persisted_digest:
                raise CampaignBudgetConflict("persisted campaign budget changed since load/save")
            payload = (json.dumps(snapshot, sort_keys=True, indent=2) + "\n").encode("utf-8")
            fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, target)
                _fsync_directory(target.parent)
                self._persisted_digest = str(snapshot["ledger_sha256"])
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    @classmethod
    def load(cls, path: Path | str) -> "CampaignBudgetLedger":
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CampaignBudgetError(f"cannot load campaign budget: {exc}") from exc
        if not isinstance(value, Mapping):
            raise CampaignBudgetError("campaign budget root must be an object")
        return cls.from_dict(value)

    def _require(self, reservation_id: str) -> BudgetReservation:
        try:
            return self._reservations[reservation_id]
        except KeyError as exc:
            raise CampaignBudgetError(f"unknown reservation_id: {reservation_id}") from exc


# Short alias for callers that do not need to distinguish the evidence object.
CampaignBudget = CampaignBudgetLedger


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = [
    "BUDGET_COMPONENTS",
    "BUDGET_SCHEMA",
    "BudgetReservation",
    "CANCELLED",
    "CampaignBudget",
    "CampaignBudgetError",
    "CampaignBudgetConflict",
    "CampaignBudgetExceeded",
    "CampaignBudgetLedger",
    "CampaignBudgetSettlementError",
    "INVALID",
    "RESERVED",
    "SETTLED",
]
