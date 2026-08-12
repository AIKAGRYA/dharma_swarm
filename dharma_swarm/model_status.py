"""Canonical model-status projection for router and operator surfaces.

This module is intentionally read-only: it projects the model pool plus safe
``dkeys`` status rows into one machine-readable contract. It never reads key
values, constructs providers, or makes model calls.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import InitVar, asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import os
from pathlib import Path
import re
from typing import AbstractSet, Any, Iterable, Mapping

from dharma_swarm import key_oracle
from dharma_swarm.model_live_results import (
    TRANSIENT_LIVE_FAILURES as _TRANSIENT_LIVE_FAILURES,
    load_live_call_results,
)
from dharma_swarm import model_pool
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.model_pool import ModelEntry, Route
from dharma_swarm.models import ProviderType

MODEL_STATUS_SCHEMA_VERSION = "dharma.model_status.v1"
ROUTE_VERIFICATION_SCHEMA_VERSION = "dharma.helm.route_verification.v1"
HELM_ON_CALL_PROJECTION_SCHEMA_VERSION = "dharma.helm.on_call_projection.v1"
ACCEPTED_ROUTE_VERIFIER_ID = "dharma.route_verifier"
ACCEPTED_ROUTE_VERIFIER_VERSION = "1.0.0"
MAX_ROUTE_VERIFICATION_TTL = timedelta(hours=24)
LIVE_MODEL_E2E_ENV = "DHARMA_LIVE_MODEL_E2E"
PROFILE_PATH_ENV = "DHARMA_MODEL_PROFILE_PATH"
LIVE_CALL_MATRIX_PATH_ENV = "DHARMA_MODEL_LIVE_CALL_MATRIX_PATH"
LIVE_CALL_MATRIX_DIR_ENV = "DHARMA_MODEL_LIVE_CALL_MATRIX_DIR"
LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV = "DHARMA_MODEL_LIVE_CALL_MATRIX_MAX_AGE_HOURS"

_PROFILE_FILE_NAME = "model_pool_profiles.json"
_DEFAULT_LIVE_CALL_MATRIX_MAX_AGE_HOURS = 24.0
_LIVE_CALL_MATRIX_GLOBS = ("provider_live_matrix_*.json",)

_PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic",
    "claude_code": "Claude Code",
    "codex": "Codex",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "openrouter_free": "OpenRouter Free",
    "ollama": "Ollama",
    "nvidia_nim": "NVIDIA NIM",
    "google_ai": "Google AI",
    "deepseek": "DeepSeek",
    "kimi": "Kimi",
    "minimax": "MiniMax",
    "qwen": "Qwen",
    "local": "Local",
}

_PROVIDER_URLS: dict[str, str] = {
    "anthropic": "https://docs.anthropic.com/",
    "claude_code": "https://docs.anthropic.com/",
    "codex": "https://platform.openai.com/docs/",
    "openai": "https://platform.openai.com/docs/",
    "openrouter": "https://openrouter.ai/docs/",
    "openrouter_free": "https://openrouter.ai/docs/",
    "ollama": "https://docs.ollama.com/",
    "nvidia_nim": "https://docs.nvidia.com/nim/",
    "google_ai": "https://ai.google.dev/",
    "deepseek": "https://api-docs.deepseek.com/",
    "kimi": "https://platform.moonshot.ai/docs/",
    "minimax": "https://www.minimax.io/platform/document",
    "qwen": "https://help.aliyun.com/zh/model-studio/",
    "local": "https://docs.ollama.com/",
}

_SAFE_DKEYS_FIELDS = (
    "glyph",
    "provider",
    "cluster",
    "http",
    "status",
    "env_var",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_POSITIVE_VERDICT_AUTHORITY = object()


class RouteVerdict(str, Enum):
    """Python-owned verdict for one fixed Helm seat."""

    ON_CALL = "ON_CALL"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    CLOCK_SKEW = "CLOCK_SKEW"


class HelmOnCallState(str, Enum):
    """Aggregate state for the fixed seven-seat census."""

    ON_CALL = "ON_CALL"
    LIVE_DEGRADED = "LIVE_DEGRADED"
    CLOCK_SKEW = "CLOCK_SKEW"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class HelmSeat:
    seat_id: str
    display_label: str
    logical_lineage: str
    admissible_served_identities: tuple[tuple[str, str], ...]


HELM_SLICE1_SEATS: tuple[HelmSeat, ...] = (
    HelmSeat(
        "fable-5",
        "Fable 5",
        "fable-5",
        (("claude_code", "claude-fable-5"), ("fable", "fable-5")),
    ),
    HelmSeat(
        "gpt-5.6",
        "GPT 5.6",
        "openai-gpt-5.6",
        (("codex", "gpt-5.6"), ("openai", "gpt-5.6")),
    ),
    HelmSeat(
        "grok-4.5-4.6-lineage",
        "Grok 4.5/4.6",
        "xai-grok-4.5-4.6",
        (
            ("openrouter", "x-ai/grok-4.5"),
            ("openrouter", "x-ai/grok-4.6"),
            ("xai", "grok-4.5"),
            ("xai", "grok-4.6"),
        ),
    ),
    HelmSeat(
        "fugu-ultra",
        "Fugu Ultra",
        "sakana-fugu-ultra",
        (("sakana", "fugu-ultra"),),
    ),
    HelmSeat(
        "kimi-k3",
        "Kimi K3",
        "moonshot-kimi-k3",
        (
            ("kimi_code", "k3"),
            ("moonshot", "kimi-k3"),
            ("openrouter", "moonshotai/kimi-k3"),
        ),
    ),
    HelmSeat(
        "opus-5.0",
        "Opus 5.0",
        "anthropic-opus-5.0",
        (
            ("claude_code", "claude-opus-5.0"),
            ("anthropic", "claude-opus-5-0"),
        ),
    ),
    HelmSeat(
        "opus-4.8",
        "Opus 4.8",
        "anthropic-opus-4.8",
        (
            ("claude_code", "claude-opus-4.8"),
            ("anthropic", "claude-opus-4-8"),
        ),
    ),
)

_HELM_SEAT_BY_ID = {seat.seat_id: seat for seat in HELM_SLICE1_SEATS}
_HELM_SEAT_INDEX = {seat.seat_id: index for index, seat in enumerate(HELM_SLICE1_SEATS)}


@dataclass(frozen=True, slots=True)
class RouteEvidence:
    """Untrusted evidence input. A successful value is not itself authority."""

    seat_id: str | None
    logical_lineage: str | None
    requested_provider: str | None
    requested_model: str | None
    served_provider: str | None
    served_model: str | None
    success: bool | None
    synthetic: bool | None
    observed_at: datetime | None
    expires_at: datetime | None
    verifier_id: str | None
    verifier_version: str | None
    verifier_accepted: bool | None
    receipt_ref: str | None
    receipt_sha256: str | None
    runtime_epoch: str | None


@dataclass(frozen=True, slots=True)
class SanitizedRouteEvidence:
    """Safe evidence identity carried on the terminal wire."""

    seat_id: str | None
    logical_lineage: str | None
    requested_provider: str | None
    requested_model: str | None
    served_provider: str | None
    served_model: str | None
    observed_at: datetime | None
    expires_at: datetime | None
    age_seconds: int | None
    verifier_id: str | None
    verifier_version: str | None
    receipt_ref: str | None
    receipt_sha256: str | None
    runtime_epoch: str | None


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
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be a non-empty string")


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
        if self.total != len(HELM_SLICE1_SEATS):
            raise ValueError("Helm projection total must be seven")
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
        if isinstance(self.on_call_count, bool) or self.on_call_count != positive_count:
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


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _is_aware_datetime(value: Any) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _require_aware_datetime(value: Any, field_name: str) -> datetime:
    if not _is_aware_datetime(value):
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _format_rfc3339(value: datetime) -> str:
    _require_aware_datetime(value, "timestamp")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_rfc3339(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or _RFC3339_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be an RFC 3339 timestamp")
    candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an RFC 3339 timestamp") from exc
    return _require_aware_datetime(parsed, field_name)


def _parse_optional_rfc3339(value: Any, field_name: str) -> datetime | None:
    return None if value is None else _parse_rfc3339(value, field_name)


def _strict_keys(data: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping) or set(data) != expected:
        raise ValueError(f"{label} must contain exactly {sorted(expected)}")
    return data


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    return value


def _optional_bool(value: Any, field_name: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} must be a boolean or null")


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
    if _HELM_SEAT_BY_ID.get(seat.seat_id) != seat:
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

@dataclass(frozen=True, slots=True)
class RouteStatus:
    provider: str
    model_id: str
    route: str
    status: str
    reason: str | None
    dkeys_row: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ModelVerification:
    status: str
    verified_at: str | None = None
    response_preview: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ModelStatus:
    id: str
    rank: int
    provider: str
    display_name: str
    ui_label: str
    custom_label: str | None
    short_name: str | None
    tier: str
    lane: str
    below_floor: bool
    max_context: int
    strengths: list[str]
    available: bool
    status: str
    unavailable_reason: str | None
    available_routes: list[str]
    routes: list[str]
    route_statuses: list[RouteStatus]
    notes: str | None
    docs_url: str
    provider_url: str
    verification: ModelVerification


@dataclass(frozen=True, slots=True)
class ModelStatusProjection:
    schema_version: str
    generated_at: str
    oracle_state: str
    live_providers: list[str] | None
    models: list[ModelStatus]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _profile_path(path: Path | None = None) -> Path:
    if path is not None:
        return path
    raw = os.getenv(PROFILE_PATH_ENV)
    if raw:
        return Path(raw).expanduser()
    return dharma_state_dir() / _PROFILE_FILE_NAME


def load_profiles(path: Path | None = None) -> dict[str, dict[str, str | None]]:
    target = _profile_path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, str | None]] = {}
    for model_id, profile in data.items():
        if not isinstance(model_id, str) or not isinstance(profile, dict):
            continue
        custom_label = profile.get("custom_label")
        short_name = profile.get("short_name")
        out[model_id] = {
            "custom_label": custom_label if isinstance(custom_label, str) else None,
            "short_name": short_name if isinstance(short_name, str) else None,
        }
    return out


def save_profile(
    model_id: str,
    *,
    custom_label: str | None,
    short_name: str | None,
    path: Path | None = None,
) -> dict[str, str | None]:
    profiles = load_profiles(path)
    profile = {
        "custom_label": _clean_profile_text(custom_label),
        "short_name": _clean_profile_text(short_name),
    }
    profiles[model_id] = profile
    target = _profile_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profiles, indent=2, sort_keys=True), encoding="utf-8")
    return profile


def _clean_profile_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split()).strip()
    return cleaned[:80] if cleaned else None


def _status_data() -> dict[str, Any] | None:
    loader = getattr(key_oracle, "_load_status")
    data = loader()
    return data if isinstance(data, dict) else None


def _live_call_matrix_path() -> Path | None:
    raw = os.getenv(LIVE_CALL_MATRIX_PATH_ENV)
    if not raw:
        return _discover_live_call_matrix_path()
    return Path(raw).expanduser()


def _live_call_matrix_dir() -> Path:
    raw = os.getenv(LIVE_CALL_MATRIX_DIR_ENV)
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[1] / "reports" / "langgraph_parity" / "allnight"


def _live_call_matrix_max_age_hours() -> float:
    raw = os.getenv(LIVE_CALL_MATRIX_MAX_AGE_HOURS_ENV)
    if not raw:
        return _DEFAULT_LIVE_CALL_MATRIX_MAX_AGE_HOURS
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return _DEFAULT_LIVE_CALL_MATRIX_MAX_AGE_HOURS


def _parse_receipt_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _receipt_generated_at(path: Path) -> datetime | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    schema = str(data.get("schema_version") or "")
    if schema and schema != "dharma.provider_live_matrix_closeout.v1":
        return None
    parsed = _parse_receipt_time(data.get("generated_at"))
    if parsed is not None:
        return parsed
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None


def _discover_live_call_matrix_path(now: datetime | None = None) -> Path | None:
    directory = _live_call_matrix_dir()
    if not directory.exists():
        return None
    current = now or datetime.now(timezone.utc)
    max_age = _live_call_matrix_max_age_hours()
    candidates: list[tuple[datetime, Path]] = []
    for pattern in _LIVE_CALL_MATRIX_GLOBS:
        for path in directory.glob(pattern):
            if not path.is_file():
                continue
            generated_at = _receipt_generated_at(path)
            if generated_at is None:
                continue
            age_hours = max((current - generated_at).total_seconds(), 0.0) / 3600.0
            if age_hours <= max_age:
                candidates.append((generated_at, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1].name))[1]


def _live_call_results(path: Path | None = None) -> dict[str, dict[str, Any]]:
    target = path or _live_call_matrix_path()
    return load_live_call_results(target)


def _provider_row_key(provider: ProviderType | str) -> str | None:
    provider_name = provider.value if isinstance(provider, ProviderType) else str(provider)
    mapping = getattr(key_oracle, "_PROVIDER_TO_ROW")
    return mapping.get(provider_name, provider_name)


def _safe_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    return {field: row.get(field) for field in _SAFE_DKEYS_FIELDS if field in row}


def _row_for_provider(provider: ProviderType, status_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if status_data is None:
        return None
    rows = status_data.get("rows")
    if not isinstance(rows, dict):
        return None
    row_key = _provider_row_key(provider)
    if row_key is None:
        return None
    return rows.get(row_key) if isinstance(rows.get(row_key), dict) else None


def _classify_route(
    route: Route,
    *,
    live: set[str] | None,
    status_data: dict[str, Any] | None,
    live_results: dict[str, dict[str, Any]],
) -> RouteStatus:
    route_id = f"{route.provider.value}:{route.model_id}"
    live_result = live_results.get(route_id)
    if live_result is not None:
        result_status = str(live_result.get("status", "")).strip()
        if result_status == "ok":
            return RouteStatus(
                provider=route.provider.value,
                model_id=route.model_id,
                route=route_id,
                status="live_routable",
                reason=None,
                dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
            )
        if result_status == "failed":
            reason = str(live_result.get("failure_class") or "routing_bug")
            if reason in _TRANSIENT_LIVE_FAILURES:
                return RouteStatus(
                    provider=route.provider.value,
                    model_id=route.model_id,
                    route=route_id,
                    status="live_routable",
                    reason=None,
                    dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
                )
            return RouteStatus(
                provider=route.provider.value,
                model_id=route.model_id,
                route=route_id,
                status="unavailable",
                reason=reason,
                dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
            )
    if live is None:
        return RouteStatus(
            provider=route.provider.value,
            model_id=route.model_id,
            route=route_id,
            status="unverified",
            reason="key_status_unknown",
            dkeys_row=None,
        )
    if route.provider.value in live:
        return RouteStatus(
            provider=route.provider.value,
            model_id=route.model_id,
            route=route_id,
            status="live_routable",
            reason=None,
            dkeys_row=_safe_row(_row_for_provider(route.provider, status_data)),
        )
    row = _row_for_provider(route.provider, status_data)
    reason = _classify_unavailable_reason(row)
    return RouteStatus(
        provider=route.provider.value,
        model_id=route.model_id,
        route=route_id,
        status="unavailable",
        reason=reason,
        dkeys_row=_safe_row(row),
    )


def _classify_unavailable_reason(row: dict[str, Any] | None) -> str:
    if row is None:
        return "key_missing"
    glyph = str(row.get("glyph", "")).strip()
    http = str(row.get("http", "")).strip()
    status = str(row.get("status", "")).lower()
    if glyph == "·" or "no key" in status:
        return "key_missing"
    if glyph == "$" or "funds=0" in status or "insufficient" in status:
        return "quota"
    if glyph == "~" or http == "429" or "rate" in status:
        return "rate_limited"
    if "model" in status and ("missing" in status or "not found" in status):
        return "model_missing"
    if http == "404":
        return "provider_dead"
    if http == "400" or http == "401" or http == "403" or glyph == "✗":
        return "provider_dead"
    return "provider_dead"


def _dominant_reason(route_statuses: Iterable[RouteStatus]) -> str | None:
    reasons = [route.reason for route in route_statuses if route.reason]
    if not reasons:
        return None
    for reason in (
        "key_status_unknown",
        "key_missing",
        "rate_limited",
        "quota",
        "model_missing",
        "provider_dead",
        "unsupported_route",
        "timeout",
        "schema_failure",
        "routing_bug",
    ):
        if reason in reasons:
            return reason
    return reasons[0]


def _verification_for_model(
    model_id: str,
    route_statuses: Iterable[RouteStatus],
    live_results: dict[str, dict[str, Any]],
) -> ModelVerification:
    for route_status in route_statuses:
        live_result = live_results.get(route_status.route)
        if live_result is None:
            continue
        verified_at = live_result.get("started_at") if isinstance(live_result.get("started_at"), str) else None
        if live_result.get("status") == "ok":
            preview = live_result.get("response_preview")
            return ModelVerification(
                status="verified",
                verified_at=verified_at,
                response_preview=preview if isinstance(preview, str) else None,
                error=None,
            )
        error = live_result.get("reason") or live_result.get("error") or live_result.get("failure_class")
        return ModelVerification(
            status="failed",
            verified_at=verified_at,
            response_preview=None,
            error=str(error) if error else "Live model-call receipt failed.",
        )
    return ModelVerification(
        status="unverified",
        verified_at=None,
        response_preview=None,
        error="No live model-call receipt has been recorded for this projection.",
    )


def _model_status(
    entry: ModelEntry,
    *,
    rank: int,
    live: set[str] | None,
    status_data: dict[str, Any] | None,
    live_results: dict[str, dict[str, Any]],
    profiles: dict[str, dict[str, str | None]],
) -> ModelStatus:
    route_statuses = [
        _classify_route(route, live=live, status_data=status_data, live_results=live_results)
        for route in entry.routes
    ]
    available_routes = [
        route_status.route
        for route_status in route_statuses
        if route_status.status == "live_routable"
    ]
    has_live_evidence = any(live_results.get(route_status.route) is not None for route_status in route_statuses)
    oracle_unknown = live is None and not has_live_evidence
    available = bool(available_routes)
    status = "unverified" if oracle_unknown else ("live_routable" if available else "unavailable")
    reason = "key_status_unknown" if oracle_unknown else _dominant_reason(route_statuses)
    primary_route = route_statuses[0]
    profile = profiles.get(entry.id, {})
    label = profile.get("custom_label") or entry.display
    provider = primary_route.provider
    return ModelStatus(
        id=entry.id,
        rank=rank,
        provider=provider,
        display_name=entry.display,
        ui_label=label,
        custom_label=profile.get("custom_label"),
        short_name=profile.get("short_name"),
        tier=entry.tier.value,
        lane="grunt" if entry.below_floor else "floor",
        below_floor=entry.below_floor,
        max_context=entry.context,
        strengths=list(entry.caps),
        available=available,
        status=status,
        unavailable_reason=reason if not available else None,
        available_routes=available_routes,
        routes=[route_status.route for route_status in route_statuses],
        route_statuses=route_statuses,
        notes=_notes_for(entry, status=status, reason=reason),
        docs_url=_PROVIDER_URLS.get(provider, "https://docs.dharma.local/models"),
        provider_url=_PROVIDER_URLS.get(provider, "https://docs.dharma.local/models"),
        verification=_verification_for_model(entry.id, route_statuses, live_results),
    )


def _notes_for(entry: ModelEntry, *, status: str, reason: str | None) -> str:
    if entry.below_floor:
        return "Sub-floor model: grunt-only, never part of the default operator path."
    if status == "live_routable":
        return "Live-routable by current key oracle; live model-call receipt still required for verified status."
    if status == "unverified":
        return "Key status is missing or stale; surface must not advertise this model as callable."
    return f"Unavailable: {reason or 'no live route'}."


def project_model_status(
    *,
    entries: Iterable[ModelEntry] | None = None,
    profiles_path: Path | None = None,
) -> ModelStatusProjection:
    live = key_oracle.live_providers()
    status_data = _status_data()
    live_results = _live_call_results()
    profiles = load_profiles(profiles_path)
    selected = list(entries) if entries is not None else list(model_pool.all_entries())
    models = [
        _model_status(
            entry,
            rank=index,
            live=live,
            status_data=status_data,
            live_results=live_results,
            profiles=profiles,
        )
        for index, entry in enumerate(selected, start=1)
    ]
    return ModelStatusProjection(
        schema_version=MODEL_STATUS_SCHEMA_VERSION,
        generated_at=_utc_now(),
        oracle_state="unknown" if live is None else "fresh",
        live_providers=sorted(live) if live is not None else None,
        models=models,
    )


def floor_model_status(*, profiles_path: Path | None = None) -> ModelStatusProjection:
    return project_model_status(entries=model_pool.floor_entries(), profiles_path=profiles_path)


def all_model_status(*, profiles_path: Path | None = None) -> ModelStatusProjection:
    return project_model_status(entries=model_pool.all_entries(), profiles_path=profiles_path)


def projection_to_dict(projection: ModelStatusProjection) -> dict[str, Any]:
    return asdict(projection)


def top_floor_models_for_dashboard(*, profiles_path: Path | None = None) -> list[dict[str, Any]]:
    projection = floor_model_status(profiles_path=profiles_path)
    return [asdict(model) for model in projection.models]


def verify_floor_models(*, profiles_path: Path | None = None) -> dict[str, Any]:
    projection = floor_model_status(profiles_path=profiles_path)
    verified_at = _utc_now()
    live_enabled = os.getenv(LIVE_MODEL_E2E_ENV) == "1"
    if not live_enabled:
        return {
            "verified_at": verified_at,
            "ok_count": 0,
            "live_calls_attempted": False,
            "skipped_count": len(projection.models),
            "reason": f"{LIVE_MODEL_E2E_ENV}=1 is required for live model calls.",
        }
    return {
        "verified_at": verified_at,
        "ok_count": 0,
        "live_calls_attempted": False,
        "skipped_count": len(projection.models),
        "reason": "Live verification is performed by scripts/verify/model_pool_e2e.py receipts, not this API route.",
    }


__all__ = [
    "ACCEPTED_ROUTE_VERIFIER_ID",
    "ACCEPTED_ROUTE_VERIFIER_VERSION",
    "HELM_ON_CALL_PROJECTION_SCHEMA_VERSION",
    "HELM_SLICE1_SEATS",
    "LIVE_MODEL_E2E_ENV",
    "MAX_ROUTE_VERIFICATION_TTL",
    "MODEL_STATUS_SCHEMA_VERSION",
    "ROUTE_VERIFICATION_SCHEMA_VERSION",
    "HelmOnCallProjection",
    "HelmOnCallState",
    "HelmSeat",
    "ModelStatus",
    "ModelStatusProjection",
    "ModelVerification",
    "RouteEvidence",
    "RouteStatus",
    "RouteVerdict",
    "RouteVerification",
    "SanitizedRouteEvidence",
    "all_model_status",
    "evaluate_route_verification",
    "floor_model_status",
    "helm_on_call_projection_from_dict",
    "helm_on_call_projection_to_dict",
    "load_profiles",
    "project_helm_on_call",
    "projection_to_dict",
    "route_evidence_from_dict",
    "route_verification_from_dict",
    "route_verification_to_dict",
    "save_profile",
    "top_floor_models_for_dashboard",
    "unknown_helm_on_call_projection",
    "verify_floor_models",
]
