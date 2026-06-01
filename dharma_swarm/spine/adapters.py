# spine: compatibility-adapter
"""Compatibility adapters for carrying ExecutionIdentity across runtime organs.

This module deliberately does not route, dispatch, persist, or call tools. It
only normalizes identity into and out of existing carrier shapes so each organ
can join the RuntimeStateStore ledger without a local rewrite.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import fields, is_dataclass, replace
from typing import Any

from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

IDENTITY_FLAT_KEYS = (
    "trace_id",
    "correlation_id",
    "causation_id",
    "task_id",
    "run_id",
    "runtime_run_id",
    "claim_id",
    "parent_run_id",
    "agent_id",
    "session_id",
    "external_a2a_task_id",
    "message_id",
    "event_id",
    "artifact_id",
    "proposal_id",
    "idempotency_key",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _read(carrier: Any, key: str) -> Any:
    if isinstance(carrier, Mapping):
        return carrier.get(key)
    return getattr(carrier, key, None)


def _read_nested_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _carrier_metadata(carrier: Any) -> dict[str, Any]:
    if isinstance(carrier, Mapping):
        return _read_nested_mapping(carrier.get("metadata"))
    return _read_nested_mapping(getattr(carrier, "metadata", None))


def _surface_fields(carrier: Any, surface: str) -> dict[str, Any]:
    surface_key = surface.lower().replace("-", "_")
    data: dict[str, Any] = {}

    for key in IDENTITY_FLAT_KEYS:
        value = _read(carrier, key)
        if value not in (None, ""):
            data[key] = value

    carrier_id = _clean(_read(carrier, "id"))
    if carrier_id:
        data.setdefault("task_id", carrier_id)

    if surface_key in {"a2a", "a2a_task", "a2a_ingress"}:
        data.setdefault("external_a2a_task_id", carrier_id)
        data["task_id"] = _clean(_read(carrier, "dharma_task_id")) or data.get("task_id", carrier_id)
        data.setdefault("agent_id", _read(carrier, "to_agent") or _read(carrier, "from_agent"))

    elif surface_key in {"task", "taskboard", "task_board"}:
        data["task_id"] = carrier_id or data.get("task_id", "")
        data.setdefault("agent_id", _read(carrier, "assigned_to") or _read(carrier, "created_by"))

    elif surface_key in {"dispatch", "orchestrator", "task_dispatch"}:
        data["task_id"] = _read(carrier, "task_id") or data.get("task_id", "")
        data["agent_id"] = _read(carrier, "agent_id") or data.get("agent_id", "")

    elif surface_key in {"message", "message_bus", "event", "event_bus"}:
        data.setdefault("message_id", carrier_id or _read(carrier, "message_id"))
        data.setdefault("event_id", _read(carrier, "event_id"))
        data.setdefault("agent_id", _read(carrier, "agent_id") or _read(carrier, "to_agent") or _read(carrier, "from_agent"))
        data.setdefault("task_id", _read(carrier, "task_id") or data.get("message_id") or data.get("event_id"))

    elif surface_key in {"artifact", "artifact_record", "artifact_store"}:
        data["artifact_id"] = _read(carrier, "artifact_id") or carrier_id or data.get("artifact_id", "")
        data.setdefault("task_id", _read(carrier, "task_id") or data.get("artifact_id"))
        data.setdefault("run_id", _read(carrier, "run_id"))
        data.setdefault("trace_id", _read(carrier, "trace_id"))

    elif surface_key in {"ontology", "ontology_action", "action"}:
        params = _read_nested_mapping(_read(carrier, "params"))
        object_type = _clean(_read(carrier, "object_type") or params.get("object_type"))
        object_id = _clean(_read(carrier, "object_id") or params.get("object_id"))
        action_name = _clean(_read(carrier, "action_name") or params.get("action_name"))
        data.setdefault("agent_id", _read(carrier, "executed_by") or params.get("executed_by"))
        data.setdefault("task_id", params.get("task_id") or f"ontology:{object_type}:{object_id}:{action_name}")

    elif surface_key in {"tool", "tool_call", "mcp_tool"}:
        data.setdefault("task_id", _read(carrier, "task_id") or _read(carrier, "tool_call_id") or carrier_id)
        data.setdefault("agent_id", _read(carrier, "agent_id"))

    elif surface_key in {"checkpoint", "graph_checkpoint", "graph"}:
        data.setdefault("task_id", _read(carrier, "task_id") or _read(carrier, "checkpoint_id") or _read(carrier, "cycle_id") or carrier_id)
        data.setdefault("run_id", _read(carrier, "run_id"))

    elif surface_key in {"proposal", "self_mod", "self_mod_proposal", "evolution_proposal"}:
        proposal_id = carrier_id or _read(carrier, "proposal_id") or _read(carrier, "envelope_id")
        data["proposal_id"] = proposal_id
        data.setdefault("task_id", _read(carrier, "task_id") or proposal_id)
        data.setdefault("agent_id", _read(carrier, "agent_id"))

    return data


def identity_metadata(
    identity: ExecutionIdentity,
    *,
    surface: str = "",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return nested plus flat metadata for legacy and spine-aware callers."""
    identity.require_for_dispatch()
    payload = identity.to_dict()
    metadata: dict[str, Any] = {
        "execution_identity": payload,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "causation_id": identity.causation_id,
        "task_id": identity.task_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "parent_run_id": identity.parent_run_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "external_a2a_task_id": identity.external_a2a_task_id,
        "message_id": identity.message_id,
        "event_id": identity.event_id,
        "artifact_id": identity.artifact_id,
        "proposal_id": identity.proposal_id,
        "idempotency_key": identity.idempotency_key,
    }
    if surface:
        metadata["execution_identity_surface"] = surface
    if extra:
        metadata.update(dict(extra))
    return {key: value for key, value in metadata.items() if value not in ("", None)}


