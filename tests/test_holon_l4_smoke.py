from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.holon_l4_smoke import (
    MODEL_PROBE_LEASE_SCHEMA_VERSION,
    L4SmokeConfig,
    model_probe_lease_digest,
    run_l4_supervised_smoke,
)
from dharma_swarm.holon_persistence import load_session
from dharma_swarm.intent_router import DecomposedTask, TaskIntent
from dharma_swarm.models import AgentRole, AgentState, AgentStatus, LLMRequest, Task
from dharma_swarm.orchestrator import Orchestrator


def _make_agent(
    root: Path,
    name: str = "codex_composer",
    provider: str = "ollama",
) -> Path:
    agent_dir = root / name
    (agent_dir / "prompt_variants").mkdir(parents=True)
    (agent_dir / "identity.json").write_text(
        json.dumps(
            {
                "model": "identity-model",
                "provider": provider,
                "system_prompt": "fallback prompt",
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt_variants" / "active.txt").write_text(
        "I am codex_composer.",
        encoding="utf-8",
    )
    return root


def _write_transport_heartbeat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "agent_uid": "codex_composer",
                "subject": "dharma.agent.codex_composer.inbox",
                "stream": "DHARMA_FLEET",
                "consumer": "codex_composer_inbox",
                "status": "IDLE",
                "cycle": 1,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_model_probe_lease(
    path: Path,
    *,
    lease_id: str = "lease:test:l4-subprocess-lease",
    holon: str = "codex_composer",
    provider_type: str = "codex",
    model: str = "identity-model",
    session_id: str = "l4-subprocess-lease",
    allow_subprocess_provider: bool = True,
    expires_delta: timedelta = timedelta(minutes=10),
    mutate_digest: bool = False,
) -> Path:
    now = datetime.now(UTC).replace(microsecond=0)
    payload = {
        "schema_version": MODEL_PROBE_LEASE_SCHEMA_VERSION,
        "lease_id": lease_id,
        "holon": holon,
        "provider_type": provider_type,
        "model": model,
        "session_id": session_id,
        "allow_live_model_probe": True,
        "allow_subprocess_provider": allow_subprocess_provider,
        "issued_at": (now - timedelta(seconds=5)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + expires_delta).isoformat().replace("+00:00", "Z"),
        "purpose": "unit test structured model probe lease",
    }
    payload["digest"] = model_probe_lease_digest(payload)
    if mutate_digest:
        payload["digest"] = "sha256:bad"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


class _MemoryTaskBoard:
    def __init__(self) -> None:
        self.tasks: list[Task] = []

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
        return next((task for task in self.tasks if task.id == task_id), None)

    async def update_task(self, task_id, **fields):
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


class _MemoryAgentPool:
    def __init__(self) -> None:
        self.agents = [
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
                model="glm-5",
            ),
        ]
        self.results = {
            "a-architect": "runtime surfaces mapped",
            "a-validator": "proof chain verified",
        }

    async def get_idle_agents(self):
        return list(self.agents)

    async def list_agents(self):
        return list(self.agents)

    async def assign(self, agent_id, task_id):
        return None

    async def release(self, agent_id):
        return None

    async def get_result(self, agent_id):
        return self.results.get(agent_id)

    async def get(self, agent_id):
        return None


class _ExecutingRunner:
    def __init__(self, state: AgentState) -> None:
        self.state = state
        self._lock = asyncio.Lock()

    async def run_task(self, task: Task) -> str:
        self.state.status = AgentStatus.BUSY
        return f"{self.state.name} executed {task.title}: {task.description}"


class _ExecutingAgentPool(_MemoryAgentPool):
    def __init__(self) -> None:
        super().__init__()
        self.runners = {agent.id: _ExecutingRunner(agent) for agent in self.agents}

    async def get(self, agent_id):
        return self.runners.get(agent_id)

    async def assign(self, agent_id, task_id):
        runner = self.runners.get(agent_id)
        if runner is not None:
            runner.state.current_task = task_id
            runner.state.status = AgentStatus.BUSY

    async def release(self, agent_id):
        runner = self.runners.get(agent_id)
        if runner is not None:
            runner.state.current_task = None
            runner.state.status = AgentStatus.IDLE


def _l4_decomposition(mission: str) -> DecomposedTask:
    return DecomposedTask(
        original=mission,
        sub_tasks=[
            TaskIntent(task="Map L4 runtime surfaces", primary_skill="cartographer"),
            TaskIntent(task="Verify L4 proof chain", primary_skill="validator"),
        ],
        total_agents=2,
        has_parallel_work=True,
    )


async def test_l4_supervised_smoke_records_full_chain(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    receipt_path = tmp_path / "reports" / "l4_memory_write_receipts.jsonl"

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=receipt_path,
            session_id="l4-test-session",
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is True
    assert proof["holon"]["model"] == "identity-model"
    assert proof["routing_decision"] == {
        "provider_type": "ollama",
        "model": "identity-model",
        "request_model": "identity-model",
        "declared_first": True,
        "live_model_call": False,
    }
    assert proof["memory_receipt"]["receipt_id"].startswith("memory_kernel_write_receipt:")
    assert proof["memory_receipt"]["policy_decision"]["outcome"] == "allow"
    assert receipt_path.exists()

    artifact_path = Path(proof["artifact"]["path"])
    assert artifact_path.exists()
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["artifact"]["digest"] == proof["artifact"]["digest"]

    events = load_session("codex_composer", agents_root=agents_root)
    assert len(events) == 1
    assert events[0]["record"]["session_id"] == "l4-test-session"
    assert events[0]["record"]["overall_pass"] is True
    assert events[0]["record"]["proof_levels"]["persistence"] is True
    assert events[0]["record"]["claim_scope"]["service_alive"] is True
    assert events[0]["record"]["claim_scope"]["transport_reachable"] is False
    assert proof["proof_levels"]["persistence"] is True
    assert proof["proof_levels"]["service_heartbeat"] is True
    assert proof["proof_levels"]["transport_reachable"] is False
    assert proof["claim_scope"]["service_alive"] is True
    assert proof["claim_scope"]["transport_reachable"] is False
    assert proof["claim_scope"]["live_specialist_execution"] is False
    assert proof["transport_liveness"]["transport_reachable"] is False
    assert proof["service_heartbeat"]["heartbeat_ref"]["record_hash"].startswith("sha256:")
    assert proof["service_heartbeat"]["liveness"]["service_alive"] is True
    assert Path(proof["service_heartbeat"]["heartbeat_ref"]["path"]).exists()


async def test_l4_supervised_smoke_can_require_orchestration_probe(
    tmp_path: Path,
    fast_gate,
) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    orchestrator = Orchestrator(
        task_board=_MemoryTaskBoard(),
        agent_pool=_MemoryAgentPool(),
    )

    async def synthesize(holon, mission, records, aggregate):
        return f"{holon.name} synthesized {len(records)} records: {aggregate}"

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-orchestration-required",
            transport_heartbeat_path=tmp_path / "missing_transport.json",
            enable_orchestration_probe=True,
            require_orchestration=True,
            orchestration_orchestrator=orchestrator,
            orchestration_decomposer=_l4_decomposition,
            orchestration_synthesizer=synthesize,
        )
    )

    assert proof["overall_pass"] is True
    assert proof["proof_levels"]["orchestration"] is True
    assert proof["claim_scope"]["orchestration_proven"] is True
    assert proof["orchestration_probe"]["status"] == "ok"
    assert proof["orchestration_probe"]["orchestrated"] is True
    assert proof["orchestration_probe"]["execution_mode"] == "dispatch_aggregation_probe"
    assert proof["orchestration_probe"]["subtask_count"] == 2
    assert proof["orchestration_probe"]["dispatch_count"] == 2
    assert len(proof["orchestration_probe"]["model_tiers"]) == 2
    assert proof["orchestration_probe"]["live_specialist_execution_claimed"] is False
    assert proof["orchestration_probe"]["synthesis_source"] == (
        "injected_holon_synthesizer"
    )
    artifact_payload = json.loads(Path(proof["artifact"]["path"]).read_text())
    assert artifact_payload["orchestration_probe"]["orchestrated"] is True


