"""Tests for dharma_swarm.orchestrator."""

import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from dharma_swarm.models import (
    AgentRole,
    AgentState,
    AgentStatus,
    GateCheckResult,
    GateDecision,
    Message,
    Task,
    TaskDispatch,
    TaskStatus,
    TopologyType,
)
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.runtime_state import RuntimeStateStore


class MockTaskBoard:
    def __init__(self):
        self.tasks = []
        self.updates = []

    async def get_ready_tasks(self):
        return [t for t in self.tasks if t.status.value == "pending"]

    async def update_task(self, task_id, **fields):
        self.updates.append((task_id, fields))
        for task in self.tasks:
            if task.id != task_id:
                continue
            if "status" in fields:
                task.status = fields["status"]
            if "assigned_to" in fields:
                task.assigned_to = fields["assigned_to"]
            if "result" in fields:
                task.result = fields["result"]
            if "metadata" in fields and isinstance(fields["metadata"], dict):
                task.metadata = dict(fields["metadata"])
            break

    async def get(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    async def list_tasks(self, status=None, limit=100):
        tasks = list(self.tasks)
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return tasks[:limit]


class MockAgentPool:
    def __init__(self, agents=None):
        self._agents = agents or []
        self._results = {}
        self._assignments = []
        self._runners = {}

    async def list_agents(self):
        return list(self._agents)

    async def get_idle_agents(self):
        return self._agents

    async def assign(self, agent_id, task_id):
        self._assignments.append((agent_id, task_id))

    async def release(self, agent_id):
        pass

    async def get_result(self, agent_id):
        return self._results.get(agent_id)

    def set_result(self, agent_id, result):
        self._results[agent_id] = result

    async def get(self, agent_id):
        return self._runners.get(agent_id)

    def set_runner(self, agent_id, runner):
        self._runners[agent_id] = runner


class MockEventMemory:
    def __init__(self):
        self.envelopes = []

    async def ingest_envelope(self, envelope):
        self.envelopes.append(envelope)


@pytest.fixture(autouse=True)
def fast_dispatch_gate():
    """Default orchestrator dispatch gates to ALLOW for non-gate tests."""
    from unittest.mock import patch

    from dharma_swarm.telos_gates import ReflectiveGateOutcome

    allow = ReflectiveGateOutcome(
        result=GateCheckResult(
            decision=GateDecision.ALLOW,
            reason="All gates passed (test mock)",
        ),
    )
    with patch(
        "dharma_swarm.orchestrator.check_with_reflective_reroute",
        return_value=allow,
    ):
        yield allow


@pytest.fixture
def agents():
    return [
        AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE),
        AgentState(id="a2", name="agent-2", role=AgentRole.CODER, status=AgentStatus.IDLE),
    ]


@pytest.fixture
def tasks():
    return [
        Task(id="t1", title="Task 1"),
        Task(id="t2", title="Task 2"),
    ]


@pytest.mark.asyncio
async def test_dispatch_fan_out(agents, tasks):
    pool = MockAgentPool(agents)
    orch = Orchestrator(agent_pool=pool)
    dispatches = await orch.dispatch(tasks[0], topology=TopologyType.FAN_OUT)
    assert len(dispatches) == 2
    assert dispatches[0].agent_id == "a1"
    assert dispatches[1].agent_id == "a2"


@pytest.mark.asyncio
async def test_dispatch_no_agents():
    pool = MockAgentPool([])
    orch = Orchestrator(agent_pool=pool)
    dispatches = await orch.dispatch(Task(title="test"))
    assert len(dispatches) == 0


@pytest.mark.asyncio
async def test_route_next(agents, tasks):
    board = MockTaskBoard()
    board.tasks = tasks
    pool = MockAgentPool(agents)
    orch = Orchestrator(task_board=board, agent_pool=pool)

    dispatches = await orch.route_next()
    assert len(dispatches) == 2


@pytest.mark.asyncio
async def test_route_next_limited_agents(tasks):
    board = MockTaskBoard()
    board.tasks = tasks
    pool = MockAgentPool([
        AgentState(id="a1", name="only-one", role=AgentRole.GENERAL, status=AgentStatus.IDLE),
    ])
    orch = Orchestrator(task_board=board, agent_pool=pool)

    dispatches = await orch.route_next()
    assert len(dispatches) == 1  # Only 1 agent for 2 tasks


@pytest.mark.asyncio
async def test_route_next_prefers_reviewer_for_uncertain_coordination_task():
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-review",
            title="Resolve disagreement",
            metadata={
                "coordination_claim_key": "route-policy",
                "coordination_route": "synthesis_review",
                "coordination_preferred_roles": ["reviewer", "researcher"],
            },
        )
    ]
    pool = MockAgentPool(
        [
            AgentState(
                id="a-general",
                name="agent-general",
                role=AgentRole.GENERAL,
                status=AgentStatus.IDLE,
            ),
            AgentState(
                id="a-review",
                name="agent-review",
                role=AgentRole.REVIEWER,
                status=AgentStatus.IDLE,
            ),
        ]
    )
    orch = Orchestrator(task_board=board, agent_pool=pool)

    dispatches = await orch.route_next()

    assert len(dispatches) == 1
    assert dispatches[0].agent_id == "a-review"


@pytest.mark.asyncio
async def test_route_next_prefers_director_named_agent_over_role_match():
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-cyber",
            title="Wire cybernetics lever",
            metadata={
                "director_preferred_agents": ["cyber-codex", "cyber-opus"],
                "coordination_preferred_roles": ["architect"],
            },
        )
    ]
    pool = MockAgentPool(
        [
            AgentState(
                id="a-opus-legacy",
                name="opus-primus",
                role=AgentRole.ARCHITECT,
                status=AgentStatus.IDLE,
            ),
            AgentState(
                id="a-cyber-codex",
                name="cyber-codex",
                role=AgentRole.SURGEON,
                status=AgentStatus.IDLE,
            ),
        ]
    )
    orch = Orchestrator(task_board=board, agent_pool=pool)

    dispatches = await orch.route_next()

    assert len(dispatches) == 1
    assert dispatches[0].agent_id == "a-cyber-codex"


