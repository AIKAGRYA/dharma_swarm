"""Fail-closed MCP projection for the canonical Mission Control adapter.

This transport- and storage-free module delegates state changes to
``MissionControl``. Reads are available by default; mutations require both an
injected authorizer and a trusted principal. Constructing it does not start or
prove a live executor.
"""

from __future__ import annotations

import inspect
import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias

from dharma_swarm.models import TaskPriority, TaskStatus


SCHEMA_VERSION = "dharma.mission_control.v1"

MISSION_GET = "mission_get"
MISSION_SNAPSHOT = "mission_snapshot"
MISSION_LIST_TASKS = "mission_list_tasks"
MISSION_CREATE = "mission_create"
MISSION_CREATE_TASK = "mission_create_task"
MISSION_START_ATTEMPT = "mission_start_attempt"
MISSION_HEARTBEAT_LEASE = "mission_heartbeat_lease"
MISSION_FINISH_ATTEMPT = "mission_finish_attempt"

READ_TOOL_NAMES = (
    MISSION_GET,
    MISSION_SNAPSHOT,
    MISSION_LIST_TASKS,
)
MUTATION_TOOL_NAMES = (
    MISSION_CREATE,
    MISSION_CREATE_TASK,
    MISSION_START_ATTEMPT,
    MISSION_HEARTBEAT_LEASE,
    MISSION_FINISH_ATTEMPT,
)
TOOL_NAMES = READ_TOOL_NAMES + MUTATION_TOOL_NAMES


@dataclass(frozen=True, slots=True)
class MutationRequest:
    """Minimal, non-secret context presented to a mutation authorizer.

    Descriptions, results, evidence, and metadata are intentionally excluded so
    an authorization integration cannot accidentally treat request content as
    a bearer credential or leak it through policy logs.
    """

    tool_name: str
    principal: str
    mission_id: str
    task_id: str = ""
    attempt_id: str = ""
    attempt_key: str = ""
    agent_id: str = ""
    operator_id: str = ""
    created_by: str = ""
    priority: str = ""
    dependency_count: int = 0
    dependency_ids: tuple[str, ...] = ()
    has_idempotency_key: bool = False
    lease_seconds: int | None = None
    terminal_status: str = ""
    failure_code_present: bool = False


MutationDecision: TypeAlias = bool | Awaitable[bool]
MutationAuthorizer: TypeAlias = Callable[[MutationRequest], MutationDecision]
PrincipalDecision: TypeAlias = str | Awaitable[str]
TrustedPrincipalResolver: TypeAlias = Callable[[], PrincipalDecision]
TrustedPrincipal: TypeAlias = str | TrustedPrincipalResolver
ReadStateGuard: TypeAlias = Callable[[str], bool]


class _ArgumentError(ValueError):
    """A safe, caller-correctable MCP argument error."""


