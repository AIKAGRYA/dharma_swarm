"""Exact runtime-owned authority for one TaskBoard projection."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

TASK_BOARD_PROJECTION_INTENT_KEY = "task_board_projection_intent"
TASK_BOARD_PROJECTION_WITNESS_KEY = "task_board_projection"
TASK_BOARD_PROJECTION_INTENT_SCHEMA = (
    "dharma.graph.task_board_projection_intent.v1"
)
GRAPH_PROJECTION_KEY = "graph_reconcile_projection"
GRAPH_PROJECTION_HISTORY_KEY = "graph_reconcile_projection_history"

PROJECTION_RUN_STATUSES = {
    "receipt": frozenset({"completed", "failed"}),
    "retry": frozenset({"failed"}),
    "requeue": frozenset({"failed"}),
    "quarantine": frozenset({"failed"}),
}
_COMPLETION_BINDING_FIELDS = frozenset(
    "schema_version task_id run_id claim_id agent_id receipt_id side_effect_key "
    "idempotency_key dispatch_idempotency_key result_sha256".split()
)
_EXECUTION_IDENTITY_FIELDS = frozenset(
    "trace_id correlation_id task_id run_id claim_id idempotency_key causation_id "
    "parent_run_id agent_id session_id external_a2a_task_id message_id event_id "
    "artifact_id proposal_id metadata".split()
)
_PROJECTION_INTENT_FIELDS = frozenset(
    "schema_version task_id run_id claim_id agent_id action run_status source_kind "
    "runtime_authority_snapshot_sha256 result result_sha256 metadata_set "
    "metadata_remove metadata_delta_sha256 completion_binding execution_identity "
    "prepared_at intent_sha256".split()
)
_PROJECTION_PROTOCOL_METADATA_FIELDS = frozenset(
    {GRAPH_PROJECTION_KEY, GRAPH_PROJECTION_HISTORY_KEY, "task_board_completion_binding"}
)
_PROJECTION_SOURCE_KIND = {
    "receipt": "idempotency_record",
    "retry": "idempotency_record",
    "requeue": "delegation_run",
    "quarantine": "delegation_run",
}
_RUN_IDENTITY_ALIASES = {
    "trace_id": "trace_id",
    "correlation_id": "correlation_id",
    "idempotency_key": "idempotency_key",
    "task_id": "task_id",
    "run_id": "run_id",
    "claim_id": "claim_id",
    "agent_id": "agent_id",
    "session_id": "session_id",
    "parent_run_id": "parent_run_id",
    "causation_id": "causation_id",
}


class CampaignTaskMutationError(ValueError):
    """Raised when typed campaign or projection authority is violated."""


def is_sha256_hex(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def is_aware_iso8601(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def stable_sha256(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def valid_completion_binding(
    value: Any,
    *,
    task_id: str,
    run_id: str,
    claim_id: str,
    agent_id: str,
    dispatch_idempotency_key: str,
    result: str,
) -> bool:
    if not isinstance(value, dict) or set(value) != _COMPLETION_BINDING_FIELDS:
        return False
    side_effect_key = value.get("side_effect_key")
    required_strings = _COMPLETION_BINDING_FIELDS - {
        "schema_version",
        "task_id",
        "run_id",
        "result_sha256",
    }
    return bool(
        value.get("schema_version")
        == "dharma.graph.task_board_completion_binding.v1"
        and value.get("task_id") == task_id
        and value.get("run_id") == run_id
        and value.get("claim_id") == claim_id
        and value.get("agent_id") == agent_id
        and value.get("side_effect_key") == f"invoke_agent:{task_id}:{agent_id}"
        and value.get("dispatch_idempotency_key") == dispatch_idempotency_key
        and value.get("result_sha256")
        == hashlib.sha256(result.encode("utf-8")).hexdigest()
        and all(
            isinstance(value.get(key), str) and value.get(key)
            for key in required_strings
        )
        and value.get("idempotency_key")
        == "sek_" + hashlib.sha256(str(side_effect_key).encode()).hexdigest()
    )


def runtime_idempotency_authority_snapshot_sha256(record: Any) -> str:
    metadata = getattr(record, "metadata", None)
    if not isinstance(metadata, dict):
        return ""
    return stable_sha256(
        {
            key: getattr(record, key, None)
            for key in (
                "idempotency_key",
                "side_effect_key",
                "run_id",
                "task_id",
                "trace_id",
                "correlation_id",
                "status",
                "result_receipt_id",
            )
        }
        | {"metadata": metadata}
    )


def _runtime_run_authority_snapshot_sha256(
    run: Any,
    *,
    excluded_metadata_keys: frozenset[str] = frozenset(),
) -> str:
    metadata = getattr(run, "metadata", None)
    if not isinstance(metadata, dict):
        return ""
    snapshot_metadata = {
        key: value for key, value in metadata.items() if key not in excluded_metadata_keys
    }
    completed_at = getattr(run, "completed_at", None)
    return stable_sha256(
        {
            key: getattr(run, key, None)
            for key in (
                "run_id",
                "task_id",
                "assigned_to",
                "status",
                "session_id",
                "claim_id",
                "parent_run_id",
                "assigned_by",
                "failure_code",
            )
        }
        | {
            "completed_at": (
                completed_at.isoformat()
                if isinstance(completed_at, datetime)
                else None
            ),
            "metadata": snapshot_metadata,
        }
    )


def runtime_run_authority_snapshot_sha256(run: Any) -> str:
    """Digest the complete V4 delegation-run authority carrier."""
    return _runtime_run_authority_snapshot_sha256(run)


def runtime_run_projection_authority_snapshot_sha256(run: Any) -> str:
    """Digest recovery truth while excluding mutable projection protocol state."""
    return _runtime_run_authority_snapshot_sha256(
        run,
        excluded_metadata_keys=frozenset(
            {TASK_BOARD_PROJECTION_INTENT_KEY, TASK_BOARD_PROJECTION_WITNESS_KEY}
        ),
    )


def build_task_board_projection_intent(
    *,
    execution_identity: dict[str, Any],
    action: str,
    run_status: str,
    source_kind: str,
    runtime_authority_snapshot_sha256: str,
    result: str,
    metadata_set: dict[str, Any] | None = None,
    metadata_remove: list[str] | None = None,
    completion_binding: dict[str, Any] | None = None,
    prepared_at: datetime | str,
) -> dict[str, Any]:
    """Build the sole sealed runtime authority for one exact Board projection."""
    try:
        identity = dict(execution_identity or {})
        delta_set = dict(metadata_set or {})
        delta_remove = sorted(set(metadata_remove or []))
    except (TypeError, ValueError) as exc:
        raise CampaignTaskMutationError("ProjectionIntent boundary is invalid") from exc
    prepared = prepared_at.isoformat() if isinstance(prepared_at, datetime) else prepared_at
    if not (
        set(identity) == _EXECUTION_IDENTITY_FIELDS
        and isinstance(identity.get("metadata"), dict)
        and all(
            isinstance(identity.get(key), str)
            for key in _EXECUTION_IDENTITY_FIELDS - {"metadata"}
        )
        and all(
            identity.get(key)
            for key in (
                "trace_id",
                "correlation_id",
                "task_id",
                "run_id",
                "claim_id",
                "idempotency_key",
                "agent_id",
                "session_id",
            )
        )
        and action in PROJECTION_RUN_STATUSES
        and run_status in PROJECTION_RUN_STATUSES[action]
        and source_kind == _PROJECTION_SOURCE_KIND[action]
        and is_sha256_hex(runtime_authority_snapshot_sha256)
        and isinstance(result, str)
        and all(isinstance(key, str) and key for key in delta_set)
        and all(isinstance(key, str) and key for key in delta_remove)
        and not set(delta_set).intersection(delta_remove)
        and not (set(delta_set) | set(delta_remove)).intersection(
            _PROJECTION_PROTOCOL_METADATA_FIELDS
        )
        and is_aware_iso8601(prepared)
        and (
            action not in {"receipt", "retry"}
            or valid_completion_binding(
                completion_binding,
                task_id=identity["task_id"],
                run_id=identity["run_id"],
                claim_id=identity["claim_id"],
                agent_id=identity["agent_id"],
                dispatch_idempotency_key=identity["idempotency_key"],
                result=result,
            )
        )
        and (completion_binding is None or isinstance(completion_binding, dict))
    ):
        raise CampaignTaskMutationError("ProjectionIntent boundary is invalid")
    intent: dict[str, Any] = {
        "schema_version": TASK_BOARD_PROJECTION_INTENT_SCHEMA,
        "task_id": identity["task_id"],
        "run_id": identity["run_id"],
        "claim_id": identity["claim_id"],
        "agent_id": identity["agent_id"],
        "action": action,
        "run_status": run_status,
        "source_kind": source_kind,
        "runtime_authority_snapshot_sha256": runtime_authority_snapshot_sha256,
        "result": result,
        "result_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
        "metadata_set": delta_set,
        "metadata_remove": delta_remove,
        "completion_binding": (
            dict(completion_binding) if completion_binding is not None else None
        ),
        "execution_identity": identity,
        "prepared_at": prepared,
    }
    try:
        intent["metadata_delta_sha256"] = stable_sha256(
            {"set": delta_set, "remove": delta_remove}
        )
        intent["intent_sha256"] = stable_sha256(intent)
    except (TypeError, ValueError) as exc:
        raise CampaignTaskMutationError("ProjectionIntent boundary is invalid") from exc
    return intent


def _projection_marker_from_intent(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "dharma.graph.board_projection_receipt.v1",
        "task_id": intent["task_id"],
        "run_id": intent["run_id"],
        "action": intent["action"],
        "run_status": intent["run_status"],
        "runtime_authority_snapshot_sha256": intent[
            "runtime_authority_snapshot_sha256"
        ],
        "board_result_sha256": intent["result_sha256"],
        "projected_at": intent["prepared_at"],
    }


def _projection_target_metadata(
    current: dict[str, Any],
    intent: dict[str, Any],
    marker: dict[str, Any],
) -> dict[str, Any] | None:
    metadata_set = intent.get("metadata_set")
    metadata_remove = intent.get("metadata_remove")
    if not (
        isinstance(metadata_set, dict)
        and all(isinstance(key, str) and key for key in metadata_set)
        and isinstance(metadata_remove, list)
        and metadata_remove == sorted(set(metadata_remove))
        and all(isinstance(key, str) and key for key in metadata_remove)
        and not set(metadata_set).intersection(metadata_remove)
        and not (set(metadata_set) | set(metadata_remove)).intersection(
            _PROJECTION_PROTOCOL_METADATA_FIELDS
        )
        and intent.get("metadata_delta_sha256")
        == stable_sha256({"set": metadata_set, "remove": metadata_remove})
    ):
        return None
    target = dict(current)
    for key in metadata_remove:
        target.pop(key, None)
    target.update(metadata_set)
    binding = intent.get("completion_binding")
    if intent.get("action") in {"receipt", "retry"}:
        if not isinstance(binding, dict):
            return None
        target["task_board_completion_binding"] = binding
    elif binding != current.get("task_board_completion_binding"):
        return None
    history = target.get(GRAPH_PROJECTION_HISTORY_KEY, {})
    if not isinstance(history, dict):
        return None
    history = dict(history)
    prior_marker = target.get(GRAPH_PROJECTION_KEY)
    if prior_marker is not None:
        if not isinstance(prior_marker, dict):
            return None
        prior_run_id = prior_marker.get("run_id")
        if not isinstance(prior_run_id, str) or not prior_run_id:
            return None
        historical = history.get(prior_run_id)
        if historical is not None and historical != prior_marker:
            return None
        history[prior_run_id] = prior_marker
    history[intent["run_id"]] = marker
    target[GRAPH_PROJECTION_KEY] = marker
    target[GRAPH_PROJECTION_HISTORY_KEY] = history
    return target


def projection_intent_is_exact(
    run: Any,
    *,
    current: dict[str, Any],
    replacement: dict[str, Any],
    attempt: dict[str, str],
    binding: Any,
    marker: dict[str, Any],
    result: str,
) -> bool:
    """Validate one locked runtime intent against the exact requested Board effect."""
    run_metadata = getattr(run, "metadata", None)
    intent = (
        run_metadata.get(TASK_BOARD_PROJECTION_INTENT_KEY)
        if isinstance(run_metadata, dict)
        else None
    )
    if not isinstance(intent, dict) or set(intent) != _PROJECTION_INTENT_FIELDS:
        return False
    identity = intent.get("execution_identity")
    board_identity = current.get("execution_identity")
    run_identity = run_metadata.get("execution_identity")
    unsigned = {key: value for key, value in intent.items() if key != "intent_sha256"}
    derived_marker = _projection_marker_from_intent(intent)
    target = _projection_target_metadata(current, intent, derived_marker)
    source_kind = intent.get("source_kind")
    outcome_exact = bool(
        isinstance(run_metadata, dict)
        and run_metadata.get("status") == intent.get("run_status")
        and (
            source_kind != "idempotency_record"
            or (
                intent.get("run_status") == "completed"
                and not getattr(run, "failure_code", "")
            )
            or (
                intent.get("run_status") == "failed"
                and bool(getattr(run, "failure_code", ""))
                and run_metadata.get("error") == result
            )
        )
    )
    return bool(
        intent.get("schema_version") == TASK_BOARD_PROJECTION_INTENT_SCHEMA
        and isinstance(identity, dict)
        and set(identity) == _EXECUTION_IDENTITY_FIELDS
        and isinstance(identity.get("metadata"), dict)
        and all(
            isinstance(identity.get(key), str)
            for key in _EXECUTION_IDENTITY_FIELDS - {"metadata"}
        )
        and identity == board_identity == run_identity
        and all(
            run_metadata.get(alias) == identity[field]
            for alias, field in _RUN_IDENTITY_ALIASES.items()
        )
        and intent.get("task_id") == attempt["task_id"]
        and intent.get("run_id") == attempt["run_id"]
        and intent.get("claim_id") == attempt["claim_id"]
        and intent.get("agent_id") == attempt["agent_id"]
        and getattr(run, "task_id", None) == attempt["task_id"]
        and getattr(run, "run_id", None) == attempt["run_id"]
        and getattr(run, "claim_id", None) == attempt["claim_id"]
        and getattr(run, "assigned_to", None) == attempt["agent_id"]
        and getattr(run, "session_id", None) == attempt["session_id"]
        and getattr(run, "parent_run_id", None) == identity["parent_run_id"]
        and getattr(run, "assigned_by", None) == "orchestrator"
        and getattr(run, "status", None) == intent.get("run_status")
        and isinstance(getattr(run, "completed_at", None), datetime)
        and outcome_exact
        and intent.get("action") == marker.get("action")
        and intent.get("run_status") == marker.get("run_status")
        and intent.get("source_kind")
        == _PROJECTION_SOURCE_KIND.get(str(intent.get("action")))
        and intent.get("runtime_authority_snapshot_sha256")
        == marker.get("runtime_authority_snapshot_sha256")
        and intent.get("result") == result
        and intent.get("result_sha256")
        == hashlib.sha256(result.encode("utf-8")).hexdigest()
        and intent.get("completion_binding") == binding
        and is_aware_iso8601(intent.get("prepared_at"))
        and intent.get("intent_sha256") == stable_sha256(unsigned)
        and marker == derived_marker
        and replacement == target
    )
