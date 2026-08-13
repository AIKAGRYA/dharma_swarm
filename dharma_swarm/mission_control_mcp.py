"""Fail-closed MCP projection for the canonical Mission Control adapter.

This transport- and storage-free module delegates state changes to
``MissionControl``. Reads are available by default; mutations require both an
injected authorizer and a trusted principal. Constructing it does not start or
prove a live executor.
"""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.mission_control_mcp_mutations import (
    AUTHORIZED_PRINCIPAL_METADATA_KEY as AUTHORIZED_PRINCIPAL_METADATA_KEY,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MISSION_CREATE as MISSION_CREATE,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MISSION_CREATE_TASK as MISSION_CREATE_TASK,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MISSION_FINISH_ATTEMPT as MISSION_FINISH_ATTEMPT,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MISSION_HEARTBEAT_LEASE as MISSION_HEARTBEAT_LEASE,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MISSION_START_ATTEMPT as MISSION_START_ATTEMPT,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MUTATION_TOOL_NAMES as MUTATION_TOOL_NAMES,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MutationAuthorizer as MutationAuthorizer,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MutationDecision as MutationDecision,
)
from dharma_swarm.mission_control_mcp_mutations import (
    MutationRequest as MutationRequest,
)
from dharma_swarm.mission_control_mcp_mutations import (
    PrincipalDecision as PrincipalDecision,
)
from dharma_swarm.mission_control_mcp_mutations import (
    TrustedPrincipal as TrustedPrincipal,
)
from dharma_swarm.mission_control_mcp_mutations import (
    TrustedPrincipalResolver as TrustedPrincipalResolver,
)
from dharma_swarm.mission_control_mcp_mutations import (
    _ArgumentError as _ArgumentError,
)
from dharma_swarm.mission_control_mcp_mutations import _MissionControlMCPMutations
from dharma_swarm.mission_control_mcp_mutations import (
    _authorized_metadata as _authorized_metadata,
)
from dharma_swarm.mission_control_mcp_mutations import (
    _normalize_identifier as _normalize_identifier,
)
from dharma_swarm.mission_control_mcp_mutations import (
    _normalize_lease_seconds as _normalize_lease_seconds,
)
from dharma_swarm.mission_control_mcp_mutations import (
    _normalize_priority as _normalize_priority,
)
from dharma_swarm.mission_control_mcp_mutations import (
    _normalize_terminal_status as _normalize_terminal_status,
)
from dharma_swarm.models import TaskPriority as TaskPriority
from dharma_swarm.models import TaskStatus


SCHEMA_VERSION = "dharma.mission_control.v1"

MISSION_GET = "mission_get"
MISSION_SNAPSHOT = "mission_snapshot"
MISSION_LIST_TASKS = "mission_list_tasks"

READ_TOOL_NAMES = (
    MISSION_GET,
    MISSION_SNAPSHOT,
    MISSION_LIST_TASKS,
)
TOOL_NAMES = READ_TOOL_NAMES + MUTATION_TOOL_NAMES


ReadStateGuard: TypeAlias = Callable[[str], bool]

# Preserve the facade's historical import and pickle identity after extraction.
MutationRequest.__module__ = __name__


def _copy_immutable_sqlite(source: Path, destination: Path) -> None:
    """Copy a no-write main-database snapshot into disposable local state.

    ``immutable=1`` prevents SQLite from creating or updating source WAL/SHM
    sidecars. Rows committed only to a live WAL may therefore lag until the
    owner checkpoints them. Mission Control reports the result as an observed
    projection, never as executor liveness or a linearizable read.
    """

    source_uri = f"{source.resolve().as_uri()}?mode=ro&immutable=1"
    with (
        sqlite3.connect(source_uri, uri=True) as source_db,
        sqlite3.connect(destination) as destination_db,
    ):
        source_db.backup(destination_db)