def _normalize_lease_seconds(value: Any) -> int:
    """Return an authorization-safe lease duration without bool coercion."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _ArgumentError("lease_ttl_seconds must be a positive integer")
    return value


def _normalize_identifier(value: Any, label: str) -> str:
    """Mirror Mission Control identifier normalization before authorization."""

    normalized = str(value or "").strip()
    if not normalized:
        raise _ArgumentError(f"{label} is required")
    if any(character.isspace() for character in normalized):
        raise _ArgumentError(f"{label} must not contain whitespace")
    return normalized


def _normalize_actor(value: Any, *, default: str, label: str) -> str:
    return _normalize_identifier(value or default, label)


def _normalize_priority(value: Any) -> TaskPriority:
    try:
        return TaskPriority(value)
    except (TypeError, ValueError) as exc:
        raise _ArgumentError(f"invalid task priority: {value!r}") from exc


def _normalize_terminal_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in {"succeeded", "failed"}:
        raise _ArgumentError("outcome must be 'succeeded' or 'failed'")
    return normalized


class MissionControlMCPService:
    """JSON-safe service layer used by the FastMCP tool functions."""

    def __init__(
        self,
        control: Any,
        *,
        mutation_authorizer: MutationAuthorizer | None = None,
        trusted_principal: TrustedPrincipal | None = None,
        read_state_guard: ReadStateGuard | None = None,
    ) -> None:
        self._control = control
        self._mutation_authorizer = mutation_authorizer
        self._trusted_principal = trusted_principal
        self._read_state_guard = read_state_guard

    async def get_mission(self, mission_id: str) -> dict[str, Any]:
        return await self._read(
            MISSION_GET,
            lambda: self._control.get_mission(mission_id),
            not_found=f"mission {mission_id!r} was not found",
        )

    async def get_snapshot(self, mission_id: str) -> dict[str, Any]:
        return await self._read(
            MISSION_SNAPSHOT,
            lambda: self._control.get_snapshot(mission_id),
            not_found=f"mission {mission_id!r} was not found",
        )

    async def list_tasks(
        self,
        mission_id: str,
        *,
        status: str = "",
        assigned_to: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            if not self._read_state_is_available(MISSION_LIST_TASKS):
                return self._state_not_initialized(MISSION_LIST_TASKS)
            if not 1 <= limit <= 1_000:
                raise _ArgumentError("limit must be between 1 and 1000")
            parsed_status = TaskStatus(status) if status else None
            value = await self._control.list_tasks(
                mission_id,
                status=parsed_status,
                assigned_to=assigned_to or None,
                limit=limit,
            )
            return self._success(MISSION_LIST_TASKS, value)
        except Exception as exc:
            return self._failure(MISSION_LIST_TASKS, exc)

    async def create_mission(
        self,
        mission_id: str,
        title: str,
        objective: str = "",
        *,
        operator_id: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_CREATE
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                operator_id=_normalize_actor(
                    operator_id,
                    default="system",
                    label="operator_id",
                ),
            ),
            lambda request: self._control.create_mission(
                request.mission_id,
                title=title,
                goal=objective,
                operator_id=request.operator_id,
                metadata=metadata,
            ),
        )

    async def create_task(
        self,
        mission_id: str,
        title: str,
        description: str = "",
        *,
        priority: str = "normal",
        created_by: str = "system",
        depends_on: list[str] | None = None,
        idempotency_key: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_CREATE_TASK

        def request_factory(principal: str) -> MutationRequest:
            parsed_priority = _normalize_priority(priority)
            dependency_ids = tuple(
                _normalize_identifier(item, "depends_on item")
                for item in (depends_on or ())
            )
            return MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                created_by=_normalize_actor(
                    created_by,
                    default="system",
                    label="created_by",
                ),
                priority=parsed_priority.value,
                dependency_count=len(dependency_ids),
                dependency_ids=dependency_ids,
                has_idempotency_key=bool(str(idempotency_key or "").strip()),
            )

        async def operation(request: MutationRequest) -> Any:
            return await self._control.create_task(
                request.mission_id,
                title=title,
                description=description,
                priority=TaskPriority(request.priority),
                created_by=request.created_by,
                depends_on=(
                    list(request.dependency_ids) if depends_on is not None else None
                ),
                idempotency_key=idempotency_key,
                metadata=metadata,
            )

        return await self._mutate(tool_name, request_factory, operation)

    async def start_attempt(
        self,
        mission_id: str,
        task_id: str,
        attempt_key: str,
        agent_id: str,
        *,
        lease_ttl_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_START_ATTEMPT
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                task_id=_normalize_identifier(task_id, "task_id"),
                attempt_key=str(attempt_key or "").strip(),
                agent_id=_normalize_identifier(agent_id, "agent_id"),
                lease_seconds=_normalize_lease_seconds(lease_ttl_seconds),
            ),
            lambda request: self._control.start_attempt(
                request.mission_id,
                request.task_id,
                request.agent_id,
                attempt_key=request.attempt_key,
                lease_seconds=request.lease_seconds,
                metadata=metadata,
            ),
        )

    async def heartbeat_lease(
        self,
        mission_id: str,
        task_id: str,
        attempt_id: str,
        agent_id: str,
        *,
        lease_ttl_seconds: int = 300,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_HEARTBEAT_LEASE
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                task_id=_normalize_identifier(task_id, "task_id"),
                attempt_id=_normalize_identifier(attempt_id, "attempt_id"),
                agent_id=_normalize_identifier(agent_id, "agent_id"),
                lease_seconds=_normalize_lease_seconds(lease_ttl_seconds),
            ),
            lambda request: self._control.heartbeat_lease(
                request.mission_id,
                request.task_id,
                request.agent_id,
                attempt_id=request.attempt_id,
                lease_seconds=request.lease_seconds,
                metadata=metadata,
            ),
        )

    async def finish_attempt(
        self,
        mission_id: str,
        task_id: str,
        attempt_id: str,
        agent_id: str,
        outcome: str,
        *,
        result: str = "",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_name = MISSION_FINISH_ATTEMPT
        return await self._mutate(
            tool_name,
            lambda principal: MutationRequest(
                tool_name=tool_name,
                principal=principal,
                mission_id=_normalize_identifier(mission_id, "mission_id"),
                task_id=_normalize_identifier(task_id, "task_id"),
                attempt_id=_normalize_identifier(attempt_id, "attempt_id"),
                agent_id=_normalize_identifier(agent_id, "agent_id"),
                terminal_status=_normalize_terminal_status(outcome),
                failure_code_present=bool(str(error or "").strip()),
            ),
            lambda request: self._control.finish_attempt(
                request.mission_id,
                request.task_id,
                request.agent_id,
                attempt_id=request.attempt_id,
                status=request.terminal_status,
                result=result,
                failure_code=error,
                metadata=metadata,
            ),
        )

    async def _read(
        self,
        tool_name: str,
        operation: Callable[[], Awaitable[Any]],
        *,
        not_found: str,
    ) -> dict[str, Any]:
        try:
            if not self._read_state_is_available(tool_name):
                return self._state_not_initialized(tool_name)
            value = await operation()
            if value is None:
                return self._error(tool_name, "not_found", not_found)
            return self._success(tool_name, value)
        except Exception as exc:
            return self._failure(tool_name, exc)

    async def _mutate(
        self,
        tool_name: str,
        request_factory: Callable[[str], MutationRequest],
        operation: Callable[[MutationRequest], Awaitable[Any]],
    ) -> dict[str, Any]:
        if self._mutation_authorizer is None:
            return self._mutation_denied(tool_name)
        principal = await self._resolve_trusted_principal()
        if principal is None:
            return self._mutation_denied(tool_name)
        try:
            request = request_factory(principal)
        except Exception as exc:
            return self._failure(tool_name, exc)
        if not await self._is_authorized(request):
            return self._mutation_denied(tool_name)
        try:
            return self._success(tool_name, await operation(request))
        except Exception as exc:
            return self._failure(tool_name, exc)

    async def _is_authorized(self, request: MutationRequest) -> bool:
        authorizer = self._mutation_authorizer
        if authorizer is None:
            return False
        try:
            decision = authorizer(request)
            if inspect.isawaitable(decision):
                decision = await decision
        except Exception:
            return False
        return decision is True

    async def _resolve_trusted_principal(self) -> str | None:
        source = self._trusted_principal
        if source is None:
            return None
        try:
            principal = source() if callable(source) else source
            if inspect.isawaitable(principal):
                principal = await principal
        except Exception:
            return None
        if not isinstance(principal, str):
            return None
        normalized = principal.strip()
        if not normalized or len(normalized) > 256 or any(
            character.isspace() or ord(character) < 32 for character in normalized
        ):
            return None
        return normalized

    def _read_state_is_available(self, tool_name: str) -> bool:
        guard = self._read_state_guard
        if guard is None:
            return True
        try:
            return guard(tool_name) is True
        except Exception:
            return False

    @staticmethod
    def _mutation_denied(tool_name: str) -> dict[str, Any]:
        return MissionControlMCPService._error(
            tool_name,
            "mutation_not_authorized",
            "mutation denied: this Mission Control MCP surface is read-only by default",
        )

    @staticmethod
    def _state_not_initialized(tool_name: str) -> dict[str, Any]:
        return MissionControlMCPService._error(
            tool_name,
            "state_not_initialized",
            "Mission Control state is not initialized",
        )

    @staticmethod
    def _success(tool_name: str, value: Any) -> dict[str, Any]:
        try:
            data = _json_projection(value)
        except (TypeError, ValueError) as exc:
            return MissionControlMCPService._error(
                tool_name,
                "projection_error",
                str(exc),
            )
        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "tool": tool_name,
            "data": data,
        }

    @staticmethod
    def _failure(tool_name: str, exc: Exception) -> dict[str, Any]:
        if isinstance(exc, (_ArgumentError, ValueError)):
            return MissionControlMCPService._error(
                tool_name,
                "invalid_argument",
                str(exc),
            )

        # Keep domain failures useful while preventing unexpected exceptions
        # (which may include local paths or database details) from crossing the
        # MCP boundary.
        try:
            from dharma_swarm.mission_control import MissionControlError
        except ImportError:
            MissionControlError = ()  # type: ignore[assignment,misc]
        if isinstance(exc, MissionControlError):
            return MissionControlMCPService._error(
                tool_name,
                "mission_control_error",
                str(exc),
            )
        return MissionControlMCPService._error(
            tool_name,
            "internal_error",
            "Mission Control operation failed",
        )

    @staticmethod
    def _error(tool_name: str, code: str, message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "tool": tool_name,
            "error": {"code": code, "message": message},
        }


def _json_projection(value: Any) -> Any:
    """Project typed Mission Control views without permissive ``default=str``."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _json_projection(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_projection(to_dict())
    if is_dataclass(value) and not isinstance(value, type):
        return _json_projection(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_projection(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_projection(item) for item in value]
    raise TypeError(f"unsupported Mission Control projection type: {type(value).__name__}")


def create_mission_control_mcp(
    control: Any,
    *,
    mutation_authorizer: MutationAuthorizer | None = None,
    trusted_principal: TrustedPrincipal | None = None,
    read_state_guard: ReadStateGuard | None = None,
    server_name: str = "dharma-mission-control",
) -> Any:
    """Create the standalone FastMCP server.

    Both ``mutation_authorizer`` and ``trusted_principal`` are intentionally
    dependency-injected. No token, environment variable, or request argument
    can silently enable writes. The principal may be a fixed trusted identity
    or a zero-argument resolver owned by the embedding transport.
    """

    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "Mission Control MCP support requires the 'mcp' package. "
            "Install with: pip install dharma-swarm[mcp]"
        ) from exc

    service = MissionControlMCPService(
        control,
        mutation_authorizer=mutation_authorizer,
        trusted_principal=trusted_principal,
        read_state_guard=read_state_guard,
    )
    server = FastMCP(
        server_name,
        instructions=(
            "Read-first projection of canonical Mission Control state. "
            "Mutation tools are denied unless the embedding process injects "
            "both an authorizer and trusted principal identity. Attempt "
            "records do not prove executor liveness."
        ),
    )
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    mutation = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )

    registrations = (
        (service.get_mission, MISSION_GET,
         "Read one canonical mission projection by mission ID.", read_only),
        (service.get_snapshot, MISSION_SNAPSHOT,
         "Read a coherent snapshot with reconciliation state.", read_only),
        (service.list_tasks, MISSION_LIST_TASKS,
         "List canonical TaskBoard tasks belonging to one mission.", read_only),
        (service.create_mission, MISSION_CREATE,
         "Create or project a mission; requires injected authorization.", mutation),
        (service.create_task, MISSION_CREATE_TASK,
         "Create a canonical task; requires injected authorization.", mutation),
        (service.start_attempt, MISSION_START_ATTEMPT,
         "Record an attempt and lease; authorized only; does not launch or prove a live executor.",
         mutation),
        (service.heartbeat_lease, MISSION_HEARTBEAT_LEASE,
         "Refresh an existing lease; requires injected authorization.", mutation),
        (service.finish_attempt, MISSION_FINISH_ATTEMPT,
         "Record a terminal receipt then project task state; requires authorization.",
         mutation),
    )
    for function, name, description, tool_annotations in registrations:
        server.add_tool(
            function,
            name=name,
            description=description,
            annotations=tool_annotations,
            structured_output=True,
        )

    return server