@pytest.mark.asyncio
async def test_fan_in(agents):
    pool = MockAgentPool(agents)
    pool.set_result("a1", "result from agent 1")
    pool.set_result("a2", "result from agent 2")
    orch = Orchestrator(agent_pool=pool)

    from dharma_swarm.models import TaskDispatch
    dispatches = [
        TaskDispatch(task_id="t1", agent_id="a1"),
        TaskDispatch(task_id="t2", agent_id="a2"),
    ]
    combined = await orch.fan_in(dispatches)
    assert "result from agent 1" in combined
    assert "result from agent 2" in combined


@pytest.mark.asyncio
async def test_tick(agents, tasks):
    board = MockTaskBoard()
    board.tasks = tasks
    pool = MockAgentPool(agents)
    orch = Orchestrator(task_board=board, agent_pool=pool)

    activity = await orch.tick()
    # Should have dispatched
    assert len(pool._assignments) > 0
    assert activity["dispatched"] == 2


@pytest.mark.asyncio
async def test_tick_emits_runtime_event_with_coordination_summary(agents, tasks, monkeypatch):
    board = MockTaskBoard()
    board.tasks = [tasks[0]]
    pool = MockAgentPool([agents[0]])
    event_memory = MockEventMemory()
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        event_memory=event_memory,
        session_id="sess-tick",
    )

    async def fake_refresh():
        return {"global_truths": 3, "productive_disagreements": 1}

    monkeypatch.setattr(orch, "_refresh_coordination_state", fake_refresh)

    activity = await orch.tick()

    assert activity["dispatched"] == 1
    assert activity["coordination_global_truths"] == 3
    assert activity["coordination_disagreements"] == 1
    tick_events = [
        envelope
        for envelope in event_memory.envelopes
        if envelope.payload.get("action_name") == "tick_summary"
    ]
    assert len(tick_events) == 1
    envelope = tick_events[0]
    assert envelope.source == "orchestrator.tick"
    assert envelope.session_id == "sess-tick"
    assert envelope.payload["action_name"] == "tick_summary"
    assert envelope.payload["dispatched_count"] == 1
    assert envelope.payload["dispatched_task_ids"] == ["t1"]
    assert envelope.payload["coordination_global_truths"] == 3
    assert envelope.payload["coordination_disagreements"] == 1


@pytest.mark.asyncio
async def test_stop():
    orch = Orchestrator()
    orch._running = True
    orch.stop()
    assert not orch._running


@pytest.mark.asyncio
async def test_no_deps():
    orch = Orchestrator()
    dispatches = await orch.route_next()
    assert dispatches == []


@pytest.mark.asyncio
async def test_task_memory_palace_ingestion_gate_skips_constructor(
    tmp_path,
    monkeypatch,
):
    """A false runtime control must not enter the synchronous native constructor."""
    memory_palace_constructor = MagicMock(
        side_effect=AssertionError("disabled MemoryPalace constructor called")
    )
    monkeypatch.setenv("DGC_TASK_MEMORY_PALACE_INGESTION", "0")
    monkeypatch.setattr(
        "dharma_swarm.memory_palace.MemoryPalace",
        memory_palace_constructor,
    )
    orch = Orchestrator(
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=tmp_path / "state" / "runtime.db",
        shared_dir=tmp_path / "shared",
        stigmergy_dir=tmp_path / "stigmergy",
        session_id="memory-palace-gate",
    )
    orch._runtime_lifecycle.record_artifact = AsyncMock()

    await orch._persist_result(
        agent_name="agent-test",
        model_name="test-model",
        provider_name="test-provider",
        task=Task(id="memory-gate-task", title="Memory gate task"),
        result="constructor must stay cold",
    )

    memory_palace_constructor.assert_not_called()
    orch._runtime_lifecycle.record_artifact.assert_awaited_once()


# ---------------------------------------------------------------------------
# MockMessageBus for bus-related tests
# ---------------------------------------------------------------------------

class MockMessageBus:
    """Simple mock for the message bus duck-type contract."""

    def __init__(self):
        self.sent: list = []
        self.published: list = []
        self._messages: list[Message] = []

    async def send(self, message):
        self.sent.append(message)
        self._messages.append(message)
        return message.id

    async def publish(self, topic, message):
        self.published.append((topic, message))
        self._messages.append(message)
        return [message.id]

    async def list_messages(self, limit=200, agent_id=None):
        messages = list(self._messages)
        if agent_id:
            messages = [
                message
                for message in messages
                if message.from_agent == agent_id or message.to_agent == agent_id
            ]
        return messages[-limit:]

    def seed_message(self, message: Message) -> None:
        self._messages.append(message)


class DummyRunner:
    """Tiny runner shim to drive _execute_task paths in tests."""

    def __init__(
        self,
        result: str | None = None,
        error: Exception | None = None,
        delay_seconds: float = 0.0,
    ):
        self._result = result or "ok"
        self._error = error
        self._delay_seconds = delay_seconds
        self._config = None

    async def run_task(self, task):
        if self._delay_seconds > 0:
            await asyncio.sleep(self._delay_seconds)
        if self._error:
            raise self._error
        return self._result


async def _drain_running_tasks(orch: Orchestrator, *, attempts: int = 500) -> None:
    for _ in range(attempts):
        if not orch._running_tasks:
            break
        await orch._collect_completed()
        await asyncio.sleep(0.01)
    await orch._collect_completed()


def _ledger_event_names(path):
    if not path.exists():
        return []
    return [
        json.loads(line)["event"]
        for line in path.read_text().splitlines()
        if line.strip()
    ]


