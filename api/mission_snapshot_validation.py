"""Strict wire validation for the derived Mission Control campaign projection."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

CAMPAIGN_PROJECTION_SCHEMA_VERSION = "dharma.mission_control.read_model.v1"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_MAX_CLOCK_SKEW = timedelta(seconds=5)
_RECONCILIATION_STATES = frozenset(
    "coherent needs_task_projection missing_terminal_receipt "
    "conflicting_active_claims active_claim_without_run expired_lease "
    "evidence_scan_saturated foreign_runtime_record "
    "conflicting_terminal_evidence".split()
)
_VIEW_ID_FIELDS = {
    "tasks": ("task_id", "mission_id"),
    "attempts": ("attempt_id", "mission_id", "session_id", "task_id", "claim_id"),
    "leases": ("claim_id", "mission_id", "session_id", "task_id", "attempt_id"),
    "receipts": ("receipt_id", "mission_id", "task_id", "attempt_id"),
}
_SNAPSHOT_FIELDS = frozenset(
    "mission tasks attempts leases receipts reconciliation observed_at authority "
    "proves_executor_liveness".split()
)
_MISSION_FIELDS = frozenset(
    "mission_id session_id title goal operator_id status metadata created_at updated_at".split()
)
_VIEW_FIELDS = {
    "tasks": frozenset(
        "task_id mission_id title description status priority assigned_to result "
        "metadata created_at updated_at".split()
    ),
    "attempts": frozenset(
        "attempt_id mission_id session_id task_id claim_id assigned_to assigned_by "
        "status failure_code idempotency_key metadata started_at completed_at".split()
    ),
    "leases": frozenset(
        "claim_id mission_id session_id task_id agent_id attempt_id status active "
        "expired heartbeat_at stale_after metadata".split()
    ),
    "receipts": frozenset(
        "receipt_id mission_id task_id attempt_id agent_id receipt_type status "
        "idempotency_key payload created_at".split()
    ),
}
_VIEW_STRING_FIELDS = {
    "tasks": frozenset(
        "task_id mission_id title description status priority assigned_to result".split()
    ),
    "attempts": frozenset(
        "attempt_id mission_id session_id task_id claim_id assigned_to assigned_by "
        "status failure_code idempotency_key".split()
    ),
    "leases": frozenset(
        "claim_id mission_id session_id task_id agent_id attempt_id status".split()
    ),
    "receipts": frozenset(
        "receipt_id mission_id task_id attempt_id agent_id receipt_type status "
        "idempotency_key".split()
    ),
}
_VIEW_TIME_FIELDS = {
    "tasks": ("created_at", "updated_at"),
    "attempts": ("started_at", "completed_at"),
    "leases": ("heartbeat_at", "stale_after"),
    "receipts": ("created_at",),
}


class MissionSnapshotReadError(RuntimeError):
    """The configured projection did not satisfy secure read admission."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MissionSnapshotReadError(message)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MissionSnapshotReadError("campaign projection contains duplicate keys")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> None:
    raise MissionSnapshotReadError(
        f"campaign projection contains non-finite JSON constant {value}"
    )


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise MissionSnapshotReadError(f"campaign projection {field} is not a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MissionSnapshotReadError(
            f"campaign projection {field} is not ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MissionSnapshotReadError(
            f"campaign projection {field} must be timezone-aware"
        )
    return parsed.astimezone(timezone.utc)