def create_default_mission_control_mcp() -> Any:
    """Bind canonical local owners to a read-only stdio-ready MCP server."""

    from dharma_swarm.mission_control import MissionControl
    from dharma_swarm.runtime_state import RuntimeStateStore
    from dharma_swarm.task_board import TaskBoard

    state_dir = Path(os.environ.get("DHARMA_STATE_DIR", "~/.dharma")).expanduser()
    task_db = state_dir / "db" / "tasks.db"
    runtime_db = state_dir / "state" / "runtime.db"
    control = MissionControl(TaskBoard(task_db), RuntimeStateStore(runtime_db))

    def read_state_guard(tool_name: str) -> bool:
        # Canonical owner read methods initialize SQLite before querying. Guard
        # absent files here so merely connecting a read-only MCP client cannot
        # create ~/.dharma, either database, or their parent directories.
        if tool_name == MISSION_GET:
            return runtime_db.is_file()
        return runtime_db.is_file() and task_db.is_file()

    # No environment flag can supply an authorizer. The executable surface is
    # therefore read-only even if a caller controls its environment. The read
    # guard also makes an uninitialized state tree observationally read-only.
    return create_mission_control_mcp(control, read_state_guard=read_state_guard)


def main() -> None:
    """Serve Mission Control over stdio, read-only by default."""

    create_default_mission_control_mcp().run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover - exercised by an MCP client
    main()