async def _drain_until_task_ledger_event(
    orch,
    task_path,
    progress_path,
    expected_event,
    *,
    attempts=100,
    delay_seconds=0.01,
):
    terminal_progress_events = {
        "result_persist_failed",
        "task_blocked",
        "task_failed",
        "task_retry_scheduled",
        "task_dead_lettered",
    }
    task_events = []
    progress_events = []
    for _ in range(attempts):
        await orch._collect_completed()
        task_events = _ledger_event_names(task_path)
        progress_events = _ledger_event_names(progress_path)
        if expected_event in task_events:
            break
        if terminal_progress_events.intersection(progress_events):
            break
        await asyncio.sleep(delay_seconds)

    await orch._collect_completed()
    return _ledger_event_names(task_path), _ledger_event_names(progress_path)


# ---------------------------------------------------------------------------
# New tests — coverage expansion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_swarm_handoff_persists_restartable_topology_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")
    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "0")
    runtime_db = tmp_path / "runtime.db"
    board = MockTaskBoard()
    task = Task(
        id="t-swarm-handoff",
        title="Swarm handoff",
        description="safe",
        metadata={
            "active_agent": "a1",
            "allowed_handoffs": {"a1": ["a2"]},
            "handoff_to_agent": "a2",
            "handoff_reason": "specialist handoff",
        },
    )
    board.tasks = [task]
    pool = MockAgentPool(
        [
            AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL),
            AgentState(id="a2", name="agent-2", role=AgentRole.CODER),
        ]
    )
    pool.set_runner("a2", DummyRunner(result="handoff ok"))
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=runtime_db,
        session_id="sess_swarm_handoff",
    )

    dispatches = await orch.dispatch(task, topology=TopologyType.SWARM)
    await _drain_running_tasks(orch)

    assert dispatches[0].agent_id == "a2"
    restarted = RuntimeStateStore(runtime_db, include_memory_plane=False)
    latest = await restarted.get_latest_topology_state_for_task("t-swarm-handoff")
    assert latest is not None
    loaded = await restarted.get_topology_state(latest.run_id)
    assert loaded is not None
    assert loaded.topology == "swarm"
    assert loaded.active_agent == "a2"
    assert loaded.handoff_receipts[0]["status"] == "accepted"
    assert loaded.handoff_receipts[0]["from_agent"] == "a1"
    assert loaded.allowed_handoffs["a1"] == ["a2"]

    receipts = await restarted.list_runtime_receipts(
        run_id=latest.run_id,
        receipt_type="topology_handoff",
        limit=10,
    )
    assert any(receipt.payload.get("status") == "accepted" for receipt in receipts)


@pytest.mark.asyncio
async def test_supervisor_persists_restartable_final_output_policy_and_delegated_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")
    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "0")
    runtime_db = tmp_path / "runtime.db"
    board = MockTaskBoard()
    task = Task(
        id="t-supervisor-final-output",
        title="Supervisor final output",
        description="safe",
        metadata={"active_agent": "lead"},
    )
    board.tasks = [task]
    pool = MockAgentPool(
        [
            AgentState(id="lead", name="lead", role=AgentRole.GENERAL),
            AgentState(id="child-a", name="child-a", role=AgentRole.CODER),
            AgentState(id="child-b", name="child-b", role=AgentRole.TESTER),
        ]
    )
    pool.set_runner("lead", DummyRunner(result="supervisor final answer"))
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=runtime_db,
        session_id="sess_supervisor_final_output",
    )

    dispatches = await orch.dispatch(task, topology=TopologyType.SUPERVISOR)
    await _drain_running_tasks(orch)

    supervisor_dispatch = dispatches[0]
    supervisor_run_id = str(supervisor_dispatch.metadata["runtime_run_id"])
    store = RuntimeStateStore(runtime_db, include_memory_plane=False)
    supervisor_run = await store.get_delegation_run(supervisor_run_id)
    topology_state = await store.get_topology_state(supervisor_run_id)
    detail = await store.describe_run(supervisor_run_id)

    assert supervisor_run is not None
    assert supervisor_run.assigned_to == "lead"
    assert topology_state is not None
    assert topology_state.topology == "supervisor"
    assert topology_state.active_agent == "lead"
    assert topology_state.current_node == "supervisor"
    assert topology_state.state["delegated_agent_ids"] == ["child-a", "child-b"]
    assert topology_state.state["supervisor_final_output_only"] is True
    assert topology_state.state["user_visible_output"] == "supervisor_final"
    assert detail is not None
    assert detail["topology_state"].state["supervisor_final_output_only"] is True
    assert detail["topology_state"].state["user_visible_output"] == "supervisor_final"

    receipts = await store.list_runtime_receipts(
        run_id=supervisor_run_id,
        receipt_type="topology_state",
        limit=10,
    )
    assert any(
        receipt.payload.get("topology") == "supervisor"
        and receipt.payload.get("state", {}).get("supervisor_final_output_only") is True
        for receipt in receipts
    )


