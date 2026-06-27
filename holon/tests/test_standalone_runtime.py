from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from holon import HolonCycleResult, MemoryKernel, holon_wake_cycle, run_holon_loop
from holon import _build_backend
from holon.a2a import ping_agents
from holon.burn_in import BurnInConfig, run_burn_in
from holon.contracts import ArtifactRef, LLMRequest
from holon.holon_bridge import load_holon
from holon.holon_runtime import HolonRuntime
from holon.memory_kernel import MemoryContextPack, MemoryContextPackItem
from holon.organs import killswitch, persistence, service
from holon.providers import ProviderResponse, ProviderRouter, build_provider_router, estimate_usage_cost_usd
from holon.receipts import build_receipt, write_receipt
from holon.source_proof import package_source_proof
from holon.supervisor import SupervisorConfig, run_supervisor
from holon.tools import default_tool_registry
from holon.verifier import verify_standalone


def _make_agent(root: Path, name: str = "codex_composer") -> Path:
    agent = root / name
    (agent / "prompt_variants").mkdir(parents=True)
    (agent / "identity.json").write_text(
        json.dumps({"model": "holon-echo-v1", "provider": "echo", "system_prompt": "fallback"}),
        encoding="utf-8",
    )
    (agent / "prompt_variants" / "active.txt").write_text("I am a standalone Holon.", encoding="utf-8")
    return root


class _SnippetMemory:
    def preview_memory_pack(self, **kwargs):
        return MemoryContextPack(
            items=(
                MemoryContextPackItem(
                    surface_id="facts",
                    content_ref="facts:1",
                    content_snippet="continuity requires receipt evidence",
                ),
            ),
            total_chars=37,
        )

    def context_eval(self, summary_lines):
        return f"lines={len(summary_lines)}"


async def test_wake_cycle_uses_content_snippet_and_writes_receipt(tmp_path: Path) -> None:
    _make_agent(tmp_path)
    calls: list[str] = []

    async def runner(task: str):
        calls.append(task)
        return "bounded task", "reply with dharma evidence"

    result = await holon_wake_cycle(
        "codex_composer",
        runner,
        spent_usd=0.0,
        cap_usd=10.0,
        agents_root=tmp_path,
        memory_kernel=_SnippetMemory(),
    )

    assert result["status"] == "ran"
    assert result["context_injected"] is True
    assert "continuity requires receipt evidence" in calls[0]
    assert result["receipt_refs"]
    assert Path(result["receipt_refs"][0]).exists()


async def test_loop_survives_restart_and_halts_on_kill(tmp_path: Path) -> None:
    _make_agent(tmp_path, name="h")

    async def runner(task: str):
        return "task", "reply"

    first = await run_holon_loop("h", runner, max_cycles=2, agents_root=tmp_path)
    assert [item["status"] for item in first] == ["ran", "ran"]
    assert persistence.resume_point("h", agents_root=tmp_path)["cycle"] == 1

    killswitch.request_kill("h", agents_root=tmp_path)
    second = await run_holon_loop("h", runner, max_cycles=2, agents_root=tmp_path)
    assert second[0]["status"] == "halted:kill"


