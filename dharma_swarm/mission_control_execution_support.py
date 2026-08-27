"""Internal validation support for Mission Control owner execution."""

from __future__ import annotations

from typing import Any

from dharma_swarm.mission_control_contract import MissionControlError, stable_id
from dharma_swarm.models import Task
from dharma_swarm.runtime_state import DelegationRun, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity


EXECUTION_SCHEMA_VERSION = "dharma.mission_control.owner_execution.v1"
EXECUTION_METADATA_KEY = "mission_control_owner_execution"
OWNER_BACKEND = "orchestrator"
OWNER_TERMINAL_STATUSES = frozenset({"completed", "failed"})
OWNER_RUN_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})
OWNER_CLAIM_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})


class _OwnerExecutionValidationMixin:
    """Validate stable identity metadata shared by owner execution paths."""

    @staticmethod
    def _require_claim(
        claim: TaskClaim,
        run: DelegationRun,
        identity: ExecutionIdentity,
        mission_id: str,
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
        if claim.status.lower() not in OWNER_CLAIM_STATUSES:
            raise MissionControlError("owner claim has an invalid status")

    @staticmethod
    def _expected_identity(
        mission_id: str,
        task_id: str,
        dispatch_key: str,
    ) -> dict[str, str]:
        parts = (mission_id, task_id, dispatch_key)
        return {
            "run_id": stable_id("owner_run", *parts),
            "idempotency_key": stable_id("owner_dispatch", *parts),
            "trace_id": stable_id("owner_trace", *parts),
            "correlation_id": stable_id("owner_correlation", *parts),
        }

    def _stamp_metadata(
        self,
        task: Task,
        *,
        mission_id: str,
        dispatch_key: str,
        expected: dict[str, str],
    ) -> dict[str, Any]:
        self._require_stamp_compatible(
            task.metadata, mission_id, dispatch_key, expected
        )
        marker = {
            "schema_version": EXECUTION_SCHEMA_VERSION,
            "backend": OWNER_BACKEND,
            "mission_id": mission_id,
            "task_id": task.id,
            "dispatch_key": dispatch_key,
            **expected,
        }
        return {
            **dict(task.metadata),
            EXECUTION_METADATA_KEY: marker,
            "runtime_run_id": expected["run_id"],
            "run_id": expected["run_id"],
            "idempotency_key": expected["idempotency_key"],
            "trace_id": expected["trace_id"],
            "correlation_id": expected["correlation_id"],
        }

    def _require_stamp(
        self,
        task: Task,
        mission_id: str,
        dispatch_key: str,
        expected: dict[str, str],
    ) -> None:
        self._require_stamp_compatible(
            task.metadata, mission_id, dispatch_key, expected
        )
        marker = task.metadata.get(EXECUTION_METADATA_KEY)
        if not isinstance(marker, dict):
            raise MissionControlError("owner dispatch metadata was not persisted")

    @staticmethod
    def _require_stamp_compatible(
        metadata: dict[str, Any],
        mission_id: str,
        dispatch_key: str,
        expected: dict[str, str],
    ) -> None:
        marker = metadata.get(EXECUTION_METADATA_KEY)
        if marker is not None and not isinstance(marker, dict):
            raise MissionControlError("owner execution metadata has an invalid shape")
        if isinstance(marker, dict):
            required = {
                "schema_version": EXECUTION_SCHEMA_VERSION,
                "backend": OWNER_BACKEND,
                "mission_id": mission_id,
                "dispatch_key": dispatch_key,
                **expected,
            }
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
            for key in ("run_id", "idempotency_key", "trace_id", "correlation_id"):
                value = str(nested.get(key) or "").strip()
                if value and value != expected[key]:
                    raise MissionControlError("nested owner identity is inconsistent")

    @staticmethod
    def _require_dispatch_metadata(
        metadata: dict[str, Any],
        expected: dict[str, str],
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
        if (
            observed_run != expected["run_id"]
            or observed_key != expected["idempotency_key"]
        ):
            raise MissionControlError("Orchestrator changed the stable owner identity")


__all__ = [
    "EXECUTION_METADATA_KEY",
    "EXECUTION_SCHEMA_VERSION",
    "OWNER_BACKEND",
    "OWNER_CLAIM_STATUSES",
    "OWNER_RUN_STATUSES",
    "OWNER_TERMINAL_STATUSES",
]
