"""Execution-identity + idempotency helper functions.

Mechanical split from the former dharma_swarm/runtime_state.py (item 6a).
Zero logic change: bodies are verbatim.
"""

from __future__ import annotations

from typing import Any

from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

from .models import _EXECUTION_IDENTITY_CONFLICT_FIELDS, IdempotencyRecord


def _operation_hash(metadata: dict[str, Any] | None) -> str:
    return str((metadata or {}).get("operation_hash") or "")


def _merge_idempotency_metadata(
    existing: IdempotencyRecord,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(existing.metadata)
    merged.update(metadata or {})
    return merged


def _execution_identity_conflicts(
    existing: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
) -> dict[str, dict[str, str]]:
    if existing is None:
        return {}
    conflicts: dict[str, dict[str, str]] = {}
    for field_name in _EXECUTION_IDENTITY_CONFLICT_FIELDS:
        existing_value = str(getattr(existing, field_name, "") or "")
        incoming_value = str(getattr(incoming, field_name, "") or "")
        if existing_value and incoming_value and existing_value != incoming_value:
            conflicts[field_name] = {
                "existing": existing_value,
                "incoming": incoming_value,
            }
    return conflicts


def _raise_on_execution_identity_conflict(
    existing: ExecutionIdentity | None,
    incoming: ExecutionIdentity,
) -> None:
    conflicts = _execution_identity_conflicts(existing, incoming)
    if not conflicts:
        return
    details = ", ".join(
        f"{field} existing={values['existing']!r} incoming={values['incoming']!r}"
        for field, values in sorted(conflicts.items())
    )
    raise ValueError(
        f"execution identity conflict for run_id {incoming.run_id!r}: {details}"
    )


def _identity_from_metadata(metadata: dict[str, Any] | None) -> ExecutionIdentity | None:
    return ExecutionIdentity.from_metadata(metadata, require=False)


def _required_identity_from_metadata(
    metadata: dict[str, Any] | None,
    *,
    task_id: str,
    agent_id: str = "",
    session_id: str = "",
) -> ExecutionIdentity:
    identity = ExecutionIdentity.from_metadata(
        metadata,
        task_id=task_id,
        agent_id=agent_id,
        session_id=session_id,
        require=True,
    )
    if identity is None:
        raise MissingExecutionIdentity("ExecutionIdentity is required")
    return identity.require_for_dispatch()


def _legacy_no_identity_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return {
        **dict(metadata or {}),
        "legacy_no_identity_allowed": True,
        "runtime_spine_status": "legacy_no_identity",
    }


def _metadata_with_identity(
    metadata: dict[str, Any] | None,
    identity: ExecutionIdentity,
) -> dict[str, Any]:
    return {
        **dict(metadata or {}),
        **identity.to_metadata(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
    }


def _require_identity_match(
    identity: ExecutionIdentity,
    *,
    surface: str,
    task_id: str = "",
    claim_id: str = "",
    run_id: str = "",
    agent_id: str = "",
    session_id: str = "",
) -> None:
    expected = {
        "task_id": task_id,
        "claim_id": claim_id,
        "run_id": run_id,
        "agent_id": agent_id,
        "session_id": session_id,
    }
    mismatches = [
        f"{name}={actual!r} expected {wanted!r}"
        for name, wanted in expected.items()
        if wanted and (actual := str(getattr(identity, name, "") or "")) and actual != wanted
    ]
    if mismatches:
        raise MissingExecutionIdentity(
            f"ExecutionIdentity does not match {surface}: " + ", ".join(mismatches)
        )


def _trace_from_metadata(metadata: dict[str, Any] | None) -> str:
    identity = _identity_from_metadata(metadata)
    if identity is not None and identity.trace_id:
        return identity.trace_id
    meta = dict(metadata or {})
    return str(meta.get("trace_id", "") or "")
