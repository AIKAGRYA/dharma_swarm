"""Operator/API-submitted tasks dispatch before system self-spawned tasks.

Production failure mode: after a timeout requeue, dispatch selected
system-spawned "Develop latent insight" tasks over operator-submitted tasks
that were waiting at the same priority. The fix orders the board's ready
query (``_READY_QUERY``) by origin at equal priority, derived from what the
create paths already store: the API path (api/routers/commands.py ->
Swarm.create_task) stamps ``metadata.created_via='swarm.create_task'``,
startup_crew sets ``created_by='operator'``, and self-spawns stamp
``metadata.source`` ('swarm.latent_gold' / 'swarm.coordination_synthesis').
"""

import asyncio

import pytest

from dharma_swarm.models import (
    AgentRole,
    AgentState,
    AgentStatus,
    GateCheckResult,
    GateDecision,
    TaskPriority,
)
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.task_board import TaskBoard

# What spawn_latent_gold_tasks / create_task_batch actually store (swarm.py).
SELF_SPAWN_META = {
    "latent_gold_reopened": True,
    "source": "swarm.latent_gold",
    "created_via": "swarm.create_task_batch",
}
# What the operator/API path (Swarm.create_task) actually stores.
OPERATOR_META = {"created_via": "swarm.create_task"}


@pytest.fixture(autouse=True)
def fast_dispatch_gate():
    """Default orchestrator dispatch gates to ALLOW (mirrors test_orchestrator)."""
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
async def board(tmp_path):
    b = TaskBoard(tmp_path / "tasks.db")
    await b.init_db()
    return b


class SingleAgentPool:
    """Minimal pool duck-type with one idle agent and a slow runner."""

    def __init__(self):
        self.agent = AgentState(
            id="a1", name="agent-1", role=AgentRole.GENERAL, status=AgentStatus.IDLE,
        )
        self.assignments: list[tuple[str, str]] = []

    async def list_agents(self):
        return [self.agent]

    async def get_idle_agents(self):
        return [self.agent]

    async def assign(self, agent_id, task_id):
        self.assignments.append((agent_id, task_id))

    async def release(self, agent_id):
        pass

    async def get(self, agent_id):
        class _Runner:
            _config = None

            async def run_task(self, task):
                await asyncio.sleep(3600)

        return _Runner()


@pytest.mark.asyncio
async def test_operator_task_ready_before_older_self_spawned(board):
    spawned = await board.create("Develop latent insight", metadata=SELF_SPAWN_META)
    operator = await board.create("Fix the dashboard", metadata=OPERATOR_META)

    ready = await board.get_ready_tasks()

    # Self-spawned was created first, yet the operator task ranks ahead.
    assert [t.id for t in ready] == [operator.id, spawned.id]


@pytest.mark.asyncio
async def test_created_by_operator_column_ranks_first(board):
    spawned = await board.create("Develop latent insight", metadata=SELF_SPAWN_META)
    operator = await board.create("Operator crew task", created_by="operator")

    ready = await board.get_ready_tasks()

    assert [t.id for t in ready] == [operator.id, spawned.id]


@pytest.mark.asyncio
async def test_priority_still_dominates_origin(board):
    spawned_high = await board.create(
        "Develop latent insight",
        priority=TaskPriority.HIGH,
        metadata=SELF_SPAWN_META,
    )
    operator_normal = await board.create("Operator task", metadata=OPERATOR_META)

    ready = await board.get_ready_tasks()

    assert [t.id for t in ready] == [spawned_high.id, operator_normal.id]


@pytest.mark.asyncio
async def test_unmarked_tasks_sit_between_operator_and_self_spawned(board):
    spawned = await board.create("Develop latent insight", metadata=SELF_SPAWN_META)
    plain = await board.create("Untagged task")
    operator = await board.create("Operator task", metadata=OPERATOR_META)

    ready = await board.get_ready_tasks()

    assert [t.id for t in ready] == [operator.id, plain.id, spawned.id]


@pytest.mark.asyncio
async def test_route_next_dispatches_operator_task_first(board, tmp_path, monkeypatch):
    """With one idle agent, the operator task wins the dispatch slot."""
    monkeypatch.setenv("DHARMA_SPINE_DISPATCH", "0")
    await board.create("Develop latent insight", metadata=SELF_SPAWN_META)
    operator = await board.create("Fix the dashboard", metadata=OPERATOR_META)

    pool = SingleAgentPool()
    orch = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=tmp_path / "runtime.db",
        session_id="sess_user_priority",
    )

    dispatches = await orch.route_next()

    assert len(dispatches) == 1
    assert dispatches[0].task_id == operator.id
    assert pool.assignments == [("a1", operator.id)]

    # Tear down the never-finishing background execution.
    for bg in orch._running_tasks.values():
        bg.cancel()
    await asyncio.gather(*orch._running_tasks.values(), return_exceptions=True)