@pytest.mark.asyncio
async def test_subagents_as_tools_persists_parent_and_child_runs(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")
    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "0")
    runtime_db = tmp_path / "runtime.db"
    board = MockTaskBoard()
    task = Task(
        id="t-subagent-tools",
        title="Subagents as tools",
        description="safe",
        metadata={"active_agent": "parent"},
    )
    board.tasks = [task]
    pool = MockAgentPool(
        [
            AgentState(id="parent", name="parent", role=AgentRole.GENERAL),
            AgentState(id="child-a", name="child-a", role=AgentRole.CODER),
            AgentState(id="child-b", name="child-b", role=AgentRole.TESTER),
        ]
    )
    pool.set_runner("parent", DummyRunner(result="parent ok"))
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=runtime_db,
        session_id="sess_subagent_tools",
    )

    dispatches = await orch.dispatch(task, topology=TopologyType.SUBAGENTS_AS_TOOLS)
    await _drain_running_tasks(orch)

    parent_dispatch = dispatches[0]
    parent_run_id = str(parent_dispatch.metadata["runtime_run_id"])
    child_run_ids = parent_dispatch.metadata["parent_graph_state"]["child_run_ids"]
    assert len(child_run_ids) == 2

    store = RuntimeStateStore(runtime_db, include_memory_plane=False)
    parent_run = await store.get_delegation_run(parent_run_id)
    children = await store.list_child_runs(parent_run_id)
    topology_state = await store.get_topology_state(parent_run_id)

    assert parent_run is not None
    assert parent_run.assigned_to == "parent"
    assert {child.run_id for child in children} == set(child_run_ids)
    assert {child.parent_run_id for child in children} == {parent_run_id}
    assert {child.assigned_to for child in children} == {"child-a", "child-b"}
    assert topology_state is not None
    assert topology_state.child_run_ids == child_run_ids

    receipts = await store.list_runtime_receipts(
        run_id=parent_run_id,
        receipt_type="child_spawned",
        limit=10,
    )
    assert {receipt.payload["child_run_id"] for receipt in receipts} >= set(child_run_ids)

@pytest.mark.asyncio
async def test_dispatch_pipeline_assigns_first_idle_only(agents, tasks):
    """PIPELINE topology should assign the task to exactly the first idle agent."""
    pool = MockAgentPool(agents)
    orch = Orchestrator(agent_pool=pool)

    dispatches = await orch.dispatch(tasks[0], topology=TopologyType.PIPELINE)

    assert len(dispatches) == 1
    assert dispatches[0].agent_id == "a1"
    assert dispatches[0].topology == TopologyType.PIPELINE
    # Only one assignment should have been made
    assert len(pool._assignments) == 1
    assert pool._assignments[0] == ("a1", "t1")


@pytest.mark.asyncio
async def test_dispatch_no_pool_returns_empty(tasks):
    """dispatch with pool=None should return an empty list immediately."""
    orch = Orchestrator(agent_pool=None)
    dispatches = await orch.dispatch(tasks[0])
    assert dispatches == []


@pytest.mark.asyncio
async def test_fan_in_no_pool_returns_empty():
    """fan_in with pool=None should return an empty string."""
    from dharma_swarm.models import TaskDispatch

    orch = Orchestrator(agent_pool=None)
    dispatches = [
        TaskDispatch(task_id="t1", agent_id="a1"),
        TaskDispatch(task_id="t2", agent_id="a2"),
    ]
    result = await orch.fan_in(dispatches)
    assert result == ""


@pytest.mark.asyncio
async def test_fan_in_skips_none_results(agents):
    """fan_in should collect only non-None results, skipping agents that returned None."""
    from dharma_swarm.models import TaskDispatch

    pool = MockAgentPool(agents)
    pool.set_result("a1", "good result")
    # a2 has no result set -> get_result returns None
    orch = Orchestrator(agent_pool=pool)

    dispatches = [
        TaskDispatch(task_id="t1", agent_id="a1"),
        TaskDispatch(task_id="t2", agent_id="a2"),
    ]
    combined = await orch.fan_in(dispatches)

    assert "good result" in combined
    # The combined string should NOT contain "None" as a literal
    assert "None" not in combined
    # Only one fragment was collected
    assert combined == "good result"


@pytest.mark.asyncio
async def test_collect_completed_cleans_done_tasks():
    """_collect_completed should remove finished asyncio tasks from _running_tasks."""
    import asyncio

    orch = Orchestrator()

    # Create a coroutine that completes immediately
    async def _noop():
        return "done"

    done_task = asyncio.create_task(_noop())
    # Allow the task to finish
    await done_task

    orch._running_tasks["task-done"] = done_task
    # Also add a still-pending task to verify it is NOT removed
    pending_future: asyncio.Future = asyncio.get_event_loop().create_future()
    orch._running_tasks["task-pending"] = pending_future  # type: ignore[assignment]

    await orch._collect_completed()

    assert "task-done" not in orch._running_tasks
    assert "task-pending" in orch._running_tasks

    # Clean up the pending future so asyncio doesn't complain
    pending_future.cancel()


@pytest.mark.asyncio
async def test_assign_dispatch_calls_message_bus(agents, tasks):
    """_assign_dispatch should call bus.send when a message_bus is provided."""
    from dharma_swarm.models import TaskDispatch

    pool = MockAgentPool(agents)
    board = MockTaskBoard()
    bus = MockMessageBus()
    orch = Orchestrator(task_board=board, agent_pool=pool, message_bus=bus)

    td = TaskDispatch(task_id="t1", agent_id="a1")
    await orch._assign_dispatch(td)

    assert len(bus.sent) == 1
    msg = bus.sent[0]
    assert msg.from_agent == "orchestrator"
    assert msg.to_agent == "a1"
    assert "t1" in msg.subject
    assert "t1" in msg.body


@pytest.mark.asyncio
async def test_route_next_skips_running_tasks(agents, tasks):
    """route_next should skip tasks whose IDs are already in _running_tasks."""
    import asyncio

    board = MockTaskBoard()
    board.tasks = tasks  # t1 and t2 both pending
    pool = MockAgentPool(agents)
    orch = Orchestrator(task_board=board, agent_pool=pool)

    # Simulate t1 already running by placing a dummy task in _running_tasks
    pending_future: asyncio.Future = asyncio.get_event_loop().create_future()
    orch._running_tasks["t1"] = pending_future  # type: ignore[assignment]

    dispatches = await orch.route_next()

    # Only t2 should have been dispatched (t1 is already running)
    assert len(dispatches) == 1
    assert dispatches[0].task_id == "t2"
    assert dispatches[0].agent_id == "a1"

    # Clean up
    pending_future.cancel()


