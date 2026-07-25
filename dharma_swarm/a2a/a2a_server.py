"""A2A Server -- accepts task delegations from other agents.

Receives A2A task requests and dispatches them to the dharma_swarm
task board and orchestrator. Manages the A2A task lifecycle per
A2A 1.0 spec (Linux Foundation):

    submitted -> working -> {completed, failed, canceled,
                             rejected, input-required, auth-required}

For local agents: direct function calls (no HTTP).
For remote agents (AGNI/RUSHABDEV): HTTP endpoint via NodeGateway.

The server maintains an in-memory task store with A2A-specific metadata
layered on top of dharma_swarm's Task model. This keeps the protocol
boundary clean while reusing existing infrastructure.

A2A 1.0 spec conformance:
    - 8 task states (SUBMITTED through AUTH_REQUIRED)
    - contextId for grouping related tasks
    - Part as strict one-of (text|raw|url|data) with mediaType/filename
    - Artifact separate from Message (outputs vs conversation)
    - extensions[] with required flag for dharma-specific layers
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

logger = logging.getLogger(__name__)

_STATE_DIR = dharma_state_dir("DHARMA_HOME")
_DEFAULT_TASK_LOG = _STATE_DIR / "a2a" / "task_log.jsonl"


# ---------------------------------------------------------------------------
# A2A task lifecycle
# ---------------------------------------------------------------------------


class A2ATaskStatus(str, Enum):
    """Task lifecycle states per A2A 1.0 spec (all 8 states)."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth-required"

    @classmethod
    def terminal_states(cls) -> frozenset[A2ATaskStatus]:
        return frozenset({cls.COMPLETED, cls.FAILED, cls.CANCELLED, cls.REJECTED})


class A2ATransitionError(RuntimeError):
    """Raised on an illegal A2A task-lifecycle transition.

    In particular, any attempt to move a terminal task (completed, failed,
    cancelled, rejected) to any other state -- the resurrection/re-billing
    hole this guard closes.
    """


# Explicit lifecycle transition table (mirrors task_board.py:_TRANSITIONS).
# The load-bearing invariant is TERMINAL ABSORPTION: every terminal state maps
# to the empty frozenset, so no terminal task has an outgoing edge. Moves among
# non-terminal states stay permissive to preserve existing A2A 1.0 behaviour.
# Registered as INV-A2A-TERMINAL-ABSORBING.
_A2A_TRANSITIONS: dict[A2ATaskStatus, frozenset[A2ATaskStatus]] = {
    A2ATaskStatus.SUBMITTED: frozenset({
        A2ATaskStatus.WORKING,
        A2ATaskStatus.INPUT_REQUIRED,
        A2ATaskStatus.AUTH_REQUIRED,
        A2ATaskStatus.COMPLETED,
        A2ATaskStatus.FAILED,
        A2ATaskStatus.CANCELLED,
        A2ATaskStatus.REJECTED,
    }),
    A2ATaskStatus.WORKING: frozenset({
        A2ATaskStatus.INPUT_REQUIRED,
        A2ATaskStatus.AUTH_REQUIRED,
        A2ATaskStatus.COMPLETED,
        A2ATaskStatus.FAILED,
        A2ATaskStatus.CANCELLED,
        A2ATaskStatus.REJECTED,
    }),
    A2ATaskStatus.INPUT_REQUIRED: frozenset({
        A2ATaskStatus.WORKING,
        A2ATaskStatus.AUTH_REQUIRED,
        A2ATaskStatus.COMPLETED,
        A2ATaskStatus.FAILED,
        A2ATaskStatus.CANCELLED,
        A2ATaskStatus.REJECTED,
    }),
    A2ATaskStatus.AUTH_REQUIRED: frozenset({
        A2ATaskStatus.WORKING,
        A2ATaskStatus.INPUT_REQUIRED,
        A2ATaskStatus.COMPLETED,
        A2ATaskStatus.FAILED,
        A2ATaskStatus.CANCELLED,
        A2ATaskStatus.REJECTED,
    }),
    A2ATaskStatus.COMPLETED: frozenset(),
    A2ATaskStatus.FAILED: frozenset(),
    A2ATaskStatus.CANCELLED: frozenset(),
    A2ATaskStatus.REJECTED: frozenset(),
}


