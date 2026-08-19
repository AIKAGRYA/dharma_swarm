"""Strict wire codecs for Helm route evidence and read-only projections."""

from __future__ import annotations

from typing import Any, Mapping

from dharma_swarm.helm_route_truth_evaluator import (
    HelmOnCallProjection,
    RouteVerification,
)
from dharma_swarm.helm_route_truth_types import (
    HelmOnCallState,
    RouteEvidence,
    RouteVerdict,
    SanitizedRouteEvidence,
    _HELM_SEAT_BY_ID,
    _format_rfc3339,
    _is_aware_datetime,
    _optional_bool,
    _optional_string,
    _parse_optional_rfc3339,
    _parse_rfc3339,
    _require_non_empty_string,
    _strict_keys,
)


_ROUTE_EVIDENCE_KEYS = {
    "seat_id",
    "logical_lineage",
    "requested_provider",
    "requested_model",
    "served_provider",
    "served_model",
    "success",
    "synthetic",
    "observed_at",
    "expires_at",
    "verifier_id",
    "verifier_version",
    "verifier_accepted",
    "receipt_ref",
    "receipt_sha256",
    "runtime_epoch",
}
_SANITIZED_EVIDENCE_KEYS = {
    "seat_id",
    "logical_lineage",
    "requested_provider",
    "requested_model",
    "served_provider",
    "served_model",
    "observed_at",
    "expires_at",
    "age_seconds",
    "verifier_id",
    "verifier_version",
    "receipt_ref",
    "receipt_sha256",
    "runtime_epoch",
}
_ROUTE_VERIFICATION_KEYS = {
    "schema_version",
    "seat_id",
    "display_label",
    "logical_lineage",
    "verdict",
    "reason",
    "evaluated_at",
    "runtime_epoch",
    "evidence",
}
_HELM_PROJECTION_KEYS = {
    "schema_version",
    "state",
    "on_call_count",
    "total",
    "seats",
    "evaluated_at",
    "runtime_epoch",
}


def route_evidence_from_dict(data: Mapping[str, Any]) -> RouteEvidence:
    """Strictly parse untrusted raw evidence; no verdict is accepted."""

    row = _strict_keys(data, _ROUTE_EVIDENCE_KEYS, "route evidence")
    return RouteEvidence(
        seat_id=_optional_string(row["seat_id"], "seat_id"),
        logical_lineage=_optional_string(row["logical_lineage"], "logical_lineage"),
        requested_provider=_optional_string(row["requested_provider"], "requested_provider"),
        requested_model=_optional_string(row["requested_model"], "requested_model"),
        served_provider=_optional_string(row["served_provider"], "served_provider"),
        served_model=_optional_string(row["served_model"], "served_model"),
        success=_optional_bool(row["success"], "success"),
        synthetic=_optional_bool(row["synthetic"], "synthetic"),
        observed_at=_parse_optional_rfc3339(row["observed_at"], "observed_at"),
        expires_at=_parse_optional_rfc3339(row["expires_at"], "expires_at"),
        verifier_id=_optional_string(row["verifier_id"], "verifier_id"),
        verifier_version=_optional_string(row["verifier_version"], "verifier_version"),
        verifier_accepted=_optional_bool(row["verifier_accepted"], "verifier_accepted"),
        receipt_ref=_optional_string(row["receipt_ref"], "receipt_ref"),
        receipt_sha256=_optional_string(row["receipt_sha256"], "receipt_sha256"),
        runtime_epoch=_optional_string(row["runtime_epoch"], "runtime_epoch"),
    )


def _sanitized_evidence_to_dict(evidence: SanitizedRouteEvidence) -> dict[str, Any]:
    return {
        "seat_id": evidence.seat_id,
        "logical_lineage": evidence.logical_lineage,
        "requested_provider": evidence.requested_provider,
        "requested_model": evidence.requested_model,
        "served_provider": evidence.served_provider,
        "served_model": evidence.served_model,
        "observed_at": _format_rfc3339(evidence.observed_at) if _is_aware_datetime(evidence.observed_at) else None,
        "expires_at": _format_rfc3339(evidence.expires_at) if _is_aware_datetime(evidence.expires_at) else None,
        "age_seconds": evidence.age_seconds,
        "verifier_id": evidence.verifier_id,
        "verifier_version": evidence.verifier_version,
        "receipt_ref": evidence.receipt_ref,
        "receipt_sha256": evidence.receipt_sha256,
        "runtime_epoch": evidence.runtime_epoch,
    }


def route_verification_to_dict(verification: RouteVerification) -> dict[str, Any]:
    return {
        "schema_version": verification.schema_version,
        "seat_id": verification.seat_id,
        "display_label": verification.display_label,
        "logical_lineage": verification.logical_lineage,
        "verdict": verification.verdict.value,
        "reason": verification.reason,
        "evaluated_at": _format_rfc3339(verification.evaluated_at),
        "runtime_epoch": verification.runtime_epoch,
        "evidence": (
            _sanitized_evidence_to_dict(verification.evidence)
            if verification.evidence is not None
            else None
        ),
    }


