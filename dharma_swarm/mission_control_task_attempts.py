"""Exact TaskBoard CAS protocol for bounded campaign attempt generations."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Literal, Protocol

import aiosqlite

from dharma_swarm.models import TaskStatus, _utc_now

CAMPAIGN_AUTHORITY_KEY = "mission_campaign_authority"
CAMPAIGN_GOVERNANCE_KEY = "mission_control_governance"
CAMPAIGN_ATTEMPT_HISTORY_KEY = "campaign_dispatch_attempt_history"
OWNER_EXECUTION_KEY = "mission_control_owner_execution"
AUTHORITY_SCHEMA_V4 = "dharma.sadhana.campaign_task_authority.v4"
GOVERNANCE_SCHEMA_V4 = "dharma.sadhana.campaign_governance.v4"
OWNER_SCHEMA_V2 = "dharma.mission_control.owner_execution.v2"
RECOVERY_SCHEMA_V2 = "dharma.sadhana.dispatch_recovery.v2"
ATTEMPT_EVIDENCE_SCHEMA_V1 = "dharma.sadhana.dispatch_attempt_evidence.v1"
INDETERMINATE_RESULT = (
    "dispatch_indeterminate: exception before provider task scheduling"
)
OWNER_IDENTITY_KEYS = (
    "runtime_run_id",
    "run_id",
    "claim_id",
    "idempotency_key",
    "trace_id",
    "correlation_id",
    "execution_identity",
    "agent_id",
    "session_id",
    "active_claim",
    "last_claim",
    "runtime_run_started_at",
)

_AUTHORITY_FIELDS = frozenset(
    {
        "schema_version", "campaign_id", "mission_id", "goal_id",
        "portfolio_contract_sha256", "goal_contract_sha256", "manifest_digest",
        "agent_roster_sha256", "effect_mode", "campaign_end", "agent_name",
        "claimed_principal", "dispatch_key", "request_id", "workspace_path",
        "allowed_files", "max_usd", "authority_ref", "authority_digest",
        "attempt_generation", "max_attempts", "observed_input_manifest_digest",
        "held_out_oracle_manifest_digest", "operator_control_semantics_sha256",
        "operator_control_authority_binding_sha256",
        "deployment_authority_topology_sha256",
        "deployment_authority_credential_clarification_sha256",
        "observed_input_ref",
    }
)
_GOVERNANCE_FIELDS = frozenset(
    {
        "schema_version", "campaign_id", "mission_id", "goal_id",
        "portfolio_contract_sha256", "goal_contract_sha256", "manifest_digest",
        "agent_roster_sha256", "effect_mode", "campaign_end", "workspace_path",
        "allowed_files", "forbidden_files", "max_usd", "attempt_generation",
        "max_attempts", "observed_input_manifest_digest",
        "held_out_oracle_manifest_digest", "operator_control_semantics_sha256",
        "operator_control_authority_binding_sha256",
        "deployment_authority_topology_sha256",
        "deployment_authority_credential_clarification_sha256",
        "observed_input_ref",
    }
)
_OWNER_FIELDS = frozenset(
    {
        "schema_version", "backend", "mission_id", "task_id", "dispatch_key",
        "attempt_generation", "run_id", "claim_id", "idempotency_key",
        "trace_id", "correlation_id",
    }
)
_RECOVERY_FIELDS = frozenset(
    {
        "schema_version", "state", "task_id", "authenticated_principal",
        "prior_status", "provider_task_scheduled", "attempt_generation",
        "max_attempts", "dispatch_key", "request_id", "authority_ref",
        "authority_digest", "run_id", "claim_id", "idempotency_key",
    }
)
_EVIDENCE_FIELDS = frozenset(
    {
        "schema_version", "attempt_generation", "terminal_status", "result",
        "authority", "owner_execution", "recovery",
    }
)
_DYNAMIC_AUTHORITY_FIELDS = frozenset(
    {
        "claimed_principal", "dispatch_key", "request_id", "authority_ref",
        "authority_digest", "attempt_generation",
    }
)


class CampaignAttemptBoard(Protocol):
    def _open(self) -> AbstractAsyncContextManager[aiosqlite.Connection]: ...

    @staticmethod
    def _coerce_db_value(column: str, value: Any) -> Any: ...


class CampaignTaskAttemptError(ValueError):
    """Campaign attempt evidence or successor authority is malformed."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise CampaignTaskAttemptError(message)


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _generation(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _observed_ref(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "receipt_id",
            "receipt_sha256",
            "artifact_id",
            "artifact_record_sha256",
            "content_sha256",
        }
        and _text(value.get("receipt_id"))
        and _text(value.get("artifact_id"))
        and all(
            _sha256(value.get(key))
            for key in (
                "receipt_sha256",
                "artifact_record_sha256",
                "content_sha256",
            )
        )
    )


