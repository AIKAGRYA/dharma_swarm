from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.holon_orchestrate import (
    HolonOrchestrationConfig,
    HolonOrchestrationError,
    run_holon_orchestration,
)
from dharma_swarm.intent_router import DecomposedTask, TaskIntent
from dharma_swarm.models import (
    AgentConfig,
    AgentRole,
    AgentState,
    AgentStatus,
    ProviderType,
    Task,
    TaskStatus,
)
from dharma_swarm.orchestrator import Orchestrator


class MemoryTaskBoard:
    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.updates: list[tuple[str, dict]] = []

    async def create(self, **kwargs):
        task = Task(
            title=kwargs["title"],
            description=kwargs.get("description", ""),
            priority=kwargs.get("priority"),
            created_by=kwargs.get("created_by", "system"),
            metadata=dict(kwargs.get("metadata") or {}),
        )
        self.tasks.append(task)
        return task

    async def get(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    async def update_task(self, task_id, **fields):
        self.updates.append((task_id, dict(fields)))
        task = await self.get(task_id)
        if task is None:
            return
        if "status" in fields:
            task.status = fields["status"]
        if "assigned_to" in fields:
            task.assigned_to = fields["assigned_to"]
        if "metadata" in fields and isinstance(fields["metadata"], dict):
            task.metadata = dict(fields["metadata"])
        if "result" in fields:
            task.result = fields["result"]

    async def list_tasks(self, status=None, limit=100):
        tasks = list(self.tasks)
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return tasks[:limit]


class MemoryAgentPool:
    def __init__(self, agents: list[AgentState]) -> None:
        self.agents = agents
        self.results: dict[str, str] = {}
        self.assignments: list[tuple[str, str]] = []
        self.releases: list[str] = []

    async def get_idle_agents(self):
        return list(self.agents)

    async def list_agents(self):
        return list(self.agents)

    async def assign(self, agent_id, task_id):
        self.assignments.append((agent_id, task_id))

    async def release(self, agent_id):
        self.releases.append(agent_id)

    async def get_result(self, agent_id):
        return self.results.get(agent_id)

    async def get(self, agent_id):
        return None


class ExecutingRunner:
    def __init__(self, state: AgentState) -> None:
        self.state = state
        self._lock = asyncio.Lock()

    async def run_task(self, task: Task) -> str:
        self.state.status = AgentStatus.BUSY
        return f"{self.state.name} executed {task.title}: {task.description}"


class ExecutingAgentPool(MemoryAgentPool):
    def __init__(self, agents: list[AgentState]) -> None:
        super().__init__(agents)
        self.runners = {agent.id: ExecutingRunner(agent) for agent in agents}

    async def get(self, agent_id):
        return self.runners.get(agent_id)

    async def assign(self, agent_id, task_id):
        await super().assign(agent_id, task_id)
        runner = self.runners.get(agent_id)
        if runner is not None:
            runner.state.current_task = task_id
            runner.state.status = AgentStatus.BUSY

    async def release(self, agent_id):
        await super().release(agent_id)
        runner = self.runners.get(agent_id)
        if runner is not None:
            runner.state.current_task = None
            runner.state.status = AgentStatus.IDLE


class NoopAdvancedMemory:
    async def remember(self, **kwargs):
        return None

    async def consolidate(self):
        return None


def _write_holon(root: Path, name: str = "codex_composer") -> None:
    agent_dir = root / name
    (agent_dir / "prompt_variants").mkdir(parents=True)
    (agent_dir / "identity.json").write_text(
        json.dumps(
            {
                "name": name,
                "model": "gpt-5.5",
                "provider": "codex",
                "system_prompt": "You are a sovereign composer holon.",
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt_variants" / "active.txt").write_text(
        "You are a sovereign composer holon.",
        encoding="utf-8",
    )


def _decomposition(mission: str) -> DecomposedTask:
    return DecomposedTask(
        original=mission,
        sub_tasks=[
            TaskIntent(
                task="Map the existing L4 runtime surfaces",
                primary_skill="cartographer",
                confidence=0.91,
                complexity="moderate",
            ),
            TaskIntent(
                task="Verify the runtime proof chain",
                primary_skill="validator",
                confidence=0.93,
                complexity="moderate",
            ),
        ],
        total_agents=2,
        has_parallel_work=True,
        estimated_complexity="moderate",
    )


def _agents(*, same_tier: bool = False) -> list[AgentState]:
    second_model = "qwen3-coder:480b-cloud" if same_tier else "glm-5"
    return [
        AgentState(
            id="a-architect",
            name="architect",
            role=AgentRole.ARCHITECT,
            status=AgentStatus.IDLE,
            provider="ollama",
            model="qwen3-coder:480b-cloud",
        ),
        AgentState(
            id="a-validator",
            name="validator",
            role=AgentRole.VALIDATOR,
            status=AgentStatus.IDLE,
            provider="ollama",
            model=second_model,
        ),
    ]


@pytest.mark.asyncio
async def test_holon_orchestration_reuses_fan_out_fan_in_and_injected_synthesis(
    tmp_path: Path,
    fast_gate,
) -> None:
    agents_root = tmp_path / "agents"
    _write_holon(agents_root)
    board = MemoryTaskBoard()
    pool = MemoryAgentPool(_agents())
    pool.results = {
        "a-architect": "runtime surfaces mapped",
        "a-validator": "proof chain verified",
    }
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)

    async def synthesize(holon, mission, records, aggregate):
        return (
            f"{holon.name} synthesized {len(records)} records for {mission}: "
            f"{aggregate}"
        )

    result = await run_holon_orchestration(
        HolonOrchestrationConfig(
            name="codex_composer",
            mission="Build the L4 HOLON body and verify it",
        ),
        orchestrator=orchestrator,
        agents_root=agents_root,
        decomposer=_decomposition,
        synthesizer=synthesize,
    )

    assert result["overall_pass"] is True
    assert result["holon"]["model"] == "gpt-5.5"
    assert result["execution_mode"] == "dispatch_aggregation_probe"
    assert result["synthesis_source"] == "injected_holon_synthesizer"
    assert result["live_model_call_claimed"] is False
    assert result["live_specialist_execution_claimed"] is False
    assert result["proof_levels"]["fan_out_dispatches"] is True
    assert result["proof_levels"]["model_tier_diversity"] is True
    assert len(result["dispatches"]) == 2
    assert len(pool.assignments) == 2
    assert "runtime surfaces mapped" in result["aggregate"]
    assert "proof chain verified" in result["aggregate"]
    assert result["dispatches"][0]["metadata"]["holon_orchestration"] is True
    assert result["dispatches"][0]["metadata"]["holon_subtask"]["primary_skill"] == (
        "cartographer"
    )
    assert board.tasks[0].metadata["holon_subtasks"][1]["primary_skill"] == "validator"


@pytest.mark.asyncio
async def test_holon_orchestration_can_execute_bounded_real_subtasks(
    tmp_path: Path,
    fast_gate,
) -> None:
    agents_root = tmp_path / "agents"
    _write_holon(agents_root)
    board = MemoryTaskBoard()
    pool = ExecutingAgentPool(_agents())
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "runtime" / "ledgers",
        runtime_db_path=tmp_path / "runtime" / "state" / "runtime.db",
    )

    result = await run_holon_orchestration(
        HolonOrchestrationConfig(
            name="codex_composer",
            mission="Build the L4 HOLON body and verify it",
            execution_mode="bounded_subtask_execution",
            execution_timeout_seconds=5.0,
        ),
        orchestrator=orchestrator,
        agents_root=agents_root,
        decomposer=_decomposition,
    )

    assert result["overall_pass"] is True
    assert result["execution_mode"] == "bounded_subtask_execution"
    assert result["live_specialist_execution_claimed"] is True
    assert result["live_model_call_claimed"] is False
    assert result["proof_levels"]["live_specialist_execution"] is True
    assert len(result["subtask_task_ids"]) == 2
    assert "architect executed HOLON subtask 1" in result["aggregate"]
    assert "validator executed HOLON subtask 2" in result["aggregate"]
    assert len(pool.assignments) == 2
    assert len(pool.releases) == 2
    subtask_ids = set(result["subtask_task_ids"])
    completed = [
        task for task in board.tasks if task.id in subtask_ids and task.result
    ]
    assert len(completed) == 2

    runtime_db = tmp_path / "runtime" / "state" / "runtime.db"
    with sqlite3.connect(runtime_db) as db:
        rows = db.execute(
            """
            SELECT receipt_type, status, payload_json
            FROM runtime_receipts
            WHERE task_id IN (?, ?)
              AND receipt_type IN ('task_claim', 'delegation_run')
            ORDER BY created_at, receipt_type
            """,
            tuple(result["subtask_task_ids"]),
        ).fetchall()
    assert rows
    payloads = [json.loads(row[2]) for row in rows]
    assert {row[1] for row in rows} >= {"claimed", "running", "completed"}
    assert all(payload["provider_execution"] is False for payload in payloads)
    assert all(
        payload["provider_model_applicability"] == "not_applicable"
        for payload in payloads
    )
    assert all(
        payload["provider_model_truth_source"]
        == "holon_orchestrate.no_provider_execution"
        for payload in payloads
    )
    assert all(
        payload["no_provider_model_reason"]
        == "holon_bounded_subtask_execution_no_live_model_call_claimed"
        for payload in payloads
    )


@pytest.mark.asyncio
async def test_holon_orchestration_executes_on_read_only_swarm_manager_stack(
    tmp_path: Path,
    monkeypatch,
    fast_gate,
) -> None:
    from dharma_swarm.swarm import SwarmManager

    home = tmp_path / "home"
    home.mkdir()
    state_dir = tmp_path / "state"
    meta_dir = state_dir / "meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "telos_seeded").write_text("test preseed\n", encoding="utf-8")
    (meta_dir / "gnani_seeded").write_text("test preseed\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("DHARMA_READ_ONLY_BOOT", "1")
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")

    import dharma_swarm.sleep_time_agent as sleep_time_agent
    import dharma_swarm.telos_tracker as telos_tracker

    class NoopSleepTimeAgent:
        async def consolidate_knowledge(self, *args, **kwargs):
            return []

    async def noop_record_task_completion(*args, **kwargs):
        return None

    monkeypatch.setattr(sleep_time_agent, "SleepTimeAgent", NoopSleepTimeAgent)
    monkeypatch.setattr(
        telos_tracker,
        "record_task_completion",
        noop_record_task_completion,
    )

    agents_root = tmp_path / "agents"
    _write_holon(agents_root)
    swarm = SwarmManager(state_dir=state_dir)
    await swarm.init()
    try:
        assert swarm._agent_pool is not None
        assert swarm._orchestrator is not None
        assert swarm._task_board is not None

        for name, role, model in (
            (
                "l4-swmanager-architect",
                AgentRole.ARCHITECT,
                "deterministic-architect",
            ),
            (
                "l4-swmanager-validator",
                AgentRole.VALIDATOR,
                "deterministic-validator",
            ),
        ):
            await swarm._agent_pool.spawn(
                AgentConfig(
                    name=name,
                    role=role,
                    provider=ProviderType.OLLAMA,
                    model=model,
                    system_prompt="Return concise deterministic proof notes.",
                    metadata={"state_dir": str(state_dir)},
                ),
                provider=None,
                message_bus=swarm._message_bus,
                advanced_memory=NoopAdvancedMemory(),
            )

        result = await run_holon_orchestration(
            HolonOrchestrationConfig(
                name="codex_composer",
                mission="Prove bounded HOLON execution on SwarmManager organs",
                execution_mode="bounded_subtask_execution",
                execution_timeout_seconds=10.0,
            ),
            orchestrator=swarm._orchestrator,
            agents_root=agents_root,
            decomposer=_decomposition,
        )

        assert result["overall_pass"] is True
        assert result["execution_mode"] == "bounded_subtask_execution"
        assert result["live_specialist_execution_claimed"] is True
        assert result["live_model_call_claimed"] is False
        assert result["proof_levels"]["live_specialist_execution"] is True
        assert len(result["subtask_task_ids"]) == 2

        completed = []
        for task_id in result["subtask_task_ids"]:
            task = await swarm._task_board.get(task_id)
            completed.append(task)
        assert all(task is not None for task in completed)
        assert all(task.status == TaskStatus.COMPLETED for task in completed if task)
        assert all(task.result for task in completed if task)

        runtime_db = state_dir / "state" / "runtime.db"
        with sqlite3.connect(runtime_db) as db:
            rows = db.execute(
                """
                SELECT receipt_type, status, payload_json
                FROM runtime_receipts
                WHERE task_id IN (?, ?)
                  AND status = 'completed'
                  AND receipt_type IN ('task_claim', 'delegation_run')
                ORDER BY receipt_type
                """,
                tuple(result["subtask_task_ids"]),
            ).fetchall()
        assert rows
        payloads = [json.loads(row[2]) for row in rows]
        assert all(payload["provider_execution"] is False for payload in payloads)
        assert all(
            payload["provider_model_truth_source"]
            == "agent_runner.no_provider_execution"
            for payload in payloads
        )
        assert all(
            payload["no_provider_model_reason"] == "agent_runner_no_provider_attached"
            for payload in payloads
        )
    finally:
        await swarm.shutdown(drain_timeout=1.0)


@pytest.mark.asyncio
async def test_holon_orchestration_refuses_false_tier_diversity(
    tmp_path: Path,
    fast_gate,
) -> None:
    agents_root = tmp_path / "agents"
    _write_holon(agents_root)
    board = MemoryTaskBoard()
    pool = MemoryAgentPool(_agents(same_tier=True))
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)

    with pytest.raises(HolonOrchestrationError, match="model tier diversity"):
        await run_holon_orchestration(
            HolonOrchestrationConfig(
                name="codex_composer",
                mission="Build the L4 HOLON body and verify it",
            ),
            orchestrator=orchestrator,
            agents_root=agents_root,
            decomposer=_decomposition,
        )


@pytest.mark.asyncio
async def test_holon_orchestration_refuses_under_decomposed_work(
    tmp_path: Path,
    fast_gate,
) -> None:
    agents_root = tmp_path / "agents"
    _write_holon(agents_root)
    board = MemoryTaskBoard()
    pool = MemoryAgentPool(_agents())
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)

    def one_task(mission: str) -> DecomposedTask:
        return DecomposedTask(
            original=mission,
            sub_tasks=[TaskIntent(task="Only one lens", primary_skill="general")],
            total_agents=1,
        )

    with pytest.raises(HolonOrchestrationError, match="need at least 2"):
        await run_holon_orchestration(
            HolonOrchestrationConfig(
                name="codex_composer",
                mission="Build the L4 HOLON body and verify it",
            ),
            orchestrator=orchestrator,
            agents_root=agents_root,
            decomposer=one_task,
        )