def _sanitized_evidence_from_dict(data: Mapping[str, Any]) -> SanitizedRouteEvidence:
    row = _strict_keys(data, _SANITIZED_EVIDENCE_KEYS, "sanitized route evidence")
    age_seconds = row["age_seconds"]
    if age_seconds is not None and (
        isinstance(age_seconds, bool) or not isinstance(age_seconds, int) or age_seconds < 0
    ):
        raise ValueError("age_seconds must be a nonnegative integer or null")
    return SanitizedRouteEvidence(
        seat_id=_optional_string(row["seat_id"], "seat_id"),
        logical_lineage=_optional_string(row["logical_lineage"], "logical_lineage"),
        requested_provider=_optional_string(row["requested_provider"], "requested_provider"),
        requested_model=_optional_string(row["requested_model"], "requested_model"),
        served_provider=_optional_string(row["served_provider"], "served_provider"),
        served_model=_optional_string(row["served_model"], "served_model"),
        observed_at=_parse_optional_rfc3339(row["observed_at"], "observed_at"),
        expires_at=_parse_optional_rfc3339(row["expires_at"], "expires_at"),
        age_seconds=age_seconds,
        verifier_id=_optional_string(row["verifier_id"], "verifier_id"),
        verifier_version=_optional_string(row["verifier_version"], "verifier_version"),
        receipt_ref=_optional_string(row["receipt_ref"], "receipt_ref"),
        receipt_sha256=_optional_string(row["receipt_sha256"], "receipt_sha256"),
        runtime_epoch=_optional_string(row["runtime_epoch"], "runtime_epoch"),
    )


def route_verification_from_dict(data: Mapping[str, Any]) -> RouteVerification:
    """Strict untrusted decoder which categorically rejects positive authority."""

    row = _strict_keys(data, _ROUTE_VERIFICATION_KEYS, "route verification")
    try:
        verdict = RouteVerdict(row["verdict"])
    except (TypeError, ValueError) as exc:
        raise ValueError("unknown route verdict") from exc
    if verdict is RouteVerdict.ON_CALL:
        raise ValueError("serialized ON_CALL is not evaluation authority")
    seat_id = _require_non_empty_string(row["seat_id"], "seat_id")
    seat = _HELM_SEAT_BY_ID.get(seat_id)
    if seat is None:
        raise ValueError("unknown Helm seat")
    evidence_value = row["evidence"]
    evidence = None if evidence_value is None else _sanitized_evidence_from_dict(evidence_value)
    return RouteVerification(
        schema_version=_require_non_empty_string(row["schema_version"], "schema_version"),
        seat_id=seat_id,
        display_label=_require_non_empty_string(row["display_label"], "display_label"),
        logical_lineage=_require_non_empty_string(row["logical_lineage"], "logical_lineage"),
        verdict=verdict,
        reason=_require_non_empty_string(row["reason"], "reason"),
        evaluated_at=_parse_rfc3339(row["evaluated_at"], "evaluated_at"),
        runtime_epoch=_require_non_empty_string(row["runtime_epoch"], "runtime_epoch"),
        evidence=evidence,
    )


def helm_on_call_projection_to_dict(projection: HelmOnCallProjection) -> dict[str, Any]:
    return {
        "schema_version": projection.schema_version,
        "state": projection.state.value,
        "on_call_count": projection.on_call_count,
        "total": projection.total,
        "seats": [route_verification_to_dict(row) for row in projection.seats],
        "evaluated_at": _format_rfc3339(projection.evaluated_at),
        "runtime_epoch": projection.runtime_epoch,
    }


def helm_on_call_projection_from_dict(data: Mapping[str, Any]) -> HelmOnCallProjection:
    """Decode negative state only; serialized positive truth is never authority."""

    row = _strict_keys(data, _HELM_PROJECTION_KEYS, "Helm projection")
    try:
        state = HelmOnCallState(row["state"])
    except (TypeError, ValueError) as exc:
        raise ValueError("unknown Helm projection state") from exc
    if state is HelmOnCallState.ON_CALL:
        raise ValueError("serialized ON_CALL projection is not evaluation authority")
    seats_value = row["seats"]
    if not isinstance(seats_value, list):
        raise ValueError("seats must be a list")
    seats = tuple(route_verification_from_dict(item) for item in seats_value)
    on_call_count = row["on_call_count"]
    if on_call_count is not None and (
        isinstance(on_call_count, bool) or not isinstance(on_call_count, int)
    ):
        raise ValueError("on_call_count must be an integer or null")
    total = row["total"]
    if isinstance(total, bool) or not isinstance(total, int):
        raise ValueError("total must be an integer")
    return HelmOnCallProjection(
        schema_version=_require_non_empty_string(row["schema_version"], "schema_version"),
        state=state,
        on_call_count=on_call_count,
        total=total,
        seats=seats,
        evaluated_at=_parse_rfc3339(row["evaluated_at"], "evaluated_at"),
        runtime_epoch=_require_non_empty_string(row["runtime_epoch"], "runtime_epoch"),
    )