@pytest.mark.asyncio
async def test_assign_dispatch_telos_block_marks_failed_and_skips_assignment(agents, monkeypatch):
    """Harmful dispatch should fail fast before pool assignment."""
    from dharma_swarm.models import TaskDispatch
    from dharma_swarm.telos_gates import ReflectiveGateOutcome

    monkeypatch.setattr(
        "dharma_swarm.orchestrator.check_with_reflective_reroute",
        lambda **_: ReflectiveGateOutcome(
            result=GateCheckResult(
                decision=GateDecision.BLOCK,
                reason="Mock telos block",
            ),
        ),
        raising=True,
    )

    board = MockTaskBoard()
    board.tasks = [
        Task(id="harm1", title="rm -rf /important", description="delete all"),
    ]
    pool = MockAgentPool(agents)
    orch = Orchestrator(task_board=board, agent_pool=pool)

    td = TaskDispatch(task_id="harm1", agent_id="a1")
    await orch._assign_dispatch(td)

    assert pool._assignments == []
    assert any(
        task_id == "harm1"
        and fields.get("status") == TaskStatus.FAILED
        and "TELOS BLOCK (dispatch)" in str(fields.get("result", ""))
        for task_id, fields in board.updates
    )


@pytest.mark.asyncio
async def test_attach_context_bundle_exposes_memory_kernel_metadata(
    tmp_path,
    monkeypatch,
):
    from dharma_swarm.runtime_state import ContextBundleRecord

    class FakeMemoryLattice:
        def __init__(self, **_kwargs):
            pass

        async def close(self):
            pass

    class FakeContextCompiler:
        def __init__(self, **kwargs):
            assert kwargs.get("memory_kernel") is not None

        async def compile_bundle(self, **kwargs):
            assert kwargs["metadata"]["agent_id"] == "a1"
            assert kwargs["metadata"]["topology"] == "swarm"
            return ContextBundleRecord(
                bundle_id="bnd_memory_kernel",
                session_id=kwargs["session_id"],
                task_id=kwargs["task_id"],
                run_id=kwargs["run_id"],
                token_budget=kwargs["token_budget"],
                rendered_text="# DGC Context Bundle\n\n## Memory Kernel\nused",
                sections=[{"name": "Memory Kernel"}],
                source_refs=["memory_kernel:home.witness"],
                checksum="checksum",
                created_at=datetime.now(timezone.utc),
                metadata={
                    "memory_kernel_default": {
                        "status": "used",
                        "pack_id": "memory_context_pack:test",
                        "admitted_count": 1,
                        "omitted_count": 2,
                        "warnings": ["preview_only_no_runtime_prompt_injection"],
                        "isolation_applied": True,
                        "isolation_agent_id": "a1",
                        "allowed_agent_ids": ["a1"],
                        "allowed_scopes": ["project", "agent", "swarm"],
                        "allowed_memory_lanes": ["provenance", "semantic"],
                    }
                },
            )

    monkeypatch.setattr(
        "dharma_swarm.memory_lattice.MemoryLattice",
        FakeMemoryLattice,
    )
    monkeypatch.setattr(
        "dharma_swarm.memory_kernel.MemoryKernel",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        "dharma_swarm.context_compiler.ContextCompiler",
        FakeContextCompiler,
    )

    board = MockTaskBoard()
    task = Task(id="t-memory-kernel", title="Memory task", description="safe")
    board.tasks = [task]
    orch = Orchestrator(
        task_board=board,
        agent_pool=MockAgentPool(),
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=tmp_path / "runtime.db",
    )
    td = TaskDispatch(task_id=task.id, agent_id="a1", topology=TopologyType.SWARM)

    meta = await orch._attach_context_bundle(task, td, {})

    assert meta["context_bundle_status"] == "attached"
    assert meta["memory_kernel_status"] == "used"
    assert meta["memory_kernel_pack_id"] == "memory_context_pack:test"
    assert meta["memory_kernel_admitted_count"] == 1
    assert meta["memory_kernel_omitted_count"] == 2
    assert meta["memory_kernel_isolation_applied"] is True
    assert meta["memory_kernel_isolation_agent_id"] == "a1"
    assert meta["memory_kernel_allowed_agent_ids"] == ["a1"]
    assert meta["memory_kernel_allowed_scopes"] == ["project", "agent", "swarm"]
    assert meta["memory_kernel_allowed_memory_lanes"] == ["provenance", "semantic"]
    assert td.metadata["memory_kernel_status"] == "used"
    assert td.metadata["memory_kernel_isolation_applied"] is True


@pytest.mark.asyncio
async def test_orchestrator_writes_task_and_progress_ledgers(tmp_path):
    """Successful execution should write both task and progress ledgers."""
    board = MockTaskBoard()
    board.tasks = [Task(id="t-ledger", title="Ledger task", description="safe")]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner("a1", DummyRunner(result="ledger ok"))
    bus = MockMessageBus()

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        message_bus=bus,
        ledger_dir=tmp_path,
        session_id="sess_test",
    )

    task_path = tmp_path / "sess_test" / "task_ledger.jsonl"
    progress_path = tmp_path / "sess_test" / "progress_ledger.jsonl"
    dispatches = await orch.route_next()
    assert len(dispatches) == 1

    task_events, progress_events = await _drain_until_task_ledger_event(
        orch,
        task_path,
        progress_path,
        "result_persisted",
    )

    assert task_path.exists()
    assert progress_path.exists()

    assert "dispatch_assigned" in task_events
    assert "result_persisted" in task_events, {
        "task_events": task_events,
        "progress_events": progress_events,
    }
    assert "task_started" in progress_events
    assert "task_completed" in progress_events
    assert any(topic == "orchestrator.lifecycle" for topic, _ in bus.published)


