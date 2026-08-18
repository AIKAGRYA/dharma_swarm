"""Authoritative evaluator for the fixed Helm route-truth census.

The positive-verdict capability is module-private and never crosses the public
``model_status`` compatibility surface.  Raw evidence therefore cannot become
``ON_CALL`` without satisfying this evaluator's proof obligations.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import InitVar, dataclass
from datetime import datetime
import re
from typing import AbstractSet, Iterable

from dharma_swarm.helm_route_truth_types import (
    ACCEPTED_ROUTE_VERIFIER_ID,
    ACCEPTED_ROUTE_VERIFIER_VERSION,
    HELM_ON_CALL_PROJECTION_SCHEMA_VERSION,
    HELM_SLICE1_SEATS,
    MAX_ROUTE_VERIFICATION_TTL,
    ROUTE_VERIFICATION_SCHEMA_VERSION,
    HelmOnCallState,
    HelmSeat,
    RouteEvidence,
    RouteVerdict,
    SanitizedRouteEvidence,
    _HELM_SEAT_BY_ID,
    _HELM_SEAT_INDEX,
    _is_aware_datetime,
    _require_aware_datetime,
    _require_non_empty_string,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_POSITIVE_VERDICT_AUTHORITY = object()


@dataclass(frozen=True, slots=True)
class RouteVerification:
    schema_version: str
    seat_id: str
    display_label: str
    logical_lineage: str
    verdict: RouteVerdict
    reason: str
    evaluated_at: datetime
    runtime_epoch: str
    evidence: SanitizedRouteEvidence | None
    _positive_authority: InitVar[object | None] = None

    def __post_init__(self, _positive_authority: object | None) -> None:
        if not isinstance(self.verdict, RouteVerdict):
            raise ValueError("verdict must be a RouteVerdict")
        if self.verdict is RouteVerdict.ON_CALL and _positive_authority is not _POSITIVE_VERDICT_AUTHORITY:
            raise ValueError("ON_CALL may only be constructed by evaluate_route_verification")
        if self.schema_version != ROUTE_VERIFICATION_SCHEMA_VERSION:
            raise ValueError("invalid route-verification schema")
        seat = _HELM_SEAT_BY_ID.get(self.seat_id)
        if (
            seat is None
            or self.display_label != seat.display_label
            or self.logical_lineage != seat.logical_lineage
        ):
            raise ValueError("route verification does not identify a fixed Helm seat")
        _require_aware_datetime(self.evaluated_at, "evaluated_at")
        _require_non_empty_string(self.runtime_epoch, "runtime_epoch")
        _require_non_empty_string(self.reason, "reason")
        if self.evidence is not None and not isinstance(self.evidence, SanitizedRouteEvidence):
            raise ValueError("evidence must be sanitized route evidence or null")


@dataclass(frozen=True, slots=True)
class HelmOnCallProjection:
    schema_version: str
    state: HelmOnCallState
    on_call_count: int | None
    total: int
    seats: tuple[RouteVerification, ...]
    evaluated_at: datetime
    runtime_epoch: str

    def __post_init__(self) -> None:
        if self.schema_version != HELM_ON_CALL_PROJECTION_SCHEMA_VERSION:
            raise ValueError("invalid Helm projection schema")
        if not isinstance(self.state, HelmOnCallState):
            raise ValueError("state must be a HelmOnCallState")
        if (
            isinstance(self.total, bool)
            or not isinstance(self.total, int)
            or self.total != len(HELM_SLICE1_SEATS)
        ):
            raise ValueError("Helm projection total must be seven")
        if not isinstance(self.seats, tuple) or any(
            not isinstance(row, RouteVerification) for row in self.seats
        ):
            raise ValueError("Helm projection seats must be an immutable verification tuple")
        expected_ids = tuple(seat.seat_id for seat in HELM_SLICE1_SEATS)
        if tuple(row.seat_id for row in self.seats) != expected_ids:
            raise ValueError("Helm projection seats must be complete and ordered")
        _require_aware_datetime(self.evaluated_at, "evaluated_at")
        _require_non_empty_string(self.runtime_epoch, "runtime_epoch")
        if any(row.runtime_epoch != self.runtime_epoch for row in self.seats):
            raise ValueError("seat runtime epoch disagrees with projection")
        if any(row.evaluated_at != self.evaluated_at for row in self.seats):
            raise ValueError("seat evaluation time disagrees with projection")
        positive_count = sum(row.verdict is RouteVerdict.ON_CALL for row in self.seats)
        if self.state is HelmOnCallState.UNKNOWN:
            if self.on_call_count is not None:
                raise ValueError("UNKNOWN projections must report ?/7")
            if any(row.verdict is not RouteVerdict.UNKNOWN for row in self.seats):
                raise ValueError("UNKNOWN projections cannot carry seat verdicts")
            return
        if (
            isinstance(self.on_call_count, bool)
            or not isinstance(self.on_call_count, int)
            or self.on_call_count != positive_count
        ):
            raise ValueError("projection count disagrees with seat verdicts")
        if self.state is HelmOnCallState.ON_CALL and positive_count != self.total:
            raise ValueError("ON_CALL requires exactly 7/7")
        if self.state is HelmOnCallState.LIVE_DEGRADED:
            if positive_count >= self.total:
                raise ValueError("LIVE_DEGRADED requires fewer than 7/7")
            if any(row.verdict is RouteVerdict.CLOCK_SKEW for row in self.seats):
                raise ValueError("clock-skew evidence requires CLOCK_SKEW state")
        if self.state is HelmOnCallState.CLOCK_SKEW and not any(
            row.verdict is RouteVerdict.CLOCK_SKEW for row in self.seats
        ):
            raise ValueError("CLOCK_SKEW requires future-dated seat evidence")


def _sanitized_evidence(evidence: RouteEvidence, now: datetime) -> SanitizedRouteEvidence:
    observed_at = evidence.observed_at if isinstance(evidence.observed_at, datetime) else None
    expires_at = evidence.expires_at if isinstance(evidence.expires_at, datetime) else None
    age_seconds: int | None = None
    if _is_aware_datetime(observed_at) and observed_at <= now:
        age_seconds = int((now - observed_at).total_seconds())
    return SanitizedRouteEvidence(
        seat_id=evidence.seat_id,
        logical_lineage=evidence.logical_lineage,
        requested_provider=evidence.requested_provider,
        requested_model=evidence.requested_model,
        served_provider=evidence.served_provider,
        served_model=evidence.served_model,
        observed_at=observed_at,
        expires_at=expires_at,
        age_seconds=age_seconds,
        verifier_id=evidence.verifier_id,
        verifier_version=evidence.verifier_version,
        receipt_ref=evidence.receipt_ref,
        receipt_sha256=evidence.receipt_sha256,
        runtime_epoch=evidence.runtime_epoch,
    )


def _negative_verification(
    seat: HelmSeat,
    verdict: RouteVerdict,
    reason: str,
    now: datetime,
    current_runtime_epoch: str,
    evidence: SanitizedRouteEvidence | None,
) -> RouteVerification:
    if verdict is RouteVerdict.ON_CALL:
        raise ValueError("positive verdicts require the evaluator")
    return RouteVerification(
        schema_version=ROUTE_VERIFICATION_SCHEMA_VERSION,
        seat_id=seat.seat_id,
        display_label=seat.display_label,
        logical_lineage=seat.logical_lineage,
        verdict=verdict,
        reason=reason,
        evaluated_at=now,
        runtime_epoch=current_runtime_epoch,
        evidence=evidence,
    )


def evaluate_route_verification(
    *,
    seat: HelmSeat,
    evidence: RouteEvidence | None,
    now: datetime,
    current_runtime_epoch: str,
    replayed_receipts: AbstractSet[str] = frozenset(),
    receipt_duplicated: bool = False,
) -> RouteVerification:
    """Construct one verdict, with the sole guarded path to ``ON_CALL``."""

    _require_aware_datetime(now, "now")
    _require_non_empty_string(current_runtime_epoch, "current_runtime_epoch")
    if not isinstance(seat, HelmSeat) or _HELM_SEAT_BY_ID.get(seat.seat_id) != seat:
        raise ValueError("seat must be one of HELM_SLICE1_SEATS")
    if evidence is None:
        return _negative_verification(
            seat,
            RouteVerdict.UNKNOWN,
            "missing_evidence",
            now,
            current_runtime_epoch,
            None,
        )
    if not isinstance(evidence, RouteEvidence):
        return _negative_verification(
            seat,
            RouteVerdict.UNKNOWN,
            "malformed_evidence",
            now,
            current_runtime_epoch,
            None,
        )

    sanitized = _sanitized_evidence(evidence, now)

    def reject(verdict: RouteVerdict, reason: str) -> RouteVerification:
        return _negative_verification(
            seat,
            verdict,
            reason,
            now,
            current_runtime_epoch,
            sanitized,
        )

    if evidence.seat_id != seat.seat_id:
        return reject(RouteVerdict.REJECTED, "seat_mismatch")
    if evidence.logical_lineage != seat.logical_lineage:
        return reject(RouteVerdict.REJECTED, "lineage_mismatch")
    if evidence.runtime_epoch != current_runtime_epoch:
        return reject(RouteVerdict.UNKNOWN, "runtime_epoch_mismatch")
    if evidence.success is not True:
        return reject(RouteVerdict.REJECTED, "provider_completion_failed")
    if evidence.synthetic is not False:
        return reject(RouteVerdict.REJECTED, "synthetic_evidence")
    if not all(
        isinstance(value, str) and bool(value.strip())
        for value in (evidence.requested_provider, evidence.requested_model)
    ):
        return reject(RouteVerdict.REJECTED, "requested_identity_missing")
    if not all(
        isinstance(value, str) and bool(value.strip())
        for value in (evidence.served_provider, evidence.served_model)
    ):
        return reject(RouteVerdict.REJECTED, "served_identity_missing")
    served_identity = (evidence.served_provider, evidence.served_model)
    if served_identity not in seat.admissible_served_identities:
        return reject(RouteVerdict.REJECTED, "served_identity_mismatch")
    if not _is_aware_datetime(evidence.observed_at) or not _is_aware_datetime(evidence.expires_at):
        return reject(RouteVerdict.REJECTED, "timestamp_not_timezone_aware")
    observed_at = evidence.observed_at
    expires_at = evidence.expires_at
    if observed_at > now:
        return reject(RouteVerdict.CLOCK_SKEW, "timestamp_in_future")
    if expires_at <= observed_at:
        return reject(RouteVerdict.REJECTED, "expiry_not_after_observation")
    if expires_at - observed_at > MAX_ROUTE_VERIFICATION_TTL:
        return reject(RouteVerdict.REJECTED, "ttl_exceeds_24_hours")
    if now >= expires_at:
        return reject(RouteVerdict.REJECTED, "evidence_expired")
    if (
        evidence.verifier_id != ACCEPTED_ROUTE_VERIFIER_ID
        or evidence.verifier_version != ACCEPTED_ROUTE_VERIFIER_VERSION
    ):
        return reject(RouteVerdict.REJECTED, "verifier_identity_rejected")
    if evidence.verifier_accepted is not True:
        return reject(RouteVerdict.REJECTED, "verifier_decision_rejected")
    if not isinstance(evidence.receipt_ref, str) or not evidence.receipt_ref.strip():
        return reject(RouteVerdict.REJECTED, "receipt_reference_missing")
    if not isinstance(evidence.receipt_sha256, str) or _SHA256_RE.fullmatch(evidence.receipt_sha256) is None:
        return reject(RouteVerdict.REJECTED, "receipt_hash_invalid")
    if receipt_duplicated:
        return reject(RouteVerdict.REJECTED, "receipt_duplicated")
    if evidence.receipt_ref in replayed_receipts or evidence.receipt_sha256 in replayed_receipts:
        return reject(RouteVerdict.REJECTED, "receipt_replayed")

    return RouteVerification(
        schema_version=ROUTE_VERIFICATION_SCHEMA_VERSION,
        seat_id=seat.seat_id,
        display_label=seat.display_label,
        logical_lineage=seat.logical_lineage,
        verdict=RouteVerdict.ON_CALL,
        reason="verified",
        evaluated_at=now,
        runtime_epoch=current_runtime_epoch,
        evidence=sanitized,
        _positive_authority=_POSITIVE_VERDICT_AUTHORITY,
    )


def _unknown_helm_projection(
    *,
    now: datetime,
    current_runtime_epoch: str,
    reason: str,
) -> HelmOnCallProjection:
    seats = tuple(
        _negative_verification(
            seat,
            RouteVerdict.UNKNOWN,
            reason,
            now,
            current_runtime_epoch,
            None,
        )
        for seat in HELM_SLICE1_SEATS
    )
    return HelmOnCallProjection(
        schema_version=HELM_ON_CALL_PROJECTION_SCHEMA_VERSION,
        state=HelmOnCallState.UNKNOWN,
        on_call_count=None,
        total=len(HELM_SLICE1_SEATS),
        seats=seats,
        evaluated_at=now,
        runtime_epoch=current_runtime_epoch,
    )


def unknown_helm_on_call_projection(
    *,
    now: datetime,
    current_runtime_epoch: str,
) -> HelmOnCallProjection:
    """Return the mandatory connect/reconnect/epoch-change ``?/7`` state."""

    _require_aware_datetime(now, "now")
    _require_non_empty_string(current_runtime_epoch, "current_runtime_epoch")
    return _unknown_helm_projection(
        now=now,
        current_runtime_epoch=current_runtime_epoch,
        reason="awaiting_authoritative_projection",
    )


def project_helm_on_call(
    evidences: Iterable[RouteEvidence],
    *,
    now: datetime,
    current_runtime_epoch: str,
    replayed_receipts: AbstractSet[str] = frozenset(),
) -> HelmOnCallProjection:
    """Evaluate a complete ordered seven-seat census from raw evidence."""

    _require_aware_datetime(now, "now")
    _require_non_empty_string(current_runtime_epoch, "current_runtime_epoch")
    rows = list(evidences)
    if any(
        not isinstance(row, RouteEvidence) or not isinstance(row.seat_id, str) for row in rows
    ):
        return _unknown_helm_projection(
            now=now,
            current_runtime_epoch=current_runtime_epoch,
            reason="malformed_evidence_batch",
        )
    positions = [_HELM_SEAT_INDEX.get(row.seat_id) for row in rows]
    known_positions = [position for position in positions if position is not None]
    seat_counts = Counter(row.seat_id for row in rows)
    if (
        len(known_positions) != len(rows)
        or known_positions != sorted(known_positions)
        or any(count > 1 for count in seat_counts.values())
    ):
        return _unknown_helm_projection(
            now=now,
            current_runtime_epoch=current_runtime_epoch,
            reason="malformed_evidence_batch",
        )

    by_seat = {row.seat_id: row for row in rows}
    ref_counts = Counter(
        row.receipt_ref for row in rows if isinstance(row.receipt_ref, str) and row.receipt_ref.strip()
    )
    hash_counts = Counter(
        row.receipt_sha256
        for row in rows
        if isinstance(row.receipt_sha256, str) and row.receipt_sha256
    )
    verifications = tuple(
        evaluate_route_verification(
            seat=seat,
            evidence=by_seat.get(seat.seat_id),
            now=now,
            current_runtime_epoch=current_runtime_epoch,
            replayed_receipts=replayed_receipts,
            receipt_duplicated=(
                by_seat.get(seat.seat_id) is not None
                and (
                    ref_counts[by_seat[seat.seat_id].receipt_ref] > 1
                    or hash_counts[by_seat[seat.seat_id].receipt_sha256] > 1
                )
            ),
        )
        for seat in HELM_SLICE1_SEATS
    )
    if any(row.reason == "runtime_epoch_mismatch" for row in verifications):
        return _unknown_helm_projection(
            now=now,
            current_runtime_epoch=current_runtime_epoch,
            reason="runtime_epoch_mismatch",
        )
    on_call_count = sum(row.verdict is RouteVerdict.ON_CALL for row in verifications)
    if any(row.verdict is RouteVerdict.CLOCK_SKEW for row in verifications):
        state = HelmOnCallState.CLOCK_SKEW
    elif on_call_count == len(HELM_SLICE1_SEATS):
        state = HelmOnCallState.ON_CALL
    else:
        state = HelmOnCallState.LIVE_DEGRADED
    return HelmOnCallProjection(
        schema_version=HELM_ON_CALL_PROJECTION_SCHEMA_VERSION,
        state=state,
        on_call_count=on_call_count,
        total=len(HELM_SLICE1_SEATS),
        seats=verifications,
        evaluated_at=now,
        runtime_epoch=current_runtime_epoch,
    )
