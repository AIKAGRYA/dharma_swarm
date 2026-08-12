"""Base types and invariants for the fixed Helm route-truth census.

This module contains no positive-verdict constructor.  Authoritative
``ON_CALL`` construction lives only in :mod:`helm_route_truth_evaluator`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from typing import Any, Mapping


ROUTE_VERIFICATION_SCHEMA_VERSION = "dharma.helm.route_verification.v1"
HELM_ON_CALL_PROJECTION_SCHEMA_VERSION = "dharma.helm.on_call_projection.v1"
ACCEPTED_ROUTE_VERIFIER_ID = "dharma.route_verifier"
ACCEPTED_ROUTE_VERIFIER_VERSION = "1.0.0"
MAX_ROUTE_VERIFICATION_TTL = timedelta(hours=24)

_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


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
