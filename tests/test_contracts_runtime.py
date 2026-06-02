"""Tests for dharma_swarm/contracts/runtime.py — Protocol interface contracts."""

from __future__ import annotations

from typing import Any

import pytest

from dharma_swarm.contracts.common import (
    CheckpointRecord,
    CheckpointStatus,
    ExecutionRequest,
    ExecutionResult,
    GatewayMessage,
    RunDescriptor,
    RunStatus,
)
from dharma_swarm.contracts.runtime import (
    AgentRuntime,
    CheckpointStore,
    GatewayAdapter,
    InteropAdapter,
    SandboxProvider,
)


# --- Concrete implementations for testing ---


class StubAgentRuntime:
    """Minimal implementation of AgentRuntime for contract testing."""

    def __init__(self) -> None:
        self._runs: dict[str, RunDescriptor] = {}

    async def start_run(self, run: RunDescriptor) -> RunDescriptor:
        self._runs[run.run_id] = run
        return run

    async def update_run(self, run: RunDescriptor) -> RunDescriptor:
        self._runs[run.run_id] = run
        return run

    async def get_run(self, run_id: str) -> RunDescriptor | None:
        return self._runs.get(run_id)

    async def list_runs(
        self,
        *,
        session_id: str | None = None,
        task_id: str | None = None,
        limit: int = 50,
    ) -> list[RunDescriptor]:
        results = list(self._runs.values())
        if session_id:
            results = [r for r in results if r.session_id == session_id]
        if task_id:
            results = [r for r in results if r.task_id == task_id]
        return results[:limit]


class StubGatewayAdapter:
    """Minimal implementation of GatewayAdapter for contract testing."""

    def __init__(self) -> None:
        self._messages: list[GatewayMessage] = []
        self._acknowledged: set[str] = set()

    async def send_message(self, message: GatewayMessage) -> str:
        self._messages.append(message)
        return message.message_id

    async def receive_messages(
        self,
        *,
        recipient: str,
        channel: str | None = None,
        limit: int = 50,
    ) -> list[GatewayMessage]:
        results = [m for m in self._messages if m.recipient == recipient]
        if channel:
            results = [m for m in results if m.channel == channel]
        return results[:limit]

    async def acknowledge_delivery(
        self,
        *,
        message_id: str,
        acknowledged_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._acknowledged.add(message_id)

    async def list_channels(self) -> list[str]:
        return list(set(m.channel for m in self._messages))


class StubCheckpointStore:
    """Minimal implementation of CheckpointStore for contract testing."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, CheckpointRecord] = {}

    async def save_checkpoint(self, checkpoint: CheckpointRecord) -> CheckpointRecord:
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        return checkpoint

    async def get_checkpoint(self, checkpoint_id: str) -> CheckpointRecord | None:
        return self._checkpoints.get(checkpoint_id)

    async def list_checkpoints(
        self,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        limit: int = 50,
    ) -> list[CheckpointRecord]:
        results = list(self._checkpoints.values())
        return results[:limit]

    async def resolve_checkpoint(
        self,
        *,
        checkpoint_id: str,
        status: str,
        resolved_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> CheckpointRecord:
        cp = self._checkpoints[checkpoint_id]
        # Return a new record with updated status
        resolved = CheckpointRecord(
            checkpoint_id=cp.checkpoint_id,
            session_id=cp.session_id,
            run_id=cp.run_id,
            status=CheckpointStatus(status),
            metadata=metadata or {},
        )
        self._checkpoints[checkpoint_id] = resolved
        return resolved


class StubSandboxProvider:
    """Minimal implementation of SandboxProvider for contract testing."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            exit_code=0,
            stdout=f"executed: {request.command}",
            stderr="",
        )

    async def describe_capabilities(self) -> dict[str, Any]:
        return {"max_timeout_seconds": 300, "sandboxed": True}


class StubInteropAdapter:
    """Minimal implementation of InteropAdapter for contract testing."""

    async def export_snapshot(self, *, format_name: str) -> dict[str, Any]:
        return {"format": format_name, "data": {}}

    async def import_snapshot(self, payload: dict[str, Any], *, source: str) -> dict[str, Any]:
        return {"imported_from": source, "records": 0}


# --- Protocol conformance tests ---


def test_agent_runtime_protocol_conformance() -> None:
    """StubAgentRuntime satisfies the AgentRuntime Protocol."""
    runtime = StubAgentRuntime()
    assert isinstance(runtime, AgentRuntime)