async def test_runtime_returns_cycle_result_and_artifact_gate(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    holon = load_holon("h", agents_root=agents_root)
    runtime = HolonRuntime(holon, agents_root=agents_root)

    result = await runtime.run_provider_cycle("created a report")

    assert isinstance(result, HolonCycleResult)
    assert result.status == "halted:unverified"
    assert result.provider_attempts[0].provider == "echo"
    assert result.receipt_refs and Path(result.receipt_refs[0]).exists()


async def test_runtime_honors_echo_identity_even_when_env_has_live_keys(tmp_path: Path, monkeypatch) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    runtime = HolonRuntime(load_holon("h", agents_root=agents_root), agents_root=agents_root)

    assert runtime.provider_router.providers[0].name == "echo"


async def test_runtime_accepts_artifact_backed_outcome(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    artifact = ArtifactRef(kind="file", path=str(tmp_path / "out.json"), digest="sha256:abc")

    class _ArtifactRouter:
        async def complete(self, request):
            return ProviderResponse(
                content="created report",
                provider="test",
                model="test-model",
                finish_reason="stop",
                cost_usd=0.0,
                attempts=[],
                artifacts=[artifact],
            )

    runtime = HolonRuntime(
        load_holon("h", agents_root=agents_root),
        agents_root=agents_root,
        provider_router=_ArtifactRouter(),
    )

    result = await runtime.run_provider_cycle("make artifact")

    assert result.status == "ran"
    assert result.artifacts == [artifact]


async def test_runtime_executes_provider_tool_call_envelope(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")

    class _ToolRouter:
        async def complete(self, request):
            return ProviderResponse(
                content=json.dumps(
                    {
                        "content": "created report",
                        "tool_calls": [
                            {
                                "name": "write_artifact",
                                "arguments": {
                                    "name": "tool-result.json",
                                    "content": {"ok": True},
                                },
                            }
                        ],
                    },
                    sort_keys=True,
                ),
                provider="test",
                model="test-model",
                finish_reason="tool_calls",
                cost_usd=0.01,
                attempts=[],
            )

    runtime = HolonRuntime(
        load_holon("h", agents_root=agents_root),
        agents_root=agents_root,
        provider_router=_ToolRouter(),
    )

    result = await runtime.run_provider_cycle("make artifact")

    assert result.status == "ran"
    assert result.reply == "created report"
    assert result.cost_usd == 0.01
    assert result.tool_calls[0].name == "write_artifact"
    assert result.tool_calls[0].status == "success"
    assert result.artifacts and Path(result.artifacts[0].path).exists()


async def test_runtime_halts_when_provider_tool_call_fails(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")

    class _BadToolRouter:
        async def complete(self, request):
            return ProviderResponse(
                content=json.dumps(
                    {
                        "content": "created report",
                        "tool_calls": [{"name": "missing_tool", "arguments": {}}],
                    },
                    sort_keys=True,
                ),
                provider="test",
                model="test-model",
                finish_reason="tool_calls",
                cost_usd=0.0,
                attempts=[],
            )

    runtime = HolonRuntime(
        load_holon("h", agents_root=agents_root),
        agents_root=agents_root,
        provider_router=_BadToolRouter(),
    )

    result = await runtime.run_provider_cycle("make artifact")

    assert result.status == "halted:tool"
    assert result.metadata["tool_call_failure"] is True
    assert result.tool_calls[0].status == "failed"


async def test_runtime_records_post_provider_budget_overrun(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")

    class _CostRouter:
        async def complete(self, request):
            return ProviderResponse(
                content="reply",
                provider="test",
                model="test-model",
                finish_reason="stop",
                cost_usd=0.25,
                attempts=[],
            )

    runtime = HolonRuntime(
        load_holon("h", agents_root=agents_root),
        agents_root=agents_root,
        provider_router=_CostRouter(),
    )

    result = await runtime.run_provider_cycle("budget check", spent_usd=0.0, cap_usd=0.1)

    assert result.status == "halted:budget"
    assert result.cost_usd == 0.25
    assert result.metadata["spent_usd"] == 0.25


async def test_provider_router_propagates_cost_and_enforces_cap() -> None:
    class _CostProvider:
        name = "cost-provider"
        model = "cost-model"

        async def complete(self, request):
            return ProviderResponse(
                content="reply",
                provider=self.name,
                model=self.model,
                finish_reason="stop",
                cost_usd=0.25,
                attempts=[],
            )

    request = LLMRequest(model="cost-model", messages=[{"role": "user", "content": "hi"}])
    response = await ProviderRouter([_CostProvider()], max_cost_usd=1.0).complete(request)
    assert response.cost_usd == 0.25
    assert response.attempts[0].cost_usd == 0.25

    with pytest.raises(RuntimeError, match="all providers failed"):
        await ProviderRouter([_CostProvider()], max_cost_usd=0.1).complete(request)


def test_usage_cost_estimator_prefers_reported_cost() -> None:
    usage = {"prompt_tokens": 1_000, "completion_tokens": 1_000, "cost_usd": "0.123"}

    assert estimate_usage_cost_usd(
        usage,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=1.0,
    ) == 0.123
    assert usage["cost_usd_source"] == "cost_usd"


def test_usage_cost_estimator_uses_configured_token_pricing() -> None:
    usage = {"prompt_tokens": 2_000, "completion_tokens": 500}

    cost = estimate_usage_cost_usd(
        usage,
        input_cost_per_mtok=2.0,
        output_cost_per_mtok=8.0,
    )

    assert cost == pytest.approx(0.008)
    assert usage["cost_usd_estimated"] == pytest.approx(0.008)
    assert usage["cost_usd_source"] == "configured_token_pricing"


def test_usage_cost_estimator_uses_total_token_fallback() -> None:
    usage = {"total_tokens": 2_500}

    cost = estimate_usage_cost_usd(usage, total_cost_per_mtok=4.0)

    assert cost == pytest.approx(0.01)
    assert usage["cost_usd_source"] == "configured_token_pricing"


def test_build_provider_router_wires_configured_pricing() -> None:
    router = build_provider_router(
        {
            "OPENAI_API_KEY": "test-key",
            "HOLON_OPENAI_INPUT_USD_PER_1M_TOKENS": "3",
            "HOLON_OPENAI_OUTPUT_USD_PER_1M_TOKENS": "9",
            "HOLON_PROVIDER_RETRIES": "1",
        },
        preferred_provider="openai",
        model="test-model",
    )

    provider = router.providers[0]
    assert provider.name == "openai"
    assert getattr(provider, "input_cost_per_mtok") == 3.0
    assert getattr(provider, "output_cost_per_mtok") == 9.0


async def test_provider_halt_does_not_write_compass_signal(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    runtime = HolonRuntime(load_holon("h", agents_root=agents_root), agents_root=agents_root)
    killswitch.request_kill("h", agents_root=agents_root)

    result = await runtime.run_provider_cycle("stop")

    assert result.status == "halted:kill"
    assert not (agents_root / "h" / "compass_signals.jsonl").exists()


async def test_supervisor_resumes_next_cycle(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    config = SupervisorConfig(name="h", prompt="report evidence", max_cycles=1, agents_root=agents_root)

    first = await run_supervisor(config)
    second = await run_supervisor(config)

    assert first["results"][0]["cycle"] == 0
    assert second["results"][0]["cycle"] == 1


async def test_supervisor_writes_hash_chained_heartbeat_and_releases_lock(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    config = SupervisorConfig(name="h", prompt="report evidence", max_cycles=1, agents_root=agents_root)

    result = await run_supervisor(config)

    heartbeat_path = service.service_heartbeat_path("h", agents_root=agents_root)
    ledger_ok, errors = service.verify_service_heartbeat_ledger(heartbeat_path)
    latest = service.latest_service_heartbeat("h", agents_root=agents_root)
    liveness = service.assess_service_liveness("h", agents_root=agents_root)
    assert result["status"] == "completed"
    assert result["lock"]["released"] is True
    assert not service.supervisor_lock_path("h", agents_root=agents_root).exists()
    assert ledger_ok, errors
    assert latest["status"] == "idle"
    assert liveness["service_alive"] is True


async def test_supervisor_reports_lock_held_without_running_cycle(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    lock = service.acquire_service_lock(
        "h",
        agents_root=agents_root,
        holder="test-holder",
        lease_seconds=60,
    )
    assert lock.acquired is True
    try:
        result = await run_supervisor(
            SupervisorConfig(name="h", prompt="report evidence", max_cycles=1, agents_root=agents_root)
        )
    finally:
        service.release_service_lock(lock)

    assert result["status"] == "lock_held"
    assert result["results"] == []
    assert result["lock"]["reason"] == "lock_held"
    assert Path(result["receipt"]["path"]).exists()
    latest = service.latest_service_heartbeat("h", agents_root=agents_root)
    assert latest["status"] == "paused"
    assert latest["claim_scope"]["lock_held"] is True


async def test_burn_in_writes_receipt_and_does_not_overclaim_multi_hour(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")

    result = await run_burn_in(
        BurnInConfig(
            name="h",
            prompt="observe continuity",
            duration_seconds=0.0,
            interval_seconds=0.0,
            min_cycles=2,
            agents_root=agents_root,
            multi_hour_threshold_seconds=3600.0,
        )
    )

    assert result["status"] == "pass"
    assert result["passed"] is True
    assert result["multi_hour_proven"] is False
    assert result["sample_count"] == 2
    assert result["failed_sample_count"] == 0
    assert result["source_proof"]["source_tree_digest"].startswith("sha256:")
    assert Path(result["receipt"]["path"]).exists()
    assert all(Path(sample["receipt"]["path"]).exists() for sample in result["samples"])


def test_package_source_proof_hashes_holon_sources() -> None:
    proof = package_source_proof()

    assert proof["schema_version"] == "holon.source_proof.v1"
    assert proof["source_tree_digest"].startswith("sha256:")
    assert proof["file_count"] > 0
    assert any(item["path"] == "holon_runtime.py" for item in proof["files"])


def test_service_lock_recovers_expired_lock(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    lock_path = service.supervisor_lock_path("h", agents_root=agents_root)
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": "holon.service_lock.v1",
                "holon": "h",
                "holder": "old",
                "lock_id": "old-lock",
                "acquired_at": "2026-06-25T00:00:00Z",
                "expires_at": (
                    datetime.now(UTC) - timedelta(seconds=30)
                ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    lock = service.acquire_service_lock(
        "h",
        agents_root=agents_root,
        holder="new-holder",
        lease_seconds=60,
    )

    assert lock.acquired is True
    assert service.release_service_lock(lock) is True


def test_receipt_id_is_idempotent_by_side_effect_key(tmp_path: Path) -> None:
    first = build_receipt(
        kind="cycle",
        subject="h",
        status="ran",
        side_effect_key="same-effect",
        payload={"at": "one"},
    )
    second = build_receipt(
        kind="cycle",
        subject="h",
        status="ran",
        side_effect_key="same-effect",
        payload={"at": "two"},
    )

    assert first.receipt_id == second.receipt_id
    first_ref = write_receipt(first, agents_root=tmp_path, holon_name="h")
    second_ref = write_receipt(second, agents_root=tmp_path, holon_name="h")
    assert first_ref["path"] == second_ref["path"]


def test_tool_registry_returns_artifact_ref(tmp_path: Path) -> None:
    result = default_tool_registry(artifact_root=tmp_path).run(
        "write_artifact",
        {"name": "report.json", "content": {"ok": True}},
    )

    assert result.record.status == "success"
    assert result.artifact is not None
    assert Path(result.artifact.path).exists()


def test_memory_kernel_reads_local_jsonl(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path, name="h")
    memory = agents_root / "h" / "memory.jsonl"
    memory.write_text(json.dumps({"content": "remember the receipt chain"}) + "\n", encoding="utf-8")

    pack = MemoryKernel(agents_root=agents_root, holon="h").preview_memory_pack()

    assert pack.items
    assert pack.items[0].content_snippet == "remember the receipt chain"


def test_a2a_ping_writes_three_receipts(tmp_path: Path) -> None:
    _make_agent(tmp_path, name="h")
    for name in ["a", "b", "c"]:
        _make_agent(tmp_path, name=name)

    results = ping_agents(holon_name="h", agents_root=tmp_path, min_agents=3)

    assert len(results) == 3
    assert all(result.status == "pass" for result in results)
    assert all(Path(result.receipt_path).exists() for result in results)


def test_strict_isolation_verifier_passes() -> None:
    report = verify_standalone()

    assert report.status == "pass", report.to_dict()


def test_strict_isolation_verifier_rejects_dynamic_parent_import(tmp_path: Path) -> None:
    for name in ["pyproject.toml", "README.md", "cli.py", "holon_runtime.py", "receipts.py"]:
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "bad.py").write_text(
        "import importlib\nimportlib.import_module('dharma_swarm.holon_runtime')\n",
        encoding="utf-8",
    )

    report = verify_standalone(tmp_path)

    assert report.status == "fail"
    assert any(item.code == "forbidden_dynamic_parent_import" for item in report.findings)


def test_build_backend_metadata_preserves_project_extras(tmp_path: Path) -> None:
    wheel_name = _build_backend.build_wheel(tmp_path)
    with zipfile.ZipFile(tmp_path / wheel_name) as wheel:
        metadata = wheel.read("holon_runtime-0.1.0.dist-info/METADATA").decode("utf-8")

    assert "Metadata-Version: 2.4" in metadata
    assert "Provides-Extra: dev" in metadata
    assert 'Requires-Dist: pytest>=7.0; extra == "dev"' in metadata
