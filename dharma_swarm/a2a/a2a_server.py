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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.daemon_config import dharma_state_dir

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
    ) -> None:
        self._tasks: dict[str, A2ATask] = {}
        self._handlers: dict[str, TaskHandler] = {}
        self._default_handler: TaskHandler | None = None
        self._persist = persist
        self._task_log_path = task_log_path or _DEFAULT_TASK_LOG

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

    def submit(self, task: A2ATask) -> A2ATask:
        """Submit a new task for processing.

        Auto-generates context_id if not set (A2A 1.0 spec: server-generated).

        Args:
            task: The A2ATask to submit.

        Returns:
            The task with updated status.
        """
        task.status = A2ATaskStatus.SUBMITTED
        task.updated_at = datetime.now(timezone.utc).isoformat()

        if not task.trace_id:
            task.trace_id = _inherit_trace_id()
        if not task.context_id:
            task.context_id = uuid.uuid4().hex[:12]

        self._tasks[task.id] = task

        logger.info(
            "A2A task submitted: %s ctx=%s trace=%s (from=%s, to=%s, cap=%s)",
            task.id, task.context_id, task.trace_id,
            task.from_agent, task.to_agent, task.capability,
        )

        # Dispatch to handler
        result = self._dispatch(task)
        self._append_task_log(result)
        return result

    def _dispatch(self, task: A2ATask) -> A2ATask:
        """Route task to appropriate handler and execute."""
        handler = self._handlers.get(task.capability)
        if handler is None:
            handler = self._default_handler

        if handler is None:
            task.status = A2ATaskStatus.FAILED
            task.error = f"No handler registered for capability: {task.capability!r}"
            task.updated_at = datetime.now(timezone.utc).isoformat()
            logger.warning("A2A task %s failed: no handler for %s", task.id, task.capability)
            return task

        task.status = A2ATaskStatus.WORKING
        task.updated_at = datetime.now(timezone.utc).isoformat()

        try:
            task = handler(task)
            if task.status == A2ATaskStatus.WORKING:
                # Handler didn't set final status -- mark completed
                task.status = A2ATaskStatus.COMPLETED
            task.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info("A2A task %s completed (status=%s)", task.id, task.status.value)
        except Exception as exc:
            task.status = A2ATaskStatus.FAILED
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
        task.status = A2ATaskStatus.CANCELLED
        task.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("A2A task %s cancelled", task_id)
        return True

    def reject(self, task_id: str, reason: str = "") -> bool:
        """Reject a task (A2A 1.0). Returns True if successful."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.is_terminal():
            return False
        safe_reason = str(reason).replace("\n", " ").replace("\r", " ")[:200]
        task.status = A2ATaskStatus.REJECTED
        task.error = safe_reason
        task.updated_at = datetime.now(timezone.utc).isoformat()
        logger.info("A2A task %s rejected: %s", task_id, safe_reason)
        return True

    def require_auth(self, task_id: str, reason: str = "") -> bool:
        """Set a task to AUTH_REQUIRED (A2A 1.0). Returns True if successful."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.is_terminal():
            return False
        safe_reason = str(reason).replace("\n", " ").replace("\r", " ")[:200]
        task.status = A2ATaskStatus.AUTH_REQUIRED
        task.error = safe_reason
        task.updated_at = datetime.now(timezone.utc).isoformat()
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
