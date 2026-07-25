# spine: canonical-store
"""Canonical execution identity for the Runtime Truth Spine.

This module is intentionally dependency-light so runtime producers can import
it without creating circular ownership between the spine, orchestration, and
durable store layers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


class MissingExecutionIdentity(ValueError):
    """Raised when a runtime path requires identity but cannot construct it."""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def _clean(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    """Join key set for one durable unit of work.

    `trace_id` is the local dispatch identity. `correlation_id` is the
    cross-layer alias used by A2A/operator-core receipts. They may be equal,
    but both fields are explicit so adapters cannot silently rename identity.
    """

    trace_id: str
    correlation_id: str
    task_id: str
    run_id: str
    claim_id: str
    idempotency_key: str
    causation_id: str = ""
    parent_run_id: str = ""
    agent_id: str = ""
    session_id: str = ""
    external_a2a_task_id: str = ""
    message_id: str = ""
    event_id: str = ""
    artifact_id: str = ""
    proposal_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        task_id: str,
        agent_id: str = "",
        session_id: str = "",
        trace_id: str = "",
        correlation_id: str = "",
        causation_id: str = "",
        parent_run_id: str = "",
        run_id: str = "",
        claim_id: str = "",
        idempotency_key: str = "",
        external_a2a_task_id: str = "",
        message_id: str = "",
        event_id: str = "",
        artifact_id: str = "",
        proposal_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "ExecutionIdentity":
        clean_task_id = _clean(task_id)
        if not clean_task_id:
            raise MissingExecutionIdentity("ExecutionIdentity requires task_id")
        clean_trace = _clean(trace_id) or _new_id("trace")
        clean_correlation = _clean(correlation_id) or clean_trace
        clean_run = _clean(run_id) or _new_id("run")
        clean_claim = _clean(claim_id) or _new_id("claim")
        clean_idem = _clean(idempotency_key) or f"idem_{clean_run}"
        return cls(
            trace_id=clean_trace,
            correlation_id=clean_correlation,
            task_id=clean_task_id,
            run_id=clean_run,
            claim_id=clean_claim,
            idempotency_key=clean_idem,
            causation_id=_clean(causation_id),
            parent_run_id=_clean(parent_run_id),
            agent_id=_clean(agent_id),
            session_id=_clean(session_id),
            external_a2a_task_id=_clean(external_a2a_task_id),
            message_id=_clean(message_id),
            event_id=_clean(event_id),
            artifact_id=_clean(artifact_id),
            proposal_id=_clean(proposal_id),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def from_metadata(
        cls,
        metadata: dict[str, Any] | None,
        *,
        task_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        require: bool = False,
    ) -> "ExecutionIdentity | None":
        meta = dict(metadata or {})
        nested = meta.get("execution_identity")
        raw = dict(nested) if isinstance(nested, dict) else meta
        resolved_task_id = _clean(raw.get("task_id")) or _clean(task_id)
        if require and not resolved_task_id:
            raise MissingExecutionIdentity("missing task_id for required ExecutionIdentity")
        if not resolved_task_id:
            return None
        if require:
            required = ("trace_id", "correlation_id", "run_id", "claim_id", "idempotency_key")
            missing = [name for name in required if not _clean(raw.get(name))]
            if missing:
                raise MissingExecutionIdentity(
                    "missing required ExecutionIdentity field(s): " + ", ".join(missing)
                )
        return cls.new(
            task_id=resolved_task_id,
            agent_id=_clean(raw.get("agent_id")) or _clean(agent_id),
            session_id=_clean(raw.get("session_id")) or _clean(session_id),
            trace_id=_clean(raw.get("trace_id")),
            correlation_id=_clean(raw.get("correlation_id")),
            causation_id=_clean(raw.get("causation_id")),
            parent_run_id=_clean(raw.get("parent_run_id")),
            run_id=_clean(raw.get("run_id")),
            claim_id=_clean(raw.get("claim_id")),
            idempotency_key=_clean(raw.get("idempotency_key")),
            external_a2a_task_id=_clean(raw.get("external_a2a_task_id")),
            message_id=_clean(raw.get("message_id")),
            event_id=_clean(raw.get("event_id")),
            artifact_id=_clean(raw.get("artifact_id")),
            proposal_id=_clean(raw.get("proposal_id")),
            metadata=dict(raw.get("metadata") or {}),
        )

    def require_for_dispatch(self) -> "ExecutionIdentity":
        missing = [
            name
            for name in ("trace_id", "correlation_id", "task_id", "run_id", "claim_id", "idempotency_key")
            if not _clean(getattr(self, name))
        ]
        if missing:
            raise MissingExecutionIdentity(
                "ExecutionIdentity is incomplete for dispatch: " + ", ".join(missing)
            )
        return self

    def with_updates(self, **updates: Any) -> "ExecutionIdentity":
        payload = self.to_dict()
        nested_metadata = payload.pop("metadata", {})
        payload.update({key: value for key, value in updates.items() if key != "metadata"})
        payload["metadata"] = {
            **nested_metadata,
            **dict(updates.get("metadata") or {}),
        }
        return ExecutionIdentity(**payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_metadata(self) -> dict[str, Any]:
        return {"execution_identity": self.to_dict()}


def require_execution_identity(
    metadata: dict[str, Any] | None,
    *,
    task_id: str = "",
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


_PROCESS_BOOT_ID = ""


def process_boot_id() -> str:
    """Mint-once boot identity for this OS process.

    ``run_id`` is minted per invocation (``_new_id`` above), so receipts on
    either side of a process restart are indistinguishable by it; P4 restart
    survival requires producer and consumer receipts to carry different boot
    identities across a deliberate restart
    (docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md, invariant P4). This is the
    single minting site — carriers import it and never mint their own.
    """
    global _PROCESS_BOOT_ID
    if not _PROCESS_BOOT_ID:
        _PROCESS_BOOT_ID = f"boot_{uuid4().hex}"
    return _PROCESS_BOOT_ID
