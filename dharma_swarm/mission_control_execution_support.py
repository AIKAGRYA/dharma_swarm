"""Internal validation support for Mission Control owner execution."""

from __future__ import annotations

from typing import Any

from dharma_swarm.mission_control_contract import MissionControlError, stable_id
from dharma_swarm.models import Task
from dharma_swarm.runtime_state import DelegationRun, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity


LEGACY_EXECUTION_SCHEMA_VERSION = "dharma.mission_control.owner_execution.v1"
EXECUTION_SCHEMA_VERSION = "dharma.mission_control.owner_execution.v2"
EXECUTION_METADATA_KEY = "mission_control_owner_execution"
OWNER_BACKEND = "orchestrator"
OWNER_TERMINAL_STATUSES = frozenset({"completed", "failed"})
OWNER_RUN_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})
OWNER_CLAIM_STATUSES = frozenset({"claimed", "running", *OWNER_TERMINAL_STATUSES})


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
]