def a2a_transition_allowed(
    current: A2ATaskStatus, new: A2ATaskStatus
) -> bool:
    """Return True if current -> new is a legal A2A lifecycle transition.

    A same-state move is treated as an idempotent no-op (allowed). Any move
    out of a terminal state is rejected regardless of the destination.
    """
    if new == current:
        return True
    return new in _A2A_TRANSITIONS.get(current, frozenset())


class A2APartType(str, Enum):
    """Part types per A2A 1.0 spec — strict one-of."""

    TEXT = "text"
    RAW = "raw"
    URL = "url"
    DATA = "data"
    FILE = "file"  # backward compat alias for RAW


@dataclass
class A2APart:
    """A single part of an A2A message — strict one-of per spec.

    A2A 1.0 requires exactly one content field set (text, raw, url, or data)
    plus optional mediaType and filename.  Validation in ``__post_init__``
    rejects zero-content and multi-content construction (except for the
    legacy ``FILE`` type which is exempt for backward compatibility).

    Attributes:
        type: One of text, raw, url, data (or file for backward compat).
        content: The actual content string.
        media_type: MIME type (e.g. "application/json", "image/png").
        filename: Original filename when transferring files.
        metadata: Extra context (preserved for backward compat).
    """

    type: A2APartType = A2APartType.TEXT
    content: str = ""
    media_type: str = ""
    filename: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    _skip_validation: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if self._skip_validation:
            return
        # Legacy FILE type is exempt from strict one-of validation
        if self.type == A2APartType.FILE:
            return
        if not self.content:
            raise ValueError(
                f"A2APart(type={self.type.value!r}) requires non-empty content. "
                "Exactly one content field must be set per A2A 1.0 spec."
            )

    @classmethod
    def text(cls, content: str) -> A2APart:
        """Construct a text part."""
        return cls(type=A2APartType.TEXT, content=content)

    @classmethod
    def raw(cls, content: str, media_type: str = "application/octet-stream",
            filename: str = "") -> A2APart:
        """Construct a raw (binary) part."""
        return cls(type=A2APartType.RAW, content=content,
                   media_type=media_type, filename=filename)

    @classmethod
    def url(cls, content: str, media_type: str = "",
            filename: str = "") -> A2APart:
        """Construct a URL part."""
        return cls(type=A2APartType.URL, content=content,
                   media_type=media_type, filename=filename)

    @classmethod
    def data(cls, content: str, media_type: str = "application/json") -> A2APart:
        """Construct a structured data part."""
        return cls(type=A2APartType.DATA, content=content, media_type=media_type)


@dataclass
class A2AExtension:
    """A2A 1.0 extension declaration.

    Allows dharma-specific semantics (telos gates, witness packets,
    gnani lodestone) to layer on top of A2A without breaking interop.
    """

    uri: str = ""
    required: bool = False
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class A2AMessage:
    """A message in the A2A protocol.

    Messages contain one or more parts and travel between agents.
    """

    role: str = "user"  # "user" (requester) or "agent" (responder)
    parts: list[A2APart] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def text(cls, content: str, role: str = "user") -> A2AMessage:
        """Convenience: create a single-text-part message."""
        return cls(role=role, parts=[A2APart(type=A2APartType.TEXT, content=content)])


