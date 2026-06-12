from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dharma_swarm.models import LLMRequest, LLMResponse
from dharma_swarm.operator_core.living_agent_kernel import (
    AgentRunEnvelope,
    KernelRunStore,
    KernelTask,
    LivingAgentKernel,
    MemoryPlan,
    ProofRequest,
    ToolRequest,
    TriggerEnvelope,
)
from dharma_swarm.operator_core.living_agent_kernel_promotion import KernelPromotionStore
from dharma_swarm.operator_core.living_agent_kernel_provider_worker import (
    KernelProviderWorkerStore,
    evaluate_provider_tool_boundary,
    execute_provider_worker_cycle_sync,
)
from dharma_swarm.operator_core.living_agent_kernel_status import living_agent_os_status
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def _envelope(
    correlation_id: str,
    *,
    source: str = "manual",
    requested_tools: list[str] | None = None,
    tool_calls: list[dict] | None = None,
) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="promoted_agent",
        task=KernelTask(text=f"Provider wake {correlation_id}"),
        trigger=TriggerEnvelope(source=source, correlation_id=correlation_id),
        memory=MemoryPlan(read_namespaces=["agent:promoted_agent:working"]),
        tool_request=ToolRequest(
            requested_tools=requested_tools or ["session_status"],
            tool_calls=tool_calls or [],
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_promotion_provider.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


def _promote_provider_agent(store_dir: Path, *, agent_uid: str = "promoted_agent"):
    return KernelPromotionStore(store_dir).append_promotion(
        agent_uid=agent_uid,
        level="provider_executor",
        allowed_sources=["manual"],
        allowed_tools=["provider_complete"],
        allowed_work_kinds=["provider_execution"],
        max_lease_seconds=30,
        reviewer="test",
        reason="fixture promotion",
        evidence_refs=[{"kind": "holdout_eval_receipt", "path": "holdout.json"}],
        now="2026-06-06T00:00:00Z",
    )


def test_promotion_allows_provider_worker_with_reduced_authority(tmp_path):
    store = KernelPromotionStore(tmp_path / "kernel")
    receipt = store.append_promotion(
        agent_uid="agent-a",
        level="provider_executor",
        allowed_sources=["manual", "manual"],
        allowed_tools=["provider_complete"],
        allowed_work_kinds=["provider_execution"],
        max_lease_seconds=12,
        evidence_refs=[{"kind": "holdout_eval_receipt"}],
        now="2026-06-06T00:00:00Z",
    )

    admission = store.evaluate_worker_admission(
        agent_uid="agent-a",
        requested_level="provider_executor",
        source="manual",
        requested_tools=["provider_complete"],
        work_kind="provider_execution",
        requested_lease_seconds=300,
        now="2026-06-06T00:00:01Z",
    )
    ok, errors = store.verify_promotion_ledger()

    assert receipt.record_hash.startswith("sha256:")
    assert admission.decision == "allowed"
    assert admission.reduced_worker_authority["max_lease_seconds"] == 12
    assert admission.reduced_worker_authority["allowed_sources"] == ["manual"]
    assert admission.promotion_ref["record_hash"] == receipt.record_hash
    assert ok, errors


def test_promotion_blocks_missing_expired_and_revoked_authority(tmp_path):
    store = KernelPromotionStore(tmp_path / "kernel")
    missing = store.evaluate_worker_admission(
        agent_uid="agent-missing",
        requested_level="provider_executor",
        requested_tools=["provider_complete"],
        work_kind="provider_execution",
        now="2026-06-06T00:00:00Z",
    )
    store.append_promotion(
        agent_uid="agent-expired",
        level="provider_executor",
        allowed_sources=["manual"],
        allowed_tools=["provider_complete"],
        allowed_work_kinds=["provider_execution"],
        expires_at="2026-06-05T00:00:00Z",
        evidence_refs=[{"kind": "holdout_eval_receipt"}],
        now="2026-06-04T00:00:00Z",
    )
    expired = store.evaluate_worker_admission(
        agent_uid="agent-expired",
        requested_level="provider_executor",
        source="manual",
        requested_tools=["provider_complete"],
        work_kind="provider_execution",
        now="2026-06-06T00:00:00Z",
    )
    store.append_promotion(
        agent_uid="agent-revoked",
        level="provider_executor",
        allowed_sources=["manual"],
        allowed_tools=["provider_complete"],
        allowed_work_kinds=["provider_execution"],
        evidence_refs=[{"kind": "holdout_eval_receipt"}],
        now="2026-06-06T00:00:00Z",
    )
    store.revoke_promotion(agent_uid="agent-revoked", now="2026-06-06T00:00:01Z")
    revoked = store.evaluate_worker_admission(
        agent_uid="agent-revoked",
        requested_level="provider_executor",
        source="manual",
        requested_tools=["provider_complete"],
        work_kind="provider_execution",
        now="2026-06-06T00:00:02Z",
    )

    assert missing.decision == "blocked"
    assert "promotion_receipt_missing" in missing.reasons
    assert expired.decision == "blocked"
    assert "promotion_expired" in expired.reasons
    assert revoked.decision == "blocked"
    assert "promotion_revoked" in revoked.reasons


def test_provider_worker_denies_without_promotion_and_leaves_wake_queued(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("no-promotion"), wake_id="wake-no-promotion")

    result = execute_provider_worker_cycle_sync(
        store_dir=store_dir,
        workspace_root=tmp_path,
        worker_id="provider-worker",
        agent_uid="promoted_agent",
        provider="openrouter_free",
        model="fixture-model",
        allowed_sources=["manual"],
        fixture_response="should not run",
        now="2026-06-06T00:00:00Z",
    )
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-no-promotion"]
    receipts = KernelProviderWorkerStore(store_dir).receipts()

    assert result.status == "denied"
    assert result.admission.decision == "blocked"
    assert latest.status == "queued"
    assert receipts[0].status == "denied"
    assert receipts[0].error == "promotion_receipt_missing"


def test_provider_tool_boundary_records_context_only_tool_visibility(tmp_path):
    store_dir = tmp_path / "kernel"
    receipt = _promote_provider_agent(store_dir)
    wake = KernelRunStore(store_dir).enqueue_wake(
        _envelope(
            "tool-boundary",
            requested_tools=["session_status", "read_file"],
            tool_calls=[{"name": "read_file", "arguments": {"path": "README.md"}}],
        ),
        wake_id="wake-tool-boundary",
        now="2026-06-06T00:00:00Z",
    )
    admission = KernelPromotionStore(store_dir).evaluate_worker_admission(
        agent_uid="promoted_agent",
        requested_level="provider_executor",
        source="manual",
        requested_tools=["provider_complete"],
        work_kind="provider_execution",
        now="2026-06-06T00:00:01Z",
    )

    boundary = evaluate_provider_tool_boundary(
        wake,
        worker_id="provider-worker",
        agent_uid="promoted_agent",
        admission=admission,
    )

    assert receipt.allowed_tools == ["provider_complete"]
    assert boundary.provider_may_execute_tools is False
    assert boundary.delegated_tools == ["provider_complete"]
    assert boundary.requested_wake_tools == ["read_file", "session_status"]
    assert boundary.requested_tool_call_names == ["read_file"]
    assert boundary.denied_delegated_tools == ["read_file", "session_status"]
    assert boundary.context_visible_tools == ["read_file", "session_status"]


def test_promoted_provider_worker_executes_wake_with_fixture_response(tmp_path):
    store_dir = tmp_path / "kernel"
    _promote_provider_agent(store_dir)
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("fixture"), wake_id="wake-fixture")

    result = execute_provider_worker_cycle_sync(
        store_dir=store_dir,
        workspace_root=tmp_path,
        worker_id="provider-worker",
        agent_uid="promoted_agent",
        provider="openrouter_free",
        model="fixture-model",
        allowed_sources=["manual"],
        fixture_response="Provider fixture completed the wake.",
        now="2026-06-06T00:00:01Z",
    )
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-fixture"]
    provider_store = KernelProviderWorkerStore(store_dir)
    worker_store = KernelExternalWorkerStore(store_dir)
    provider_ok, provider_errors = provider_store.verify_provider_worker_ledger()
    worker_ok, worker_errors = worker_store.verify_worker_ledgers()
    wake_ok, wake_errors = KernelRunStore(store_dir).verify_wake_ledger()

    assert result.status == "completed"
    assert latest.status == "completed"
    assert latest.result_ref["kind"] == "external_worker_result"
    assert latest.result_ref["payload_ref"]["kind"] == "kernel_provider_worker_result"
    assert latest.result_ref["payload_ref"]["provider_execution"] is True
    assert latest.result_ref["payload_ref"]["provider"] == "openrouter_free"
    provider_receipt = provider_store.receipts()[0]
    assert provider_receipt.response_content == "Provider fixture completed the wake."
    assert provider_receipt.tool_boundary["provider_may_execute_tools"] is False
    assert provider_receipt.tool_boundary["delegated_tools"] == ["provider_complete"]
    assert provider_receipt.tool_boundary["denied_delegated_tools"] == ["session_status"]
    assert latest.result_ref["payload_ref"]["tool_boundary"]["provider_may_execute_tools"] is False
    assert provider_ok, provider_errors
    assert worker_ok, worker_errors
    assert wake_ok, wake_errors


