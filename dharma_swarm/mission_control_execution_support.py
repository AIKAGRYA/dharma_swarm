"""Internal validation support for Mission Control owner execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import aiosqlite

from dharma_swarm.mission_control_contract import MissionControlError, stable_id
from dharma_swarm.models import Task
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board_projection_intent import (
    TASK_BOARD_PROJECTION_INTENT_KEY,
    TASK_BOARD_PROJECTION_INTENT_SCHEMA,
    is_aware_iso8601,
    is_sha256_hex,
    stable_sha256,
    valid_completion_binding,
)


LEGACY_EXECUTION_SCHEMA_VERSION = "dharma.mission_control.owner_execution.v1"
EXECUTION_SCHEMA_VERSION = "dharma.mission_control.owner_execution.v2"
EXECUTION_METADATA_KEY = "mission_control_owner_execution"
OWNER_BACKEND = "orchestrator"
OWNER_TERMINAL_STATUSES = frozenset({"completed", "failed"})
OWNER_RUN_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})
OWNER_CLAIM_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})
_PROJECTION_INTENT_FIELDS = frozenset(
    "schema_version task_id run_id claim_id agent_id action run_status source_kind "
    "runtime_authority_snapshot_sha256 result result_sha256 metadata_set "
    "metadata_remove metadata_delta_sha256 completion_binding execution_identity "
    "prepared_at intent_sha256".split()
)
_PROJECTION_PROTOCOL_METADATA_FIELDS = frozenset(
    {
        "graph_reconcile_projection",
        "graph_reconcile_projection_history",
        "task_board_completion_binding",
    }
)


async def _exact_terminal_projection_intent(
    runtime_state: RuntimeStateStore,
    *,
    task: Task,
    run: DelegationRun,
    identity: ExecutionIdentity,
    task_id: str,
    run_id: str,
    claim_id: str,
    agent_id: str,
    session_id: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    """Re-derive one exact terminal ProjectionIntent from durable authority."""

    metadata = run.metadata if isinstance(run.metadata, dict) else {}
    intent = metadata.get(TASK_BOARD_PROJECTION_INTENT_KEY)
    durable_identity = identity.to_dict()
    board_identity = task.metadata.get("execution_identity")
    run_identity = metadata.get("execution_identity")
    run_status = run.status.lower()
    if not (
        run_status in OWNER_TERMINAL_STATUSES
        and isinstance(intent, dict)
        and set(intent) == _PROJECTION_INTENT_FIELDS
        and intent.get("schema_version") == TASK_BOARD_PROJECTION_INTENT_SCHEMA
        and intent.get("action") == "receipt"
        and intent.get("source_kind") == "idempotency_record"
        and intent.get("run_status") == run_status
        and intent.get("task_id") == task_id == run.task_id
        and intent.get("run_id") == run_id == run.run_id
        and intent.get("claim_id") == claim_id == run.claim_id
        and intent.get("agent_id") == agent_id == run.assigned_to
        and run.session_id == session_id
        and run.assigned_by == OWNER_BACKEND
        and intent.get("execution_identity")
        == board_identity
        == run_identity
        == durable_identity
        and durable_identity.get("task_id") == task_id
        and durable_identity.get("run_id") == run_id
        and durable_identity.get("claim_id") == claim_id
        and durable_identity.get("agent_id") == agent_id
        and durable_identity.get("session_id") == session_id
        and durable_identity.get("idempotency_key") == idempotency_key
        and metadata.get("status") == run_status
        and metadata.get("trace_id") == durable_identity.get("trace_id")
        and metadata.get("correlation_id")
        == durable_identity.get("correlation_id")
        and metadata.get("task_id") == task_id
        and metadata.get("run_id") == run_id
        and metadata.get("runtime_run_id") == run_id
        and metadata.get("claim_id") == claim_id
        and metadata.get("agent_id") == agent_id
        and metadata.get("session_id") == session_id
        and metadata.get("parent_run_id")
        == durable_identity.get("parent_run_id")
        and metadata.get("causation_id") == durable_identity.get("causation_id")
        and metadata.get("idempotency_key") == idempotency_key
        and run.parent_run_id == durable_identity.get("parent_run_id")
        and run.completed_at is not None
        and is_sha256_hex(intent.get("runtime_authority_snapshot_sha256"))
        and isinstance(intent.get("result"), str)
        and intent.get("result_sha256")
        == hashlib.sha256(intent["result"].encode("utf-8")).hexdigest()
        and is_aware_iso8601(intent.get("prepared_at"))
    ):
        return None

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
        and valid_completion_binding(
            intent.get("completion_binding"),
            task_id=task_id,
            run_id=run_id,
            claim_id=claim_id,
            agent_id=agent_id,
            dispatch_idempotency_key=idempotency_key,
            result=intent["result"],
        )
        and intent.get("intent_sha256")
        == stable_sha256(
            {key: value for key, value in intent.items() if key != "intent_sha256"}
        )
        and (
            (run_status == "completed" and not run.failure_code)
            or (
                run_status == "failed"
                and bool(run.failure_code)
                and metadata.get("error") == intent["result"]
            )
        )
    ):
        return None

    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN")
        # Local import avoids making Mission Control startup depend on the
        # broader Graph package initialization path.
        from dharma_swarm.graph.reconcile_board_intent import (
            projection_intent_authority_is_exact,
        )

        if not await projection_intent_authority_is_exact(
            db,
            run_id=run_id,
            expected_intent=intent,
        ):
            await db.rollback()
            return None
        await db.rollback()
    return intent


async def terminal_projection_is_pending(
    runtime_state: RuntimeStateStore,
    *,
    task: Task,
    run: DelegationRun,
    identity: ExecutionIdentity,
    task_id: str,
    run_id: str,
    claim_id: str,
    agent_id: str,
    session_id: str,
    idempotency_key: str,
) -> bool:
    """Prove the narrow runtime-first window before phase-three ACK."""
    intent = await _exact_terminal_projection_intent(
        runtime_state,
        task=task,
        run=run,
        identity=identity,
        task_id=task_id,
        run_id=run_id,
        claim_id=claim_id,
        agent_id=agent_id,
        session_id=session_id,
        idempotency_key=idempotency_key,
    )
    if intent is None:
        return False
    async with aiosqlite.connect(runtime_state.db_path) as db:
        ledger = await (
            await db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table'"
                " AND name = 'task_board_projection_acks'"
            )
        ).fetchone()
        if ledger is None:
            return True
        acknowledgement = await (
            await db.execute(
                "SELECT 1 FROM task_board_projection_acks WHERE run_id = ?",
                (run_id,),
            )
        ).fetchone()
    return acknowledgement is None


async def terminal_projection_is_acknowledged(
    runtime_state: RuntimeStateStore,
    task_board: Any,
    *,
    task: Task,
    run: DelegationRun,
    identity: ExecutionIdentity,
    task_id: str,
    run_id: str,
    claim_id: str,
    agent_id: str,
    session_id: str,
    idempotency_key: str,
) -> bool:
    """Prove terminal Board state is this run's exact acknowledged effect."""
    intent = await _exact_terminal_projection_intent(
        runtime_state,
        task=task,
        run=run,
        identity=identity,
        task_id=task_id,
        run_id=run_id,
        claim_id=claim_id,
        agent_id=agent_id,
        session_id=session_id,
        idempotency_key=idempotency_key,
    )
    if intent is None:
        return False

    # Local imports keep Mission Control startup independent of Graph package
    # initialization while binding terminal truth to both stores at observe.
    from dharma_swarm.graph.reconcile_board_proof import (
        load_exact_atomic_projection_witness,
        validate_atomic_graph_projection_commit,
    )
    from dharma_swarm.graph.reconcile_board_replay import (
        PROJECTION_ACK_SCHEMA,
        _projection_marker,
    )
    from dharma_swarm.task_board_effect_commit import (
        graph_projection_effect_id,
        load_board_effect_commit,
        task_effect_snapshot,
    )

    marker = _projection_marker(intent)
    try:
        receipt = await load_board_effect_commit(
            task_board,
            effect_id=graph_projection_effect_id(run_id),
        )
        if (
            receipt is None
            or validate_atomic_graph_projection_commit(
                receipt,
                intent=intent,
                marker=marker,
            )
            is None
            or receipt["target_snapshot"] != task_effect_snapshot(task)
            or await load_exact_atomic_projection_witness(
                runtime_state,
                intent=intent,
                marker=marker,
                expected_board_receipt=receipt,
            )
            is None
        ):
            return False
    except (KeyError, TypeError, ValueError, RuntimeError):
        return False

    encoded_marker = json.dumps(marker, sort_keys=True, separators=(",", ":"))
    async with aiosqlite.connect(runtime_state.db_path) as db:
        db.row_factory = aiosqlite.Row
        ledger = await (
            await db.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table'"
                " AND name = 'task_board_projection_acks'"
            )
        ).fetchone()
        if ledger is None:
            return False
        acknowledgement = await (
            await db.execute(
                "SELECT * FROM task_board_projection_acks WHERE run_id = ?",
                (run_id,),
            )
        ).fetchone()
    return bool(
        acknowledgement is not None
        and str(acknowledgement["task_id"]) == task_id
        and str(acknowledgement["intent_sha256"]) == intent["intent_sha256"]
        and str(acknowledgement["board_receipt_sha256"])
        == stable_sha256(marker)
        and str(acknowledgement["board_receipt_json"]) == encoded_marker
        and is_aware_iso8601(str(acknowledgement["acknowledged_at"]))
        and str(acknowledgement["schema_version"]) == PROJECTION_ACK_SCHEMA
    )