def _validate_authority(authority: Any, *, task_id: str = "") -> tuple[int, int]:
    _need(
        isinstance(authority, dict)
        and set(authority) == _AUTHORITY_FIELDS
        and authority.get("schema_version") == AUTHORITY_SCHEMA_V4,
        "campaign authority evidence is not exact",
    )
    generation = authority["attempt_generation"]
    maximum = authority["max_attempts"]
    _need(
        _generation(generation)
        and _generation(maximum)
        and maximum > 0
        and generation < maximum
        and authority.get("effect_mode") == "read_only"
        and authority.get("max_usd") == 0
        and not isinstance(authority.get("max_usd"), bool)
        and all(
            _text(authority.get(key))
            for key in (
                "campaign_id", "mission_id", "goal_id", "claimed_principal",
                "dispatch_key", "request_id", "authority_ref", "authority_digest",
            )
        )
        and authority.get("campaign_id") == authority.get("mission_id")
        and all(
            _sha256(authority.get(key))
            for key in (
                "observed_input_manifest_digest",
                "held_out_oracle_manifest_digest",
                "operator_control_semantics_sha256",
                "operator_control_authority_binding_sha256",
                "deployment_authority_topology_sha256",
                "deployment_authority_credential_clarification_sha256",
            )
        )
        and _observed_ref(authority.get("observed_input_ref")),
        "campaign authority generation is invalid",
    )
    return generation, maximum


def _validate_owner(
    owner: Any,
    authority: dict[str, Any],
    *,
    task_id: str,
) -> None:
    _need(
        isinstance(owner, dict)
        and set(owner) == _OWNER_FIELDS
        and owner.get("schema_version") == OWNER_SCHEMA_V2
        and owner.get("backend") == "orchestrator"
        and owner.get("task_id") == task_id
        and (
            owner.get("mission_id"),
            owner.get("dispatch_key"),
            owner.get("attempt_generation"),
        )
        == (
            authority.get("mission_id"),
            authority.get("dispatch_key"),
            authority.get("attempt_generation"),
        )
        and all(
            _text(owner.get(key))
            for key in (
                "run_id", "claim_id", "idempotency_key", "trace_id",
                "correlation_id",
            )
        ),
        "campaign owner evidence is not exact",
    )


def _validate_governance(
    governance: Any,
    authority: dict[str, Any],
) -> None:
    shared = _GOVERNANCE_FIELDS - {"schema_version", "forbidden_files"}
    _need(
        isinstance(governance, dict)
        and set(governance) == _GOVERNANCE_FIELDS
        and governance.get("schema_version") == GOVERNANCE_SCHEMA_V4
        and governance.get("forbidden_files") == []
        and all(governance.get(key) == authority.get(key) for key in shared),
        "campaign governance evidence is not exact",
    )


def _validate_recovery(
    recovery: Any,
    authority: dict[str, Any],
    owner: dict[str, Any],
    *,
    task_id: str,
    agent_id: str,
    terminal_status: TaskStatus,
) -> None:
    expected_prior = (
        TaskStatus.ASSIGNED.value
        if terminal_status is TaskStatus.CANCELLED
        else TaskStatus.RUNNING.value
    )
    _need(
        isinstance(recovery, dict)
        and set(recovery) == _RECOVERY_FIELDS
        and recovery.get("schema_version") == RECOVERY_SCHEMA_V2
        and recovery.get("state") == "dispatch_indeterminate"
        and recovery.get("task_id") == task_id
        and recovery.get("authenticated_principal") == agent_id
        and recovery.get("prior_status") == expected_prior
        and recovery.get("provider_task_scheduled") is False
        and all(
            recovery.get(key) == authority.get(key)
            for key in (
                "attempt_generation", "max_attempts", "dispatch_key", "request_id",
                "authority_ref", "authority_digest",
            )
        )
        and all(
            recovery.get(key) == owner.get(key)
            for key in ("run_id", "claim_id", "idempotency_key")
        ),
        "campaign indeterminate evidence is foreign",
    )


