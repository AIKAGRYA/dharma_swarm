"""Execution identity helper for RuntimeLifecycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from dharma_swarm.mission_control_task_attempts import (
    GOVERNANCE_SCHEMA_V4,
    _GOVERNANCE_FIELDS,
    _validate_authority,
    _validate_governance,
    _validate_history,
    _validate_owner,
)
from dharma_swarm.models import Task, TaskDispatch
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


_CAMPAIGN_AUTHORITY_SCHEMA = "dharma.sadhana.campaign_task_authority.v5"
_CAMPAIGN_OWNER_SCHEMA = "dharma.mission_control.owner_execution.v2"
_CAMPAIGN_OWNER_FIELDS = frozenset(
    {
        "schema_version",
        "backend",
        "mission_id",
        "task_id",
        "dispatch_key",
        "attempt_generation",
        "run_id",
        "claim_id",
        "idempotency_key",
        "trace_id",
        "correlation_id",
    }
)
_INITIAL_CAMPAIGN_PROMOTION_ADDITIONS = frozenset(
    (
        "sadhana_bootstrap_schema goal_contract_schema campaign_id goal_id "
        "portfolio_contract_sha256 goal_contract_sha256 cash_ceiling_usd "
        "attempt_ceiling attempt_generation dispatch_ready dispatch_blocker "
        "campaign_effect_mode requires_tooling allow_provider_routing "
        "provider_allowlist preferred_provider preferred_model mission_task_id "
        "mission_observed_input mission_control_governance"
    ).split()
)
_INITIAL_CAMPAIGN_PROMOTION_FORBIDDEN = frozenset(
    (
        "mission_control_owner_execution active_claim last_claim execution_identity "
        "runtime_run_id runtime_db_path runtime_run_started_at task_id run_id claim_id "
        "idempotency_key trace_id correlation_id agent_id session_id causation_id "
        "parent_run_id external_a2a_task_id message_id event_id artifact_id "
        "proposal_id task_board_completion_binding graph_reconcile_projection "
        "graph_reconcile_projection_history"
    ).split()
)
BOARD_CAMPAIGN_AUTHORITY_FIELDS = frozenset(
    (
        "schema_version mission_id mission_task_id mission_task_idempotency_key "
        "goal_contract_schema campaign_id goal_id portfolio_contract_sha256 "
        "goal_contract_sha256 manifest_digest agent_roster_sha256 effect_mode "
        "campaign_effect_mode campaign_end workspace_path allowed_files max_usd "
        "cash_ceiling_usd max_attempts attempt_ceiling attempt_generation "
        "claimed_principal dispatch_key request_id authority_ref authority_digest "
        "observed_input_manifest_digest held_out_oracle_manifest_digest "
        "operator_control_semantics_sha256 operator_control_authority_binding_sha256 "
        "deployment_authority_topology_sha256 "
        "deployment_authority_credential_clarification_sha256 observed_input_ref "
        "mission_observed_input allow_provider_routing provider_allowlist "
        "preferred_provider preferred_model requires_tooling dispatch_ready "
        "dispatch_blocker"
    ).split()
)


def valid_campaign_authority(authority: Any, *, task_id: str) -> bool:
    try:
        _validate_authority(authority, task_id=task_id)
    except ValueError:
        return False
    return True


def _flat_campaign_authority_closes(
    metadata: dict[str, Any],
    authority: dict[str, Any],
    *,
    task_id: str,
) -> bool:
    required = {
        "campaign_id": "campaign_id",
        "goal_id": "goal_id",
        "attempt_generation": "attempt_generation",
        "attempt_ceiling": "max_attempts",
    }
    optional = {
        "mission_id": "mission_id",
        "portfolio_contract_sha256": "portfolio_contract_sha256",
        "goal_contract_sha256": "goal_contract_sha256",
        "manifest_digest": "manifest_digest",
        "agent_roster_sha256": "agent_roster_sha256",
        "effect_mode": "effect_mode",
        "campaign_effect_mode": "effect_mode",
        "campaign_end": "campaign_end",
        "workspace_path": "workspace_path",
        "allowed_files": "allowed_files",
        "max_usd": "max_usd",
        "cash_ceiling_usd": "max_usd",
        "max_attempts": "max_attempts",
        "claimed_principal": "claimed_principal",
        "dispatch_key": "dispatch_key",
        "request_id": "request_id",
        "authority_ref": "authority_ref",
        "authority_digest": "authority_digest",
        "observed_input_manifest_digest": "observed_input_manifest_digest",
        "held_out_oracle_manifest_digest": "held_out_oracle_manifest_digest",
        "operator_control_semantics_sha256": "operator_control_semantics_sha256",
        "operator_control_authority_binding_sha256": (
            "operator_control_authority_binding_sha256"
        ),
        "deployment_authority_topology_sha256": (
            "deployment_authority_topology_sha256"
        ),
        "deployment_authority_credential_clarification_sha256": (
            "deployment_authority_credential_clarification_sha256"
        ),
        "observed_input_ref": "observed_input_ref",
    }
    if (
        metadata.get("mission_task_id", task_id) != task_id
        or any(
            metadata.get(flat) != authority.get(bound)
            for flat, bound in required.items()
        )
        or any(
            flat in metadata and metadata.get(flat) != authority.get(bound)
            for flat, bound in optional.items()
        )
    ):
        return False
    route = authority.get("route_lock")
    route_fields = {
        "allow_provider_routing",
        "provider_allowlist",
        "preferred_provider",
        "preferred_model",
        "requires_tooling",
    }
    if any(key in metadata for key in route_fields) and (
        not isinstance(route, dict)
        or metadata.get("allow_provider_routing")
        != route.get("allow_provider_routing")
        or metadata.get("provider_allowlist") != [route.get("provider")]
        or metadata.get("preferred_provider") != route.get("provider")
        or metadata.get("preferred_model") != route.get("model")
        or metadata.get("requires_tooling") is not False
    ):
        return False
    observed = metadata.get("mission_observed_input")
    if observed is not None and (
        not isinstance(observed, dict)
        or any(
            observed.get(field) != expected
            for field, expected in {
                "campaign_id": authority.get("campaign_id"),
                "mission_id": authority.get("mission_id"),
                "goal_id": authority.get("goal_id"),
                "task_id": task_id,
                "manifest_digest": authority.get("observed_input_manifest_digest"),
                "goal_contract_sha256": authority.get("goal_contract_sha256"),
                "observed_input_ref": authority.get("observed_input_ref"),
                "content_sha256": authority.get("observed_input_ref", {}).get(
                    "content_sha256"
                ),
            }.items()
        )
    ):
        return False
    return True


def valid_board_campaign_authority(
    metadata: dict[str, Any],
    *,
    task_id: str,
) -> bool:
    """Close typed authority over its Board bootstrap and governance aliases."""
    authority = metadata.get("mission_campaign_authority")
    try:
        generation, maximum = _validate_authority(authority, task_id=task_id)
        _validate_governance(metadata.get("mission_control_governance"), authority)
        _validate_owner(
            metadata.get("mission_control_owner_execution"),
            authority,
            task_id=task_id,
        )
        _validate_history(
            metadata.get("campaign_dispatch_attempt_history", []),
            authority,
            task_id=task_id,
            generation=generation,
            maximum=maximum,
        )
    except ValueError:
        return False
    return _flat_campaign_authority_closes(metadata, authority, task_id=task_id)


def valid_initial_campaign_authority_promotion(
    current: dict[str, Any],
    replacement: dict[str, Any],
    *,
    task_id: str,
    authority_key: str,
    campaign_only_carriers: set[str],
    bootstrap_schema: str,
) -> bool:
    """Recognize the exact legacy MissionControl-to-campaign typed promotion."""
    authority = replacement.get(authority_key)
    try:
        generation, maximum = _validate_authority(authority, task_id=task_id)
    except ValueError:
        return False
    governance_key = "mission_control_governance"
    if governance_key not in replacement:
        replacement[governance_key] = {
            key: GOVERNANCE_SCHEMA_V4 if key == "schema_version" else []
            if key == "forbidden_files" else authority[key]
            for key in _GOVERNANCE_FIELDS
        }
    try:
        _validate_governance(replacement.get(governance_key), authority)
    except ValueError:
        return False
    if not _flat_campaign_authority_closes(replacement, authority, task_id=task_id):
        return False
    coordinates = (
        authority.get("mission_id"),
        replacement.get("campaign_id"),
        replacement.get("goal_id"),
        replacement.get("mission_task_id"),
        replacement.get("attempt_generation"),
        replacement.get("attempt_ceiling"),
    )
    expected = (
        current.get("mission_id"),
        authority.get("campaign_id"),
        authority.get("goal_id"),
        task_id,
        generation,
        maximum,
    )
    required = (
        "mission_id",
        "mission_task_idempotency_key",
        "mission_task_creation_hash",
    )
    bootstrap = replacement.get("sadhana_bootstrap_schema")
    bootstrap_is_exact = bootstrap is None or (
        bootstrap == bootstrap_schema
        and replacement.get("campaign_id") == authority.get("campaign_id")
        and replacement.get("goal_id") == authority.get("goal_id")
        and replacement.get("mission_task_id") == task_id
        and replacement.get("mission_task_creation_hash")
        == current.get("mission_task_creation_hash")
    )
    allowed_additions = _INITIAL_CAMPAIGN_PROMOTION_ADDITIONS | {authority_key}
    return bool(
        current.get("schema_version") == "dharma.mission_control.v1"
        and all(isinstance(current.get(key), str) and current[key] for key in required)
        and all(
            replacement.get(key) == value
            for key, value in current.items()
            if key != governance_key
        )
        and coordinates == expected
        and set(replacement) - set(current) <= allowed_additions
        and not any(
            key in current or key in replacement
            for key in _INITIAL_CAMPAIGN_PROMOTION_FORBIDDEN
        )
        and not any(
            key in replacement
            for key in campaign_only_carriers - {authority_key}
        )
        and bootstrap_is_exact
    )


def _strict_claim_identity(
    metadata: dict[str, Any],
    *,
    task_id: str,
    agent_id: str,
    claim_id: str,
) -> ExecutionIdentity | None:
    """Load only a complete nested envelope bound to one exact custody claim."""
    nested = metadata.get("execution_identity")
    if not isinstance(nested, dict) or any(
        not isinstance(nested.get(field), str) or not nested[field].strip()
        for field in (
            "trace_id",
            "correlation_id",
            "task_id",
            "run_id",
            "claim_id",
            "idempotency_key",
            "agent_id",
            "session_id",
        )
    ):
        return None
    try:
        identity = ExecutionIdentity.from_metadata(metadata, require=True)
    except MissingExecutionIdentity:
        return None
    if (
        identity is None
        or identity.task_id != task_id
        or identity.agent_id != agent_id
        or identity.claim_id != claim_id
    ):
        return None
    aliases = {
        "task_id": identity.task_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "claim_id": identity.claim_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "idempotency_key": identity.idempotency_key,
        "causation_id": identity.causation_id,
        "parent_run_id": identity.parent_run_id,
        "external_a2a_task_id": identity.external_a2a_task_id,
        "message_id": identity.message_id,
        "event_id": identity.event_id,
        "artifact_id": identity.artifact_id,
        "proposal_id": identity.proposal_id,
    }
    if any(
        alias in metadata
        and metadata.get(alias) != expected
        for alias, expected in aliases.items()
    ):
        return None
    return identity


def _require_campaign_owner_identity(
    task_metadata: dict[str, Any],
    identity: ExecutionIdentity,
) -> None:
    """Close one campaign identity over its exact authority and owner stamp."""
    if "mission_campaign_authority" not in task_metadata:
        return
    authority = task_metadata.get("mission_campaign_authority")
    owner = task_metadata.get("mission_control_owner_execution")
    generation = authority.get("attempt_generation") if isinstance(authority, dict) else None
    valid = bool(
        isinstance(authority, dict)
        and authority.get("schema_version") == _CAMPAIGN_AUTHORITY_SCHEMA
        and isinstance(owner, dict)
        and set(owner) == _CAMPAIGN_OWNER_FIELDS
        and owner.get("schema_version") == _CAMPAIGN_OWNER_SCHEMA
        and owner.get("backend") == "orchestrator"
        and owner.get("task_id") == identity.task_id
        and authority.get("claimed_principal") == identity.agent_id
        and all(
            isinstance(authority.get(field), str)
            and bool(authority[field])
            and authority[field] == authority[field].strip()
            for field in ("mission_id", "dispatch_key", "claimed_principal")
        )
        and isinstance(generation, int)
        and not isinstance(generation, bool)
        and generation >= 0
        and (
            "attempt_generation" not in task_metadata
            or isinstance(task_metadata.get("attempt_generation"), int)
            and not isinstance(task_metadata.get("attempt_generation"), bool)
            and task_metadata.get("attempt_generation") == generation
        )
        and isinstance(owner.get("attempt_generation"), int)
        and not isinstance(owner.get("attempt_generation"), bool)
        and (
            owner.get("mission_id"),
            owner.get("dispatch_key"),
            owner.get("attempt_generation"),
        )
        == (
            authority.get("mission_id"),
            authority.get("dispatch_key"),
            generation,
        )
        and all(
            owner.get(field) == getattr(identity, field)
            for field in (
                "run_id",
                "claim_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
            )
        )
    )
    if not valid:
        raise MissingExecutionIdentity(
            "TaskBoard ExecutionIdentity contradicts owner attempt authority"
        )


def _persisted_claim_identity(
    runtime_state_store: Any | None,
    td: TaskDispatch,
    claim_id: str,
) -> ExecutionIdentity | None:
    """Recover the envelope durably recorded before provider execution."""
    get_claim = getattr(
        runtime_state_store,
        "get_task_claim_snapshot_sync",
        None,
    )
    if not callable(get_claim):
        # Preserve the narrow store protocol used by adapters and fixtures.
        get_claim = getattr(runtime_state_store, "get_task_claim_sync", None)
    if not callable(get_claim) or not claim_id:
        return None
    persisted = get_claim(claim_id)
    if persisted is None:
        return None
    if (
        getattr(persisted, "claim_id", None) != claim_id
        or getattr(persisted, "task_id", None) != td.task_id
        or getattr(persisted, "agent_id", None) != td.agent_id
    ):
        raise MissingExecutionIdentity(
            "Persisted claim does not bind the reconstructed dispatch"
        )
    identity = _strict_claim_identity(
        dict(getattr(persisted, "metadata", {}) or {}),
        task_id=td.task_id,
        agent_id=td.agent_id,
        claim_id=claim_id,
    )
    if identity is None:
        raise MissingExecutionIdentity(
            "Persisted claim lacks a complete exact ExecutionIdentity"
        )
    if getattr(persisted, "session_id", None) != identity.session_id:
        raise MissingExecutionIdentity(
            "Persisted claim session contradicts its ExecutionIdentity"
        )
    get_identity = getattr(
        runtime_state_store,
        "get_execution_identity_snapshot_sync",
        None,
    )
    if callable(get_identity):
        durable_identity = get_identity(identity.run_id)
        if durable_identity is not None and durable_identity != identity:
            raise MissingExecutionIdentity(
                "Persisted claim contradicts the durable ExecutionIdentity"
            )
    return identity


def _task_claim_identity(
    task_metadata: dict[str, Any],
    td: TaskDispatch,
    claim_id: str,
) -> ExecutionIdentity | None:
    """Recover an exact envelope already committed on the TaskBoard carrier."""
    identity = _strict_claim_identity(
        task_metadata,
        task_id=td.task_id,
        agent_id=td.agent_id,
        claim_id=claim_id,
    )
    nested = task_metadata.get("execution_identity")
    if identity is None:
        if isinstance(nested, dict):
            prior_claim = str(
                nested.get("claim_id") or task_metadata.get("claim_id") or ""
            ).strip()
            prior_identity = (
                _strict_claim_identity(
                    task_metadata,
                    task_id=td.task_id,
                    agent_id=td.agent_id,
                    claim_id=prior_claim,
                )
                if prior_claim
                else None
            )
            if prior_identity is None or prior_claim == claim_id:
                raise MissingExecutionIdentity(
                    "TaskBoard claim carrier lacks a complete exact ExecutionIdentity"
                )
            _require_campaign_owner_identity(task_metadata, prior_identity)
        return None
    _require_campaign_owner_identity(task_metadata, identity)
    return identity


def _rotate_attempt_identity_for_new_claim(
    td: TaskDispatch,
    task_metadata: dict[str, Any],
    *,
    session_id: str,
) -> ExecutionIdentity | None:
    """Start a fresh attempt when Board custody minted a different claim.

    Task metadata deliberately retains the previous attempt's receipt identity.
    It must never become the identity of a newly claimed retry.  Keep only the
    logical correlation and explicit parent-run lineage across that boundary.
    """
    incoming_claim = str(td.metadata.get("claim_id") or "").strip()
    nested = task_metadata.get("execution_identity")
    previous = nested if isinstance(nested, dict) else {}
    previous_claim = str(
        previous.get("claim_id") or task_metadata.get("claim_id") or ""
    ).strip()
    if not incoming_claim or not previous_claim or incoming_claim == previous_claim:
        return None
    previous_run = str(
        previous.get("run_id")
        or task_metadata.get("runtime_run_id")
        or task_metadata.get("run_id")
        or ""
    ).strip()
    correlation_id = str(
        previous.get("correlation_id")
        or task_metadata.get("correlation_id")
        or ""
    ).strip()
    rotated = ExecutionIdentity.new(
        task_id=td.task_id,
        agent_id=td.agent_id,
        session_id=session_id,
        correlation_id=correlation_id,
        causation_id=str(previous.get("causation_id") or ""),
        parent_run_id=previous_run,
        claim_id=incoming_claim,
        external_a2a_task_id=str(previous.get("external_a2a_task_id") or ""),
        metadata={
            "source": "runtime_lifecycle.rotate_retry_attempt",
            **(
                {"attempt_generation": td.metadata["attempt_generation"]}
                if isinstance(td.metadata.get("attempt_generation"), int)
                and not isinstance(td.metadata.get("attempt_generation"), bool)
                and td.metadata["attempt_generation"] >= 0
                else {}
            ),
        },
    )
    return rotated


def ensure_execution_identity_for_dispatch(
    td: TaskDispatch,
    *,
    task: Task | None,
    task_metadata: dict[str, Any],
    session_id: str,
    ensure_runtime_run_id: Callable[[TaskDispatch], str],
    runtime_state_store: Any | None,
    require: bool = False,
) -> ExecutionIdentity:
    incoming_claim = str(td.metadata.get("claim_id") or "").strip()
    if require and not incoming_claim:
        raise MissingExecutionIdentity(
            "Required ExecutionIdentity needs an incoming custody claim"
        )
    dispatch_identity = _strict_claim_identity(
        td.metadata,
        task_id=td.task_id,
        agent_id=td.agent_id,
        claim_id=incoming_claim,
    )
    if isinstance(td.metadata.get("execution_identity"), dict) and (
        dispatch_identity is None
    ):
        raise MissingExecutionIdentity(
            "Dispatch ExecutionIdentity does not exactly bind task, agent, and claim"
        )
    persisted_identity = _persisted_claim_identity(
        runtime_state_store,
        td,
        incoming_claim,
    )
    task_identity = _task_claim_identity(task_metadata, td, incoming_claim)
    candidates = [
        identity
        for identity in (persisted_identity, task_identity, dispatch_identity)
        if identity is not None
    ]
    if candidates and any(identity != candidates[0] for identity in candidates[1:]):
        raise MissingExecutionIdentity(
            "ExecutionIdentity carriers contradict one exact custody claim"
        )
    claim_identity = persisted_identity or task_identity or dispatch_identity
    if claim_identity is None:
        claim_identity = _rotate_attempt_identity_for_new_claim(
            td,
            task_metadata,
            session_id=session_id,
        )
    if (
        require
        and claim_identity is None
        and any(
            str(task_metadata.get(field) or "").strip()
            for field in ("run_id", "runtime_run_id", "idempotency_key")
        )
    ):
        raise MissingExecutionIdentity(
            "TaskBoard attempt coordinates require a complete ExecutionIdentity"
        )
    if claim_identity is not None:
        # The nested dispatch envelope is canonical for this exact claim. Do
        # not rebuild it under the restarted process's session or allow stale
        # flat aliases to fork its run/idempotency identity.
        td.metadata.update(_identity_metadata(claim_identity))
        if task is not None:
            task.metadata = {
                **task_metadata,
                **_identity_metadata(claim_identity),
            }
        if runtime_state_store is None and require:
            raise MissingExecutionIdentity("RuntimeStateStore is required on this path")
        return claim_identity.require_for_dispatch()
    nested = task_metadata.get("execution_identity")
    merged: dict[str, Any] = {}
    if isinstance(nested, dict):
        merged.update(nested)
    merged.update(task_metadata)
    dispatch_nested = td.metadata.get("execution_identity")
    if isinstance(dispatch_nested, dict):
        merged.update(dispatch_nested)
    merged.update(td.metadata)

    run_id = str(
        merged.get("run_id")
        or merged.get("runtime_run_id")
        or ensure_runtime_run_id(td)
    ).strip()
    trace_id = str(merged.get("trace_id") or "").strip()
    if not trace_id:
        try:
            from dharma_swarm.correlation_context import get_correlation

            trace_id = get_correlation().trace_id
        except Exception:
            trace_id = ""
    if require and not trace_id:
        raise MissingExecutionIdentity("ExecutionIdentity requires trace_id on this path")
    correlation_id = str(merged.get("correlation_id") or trace_id).strip()
    if require and not correlation_id:
        raise MissingExecutionIdentity("ExecutionIdentity requires correlation_id on this path")
    claim_id = incoming_claim if require else str(merged.get("claim_id") or "").strip()
    if require and not claim_id:
        raise MissingExecutionIdentity("ExecutionIdentity requires claim_id on this path")

    identity = ExecutionIdentity.new(
        task_id=td.task_id,
        agent_id=td.agent_id,
        session_id=session_id,
        trace_id=trace_id,
        correlation_id=correlation_id,
        causation_id=str(merged.get("causation_id") or ""),
        parent_run_id=str(merged.get("parent_run_id") or ""),
        run_id=run_id,
        claim_id=claim_id,
        idempotency_key=str(merged.get("idempotency_key") or ""),
        external_a2a_task_id=str(merged.get("external_a2a_task_id") or ""),
        message_id=str(merged.get("message_id") or ""),
        event_id=str(merged.get("event_id") or ""),
        artifact_id=str(merged.get("artifact_id") or ""),
        proposal_id=str(merged.get("proposal_id") or ""),
        metadata={
            "source": "runtime_lifecycle.ensure_execution_identity",
            **dict(merged.get("metadata") or {}),
            **(
                {"attempt_generation": merged["attempt_generation"]}
                if isinstance(merged.get("attempt_generation"), int)
                and not isinstance(merged.get("attempt_generation"), bool)
                and merged["attempt_generation"] >= 0
                else {}
            ),
        },
    )
    td.metadata.update(_identity_metadata(identity))
    if task is not None:
        task.metadata = {**task_metadata, **_identity_metadata(identity)}
    if runtime_state_store is None and require:
        raise MissingExecutionIdentity("RuntimeStateStore is required on this path")
    return identity.require_for_dispatch()


def _identity_metadata(identity: ExecutionIdentity) -> dict[str, Any]:
    return {
        "execution_identity": identity.to_dict(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "runtime_run_id": identity.run_id,
        "run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "idempotency_key": identity.idempotency_key,
        **(
            {"attempt_generation": identity.metadata["attempt_generation"]}
            if "attempt_generation" in identity.metadata
            else {}
        ),
    }