@pytest.mark.asyncio
async def test_orchestrator_spine_dispatch_is_default_and_persists_receipt(
    tmp_path, monkeypatch
):
    """Unset DHARMA_SPINE_DISPATCH should use invoke_agent, not legacy direct."""
    import sqlite3

    monkeypatch.delenv("DHARMA_SPINE_DISPATCH", raising=False)
    board = MockTaskBoard()
    board.tasks = [Task(id="t-spine-default", title="Spine default", description="safe")]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner("a1", DummyRunner(result="spine ok"))
    runtime_db = tmp_path / "runtime.db"
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=runtime_db,
        session_id="sess_spine_default",
    )

    await orch.route_next()
    await _drain_running_tasks(orch)

    receipt = orch._last_evidence_receipt
    assert receipt.operation == "invoke_agent"
    assert receipt.task_id == "t-spine-default"
    assert receipt.status == "ok"

    with sqlite3.connect(runtime_db) as db:
        row = db.execute(
            "SELECT receipt_json FROM delegation_runs WHERE task_id = ?",
            ("t-spine-default",),
        ).fetchone()

    assert row is not None and row[0]
    persisted = json.loads(row[0])
    assert persisted["operation"] == "invoke_agent"
    assert persisted["receipt_id"] == str(receipt.receipt_id)
    assert persisted["attributes"]["topology"] == "fan_out"
    assert persisted["attributes"]["run_id"]
    assert persisted["attributes"]["idempotency_key"]
    assert persisted["attributes"]["side_effect_key"] == "invoke_agent:t-spine-default:a1"


def test_orchestrator_spine_dispatch_false_like_env_values_opt_out(monkeypatch):
    monkeypatch.delenv("DHARMA_SPINE_DISPATCH", raising=False)
    assert Orchestrator._spine_dispatch_enabled() is True

    for value in ("0", "false", "False", "off", "legacy", "direct"):
        monkeypatch.setenv("DHARMA_SPINE_DISPATCH", value)
        assert Orchestrator._spine_dispatch_enabled() is False

    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "1")
    assert Orchestrator._spine_dispatch_enabled() is True


@pytest.mark.asyncio
async def test_orchestrator_fail_closes_when_honors_checkpoint_missing(tmp_path):
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-honors-missing",
            title="Defended analysis",
            description="safe",
            metadata={
                "max_retries": 0,
                "completion_contract": {
                    "mode": "honors",
                    "minimum_file_references": 1,
                },
            },
        )
    ]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner("a1", DummyRunner(result="Looks polished but carried no checkpoint packet."))

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_honors_missing",
    )

    await orch.route_next()
    await _drain_running_tasks(orch)

    assert any(
        task_id == "t-honors-missing"
        and fields.get("status") == TaskStatus.FAILED
        and "honors checkpoint" in str(fields.get("result", "")).lower()
        for task_id, fields in board.updates
    )


@pytest.mark.asyncio
async def test_orchestrator_failure_records_signature(tmp_path):
    """Failure path should emit a normalized failure signature in progress ledger."""
    board = MockTaskBoard()
    board.tasks = [Task(id="t-fail", title="Fail task", description="safe")]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner(
        "a1",
        DummyRunner(
            error=RuntimeError(
                "Timeout while reading provider stream 1234567890abcdef"
            )
        ),
    )

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_fail",
    )

    await orch.route_next()
    await _drain_running_tasks(orch)

    progress_path = tmp_path / "sess_fail" / "progress_ledger.jsonl"
    assert progress_path.exists()
    rows = [json.loads(line) for line in progress_path.read_text().splitlines() if line.strip()]
    failed = [
        r
        for r in rows
        if r.get("event") in {"task_failed", "task_retry_scheduled"}
    ]
    assert failed, "Expected failure or retry event in progress ledger"
    sig = failed[0].get("failure_signature", "")
    assert "timeout while reading provider stream" in sig
    assert "<id>" in sig


@pytest.mark.asyncio
async def test_orchestrator_failure_progress_precedes_runtime_lifecycle(tmp_path, monkeypatch):
    """Failure progress receipts should not wait on runtime-state persistence."""
    board = MockTaskBoard()
    board.tasks = [Task(id="t-fail-fast-ledger", title="Fail task", description="safe")]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner(
        "a1",
        DummyRunner(
            error=RuntimeError(
                "Timeout while reading provider stream 1234567890abcdef"
            )
        ),
    )

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_fail_fast_ledger",
    )
    runtime_block = asyncio.Event()
    runtime_write_started = asyncio.Event()

    async def blocked_runtime_write(*_args, **kwargs):
        if kwargs.get("status") != "failed":
            return
        runtime_write_started.set()
        await runtime_block.wait()

    monkeypatch.setattr(
        orch._runtime_lifecycle,
        "record_task_claim",
        blocked_runtime_write,
    )
    monkeypatch.setattr(
        orch._runtime_lifecycle,
        "record_delegation_run",
        blocked_runtime_write,
    )

    await orch.route_next()
    progress_path = tmp_path / "sess_fail_fast_ledger" / "progress_ledger.jsonl"

    try:
        found = False
        for _ in range(100):
            await orch._collect_completed()
            if progress_path.exists():
                rows = [
                    json.loads(line)
                    for line in progress_path.read_text().splitlines()
                    if line.strip()
                ]
                found = any(
                    r.get("event") in {"task_failed", "task_retry_scheduled"}
                    for r in rows
                )
                if found:
                    break
            await asyncio.sleep(0.01)

        assert found, "Expected failure or retry event before runtime lifecycle finishes"
        assert orch._running_tasks
        assert runtime_write_started.is_set()
    finally:
        runtime_block.set()
        for _ in range(100):
            await orch._collect_completed()
            if not orch._running_tasks:
                break
            await asyncio.sleep(0.01)
        await orch._collect_completed()