def _validate_history(
    history: Any,
    current_authority: dict[str, Any],
    *,
    task_id: str,
    generation: int,
    maximum: int,
) -> None:
    _need(type(history) is list and len(history) == generation, "campaign attempt history is not append-only")
    static = _AUTHORITY_FIELDS - _DYNAMIC_AUTHORITY_FIELDS
    for index, evidence in enumerate(history):
        _need(
            isinstance(evidence, dict)
            and set(evidence) == _EVIDENCE_FIELDS
            and evidence.get("schema_version") == ATTEMPT_EVIDENCE_SCHEMA_V1
            and evidence.get("attempt_generation") == index
            and evidence.get("result") == INDETERMINATE_RESULT,
            "campaign attempt history evidence is malformed",
        )
        terminal = evidence.get("terminal_status")
        _need(terminal in {"cancelled", "failed"}, "campaign attempt terminal status is invalid")
        authority = evidence.get("authority")
        prior_generation, prior_maximum = _validate_authority(authority, task_id=task_id)
        assert isinstance(authority, dict)
        _need(
            (prior_generation, prior_maximum) == (index, maximum)
            and all(authority.get(key) == current_authority.get(key) for key in static),
            "campaign attempt history authority is foreign",
        )
        owner = evidence.get("owner_execution")
        _validate_owner(owner, authority, task_id=task_id)
        assert isinstance(owner, dict)
        terminal_status = TaskStatus(str(terminal))
        _validate_recovery(
            evidence.get("recovery"), authority, owner,
            task_id=task_id,
            agent_id=str(authority["claimed_principal"]),
            terminal_status=terminal_status,
        )


def validate_campaign_terminal_attempt(task: Any) -> dict[str, Any]:
    """Validate one exact terminal generation without mutating its board row."""
    _need(
        task.status in {TaskStatus.CANCELLED, TaskStatus.FAILED}
        and _text(task.assigned_to)
        and task.result == INDETERMINATE_RESULT,
        "campaign terminal attempt row is not exact",
    )
    metadata = task.metadata
    authority = metadata.get(CAMPAIGN_AUTHORITY_KEY)
    generation, maximum = _validate_authority(authority, task_id=task.id)
    assert isinstance(authority, dict)
    owner = metadata.get(OWNER_EXECUTION_KEY)
    _validate_owner(owner, authority, task_id=task.id)
    assert isinstance(owner, dict)
    _validate_governance(metadata.get(CAMPAIGN_GOVERNANCE_KEY), authority)
    _need(
        task.assigned_to == authority.get("claimed_principal")
        and maximum == metadata.get("attempt_ceiling")
        and generation == metadata.get("attempt_generation")
        and all(owner.get(key) == metadata.get(key) for key in (
            "run_id", "claim_id", "idempotency_key", "trace_id", "correlation_id",
        )),
        "campaign terminal attempt carrier is not exact",
    )
    _validate_recovery(
        metadata.get("campaign_dispatch_recovery"),
        authority,
        owner,
        task_id=task.id,
        agent_id=task.assigned_to,
        terminal_status=task.status,
    )
    _validate_history(
        metadata.get(CAMPAIGN_ATTEMPT_HISTORY_KEY, []),
        authority,
        task_id=task.id,
        generation=generation,
        maximum=maximum,
    )
    return authority