@dataclass
class A2AArtifact:
    """An output artifact from a task — distinct from conversation Messages.

    A2A 1.0 separates outputs (artifacts) from conversation (history).
    Artifacts are the deliverables; messages are the dialogue.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parts: list[A2APart] = field(default_factory=list)
    name: str = ""
    description: str = ""
    extensions: list[A2AExtension] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class A2ATask:
    """An A2A task -- the core unit of work in the protocol.

    A2A 1.0 spec-conformant with contextId, artifacts/history split,
    extensions, and all 8 lifecycle states.

    Attributes:
        id: Unique task identifier.
        context_id: Groups related tasks (server-generated, opaque to clients).
        from_agent: Name of the requesting agent.
        to_agent: Name of the target agent (or empty for capability-based routing).
        status: Current lifecycle state (8 states per A2A 1.0).
        history: Conversation messages (request + responses).
        artifacts: Output deliverables (distinct from conversation).
        capability: The capability being requested (for discovery-based routing).
        dharma_task_id: ID of the corresponding dharma_swarm Task (if created).
        created_at: ISO-8601 creation timestamp.
        updated_at: ISO-8601 last update timestamp.
        result: Final result text (convenience — also in artifacts).
        error: Error message (populated on failure/rejection).
        extensions: A2A 1.0 extension declarations.
        metadata: Arbitrary extra data.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    context_id: str = ""
    from_agent: str = ""
    to_agent: str = ""
    status: A2ATaskStatus = A2ATaskStatus.SUBMITTED
    history: list[A2AMessage] = field(default_factory=list)
    messages: list[A2AMessage] = field(default_factory=list)
    artifacts: list[A2AArtifact] = field(default_factory=list)
    capability: str = ""
    dharma_task_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: str = ""
    error: str = ""
    trace_id: str = ""
    extensions: list[A2AExtension] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Merge messages into history for backward compat
        if self.messages and not self.history:
            self.history = self.messages
        self.messages = self.history

    def is_terminal(self) -> bool:
        return self.status in A2ATaskStatus.terminal_states()


# Type alias for task handler callbacks
TaskHandler = Callable[[A2ATask], A2ATask]


# ---------------------------------------------------------------------------
# A2A Server
# ---------------------------------------------------------------------------