@pytest.mark.asyncio
async def test_orchestrator_timeout_marks_failed_without_retry(tmp_path):
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-timeout",
            title="Slow task",
            description="safe",
            metadata={"timeout_seconds": 0.01, "max_retries": 0},
        )
    ]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner("a1", DummyRunner(result="late", delay_seconds=0.05))

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_timeout",
    )

    await orch.route_next()
    await _drain_running_tasks(orch)

    assert any(
        task_id == "t-timeout"
        and fields.get("status") == TaskStatus.FAILED
        and "timed out" in str(fields.get("result", "")).lower()
        for task_id, fields in board.updates
    )


@pytest.mark.asyncio
async def test_orchestrator_timeout_requeues_with_retry_budget(tmp_path):
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-timeout-retry",
            title="Slow retriable task",
            description="safe",
            metadata={"timeout_seconds": 0.01, "max_retries": 1},
        )
    ]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner("a1", DummyRunner(result="late", delay_seconds=0.05))

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_timeout_retry",
    )

    await orch.route_next()
    await _drain_running_tasks(orch)

    failed_seen = any(
        task_id == "t-timeout-retry" and fields.get("status") == TaskStatus.FAILED
        for task_id, fields in board.updates
    )
    pending_seen = any(
        task_id == "t-timeout-retry" and fields.get("status") == TaskStatus.PENDING
        for task_id, fields in board.updates
    )
    assert failed_seen
    assert pending_seen


@pytest.mark.asyncio
async def test_orchestrator_connection_error_auto_requeues_transient_failure(tmp_path):
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-conn-retry",
            title="Transient provider failure",
            description="safe",
        )
    ]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner("a1", DummyRunner(error=RuntimeError("Connection error.")))

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_conn_retry",
    )

    await orch.route_next()
    await _drain_running_tasks(orch)

    assert any(
        task_id == "t-conn-retry" and fields.get("status") == TaskStatus.PENDING
        for task_id, fields in board.updates
    )
    task = await board.get("t-conn-retry")
    assert task is not None
    assert task.metadata["retry_count"] == 1
    assert task.metadata["max_retries"] >= 2
    assert task.metadata["last_failure_class"] == "connection_transient"
    assert task.metadata["retry_backoff_seconds"] >= 30.0


@pytest.mark.asyncio
async def test_orchestrator_long_timeout_auto_requeues_and_expands_timeout(tmp_path):
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-long-timeout",
            title="Long timeout task",
            description="safe",
            metadata={"timeout_seconds": 0.01},
        )
    ]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    pool.set_runner("a1", DummyRunner(result="late", delay_seconds=0.05))

    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_long_timeout_retry",
    )
    orch._long_timeout_retry_threshold_seconds = 0.0

    await orch.route_next()
    await _drain_running_tasks(orch)

    assert any(
        task_id == "t-long-timeout" and fields.get("status") == TaskStatus.PENDING
        for task_id, fields in board.updates
    )
    task = await board.get("t-long-timeout")
    assert task is not None
    assert task.metadata["retry_count"] == 1
    assert task.metadata["max_retries"] >= 1
    assert task.metadata["last_failure_class"] == "long_timeout"
    assert float(task.metadata["timeout_seconds"]) > 0.01
    assert task.metadata["retry_backoff_seconds"] >= 15.0


@pytest.mark.asyncio
async def test_orchestrator_coordination_summary_detects_global_truth(tmp_path):
    agents = [
        AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE),
        AgentState(id="a2", name="agent-2", role=AgentRole.RESEARCHER, status=AgentStatus.IDLE),
    ]
    board = MockTaskBoard()
    pool = MockAgentPool(agents)
    bus = MockMessageBus()
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        message_bus=bus,
        ledger_dir=tmp_path,
        session_id="sess_coord_truth",
    )
    bus.seed_message(
        Message(
            id="m1",
            from_agent="a1",
            to_agent="a2",
            subject="route-policy",
            body="Mechanism, witness, ecosystem all agree.",
            metadata={"topic": "route-policy"},
        )
    )
    bus.seed_message(
        Message(
            id="m2",
            from_agent="a2",
            to_agent="a1",
            subject="route-policy",
            body="Mechanism, witness, ecosystem all agree.",
            metadata={"topic": "route-policy"},
        )
    )

    summary = await orch.get_coordination_summary(refresh=True)

    assert summary["agent_count"] == 2
    assert summary["message_count"] == 2
    assert summary["global_truths"] == 1
    assert summary["productive_disagreements"] == 0
    assert summary["is_globally_coherent"] is True
    assert summary["global_truth_claim_keys"] == ["route-policy"]

    progress_path = tmp_path / "sess_coord_truth" / "progress_ledger.jsonl"
    rows = [json.loads(line) for line in progress_path.read_text().splitlines() if line.strip()]
    assert any(row.get("event") == "coordination_snapshot" for row in rows)


@pytest.mark.asyncio
async def test_orchestrator_coordination_summary_detects_productive_disagreement(tmp_path):
    agents = [
        AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE),
        AgentState(id="a2", name="agent-2", role=AgentRole.RESEARCHER, status=AgentStatus.IDLE),
    ]
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-route",
            title="route-policy",
            assigned_to="a1",
            status=TaskStatus.ASSIGNED,
            metadata={"coordination_claim_key": "route-policy"},
        )
    ]
    pool = MockAgentPool(agents)
    bus = MockMessageBus()
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        message_bus=bus,
        ledger_dir=tmp_path,
        session_id="sess_coord_conflict",
    )
    bus.seed_message(
        Message(
            id="m1",
            from_agent="a1",
            to_agent="a2",
            subject="route-policy",
            body="Mechanism and architecture dominate this route.",
            metadata={"topic": "route-policy"},
        )
    )
    bus.seed_message(
        Message(
            id="m2",
            from_agent="a2",
            to_agent="a1",
            subject="route-policy",
            body="Witness awareness and introspection dominate this route.",
            metadata={"topic": "route-policy"},
        )
    )

    summary = await orch.get_coordination_summary(refresh=True)

    assert summary["global_truths"] == 0
    assert summary["productive_disagreements"] == 1
    assert summary["is_globally_coherent"] is False
    assert summary["productive_disagreement_claim_keys"] == ["route-policy"]
    updated = await board.get("t-route")
    assert updated is not None
    assert updated.metadata["coordination_state"] == "uncertain"
    assert updated.metadata["coordination_review_required"] is True
    assert updated.metadata["coordination_route"] == "synthesis_review"

    progress_path = tmp_path / "sess_coord_conflict" / "progress_ledger.jsonl"
    rows = [json.loads(line) for line in progress_path.read_text().splitlines() if line.strip()]
    assert any(row.get("event") == "coordination_disagreement" for row in rows)


