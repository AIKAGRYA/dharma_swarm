"""Contract tests for the standalone, fail-closed Mission Control MCP surface."""

from __future__ import annotations

import importlib.util
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import pytest

from dharma_swarm.mission_control_mcp import (
    AUTHORIZED_PRINCIPAL_METADATA_KEY,
    MISSION_CREATE,
    MISSION_CREATE_TASK,
    MISSION_FINISH_ATTEMPT,
    MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT,
    MISSION_GET,
    MISSION_HEARTBEAT_LEASE,
    MISSION_LIST_TASKS,
    MISSION_SNAPSHOT,
    MISSION_START_ATTEMPT,
    MUTATION_TOOL_NAMES,
    READ_TOOL_NAMES,
    SCHEMA_VERSION,
    TOOL_NAMES,
    MissionControlMCPService,
    MutationRequest,
    _json_projection,
    create_mission_control_mcp,
)
from dharma_swarm import mission_control_mcp
from dharma_swarm.models import TaskPriority, TaskStatus

_MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None
_requires_mcp = pytest.mark.skipif(
    not _MCP_AVAILABLE,
    reason="mcp optional dependency not installed",
)


@dataclass(frozen=True)
class _View:
    kind: str
    identifier: str
    happened_at: datetime = datetime(2026, 8, 12, tzinfo=UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "identifier": self.identifier,
            "happened_at": self.happened_at,
        }


class _ProbeEnum(str, Enum):
    READY = "ready"