def owner_execution_identity(
    mission_id: str,
    task_id: str,
    dispatch_key: str,
    attempt_generation: int | None,
) -> dict[str, str]:
    """Derive every owner identity from one immutable attempt generation."""
    if (
        attempt_generation is not None
        and (
            isinstance(attempt_generation, bool)
            or not isinstance(attempt_generation, int)
            or attempt_generation < 0
        )
    ):
        raise MissionControlError("owner attempt generation is invalid")
    parts = [mission_id, task_id, dispatch_key]
    if attempt_generation is not None:
        parts.append(str(attempt_generation))
    identity = {
        "run_id": stable_id("owner_run", *parts),
        "idempotency_key": stable_id("owner_dispatch", *parts),
        "trace_id": stable_id("owner_trace", *parts),
        "correlation_id": stable_id("owner_correlation", *parts),
    }
    if attempt_generation is not None:
        identity["claim_id"] = stable_id("owner_claim", *parts)
    return identity


class _OwnerExecutionValidationMixin:
    """Validate stable identity metadata shared by owner execution paths."""

    @staticmethod
    def _require_claim(
        claim: TaskClaim,
        run: DelegationRun,
        identity: ExecutionIdentity,
        mission_id: str,
        attempt_generation: int | None,
    ) -> None:
        if (
            claim.claim_id != identity.claim_id
            or claim.task_id != identity.task_id
            or claim.agent_id != identity.agent_id
            or claim.session_id != identity.session_id
            or run.claim_id != claim.claim_id
        ):
            raise MissionControlError("owner claim conflicts with run identity")
        if claim.metadata.get("mission_id") != mission_id:
            raise MissionControlError("owner claim names a foreign mission")
        if (
            claim.metadata.get("attempt_generation") != attempt_generation
            or run.metadata.get("attempt_generation") != attempt_generation
            or identity.metadata.get("attempt_generation") != attempt_generation
        ):
            raise MissionControlError("owner records name a foreign attempt generation")
        if claim.status.lower() not in OWNER_CLAIM_STATUSES:
            raise MissionControlError("owner claim has an invalid status")

    @staticmethod
    def _expected_identity(
        mission_id: str,
        task_id: str,
        dispatch_key: str,
        attempt_generation: int | None,
    ) -> dict[str, str]:
        return owner_execution_identity(
            mission_id, task_id, dispatch_key, attempt_generation
        )

    def _stamp_metadata(
        self,
        task: Task,
        *,
        mission_id: str,
        dispatch_key: str,
        attempt_generation: int | None,
        expected: dict[str, str],
    ) -> dict[str, Any]:
        self._require_stamp_compatible(
            task.metadata, mission_id, dispatch_key, attempt_generation, expected
        )
        marker = {
            "schema_version": (
                EXECUTION_SCHEMA_VERSION
                if attempt_generation is not None
                else LEGACY_EXECUTION_SCHEMA_VERSION
            ),
            "backend": OWNER_BACKEND,
            "mission_id": mission_id,
            "task_id": task.id,
            "dispatch_key": dispatch_key,
            **expected,
        }
        if attempt_generation is not None:
            marker["attempt_generation"] = attempt_generation
        return {
            **dict(task.metadata),
            EXECUTION_METADATA_KEY: marker,
            "runtime_run_id": expected["run_id"],
            "run_id": expected["run_id"],
            "idempotency_key": expected["idempotency_key"],
            "trace_id": expected["trace_id"],
            "correlation_id": expected["correlation_id"],
            **({"claim_id": expected["claim_id"]} if "claim_id" in expected else {}),
            **(
                {"attempt_generation": attempt_generation}
                if attempt_generation is not None
                else {}
            ),
        }

    def _require_stamp(
        self,
        task: Task,
        mission_id: str,
        dispatch_key: str,
        attempt_generation: int | None,
        expected: dict[str, str],
    ) -> None:
        self._require_stamp_compatible(
            task.metadata, mission_id, dispatch_key, attempt_generation, expected
        )
        marker = task.metadata.get(EXECUTION_METADATA_KEY)
        if not isinstance(marker, dict):
            raise MissionControlError("owner dispatch metadata was not persisted")

    @staticmethod
    def _require_stamp_compatible(
        metadata: dict[str, Any],
        mission_id: str,
        dispatch_key: str,
        attempt_generation: int | None,
        expected: dict[str, str],
    ) -> None:
        marker = metadata.get(EXECUTION_METADATA_KEY)
        if marker is not None and not isinstance(marker, dict):
            raise MissionControlError("owner execution metadata has an invalid shape")
        if isinstance(marker, dict):
            required = {
                "schema_version": (
                    EXECUTION_SCHEMA_VERSION
                    if attempt_generation is not None
                    else LEGACY_EXECUTION_SCHEMA_VERSION
                ),
                "backend": OWNER_BACKEND,
                "mission_id": mission_id,
                "dispatch_key": dispatch_key,
                **expected,
            }
            if attempt_generation is not None:
                required["attempt_generation"] = attempt_generation
            if any(marker.get(key) != value for key, value in required.items()):
                raise MissionControlError("task carries a conflicting owner dispatch")
        elif any(
            str(metadata.get(key) or "").strip()
            for key in (
                "runtime_run_id",
                "run_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
            )
        ) or isinstance(metadata.get("execution_identity"), dict):
            raise MissionControlError(
                "task already carries foreign execution identity metadata"
            )
        for key in (
            "runtime_run_id",
            "run_id",
            "idempotency_key",
            "trace_id",
            "correlation_id",
        ):
            value = str(metadata.get(key) or "").strip()
            if (
                value
                and value != expected[key if key != "runtime_run_id" else "run_id"]
            ):
                raise MissionControlError(
                    "task owner identity metadata is inconsistent"
                )
        nested = metadata.get("execution_identity")
        if isinstance(nested, dict):
            for key in (
                "run_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
            ):
                value = str(nested.get(key) or "").strip()
                if value and value != expected[key]:
                    raise MissionControlError("nested owner identity is inconsistent")
        expected_claim = expected.get("claim_id", "")
        if expected_claim:
            if (
                (marker is not None or metadata.get("claim_id"))
                and str(metadata.get("claim_id") or "") != expected_claim
            ) or (
                isinstance(nested, dict)
                and str(nested.get("claim_id") or "") != expected_claim
            ):
                raise MissionControlError("owner claim identity is inconsistent")

    @staticmethod
    def _require_dispatch_metadata(
        metadata: dict[str, Any],
        expected: dict[str, str],
        attempt_generation: int | None,
    ) -> None:
        nested = metadata.get("execution_identity")
        identity = nested if isinstance(nested, dict) else {}
        observed_run = str(
            identity.get("run_id")
            or metadata.get("runtime_run_id")
            or metadata.get("run_id")
            or ""
        )
        observed_key = str(
            identity.get("idempotency_key") or metadata.get("idempotency_key") or ""
        )
        observed_claim = str(
            identity.get("claim_id") or metadata.get("claim_id") or ""
        )
        if (
            observed_run != expected["run_id"]
            or observed_key != expected["idempotency_key"]
            or (
                attempt_generation is not None
                and metadata.get("attempt_generation") != attempt_generation
            )
            or (
                attempt_generation is not None
                and observed_claim != expected.get("claim_id")
            )
        ):
            raise MissionControlError("Orchestrator changed the stable owner identity")


__all__ = [
    "EXECUTION_METADATA_KEY",
    "EXECUTION_SCHEMA_VERSION",
    "LEGACY_EXECUTION_SCHEMA_VERSION",
    "OWNER_BACKEND",
    "OWNER_CLAIM_STATUSES",
    "OWNER_RUN_STATUSES",
    "OWNER_TERMINAL_STATUSES",
    "owner_execution_identity",
    "terminal_projection_is_acknowledged",
    "terminal_projection_is_pending",
]