@pytest.mark.asyncio
async def test_route_next_skips_retry_backoff_tasks(agents):
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-backoff",
            title="Wait",
            metadata={"retry_not_before_epoch": time.time() + 60},
        ),
        Task(id="t-ready", title="Ready now"),
    ]
    pool = MockAgentPool(agents[:1])
    orch = Orchestrator(task_board=board, agent_pool=pool)

    dispatches = await orch.route_next()
    assert len(dispatches) == 1
    assert dispatches[0].task_id == "t-ready"


@pytest.mark.asyncio
async def test_dispatch_dropoff_requeues_once_when_runner_missing(tmp_path):
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-dropoff",
            title="No runner",
            metadata={"max_retries": 1},
        )
    ]
    pool = MockAgentPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_dropoff",
    )

    await orch.route_next()
    await orch._collect_completed()

    assert any(
        task_id == "t-dropoff" and fields.get("status") == TaskStatus.PENDING
        for task_id, fields in board.updates
    )


def test_prepare_claim_uses_explicit_room_metadata() -> None:
    orch = Orchestrator(agent_pool=None, task_board=None)
    task = Task(
        id="t-room",
        title="Room scoped",
        metadata={"source_room_id": "revenue-wedge"},
    )
    dispatch = TaskDispatch(task_id="t-room", agent_id="codex.local")

    meta = orch._prepare_claim(task, dispatch)

    assert meta["cell_id"] == "revenue-wedge"
    assert dispatch.metadata["cell_id"] == "revenue-wedge"


def test_prepare_claim_does_not_guess_ambiguous_shared_agent_room() -> None:
    from dharma_swarm.fractal.room_configs import bootstrap_registry

    orch = Orchestrator(agent_pool=None, task_board=None)
    orch._room_registry = bootstrap_registry()
    task = Task(id="t-ambiguous", title="Ambiguous room", metadata={})
    dispatch = TaskDispatch(task_id="t-ambiguous", agent_id="codex.local")

    meta = orch._prepare_claim(task, dispatch)

    assert "cell_id" not in meta
    assert "cell_id" not in dispatch.metadata


# ---------------------------------------------------------------------------
# retry_policy_for_failure public API (MM-05 resolution)
# ---------------------------------------------------------------------------


def test_retry_policy_for_failure_connection_transient():
    """Public API returns correct policy for transient connection failures."""
    orch = Orchestrator(agent_pool=None, task_board=None)
    task = Task(title="test", metadata={"max_retries": 2, "retry_backoff_seconds": 5.0})
    meta: dict = dict(task.metadata)
    failure_class, retry_count, max_retries, backoff = orch.retry_policy_for_failure(
        task=task, error="API connection error: server disconnected", source="execution_error", meta=meta,
    )
    assert failure_class == "connection_transient"
    assert max_retries >= 2
    assert backoff >= 5.0


def test_retry_policy_for_failure_passthrough():
    """Non-transient failures pass through without retry boost."""
    orch = Orchestrator(agent_pool=None, task_board=None)
    task = Task(title="test", metadata={})
    meta: dict = {}
    failure_class, retry_count, max_retries, backoff = orch.retry_policy_for_failure(
        task=task, error="ValueError: bad input", source="execution_error", meta=meta,
    )
    assert failure_class == "execution_error"
    assert retry_count == 0


@pytest.mark.asyncio
async def test_bsp_barrier_cancellation_releases_agent_and_requeues(tmp_path):
    """Stragglers cancelled by the hard barrier must not remain ghost dispatches."""

    class TrackingPool(MockAgentPool):
        def __init__(self, agents):
            super().__init__(agents)
            self.released: list[str] = []

        async def release(self, agent_id):
            self.released.append(agent_id)

    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t-straggler",
            title="Barrier straggler",
            metadata={"active_claim": {"claim_id": "claim-straggler"}, "max_retries": 1},
        )
    ]
    pool = TrackingPool(
        [AgentState(id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE)]
    )
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path,
        session_id="sess_barrier_cancel",
    )
    orch._default_timeout_seconds = -60.0
    dispatch = TaskDispatch(task_id="t-straggler", agent_id="a1")

    async def never_finishes():
        await asyncio.sleep(3600)

    running = asyncio.create_task(never_finishes())
    orch._running_tasks["t-straggler"] = running
    orch._active_dispatches["t-straggler"] = dispatch

    settled, recovered = await orch._collect_completed_with_barrier()

    assert settled == 0
    assert recovered == 1
    assert running.cancelled()
    assert "t-straggler" not in orch._running_tasks
    assert "t-straggler" not in orch._active_dispatches
    assert pool.released == ["a1"]
    assert any(
        task_id == "t-straggler"
        and fields.get("status") == TaskStatus.PENDING
        and "active_claim" not in fields.get("metadata", {})
        and fields.get("metadata", {}).get("last_failure_source") == "bsp_barrier_timeout"
        for task_id, fields in board.updates
    )