class _ImmutableSnapshotMissionControl:
    """Run owner projections against disposable copies, never canonical DBs."""

    def __init__(self, *, task_db: Path, runtime_db: Path) -> None:
        self.task_db = task_db
        self.runtime_db = runtime_db

    async def _call(
        self,
        method_name: str,
        *args: Any,
        require_task_db: bool,
        **kwargs: Any,
    ) -> Any:
        from dharma_swarm.mission_control import MissionControl
        from dharma_swarm.runtime_state import RuntimeStateStore
        from dharma_swarm.task_board import TaskBoard

        with tempfile.TemporaryDirectory(prefix="dharma-mission-control-read-") as raw:
            root = Path(raw)
            runtime_copy = root / "runtime.db"
            task_copy = root / "tasks.db"
            await asyncio.to_thread(
                _copy_immutable_sqlite, self.runtime_db, runtime_copy
            )
            if require_task_db:
                await asyncio.to_thread(_copy_immutable_sqlite, self.task_db, task_copy)
            control = MissionControl(
                TaskBoard(task_copy),
                RuntimeStateStore(runtime_copy),
            )
            return await getattr(control, method_name)(*args, **kwargs)

    async def get_mission(self, mission_id: str) -> Any:
        return await self._call("get_mission", mission_id, require_task_db=False)

    async def get_snapshot(self, mission_id: str) -> Any:
        return await self._call("get_snapshot", mission_id, require_task_db=True)

    async def list_tasks(self, mission_id: str, **kwargs: Any) -> Any:
        return await self._call(
            "list_tasks", mission_id, require_task_db=True, **kwargs
        )


class MissionControlMCPService(_MissionControlMCPMutations):
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

    def _read_state_is_available(self, tool_name: str) -> bool:
        guard = self._read_state_guard
        if guard is None:
            return True
        try:
            return guard(tool_name) is True
        except Exception:
            return False

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


# Preserve pre-split callable provenance for introspection and function pickles.
for _public_method_name in (
    "create_mission",
    "create_task",
    "start_attempt",
    "heartbeat_lease",
    "finish_attempt",
):
    _public_method = getattr(MissionControlMCPService, _public_method_name)
    _public_method.__module__ = __name__
    _public_method.__qualname__ = f"MissionControlMCPService.{_public_method.__name__}"
del _public_method, _public_method_name


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
    raise TypeError(
        f"unsupported Mission Control projection type: {type(value).__name__}"
    )


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
            "Read-first observed projection of canonical Mission Control state. "
            "Bundled reads use immutable disposable snapshots and may lag rows "
            "that the canonical owner has not checkpointed from its WAL. "
            "Mutation tools are denied unless the embedding process injects "
            "both an authorizer and trusted principal identity. The trusted "
            "principal overrides caller actor fields and reserved attribution "
            "metadata. Attempt records do not prove executor liveness."
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
        (
            service.get_mission,
            MISSION_GET,
            "Read one observed mission projection by mission ID.",
            read_only,
        ),
        (
            service.get_snapshot,
            MISSION_SNAPSHOT,
            "Read a bounded snapshot with explicit reconciliation or scan-saturation state.",
            read_only,
        ),
        (
            service.list_tasks,
            MISSION_LIST_TASKS,
            "List canonical TaskBoard tasks belonging to one mission.",
            read_only,
        ),
        (
            service.create_mission,
            MISSION_CREATE,
            "Create or project a mission; the trusted principal is its operator.",
            mutation,
        ),
        (
            service.create_task,
            MISSION_CREATE_TASK,
            "Create a canonical task; the trusted principal is its creator.",
            mutation,
        ),
        (
            service.start_attempt,
            MISSION_START_ATTEMPT,
            "Record an attempt and lease with the trusted principal as assigner; "
            "does not launch or prove a live executor.",
            mutation,
        ),
        (
            service.heartbeat_lease,
            MISSION_HEARTBEAT_LEASE,
            "Refresh an existing lease; requires injected authorization.",
            mutation,
        ),
        (
            service.finish_attempt,
            MISSION_FINISH_ATTEMPT,
            "Record a terminal receipt then project task state; requires authorization.",
            mutation,
        ),
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

    state_dir = dharma_state_dir("DHARMA_STATE_DIR")
    task_db = state_dir / "db" / "tasks.db"
    runtime_db = state_dir / "state" / "runtime.db"
    control = _ImmutableSnapshotMissionControl(
        task_db=task_db,
        runtime_db=runtime_db,
    )

    def read_state_guard(tool_name: str) -> bool:
        # Guard absent files before constructing a disposable immutable copy.
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