async def test_l4_supervised_smoke_can_require_bounded_specialist_execution(
    tmp_path: Path,
    fast_gate,
) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    orchestrator = Orchestrator(
        task_board=_MemoryTaskBoard(),
        agent_pool=_ExecutingAgentPool(),
        ledger_dir=tmp_path / "runtime" / "ledgers",
        runtime_db_path=tmp_path / "runtime" / "state" / "runtime.db",
    )

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-bounded-specialist-execution",
            transport_heartbeat_path=tmp_path / "missing_transport.json",
            enable_orchestration_probe=True,
            require_orchestration=True,
            orchestration_orchestrator=orchestrator,
            orchestration_decomposer=_l4_decomposition,
            orchestration_execution_mode="bounded_subtask_execution",
            orchestration_execution_timeout_seconds=5.0,
        )
    )

    assert proof["overall_pass"] is True
    assert proof["proof_levels"]["orchestration"] is True
    assert proof["claim_scope"]["live_specialist_execution"] is True
    assert proof["orchestration_probe"]["execution_mode"] == "bounded_subtask_execution"
    assert proof["orchestration_probe"]["live_specialist_execution_claimed"] is True
    assert proof["orchestration_probe"]["live_model_call_claimed"] is False
    assert proof["orchestration_probe"]["proof_levels"]["live_specialist_execution"] is True