def identity_from_carrier(
    carrier: Any,
    *,
    surface: str,
    task_id: str = "",
    agent_id: str = "",
    session_id: str = "",
    require_existing: bool = False,
) -> ExecutionIdentity:
    """Extract or construct ExecutionIdentity from an existing organ carrier.

    ``require_existing=True`` is for selected hard runtime boundaries. It fails
    instead of generating missing identity fields. Compatibility adapters should
    use the default during migration and persist the returned identity before
    irreversible side effects.
    """
    metadata = _carrier_metadata(carrier)
    nested = _read_nested_mapping(metadata.get("execution_identity"))
    top_level = _surface_fields(carrier, surface)
    merged: dict[str, Any] = {}
    merged.update(top_level)
    merged.update(metadata)
    merged.update(nested)

    if task_id:
        merged["task_id"] = task_id
    if agent_id:
        merged["agent_id"] = agent_id
    if session_id:
        merged["session_id"] = session_id

    if require_existing:
        identity = ExecutionIdentity.from_metadata(
            merged,
            task_id=task_id,
            agent_id=agent_id,
            session_id=session_id,
            require=True,
        )
        if identity is None:
            raise MissingExecutionIdentity("ExecutionIdentity is required")
        return identity.require_for_dispatch()

    return ExecutionIdentity.new(
        task_id=_clean(merged.get("task_id")),
        agent_id=_clean(merged.get("agent_id")),
        session_id=_clean(merged.get("session_id")),
        trace_id=_clean(merged.get("trace_id")),
        correlation_id=_clean(merged.get("correlation_id")),
        causation_id=_clean(merged.get("causation_id")),
        parent_run_id=_clean(merged.get("parent_run_id")),
        run_id=_clean(merged.get("run_id") or merged.get("runtime_run_id")),
        claim_id=_clean(merged.get("claim_id")),
        idempotency_key=_clean(merged.get("idempotency_key")),
        external_a2a_task_id=_clean(merged.get("external_a2a_task_id")),
        message_id=_clean(merged.get("message_id")),
        event_id=_clean(merged.get("event_id")),
        artifact_id=_clean(merged.get("artifact_id")),
        proposal_id=_clean(merged.get("proposal_id")),
        metadata={
            "surface": surface,
            **_read_nested_mapping(merged.get("metadata")),
        },
    ).require_for_dispatch()


def attach_execution_identity(
    carrier: Any,
    identity: ExecutionIdentity,
    *,
    surface: str,
    mutate: bool = True,
) -> Any:
    """Attach identity metadata to dicts, dataclasses, and model-like objects.

    Frozen dataclasses are returned as copies. Mutable carriers are updated
    in-place by default to match existing Task/A2A/MessageBus idioms.
    """
    identity.require_for_dispatch()
    current_meta = _carrier_metadata(carrier)
    metadata = {
        **current_meta,
        **identity_metadata(identity, surface=surface),
    }

    if isinstance(carrier, MutableMapping):
        target = carrier if mutate else dict(carrier)
        target["metadata"] = metadata
        for key, value in identity_metadata(identity, surface=surface).items():
            if key != "execution_identity":
                target.setdefault(key, value)
        return target

    if is_dataclass(carrier) and not isinstance(carrier, type):
        dataclass_fields = {field.name for field in fields(carrier)}
        updates: dict[str, Any] = {}
        if "metadata" in dataclass_fields:
            updates["metadata"] = metadata
        for key, value in identity_metadata(identity, surface=surface).items():
            if key in dataclass_fields and key != "metadata":
                current = getattr(carrier, key, "")
                if not current:
                    updates[key] = value
        if updates:
            return replace(carrier, **updates)
        return carrier

    if hasattr(carrier, "metadata"):
        current = getattr(carrier, "metadata", None)
        if current is None:
            setattr(carrier, "metadata", metadata)
        else:
            setattr(carrier, "metadata", metadata)
    for key, value in identity_metadata(identity, surface=surface).items():
        if key == "execution_identity":
            continue
        if hasattr(carrier, key) and not getattr(carrier, key):
            setattr(carrier, key, value)
    return carrier


def adapt_execution_identity(
    carrier: Any,
    *,
    surface: str,
    task_id: str = "",
    agent_id: str = "",
    session_id: str = "",
    require_existing: bool = False,
    mutate: bool = True,
) -> tuple[ExecutionIdentity, Any]:
    """Extract or create identity and attach it back to the carrier."""
    identity = identity_from_carrier(
        carrier,
        surface=surface,
        task_id=task_id,
        agent_id=agent_id,
        session_id=session_id,
        require_existing=require_existing,
    )
    return identity, attach_execution_identity(
        carrier,
        identity,
        surface=surface,
        mutate=mutate,
    )


def runtime_receipt_kwargs(
    identity: ExecutionIdentity,
    *,
    receipt_type: str,
    status: str,
    side_effect_key: str = "",
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return kwargs compatible with ``RuntimeReceipt`` without importing it."""
    identity.require_for_dispatch()
    return {
        "receipt_id": f"rr_{identity.run_id}_{receipt_type}_{status}",
        "receipt_type": receipt_type,
        "status": status,
        "run_id": identity.run_id,
        "task_id": identity.task_id,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "causation_id": identity.causation_id,
        "parent_run_id": identity.parent_run_id,
        "agent_id": identity.agent_id,
        "idempotency_key": identity.idempotency_key,
        "side_effect_key": side_effect_key,
        "payload": dict(payload or {}),
    }