async def resolve_campaign_pre_effect_failure(
    board: CampaignAttemptBoard,
    task_id: str,
    *,
    expected_status: TaskStatus,
    expected_agent_id: str | None,
    expected_metadata: dict[str, Any],
    authenticated_principal: str,
    provider_task_scheduled: bool = False,
) -> Literal["pending", "indeterminate", "conflict"]:
    _need(
        expected_status in {TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING},
        "campaign recovery expected status is invalid",
    )
    _need(_text(authenticated_principal), "campaign recovery principal is invalid")
    _need(type(provider_task_scheduled) is bool, "campaign provider scheduling witness is invalid")
    if provider_task_scheduled:
        return "conflict"
    authority = expected_metadata.get(CAMPAIGN_AUTHORITY_KEY)
    generation, maximum = _validate_authority(authority, task_id=task_id)
    assert isinstance(authority, dict)
    owner = expected_metadata.get(OWNER_EXECUTION_KEY)
    _validate_owner(owner, authority, task_id=task_id)
    assert isinstance(owner, dict)
    governance = expected_metadata.get(CAMPAIGN_GOVERNANCE_KEY)
    _validate_governance(governance, authority)
    _need(
        authority.get("claimed_principal") == authenticated_principal
        and maximum == expected_metadata.get("attempt_ceiling")
        and expected_metadata.get("attempt_generation") == generation
        and all(owner.get(key) == expected_metadata.get(key) for key in (
            "run_id", "claim_id", "idempotency_key", "trace_id", "correlation_id",
        )),
        "campaign recovery evidence is not exact",
    )
    if expected_status is TaskStatus.PENDING:
        _need(expected_agent_id is None, "pending campaign recovery cannot name an assignee")
    else:
        _need(
            expected_agent_id == authenticated_principal,
            "campaign recovery assignee is not authenticated",
        )
    expected_json = board._coerce_db_value("metadata", expected_metadata)
    async with board._open() as db:
        await db.execute("BEGIN IMMEDIATE")
        row = await (
            await db.execute(
                "SELECT status, assigned_to, metadata FROM tasks WHERE id = ?",
                (task_id,),
            )
        ).fetchone()
        if row != (expected_status.value, expected_agent_id, expected_json):
            await db.rollback()
            return "conflict"
        if expected_status is TaskStatus.PENDING:
            await db.commit()
            return "pending"
        terminal_status = (
            TaskStatus.CANCELLED
            if expected_status is TaskStatus.ASSIGNED
            else TaskStatus.FAILED
        )
        metadata = {
            **expected_metadata,
            "campaign_dispatch_recovery": {
                "schema_version": RECOVERY_SCHEMA_V2,
                "state": "dispatch_indeterminate",
                "task_id": task_id,
                "authenticated_principal": authenticated_principal,
                "prior_status": expected_status.value,
                "provider_task_scheduled": False,
                "attempt_generation": generation,
                "max_attempts": maximum,
                "dispatch_key": authority["dispatch_key"],
                "request_id": authority["request_id"],
                "authority_ref": authority["authority_ref"],
                "authority_digest": authority["authority_digest"],
                "run_id": owner["run_id"],
                "claim_id": owner["claim_id"],
                "idempotency_key": owner["idempotency_key"],
            },
        }
        cursor = await db.execute(
            "UPDATE tasks SET status = ?, result = ?, metadata = ?, updated_at = ? "
            "WHERE id = ? AND status = ? AND assigned_to = ? AND metadata = ?",
            (
                terminal_status.value,
                INDETERMINATE_RESULT,
                board._coerce_db_value("metadata", metadata),
                _utc_now().isoformat(),
                task_id,
                expected_status.value,
                expected_agent_id,
                expected_json,
            ),
        )
        if cursor.rowcount != 1:
            await db.rollback()
            return "conflict"
        await db.commit()
        return "indeterminate"