class _FakeMissionControl:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def _record(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.calls.append((name, args, kwargs))

    async def get_mission(self, mission_id: str) -> _View | None:
        self._record("get_mission", (mission_id,), {})
        if mission_id == "missing":
            return None
        if mission_id == "explode":
            raise RuntimeError("/private/secret/database.sqlite")
        return _View("mission", mission_id)

    async def get_snapshot(self, mission_id: str) -> dict[str, Any] | None:
        self._record("get_snapshot", (mission_id,), {})
        if mission_id == "missing":
            return None
        return {
            "schema_version": SCHEMA_VERSION,
            "mission": _View("mission", mission_id),
            "tasks": (_View("task", "task-1"),),
            "attempts": (),
            "leases": (),
            "receipts": (),
            "reconciliation_state": _ProbeEnum.READY,
            "reconciliation_details": (),
        }

    async def list_tasks(
        self,
        mission_id: str,
        *,
        status: TaskStatus | None,
        assigned_to: str | None,
        limit: int,
    ) -> tuple[_View, ...]:
        self._record(
            "list_tasks",
            (mission_id,),
            {"status": status, "assigned_to": assigned_to, "limit": limit},
        )
        return (_View("task", "task-1"),)

    async def create_mission(
        self,
        mission_id: str,
        *,
        title: str,
        goal: str,
        operator_id: str,
        metadata: dict[str, Any] | None,
    ) -> _View:
        self._record(
            "create_mission",
            (mission_id,),
            {
                "title": title,
                "goal": goal,
                "operator_id": operator_id,
                "metadata": metadata,
            },
        )
        return _View("mission", mission_id)

    async def create_task(
        self,
        mission_id: str,
        *,
        title: str,
        description: str,
        priority: TaskPriority,
        created_by: str,
        depends_on: list[str] | None,
        idempotency_key: str,
        metadata: dict[str, Any] | None,
    ) -> _View:
        self._record(
            "create_task",
            (mission_id,),
            {
                "title": title,
                "description": description,
                "priority": priority,
                "created_by": created_by,
                "depends_on": depends_on,
                "idempotency_key": idempotency_key,
                "metadata": metadata,
            },
        )
        return _View("task", "task-created")

    async def start_attempt(
        self, mission_id: str, task_id: str, agent_id: str, **kwargs: Any
    ) -> _View:
        self._record("start_attempt", (mission_id, task_id, agent_id), kwargs)
        return _View("attempt", str(kwargs["attempt_key"]))

    async def heartbeat_lease(
        self, mission_id: str, task_id: str, agent_id: str, **kwargs: Any
    ) -> _View:
        self._record("heartbeat_lease", (mission_id, task_id, agent_id), kwargs)
        return _View("lease", str(kwargs["attempt_id"]))

    async def finish_attempt(
        self, mission_id: str, task_id: str, agent_id: str, **kwargs: Any
    ) -> _View:
        self._record("finish_attempt", (mission_id, task_id, agent_id), kwargs)
        return _View("receipt", str(kwargs["attempt_id"]))

    async def finish_attempt_from_patch_effect(
        self, mission_id: str, task_id: str, agent_id: str, **kwargs: Any
    ) -> _View:
        self._record(
            "finish_attempt_from_patch_effect",
            (mission_id, task_id, agent_id),
            kwargs,
        )
        return _View("receipt", str(kwargs["attempt_id"]))


def _structured_result(call_result: Any) -> dict[str, Any]:
    """Extract structured output from the installed FastMCP 1.x result shape."""

    if isinstance(call_result, tuple) and len(call_result) == 2:
        return call_result[1]
    if isinstance(call_result, dict):
        return call_result
    raise AssertionError(f"unexpected FastMCP result shape: {call_result!r}")


def test_json_projection_is_typed_and_json_safe() -> None:
    projected = _json_projection(
        {
            "view": _View("task", "t-1"),
            "state": _ProbeEnum.READY,
            "items": (_View("receipt", "r-1"),),
        }
    )

    assert projected == {
        "view": {
            "kind": "task",
            "identifier": "t-1",
            "happened_at": "2026-08-12T00:00:00+00:00",
        },
        "state": "ready",
        "items": [
            {
                "kind": "receipt",
                "identifier": "r-1",
                "happened_at": "2026-08-12T00:00:00+00:00",
            }
        ],
    }


@pytest.mark.asyncio
async def test_default_service_rejects_mutations_without_calling_control() -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(control)

    result = await service.create_mission(
        "m-1",
        "Secret title",
        metadata={"not_a_bearer_token": "content"},
    )

    assert result == {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "tool": MISSION_CREATE,
        "error": {
            "code": "mutation_not_authorized",
            "message": (
                "mutation denied: this Mission Control MCP surface is read-only by default"
            ),
        },
    }
    assert control.calls == []


@pytest.mark.asyncio
async def test_mutation_requires_both_authorizer_and_trusted_principal() -> None:
    control = _FakeMissionControl()
    authorizer_calls: list[MutationRequest] = []

    def authorize(request: MutationRequest) -> bool:
        authorizer_calls.append(request)
        return True

    missing_principal = MissionControlMCPService(
        control,
        mutation_authorizer=authorize,
    )
    missing_authorizer = MissionControlMCPService(
        control,
        trusted_principal="operator:alice",
    )

    first = await missing_principal.create_mission("m-1", "Title")
    second = await missing_authorizer.create_mission("m-1", "Title")

    assert first["error"]["code"] == "mutation_not_authorized"
    assert second["error"]["code"] == "mutation_not_authorized"
    assert authorizer_calls == []
    assert control.calls == []


@pytest.mark.asyncio
async def test_principal_resolver_failure_is_denied_without_detail_leak() -> None:
    control = _FakeMissionControl()

    async def broken_resolver() -> str:
        raise RuntimeError("secret identity backend path /private/policy.db")

    service = MissionControlMCPService(
        control,
        mutation_authorizer=lambda _request: True,
        trusted_principal=broken_resolver,
    )

    result = await service.create_mission("m-1", "Title")

    assert result["error"]["code"] == "mutation_not_authorized"
    assert "secret" not in repr(result)
    assert "private" not in repr(result).lower()
    assert control.calls == []


@pytest.mark.asyncio
async def test_authorizer_receives_only_minimal_non_secret_context() -> None:
    control = _FakeMissionControl()
    requests: list[MutationRequest] = []

    async def authorize(request: MutationRequest) -> bool:
        requests.append(request)
        return request.tool_name == MISSION_CREATE

    service = MissionControlMCPService(
        control,
        mutation_authorizer=authorize,
        trusted_principal=" operator:alice ",
    )
    result = await service.create_mission(
        "m-1",
        "Private mission title",
        objective="Private objective",
        metadata={"private": "payload"},
    )

    assert result["ok"] is True
    assert result["data"]["identifier"] == "m-1"
    assert requests == [
        MutationRequest(
            tool_name=MISSION_CREATE,
            principal="operator:alice",
            mission_id="m-1",
            operator_id="operator:alice",
        )
    ]
    assert "Private" not in repr(requests[0])
    assert control.calls[0] == (
        "create_mission",
        ("m-1",),
        {
            "title": "Private mission title",
            "goal": "Private objective",
            "operator_id": "operator:alice",
            "metadata": {
                "private": "payload",
                AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:alice",
            },
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", [False, None, 1, "yes"])
async def test_authorization_fails_closed_unless_decision_is_exactly_true(
    decision: Any,
) -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(
        control,
        mutation_authorizer=lambda _request: decision,
        trusted_principal="operator:alice",
    )

    result = await service.create_mission("m-1", "Title")

    assert result["ok"] is False
    assert result["error"]["code"] == "mutation_not_authorized"
    assert control.calls == []


@pytest.mark.asyncio
async def test_authorizer_exception_fails_closed() -> None:
    control = _FakeMissionControl()

    def broken_authorizer(_request: MutationRequest) -> bool:
        raise RuntimeError("policy backend unavailable")

    service = MissionControlMCPService(
        control,
        mutation_authorizer=broken_authorizer,
        trusted_principal="operator:alice",
    )
    result = await service.create_mission("m-1", "Title")

    assert result["error"]["code"] == "mutation_not_authorized"
    assert control.calls == []


@pytest.mark.asyncio
async def test_read_projection_and_explicit_not_found_payloads() -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(control)

    found = await service.get_snapshot("m-1")
    missing = await service.get_mission("missing")

    assert found["ok"] is True
    assert found["data"]["schema_version"] == SCHEMA_VERSION
    assert found["data"]["mission"]["identifier"] == "m-1"
    assert found["data"]["reconciliation_state"] == "ready"
    assert missing["ok"] is False
    assert missing["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_unexpected_errors_do_not_leak_runtime_details() -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(control)

    result = await service.get_mission("explode")

    assert result["error"] == {
        "code": "internal_error",
        "message": "Mission Control operation failed",
    }
    assert "secret" not in repr(result)


@pytest.mark.asyncio
async def test_list_tasks_validates_and_converts_filters() -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(control)

    result = await service.list_tasks(
        "m-1",
        status="running",
        assigned_to="agent-1",
        limit=7,
    )

    assert result["ok"] is True
    assert result["data"][0]["identifier"] == "task-1"
    assert control.calls[-1] == (
        "list_tasks",
        ("m-1",),
        {"status": TaskStatus.RUNNING, "assigned_to": "agent-1", "limit": 7},
    )
    invalid = await service.list_tasks("m-1", status="not-a-status")
    assert invalid["error"]["code"] == "invalid_argument"


@pytest.mark.asyncio
async def test_create_task_converts_priority_on_authorized_path() -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(
        control,
        mutation_authorizer=lambda request: request.tool_name == MISSION_CREATE_TASK,
        trusted_principal="operator:alice",
    )

    result = await service.create_task("m-1", "Task", priority="urgent")

    assert result["ok"] is True
    assert control.calls[-1][2]["priority"] is TaskPriority.URGENT


@pytest.mark.asyncio
async def test_patch_effect_finish_is_denied_by_default_without_control_call() -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(control)

    result = await service.finish_attempt_from_patch_effect(
        "m-1",
        "task-1",
        "attempt-1",
        "agent-1",
        "effect:one",
    )

    assert result["error"]["code"] == "mutation_not_authorized"
    assert control.calls == []


@pytest.mark.asyncio
async def test_patch_effect_finish_routes_only_exact_proof_identity_to_authorizer() -> (
    None
):
    control = _FakeMissionControl()
    requests: list[MutationRequest] = []

    def authorize(request: MutationRequest) -> bool:
        requests.append(request)
        return request.tool_name == MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT

    service = MissionControlMCPService(
        control,
        mutation_authorizer=authorize,
        trusted_principal="operator:alice",
    )
    result = await service.finish_attempt_from_patch_effect(
        "m-1",
        "task-1",
        "attempt-1",
        "agent-1",
        "effect:one",
    )

    assert result["ok"] is True
    assert requests == [
        MutationRequest(
            tool_name=MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT,
            principal="operator:alice",
            mission_id="m-1",
            task_id="task-1",
            attempt_id="attempt-1",
            agent_id="agent-1",
            terminal_status="succeeded",
            effect_key="effect:one",
        )
    ]
    assert control.calls == [
        (
            "finish_attempt_from_patch_effect",
            ("m-1", "task-1", "agent-1"),
            {"attempt_id": "attempt-1", "effect_key": "effect:one"},
        )
    ]


@pytest.mark.asyncio
async def test_trusted_principal_overrides_spoofed_actor_and_metadata_fields() -> None:
    control = _FakeMissionControl()
    service = MissionControlMCPService(
        control,
        mutation_authorizer=lambda _request: True,
        trusted_principal="operator:trusted",
    )
    spoofed_metadata = {
        "kept": "caller content",
        AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:spoofed",
    }

    await service.create_mission(
        "m",
        "Mission",
        operator_id="operator:spoofed",
        metadata=spoofed_metadata,
    )
    await service.create_task(
        "m",
        "Task",
        created_by="operator:spoofed",
        metadata=spoofed_metadata,
    )
    await service.start_attempt(
        "m",
        "t",
        "attempt-key",
        "agent",
        metadata=spoofed_metadata,
    )
    await service.heartbeat_lease(
        "m",
        "t",
        "attempt",
        "agent",
        metadata=spoofed_metadata,
    )
    await service.finish_attempt(
        "m",
        "t",
        "attempt",
        "agent",
        "succeeded",
        metadata=spoofed_metadata,
    )

    expected_metadata = {
        "kept": "caller content",
        AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:trusted",
    }
    mission_call, task_call, start_call, heartbeat_call, finish_call = control.calls
    assert mission_call[2]["operator_id"] == "operator:trusted"
    assert task_call[2]["created_by"] == "operator:trusted"
    assert start_call[2]["assigned_by"] == "operator:trusted"
    for call in control.calls:
        assert call[2]["metadata"] == expected_metadata
    assert spoofed_metadata[AUTHORIZED_PRINCIPAL_METADATA_KEY] == "operator:spoofed"
    assert heartbeat_call[2]["metadata"] == expected_metadata
    assert finish_call[2]["metadata"] == expected_metadata


@pytest.mark.asyncio
@_requires_mcp
async def test_fastmcp_registers_stable_names_and_honest_annotations() -> None:
    server = create_mission_control_mcp(_FakeMissionControl())
    tools = {tool.name: tool for tool in await server.list_tools()}

    assert tuple(tools) == TOOL_NAMES
    assert set(READ_TOOL_NAMES) | set(MUTATION_TOOL_NAMES) == set(TOOL_NAMES)
    for name in READ_TOOL_NAMES:
        assert tools[name].annotations.readOnlyHint is True
    for name in MUTATION_TOOL_NAMES:
        assert tools[name].annotations.readOnlyHint is False
    assert "does not launch or prove a live executor" in (
        tools[MISSION_START_ATTEMPT].description or ""
    )
    start_schema = tools[MISSION_START_ATTEMPT].inputSchema
    assert "attempt_key" in start_schema["properties"]
    assert "attempt_id" not in start_schema["properties"]
    effect_schema = tools[MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT].inputSchema
    assert set(effect_schema["properties"]) == {
        "mission_id",
        "task_id",
        "attempt_id",
        "agent_id",
        "effect_key",
    }
    assert set(effect_schema["required"]) == set(effect_schema["properties"])
    assert "consumed governed patch effect" in (
        tools[MISSION_FINISH_ATTEMPT_FROM_PATCH_EFFECT].description or ""
    )


@pytest.mark.asyncio
@_requires_mcp
async def test_fastmcp_read_call_returns_structured_payload() -> None:
    server = create_mission_control_mcp(_FakeMissionControl())

    call_result = await server.call_tool(MISSION_GET, {"mission_id": "m-1"})
    payload = _structured_result(call_result)

    assert payload["ok"] is True
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["tool"] == MISSION_GET
    assert payload["data"]["identifier"] == "m-1"


@pytest.mark.asyncio
@_requires_mcp
async def test_fastmcp_mutation_is_denied_by_default_and_explicitly_authorizable() -> (
    None
):
    denied_control = _FakeMissionControl()
    denied_server = create_mission_control_mcp(denied_control)
    denied = _structured_result(
        await denied_server.call_tool(
            MISSION_CREATE,
            {"mission_id": "m-1", "title": "Mission"},
        )
    )

    assert denied["error"]["code"] == "mutation_not_authorized"
    assert denied_control.calls == []

    allowed_control = _FakeMissionControl()
    allowed_server = create_mission_control_mcp(
        allowed_control,
        mutation_authorizer=lambda request: request.tool_name == MISSION_CREATE,
        trusted_principal="operator:alice",
    )
    allowed = _structured_result(
        await allowed_server.call_tool(
            MISSION_CREATE,
            {"mission_id": "m-1", "title": "Mission"},
        )
    )

    assert allowed["ok"] is True
    assert allowed["data"]["kind"] == "mission"
    assert allowed_control.calls[0][0] == "create_mission"


@pytest.mark.asyncio
async def test_all_attempt_mutations_route_through_authorizer() -> None:
    control = _FakeMissionControl()
    authorized: list[MutationRequest] = []

    def authorize(request: MutationRequest) -> bool:
        authorized.append(request)
        return True

    service = MissionControlMCPService(
        control,
        mutation_authorizer=authorize,
        trusted_principal=lambda: "operator:alice",
    )
    await service.start_attempt(
        "m",
        "t",
        "a",
        "agent",
        lease_ttl_seconds=61,
        metadata={"secret": "start metadata"},
    )
    await service.heartbeat_lease(
        "m",
        "t",
        "a",
        "agent",
        lease_ttl_seconds=62,
        metadata={"secret": "heartbeat metadata"},
    )
    await service.finish_attempt(
        "m",
        "t",
        "a",
        "agent",
        " FAILED ",
        result="private result",
        error="E_PRIVATE",
        metadata={"secret": "finish metadata"},
    )

    assert authorized == [
        MutationRequest(
            tool_name=MISSION_START_ATTEMPT,
            principal="operator:alice",
            mission_id="m",
            task_id="t",
            attempt_key="a",
            agent_id="agent",
            assigned_by="operator:alice",
            lease_seconds=61,
        ),
        MutationRequest(
            tool_name=MISSION_HEARTBEAT_LEASE,
            principal="operator:alice",
            mission_id="m",
            task_id="t",
            attempt_id="a",
            agent_id="agent",
            lease_seconds=62,
        ),
        MutationRequest(
            tool_name=MISSION_FINISH_ATTEMPT,
            principal="operator:alice",
            mission_id="m",
            task_id="t",
            attempt_id="a",
            agent_id="agent",
            terminal_status="failed",
            failure_code_present=True,
        ),
    ]
    assert "private result" not in repr(authorized)
    assert "metadata" not in repr(authorized)
    assert "E_PRIVATE" not in repr(authorized)
    assert [call[0] for call in control.calls] == [
        "start_attempt",
        "heartbeat_lease",
        "finish_attempt",
    ]
    assert control.calls[0][1:] == (
        ("m", "t", "agent"),
        {
            "attempt_key": "a",
            "lease_seconds": 61,
            "assigned_by": "operator:alice",
            "metadata": {
                "secret": "start metadata",
                AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:alice",
            },
        },
    )
    assert control.calls[1][1:] == (
        ("m", "t", "agent"),
        {
            "attempt_id": "a",
            "lease_seconds": 62,
            "metadata": {
                "secret": "heartbeat metadata",
                AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:alice",
            },
        },
    )
    assert control.calls[2][1:] == (
        ("m", "t", "agent"),
        {
            "attempt_id": "a",
            "status": "failed",
            "result": "private result",
            "failure_code": "E_PRIVATE",
            "metadata": {
                "secret": "finish metadata",
                AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:alice",
            },
        },
    )


def test_main_runs_the_default_server_over_stdio(monkeypatch) -> None:
    transports: list[str] = []

    class _Server:
        def run(self, *, transport: str) -> None:
            transports.append(transport)

    monkeypatch.setattr(
        mission_control_mcp,
        "create_default_mission_control_mcp",
        lambda: _Server(),
    )
    mission_control_mcp.main()

    assert transports == ["stdio"]


@pytest.mark.asyncio
@_requires_mcp
async def test_real_canonical_owners_round_trip_through_fastmcp(tmp_path) -> None:
    from dharma_swarm.mission_control import MissionControl
    from dharma_swarm.runtime_state import RuntimeStateStore
    from dharma_swarm.task_board import TaskBoard

    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    board = TaskBoard(tmp_path / "tasks.db")
    await runtime.init_db()
    await board.init_db()
    server = create_mission_control_mcp(
        MissionControl(board, runtime),
        mutation_authorizer=lambda _request: True,
        trusted_principal="operator:test",
    )

    mission = _structured_result(
        await server.call_tool(
            MISSION_CREATE,
            {
                "mission_id": "m-real",
                "title": "Real mission",
                "objective": "Prove joins",
                "operator_id": "operator:spoofed",
                "metadata": {AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:spoofed"},
            },
        )
    )
    task = _structured_result(
        await server.call_tool(
            MISSION_CREATE_TASK,
            {
                "mission_id": "m-real",
                "title": "Round trip",
                "created_by": "operator:spoofed",
                "metadata": {AUTHORIZED_PRINCIPAL_METADATA_KEY: "operator:spoofed"},
            },
        )
    )
    task_id = task["data"]["task_id"]
    attempt = _structured_result(
        await server.call_tool(
            MISSION_START_ATTEMPT,
            {
                "mission_id": "m-real",
                "task_id": task_id,
                "attempt_key": "attempt-key-1",
                "agent_id": "agent-1",
            },
        )
    )
    attempt_id = attempt["data"]["attempt_id"]
    heartbeat = _structured_result(
        await server.call_tool(
            MISSION_HEARTBEAT_LEASE,
            {
                "mission_id": "m-real",
                "task_id": task_id,
                "attempt_id": attempt_id,
                "agent_id": "agent-1",
            },
        )
    )
    receipt = _structured_result(
        await server.call_tool(
            MISSION_FINISH_ATTEMPT,
            {
                "mission_id": "m-real",
                "task_id": task_id,
                "attempt_id": attempt_id,
                "agent_id": "agent-1",
                "outcome": "succeeded",
                "result": "verified",
            },
        )
    )
    snapshot = _structured_result(
        await server.call_tool(MISSION_SNAPSHOT, {"mission_id": "m-real"})
    )

    assert mission["data"]["goal"] == "Prove joins"
    assert mission["data"]["operator_id"] == "operator:test"
    assert mission["data"]["metadata"][AUTHORIZED_PRINCIPAL_METADATA_KEY] == (
        "operator:test"
    )
    stored_task = await board.get(task_id)
    assert stored_task is not None
    assert stored_task.created_by == "operator:test"
    assert stored_task.metadata[AUTHORIZED_PRINCIPAL_METADATA_KEY] == "operator:test"
    assert attempt["data"]["assigned_by"] == "operator:test"
    assert attempt["data"]["metadata"][AUTHORIZED_PRINCIPAL_METADATA_KEY] == (
        "operator:test"
    )
    assert heartbeat["data"]["attempt_id"] == attempt_id
    assert heartbeat["data"]["metadata"][AUTHORIZED_PRINCIPAL_METADATA_KEY] == (
        "operator:test"
    )
    assert receipt["data"]["status"] == "succeeded"
    receipt_principal = receipt["data"]["payload"]["metadata"][
        AUTHORIZED_PRINCIPAL_METADATA_KEY
    ]
    assert receipt_principal == "operator:test"
    assert snapshot["ok"] is True, snapshot
    assert snapshot["data"]["reconciliation"] == "coherent"
    assert snapshot["data"]["proves_executor_liveness"] is False


@pytest.mark.asyncio
@_requires_mcp
async def test_default_factory_is_read_only_and_does_not_initialize_state(
    tmp_path, monkeypatch
) -> None:
    state_dir = tmp_path / "uncreated-state"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_dir))

    server = mission_control_mcp.create_default_mission_control_mcp()
    tools = {tool.name: tool for tool in await server.list_tools()}

    reads = [
        _structured_result(
            await server.call_tool(MISSION_GET, {"mission_id": "m-missing"})
        ),
        _structured_result(
            await server.call_tool(MISSION_SNAPSHOT, {"mission_id": "m-missing"})
        ),
        _structured_result(
            await server.call_tool(
                MISSION_LIST_TASKS,
                {"mission_id": "m-missing"},
            )
        ),
    ]

    assert set(tools) == set(TOOL_NAMES)
    assert {result["error"]["code"] for result in reads} == {"state_not_initialized"}
    assert not state_dir.exists()


@pytest.mark.asyncio
@_requires_mcp
async def test_default_reads_do_not_create_absent_databases_in_existing_root(
    tmp_path, monkeypatch
) -> None:
    state_dir = tmp_path / "existing-state"
    state_dir.mkdir()
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_dir))
    server = mission_control_mcp.create_default_mission_control_mcp()

    for tool_name, arguments in (
        (MISSION_GET, {"mission_id": "m-missing"}),
        (MISSION_SNAPSHOT, {"mission_id": "m-missing"}),
        (MISSION_LIST_TASKS, {"mission_id": "m-missing"}),
    ):
        result = _structured_result(await server.call_tool(tool_name, arguments))
        assert result["error"]["code"] == "state_not_initialized"

    assert list(state_dir.iterdir()) == []


@pytest.mark.asyncio
@_requires_mcp
async def test_default_reads_do_not_mutate_existing_database_tree_or_wal(
    tmp_path, monkeypatch
) -> None:
    from dharma_swarm.mission_control import MissionControl
    from dharma_swarm.runtime_state import RuntimeStateStore
    from dharma_swarm.task_board import TaskBoard

    state_dir = tmp_path / "canonical-state"
    task_db = state_dir / "db" / "tasks.db"
    runtime_db = state_dir / "state" / "runtime.db"
    task_db.parent.mkdir(parents=True)
    runtime_db.parent.mkdir(parents=True)
    runtime = RuntimeStateStore(runtime_db, include_memory_plane=False)
    board = TaskBoard(task_db)
    await runtime.init_db()
    await board.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission("m-checkpointed", title="Checkpointed mission")
    await control.create_task("m-checkpointed", title="Checkpointed task")

    for path in (runtime_db, task_db):
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()

    runtime_writer = sqlite3.connect(runtime_db)
    task_writer = sqlite3.connect(task_db)
    try:
        for connection in (runtime_writer, task_writer):
            assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
            connection.execute("PRAGMA wal_autocheckpoint=0")

        # This mission remains committed only in the live WAL. Immutable bundled
        # reads intentionally lag it rather than touching the canonical sidecar.
        await control.create_mission("m-wal-only", title="WAL-only mission")
        task_writer.execute("CREATE TABLE wal_only_probe (identifier TEXT PRIMARY KEY)")
        task_writer.execute("INSERT INTO wal_only_probe VALUES ('present')")
        task_writer.commit()
        assert await control.get_mission("m-wal-only") is not None

        expected_sidecars = {
            runtime_db.with_name(f"{runtime_db.name}-wal"),
            runtime_db.with_name(f"{runtime_db.name}-shm"),
            task_db.with_name(f"{task_db.name}-wal"),
            task_db.with_name(f"{task_db.name}-shm"),
        }
        assert all(path.is_file() for path in expected_sidecars)

        def fingerprint() -> dict[str, tuple[Any, ...]]:
            entries: dict[str, tuple[Any, ...]] = {}
            paths = [state_dir, *state_dir.rglob("*")]
            for path in sorted(
                paths, key=lambda item: str(item.relative_to(state_dir))
            ):
                relative = (
                    "." if path == state_dir else str(path.relative_to(state_dir))
                )
                stat = path.stat()
                if path.is_dir():
                    entries[relative] = ("directory", stat.st_mtime_ns, stat.st_mode)
                else:
                    entries[relative] = (
                        "file",
                        path.read_bytes(),
                        stat.st_mtime_ns,
                        stat.st_mode,
                    )
            return entries

        before = fingerprint()
        monkeypatch.setenv("DHARMA_STATE_DIR", str(state_dir))
        server = mission_control_mcp.create_default_mission_control_mcp()
        checkpointed = _structured_result(
            await server.call_tool(
                MISSION_GET,
                {"mission_id": "m-checkpointed"},
            )
        )
        wal_only = _structured_result(
            await server.call_tool(MISSION_GET, {"mission_id": "m-wal-only"})
        )
        snapshot = _structured_result(
            await server.call_tool(
                MISSION_SNAPSHOT,
                {"mission_id": "m-checkpointed"},
            )
        )
        tasks = _structured_result(
            await server.call_tool(
                MISSION_LIST_TASKS,
                {"mission_id": "m-checkpointed"},
            )
        )

        assert checkpointed["ok"] is True
        assert wal_only["error"]["code"] == "not_found"
        assert snapshot["ok"] is True
        assert tasks["ok"] is True
        assert fingerprint() == before
    finally:
        runtime_writer.close()
        task_writer.close()


@_requires_mcp
def test_default_factory_binds_canonical_state_paths(tmp_path, monkeypatch) -> None:
    observed: dict[str, object] = {}

    class _SnapshotControl:
        def __init__(self, *, task_db, runtime_db) -> None:
            observed["task_board"] = task_db
            observed["runtime_state"] = runtime_db

    monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(
        mission_control_mcp,
        "_ImmutableSnapshotMissionControl",
        _SnapshotControl,
    )
    mission_control_mcp.create_default_mission_control_mcp()

    assert observed == {
        "task_board": tmp_path / "db" / "tasks.db",
        "runtime_state": tmp_path / "state" / "runtime.db",
    }
