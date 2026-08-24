"""Fail-closed campaign marker rules for generic TaskBoard mutations."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from dharma_swarm.runtime_lifecycle_identity import BOARD_CAMPAIGN_AUTHORITY_FIELDS, valid_board_campaign_authority, valid_initial_campaign_authority_promotion
from dharma_swarm.task_board_effect_commit import (
    GRAPH_PROJECTION_EFFECT_KIND,
    GRAPH_PROJECTION_PAYLOAD_SCHEMA,
    commit_locked_task_effect,
    graph_projection_effect_id,
    load_effect_commit,
    task_effect_snapshot,
)
from dharma_swarm.task_board_projection_intent import (
    CampaignTaskMutationError,
    PROJECTION_RUN_STATUSES as _PROJECTION_RUN_STATUSES,
    TASK_BOARD_PROJECTION_INTENT_KEY,
    build_task_board_projection_intent as build_task_board_projection_intent,
    is_aware_iso8601 as _is_aware_iso8601,
    is_sha256_hex as _is_sha256_hex,
    projection_intent_is_exact as _projection_intent_is_exact,
    runtime_idempotency_authority_snapshot_sha256,
    runtime_run_authority_snapshot_sha256 as runtime_run_authority_snapshot_sha256,
    runtime_run_projection_authority_snapshot_sha256,
    valid_completion_binding as _valid_completion_binding,
)

CAMPAIGN_AUTHORITY_KEY = "mission_campaign_authority"
CAMPAIGN_BOOTSTRAP_SCHEMA = "dharma.sadhana.mission_bootstrap.v1"
CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY = "campaign_runtime_recovery_fence"
CAMPAIGN_RUNTIME_RECOVERY_FENCE_SCHEMA = (
    "dharma.sadhana.campaign_runtime_recovery_fence.v1"
)
GRAPH_PROJECTION_KEY = "graph_reconcile_projection"
GRAPH_PROJECTION_HISTORY_KEY = "graph_reconcile_projection_history"
_CAMPAIGN_ONLY_CARRIERS = {
    CAMPAIGN_AUTHORITY_KEY, CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY,
    "campaign_dispatch_recovery", "campaign_dispatch_attempt_history",
}
_BOOTSTRAP_IMMUTABLE_FIELDS = frozenset(
    "sadhana_bootstrap_schema campaign_id goal_id mission_task_creation_hash".split()
)
_TERMINAL_PROJECTION_IMMUTABLE_FIELDS = frozenset(
    (
        "execution_identity trace_id correlation_id runtime_run_id runtime_db_path "
        "task_id run_id claim_id agent_id session_id idempotency_key causation_id "
        "parent_run_id external_a2a_task_id message_id event_id artifact_id proposal_id "
        "mission_control_governance mission_control_owner_execution last_claim "
        "campaign_dispatch_recovery campaign_dispatch_attempt_history "
        "attempt_generation attempt_ceiling"
    ).split()
) | {CAMPAIGN_AUTHORITY_KEY, CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY} | _BOOTSTRAP_IMMUTABLE_FIELDS | BOARD_CAMPAIGN_AUTHORITY_FIELDS
_GENERIC_CAMPAIGN_IMMUTABLE_FIELDS = _TERMINAL_PROJECTION_IMMUTABLE_FIELDS | {
    "active_claim",
    "task_board_completion_binding",
}
_OWNER_STAMP_PROMOTION_FIELDS = frozenset(
    "mission_control_owner_execution runtime_run_id run_id claim_id idempotency_key "
    "trace_id correlation_id attempt_generation".split()
)
_PROJECTION_MARKER_FIELDS = frozenset(
    "schema_version task_id run_id action run_status "
    "runtime_authority_snapshot_sha256 board_result_sha256 projected_at".split()
)
_OWNER_EXECUTION_FIELDS = frozenset(
    "schema_version backend mission_id task_id dispatch_key attempt_generation run_id "
    "claim_id idempotency_key trace_id correlation_id".split()
)
_LEGACY_OWNER_EXECUTION_FIELDS = frozenset(
    "schema_version backend mission_id task_id dispatch_key run_id "
    "idempotency_key trace_id correlation_id".split()
)


def _is_generation(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _exact_board_execution_attempt(
    current: dict[str, Any],
    *,
    task_id: str,
    assigned_to: Any,
) -> dict[str, str] | None:
    identity = current.get("execution_identity")
    required = {
        "trace_id",
        "correlation_id",
        "task_id",
        "run_id",
        "claim_id",
        "agent_id",
        "session_id",
        "idempotency_key",
    }
    if not (
        isinstance(identity, dict)
        and all(
            isinstance(identity.get(key), str) and identity[key].strip()
            for key in required
        )
        and identity.get("task_id") == task_id
    ):
        return None
    attempt = {key: str(identity[key]) for key in required}
    if assigned_to is not None and assigned_to != attempt["agent_id"]:
        return None
    aliases = {
        "trace_id": "trace_id",
        "correlation_id": "correlation_id",
        "causation_id": "causation_id",
        "task_id": "task_id",
        "runtime_run_id": "run_id",
        "run_id": "run_id",
        "claim_id": "claim_id",
        "parent_run_id": "parent_run_id",
        "agent_id": "agent_id",
        "session_id": "session_id",
        "external_a2a_task_id": "external_a2a_task_id",
        "message_id": "message_id",
        "event_id": "event_id",
        "artifact_id": "artifact_id",
        "proposal_id": "proposal_id",
        "idempotency_key": "idempotency_key",
    }
    if any(not isinstance(identity.get(field, ""), str) for field in aliases.values()) or any(
        key in current and current.get(key) != identity.get(field)
        for key, field in aliases.items()
    ):
        return None
    attempt.update({field: identity.get(field, "") for field in aliases.values()})
    campaign_bound = campaign_metadata_bound(current)
    owner = current.get("mission_control_owner_execution")
    if campaign_bound and not isinstance(owner, dict):
        return None
    if isinstance(owner, dict):
        common_owner_exact = bool(
            owner.get("backend") == "orchestrator"
            and owner.get("task_id") == task_id
            and all(
                isinstance(owner.get(field), str) and owner[field].strip()
                for field in ("mission_id", "dispatch_key")
            )
            and all(
                owner.get(field) == attempt[field]
                for field in (
                    "run_id",
                    "idempotency_key",
                    "trace_id",
                    "correlation_id",
                )
            )
        )
        exact_v2_owner = bool(
            common_owner_exact
            and set(owner) == _OWNER_EXECUTION_FIELDS
            and owner.get("schema_version")
            == "dharma.mission_control.owner_execution.v2"
            and owner.get("claim_id") == attempt["claim_id"]
        )
        # Mission Control's ordinary, generation-less owner lane deliberately
        # retains the closed v1 marker.  It is not campaign authority, but it
        # must remain byte-compatible with exact runtime/Board convergence.
        exact_legacy_owner = bool(
            not campaign_bound
            and common_owner_exact
            and set(owner) == _LEGACY_OWNER_EXECUTION_FIELDS
            and owner.get("schema_version")
            == "dharma.mission_control.owner_execution.v1"
        )
        if not (exact_v2_owner or exact_legacy_owner):
            return None
    active_claim = current.get("active_claim")
    if active_claim is not None and (
        not isinstance(active_claim, dict)
        or active_claim.get("claim_id") != attempt["claim_id"]
        or "agent_id" in active_claim
        and active_claim.get("agent_id") != attempt["agent_id"]
    ):
        return None
    authority = current.get(CAMPAIGN_AUTHORITY_KEY)
    if campaign_bound and not isinstance(authority, dict):
        return None
    if isinstance(authority, dict):
        generation = authority.get("attempt_generation")
        owner_generation = owner.get("attempt_generation")
        flat_generation = current.get("attempt_generation")
        if (
            not valid_board_campaign_authority(current, task_id=task_id)
            or authority.get("claimed_principal") != attempt["agent_id"]
            or not isinstance(owner, dict)
            or owner.get("mission_id") != authority.get("mission_id")
            or owner.get("dispatch_key") != authority.get("dispatch_key")
            or owner_generation != generation
            or flat_generation != generation
            or not all(
                _is_generation(value)
                for value in (generation, owner_generation, flat_generation)
            )
        ):
            return None
    return attempt


def _stable_owner_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _valid_owner_stamp_promotion(
    current: dict[str, Any],
    replacement: dict[str, Any],
    *,
    task_id: str,
) -> bool:
    if "mission_control_owner_execution" in current:
        return False
    authority = current.get(CAMPAIGN_AUTHORITY_KEY)
    marker = replacement.get("mission_control_owner_execution")
    if not isinstance(authority, dict) or not isinstance(marker, dict):
        return False
    mission_id = authority.get("mission_id")
    dispatch_key = authority.get("dispatch_key")
    generation = authority.get("attempt_generation")
    if not (
        isinstance(mission_id, str)
        and mission_id
        and isinstance(dispatch_key, str)
        and dispatch_key
        and _is_generation(generation)
    ):
        return False
    parts = (mission_id, task_id, dispatch_key, str(generation))
    expected = {
        "schema_version": "dharma.mission_control.owner_execution.v2",
        "backend": "orchestrator",
        "mission_id": mission_id,
        "task_id": task_id,
        "dispatch_key": dispatch_key,
        "run_id": _stable_owner_id("owner_run", *parts),
        "idempotency_key": _stable_owner_id("owner_dispatch", *parts),
        "trace_id": _stable_owner_id("owner_trace", *parts),
        "correlation_id": _stable_owner_id("owner_correlation", *parts),
        "claim_id": _stable_owner_id("owner_claim", *parts),
        "attempt_generation": generation,
    }
    return bool(
        marker == expected
        and replacement.get("runtime_run_id") == expected["run_id"]
        and all(
            replacement.get(key) == expected[key]
            for key in (
                "run_id",
                "claim_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
                "attempt_generation",
            )
        )
    )


def metadata_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        loaded = json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def campaign_metadata_bound(metadata: dict[str, Any]) -> bool:
    return bool(
        CAMPAIGN_AUTHORITY_KEY in metadata
        or metadata.get("sadhana_bootstrap_schema") == CAMPAIGN_BOOTSTRAP_SCHEMA
    )


def runtime_campaign_metadata_bound(raw: Any) -> bool:
    metadata = metadata_mapping(raw)
    return bool(
        campaign_metadata_bound(metadata)
        or CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY in metadata
    )


def campaign_runtime_recovery_fence(
    raw: Any,
    *,
    task_id: str,
) -> dict[str, Any] | None:
    metadata = metadata_mapping(raw)
    marker = metadata.get(CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY)
    required = {
        "schema_version",
        "task_id",
        "campaign_id",
        "goal_id",
        "claimed_principal",
        "authority_digest",
        "attempt_generation",
    }
    if not (
        isinstance(marker, dict)
        and set(marker) == required
        and marker.get("schema_version") == CAMPAIGN_RUNTIME_RECOVERY_FENCE_SCHEMA
        and marker.get("task_id") == task_id
    ):
        return None
    return marker


def live_campaign_runtime_fence(
    raw: Any,
    *,
    task_id: str,
) -> dict[str, Any] | None:
    marker = campaign_runtime_recovery_fence(raw, task_id=task_id)
    if marker is None:
        return None
    generation = marker.get("attempt_generation")
    if not (
        all(
            isinstance(marker.get(key), str)
            and marker.get(key)
            and marker.get(key) == marker.get(key).strip()
            for key in (
                "campaign_id",
                "goal_id",
                "claimed_principal",
                "authority_digest",
            )
        )
        and isinstance(generation, int)
        and not isinstance(generation, bool)
        and generation >= 0
    ):
        return None
    return marker


def runtime_campaign_fence_metadata(
    task_id: str,
    task_raw: Any,
) -> dict[str, Any]:
    metadata = metadata_mapping(task_raw)
    if not campaign_metadata_bound(metadata):
        return {}
    authority = metadata.get(CAMPAIGN_AUTHORITY_KEY)
    if not isinstance(authority, dict):
        authority = {}
    return {
        CAMPAIGN_RUNTIME_RECOVERY_FENCE_KEY: {
            "schema_version": CAMPAIGN_RUNTIME_RECOVERY_FENCE_SCHEMA,
            "task_id": task_id,
            "campaign_id": authority.get("campaign_id", metadata.get("campaign_id")),
            "goal_id": authority.get("goal_id", metadata.get("goal_id")),
            "claimed_principal": authority.get("claimed_principal"),
            "authority_digest": authority.get("authority_digest"),
            "attempt_generation": authority.get(
                "attempt_generation",
                metadata.get("attempt_generation"),
            ),
        }
    }


def validate_generic_campaign_mutation(
    current_raw: Any,
    *,
    task_id: str = "",
    new_status: str | None = None,
    replacement_raw: Any = None,
    replacement_provided: bool = False,
    assigned_to_provided: bool = False,
    result_provided: bool = False,
) -> None:
    current = metadata_mapping(current_raw)
    replacement = metadata_mapping(replacement_raw) if replacement_provided else {}
    if replacement_provided:
        if any(
            replacement.get(key) != current.get(key)
            for key in (GRAPH_PROJECTION_KEY, GRAPH_PROJECTION_HISTORY_KEY)
            if key in current or key in replacement
        ):
            raise CampaignTaskMutationError(
                "Generic task mutation cannot alter Graph projection receipts"
            )
        if not campaign_metadata_bound(current) and not valid_initial_campaign_authority_promotion(
            current,
            replacement if isinstance(replacement_raw, dict) else {},
            task_id=task_id,
            authority_key=CAMPAIGN_AUTHORITY_KEY,
            campaign_only_carriers=_CAMPAIGN_ONLY_CARRIERS,
            bootstrap_schema=CAMPAIGN_BOOTSTRAP_SCHEMA,
        ) and (
            any(key in replacement for key in _CAMPAIGN_ONLY_CARRIERS)
            or replacement.get("sadhana_bootstrap_schema")
            == CAMPAIGN_BOOTSTRAP_SCHEMA
        ):
            raise CampaignTaskMutationError(
                "Generic task mutation cannot mint campaign authority"
            )
    if not campaign_metadata_bound(current):
        return
    if assigned_to_provided:
        raise CampaignTaskMutationError(
            "Campaign assignee mutation requires typed authority CAS"
        )
    if new_status == "pending":
        raise CampaignTaskMutationError("Campaign retry requires typed attempt recovery")
    if new_status == "completed":
        raise CampaignTaskMutationError("Campaign completion requires receipt-backed CAS")
    if result_provided and new_status != "failed":
        raise CampaignTaskMutationError("Campaign result mutation requires typed CAS")
    if not replacement_provided:
        return
    authority = current.get(CAMPAIGN_AUTHORITY_KEY)
    if CAMPAIGN_AUTHORITY_KEY in current and (
        not isinstance(authority, dict)
        or replacement.get(CAMPAIGN_AUTHORITY_KEY) != authority
    ):
        raise CampaignTaskMutationError(
            "Generic task mutation cannot remove or replace campaign authority"
        )
    if current.get("sadhana_bootstrap_schema") == CAMPAIGN_BOOTSTRAP_SCHEMA:
        if any(
            replacement.get(field) != current.get(field)
            for field in _BOOTSTRAP_IMMUTABLE_FIELDS
        ):
            raise CampaignTaskMutationError(
                "Generic task mutation cannot alter campaign bootstrap authority"
            )
    owner_promotion = _valid_owner_stamp_promotion(
        current,
        replacement,
        task_id=task_id,
    )
    if any(
        (key in current) != (key in replacement)
        or key in current
        and replacement[key] != current[key]
        for key in _GENERIC_CAMPAIGN_IMMUTABLE_FIELDS
        if not owner_promotion or key not in _OWNER_STAMP_PROMOTION_FIELDS
        if key in current or key in replacement
    ):
        raise CampaignTaskMutationError(
            "Generic task mutation cannot alter campaign attempt authority"
        )


def _validate_terminal_projection_metadata(
    current: dict[str, Any],
    replacement: dict[str, Any],
    marker: dict[str, Any],
) -> None:
    if any(
        (key in current) != (key in replacement)
        or key in current
        and replacement[key] != current[key]
        for key in _TERMINAL_PROJECTION_IMMUTABLE_FIELDS
        if key in current or key in replacement
    ):
        raise CampaignTaskMutationError(
            "Graph projection cannot alter campaign attempt authority"
        )
    current_active_claim = current.get("active_claim")
    if "active_claim" in replacement and (
        "active_claim" not in current
        or replacement["active_claim"] != current_active_claim
    ):
        raise CampaignTaskMutationError(
            "Graph projection cannot replace active claim authority"
        )
    if marker.get("action") not in {"receipt", "retry"} and (
        ("task_board_completion_binding" in current)
        != ("task_board_completion_binding" in replacement)
        or "task_board_completion_binding" in current
        and replacement["task_board_completion_binding"]
        != current["task_board_completion_binding"]
    ):
        raise CampaignTaskMutationError(
            "Recovery projection cannot alter completion binding authority"
        )
    if replacement.get(GRAPH_PROJECTION_KEY) != marker:
        raise CampaignTaskMutationError(
            "Graph projection marker must be the exact replacement receipt"
        )
    prior_history = current.get(GRAPH_PROJECTION_HISTORY_KEY, {})
    next_history = replacement.get(GRAPH_PROJECTION_HISTORY_KEY)
    if not isinstance(prior_history, dict) or not isinstance(next_history, dict):
        raise CampaignTaskMutationError(
            "Graph projection history must be an append-only mapping"
        )
    if any(
        key not in next_history or next_history[key] != value
        for key, value in prior_history.items()
    ):
        raise CampaignTaskMutationError(
            "Graph projection cannot rewrite prior projection history"
        )
    run_id = marker.get("run_id")
    if not isinstance(run_id, str) or not run_id or next_history.get(run_id) != marker:
        raise CampaignTaskMutationError(
            "Graph projection history must bind the current run receipt"
        )
    prior_marker = current.get(GRAPH_PROJECTION_KEY)
    allowed_history_keys = set(prior_history) | {run_id}
    if isinstance(prior_marker, dict):
        prior_run_id = prior_marker.get("run_id")
        if (
            not isinstance(prior_run_id, str)
            or not prior_run_id
            or next_history.get(prior_run_id) != prior_marker
        ):
            raise CampaignTaskMutationError(
                "Graph projection must archive the prior projection receipt"
            )
        allowed_history_keys.add(prior_run_id)
    if set(next_history) != allowed_history_keys:
        raise CampaignTaskMutationError(
            "Graph projection history may append only the bound run receipt"
        )


def _runtime_store_is_bound(runtime_state_store: Any, current: dict[str, Any]) -> bool:
    try:
        from dharma_swarm.runtime_state import RuntimeStateStore

        board_path = current.get("runtime_db_path")
        store_path = getattr(runtime_state_store, "db_path", None)
        return bool(
            type(runtime_state_store) is RuntimeStateStore
            and isinstance(board_path, str)
            and board_path.strip()
            and store_path is not None
            and Path(board_path).expanduser().resolve()
            == Path(store_path).expanduser().resolve()
        )
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        return False


def _idempotency_projection_is_exact(
    record: Any,
    *,
    binding: dict[str, Any],
    attempt: dict[str, str],
    marker: dict[str, Any],
    result: str,
) -> bool:
    metadata = getattr(record, "metadata", None)
    receipt = metadata.get("receipt") if isinstance(metadata, dict) else None
    attributes = receipt.get("attributes") if isinstance(receipt, dict) else None
    if not isinstance(metadata, dict) or not isinstance(receipt, dict):
        return False
    if not isinstance(attributes, dict):
        return False
    record_status = getattr(record, "status", None)
    receipt_status = receipt.get("status")
    if record_status == "completed":
        encoded = metadata.get("result_json")
        try:
            result_exact = isinstance(encoded, str) and json.loads(encoded) == result
        except (json.JSONDecodeError, TypeError, ValueError):
            result_exact = False
        outcome_exact = receipt_status == "ok" and result_exact
    else:
        outcome_exact = bool(
            record_status == "failed"
            and receipt_status in {"failed", "dropped", "timeout", "cancelled"}
            and str(receipt.get("error_detail") or "") == result
        )
    side_effect_key = binding["side_effect_key"]
    return bool(
        outcome_exact
        and record_status == marker["run_status"]
        and getattr(record, "idempotency_key", None) == binding["idempotency_key"]
        and getattr(record, "side_effect_key", None) == side_effect_key
        and getattr(record, "run_id", None) == attempt["run_id"]
        and getattr(record, "task_id", None) == attempt["task_id"]
        and getattr(record, "trace_id", None) == attempt["trace_id"]
        and getattr(record, "correlation_id", None) == attempt["correlation_id"]
        and getattr(record, "result_receipt_id", None) == binding["receipt_id"]
        and metadata.get("task_id") == attempt["task_id"]
        and metadata.get("operation_hash")
        == hashlib.sha256(side_effect_key.encode("utf-8")).hexdigest()
        and receipt.get("receipt_id") == binding["receipt_id"]
        and receipt.get("trace_id") == attempt["trace_id"]
        and receipt.get("context_id") == attempt["session_id"]
        and receipt.get("task_id") == attempt["task_id"]
        and receipt.get("claim_id") == attempt["claim_id"]
        and receipt.get("agent_id") == attempt["agent_id"]
        and receipt.get("operation") == "invoke_agent"
        and receipt.get("provider_attempted") is True
        and attributes.get("run_id") == attempt["run_id"]
        and attributes.get("idempotency_key") == binding["idempotency_key"]
        and attributes.get("dispatch_idempotency_key")
        == attempt["idempotency_key"]
        and attributes.get("side_effect_key") == side_effect_key
        and attributes.get("unprotected_dispatch") is not True
        and marker["runtime_authority_snapshot_sha256"]
        == runtime_idempotency_authority_snapshot_sha256(record)
    )


def _run_projection_is_exact(
    run: Any,
    *,
    attempt: dict[str, str],
    marker: dict[str, Any],
    result: str,
) -> bool:
    metadata = getattr(run, "metadata", None)
    identity = metadata.get("execution_identity") if isinstance(metadata, dict) else None
    completed_at = getattr(run, "completed_at", None)
    return bool(
        isinstance(metadata, dict)
        and isinstance(identity, dict)
        and isinstance(completed_at, datetime)
        and getattr(run, "run_id", None) == attempt["run_id"]
        and getattr(run, "task_id", None) == attempt["task_id"]
        and getattr(run, "assigned_to", None) == attempt["agent_id"]
        and getattr(run, "session_id", None) == attempt["session_id"]
        and getattr(run, "claim_id", None) == attempt["claim_id"]
        and getattr(run, "assigned_by", None) == "orchestrator"
        and getattr(run, "status", None) == marker["run_status"]
        and metadata.get("status") == marker["run_status"]
        and str(metadata.get("error") or "") == result
        and all(identity.get(key) == attempt[key] for key in attempt)
        and metadata.get("trace_id") == attempt["trace_id"]
        and metadata.get("correlation_id") == attempt["correlation_id"]
        and metadata.get("idempotency_key") == attempt["idempotency_key"]
        and marker["runtime_authority_snapshot_sha256"]
        == runtime_run_projection_authority_snapshot_sha256(run)
    )


async def _runtime_projection_is_authorized(
    runtime_db: aiosqlite.Connection,
    *,
    current: dict[str, Any],
    replacement: dict[str, Any],
    attempt: dict[str, str],
    binding: Any,
    marker: dict[str, Any],
    result: str,
) -> bool:
    try:
        from dharma_swarm.runtime_state import (
            _row_to_idempotency_record,
            _row_to_run,
        )

        run_row = await (
            await runtime_db.execute(
                "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                " assigned_by, assigned_to, requested_output_json,"
                " current_artifact_id, status, started_at, completed_at,"
                " failure_code, metadata_json FROM delegation_runs WHERE run_id = ?",
                (attempt["run_id"],),
            )
        ).fetchone()
        run = _row_to_run(run_row) if run_row is not None else None
        if run is None or not _projection_intent_is_exact(
            run,
            current=current,
            replacement=replacement,
            attempt=attempt,
            binding=binding,
            marker=marker,
            result=result,
        ):
            return False
        intent = run.metadata[TASK_BOARD_PROJECTION_INTENT_KEY]
        from dharma_swarm.graph.reconcile_board_intent import (
            projection_intent_authority_is_exact,
        )

        if not await projection_intent_authority_is_exact(
            runtime_db,
            run_id=attempt["run_id"],
            expected_intent=intent,
        ):
            return False
        if intent["source_kind"] == "idempotency_record":
            if not isinstance(binding, dict):
                return False
            row = await (
                await runtime_db.execute(
                    "SELECT idempotency_key, side_effect_key, run_id, task_id,"
                    " trace_id, correlation_id, status, result_receipt_id,"
                    " metadata_json, created_at, updated_at FROM idempotency_records"
                    " WHERE idempotency_key = ? AND side_effect_key = ?",
                    (binding["idempotency_key"], binding["side_effect_key"]),
                )
            ).fetchone()
            record = _row_to_idempotency_record(row) if row is not None else None
            return record is not None and _idempotency_projection_is_exact(
                record,
                binding=binding,
                attempt=attempt,
                marker=marker,
                result=result,
            )
        return _run_projection_is_exact(
            run,
            attempt=attempt,
            marker=marker,
            result=result,
        )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return False


async def compare_and_swap_terminal_projection(
    board: Any,
    expected: Any,
    *,
    metadata: dict[str, Any],
    result: str | None = None,
    expected_claim_id: str = "",
    expected_agent_id: str = "",
    runtime_state_store: Any = None,
) -> Any | None:
    status = getattr(expected.status, "value", str(expected.status))
    marker = metadata.get("graph_reconcile_projection")
    current = dict(getattr(expected, "metadata", {}) or {})
    action = marker.get("action") if isinstance(marker, dict) else None
    run_status = marker.get("run_status") if isinstance(marker, dict) else None
    target_status = (
        "pending"
        if action in {"retry", "requeue"}
        else "completed"
        if action == "receipt" and run_status == "completed"
        else "failed"
    )
    binding = metadata.get("task_board_completion_binding")
    active_claim = current.get("active_claim")
    active_claim = active_claim if isinstance(active_claim, dict) else {}
    board_attempt = _exact_board_execution_attempt(
        current,
        task_id=expected.id,
        assigned_to=getattr(expected, "assigned_to", None),
    )
    binding_valid = bool(
        board_attempt
        and isinstance(result, str)
        and isinstance(marker, dict)
        and isinstance(marker.get("run_id"), str)
        and _valid_completion_binding(
            binding,
            task_id=expected.id,
            run_id=board_attempt["run_id"],
            claim_id=board_attempt["claim_id"],
            agent_id=board_attempt["agent_id"],
            dispatch_idempotency_key=board_attempt["idempotency_key"],
            result=result,
        )
    )
    exact_bound_value = bool(
        binding_valid
        and current.get("task_board_completion_binding") == binding
        and getattr(expected, "result", None) == result
    )
    live_bound_attempt = bool(
        binding_valid
        and status in {"assigned", "running"}
        and active_claim.get("claim_id") == board_attempt.get("claim_id")
    )
    binding_attempt = bool(
        live_bound_attempt
        or exact_bound_value
        and (
            status == target_status
            or action == "retry" and status == "failed"
        )
    )
    recovery_attempt = bool(
        expected_claim_id
        and expected_agent_id
        and active_claim.get("claim_id") == expected_claim_id
        and getattr(expected, "assigned_to", None) == expected_agent_id
        and board_attempt
        and expected_claim_id == board_attempt.get("claim_id")
        and expected_agent_id == board_attempt.get("agent_id")
    )
    exact_recovery_replay = bool(
        action in {"requeue", "quarantine"}
        and expected_claim_id
        and expected_agent_id
        and board_attempt
        and expected_claim_id == board_attempt.get("claim_id")
        and expected_agent_id == board_attempt.get("agent_id")
        and status == target_status
        and (
            getattr(expected, "assigned_to", None) is None
            if action == "requeue"
            else getattr(expected, "assigned_to", None) == expected_agent_id
        )
        and getattr(expected, "result", None) == result
        and current == metadata
    )
    same_attempt = (
        binding_attempt
        if action in {"receipt", "retry"}
        else recovery_attempt or exact_recovery_replay
    )
    allowed_sources = {
        "receipt": (
            {"assigned", "running", "completed"}
            if run_status == "completed"
            else {"assigned", "running", "failed"}
        ),
        "retry": {"assigned", "running", "failed", "pending"},
        "requeue": {"assigned", "running", "failed", "pending"},
        "quarantine": {"assigned", "running", "failed"},
    }
    if (
        action not in {"receipt", "retry", "requeue", "quarantine"}
        or status not in allowed_sources.get(action, set())
        or not same_attempt
        or not isinstance(result, str)
        or not isinstance(marker, dict)
        or not board_attempt
        or marker.get("run_id") != board_attempt.get("run_id")
        or set(marker) != _PROJECTION_MARKER_FIELDS
        or marker.get("schema_version")
        != "dharma.graph.board_projection_receipt.v1"
        or marker.get("task_id") != expected.id
        or run_status not in _PROJECTION_RUN_STATUSES.get(action, frozenset())
        or not _is_sha256_hex(marker.get("runtime_authority_snapshot_sha256"))
        or not _is_aware_iso8601(marker.get("projected_at"))
        or marker.get("board_result_sha256")
        != hashlib.sha256(result.encode("utf-8")).hexdigest()
    ):
        raise CampaignTaskMutationError("Graph projection CAS boundary is invalid")
    _validate_terminal_projection_metadata(current, metadata, marker)
    if not _runtime_store_is_bound(runtime_state_store, current):
        raise CampaignTaskMutationError(
            "Graph projection lacks exact durable runtime authority"
        )
    async with board._open() as db:
        await db.execute("BEGIN IMMEDIATE")
        row = await (
            await db.execute("SELECT * FROM tasks WHERE id = ?", (expected.id,))
        ).fetchone()
        deps = await board._fetch_deps(db, expected.id)
        observed = board._row_to_task(row, deps) if row is not None else None
        if observed != expected:
            await db.rollback()
            return None
        try:
            async with aiosqlite.connect(
                runtime_state_store.db_path,
                timeout=2.0,
            ) as runtime_db:
                runtime_db.row_factory = aiosqlite.Row
                await runtime_db.execute("PRAGMA busy_timeout=2000")
                await runtime_db.execute("BEGIN IMMEDIATE")
                try:
                    authorized = await _runtime_projection_is_authorized(
                        runtime_db,
                        current=current,
                        replacement=metadata,
                        attempt=board_attempt,
                        binding=binding,
                        marker=marker,
                        result=result,
                    )
                    if not authorized:
                        await db.rollback()
                        raise CampaignTaskMutationError(
                            "Graph projection lacks exact durable runtime authority"
                        )
                    intent_row = await (
                        await runtime_db.execute(
                            "SELECT metadata_json FROM delegation_runs WHERE run_id = ?",
                            (board_attempt["run_id"],),
                        )
                    ).fetchone()
                    intent = (
                        metadata_mapping(intent_row["metadata_json"]).get(
                            TASK_BOARD_PROJECTION_INTENT_KEY
                        )
                        if intent_row is not None
                        else None
                    )
                    if not isinstance(intent, dict):
                        await db.rollback()
                        raise CampaignTaskMutationError(
                            "Graph projection lost its locked ProjectionIntent"
                        )
                    effect_id = graph_projection_effect_id(board_attempt["run_id"])
                    effect_payload = {
                        "schema_version": GRAPH_PROJECTION_PAYLOAD_SCHEMA,
                        "intent_sha256": intent["intent_sha256"],
                        "marker": marker,
                    }
                    existing_commit = await load_effect_commit(
                        db,
                        effect_id=effect_id,
                    )
                    assigned_to = (
                        None if target_status == "pending" else expected.assigned_to
                    )
                    if (
                        status == target_status
                        and expected.assigned_to == assigned_to
                        and getattr(expected, "result", None) == result
                        and current == metadata
                    ):
                        if not (
                            existing_commit is not None
                            and existing_commit["effect_kind"]
                            == GRAPH_PROJECTION_EFFECT_KIND
                            and existing_commit["authority_sha256"]
                            == intent["intent_sha256"]
                            and existing_commit["effect_payload"] == effect_payload
                            and existing_commit["target_snapshot"]
                            == task_effect_snapshot(observed)
                        ):
                            await db.rollback()
                            raise CampaignTaskMutationError(
                                "Graph projection lacks its atomic Board receipt"
                            )
                        await db.rollback()
                        return observed
                    if existing_commit is not None:
                        await db.rollback()
                        raise CampaignTaskMutationError(
                            "Graph projection Board receipt conflicts"
                        )
                    now = datetime.now(timezone.utc)
                    target = await commit_locked_task_effect(
                        board,
                        db,
                        observed,
                        status=target_status,
                        assigned_to=assigned_to,
                        result=result,
                        metadata=metadata,
                        effect_id=effect_id,
                        effect_kind=GRAPH_PROJECTION_EFFECT_KIND,
                        authority_sha256=intent["intent_sha256"],
                        effect_payload=effect_payload,
                        committed_at=now,
                    )
                    if target is None:
                        await db.rollback()
                        return None
                    await db.commit()
                    return target
                finally:
                    await runtime_db.rollback()
        except aiosqlite.Error as exc:
            await db.rollback()
            raise CampaignTaskMutationError(
                "Graph projection runtime authority lock is unavailable"
            ) from exc
        except (TypeError, ValueError) as exc:
            await db.rollback()
            raise CampaignTaskMutationError(
                "Graph projection lacks exact durable runtime authority"
            ) from exc