async def advance_campaign_dispatch_attempt(
    board: CampaignAttemptBoard,
    task_id: str,
    *,
    expected_status: TaskStatus,
    expected_agent_id: str,
    expected_metadata: dict[str, Any],
    next_authority: dict[str, Any],
    next_governance: dict[str, Any],
    next_routing: dict[str, Any],
) -> Literal["advanced", "exhausted", "conflict"]:
    _need(
        expected_status in {TaskStatus.CANCELLED, TaskStatus.FAILED},
        "campaign attempt advance requires a terminal row",
    )
    authority = expected_metadata.get(CAMPAIGN_AUTHORITY_KEY)
    generation, maximum = _validate_authority(authority, task_id=task_id)
    assert isinstance(authority, dict)
    owner = expected_metadata.get(OWNER_EXECUTION_KEY)
    _validate_owner(owner, authority, task_id=task_id)
    assert isinstance(owner, dict)
    governance = expected_metadata.get(CAMPAIGN_GOVERNANCE_KEY)
    _validate_governance(governance, authority)
    _need(
        maximum == expected_metadata.get("attempt_ceiling")
        and expected_agent_id == authority.get("claimed_principal"),
        "campaign attempt bounds are invalid",
    )
    _validate_recovery(
        expected_metadata.get("campaign_dispatch_recovery"),
        authority,
        owner,
        task_id=task_id,
        agent_id=expected_agent_id,
        terminal_status=expected_status,
    )
    history = expected_metadata.get(CAMPAIGN_ATTEMPT_HISTORY_KEY, [])
    _validate_history(
        history,
        authority,
        task_id=task_id,
        generation=generation,
        maximum=maximum,
    )
    expected_json = board._coerce_db_value("metadata", expected_metadata)
    async with board._open() as db:
        await db.execute("BEGIN IMMEDIATE")
        row = await (
            await db.execute(
                "SELECT status, assigned_to, result, metadata FROM tasks WHERE id = ?",
                (task_id,),
            )
        ).fetchone()
        if row != (
            expected_status.value,
            expected_agent_id,
            INDETERMINATE_RESULT,
            expected_json,
        ):
            await db.rollback()
            return "conflict"
        if generation + 1 >= maximum:
            await db.commit()
            return "exhausted"
        next_generation, next_maximum = _validate_authority(next_authority, task_id=task_id)
        _validate_governance(next_governance, next_authority)
        dynamic = _DYNAMIC_AUTHORITY_FIELDS
        routing_fields = {
            "campaign_effect_mode", "requires_tooling", "allow_provider_routing",
            "provider_allowlist", "preferred_provider", "preferred_model",
        }
        _need(
            (next_generation, next_maximum) == (generation + 1, maximum)
            and all(
                next_authority.get(key) == value
                for key, value in authority.items()
                if key not in dynamic
            )
            and set(next_routing) == routing_fields
            and next_routing.get("campaign_effect_mode") == "read_only"
            and next_routing.get("requires_tooling") is False
            and next_routing.get("allow_provider_routing") is False
            and next_routing.get("provider_allowlist")
            == [next_routing.get("preferred_provider")]
            and _text(next_routing.get("preferred_provider"))
            and _text(next_routing.get("preferred_model")),
            "next campaign attempt authority is not an exact successor",
        )
        evidence = {
            "schema_version": ATTEMPT_EVIDENCE_SCHEMA_V1,
            "attempt_generation": generation,
            "terminal_status": expected_status.value,
            "result": INDETERMINATE_RESULT,
            "authority": authority,
            "owner_execution": owner,
            "recovery": expected_metadata["campaign_dispatch_recovery"],
        }
        metadata = {
            key: value
            for key, value in expected_metadata.items()
            if key
            not in {*OWNER_IDENTITY_KEYS, OWNER_EXECUTION_KEY, "campaign_dispatch_recovery"}
        }
        metadata.update(next_routing)
        metadata[CAMPAIGN_AUTHORITY_KEY] = next_authority
        metadata[CAMPAIGN_GOVERNANCE_KEY] = next_governance
        metadata[CAMPAIGN_ATTEMPT_HISTORY_KEY] = [*history, evidence]
        metadata["attempt_generation"] = generation + 1
        cursor = await db.execute(
            "UPDATE tasks SET status = ?, assigned_to = NULL, result = NULL,"
            " metadata = ?, updated_at = ? WHERE id = ? AND status = ?"
            " AND assigned_to = ? AND result = ? AND metadata = ?",
            (
                TaskStatus.PENDING.value,
                board._coerce_db_value("metadata", metadata),
                _utc_now().isoformat(),
                task_id,
                expected_status.value,
                expected_agent_id,
                INDETERMINATE_RESULT,
                expected_json,
            ),
        )
        if cursor.rowcount != 1:
            await db.rollback()
            return "conflict"
        await db.commit()
    return "advanced"


__all__ = [
    "CampaignTaskAttemptError",
    "advance_campaign_dispatch_attempt",
    "resolve_campaign_pre_effect_failure",
    "validate_campaign_terminal_attempt",
]