def test_provider_worker_accepts_injected_async_provider_client(tmp_path):
    store_dir = tmp_path / "kernel"
    _promote_provider_agent(store_dir)
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("client"), wake_id="wake-client")
    fake = _FakeProvider()

    result = execute_provider_worker_cycle_sync(
        store_dir=store_dir,
        workspace_root=tmp_path,
        worker_id="provider-worker",
        agent_uid="promoted_agent",
        provider="openrouter_free",
        model="fixture-model",
        allowed_sources=["manual"],
        provider_client=fake,
        now="2026-06-06T00:00:01Z",
    )

    assert result.status == "completed"
    assert len(fake.requests) == 1
    assert fake.requests[0].model == "fixture-model"
    assert "Provider wake client" in fake.requests[0].messages[0]["content"]
    request_payload = json.loads(fake.requests[0].messages[0]["content"])
    assert request_payload["tool_request"]["provider_may_execute_tools"] is False
    assert request_payload["provider_tool_boundary"]["provider_may_execute_tools"] is False
    assert request_payload["provider_tool_boundary"]["denied_delegated_tools"] == ["session_status"]


def test_provider_worker_cli_and_os_status_surface(tmp_path):
    store_dir = tmp_path / "kernel"
    promotion_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_promotion.py"
    provider_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_provider_worker.py"
    status_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_status.py"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("cli"), wake_id="wake-cli")

    promoted = subprocess.run(
        [
            sys.executable,
            str(promotion_script),
            "--store-dir",
            str(store_dir),
            "promote",
            "--agent-uid",
            "promoted_agent",
            "--level",
            "provider_executor",
            "--allowed-source",
            "manual",
            "--allowed-tool",
            "provider_complete",
            "--allowed-work-kind",
            "provider_execution",
            "--max-lease-seconds",
            "30",
            "--evidence-kind",
            "holdout_eval_receipt",
            "--now",
            "2026-06-06T00:00:00Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    ran = subprocess.run(
        [
            sys.executable,
            str(provider_script),
            "--store-dir",
            str(store_dir),
            "--workspace-root",
            str(tmp_path),
            "--worker-id",
            "cli-provider-worker",
            "--agent-uid",
            "promoted_agent",
            "--provider",
            "openrouter_free",
            "--model",
            "fixture-model",
            "--allowed-source",
            "manual",
            "--fixture-response",
            "CLI provider worker completed.",
            "--now",
            "2026-06-06T00:00:01Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        [
            sys.executable,
            str(status_script),
            "--store-dir",
            str(store_dir),
            "--now",
            "2026-06-06T00:00:02Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    promoted_payload = json.loads(promoted.stdout)
    ran_payload = json.loads(ran.stdout)
    status_payload = json.loads(status.stdout)
    direct_status = living_agent_os_status(store_dir=store_dir, now="2026-06-06T00:00:02Z")

    assert promoted_payload["record_hash"].startswith("sha256:")
    assert ran_payload["cycles"][0]["status"] == "completed"
    assert status_payload["provider_worker_receipt_count"] == 1
    assert status_payload["wake_snapshot"]["terminal_wake_ids"] == ["wake-cli"]
    assert status_payload["worker_states"][0]["status"] == "online"
    assert status_payload["ledger_integrity"]["provider_worker"]["ok"] is True
    assert direct_status.provider_worker_receipt_count == 1


class _FakeProvider:
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            content="Injected provider completed the wake.",
            model=request.model,
            provider="openrouter_free",
            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            stop_reason="stop",
        )