def test_gateway_adapter_protocol_conformance() -> None:
    """StubGatewayAdapter satisfies the GatewayAdapter Protocol."""
    adapter = StubGatewayAdapter()
    assert isinstance(adapter, GatewayAdapter)


def test_checkpoint_store_protocol_conformance() -> None:
    """StubCheckpointStore satisfies the CheckpointStore Protocol."""
    store = StubCheckpointStore()
    assert isinstance(store, CheckpointStore)


def test_sandbox_provider_protocol_conformance() -> None:
    """StubSandboxProvider satisfies the SandboxProvider Protocol."""
    provider = StubSandboxProvider()
    assert isinstance(provider, SandboxProvider)


def test_interop_adapter_protocol_conformance() -> None:
    """StubInteropAdapter satisfies the InteropAdapter Protocol."""
    adapter = StubInteropAdapter()
    assert isinstance(adapter, InteropAdapter)


# --- Behavioral tests ---


@pytest.mark.asyncio
async def test_agent_runtime_crud_lifecycle() -> None:
    """AgentRuntime: start, get, update, list runs."""
    runtime = StubAgentRuntime()

    run = RunDescriptor(run_id="run-001", session_id="sess-1", task_id="task-1")
    started = await runtime.start_run(run)
    assert started.run_id == "run-001"

    fetched = await runtime.get_run("run-001")
    assert fetched is not None
    assert fetched.session_id == "sess-1"

    updated = RunDescriptor(
        run_id="run-001", session_id="sess-1", task_id="task-1", status=RunStatus.COMPLETED
    )
    result = await runtime.update_run(updated)
    assert result.status == RunStatus.COMPLETED

    runs = await runtime.list_runs(session_id="sess-1")
    assert len(runs) == 1

    assert await runtime.get_run("nonexistent") is None


@pytest.mark.asyncio
async def test_gateway_adapter_send_receive_ack() -> None:
    """GatewayAdapter: send, receive, acknowledge, list channels."""
    gw = StubGatewayAdapter()

    msg = GatewayMessage(
        message_id="msg-001",
        channel="fleet",
        sender="devin",
        recipient="mike",
        body="PR #332 ready",
    )
    msg_id = await gw.send_message(msg)
    assert msg_id == "msg-001"

    received = await gw.receive_messages(recipient="mike")
    assert len(received) == 1
    assert received[0].body == "PR #332 ready"

    await gw.acknowledge_delivery(message_id="msg-001", acknowledged_by="mike")

    channels = await gw.list_channels()
    assert "fleet" in channels


@pytest.mark.asyncio
async def test_checkpoint_store_save_resolve() -> None:
    """CheckpointStore: save, get, list, resolve."""
    store = StubCheckpointStore()

    cp = CheckpointRecord(
        checkpoint_id="cp-001",
        session_id="sess-1",
        run_id="run-001",
        status=CheckpointStatus.DRAFT,
    )
    saved = await store.save_checkpoint(cp)
    assert saved.checkpoint_id == "cp-001"

    fetched = await store.get_checkpoint("cp-001")
    assert fetched is not None
    assert fetched.status == CheckpointStatus.DRAFT

    resolved = await store.resolve_checkpoint(
        checkpoint_id="cp-001", status="approved", resolved_by="operator"
    )
    assert resolved.status == CheckpointStatus.APPROVED

    all_cps = await store.list_checkpoints()
    assert len(all_cps) == 1


@pytest.mark.asyncio
async def test_sandbox_provider_execute() -> None:
    """SandboxProvider: execute and describe capabilities."""
    sandbox = StubSandboxProvider()

    request = ExecutionRequest(command="echo hello")
    result = await sandbox.execute(request)
    assert result.exit_code == 0
    assert "echo hello" in result.stdout

    caps = await sandbox.describe_capabilities()
    assert "max_timeout_seconds" in caps


@pytest.mark.asyncio
async def test_interop_adapter_export_import() -> None:
    """InteropAdapter: export and import snapshots."""
    adapter = StubInteropAdapter()

    exported = await adapter.export_snapshot(format_name="json-v1")
    assert exported["format"] == "json-v1"

    imported = await adapter.import_snapshot({"records": []}, source="external-system")
    assert imported["imported_from"] == "external-system"
