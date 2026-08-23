"""Strict wire validation for the derived Mission Control campaign projection."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

CAMPAIGN_PROJECTION_SCHEMA_VERSION = "dharma.mission_control.read_model.v1"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_MAX_CLOCK_SKEW = timedelta(seconds=5)
_MAX_SAFE_INTEGER = (1 << 53) - 1
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
CAMPAIGN_EVIDENCE_SCHEMA_VERSION = "dharma.mission_control.campaign_evidence.v1"
OPERATOR_CONTROL_EVIDENCE_SCHEMA_VERSION = (
    "dharma.sadhana.operator_control_evidence.v1"
)
_OPERATOR_CONTROL_STATE_SCHEMA_VERSION = "dharma.sadhana.operator_control_state.v1"
_OPERATOR_CONTROL_STATE_FIELDS = frozenset(
    "schema_version control_state campaign_generation transition_sequence request_id "
    "idempotency_key action source_envelope_sha256 authority_receipt_ref "
    "authority_receipt_sha256 authority_applied_at effect_state effect_receipt_ref "
    "effect_receipt_sha256 effect_observed_at".split()
)
_OPERATOR_CONTROL_ACTION_STATES = {
    "pause": "PAUSED",
    "resume": "RUNNING",
    "emergency_stop": "STOPPED_TERMINAL",
}
_OPERATOR_CONTROL_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_CAMPAIGN_AUTHORITY = "TaskBoard+RuntimeStateStore+owner execution projection"
_OWNER_EXECUTION_FIELDS = frozenset(
    "ref task_status run_status claim_status stale receipt_ids terminal succeeded "
    "result failure_code observed_at proves_executor_liveness".split()
)
_OWNER_REF_FIELDS = frozenset(
    "backend mission_id task_id dispatch_key run_id claim_id agent_id "
    "idempotency_key owner_session_id".split()
)
_OWNER_RUN_STATUSES = frozenset({"claimed", "running", "completed", "failed"})
_OWNER_TERMINAL_STATUSES = frozenset({"completed", "failed"})
_VERDICT_FIELDS = (
    "candidate_task_ids",
    "accepted_task_ids",
    "rejected_task_ids",
    "conflicting_acceptance_task_ids",
)
_ACCEPTANCE_STATES = frozenset(
    {"unobserved", "candidate_only", "accepted", "rejected", "conflicting"}
)


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


def _identifier(value: Any, field: str) -> str:
    _require(
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= 500
        and not any(character.isspace() for character in value),
        f"campaign projection {field} is not a bounded canonical identifier",
    )
    return value


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _task_owner_stamp(
    task: dict[str, Any],
    *,
    mission_id: str,
    task_id: str,
    dispatch_key: str,
    run_id: str,
    idempotency_key: str,
) -> None:
    metadata = task.get("metadata")
    marker = (
        metadata.get("mission_control_owner_execution")
        if isinstance(metadata, dict)
        else None
    )
    _require(
        isinstance(marker, dict)
        and marker.get("schema_version")
        == "dharma.mission_control.owner_execution.v1"
        and marker.get("backend") == "orchestrator"
        and marker.get("mission_id") == mission_id
        and marker.get("task_id") == task_id
        and marker.get("dispatch_key") == dispatch_key
        and marker.get("run_id") == run_id
        and marker.get("idempotency_key") == idempotency_key,
        "campaign projection owner execution lacks an exact canonical task stamp",
    )
    for compatibility_key in ("runtime_run_id", "run_id", "idempotency_key"):
        expected = run_id if compatibility_key != "idempotency_key" else idempotency_key
        observed = metadata.get(compatibility_key)
        _require(
            observed is None or observed == expected,
            "campaign projection owner execution conflicts with task compatibility identity",
        )


def _validate_owner_executions(
    payload: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    mission_id: str,
    observed: datetime,
    now: datetime,
    max_age: timedelta,
) -> tuple[list[dict[str, Any]], set[str]]:
    raw = payload.get("owner_executions")
    _require(
        isinstance(raw, list) and len(raw) <= len(snapshot["tasks"]),
        "campaign projection owner_executions is not bounded by mission tasks",
    )
    tasks = {task["task_id"]: task for task in snapshot["tasks"]}
    projected: list[dict[str, Any]] = []
    task_ids: set[str] = set()
    run_ids: set[str] = set()
    succeeded_task_ids: set[str] = set()
    for row in raw:
        _require(
            isinstance(row, dict) and set(row) == _OWNER_EXECUTION_FIELDS,
            "campaign projection owner execution has a foreign field set",
        )
        ref = row.get("ref")
        _require(
            isinstance(ref, dict) and set(ref) == _OWNER_REF_FIELDS,
            "campaign projection owner execution ref has a foreign field set",
        )
        task_id = _identifier(ref.get("task_id"), "owner task_id")
        dispatch_key = _identifier(ref.get("dispatch_key"), "owner dispatch_key")
        run_id = _identifier(ref.get("run_id"), "owner run_id")
        idempotency_key = _identifier(
            ref.get("idempotency_key"), "owner idempotency_key"
        )
        for field in ("claim_id", "agent_id", "owner_session_id"):
            _identifier(ref.get(field), f"owner {field}")
        _require(
            ref.get("backend") == "orchestrator"
            and ref.get("mission_id") == mission_id
            and task_id in tasks,
            "campaign projection owner execution names a foreign owner or task",
        )
        _require(
            run_id == _stable_id("owner_run", mission_id, task_id, dispatch_key)
            and idempotency_key
            == _stable_id("owner_dispatch", mission_id, task_id, dispatch_key),
            "campaign projection owner execution stable identity is invalid",
        )
        _require(
            task_id not in task_ids and run_id not in run_ids,
            "campaign projection owner execution identity is duplicated",
        )
        task_ids.add(task_id)
        run_ids.add(run_id)
        task = tasks[task_id]
        _task_owner_stamp(
            task,
            mission_id=mission_id,
            task_id=task_id,
            dispatch_key=dispatch_key,
            run_id=run_id,
            idempotency_key=idempotency_key,
        )
        run_status = row.get("run_status")
        claim_status = row.get("claim_status")
        task_status = row.get("task_status")
        terminal = row.get("terminal")
        succeeded = row.get("succeeded")
        _require(
            isinstance(run_status, str)
            and run_status in _OWNER_RUN_STATUSES
            and isinstance(claim_status, str)
            and claim_status in _OWNER_RUN_STATUSES
            and isinstance(task_status, str)
            and task_status == task.get("status")
            and isinstance(row.get("stale"), bool)
            and isinstance(terminal, bool)
            and isinstance(succeeded, bool)
            and terminal == (run_status in _OWNER_TERMINAL_STATUSES)
            and succeeded
            == (run_status == "completed" and task_status == "completed")
            and isinstance(row.get("result"), str)
            and isinstance(row.get("failure_code"), str)
            and row.get("proves_executor_liveness") is False,
            "campaign projection owner execution lifecycle is incoherent",
        )
        receipts = row.get("receipt_ids")
        _require(
            isinstance(receipts, list)
            and len(receipts) == len(set(receipts))
            and all(_identifier(item, "owner receipt_id") for item in receipts),
            "campaign projection owner receipt identities are invalid",
        )
        owner_observed = _parse_timestamp(
            row.get("observed_at"), "owner_executions.observed_at"
        )
        _require(
            now - owner_observed <= max_age
            and owner_observed <= observed
            and owner_observed <= now + _MAX_CLOCK_SKEW,
            "campaign projection owner observation is stale or causally invalid",
        )
        if succeeded:
            succeeded_task_ids.add(task_id)
        projected.append(row)
    return projected, succeeded_task_ids


def _validate_verdict_ids(
    payload: dict[str, Any],
    *,
    task_ids: set[str],
) -> dict[str, list[str]]:
    verdicts: dict[str, list[str]] = {}
    for field in _VERDICT_FIELDS:
        values = payload.get(field)
        _require(
            isinstance(values, list)
            and values == sorted(values)
            and len(values) == len(set(values))
            and all(_identifier(value, field) in task_ids for value in values),
            f"campaign projection {field} is not a canonical succeeded-task set",
        )
        verdicts[field] = values
    accepted = set(verdicts["accepted_task_ids"])
    rejected = set(verdicts["rejected_task_ids"])
    conflicting = set(verdicts["conflicting_acceptance_task_ids"])
    _require(
        not accepted.intersection(rejected | conflicting)
        and not rejected.intersection(conflicting),
        "campaign projection acceptance verdict sets overlap",
    )
    expected_state = (
        "conflicting"
        if conflicting
        else "accepted"
        if accepted
        else "rejected"
        if rejected
        else "candidate_only"
        if verdicts["candidate_task_ids"]
        else "unobserved"
    )
    _require(
        payload.get("acceptance_state") in _ACCEPTANCE_STATES
        and payload.get("acceptance_state") == expected_state
        and payload.get("proves_semantic_acceptance") is bool(accepted),
        "campaign projection semantic acceptance claims are incoherent",
    )
    return verdicts


def _campaign_evidence(
    payload: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    mission_id: str,
    observed: datetime,
    now: datetime,
    max_age: timedelta,
) -> dict[str, Any]:
    _require(
        payload.get("authority") == _CAMPAIGN_AUTHORITY,
        "campaign projection evidence authority is unsupported",
    )
    owner_executions, succeeded_task_ids = _validate_owner_executions(
        payload,
        snapshot,
        mission_id=mission_id,
        observed=observed,
        now=now,
        max_age=max_age,
    )
    verdicts = _validate_verdict_ids(payload, task_ids=succeeded_task_ids)
    invalid = payload.get("invalid_acceptance_receipts")
    _require(
        not isinstance(invalid, bool) and isinstance(invalid, int) and invalid >= 0,
        "campaign projection invalid acceptance count is invalid",
    )
    return {
        "schema_version": CAMPAIGN_EVIDENCE_SCHEMA_VERSION,
        "authority": _CAMPAIGN_AUTHORITY,
        "observed_at": payload["observed_at"],
        "owner_executions": owner_executions,
        **verdicts,
        "invalid_acceptance_receipts": invalid,
        "acceptance_state": payload["acceptance_state"],
        "proves_executor_liveness": False,
        "proves_semantic_acceptance": payload["proves_semantic_acceptance"],
    }


def _canonical_utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_receipt_ref(value: Any, field: str) -> str:
    _require(
        isinstance(value, str)
        and len(value) <= 512
        and value == value.strip()
        and value == unicodedata.normalize("NFC", value)
        and not any(unicodedata.category(character).startswith("C") for character in value),
        f"campaign projection {field} is not a bounded canonical receipt ref",
    )
    return value


def _operator_control_evidence(
    payload: dict[str, Any],
    *,
    generation: int,
    observed: datetime,
    now: datetime,
) -> dict[str, Any]:
    _require(
        "operator_login" not in payload,
        "campaign projection contains private operator identity",
    )
    raw = payload.get("operator_control_state")
    _require(
        isinstance(raw, dict) and set(raw) == _OPERATOR_CONTROL_STATE_FIELDS,
        "campaign projection operator control state fields are not exact",
    )
    state = dict(raw)
    sequence = state.get("transition_sequence")
    _require(
        state.get("schema_version") == _OPERATOR_CONTROL_STATE_SCHEMA_VERSION
        and state.get("control_state") in {"RUNNING", "PAUSED", "STOPPED_TERMINAL"}
        and not isinstance(state.get("campaign_generation"), bool)
        and isinstance(state.get("campaign_generation"), int)
        and state.get("campaign_generation") == generation
        and not isinstance(sequence, bool)
        and isinstance(sequence, int)
        and 0 <= sequence <= _MAX_SAFE_INTEGER
        and state.get("action") in {"", *_OPERATOR_CONTROL_ACTION_STATES}
        and state.get("effect_state") in {"unobserved", "observed", "violated"},
        "campaign projection operator control coordinates are invalid",
    )
    text_fields = (
        "request_id",
        "idempotency_key",
        "action",
        "source_envelope_sha256",
        "authority_receipt_ref",
        "authority_receipt_sha256",
        "effect_receipt_ref",
        "effect_receipt_sha256",
    )
    _require(
        all(isinstance(state.get(field), str) for field in text_fields),
        "campaign projection operator control text fields are invalid",
    )
    authority_ref = _bounded_receipt_ref(
        state["authority_receipt_ref"], "operator authority_receipt_ref"
    )
    effect_ref = _bounded_receipt_ref(
        state["effect_receipt_ref"], "operator effect_receipt_ref"
    )
    authority_raw = state.get("authority_applied_at")
    effect_raw = state.get("effect_observed_at")
    _require(
        authority_raw is None or isinstance(authority_raw, str),
        "campaign projection operator authority_applied_at is invalid",
    )
    _require(
        effect_raw is None or isinstance(effect_raw, str),
        "campaign projection operator effect_observed_at is invalid",
    )
    authority_at = (
        None
        if authority_raw is None
        else _parse_timestamp(authority_raw, "operator_control_state.authority_applied_at")
    )
    effect_at = (
        None
        if effect_raw is None
        else _parse_timestamp(effect_raw, "operator_control_state.effect_observed_at")
    )
    if sequence == 0:
        _require(
            state["control_state"] == "RUNNING"
            and state["request_id"] == ""
            and state["idempotency_key"] == ""
            and state["action"] == ""
            and state["source_envelope_sha256"] == ""
            and authority_ref == ""
            and state["authority_receipt_sha256"] == ""
            and authority_at is None
            and state["effect_state"] == "unobserved"
            and effect_ref == ""
            and state["effect_receipt_sha256"] == ""
            and effect_at is None,
            "campaign projection initial operator control state is not exact",
        )
        claim_stage = "none"
    else:
        _require(
            bool(_OPERATOR_CONTROL_IDENTIFIER_RE.fullmatch(state["request_id"]))
            and bool(
                _OPERATOR_CONTROL_IDENTIFIER_RE.fullmatch(state["idempotency_key"])
            )
            and state["action"] in _OPERATOR_CONTROL_ACTION_STATES
            and state["control_state"]
            == _OPERATOR_CONTROL_ACTION_STATES[state["action"]]
            and bool(_SHA256_RE.fullmatch(state["source_envelope_sha256"]))
            and bool(authority_ref)
            and bool(_SHA256_RE.fullmatch(state["authority_receipt_sha256"]))
            and authority_at is not None
            and authority_at <= observed
            and authority_at <= now + _MAX_CLOCK_SKEW,
            "campaign projection applied operator control state is incomplete or causal",
        )
        effect_state = state["effect_state"]
        if effect_state == "unobserved":
            _require(
                effect_ref == ""
                and state["effect_receipt_sha256"] == ""
                and effect_at is None,
                "campaign projection unobserved operator effect claims evidence",
            )
            claim_stage = "authority_applied"
        else:
            _require(
                bool(effect_ref)
                and bool(_SHA256_RE.fullmatch(state["effect_receipt_sha256"]))
                and effect_at is not None
                and authority_at <= effect_at <= observed
                and effect_at <= now + _MAX_CLOCK_SKEW,
                "campaign projection operator effect evidence is incomplete or causal",
            )
            claim_stage = (
                "effect_observed" if effect_state == "observed" else "effect_violated"
            )
    return {
        "schema_version": OPERATOR_CONTROL_EVIDENCE_SCHEMA_VERSION,
        "claim_stage": claim_stage,
        "control_state": state["control_state"],
        "campaign_generation": generation,
        "transition_sequence": sequence,
        "request_id": state["request_id"],
        "idempotency_key": state["idempotency_key"],
        "action": state["action"],
        "source_envelope_sha256": state["source_envelope_sha256"],
        "authority_receipt_ref": authority_ref,
        "authority_receipt_sha256": state["authority_receipt_sha256"],
        "authority_applied_at": (
            None if authority_at is None else _canonical_utc_timestamp(authority_at)
        ),
        "effect_state": state["effect_state"],
        "effect_receipt_ref": effect_ref,
        "effect_receipt_sha256": state["effect_receipt_sha256"],
        "effect_observed_at": (
            None if effect_at is None else _canonical_utc_timestamp(effect_at)
        ),
    }


def validate_campaign_projection(
    content: bytes,
    *,
    mission_id: str,
    config_digest: str,
    minimum_generation: int,
    max_age_seconds: float,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any], int, int, str]:
    """Return nested views and their monotonic wire identity or fail closed."""
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
        and minimum_generation <= generation <= _MAX_SAFE_INTEGER,
        "campaign projection generation is below the admitted floor",
    )
    cycle_sequence = payload.get("cycle_sequence")
    _require(
        not isinstance(cycle_sequence, bool)
        and isinstance(cycle_sequence, int)
        and 0 <= cycle_sequence <= _MAX_SAFE_INTEGER,
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
    evidence = _campaign_evidence(
        payload,
        snapshot,
        mission_id=mission_id,
        observed=observed,
        now=now,
        max_age=max_age,
    )
    operator_evidence = _operator_control_evidence(
        payload,
        generation=generation,
        observed=observed,
        now=now,
    )
    projected = {**snapshot, "campaign_evidence": evidence}
    return (
        projected,
        operator_evidence,
        generation,
        cycle_sequence,
        canonical_digest(
            {
                "mission_snapshot": projected,
                "operator_control_evidence": operator_evidence,
            }
        ),
    )