class A2AServer:
    """Accepts A2A task delegations and dispatches to dharma_swarm.

    Local-first: tasks are dispatched via direct function calls.
    The server maintains its own task store for A2A lifecycle tracking,
    separate from (but linked to) the dharma_swarm task board.

    Usage::

        server = A2AServer()
        server.register_handler("code_review", my_review_handler)

        task = server.submit(A2ATask(
            from_agent="orchestrator",
            to_agent="reviewer",
            capability="code_review",
            messages=[A2AMessage.text("Review this PR")],
        ))

        # Later: check status
        status = server.get_status(task.id)

    Attributes:
        tasks: In-memory store of A2A tasks keyed by task ID.
    """

    def __init__(
        self,
        task_log_path: Path | None = None,
        persist: bool = True,
        runtime_state: RuntimeStateStore | None = None,
        require_execution_identity: bool = False,
    ) -> None:
        self._tasks: dict[str, A2ATask] = {}
        self._handlers: dict[str, TaskHandler] = {}
        self._default_handler: TaskHandler | None = None
        self._persist = persist
        self._task_log_path = task_log_path or _DEFAULT_TASK_LOG
        self._runtime_state = runtime_state
        self._require_execution_identity = require_execution_identity

    # -- handler registration ------------------------------------------------

    def register_handler(
        self,
        capability: str,
        handler: TaskHandler,
    ) -> None:
        """Register a handler for a specific capability.

        When a task targeting this capability is submitted, the handler
        is called to process it.

        Args:
            capability: Capability name (e.g., "code_review").
            handler: Callable that takes A2ATask and returns updated A2ATask.
        """
        self._handlers[capability] = handler
        logger.info("Registered A2A handler for capability: %s", capability)

    def set_default_handler(self, handler: TaskHandler) -> None:
        """Set a fallback handler for tasks with no matching capability handler."""
        self._default_handler = handler

    # -- task lifecycle ------------------------------------------------------

    def _set_status(self, task: A2ATask, new: A2ATaskStatus) -> A2ATask:
        """Apply a guarded lifecycle transition on task.

        Validates current -> new against _A2A_TRANSITIONS. Raises
        A2ATransitionError on any illegal move -- in particular any attempt to
        leave a terminal state (the resurrection/re-billing hole). Bumps
        updated_at when the status actually changes.
        """
        current = task.status
        if not a2a_transition_allowed(current, new):
            raise A2ATransitionError(
                f"Illegal A2A transition: {current.value} -> {new.value} "
                f"(task {task.id})"
            )
        if new != current:
            task.status = new
            task.updated_at = datetime.now(timezone.utc).isoformat()
        return task

    def submit(self, task: A2ATask) -> A2ATask:
        """Submit a new task for processing.

        Auto-generates context_id if not set (A2A 1.0 spec: server-generated).

        Args:
            task: The A2ATask to submit.

        Returns:
            The task with updated status.

        Raises:
            A2ATransitionError: if the task is already in a terminal state
                (resurrecting a completed/failed/cancelled/rejected task).
        """
        if task.is_terminal():
            raise A2ATransitionError(
                f"Cannot submit terminal task {task.id}: status "
                f"{task.status.value} is absorbing"
            )
        self._set_status(task, A2ATaskStatus.SUBMITTED)

        if not task.trace_id:
            task.trace_id = _inherit_trace_id()
        if not task.context_id:
            task.context_id = uuid.uuid4().hex[:12]

        identity = self._ensure_execution_identity(task)
        side_effect_key = f"a2a_handler:{task.id}:{task.capability or 'default'}"
        effective_side_effect_key = side_effect_key
        if self._runtime_state is not None:
            self._runtime_state.record_execution_identity_sync(
                identity,
                source="a2a_server.submit",
                metadata={
                    "ingress_surface": "a2a_local",
                    "context_id": task.context_id,
                    "capability": task.capability,
                    "status": task.status.value,
                },
            )
            handler_metadata = {"source": "a2a_server.submit"}
            if not self._runtime_state.try_begin_idempotent_side_effect_sync(
                identity,
                side_effect_key,
                metadata=handler_metadata,
            ):
                existing_record = self._runtime_state.get_idempotency_record_sync(
                    identity.idempotency_key,
                    side_effect_key,
                )
                existing_status = str(existing_record.status if existing_record is not None else "")
                if existing_status in {"failed", "stale"}:
                    retry_key = f"{side_effect_key}:retry:{uuid.uuid4().hex[:12]}"
                    retry_metadata = {
                        **handler_metadata,
                        "retry_of_side_effect_key": side_effect_key,
                        "retry_of_status": existing_status,
                        "retry_of_result_receipt_id": (
                            existing_record.result_receipt_id if existing_record is not None else ""
                        ),
                    }
                    if self._runtime_state.try_begin_idempotent_side_effect_sync(
                        identity,
                        retry_key,
                        metadata=retry_metadata,
                    ):
                        effective_side_effect_key = retry_key
                        task.metadata["idempotency_status"] = "retry"
                    else:
                        task.metadata["idempotency_status"] = "retry_blocked"
                        self._tasks[task.id] = task
                        return task
                else:
                    existing = self._tasks.get(task.id)
                    if existing is not None:
                        return existing
                    task.metadata["idempotency_status"] = "duplicate"
                    self._tasks[task.id] = task
                    return task

        self._tasks[task.id] = task

        logger.info(
            "A2A task submitted: %s ctx=%s trace=%s (from=%s, to=%s, cap=%s)",
            task.id, task.context_id, task.trace_id,
            task.from_agent, task.to_agent, task.capability,
        )

        # Dispatch to handler
        result = self._dispatch(task)
        if self._runtime_state is not None:
            receipt_id = f"rr_{identity.run_id}_a2a_{result.status.value}"
            self._runtime_state.record_runtime_receipt_sync(
                RuntimeReceipt(
                    receipt_id=receipt_id,
                    receipt_type="a2a_task",
                    status=result.status.value,
                    run_id=identity.run_id,
                    task_id=identity.task_id,
                    trace_id=identity.trace_id,
                    correlation_id=identity.correlation_id,
                    causation_id=identity.causation_id,
                    parent_run_id=identity.parent_run_id,
                    agent_id=identity.agent_id,
                    idempotency_key=identity.idempotency_key,
                    side_effect_key=effective_side_effect_key,
                    payload={
                        "external_a2a_task_id": result.id,
                        "context_id": result.context_id,
                        "capability": result.capability,
                    },
                )
            )
            self._runtime_state.complete_idempotent_side_effect_sync(
                identity,
                effective_side_effect_key,
                status=(
                    "failed"
                    if result.status
                    in {
                        A2ATaskStatus.FAILED,
                        A2ATaskStatus.REJECTED,
                        A2ATaskStatus.CANCELLED,
                    }
                    else "completed"
                ),
                result_receipt_id=receipt_id,
                metadata={"status": result.status.value},
            )
        self._append_task_log(result)
        return result

    def _ensure_execution_identity(self, task: A2ATask) -> ExecutionIdentity:
        meta = dict(task.metadata or {})
        nested = meta.get("execution_identity")
        explicit = dict(nested) if isinstance(nested, dict) else {}
        trace_id = task.trace_id or str(meta.get("trace_id") or explicit.get("trace_id") or "")
        if self._require_execution_identity and not trace_id:
            raise MissingExecutionIdentity("A2A task requires trace_id")
        identity = ExecutionIdentity.new(
            task_id=str(explicit.get("task_id") or meta.get("task_id") or task.dharma_task_id or task.id),
            agent_id=str(explicit.get("agent_id") or meta.get("agent_id") or task.to_agent or ""),
            session_id=str(meta.get("session_id") or explicit.get("session_id") or ""),
            trace_id=trace_id,
            correlation_id=str(meta.get("correlation_id") or explicit.get("correlation_id") or trace_id),
            causation_id=str(meta.get("causation_id") or explicit.get("causation_id") or ""),
            parent_run_id=str(meta.get("parent_run_id") or explicit.get("parent_run_id") or ""),
            run_id=str(meta.get("run_id") or meta.get("runtime_run_id") or explicit.get("run_id") or ""),
            claim_id=str(meta.get("claim_id") or explicit.get("claim_id") or ""),
            idempotency_key=str(meta.get("idempotency_key") or explicit.get("idempotency_key") or ""),
            external_a2a_task_id=task.id,
            message_id=str(meta.get("message_id") or explicit.get("message_id") or ""),
            event_id=str(meta.get("event_id") or explicit.get("event_id") or ""),
            artifact_id=str(meta.get("artifact_id") or explicit.get("artifact_id") or ""),
            proposal_id=str(meta.get("proposal_id") or explicit.get("proposal_id") or ""),
            metadata={"context_id": task.context_id, "capability": task.capability},
        )
        task.trace_id = identity.trace_id
        task.dharma_task_id = task.dharma_task_id or identity.task_id
        task.metadata.update(
            {
                "execution_identity": identity.to_dict(),
                "trace_id": identity.trace_id,
                "correlation_id": identity.correlation_id,
                "run_id": identity.run_id,
                "runtime_run_id": identity.run_id,
                "claim_id": identity.claim_id,
                "idempotency_key": identity.idempotency_key,
                "external_a2a_task_id": identity.external_a2a_task_id,
            }
        )
        return identity.require_for_dispatch()

    def _dispatch(self, task: A2ATask) -> A2ATask:
        """Route task to appropriate handler and execute."""
        handler = self._handlers.get(task.capability)
        if handler is None:
            handler = self._default_handler

        if handler is None:
            self._set_status(task, A2ATaskStatus.FAILED)
            task.error = f"No handler registered for capability: {task.capability!r}"
            logger.warning("A2A task %s failed: no handler for %s", task.id, task.capability)
            return task

        self._set_status(task, A2ATaskStatus.WORKING)

        try:
            task = handler(task)
            if task.status == A2ATaskStatus.WORKING:
                # Handler didn't set final status -- mark completed
                self._set_status(task, A2ATaskStatus.COMPLETED)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("A2A task %s completed (status=%s)", task.id, task.status.value)
        except Exception as exc:
            # Preserve terminal absorption: if the handler already drove the
            # task to a terminal state before raising, keep it -- only record
            # the error. A non-terminal task fails as usual.
            if not task.is_terminal():
                self._set_status(task, A2ATaskStatus.FAILED)
            task.error = str(exc)
            task.updated_at = datetime.now(timezone.utc).isoformat()
            logger.error("A2A task %s failed: %s", task.id, exc)

        return task

    def get_task(self, task_id: str) -> A2ATask | None:
        """Retrieve a task by ID."""
        return self._tasks.get(task_id)

    def get_status(self, task_id: str) -> A2ATaskStatus | None:
        """Get the status of a task. Returns None if task not found."""
        task = self._tasks.get(task_id)
        return task.status if task else None

    def cancel(self, task_id: str) -> bool:
        """Cancel a task. Returns True if successful.

        Only non-terminal tasks can be cancelled.
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.is_terminal():
            return False
        self._set_status(task, A2ATaskStatus.CANCELLED)
        safe_task_id = str(task_id).replace("\n", " ").replace("\r", " ")[:128]
        logger.info("A2A task %s cancelled", safe_task_id)
        return True

    def reject(self, task_id: str, reason: str = "") -> bool:
        """Reject a task (A2A 1.0). Returns True if successful."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.is_terminal():
            return False
        safe_reason = str(reason).replace("\n", " ").replace("\r", " ")[:200]
        self._set_status(task, A2ATaskStatus.REJECTED)
        task.error = safe_reason
        safe_task_id = str(task_id).replace("\n", " ").replace("\r", " ")[:128]
        logger.info("A2A task %s rejected: %s", safe_task_id, safe_reason)
        return True

    def require_auth(self, task_id: str, reason: str = "") -> bool:
        """Set a task to AUTH_REQUIRED (A2A 1.0). Returns True if successful."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.is_terminal():
            return False
        safe_reason = str(reason).replace("\n", " ").replace("\r", " ")[:200]
        self._set_status(task, A2ATaskStatus.AUTH_REQUIRED)
        task.error = safe_reason
        logger.info("A2A task %s requires auth: %s", task_id, safe_reason)
        return True

    def list_tasks(
        self,
        status: A2ATaskStatus | None = None,
        from_agent: str | None = None,
        to_agent: str | None = None,
        context_id: str | None = None,
    ) -> list[A2ATask]:
        """List tasks with optional filters.

        Args:
            status: Filter by task status.
            from_agent: Filter by requesting agent.
            to_agent: Filter by target agent.
            context_id: Filter by context group (A2A 1.0).

        Returns:
            List of matching tasks.
        """
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if from_agent is not None:
            tasks = [t for t in tasks if t.from_agent == from_agent]
        if to_agent is not None:
            tasks = [t for t in tasks if t.to_agent == to_agent]
        if context_id is not None:
            tasks = [t for t in tasks if t.context_id == context_id]
        return tasks

    def task_count(self) -> int:
        """Total number of tracked tasks."""
        return len(self._tasks)

    def summary(self) -> dict[str, int]:
        """Return counts by status."""
        counts: dict[str, int] = {}
        for task in self._tasks.values():
            key = task.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    # -- persistence (JSONL append log) --------------------------------------

    def _append_task_log(self, task: A2ATask) -> None:
        """Append a task snapshot to the JSONL audit log."""
        if not self._persist:
            return
        try:
            self._task_log_path.parent.mkdir(parents=True, exist_ok=True)
            record = _task_to_log_record(task)
            with self._task_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")
        except Exception as exc:
            logger.warning("Failed to persist A2A task log entry: %s", exc)

    def load_task_log(self) -> list[dict[str, Any]]:
        """Read back the full task log (for auditing / replay)."""
        if not self._task_log_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in self._task_log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _inherit_trace_id() -> str:
    """Pull trace_id from CorrelationContext if set, else generate a new one."""
    try:
        from dharma_swarm.correlation_context import get_correlation
        corr = get_correlation()
        if corr.trace_id:
            return corr.trace_id
    except Exception:
        pass
    return f"trc_{uuid.uuid4().hex[:16]}"


def _task_to_log_record(task: A2ATask) -> dict[str, Any]:
    """Serialize an A2ATask to a flat dict for JSONL logging."""
    return {
        "id": task.id,
        "from_agent": task.from_agent,
        "to_agent": task.to_agent,
        "status": task.status.value,
        "capability": task.capability,
        "trace_id": task.trace_id,
        "dharma_task_id": task.dharma_task_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "result": task.result,
        "error": task.error,
        "message_count": len(task.messages),
        "metadata": task.metadata,
    }