def canonical_digest(payload: dict[str, Any]) -> str:
    """Digest canonical JSON while excluding the outer self-digest field."""
    digest_payload = dict(payload)
    digest_payload.pop("projection_content_digest", None)
    try:
        encoded = json.dumps(
            digest_payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MissionSnapshotReadError(
            "campaign projection is not canonical JSON"
        ) from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_campaign_projection(
    content: bytes,
    *,
    mission_id: str,
    config_digest: str,
    minimum_generation: int,
    max_age_seconds: float,
    now: datetime,
) -> tuple[dict[str, Any], int, int, str]:
    """Return the nested snapshot and monotonic wire identity or fail closed."""
    try:
        decoded = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise MissionSnapshotReadError(
            "campaign projection is not strict UTF-8"
        ) from exc
    try:
        payload = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, MissionSnapshotReadError):
            raise
        raise MissionSnapshotReadError(
            "campaign projection is not strict JSON"
        ) from exc
    _require(isinstance(payload, dict), "campaign projection must be an object")
    supplied_digest = payload.get("projection_content_digest")
    _require(
        isinstance(supplied_digest, str)
        and bool(_SHA256_RE.fullmatch(supplied_digest)),
        "campaign projection content digest is missing or malformed",
    )
    _require(
        hmac.compare_digest(supplied_digest, canonical_digest(payload)),
        "campaign projection content digest does not match",
    )
    _require(
        payload.get("projection_schema_version")
        == CAMPAIGN_PROJECTION_SCHEMA_VERSION
        and payload.get("projection_kind") == "derived_read_model"
        and payload.get("canonical_state_copied") is False,
        "campaign projection schema or read-model kind is unsupported",
    )
    _require(
        payload.get("mission_id") == mission_id
        and payload.get("session_id") == f"mission_campaign:{mission_id}"
        and payload.get("config_digest") == config_digest,
        "campaign projection identity does not match configuration",
    )
    generation = payload.get("generation")
    _require(
        not isinstance(generation, bool)
        and isinstance(generation, int)
        and generation >= minimum_generation,
        "campaign projection generation is below the admitted floor",
    )
    cycle_sequence = payload.get("cycle_sequence")
    _require(
        not isinstance(cycle_sequence, bool)
        and isinstance(cycle_sequence, int)
        and cycle_sequence >= 0,
        "campaign projection cycle sequence is invalid",
    )
    freshness = payload.get("freshness_seconds")
    _require(
        not isinstance(freshness, bool)
        and isinstance(freshness, (int, float))
        and math.isfinite(float(freshness))
        and 0 < float(freshness) <= max_age_seconds,
        "campaign projection freshness budget is invalid",
    )

    snapshot = payload.get("mission_snapshot")
    _require(isinstance(snapshot, dict), "nested MissionSnapshot is missing")
    _require(
        set(snapshot) == _SNAPSHOT_FIELDS,
        "nested MissionSnapshot has a foreign top-level shape",
    )
    mission = snapshot.get("mission")
    _require(
        isinstance(mission, dict)
        and set(mission) == _MISSION_FIELDS
        and mission.get("mission_id") == mission_id
        and mission.get("session_id") == f"mission:{mission_id}",
        "nested MissionSnapshot identity is foreign",
    )
    _require(
        all(
            isinstance(mission[name], str)
            for name in ("mission_id", "session_id", "title", "goal", "operator_id", "status")
        )
        and isinstance(mission["metadata"], dict)
        and all(
            mission[name] is None or isinstance(mission[name], str)
            for name in ("created_at", "updated_at")
        ),
        "nested MissionSnapshot mission has foreign field types",
    )
    reconciliation = snapshot.get("reconciliation")
    _require(
        reconciliation in _RECONCILIATION_STATES
        and snapshot.get("authority") == "TaskBoard+RuntimeStateStore"
        and snapshot.get("proves_executor_liveness") is False,
        "nested MissionSnapshot claims are outside the producer contract",
    )
    foreign_runtime = False
    for field, identity_fields in _VIEW_ID_FIELDS.items():
        rows = snapshot.get(field)
        _require(
            isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
            f"nested MissionSnapshot {field} has a foreign view shape",
        )
        _require(
            all(set(row) == _VIEW_FIELDS[field] for row in rows),
            f"nested MissionSnapshot {field} has a foreign field set",
        )
        _require(
            all(
                all(isinstance(row[name], str) for name in _VIEW_STRING_FIELDS[field])
                and isinstance(
                    row["payload" if field == "receipts" else "metadata"], dict
                )
                and all(
                    row[name] is None or isinstance(row[name], str)
                    for name in _VIEW_TIME_FIELDS[field]
                )
                and (
                    field != "leases"
                    or (
                        isinstance(row["active"], bool)
                        and isinstance(row["expired"], bool)
                    )
                )
                for row in rows
            ),
            f"nested MissionSnapshot {field} has foreign field types",
        )
        _require(
            all(
                all(isinstance(row.get(name), str) for name in identity_fields)
                for row in rows
            ),
            f"nested MissionSnapshot {field} has a foreign identity shape",
        )
        _require(
            field != "tasks"
            or all(row["mission_id"] == mission_id for row in rows),
            "nested MissionSnapshot task is foreign",
        )
        if field in {"attempts", "leases"}:
            foreign_runtime = foreign_runtime or any(
                row["mission_id"] != mission_id
                or row["session_id"] != f"mission:{mission_id}"
                for row in rows
            )
        elif field == "receipts":
            _require(
                all(row["mission_id"] == mission_id for row in rows),
                "nested MissionSnapshot receipt is foreign",
            )
    _require(
        not foreign_runtime or reconciliation == "foreign_runtime_record",
        "nested MissionSnapshot foreign runtime is not reconciled",
    )
    observed = _parse_timestamp(payload.get("observed_at"), "observed_at")
    published = _parse_timestamp(payload.get("published_at"), "published_at")
    nested_observed = _parse_timestamp(
        snapshot.get("observed_at"), "mission_snapshot.observed_at"
    )
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("mission snapshot provider clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    _require(
        all(
            item <= now + _MAX_CLOCK_SKEW
            for item in (observed, published, nested_observed)
        ),
        "campaign projection contains a future observation",
    )
    _require(
        nested_observed <= observed <= published
        and (
            cycle_sequence != 0
            or (
                payload.get("latest_cycle_at") is None
                and payload.get("fresh_until") is None
            )
        ),
        "campaign projection timestamp or zero-cycle shape is inconsistent",
    )
    max_age = timedelta(seconds=max_age_seconds)
    _require(
        now - nested_observed <= max_age
        and now - observed <= max_age
        and now - published <= max_age,
        "campaign projection is stale",
    )
    if cycle_sequence > 0:
        latest = _parse_timestamp(payload.get("latest_cycle_at"), "latest_cycle_at")
        fresh_until = _parse_timestamp(payload.get("fresh_until"), "fresh_until")
        _require(
            latest <= observed
            and latest <= now + _MAX_CLOCK_SKEW
            and fresh_until == latest + timedelta(seconds=float(freshness)),
            "campaign projection timestamp ordering is inconsistent",
        )
        _require(now <= fresh_until, "campaign projection is stale")
    return (
        snapshot,
        generation,
        cycle_sequence,
        canonical_digest({"mission_snapshot": snapshot}),
    )