async def test_l4_supervised_smoke_is_honest_about_model_responsiveness(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-honesty",
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["claim_scope"]["service_alive"] is True
    assert proof["claim_scope"]["transport_reachable"] is False
    assert proof["claim_scope"]["model_responsive"] is False
    assert proof["claim_scope"]["safe_refusal"] is False
    assert proof["proof_levels"]["service_heartbeat"] is True
    assert proof["proof_levels"]["model_responsive"] is False
    assert proof["model_probe"]["status"] == "skipped"


async def test_l4_supervised_smoke_records_model_response_probe(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    seen: dict[str, object] = {}

    class StubProvider:
        async def stream(self, request: LLMRequest):
            seen["model"] = request.model
            seen["system"] = request.system
            seen["messages"] = list(request.messages)
            yield "codex_composer "
            yield "is responsive."

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-model-responsive",
            enable_model_probe=True,
            model_probe_provider=StubProvider(),
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is True
    assert proof["routing_decision"]["live_model_call"] is True
    assert proof["proof_levels"]["model_responsive"] is True
    assert proof["proof_levels"]["service_heartbeat"] is True
    assert proof["claim_scope"]["model_responsive"] is True
    assert proof["claim_scope"]["safe_refusal"] is False
    assert proof["model_probe"]["status"] == "ok"
    assert proof["model_probe"]["responsive"] is True
    assert proof["model_probe"]["route_policy"]["decision"] == "allow"
    assert proof["model_probe"]["route_policy"]["execution_kind"] == "injected"
    assert proof["model_probe"]["chunk_count"] == 2
    assert proof["model_probe"]["reply_digest"].startswith("sha256:")
    assert seen["model"] == "identity-model"
    assert seen["system"] == "I am codex_composer."
    assert seen["messages"][-1]["content"] == (
        "Reply with one short sentence confirming you are responsive as this holon."
    )


async def test_l4_supervised_smoke_can_require_transport_reachability(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    transport_heartbeat = tmp_path / "a2a" / "bridge_heartbeats" / "codex_composer.json"
    _write_transport_heartbeat(transport_heartbeat)

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-transport-responsive",
            transport_agent_uid="codex_composer",
            transport_heartbeat_path=transport_heartbeat,
            require_transport_reachable=True,
        )
    )

    assert proof["overall_pass"] is True
    assert proof["proof_levels"]["transport_reachable"] is True
    assert proof["claim_scope"]["transport_reachable"] is True
    assert proof["transport_liveness"]["transport_reachable"] is True
    assert proof["artifact"]["digest"].startswith("sha256:")


async def test_l4_supervised_smoke_refuses_model_responsive_claim_on_probe_error(
    tmp_path: Path,
) -> None:
    agents_root = _make_agent(tmp_path / "agents")

    class BoomProvider:
        async def stream(self, request: LLMRequest):
            raise RuntimeError("provider exploded token=sk-testsecret123456")
            yield ""

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-model-error",
            enable_model_probe=True,
            model_probe_provider=BoomProvider(),
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is False
    assert proof["proof_levels"]["service_heartbeat"] is True
    assert proof["proof_levels"]["model_responsive"] is False
    assert proof["claim_scope"]["model_responsive"] is False
    assert proof["claim_scope"]["safe_refusal"] is True
    assert proof["claim_scope"]["transport_reachable"] is False
    assert proof["model_probe"]["status"] == "error"
    assert proof["model_probe"]["route_policy"]["decision"] == "allow"
    assert proof["model_probe"]["route_policy"]["execution_kind"] == "injected"
    assert proof["model_probe"]["error_type"] == "RuntimeError"
    assert "sk-testsecret" not in proof["model_probe"]["error_preview"]
    assert "[redacted]" in proof["model_probe"]["error_preview"]


async def test_l4_supervised_smoke_refuses_subprocess_model_probe_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents_root = _make_agent(tmp_path / "agents", provider="codex")

    def fail_provider_construction(*args: object, **kwargs: object) -> object:
        raise AssertionError("subprocess provider must not be constructed")

    monkeypatch.setattr(
        "dharma_swarm.holon_l4_smoke.get_holon_provider",
        fail_provider_construction,
    )

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-unsafe-subprocess-refusal",
            enable_model_probe=True,
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is False
    assert proof["proof_levels"]["service_heartbeat"] is True
    assert proof["proof_levels"]["model_responsive"] is False
    assert proof["claim_scope"]["model_responsive"] is False
    assert proof["claim_scope"]["safe_refusal"] is True
    assert proof["model_probe"]["status"] == "refused_unsafe_provider"
    assert proof["model_probe"]["attempted"] is False
    assert proof["model_probe"]["provider_type"] == "codex"
    assert proof["model_probe"]["route_policy"]["decision"] == "refuse"
    assert proof["model_probe"]["route_policy"]["subprocess_provider"] is True
    assert proof["model_probe"]["route_policy"]["explicit_override"] is False


async def test_l4_supervised_smoke_requires_lease_for_subprocess_model_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents_root = _make_agent(tmp_path / "agents", provider="codex")

    def fail_provider_construction(*args: object, **kwargs: object) -> object:
        raise AssertionError("subprocess provider must not be constructed")

    monkeypatch.setattr(
        "dharma_swarm.holon_l4_smoke.get_holon_provider",
        fail_provider_construction,
    )

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-subprocess-requires-lease",
            enable_model_probe=True,
            allow_subprocess_model_probe=True,
            model_probe_lease_id="lease:test:missing-path",
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is False
    assert proof["proof_levels"]["model_responsive"] is False
    assert proof["claim_scope"]["model_responsive"] is False
    assert proof["claim_scope"]["safe_refusal"] is True
    assert proof["model_probe"]["status"] == "refused_unsafe_provider"
    assert proof["model_probe"]["attempted"] is False
    route_policy = proof["model_probe"]["route_policy"]
    assert route_policy["decision"] == "refuse"
    assert route_policy["reason"] == "model_probe_lease_path_missing"
    assert route_policy["subprocess_provider"] is True
    assert route_policy["explicit_override"] is True
    assert route_policy["explicit_lease"] is False
    assert route_policy["lease_evidence"]["valid"] is False
    assert route_policy["lease_evidence"]["lease_id"] == "lease:test:missing-path"


async def test_l4_supervised_smoke_refuses_bad_model_probe_lease_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents_root = _make_agent(tmp_path / "agents", provider="codex")
    lease_path = _write_model_probe_lease(
        tmp_path / "leases" / "bad-digest.json",
        lease_id="lease:test:bad-digest",
        session_id="l4-subprocess-bad-lease",
        mutate_digest=True,
    )

    def fail_provider_construction(*args: object, **kwargs: object) -> object:
        raise AssertionError("subprocess provider must not be constructed")

    monkeypatch.setattr(
        "dharma_swarm.holon_l4_smoke.get_holon_provider",
        fail_provider_construction,
    )

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-subprocess-bad-lease",
            enable_model_probe=True,
            allow_subprocess_model_probe=True,
            model_probe_lease_id="lease:test:bad-digest",
            model_probe_lease_path=lease_path,
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    route_policy = proof["model_probe"]["route_policy"]
    assert proof["overall_pass"] is False
    assert proof["model_probe"]["status"] == "refused_unsafe_provider"
    assert proof["model_probe"]["attempted"] is False
    assert route_policy["decision"] == "refuse"
    assert route_policy["reason"] == "model_probe_lease_invalid:digest"
    assert route_policy["explicit_lease"] is False
    assert route_policy["lease_evidence"]["checks"]["digest"] is False
    assert route_policy["lease_evidence"]["expected_digest"].startswith("sha256:")


async def test_l4_supervised_smoke_allows_subprocess_model_probe_with_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents_root = _make_agent(tmp_path / "agents", provider="codex")
    lease_path = _write_model_probe_lease(
        tmp_path / "leases" / "valid.json",
        session_id="l4-subprocess-lease",
    )
    seen: dict[str, object] = {}

    class StubProvider:
        async def stream(self, request: LLMRequest):
            seen["model"] = request.model
            yield "leased subprocess route is responsive"

    def stub_provider(*args: object, **kwargs: object) -> StubProvider:
        return StubProvider()

    monkeypatch.setattr(
        "dharma_swarm.holon_l4_smoke.get_holon_provider",
        stub_provider,
    )

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-subprocess-lease",
            enable_model_probe=True,
            allow_subprocess_model_probe=True,
            model_probe_lease_id="lease:test:l4-subprocess-lease",
            model_probe_lease_path=lease_path,
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is True
    assert proof["proof_levels"]["model_responsive"] is True
    assert proof["claim_scope"]["model_responsive"] is True
    assert proof["claim_scope"]["safe_refusal"] is False
    assert proof["model_probe"]["status"] == "ok"
    assert proof["model_probe"]["attempted"] is True
    route_policy = proof["model_probe"]["route_policy"]
    assert route_policy["decision"] == "allow"
    assert route_policy["execution_kind"] == "subprocess_cli"
    assert route_policy["subprocess_provider"] is True
    assert route_policy["explicit_override"] is True
    assert route_policy["explicit_lease"] is True
    assert route_policy["model_probe_lease_id"] == "lease:test:l4-subprocess-lease"
    assert route_policy["lease_evidence"]["valid"] is True
    assert route_policy["lease_evidence"]["digest"].startswith("sha256:")
    assert route_policy["lease_evidence"]["checks"]["expires_at"] is True
    assert seen["model"] == "identity-model"


async def test_l4_supervised_smoke_can_use_safe_codex_subprocess_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents_root = _make_agent(tmp_path / "agents", provider="codex")
    lease_path = _write_model_probe_lease(
        tmp_path / "leases" / "safe-codex.json",
        lease_id="lease:test:safe-codex",
        session_id="l4-safe-codex-probe",
    )
    seen: dict[str, object] = {}

    def fail_provider_construction(*args: object, **kwargs: object) -> object:
        raise AssertionError("safe subprocess probe must not use CodexProvider")

    async def safe_runner(**kwargs: object) -> dict[str, str]:
        seen.update(kwargs)
        return {"reply": "codex_composer is responsive through safe read-only codex exec."}

    monkeypatch.setattr(
        "dharma_swarm.holon_l4_smoke.get_holon_provider",
        fail_provider_construction,
    )

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-safe-codex-probe",
            enable_model_probe=True,
            allow_subprocess_model_probe=True,
            safe_subprocess_model_probe=True,
            safe_subprocess_model_probe_runner=safe_runner,
            model_probe_lease_id="lease:test:safe-codex",
            model_probe_lease_path=lease_path,
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is True
    assert proof["proof_levels"]["model_responsive"] is True
    assert proof["claim_scope"]["model_responsive"] is True
    assert proof["model_probe"]["status"] == "ok"
    assert proof["model_probe"]["provider_source"] == "declared_identity"
    route_policy = proof["model_probe"]["route_policy"]
    assert route_policy["decision"] == "allow"
    assert route_policy["execution_kind"] == "safe_codex_exec_read_only"
    assert route_policy["safe_subprocess_probe"] is True
    assert route_policy["explicit_lease"] is True
    assert seen["cwd"] == Path.cwd().resolve()
    assert "read-only L4 HOLON responsiveness probe" in seen["prompt"]


async def test_l4_safe_codex_subprocess_probe_uses_readonly_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents_root = _make_agent(tmp_path / "agents", provider="codex")
    lease_path = _write_model_probe_lease(
        tmp_path / "leases" / "safe-codex-argv.json",
        lease_id="lease:test:safe-codex-argv",
        session_id="l4-safe-codex-argv",
    )
    captured: dict[str, object] = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"codex_composer is responsive.", b""

    async def fake_create_subprocess_exec(*cmd, **kwargs):  # noqa: ANN002, ANN003
        captured["cmd"] = list(cmd)
        captured["kwargs"] = dict(kwargs)
        return FakeProcess()

    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.resolve_runtime_provider_config",
        lambda *args, **kwargs: SimpleNamespace(binary_path="/bin/codex"),
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-safe-codex-argv",
            enable_model_probe=True,
            allow_subprocess_model_probe=True,
            safe_subprocess_model_probe=True,
            safe_subprocess_probe_cwd=tmp_path,
            model_probe_lease_id="lease:test:safe-codex-argv",
            model_probe_lease_path=lease_path,
            transport_heartbeat_path=tmp_path / "missing_transport.json",
        )
    )

    assert proof["overall_pass"] is True
    cmd = captured["cmd"]
    assert cmd[:4] == ["/bin/codex", "--ask-for-approval", "never", "exec"]
    assert cmd[cmd.index("-c") + 1] == 'approval_policy="never"'
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert "--ephemeral" in cmd
    assert "--ignore-rules" in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert cmd[cmd.index("-C") + 1] == str(tmp_path.resolve())


async def test_l4_supervised_smoke_rejects_unknown_holon(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await run_l4_supervised_smoke(
            L4SmokeConfig(
                name="missing",
                agents_root=tmp_path,
                memory_receipt_path=tmp_path / "receipts.jsonl",
                session_id="missing",
            )
        )


async def test_l4_supervised_smoke_fails_when_transport_required_but_missing(
    tmp_path: Path,
) -> None:
    agents_root = _make_agent(tmp_path / "agents")

    proof = await run_l4_supervised_smoke(
        L4SmokeConfig(
            name="codex_composer",
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "receipts.jsonl",
            session_id="l4-transport-missing",
            transport_heartbeat_path=tmp_path / "missing.json",
            require_transport_reachable=True,
        )
    )

    assert proof["overall_pass"] is False
    assert proof["proof_levels"]["transport_reachable"] is False
    assert proof["claim_scope"]["transport_reachable"] is False
    assert proof["transport_liveness"]["failure_reasons"] == [
        "a2a_inbox_bridge_heartbeat_missing"
    ]
