"""Tests for dharma_swarm.orchestrator."""

import ast
import asyncio
import hashlib
import inspect
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from dharma_swarm.models import (
    AgentConfig,
    AgentRole,
    AgentState,
    AgentStatus,
    GateCheckResult,
    GateDecision,
    LLMRequest,
    LLMResponse,
    Message,
    ProviderType,
    Task,
    TaskDispatch,
    TaskStatus,
    TopologyType,
)
from dharma_swarm.agent_runner import (
    AgentPool,
    AgentRunner,
    _campaign_provider_result_is_exact,
    _prepend_organism_genome,
)
from dharma_swarm.campaign_provider_guard import CampaignProviderEffectBoundary
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.providers import ModelRouter, OllamaProvider, _ollama_cloud_wire_model
from dharma_swarm.ollama_config import get_ollama_cloud_frontier_chain
from dharma_swarm.resilience import RetryPolicy
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine import ExecutionIdentity, identity_metadata


def _ensure_fixture_execution_identity(td, *, task=None, require=False):
    raw = {**dict(getattr(task, "metadata", {}) or {}), **dict(td.metadata)}
    identity = ExecutionIdentity.new(
        task_id=td.task_id,
        agent_id=td.agent_id,
        session_id=str(raw.get("session_id") or "fixture-session"),
        trace_id=str(raw.get("trace_id") or f"trace-{td.task_id}"),
        correlation_id=str(raw.get("correlation_id") or f"corr-{td.task_id}"),
        causation_id=str(raw.get("causation_id") or ""),
        parent_run_id=str(raw.get("parent_run_id") or ""),
        run_id=str(raw.get("run_id") or raw.get("runtime_run_id") or f"run-{td.task_id}"),
        claim_id=str(raw.get("claim_id") or f"claim-{td.task_id}"),
        idempotency_key=str(raw.get("idempotency_key") or f"idem-{td.task_id}"),
    ).require_for_dispatch()
    metadata = identity_metadata(identity, surface="fixture")
    td.metadata.update(metadata)
    if task is not None:
        task.metadata = {**dict(task.metadata), **metadata}
    return identity


def test_orchestrator_execution_helper_import_leaf_both_orders() -> None:
    root = Path(__file__).resolve().parents[1]
    helper_path = root / "dharma_swarm" / "orchestrator_execution.py"
    tree = ast.parse(helper_path.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "dharma_swarm.orchestrator" not in imported_modules | imported_from

    orders = [
        (
            "import dharma_swarm.orchestrator_execution as helper; "
            "import dharma_swarm.orchestrator as host"
        ),
        (
            "import dharma_swarm.orchestrator as host; "
            "import dharma_swarm.orchestrator_execution as helper"
        ),
    ]
    for imports in orders:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                imports
                + "; assert host.Orchestrator._execute_task.__module__ "
                "== 'dharma_swarm.orchestrator'; assert callable(helper.execute_task)",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


@pytest.mark.asyncio
async def test_orchestrator_execution_helper_preserves_host_surface(monkeypatch) -> None:
    from dharma_swarm import orchestrator as host
    from dharma_swarm import orchestrator_execution as helper

    signature = inspect.signature(Orchestrator._execute_task)
    assert str(signature) == (
        "(self, runner: 'Any', task: 'Task', td: 'TaskDispatch') -> 'None'"
    )
    campaign_signature = inspect.signature(Orchestrator._execute_campaign_task)
    assert str(campaign_signature) == (
        "(self, runner: 'Any', task: 'Task', td: 'TaskDispatch', *, "
        "campaign_effect_fence: 'Callable[[], Awaitable[None]] | None' = None, "
        "campaign_effect_ready: 'Callable[[], None] | None' = None, "
        "campaign_principal: 'str' = '', "
        "campaign_reservation_token: 'dict[str, Any] | None' = None) -> 'None'"
    )
    assert list(signature.parameters) == ["self", "runner", "task", "td"]
    assert list(campaign_signature.parameters) == [
        "self",
        "runner",
        "task",
        "td",
        "campaign_effect_fence",
        "campaign_effect_ready",
        "campaign_principal",
        "campaign_reservation_token",
    ]
    assert (
        campaign_signature.parameters["campaign_effect_fence"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
    assert (
        campaign_signature.parameters["campaign_effect_ready"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
    assert (
        campaign_signature.parameters["campaign_principal"].kind
        is inspect.Parameter.KEYWORD_ONLY
    )
    assert Orchestrator._execute_task.__module__ == "dharma_swarm.orchestrator"
    assert Orchestrator.__mro__ == (Orchestrator, object)
    assert host.TaskBoard.__module__ == "dharma_swarm.orchestrator"
    assert host.AgentPool.__module__ == "dharma_swarm.orchestrator"
    assert isinstance(object(), host.TaskBoard) is False
    assert isinstance(object(), host.AgentPool) is False

    invoked = AsyncMock()
    sentinel_logger = object()
    monkeypatch.setattr(helper, "execute_task", invoked)
    monkeypatch.setattr(host, "logger", sentinel_logger)
    orchestrator = object.__new__(Orchestrator)
    runner = object()
    task = Task(id="helper-task", title="helper")
    dispatch = TaskDispatch(task_id=task.id, agent_id="helper-agent")

    await orchestrator._execute_task(runner, task, dispatch)
    invoked.assert_awaited_once_with(
        orchestrator,
        runner,
        task,
        dispatch,
        logger=sentinel_logger,
    )

    invoked.reset_mock()
    await orchestrator._execute_campaign_task(
        runner,
        task,
        dispatch,
        campaign_principal="helper-agent",
    )

    invoked.assert_awaited_once_with(
        orchestrator,
        runner,
        task,
        dispatch,
        campaign_effect_fence=None,
        campaign_effect_ready=None,
        campaign_principal="helper-agent",
        campaign_reservation_token=None,
        logger=sentinel_logger,
    )


def test_orchestrator_execution_helper_preserves_operation_order() -> None:
    helper_path = (
        Path(__file__).resolve().parents[1]
        / "dharma_swarm"
        / "orchestrator_execution.py"
    )
    tree = ast.parse(helper_path.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "execute_task"
    )
    calls: dict[str, list[int]] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        calls.setdefault(name, []).append(node.lineno)

    first_run = min(
        calls["self._run_task_via_spine"][0],
        calls["runner.run_task"][0],
    )
    delegation_lines = sorted(
        calls["self._runtime_lifecycle.record_delegation_run"]
    )
    assert calls["asyncio.sleep"][0] < delegation_lines[0] < first_run
    terminal_line = calls["record_terminal_projection"][0]
    release_after_terminal = min(
        line for line in calls["release_dispatch_owner"] if line > terminal_line
    )
    assert first_run < terminal_line < release_after_terminal
    assert terminal_line < calls["self._persist_result"][0]
    terminal = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "record_terminal_projection"
    )
    terminal_calls: dict[str, list[int]] = {}
    for node in ast.walk(terminal):
        if isinstance(node, ast.Call):
            terminal_calls.setdefault(ast.unparse(node.func), []).append(node.lineno)
    assert (
        max(terminal_calls["self._runtime_lifecycle.record_task_claim"])
        < max(terminal_calls["self._runtime_lifecycle.record_delegation_run"])
        < terminal_calls["settle_task_board"][0]
    )
    lifecycle_try = next(
        node
        for node in function.body
        if isinstance(node, ast.Try)
        and any(
            isinstance(child, ast.Call)
            and ast.unparse(child.func)
            == "self._runtime_lifecycle.record_delegation_run"
            for child in ast.walk(node)
        )
    )
    handler_names = {
        ast.unparse(handler.type)
        for handler in lifecycle_try.handlers
        if handler.type is not None
    }
    assert handler_names == {
        "asyncio.TimeoutError",
        "asyncio.CancelledError",
        "Exception",
    }
    cancelled_handler = next(
        handler
        for handler in lifecycle_try.handlers
        if handler.type is not None
        and ast.unparse(handler.type) == "asyncio.CancelledError"
    )
    released_cancel = cancelled_handler.body[0]
    assert isinstance(released_cancel, ast.If)
    assert ast.unparse(released_cancel.test) == "dispatch_owner_released"
    assert len(released_cancel.body) == 1
    assert isinstance(released_cancel.body[0], ast.Raise)
    generic_cancel = cancelled_handler.body[1]
    assert isinstance(generic_cancel, ast.If)
    assert ast.unparse(generic_cancel.test) == "not campaign_owner"
    assert len(generic_cancel.body) == 2
    cleanup_source = ast.unparse(generic_cancel.body[0])
    assert "await shield_recovery" in cleanup_source
    assert "abort_generic_dispatch_setup(self, td, cause)" in cleanup_source
    assert "release_generic_dispatch" not in cleanup_source
    assert isinstance(generic_cancel.body[1], ast.Raise)
    assert lifecycle_try.finalbody
    spine_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "self._run_task_via_spine"
    ]
    assert len(spine_calls) == 2
    assert all(len(node.args) == 4 for node in spine_calls)
    assert sorted(
        sorted(keyword.arg for keyword in node.keywords if keyword.arg is not None)
        for node in spine_calls
    ) == [
        ["campaign_effect_fence", "campaign_effect_ready", "campaign_fail_closed"],
        ["campaign_fail_closed"],
    ]
    sidecar_guards = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "not campaign_principal"
        and any(
            isinstance(child, ast.Call)
            and ast.unparse(child.func) == "SleepTimeAgent"
            for child in ast.walk(node)
        )
    ]
    assert len(sidecar_guards) == 1
    assert sidecar_guards[0] in set(ast.walk(lifecycle_try))


@pytest.mark.asyncio
async def test_generic_cancellation_quarantines_before_release() -> None:
    agent = AgentState(
        id="generic-cancel-agent",
        name="generic-cancel-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.BUSY,
        current_task="generic-cancel-task",
    )
    task = Task(id="generic-cancel-task", title="Generic cancellation fixture")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    pool.release = AsyncMock()  # type: ignore[method-assign]
    entered = asyncio.Event()
    never_complete = asyncio.Event()

    class _BlockedRunner:
        async def run_task(self, _task):
            entered.set()
            await never_complete.wait()
            raise AssertionError("unreachable")

    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    orchestrator._handle_task_failure = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: False  # type: ignore[method-assign]
    orchestrator._active_dispatches[task.id] = dispatch
    execution = asyncio.create_task(
        orchestrator._execute_task(_BlockedRunner(), task, dispatch)
    )
    await asyncio.wait_for(entered.wait(), timeout=2)

    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(execution, timeout=2)

    pool.release.assert_not_awaited()  # type: ignore[attr-defined]
    orchestrator._handle_task_failure.assert_not_awaited()  # type: ignore[attr-defined]
    assert orchestrator._active_dispatches == {}
    assert orchestrator._generic_recovery_owners[id(dispatch)][0] is dispatch
    assert "cleanup is indeterminate" in orchestrator._generic_recovery_owners[
        id(dispatch)
    ][1]
    assert agent.status is AgentStatus.BUSY
    assert agent.current_task == task.id
    assert task.status is TaskStatus.PENDING
    assert board.updates == []


@pytest.mark.asyncio
async def test_graceful_stop_retains_exact_owner_when_cancellation_times_out() -> None:
    orchestrator = Orchestrator()
    started = asyncio.Event()
    cancellation_seen = asyncio.Event()
    release_stubborn_task = asyncio.Event()

    async def stubborn_work() -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellation_seen.set()
            await release_stubborn_task.wait()

    background = asyncio.create_task(stubborn_work())
    await started.wait()
    dispatch = TaskDispatch(task_id="stubborn-task", agent_id="stubborn-agent")
    orchestrator._running_tasks[dispatch.task_id] = background
    orchestrator._running_dispatch_owners[dispatch.task_id] = (
        background,
        dispatch,
    )
    orchestrator._active_dispatches[dispatch.task_id] = dispatch

    try:
        summary = await orchestrator.graceful_stop(timeout=0.01)
        await cancellation_seen.wait()

        assert summary["cancelled"] == 1
        assert summary["live_task_ids"] == [dispatch.task_id]
        assert summary["live_owners"] == {dispatch.task_id: dispatch.agent_id}
        assert orchestrator._running_tasks[dispatch.task_id] is background
        assert orchestrator._running_dispatch_owners[dispatch.task_id] == (
            background,
            dispatch,
        )
        assert orchestrator._active_dispatches[dispatch.task_id] is dispatch
        assert not background.done()

        release_stubborn_task.set()
        await background
        await orchestrator._collect_completed()
        assert dispatch.task_id not in orchestrator._running_tasks
        assert dispatch.task_id not in orchestrator._running_dispatch_owners
        assert dispatch.task_id not in orchestrator._active_dispatches
    finally:
        release_stubborn_task.set()
        if not background.done():
            background.cancel()
        await asyncio.gather(background, return_exceptions=True)


@pytest.mark.asyncio
async def test_graceful_stop_releases_cooperatively_cancelled_generic_owner() -> None:
    agent = AgentState(
        id="cooperative-agent",
        name="cooperative-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="cooperative-task", title="Cooperative cancellation")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    entered = asyncio.Event()

    class _CooperativeRunner:
        async def run_task(self, _task):
            entered.set()
            await asyncio.Event().wait()

    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    runner = _CooperativeRunner()
    pool.set_runner(agent.id, runner)
    assert await pool.reserve(agent.id, task.id, reservation_token=dispatch)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    orchestrator._spine_dispatch_enabled = lambda: False  # type: ignore[method-assign]
    orchestrator._active_dispatches[task.id] = dispatch
    background = asyncio.create_task(
        orchestrator._execute_task(runner, task, dispatch)
    )
    orchestrator._running_tasks[task.id] = background
    orchestrator._running_dispatch_owners[task.id] = (background, dispatch)
    await asyncio.wait_for(entered.wait(), timeout=2)

    summary = await orchestrator.graceful_stop(timeout=1)

    assert summary == {"cancelled": 1, "completed": 0, "recovered": 1}
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert agent.id not in pool._reservation_tokens
    assert task.id not in orchestrator._active_dispatches
    assert task.id not in orchestrator._running_tasks
    assert task.id not in orchestrator._running_dispatch_owners
    assert board.updates == []


@pytest.mark.asyncio
async def test_authenticated_campaign_cannot_use_legacy_direct_provider_path() -> None:
    task = Task(id="campaign-spine-required", title="Campaign spine boundary")
    runner = MagicMock()
    runner.run_task = AsyncMock(return_value="must not execute")
    dispatch = TaskDispatch(task_id=task.id, agent_id="campaign-agent")
    token = {
        "reservation_id": "campaign-spine-required-token",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    orchestrator = Orchestrator(task_board=MockTaskBoard(), agent_pool=None)
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    orchestrator._spine_dispatch_enabled = lambda: False  # type: ignore[method-assign]
    recovery_ticket = object()
    orchestrator._prepare_campaign_before_effect_recovery = MagicMock(  # type: ignore[method-assign]
        return_value=recovery_ticket
    )
    orchestrator._finish_campaign_before_effect_recovery = AsyncMock(  # type: ignore[method-assign]
        return_value=True
    )

    await orchestrator._execute_campaign_task(
        runner,
        task,
        dispatch,
        campaign_effect_fence=_allow_campaign_effect,
        campaign_effect_ready=lambda: None,
        campaign_principal="campaign-agent",
        campaign_reservation_token=token,
    )

    runner.run_task.assert_not_awaited()
    assert "evidence_receipt_id" not in dispatch.metadata
    assert token["provider_task_scheduled"] is False
    orchestrator._prepare_campaign_before_effect_recovery.assert_called_once_with(
        dispatch,
        "campaign-agent",
        token,
        allow_uninstalled_active=False,
    )
    orchestrator._finish_campaign_before_effect_recovery.assert_awaited_once_with(
        token,
        recovery_ticket,
    )


@pytest.mark.asyncio
async def test_authenticated_campaign_idempotency_begin_failure_blocks_runner(
    tmp_path: Path,
) -> None:
    task = Task(id="campaign-begin-failure", title="Campaign begin failure")
    dispatch = TaskDispatch(task_id=task.id, agent_id="campaign-agent")
    _ensure_fixture_execution_identity(dispatch, task=task, require=True)
    dispatch.metadata.pop("evidence_receipt_id", None)
    runner = MagicMock()
    runner.run_task = AsyncMock(return_value="must not execute")
    orchestrator = Orchestrator(runtime_db_path=tmp_path / "runtime.db")
    store = orchestrator._runtime_lifecycle._runtime_state_store()
    await store.init_db()
    store.try_begin_idempotent_side_effect_with_token = AsyncMock(
        side_effect=RuntimeError("durable begin unavailable")
    )

    with pytest.raises(RuntimeError, match="durable idempotency fence"):
        await orchestrator._run_task_via_spine(
            runner,
            task,
            dispatch,
            1.0,
            campaign_fail_closed=True,
        )

    runner.run_task.assert_not_awaited()
    assert "evidence_receipt_id" not in dispatch.metadata


@pytest.mark.asyncio
async def test_authenticated_campaign_rejects_failed_receipt_persistence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm.graph import durable_invoker

    task = Task(id="campaign-receipt-failure", title="Campaign receipt failure")
    dispatch = TaskDispatch(task_id=task.id, agent_id="campaign-agent")
    _ensure_fixture_execution_identity(dispatch, task=task, require=True)
    runner = SimpleNamespace(
        _config=None,
        run_task=AsyncMock(return_value="provider effect"),
    )
    orchestrator = Orchestrator(runtime_db_path=tmp_path / "runtime.db")
    await orchestrator._runtime_lifecycle._runtime_state_store().init_db()
    persist = AsyncMock(return_value=False)
    monkeypatch.setattr(durable_invoker, "persist_evidence_receipt", persist)

    with pytest.raises(RuntimeError, match="receipt persistence failed"):
        await orchestrator._run_task_via_spine(
            runner,
            task,
            dispatch,
            1.0,
            campaign_effect_fence=_allow_campaign_effect,
            campaign_effect_ready=lambda: None,
        )

    runner.run_task.assert_awaited_once()
    persist.assert_awaited_once()
    assert dispatch.metadata["evidence_receipt_status"] == "ok"


async def _allow_campaign_effect() -> None:
    return None


def _allow_campaign_boundary() -> CampaignProviderEffectBoundary:
    return CampaignProviderEffectBoundary(_allow_campaign_effect, lambda: None)


def _campaign_metadata(
    principal: str,
    *,
    task_id: str,
    provider: str = "local",
    model: str = "fixture-model",
) -> dict:
    campaign_id = "campaign-fixture"
    goal_id = "goal-fixture"
    portfolio = "sha256:" + "a" * 64
    goal_digest = "sha256:" + "b" * 64
    content = "Observed fixture state; verify independently.\n"
    content_sha256 = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    observed_ref = {
        "receipt_id": "observed-receipt-fixture",
        "receipt_sha256": "sha256:" + "1" * 64,
        "artifact_id": "observed-artifact-fixture",
        "artifact_record_sha256": "sha256:" + "2" * 64,
        "content_sha256": content_sha256,
    }
    observed_manifest = "sha256:" + "3" * 64
    held_out_oracle = "sha256:" + "4" * 64
    operator_control = "sha256:" + "5" * 64
    return {
        "campaign_id": campaign_id,
        "goal_id": goal_id,
        "portfolio_contract_sha256": portfolio,
        "goal_contract_sha256": goal_digest,
        "campaign_effect_mode": "read_only",
        "requires_tooling": False,
        "allow_provider_routing": False,
        "provider_allowlist": [provider],
        "preferred_provider": provider,
        "preferred_model": model,
        "attempt_ceiling": 3,
        "attempt_generation": 0,
        "mission_task_id": task_id,
        "mission_observed_input": {
            "schema_version": "dharma.sadhana.observed_input_prompt.v1",
            "campaign_id": campaign_id,
            "mission_id": campaign_id,
            "goal_id": goal_id,
            "task_id": task_id,
            "manifest_digest": observed_manifest,
            "goal_contract_sha256": goal_digest,
            "task_creation_hash": "6" * 64,
            "observed_at": "2026-08-23T00:00:00+00:00",
            "epistemic_state": "observed_unverified",
            "authority_scope": "prompt_context_only",
            "media_type": "text/markdown; charset=utf-8",
            "content": content,
            "content_sha256": content_sha256,
            "observed_input_ref": observed_ref,
        },
        "mission_control_governance": {
            "schema_version": "dharma.sadhana.campaign_governance.v4",
            "campaign_id": campaign_id,
            "mission_id": campaign_id,
            "goal_id": goal_id,
            "portfolio_contract_sha256": portfolio,
            "goal_contract_sha256": goal_digest,
            "manifest_digest": "sha256:" + "c" * 64,
            "agent_roster_sha256": "d" * 64,
            "effect_mode": "read_only",
            "campaign_end": "2026-09-02T00:00:00+00:00",
            "workspace_path": "workspaces/goal-fixture",
            "allowed_files": ["workspaces/goal-fixture/**"],
            "forbidden_files": [],
            "max_usd": 0.0,
            "attempt_generation": 0,
            "max_attempts": 3,
            "observed_input_manifest_digest": observed_manifest,
            "held_out_oracle_manifest_digest": held_out_oracle,
            "operator_control_semantics_sha256": operator_control,
            "operator_control_authority_binding_sha256": "sha256:" + "7" * 64,
            "deployment_authority_topology_sha256": "sha256:" + "8" * 64,
            "deployment_authority_credential_clarification_sha256": (
                "sha256:" + "9" * 64
            ),
            "observed_input_ref": observed_ref,
        },
        "mission_campaign_authority": {
            "schema_version": "dharma.sadhana.campaign_task_authority.v5",
            "campaign_id": campaign_id,
            "mission_id": campaign_id,
            "goal_id": goal_id,
            "portfolio_contract_sha256": portfolio,
            "goal_contract_sha256": goal_digest,
            "manifest_digest": "sha256:" + "c" * 64,
            "agent_roster_sha256": "d" * 64,
            "effect_mode": "read_only",
            "campaign_end": "2026-09-02T00:00:00+00:00",
            "agent_name": "campaign-seat",
            "claimed_principal": principal,
            "dispatch_key": "default",
            "request_id": "request-fixture",
            "workspace_path": "workspaces/goal-fixture",
            "allowed_files": ["workspaces/goal-fixture/**"],
            "max_usd": 0.0,
            "authority_ref": "lease-fixture",
            "authority_digest": "sha256:" + "e" * 64,
            "attempt_generation": 0,
            "max_attempts": 3,
            "observed_input_manifest_digest": observed_manifest,
            "held_out_oracle_manifest_digest": held_out_oracle,
            "operator_control_semantics_sha256": operator_control,
            "operator_control_authority_binding_sha256": "sha256:" + "7" * 64,
            "deployment_authority_topology_sha256": "sha256:" + "8" * 64,
            "deployment_authority_credential_clarification_sha256": (
                "sha256:" + "9" * 64
            ),
            "observed_input_ref": observed_ref,
            "route_lock": {
                "schema_version": "dharma.sadhana.campaign_route_lock.v1",
                "task_id": task_id,
                "principal_id": principal,
                "provider": provider,
                "model": model,
                "allow_provider_routing": False,
            },
        },
    }


def _owner_stamped_campaign_metadata(
    principal: str,
    task_id: str,
    *,
    provider: str = "local",
    model: str = "fixture-model",
) -> dict:
    metadata = _campaign_metadata(
        principal,
        task_id=task_id,
        provider=provider,
        model=model,
    )
    identity = {
        "run_id": "owner-run-fixture",
        "claim_id": "owner-claim-fixture",
        "idempotency_key": "owner-key-fixture",
        "trace_id": "owner-trace-fixture",
        "correlation_id": "owner-correlation-fixture",
    }
    metadata.update(identity)
    metadata["runtime_run_id"] = identity["run_id"]
    metadata["mission_control_owner_execution"] = {
        "schema_version": "dharma.mission_control.owner_execution.v2",
        "backend": "orchestrator",
        "mission_id": "campaign-fixture",
        "task_id": task_id,
        "dispatch_key": "default",
        "attempt_generation": 0,
        **identity,
    }
    return metadata


class _CampaignProviderSpy:
    available = True

    def __init__(
        self,
        *,
        provider: object = "ollama",
        model: object = "fixture-model:cloud",
        error: Exception | None = None,
        content: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.error = error
        self.content = content
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> object:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        if isinstance(self.provider, str) and isinstance(self.model, str):
            return LLMResponse(
                content=self.content
                or (
                    "Completed the exact bounded read-only campaign analysis with "
                    "explicit observations, limitations, and reproducible evidence."
                ),
                provider=self.provider,
                model=self.model,
            )
        return SimpleNamespace(
            content="Malformed provider identity fixture",
            provider=self.provider,
            model=self.model,
            usage={},
        )

    async def complete_exact_model(self, request: LLMRequest) -> object:
        return await self.complete(request)


class _UnauditedCampaignRouterSpy:
    def __init__(self, decision: object, response: object) -> None:
        self.decision = decision
        self.response = response
        self.calls: list[tuple[object, LLMRequest, object]] = []

    async def complete_for_task(
        self,
        route_request,
        request: LLMRequest,
        *,
        available_provider_types=None,
        campaign_effect_boundary=None,
    ):
        if campaign_effect_boundary is not None:
            await campaign_effect_boundary()
        self.calls.append((route_request, request, available_provider_types))
        return self.decision, self.response

    def record_task_feedback(self, **_kwargs) -> str:
        return "campaign-fixture"


class _LegacyGenericRouterSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[object, LLMRequest, object]] = []

    async def complete_for_task(
        self,
        route_request,
        request: LLMRequest,
        *,
        available_provider_types=None,
    ):
        self.calls.append((route_request, request, available_provider_types))
        return _campaign_route_decision(), _campaign_response()

    def record_task_feedback(self, **_kwargs) -> str:
        return "generic-fixture"


class _DirectOllamaHTTPResponse:
    def __init__(self, status_code: int, *, model: str = "") -> None:
        self.status_code = status_code
        self.text = "fixture failure" if status_code != 200 else ""
        self._model = model

    def json(self) -> dict:
        return {
            "model": self._model,
            "choices": [
                {
                    "message": {"content": "bounded fixture response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
        }


class _DirectOllamaHTTPClient:
    is_closed = False

    def __init__(self, responses: list[_DirectOllamaHTTPResponse]) -> None:
        self.responses = list(responses)
        self.payloads: list[dict] = []

    async def post(self, _url, *, json, headers):
        self.payloads.append(dict(json))
        return self.responses.pop(0)


def _campaign_config(tmp_path: Path) -> AgentConfig:
    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    return AgentConfig(
        id="agent-exact",
        name="exact-seat",
        role=AgentRole.RESEARCHER,
        provider=ProviderType.OLLAMA,
        model="fixture-model:cloud",
        metadata={
            "state_dir": str(state_dir),
            "memory_state_dir": str(state_dir),
        },
    )


def _campaign_task(
    config: AgentConfig,
    *,
    task_id: str = "campaign-provider-task",
    title: str = "Inspect the bounded campaign evidence",
    description: str = "Return only evidence-bound findings.",
) -> Task:
    return Task(
        id=task_id,
        title=title,
        description=description,
        metadata=_campaign_metadata(
            config.id,
            task_id=task_id,
            provider=config.provider.value,
            model=config.model,
        ),
    )


def _campaign_response(
    *,
    provider: str = "ollama",
    model: str = "fixture-model:cloud",
) -> LLMResponse:
    return LLMResponse(
        content=(
            "Completed the exact bounded read-only campaign analysis with explicit "
            "observations, limitations, and reproducible evidence."
        ),
        provider=provider,
        model=model,
    )


def _campaign_route_decision(
    *,
    provider: object = ProviderType.OLLAMA,
    model: object = "fixture-model:cloud",
    fallback_providers: object = None,
    fallback_models: object = None,
) -> object:
    return SimpleNamespace(
        selected_provider=provider,
        selected_model_hint=model,
        fallback_providers=[] if fallback_providers is None else fallback_providers,
        fallback_model_hints=[] if fallback_models is None else fallback_models,
    )


class MockTaskBoard:
    projection_commit_mode = "non_production_exact_readback.v1"

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

    async def compare_and_swap_campaign_status(
        self, expected, *, new_status, assigned_to, metadata
    ):
        current = await self.get(expected.id)
        if current is None or current != expected:
            return None
        await self.update_task(
            expected.id,
            status=new_status,
            assigned_to=assigned_to,
            metadata=metadata,
        )
        return await self.get(expected.id)

    async def compare_and_swap_terminal_projection(
        self,
        expected,
        *,
        metadata,
        result,
        expected_claim_id,
        expected_agent_id,
        runtime_state_store,
    ):
        current = await self.get(expected.id)
        if current is None or current != expected:
            return None
        marker = metadata["graph_reconcile_projection"]
        action = marker["action"]
        status = (
            TaskStatus.PENDING
            if action in {"retry", "requeue"}
            else TaskStatus.COMPLETED
            if action == "receipt" and marker["run_status"] == "completed"
            else TaskStatus.FAILED
        )
        await self.update_task(
            expected.id,
            status=status,
            assigned_to=(None if action in {"retry", "requeue"} else expected_agent_id),
            result=result,
            metadata=metadata,
        )
        return await self.get(expected.id)

    async def resolve_campaign_pre_effect_failure(
        self,
        task_id,
        *,
        expected_status,
        expected_agent_id,
        expected_metadata,
        authenticated_principal,
        provider_task_scheduled=False,
    ):
        task = await self.get(task_id)
        if task is None or (
            task.status is not expected_status
            or task.assigned_to != expected_agent_id
            or task.metadata != expected_metadata
        ):
            return "conflict"
        if expected_status is TaskStatus.PENDING:
            return "pending"
        task.status = (
            TaskStatus.CANCELLED
            if expected_status is TaskStatus.ASSIGNED
            else TaskStatus.FAILED
        )
        task.result = "dispatch_indeterminate: exception before provider task scheduling"
        task.metadata = {
            **task.metadata,
            "campaign_dispatch_recovery": {
                "schema_version": "dharma.sadhana.dispatch_recovery.v2",
                "state": "dispatch_indeterminate",
                "task_id": task_id,
                "authenticated_principal": authenticated_principal,
                "prior_status": expected_status.value,
                "provider_task_scheduled": provider_task_scheduled,
            },
        }
        return "indeterminate"

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
        self._reservation_tokens = {}
        self._reservation_runners = {}

    async def list_agents(self):
        return list(self._agents)

    async def get_idle_agents(self):
        return [
            agent
            for agent in self._agents
            if agent.status is AgentStatus.IDLE
            and agent.id not in self._reservation_tokens
        ]

    async def assign(self, agent_id, task_id):
        if agent_id in self._reservation_tokens:
            raise RuntimeError("agent has an outstanding opaque campaign reservation")
        self._assignments.append((agent_id, task_id))

    async def reserve(self, agent_id, task_id, *, reservation_token=None):
        matches = [agent for agent in self._agents if agent.id == agent_id]
        if len(matches) != 1:
            return False
        agent = matches[0]
        if (
            agent_id in self._reservation_tokens
            or agent.status is not AgentStatus.IDLE
            or agent.current_task
        ):
            return False
        agent.status = AgentStatus.BUSY
        agent.current_task = task_id
        if reservation_token is not None:
            self._reservation_tokens[agent_id] = (task_id, reservation_token)
            self._reservation_runners[agent_id] = self._runners.get(agent_id)
            if isinstance(reservation_token, TaskDispatch):
                self._assignments.append((agent_id, task_id))
        return True

    def owns_reservation(self, agent_id, task_id, *, reservation_token):
        matches = [agent for agent in self._agents if agent.id == agent_id]
        owned = self._reservation_tokens.get(agent_id)
        bound_runner = self._reservation_runners.get(agent_id)
        return bool(
            len(matches) == 1
            and owned is not None
            and owned[0] == task_id
            and owned[1] is reservation_token
            and self._runners.get(agent_id) is bound_runner
            and matches[0].status is AgentStatus.BUSY
            and matches[0].current_task == task_id
        )

    async def release_reservation(self, agent_id, task_id, *, reservation_token=None):
        matches = [agent for agent in self._agents if agent.id == agent_id]
        if len(matches) != 1:
            return False
        agent = matches[0]
        owned = self._reservation_tokens.get(agent_id)
        bound_runner = self._reservation_runners.get(agent_id)
        if reservation_token is not None and (
            self._runners.get(agent_id) is not bound_runner
        ):
            return False
        if owned is not None and (
            owned[0] != task_id or owned[1] is not reservation_token
        ):
            return False
        if owned is None and reservation_token is not None:
            return False
        if agent.status is not AgentStatus.BUSY or agent.current_task != task_id:
            return False
        self._reservation_tokens.pop(agent_id, None)
        self._reservation_runners.pop(agent_id, None)
        agent.status = AgentStatus.IDLE
        agent.current_task = None
        return True

    async def release(self, agent_id):
        owned = self._reservation_tokens.get(agent_id)
        if owned is not None:
            return
        for agent in self._agents:
            if agent.id == agent_id:
                agent.status = AgentStatus.IDLE
                agent.current_task = None

    async def get_result(self, agent_id):
        return self._results.get(agent_id)

    def set_result(self, agent_id, result):
        self._results[agent_id] = result

    async def get(self, agent_id):
        return self._runners.get(agent_id)

    def set_runner(self, agent_id, runner):
        self._runners[agent_id] = runner


class LegacyDispatchPool:
    """Documented assign/release-only pool used by compatibility regressions."""

    def __init__(self, agent, runner=None, *, block_assign=False):
        self.agent = agent
        self.runner = runner
        self.assignments = []
        self.releases = []
        self.assign_entered = asyncio.Event()
        self.assign_continue = asyncio.Event()
        self.release_error: BaseException | None = None
        if not block_assign:
            self.assign_continue.set()

    async def get_idle_agents(self):
        return [self.agent] if self.agent.status is AgentStatus.IDLE else []

    async def assign(self, agent_id, task_id):
        self.assignments.append((agent_id, task_id))
        self.assign_entered.set()
        await self.assign_continue.wait()
        self.agent.status = AgentStatus.BUSY
        self.agent.current_task = task_id

    async def release(self, agent_id):
        self.releases.append(agent_id)
        if self.release_error is not None:
            raise self.release_error
        self.agent.status = AgentStatus.IDLE
        self.agent.current_task = None

    async def get(self, agent_id):
        return self.runner if agent_id == self.agent.id else None

    async def list_agents(self):
        return [self.agent]

    async def get_result(self, agent_id):
        return None


def _installed_campaign_recovery_fixture():
    principal = "campaign-recovery-agent"
    task = Task(
        id="campaign-recovery-task",
        title="Campaign recovery fixture",
        status=TaskStatus.ASSIGNED,
        assigned_to=principal,
        metadata=_owner_stamped_campaign_metadata(
            principal,
            "campaign-recovery-task",
            provider="ollama",
            model="fixture-model:cloud",
        ),
    )
    agent = AgentState(
        id=principal,
        name="campaign-recovery-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    runner = MagicMock()
    runner.state = agent
    pool.set_runner(principal, runner)
    token = {
        "reservation_id": "campaign-recovery-token",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    assert agent.status is AgentStatus.IDLE
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=principal,
        metadata={
            "attempt_generation": 0,
            "_campaign_active_owner_installed": True,
        },
    )
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    return orchestrator, board, pool, task, agent, dispatch, token, runner


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
@pytest.mark.parametrize("topology", [TopologyType.FAN_OUT, TopologyType.BROADCAST])
async def test_parallel_public_topologies_fail_before_assignment(
    agents, tasks, topology
):
    pool = MockAgentPool(agents)
    orch = Orchestrator(agent_pool=pool)
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(NotImplementedError, match="composite across task and agent"):
        await orch.dispatch(tasks[0], topology=topology)

    orch._assign_dispatch.assert_not_awaited()  # type: ignore[attr-defined]
    assert pool._assignments == []


@pytest.mark.asyncio
async def test_multi_entrypoint_genome_fails_before_any_assignment(
    agents,
) -> None:
    pool = MockAgentPool(agents)
    orchestrator = Orchestrator(agent_pool=pool)
    orchestrator._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]
    genome = SimpleNamespace(
        genome_id="parallel-genome",
        entrypoints=["root-a", "root-b"],
        nodes=[
            SimpleNamespace(node_id="root-a"),
            SimpleNamespace(node_id="root-b"),
        ],
        validate_structure=MagicMock(),
        incoming_edge_ids=MagicMock(return_value=[]),
    )

    with pytest.raises(NotImplementedError, match="multi-entrypoint topology genomes"):
        await orchestrator.dispatch(
            Task(id="parallel-genome-task", title="Parallel genome"),
            genome,
        )

    orchestrator._assign_dispatch.assert_not_awaited()  # type: ignore[attr-defined]
    assert pool._assignments == []


@pytest.mark.asyncio
async def test_dispatch_no_agents():
    pool = MockAgentPool([])
    orch = Orchestrator(agent_pool=pool)
    with pytest.raises(NotImplementedError, match="fan_out is unsupported"):
        await orch.dispatch(Task(title="test"))


@pytest.mark.asyncio
async def test_campaign_authority_selects_exact_idle_principal_once() -> None:
    exact = AgentState(
        id="agent-exact",
        name="exact-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="local",
        model="fixture-model",
    )
    substitute = AgentState(
        id="agent-substitute",
        name="substitute-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
    )
    pool = MockAgentPool([substitute, exact])
    orchestrator = Orchestrator(agent_pool=pool)
    orchestrator._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]
    task = Task(
        id="task-authorized",
        title="Authorized task",
        metadata=_campaign_metadata(exact.id, task_id="task-authorized"),
    )

    assert await orchestrator.dispatch(task, TopologyType.PIPELINE) == []
    dispatches = await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=exact.id,
        campaign_effect_fence=_allow_campaign_effect,
    )

    assert [dispatch.agent_id for dispatch in dispatches] == [exact.id]
    orchestrator._assign_dispatch.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["missing", "busy"])
async def test_campaign_authority_missing_or_busy_principal_never_falls_back(
    mode: str,
) -> None:
    principal = AgentState(
        id="agent-required",
        name="required-seat",
        role=AgentRole.CODER,
        status=AgentStatus.BUSY,
    )
    substitute = AgentState(
        id="agent-substitute",
        name="substitute-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
    )
    agents = [substitute] if mode == "missing" else [substitute, principal]
    orchestrator = Orchestrator(agent_pool=MockAgentPool(agents))
    orchestrator._assign_dispatch = AsyncMock()  # type: ignore[method-assign]
    task = Task(
        id=f"task-{mode}",
        title="Must not substitute",
        metadata=_campaign_metadata(principal.id, task_id=f"task-{mode}"),
    )

    assert await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=principal.id,
        campaign_effect_fence=_allow_campaign_effect,
    ) == []
    orchestrator._assign_dispatch.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unbound_sadhana_seed_never_falls_through_to_generic_routing() -> None:
    substitute = AgentState(
        id="agent-substitute",
        name="substitute-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
    )
    orchestrator = Orchestrator(agent_pool=MockAgentPool([substitute]))
    orchestrator._assign_dispatch = AsyncMock()  # type: ignore[method-assign]
    task = Task(
        id="task-unbound-seed",
        title="Seeded but not authorized",
        metadata={
            "sadhana_bootstrap_schema": "dharma.sadhana.mission_bootstrap.v1",
            "dispatch_ready": False,
            "dispatch_blocker": "authority_unbound",
        },
    )

    assert await orchestrator.dispatch(task, TopologyType.PIPELINE) == []
    orchestrator._assign_dispatch.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "authority",
    [None, {}, {"claimed_principal": ""}, {"claimed_principal": " padded "}],
)
async def test_campaign_authority_malformed_or_duplicate_principal_fails_closed(
    authority: object,
) -> None:
    duplicate = [
        AgentState(
            id="agent-duplicate",
            name=f"duplicate-{index}",
            role=AgentRole.CODER,
            status=AgentStatus.IDLE,
        )
        for index in range(2)
    ]
    orchestrator = Orchestrator(agent_pool=MockAgentPool(duplicate))
    orchestrator._assign_dispatch = AsyncMock()  # type: ignore[method-assign]
    marker = (
        {"claimed_principal": "agent-duplicate"}
        if authority is None
        else authority
    )
    metadata = _campaign_metadata("agent-duplicate", task_id="task-malformed")
    metadata["mission_campaign_authority"] = marker
    task = Task(id="task-malformed", title="Malformed campaign task", metadata=metadata)

    assert await orchestrator.dispatch(task, TopologyType.PIPELINE) == []
    orchestrator._assign_dispatch.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_campaign_authority_rejects_non_pipeline_topology() -> None:
    exact = AgentState(
        id="agent-exact",
        name="exact-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
    )
    orchestrator = Orchestrator(agent_pool=MockAgentPool([exact]))
    orchestrator._assign_dispatch = AsyncMock()  # type: ignore[method-assign]
    task = Task(
        id="task-no-fanout",
        title="No fan out",
        metadata=_campaign_metadata(exact.id, task_id="task-no-fanout"),
    )

    assert await orchestrator.dispatch(
        task,
        TopologyType.FAN_OUT,
        authenticated_principal_id=exact.id,
        campaign_effect_fence=_allow_campaign_effect,
    ) == []
    orchestrator._assign_dispatch.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_generic_dispatch_routing_is_unchanged_without_campaign_authority() -> None:
    first = AgentState(
        id="agent-first",
        name="first-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    second = AgentState(
        id="agent-second",
        name="second-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    orchestrator = Orchestrator(agent_pool=MockAgentPool([first, second]))
    orchestrator._assign_dispatch = AsyncMock()  # type: ignore[method-assign]

    dispatches = await orchestrator.dispatch(
        Task(title="Generic task"),
        TopologyType.PIPELINE,
    )

    assert [dispatch.agent_id for dispatch in dispatches] == [first.id]
    orchestrator._assign_dispatch.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_route_next_never_bypasses_campaign_authority() -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="local",
        model="fixture-model",
    )
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="campaign-task",
            title="Governed campaign task",
            metadata={
                **_campaign_metadata(exact.id, task_id="campaign-task"),
                "sadhana_bootstrap_schema": "dharma.sadhana.mission_bootstrap.v1",
            },
        ),
        Task(id="generic-task", title="Generic task"),
    ]
    orchestrator = Orchestrator(task_board=board, agent_pool=MockAgentPool([exact]))
    orchestrator._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

    dispatches = await orchestrator.route_next()

    assert [dispatch.task_id for dispatch in dispatches] == ["generic-task"]
    orchestrator._assign_dispatch.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_campaign_idle_snapshot_race_never_starts_owner_provider() -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_campaign_metadata(
            exact.id,
            task_id="campaign-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    runner = MagicMock()
    runner.state = exact
    runner.run_task = AsyncMock()
    pool.set_runner(exact.id, runner)

    async def lose_reservation(
        agent_id: str, task_id: str, *, reservation_token=None
    ) -> bool:
        assert (agent_id, task_id) == (exact.id, task.id)
        assert reservation_token is not None
        exact.status = AgentStatus.BUSY
        exact.current_task = "competing-task"
        return False

    pool.reserve = AsyncMock(side_effect=lose_reservation)  # type: ignore[attr-defined]
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        return_value=dict(task.metadata)
    )

    assert await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=exact.id,
        campaign_effect_fence=_allow_campaign_effect,
    ) == []
    runner.run_task.assert_not_awaited()
    assert task.status is TaskStatus.PENDING


@pytest.mark.asyncio
async def test_campaign_dispatch_does_not_release_before_provider_fence(
    tmp_path: Path,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    reached_runner = asyncio.Event()
    allow_provider_boundary = asyncio.Event()
    provider_started = asyncio.Event()

    class _FencedRunner:
        state = exact

        async def run_task(
            self,
            _task,
            *,
            campaign_effect_fence,
            campaign_effect_ready,
        ):
            reached_runner.set()
            await allow_provider_boundary.wait()
            await campaign_effect_fence()
            campaign_effect_ready()
            provider_started.set()
            return "bounded campaign result"

    pool.set_runner(exact.id, _FencedRunner())
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        runtime_db_path=tmp_path / "campaign-fence-runtime.db",
    )
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]
    fence_calls = 0

    async def fence() -> None:
        nonlocal fence_calls
        fence_calls += 1

    dispatch_task = asyncio.create_task(
        orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=fence,
        )
    )
    await asyncio.wait_for(reached_runner.wait(), timeout=2)
    await asyncio.sleep(0)
    assert dispatch_task.done() is False

    allow_provider_boundary.set()
    await asyncio.wait_for(provider_started.wait(), timeout=2)
    dispatches = await asyncio.wait_for(dispatch_task, timeout=2)

    assert [item.agent_id for item in dispatches] == [exact.id]
    assert fence_calls == 1
    await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=2)


@pytest.mark.asyncio
@pytest.mark.parametrize("substitution", ["registry", "pool", "active", "runner"])
async def test_campaign_foreign_reservation_substitution_stays_preeffect(
    substitution: str,
    tmp_path: Path,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    fence_entered = asyncio.Event()
    fence_release = asyncio.Event()
    provider_started = asyncio.Event()

    class _FencedRunner:
        state = exact

        async def run_task(
            self,
            _task,
            *,
            campaign_effect_fence,
            campaign_effect_ready,
        ):
            await campaign_effect_fence()
            campaign_effect_ready()
            provider_started.set()
            return "must not execute"

    pool.set_runner(exact.id, _FencedRunner())
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        runtime_db_path=tmp_path / f"campaign-substitution-{substitution}.db",
    )
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]

    async def fence() -> None:
        fence_entered.set()
        await fence_release.wait()

    pending = asyncio.create_task(
        orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=fence,
        )
    )
    await asyncio.wait_for(fence_entered.wait(), timeout=2)
    key = (task.id, exact.id, 0)
    original_token = orchestrator._campaign_reservations[key]
    foreign_token = {
        "reservation_id": "foreign-reservation",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    foreign_dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=exact.id,
        metadata={"attempt_generation": 0, "foreign": True},
    )
    foreign_runner = MagicMock()
    foreign_runner.state = exact
    foreign_runner.run_task = AsyncMock(return_value="foreign must not execute")
    if substitution == "registry":
        orchestrator._campaign_reservations[key] = foreign_token
    elif substitution == "pool":
        pool._reservation_tokens[exact.id] = (task.id, foreign_token)
    elif substitution == "active":
        orchestrator._active_dispatches[task.id] = foreign_dispatch
    elif substitution == "runner":
        pool.set_runner(exact.id, foreign_runner)
    else:  # pragma: no cover - parametrization is closed above
        raise AssertionError(substitution)
    fence_release.set()

    with pytest.raises(RuntimeError, match="lost its exact reservation"):
        await asyncio.wait_for(pending, timeout=2)

    assert provider_started.is_set() is False
    assert original_token["provider_task_scheduled"] is False
    if substitution == "registry":
        assert orchestrator._campaign_reservations[key] is foreign_token
    else:
        assert key not in orchestrator._campaign_reservations
    if substitution == "active":
        assert orchestrator._active_dispatches[task.id] is foreign_dispatch
    else:
        assert task.id not in orchestrator._active_dispatches
    assert pool._reservation_tokens[exact.id] == (
        (task.id, foreign_token)
        if substitution == "pool"
        else (task.id, original_token)
    )
    if substitution == "runner":
        assert pool._runners[exact.id] is foreign_runner
        foreign_runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_stale_completion_cannot_release_foreign_owner(
    tmp_path: Path,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    provider_entered = asyncio.Event()
    provider_release = asyncio.Event()

    class _BlockedRunner:
        state = exact

        async def run_task(
            self,
            _task,
            *,
            campaign_effect_fence,
            campaign_effect_ready,
        ):
            await campaign_effect_fence()
            campaign_effect_ready()
            provider_entered.set()
            await provider_release.wait()
            return "bounded campaign result"

    pool.set_runner(exact.id, _BlockedRunner())
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        runtime_db_path=tmp_path / "campaign-stale-runtime.db",
    )
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]

    dispatches = await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=exact.id,
        campaign_effect_fence=_allow_campaign_effect,
    )
    await asyncio.wait_for(provider_entered.wait(), timeout=2)
    assert [dispatch.agent_id for dispatch in dispatches] == [exact.id]
    original_token = pool._reservation_tokens[exact.id][1]
    assert original_token["provider_task_scheduled"] is True
    generic_release = AsyncMock(wraps=pool.release)
    pool.release = generic_release  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="owner-token completion"):
        await orchestrator.fan_in(dispatches)

    generic_release.assert_not_awaited()
    assert pool._reservation_tokens[exact.id] == (task.id, original_token)
    assert orchestrator._active_dispatches[task.id] is dispatches[0]

    foreign_token = {
        "reservation_id": "foreign-post-effect",
        "attempt_generation": 1,
        "provider_task_scheduled": True,
    }
    foreign_dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=exact.id,
        metadata={"attempt_generation": 1, "foreign": True},
    )
    pool._reservation_tokens[exact.id] = (task.id, foreign_token)
    orchestrator._active_dispatches[task.id] = foreign_dispatch
    provider_release.set()
    with pytest.raises(
        RuntimeError,
        match="terminal owner release is indeterminate",
    ):
        await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=2)
    settled, recovered = await orchestrator._collect_completed()

    assert (settled, recovered) == (1, 0)
    assert exact.status is AgentStatus.BUSY
    assert exact.current_task == task.id
    assert pool._reservation_tokens[exact.id] == (task.id, foreign_token)
    assert orchestrator._active_dispatches[task.id] is foreign_dispatch
    assert task.id not in orchestrator._running_dispatch_owners


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_substitution", [False, True])
async def test_campaign_posteffect_cancellation_releases_only_exact_owner(
    foreign_substitution: bool,
    tmp_path: Path,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-cancel-task",
        title="Read-only cancellable campaign task",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-cancel-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    provider_entered = asyncio.Event()
    never_complete = asyncio.Event()

    class _BlockedRunner:
        state = exact

        async def run_task(
            self,
            _task,
            *,
            campaign_effect_fence,
            campaign_effect_ready,
        ):
            await campaign_effect_fence()
            campaign_effect_ready()
            provider_entered.set()
            await never_complete.wait()
            raise AssertionError("unreachable")

    pool.set_runner(exact.id, _BlockedRunner())
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        runtime_db_path=tmp_path / "campaign-cancel-runtime.db",
    )
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]

    dispatches = await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=exact.id,
        campaign_effect_fence=_allow_campaign_effect,
    )
    await asyncio.wait_for(provider_entered.wait(), timeout=2)
    original_dispatch = dispatches[0]
    original_token = pool._reservation_tokens[exact.id][1]
    assert original_token["provider_task_scheduled"] is True
    foreign_token = {
        "reservation_id": "foreign-cancel-owner",
        "attempt_generation": 1,
        "provider_task_scheduled": True,
    }
    foreign_dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=exact.id,
        metadata={"attempt_generation": 1, "foreign": True},
    )
    if foreign_substitution:
        pool._reservation_tokens[exact.id] = (task.id, foreign_token)
        orchestrator._active_dispatches[task.id] = foreign_dispatch

    background = orchestrator._running_tasks[task.id]
    background.cancel()
    with pytest.raises(asyncio.CancelledError):
        await background
    await orchestrator._collect_completed()

    if foreign_substitution:
        assert exact.status is AgentStatus.BUSY
        assert exact.current_task == task.id
        assert pool._reservation_tokens[exact.id] == (task.id, foreign_token)
        assert orchestrator._active_dispatches[task.id] is foreign_dispatch
    else:
        assert exact.status is AgentStatus.IDLE
        assert exact.current_task is None
        assert exact.id not in pool._reservation_tokens
        assert task.id not in orchestrator._active_dispatches
    assert original_token["provider_task_scheduled"] is True
    assert original_dispatch is not foreign_dispatch


@pytest.mark.asyncio
@pytest.mark.parametrize("campaign_evidence", ["dispatch_marker", "board_task"])
async def test_stale_claim_cleanup_never_consumes_campaign_custody(
    campaign_evidence: str,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(id="stale-campaign-task", title="Stale campaign claim")
    if campaign_evidence == "board_task":
        task.metadata = _campaign_metadata(
            exact.id,
            task_id=task.id,
            provider=exact.provider,
            model=exact.model,
        )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    token = {
        "reservation_id": "stale-campaign-owner",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    assert await pool.reserve(
        exact.id,
        task.id,
        reservation_token=token,
    ) is True
    metadata = {
        "claim_expires_monotonic": time.monotonic() - 1,
        "claim_timeout_seconds": 1,
    }
    if campaign_evidence == "dispatch_marker":
        metadata["authenticated_campaign_principal_id"] = exact.id
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=exact.id,
        metadata=metadata,
    )
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._active_dispatches[task.id] = dispatch

    settled, recovered = await orchestrator._collect_completed()

    assert (settled, recovered) == (0, 0)
    assert pool._reservation_tokens[exact.id] == (task.id, token)
    assert exact.status is AgentStatus.BUSY
    assert exact.current_task == task.id
    assert orchestrator._active_dispatches[task.id] is dispatch
    assert board.updates == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "Prove the authority invariant step by step before giving the conclusion.",
        "Analyze this long bounded record: " + "evidence " * 5000,
        "この観測された証拠だけを使って、権限境界を日本語で分析してください。",
    ],
    ids=["reasoning", "long", "japanese"],
)
async def test_campaign_actual_router_cannot_leave_locked_provider_model(
    prompt: str,
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    exact = _CampaignProviderSpy()
    foreign = _CampaignProviderSpy(provider="anthropic", model="foreign-model")
    router = ModelRouter(
        {
            ProviderType.OLLAMA: exact,
            ProviderType.ANTHROPIC: foreign,
        },
        retry_policy=RetryPolicy(
            max_attempts=1,
            base_delay_seconds=0,
            backoff_multiplier=1,
            max_delay_seconds=0,
            jitter_seconds=0,
        ),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    runner = AgentRunner(config, provider=router)
    task = _campaign_task(config, title=prompt, description=prompt)

    _, decision, response = await runner._invoke_provider(
        task,
        LLMRequest(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
        ),
        campaign_effect_boundary=_allow_campaign_boundary(),
    )

    assert len(exact.requests) == 1
    assert foreign.requests == []
    assert exact.requests[0].model == config.model
    assert response.provider == config.provider.value
    assert response.model == config.model
    assert decision.selected_provider is config.provider
    assert decision.selected_model_hint == config.model
    assert decision.fallback_providers == []
    assert decision.fallback_model_hints == []


@pytest.mark.asyncio
async def test_real_orchestrator_runner_campaign_route_reaches_only_exact_provider(
    fast_gate,
    monkeypatch,
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    exact = _CampaignProviderSpy(
        content=(
            "Operator brief: The bounded campaign route completed on the exact "
            "requested provider and model. Evidence: the request remained pinned "
            "to the authenticated seat, the foreign provider received zero calls, "
            "and the runtime receipt records the selected route. Findings: the "
            "read-only boundary held and no output path was written. Next actions: "
            "retain the same route lock, verify the durable receipt, and reject any "
            "future fallback to an unlisted provider."
        )
    )
    foreign = _CampaignProviderSpy(provider="anthropic", model="foreign-model")
    router = ModelRouter(
        {ProviderType.OLLAMA: exact, ProviderType.ANTHROPIC: foreign},
        retry_policy=RetryPolicy(max_attempts=1),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    pool = AgentPool()
    runner = await pool.spawn(
        config,
        provider=router,
        ontology_path=tmp_path / "ontology.db",
        advanced_memory=AsyncMock(),
    )
    task = _campaign_task(config, task_id="campaign-real-e2e")
    task.description = "Write results to ~/campaign-must-not-write.md"
    task.metadata = _owner_stamped_campaign_metadata(
        config.id,
        task.id,
        provider=config.provider.value,
        model=config.model,
    )
    task.metadata["allow_free_text_result_path"] = True
    board = MockTaskBoard()
    board.tasks = [task]
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledger",
        runtime_db_path=tmp_path / "campaign-real-e2e-runtime.db",
    )
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]
    sidecar_constructor = MagicMock()
    monkeypatch.setattr(
        "dharma_swarm.sleep_time_agent.SleepTimeAgent",
        sidecar_constructor,
    )
    dispatches = await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=config.id,
        campaign_effect_fence=_allow_campaign_effect,
    )
    await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=5)

    assert [dispatch.agent_id for dispatch in dispatches] == [config.id]
    assert len(exact.requests) == 1
    assert foreign.requests == []
    assert runner._last_response is not None
    assert runner._last_response.provider == config.provider.value
    assert runner._last_response.model == config.model
    assert runner.state.status is AgentStatus.IDLE
    assert runner.state.current_task is None
    assert config.id not in pool._reservation_tokens
    sidecar_constructor.assert_not_called()
    assert (tmp_path / "campaign-must-not-write.md").exists() is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allow_provider_routing", True),
        ("available_provider_types", ["anthropic"]),
        ("model_catalog_selector", "largest"),
        ("model_pack", "frontier"),
        ("model_selector", "foreign-model"),
        ("preferred_model", "foreign-model"),
        ("preferred_provider", "anthropic"),
        ("provider_allowlist", ["anthropic"]),
        ("provider_pack", "paid"),
        ("route_context", {"preferred_provider": "anthropic"}),
        ("routed_execution", True),
        ("use_router", True),
    ],
)
async def test_campaign_routing_alias_cannot_widen_before_provider(
    field: str,
    value: object,
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    exact = _CampaignProviderSpy()
    foreign = _CampaignProviderSpy(provider="anthropic", model="foreign-model")
    router = ModelRouter(
        {ProviderType.OLLAMA: exact, ProviderType.ANTHROPIC: foreign},
        retry_policy=RetryPolicy(max_attempts=1),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    runner = AgentRunner(config, provider=router)
    task = _campaign_task(config)
    task.metadata[field] = value

    with pytest.raises(RuntimeError, match="routing|route lock"):
        await runner._invoke_provider(
            task,
            LLMRequest(
                model=config.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert exact.requests == []
    assert foreign.requests == []


@pytest.mark.asyncio
async def test_campaign_agent_config_routing_alias_is_rejected_before_provider(
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    config = config.model_copy(
        update={"metadata": {**config.metadata, "available_provider_types": ["anthropic"]}}
    )
    provider = _CampaignProviderSpy()
    runner = AgentRunner(config, provider=provider)

    with pytest.raises(RuntimeError, match="AgentConfig.*routing widening"):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=config.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert provider.requests == []


@pytest.mark.asyncio
async def test_campaign_actual_router_failure_has_no_foreign_fallback(
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    exact = _CampaignProviderSpy(error=RuntimeError("exact provider unavailable"))
    foreign = _CampaignProviderSpy(provider="anthropic", model="foreign-model")
    router = ModelRouter(
        {ProviderType.OLLAMA: exact, ProviderType.ANTHROPIC: foreign},
        retry_policy=RetryPolicy(
            max_attempts=1,
            base_delay_seconds=0,
            backoff_multiplier=1,
            max_delay_seconds=0,
            jitter_seconds=0,
        ),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    runner = AgentRunner(config, provider=router)

    with pytest.raises(RuntimeError, match="All providers failed"):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=config.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert len(exact.requests) == 1
    assert foreign.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response_provider", "response_model", "message"),
    [
        ("anthropic", "fixture-model:cloud", "response provider"),
        ("ollama", "foreign-model", "response model"),
    ],
)
async def test_campaign_actual_router_rejects_wrong_served_identity_once(
    response_provider: str,
    response_model: str,
    message: str,
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    exact = _CampaignProviderSpy(
        provider=response_provider,
        model=response_model,
    )
    foreign = _CampaignProviderSpy(provider="anthropic", model="foreign-fallback")
    router = ModelRouter(
        {ProviderType.OLLAMA: exact, ProviderType.ANTHROPIC: foreign},
        retry_policy=RetryPolicy(max_attempts=5),
        routing_audit_path=tmp_path / "routing.jsonl",
        learning_enabled=False,
        telemetry_enabled=False,
        key_liveness_provider=lambda: None,
    )
    runner = AgentRunner(config, provider=router)

    with pytest.raises(RuntimeError, match=message):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=config.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert len(exact.requests) == 1
    assert foreign.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_change",
    [
        {"provider": ProviderType.ANTHROPIC},
        {"model": "foreign-model"},
    ],
)
async def test_campaign_agent_config_identity_mismatch_never_calls_provider(
    config_change: dict,
    tmp_path: Path,
) -> None:
    original = _campaign_config(tmp_path)
    task = _campaign_task(original)
    changed = original.model_copy(update=config_change)
    provider = _CampaignProviderSpy()
    runner = AgentRunner(changed, provider=provider)

    with pytest.raises(RuntimeError, match="route lock conflicts with AgentConfig"):
        await runner._invoke_provider(
            task,
            LLMRequest(
                model=changed.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert provider.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "model", "message"),
    [
        ("", "fixture-model:cloud", "response provider"),
        ("anthropic", "fixture-model:cloud", "response provider"),
        (None, "fixture-model:cloud", "response provider"),
        ("ollama", "foreign-model", "response model"),
        ("ollama", None, "response model"),
    ],
)
async def test_campaign_direct_response_identity_fails_closed_after_one_call(
    provider: object,
    model: object,
    message: str,
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    exact = _CampaignProviderSpy(provider=provider, model=model)
    runner = AgentRunner(config, provider=exact)

    with pytest.raises(RuntimeError, match=message):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=config.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert len(exact.requests) == 1


@pytest.mark.asyncio
async def test_campaign_direct_response_is_detached_after_attestation(
    tmp_path: Path,
) -> None:
    class _RetainedDirectProvider(_CampaignProviderSpy):
        def __init__(self) -> None:
            super().__init__()
            self.response = LLMResponse(
                content="trusted direct result",
                provider="ollama",
                model="fixture-model:cloud",
                usage={"total_tokens": 7},
                tool_calls=[{"id": "trusted", "name": "bounded"}],
            )

        async def complete_exact_model(self, request: LLMRequest) -> LLMResponse:
            self.requests.append(request)
            return self.response

    config = _campaign_config(tmp_path)
    provider = _RetainedDirectProvider()
    runner = AgentRunner(config, provider=provider)

    _, _, response = await runner._invoke_provider(
        _campaign_task(config),
        LLMRequest(
            model=config.model,
            messages=[{"role": "user", "content": "Bounded campaign work"}],
        ),
        campaign_effect_boundary=_allow_campaign_boundary(),
    )

    provider.response.provider = "anthropic"
    provider.response.model = "foreign-model:cloud"
    provider.response.content = "foreign mutation"
    provider.response.usage["total_tokens"] = 199_999
    provider.response.tool_calls[0]["name"] = "foreign"

    assert response is not provider.response
    assert response == LLMResponse(
        content="trusted direct result",
        provider="ollama",
        model="fixture-model:cloud",
        usage={"total_tokens": 7},
        tool_calls=[{"id": "trusted", "name": "bounded"}],
    )


@pytest.mark.asyncio
async def test_campaign_direct_provider_without_exact_entry_point_makes_no_call(
    tmp_path: Path,
) -> None:
    class _ProviderWithoutExactEntryPoint:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, _request):
            self.calls += 1
            return _campaign_response()

    config = _campaign_config(tmp_path)
    provider = _ProviderWithoutExactEntryPoint()
    runner = AgentRunner(config, provider=provider)
    fence = AsyncMock()
    ready = MagicMock()

    with pytest.raises(RuntimeError, match="lacks exact-model execution"):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=config.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=CampaignProviderEffectBoundary(fence, ready),
        )

    assert provider.calls == 0
    fence.assert_not_awaited()
    ready.assert_not_called()


@pytest.mark.asyncio
async def test_campaign_direct_ollama_failure_never_calls_foreign_frontier_model(
    tmp_path: Path,
) -> None:
    locked = "minimax-m3:cloud"
    foreign = next(
        candidate
        for candidate in get_ollama_cloud_frontier_chain()
        if candidate != locked
    )
    locked_wire = _ollama_cloud_wire_model(locked)
    foreign_wire = _ollama_cloud_wire_model(foreign)
    original = _campaign_config(tmp_path)
    config = original.model_copy(update={"model": locked})
    provider = OllamaProvider(
        base_url="https://ollama.com",
        model=locked,
        api_key="fixture-key",
    )
    client = _DirectOllamaHTTPClient(
        [
            _DirectOllamaHTTPResponse(503),
            _DirectOllamaHTTPResponse(200, model=foreign_wire),
        ]
    )
    provider._client = client
    runner = AgentRunner(config, provider=provider)

    with pytest.raises(RuntimeError, match="Ollama exact cloud error"):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=locked,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert [payload["model"] for payload in client.payloads] == [locked_wire]


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["fixture-model:cloud", "fixture-local-model"])
async def test_campaign_direct_ollama_local_transport_makes_no_http_request(
    model: str,
    tmp_path: Path,
) -> None:
    original = _campaign_config(tmp_path)
    config = original.model_copy(update={"model": model})
    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model=model,
        api_key="fixture-key",
    )
    client = _DirectOllamaHTTPClient(
        [_DirectOllamaHTTPResponse(200, model=model)]
    )
    provider._client = client
    runner = AgentRunner(config, provider=provider)

    with pytest.raises(RuntimeError, match="trusted Ollama Cloud origin"):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=_allow_campaign_boundary(),
        )

    assert client.payloads == []


@pytest.mark.parametrize(
    ("decision", "response", "message"),
    [
        (None, _campaign_response(), "missing its route decision"),
        (
            _campaign_route_decision(provider=ProviderType.ANTHROPIC),
            _campaign_response(),
            "decision provider",
        ),
        (
            _campaign_route_decision(model="foreign-model"),
            _campaign_response(),
            "decision model",
        ),
        (
            _campaign_route_decision(fallback_providers=[ProviderType.ANTHROPIC]),
            _campaign_response(),
            "fallback plan",
        ),
        (
            _campaign_route_decision(fallback_models=["foreign-model"]),
            _campaign_response(),
            "fallback plan",
        ),
        (
            SimpleNamespace(
                selected_provider=ProviderType.OLLAMA,
                selected_model_hint="fixture-model:cloud",
            ),
            _campaign_response(),
            "fallback plan",
        ),
        (
            _campaign_route_decision(),
            _campaign_response(provider="anthropic"),
            "response provider",
        ),
        (
            _campaign_route_decision(),
            _campaign_response(provider=""),
            "response provider",
        ),
        (
            _campaign_route_decision(),
            _campaign_response(model="foreign-model"),
            "response model",
        ),
        (
            _campaign_route_decision(),
            _campaign_response(model=""),
            "response model",
        ),
    ],
)
def test_campaign_routed_result_identity_fails_closed_after_one_call(
    decision: object,
    response: object,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _campaign_provider_result_is_exact(
            {
                "preferred_provider": "ollama",
                "preferred_model": "fixture-model:cloud",
            },
            response,
            routed=True,
            route_decision=decision,
        )


@pytest.mark.asyncio
async def test_campaign_unaudited_duck_router_is_rejected_before_fence(
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    provider = _UnauditedCampaignRouterSpy(
        _campaign_route_decision(),
        _campaign_response(),
    )
    runner = AgentRunner(config, provider=provider)
    fence = AsyncMock()
    ready = MagicMock()

    with pytest.raises(RuntimeError, match="requires the audited ModelRouter"):
        await runner._invoke_provider(
            _campaign_task(config),
            LLMRequest(
                model=config.model,
                messages=[{"role": "user", "content": "Bounded campaign work"}],
            ),
            campaign_effect_boundary=CampaignProviderEffectBoundary(fence, ready),
        )

    assert provider.calls == []
    fence.assert_not_awaited()
    ready.assert_not_called()


@pytest.mark.asyncio
async def test_generic_duck_router_retains_legacy_call_shape() -> None:
    provider = _LegacyGenericRouterSpy()
    runner = AgentRunner(
        AgentConfig(
            id="generic-agent",
            name="generic-agent",
            role=AgentRole.RESEARCHER,
            provider=ProviderType.OLLAMA,
            model="generic-model",
        ),
        provider=provider,
    )

    _, _, response = await runner._invoke_provider(
        Task(id="generic-task", title="Generic analysis"),
        LLMRequest(
            model="generic-model",
            messages=[{"role": "user", "content": "generic work"}],
        ),
    )

    assert len(provider.calls) == 1
    assert response.content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "request_model",
        "request_messages",
        "request_tools",
        "task_route",
        "config_model",
        "provider_replacement",
        "provider_model",
        "provider_transport",
        "provider_origin",
    ],
)
async def test_campaign_provider_fence_toctou_direct_mutation_has_zero_calls(
    mutation: str,
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    task = _campaign_task(config)
    provider = _CampaignProviderSpy()
    provider._model = config.model
    provider._transport_mode = "cloud_api"
    provider._base_url = "https://ollama.com"
    substitute = _CampaignProviderSpy()
    substitute._model = config.model
    substitute._transport_mode = "cloud_api"
    substitute._base_url = "https://ollama.com"
    runner = AgentRunner(config, provider=provider)
    request = _prepend_organism_genome(
        LLMRequest(
            model=config.model,
            messages=[{"role": "user", "content": "Bounded campaign work"}],
            tools=[{"type": "function", "function": {"name": "observe"}}],
        ),
        config,
    )

    async def mutate_after_capture() -> None:
        if mutation == "request_model":
            request.model = "foreign-model"
        elif mutation == "request_messages":
            request.messages[0]["content"] = "mutated after the authority fence"
        elif mutation == "request_tools":
            request.tools.append(
                {"type": "function", "function": {"name": "foreign-effect"}}
            )
        elif mutation == "task_route":
            task.metadata["preferred_model"] = "foreign-model"
        elif mutation == "config_model":
            runner._config.model = "foreign-model"
        elif mutation == "provider_replacement":
            runner._provider = substitute
        elif mutation == "provider_model":
            provider._model = "foreign-model"
        elif mutation == "provider_transport":
            provider._transport_mode = "local_native"
        elif mutation == "provider_origin":
            provider._base_url = "https://ollama.com.evil.invalid"
        else:  # pragma: no cover - parametrization is closed above
            raise AssertionError(mutation)

    ready = MagicMock()
    with pytest.raises(RuntimeError, match="campaign"):
        await runner._invoke_provider(
            task,
            request,
            campaign_effect_boundary=CampaignProviderEffectBoundary(
                mutate_after_capture,
                ready,
            ),
        )

    ready.assert_not_called()
    assert provider.requests == []
    assert substitute.requests == []


@pytest.mark.asyncio
async def test_campaign_direct_uses_callable_captured_before_final_fence(
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    task = _campaign_task(config)
    provider = _CampaignProviderSpy()
    provider._model = config.model
    provider._transport_mode = "cloud_api"
    provider._base_url = "https://ollama.com"
    original = AsyncMock(return_value=_campaign_response())
    replacement = AsyncMock(return_value=_campaign_response())
    provider.complete_exact_model = original  # type: ignore[method-assign]
    runner = AgentRunner(config, provider=provider)
    ready = MagicMock()

    async def replace_callable() -> None:
        provider.complete_exact_model = replacement  # type: ignore[method-assign]

    _, _, response = await runner._invoke_provider(
        task,
        LLMRequest(
            model=config.model,
            messages=[{"role": "user", "content": "Bounded campaign work"}],
        ),
        campaign_effect_boundary=CampaignProviderEffectBoundary(
            replace_callable,
            ready,
        ),
    )

    assert response.model == config.model
    original.assert_awaited_once()
    replacement.assert_not_awaited()
    ready.assert_called_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    ["request_messages", "task_route", "config_model", "router_replacement"],
)
async def test_campaign_provider_fence_toctou_routed_mutation_has_zero_calls(
    mutation: str,
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    task = _campaign_task(config)
    exact = _CampaignProviderSpy()
    substitute_exact = _CampaignProviderSpy()

    def router_for(provider: _CampaignProviderSpy) -> ModelRouter:
        return ModelRouter(
            {ProviderType.OLLAMA: provider},
            retry_policy=RetryPolicy(max_attempts=1),
            routing_audit_path=tmp_path / f"routing-{id(provider)}.jsonl",
            learning_enabled=False,
            telemetry_enabled=False,
            key_liveness_provider=lambda: None,
        )

    router = router_for(exact)
    substitute_router = router_for(substitute_exact)
    runner = AgentRunner(config, provider=router)
    request = _prepend_organism_genome(
        LLMRequest(
            model=config.model,
            messages=[{"role": "user", "content": "Bounded campaign work"}],
        ),
        config,
    )

    async def mutate_after_capture() -> None:
        if mutation == "request_messages":
            request.messages[0]["content"] = "mutated after the authority fence"
        elif mutation == "task_route":
            task.metadata["preferred_provider"] = "anthropic"
        elif mutation == "config_model":
            runner._config.model = "foreign-model"
        elif mutation == "router_replacement":
            runner._provider = substitute_router
        else:  # pragma: no cover - parametrization is closed above
            raise AssertionError(mutation)

    ready = MagicMock()
    with pytest.raises(RuntimeError, match="campaign"):
        await runner._invoke_provider(
            task,
            request,
            campaign_effect_boundary=CampaignProviderEffectBoundary(
                mutate_after_capture,
                ready,
            ),
        )

    ready.assert_not_called()
    assert exact.requests == []
    assert substitute_exact.requests == []


@pytest.mark.asyncio
async def test_campaign_exception_recovery_never_releases_foreign_reservation() -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_campaign_metadata(
            exact.id,
            task_id="campaign-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)

    async def lose_then_raise(
        td,
        *,
        authenticated_principal_id="",
        reservation_token=None,
        campaign_effect_fence=None,
    ):
        assert await pool.reserve(
            exact.id, task.id, reservation_token=reservation_token
        ) is True
        orchestrator._campaign_reservations[(task.id, exact.id, 0)] = reservation_token
        assert await pool.release_reservation(
            exact.id, task.id, reservation_token=reservation_token
        ) is True
        assert await pool.reserve(exact.id, "foreign-task") is True
        raise RuntimeError("post-reservation fixture failure")

    orchestrator._assign_dispatch = lose_then_raise  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="fixture failure"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    assert exact.status is AgentStatus.BUSY
    assert exact.current_task == "foreign-task"
    assert board.updates == []


@pytest.mark.asyncio
async def test_campaign_same_task_attempt_cannot_release_other_attempt() -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="local",
        model="fixture-model",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_campaign_metadata(exact.id, task_id="campaign-task"),
    )
    pool = MockAgentPool([exact])
    stale = exact.model_copy(update={"status": AgentStatus.IDLE, "current_task": None})

    async def stale_idle_snapshot():
        return [stale]

    pool.get_idle_agents = stale_idle_snapshot  # type: ignore[method-assign]
    orchestrator = Orchestrator(task_board=MockTaskBoard(), agent_pool=pool)
    first_reserved = asyncio.Event()
    finish_first = asyncio.Event()
    calls = 0

    async def interleave(
        td,
        *,
        authenticated_principal_id="",
        reservation_token=None,
        campaign_effect_fence=None,
    ):
        nonlocal calls
        calls += 1
        if calls == 1:
            assert await pool.reserve(
                exact.id, task.id, reservation_token=reservation_token
            ) is True
            key = (task.id, exact.id, 0)
            orchestrator._campaign_reservations[key] = reservation_token
            first_reserved.set()
            await finish_first.wait()
            if orchestrator._campaign_reservations.get(key) is reservation_token:
                orchestrator._campaign_reservations.pop(key, None)
            return True
        raise RuntimeError("second call fails before reserve")

    orchestrator._assign_dispatch = interleave  # type: ignore[method-assign]
    first = asyncio.create_task(
        orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )
    )
    await first_reserved.wait()
    with pytest.raises(RuntimeError, match="before reserve"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    assert exact.status is AgentStatus.BUSY
    assert exact.current_task == task.id
    finish_first.set()
    assert len(await first) == 1


@pytest.mark.asyncio
async def test_generic_stale_idle_snapshot_cannot_overwrite_campaign_reservation() -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
    )
    generic_task = Task(id="generic-race-task", title="Generic race fixture")
    board = MockTaskBoard()
    board.tasks = [generic_task]
    pool = MockAgentPool([exact])
    token = {
        "reservation_id": "campaign-won-race",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    assert await pool.reserve(
        exact.id,
        "campaign-owner-task",
        reservation_token=token,
    ) is True
    stale = exact.model_copy(update={"status": AgentStatus.IDLE, "current_task": None})

    async def stale_idle_snapshot():
        return [stale]

    pool.get_idle_agents = stale_idle_snapshot  # type: ignore[method-assign]
    runner = MagicMock()
    runner.state = exact
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(exact.id, runner)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )

    dispatches = await orchestrator.dispatch(generic_task, TopologyType.PIPELINE)

    assert dispatches == []
    runner.run_task.assert_not_awaited()
    assert orchestrator._running_tasks == {}
    assert orchestrator._active_dispatches == {}
    assert pool._reservation_tokens[exact.id] == (
        "campaign-owner-task",
        token,
    )
    assert exact.status is AgentStatus.BUSY
    assert exact.current_task == "campaign-owner-task"
    assert board.updates == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault_status", "terminal_status"),
    [
        ("claimed", TaskStatus.CANCELLED),
        ("running", TaskStatus.FAILED),
    ],
)
async def test_campaign_pre_provider_fault_is_terminally_cas_reconciled(
    fault_status: str,
    terminal_status: TaskStatus,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    runner = MagicMock()
    runner.state = exact
    runner.run_task = AsyncMock()
    pool.set_runner(exact.id, runner)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )

    async def record_claim(td, *, task, status, **kwargs):
        if status == fault_status:
            raise RuntimeError(f"fault after {fault_status}")

    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock(
        side_effect=record_claim
    )
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()

    with pytest.raises(RuntimeError, match=f"after {fault_status}"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    assert task.status is terminal_status
    assert task.metadata["campaign_dispatch_recovery"]["state"] == "dispatch_indeterminate"
    assert task.metadata["campaign_dispatch_recovery"]["provider_task_scheduled"] is False
    assert exact.status is AgentStatus.IDLE
    assert exact.current_task is None
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}
    runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("marker_mutation", ["foreign_backend", "extra_key"])
async def test_campaign_recovery_rejects_noncanonical_owner_marker(
    marker_mutation: str,
) -> None:
    (
        orchestrator,
        board,
        pool,
        task,
        agent,
        dispatch,
        token,
        _,
    ) = _installed_campaign_recovery_fixture()
    assert await pool.reserve(
        agent.id,
        task.id,
        reservation_token=token,
    ) is True
    key = (task.id, agent.id, 0)
    orchestrator._campaign_reservations[key] = token
    orchestrator._active_dispatches[task.id] = dispatch
    marker = task.metadata["mission_control_owner_execution"]
    if marker_mutation == "foreign_backend":
        marker["backend"] = "foreign"
    else:
        marker["uncommitted_extra"] = True

    ticket = orchestrator._prepare_campaign_before_effect_recovery(
        dispatch,
        agent.id,
        token,
        allow_uninstalled_active=False,
    )
    assert ticket is not None
    assert await orchestrator._finish_campaign_before_effect_recovery(
        token,
        ticket,
    ) is False

    assert task.status is TaskStatus.ASSIGNED
    assert "campaign_dispatch_recovery" not in task.metadata
    assert board.updates == []
    assert agent.status is AgentStatus.IDLE
    assert agent.current_task is None
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}


@pytest.mark.parametrize("status", [TaskStatus.ASSIGNED, TaskStatus.RUNNING])
def test_campaign_recovery_requires_owner_marker_after_pending(status) -> None:
    (
        orchestrator,
        _board,
        _pool,
        task,
        agent,
        _dispatch,
        _token,
        _,
    ) = _installed_campaign_recovery_fixture()
    task.status = status
    task.metadata.pop("mission_control_owner_execution")

    assert orchestrator._campaign_recovery_task_is_exact(
        task,
        task.id,
        agent.id,
        0,
    ) is False


def test_campaign_pending_recovery_rejects_any_installed_owner_marker() -> None:
    (
        orchestrator,
        _board,
        _pool,
        task,
        agent,
        _dispatch,
        _token,
        _,
    ) = _installed_campaign_recovery_fixture()
    task.status = TaskStatus.PENDING
    task.assigned_to = None

    assert orchestrator._campaign_recovery_task_is_exact(
        task,
        task.id,
        agent.id,
        0,
    ) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "token_generation",
        "token_scheduled",
        "dispatch_generation",
        "dispatch_task",
        "dispatch_agent",
        "duplicate_registry",
        "raising_pool_attestation",
    ],
)
async def test_campaign_recovery_revokes_local_authority_without_invalid_ticket(
    mutation: str,
) -> None:
    (
        orchestrator,
        board,
        pool,
        task,
        agent,
        dispatch,
        token,
        _,
    ) = _installed_campaign_recovery_fixture()
    assert await pool.reserve(
        agent.id,
        task.id,
        reservation_token=token,
    ) is True
    key = (task.id, agent.id, 0)
    orchestrator._campaign_reservations[key] = token
    orchestrator._active_dispatches[task.id] = dispatch
    if mutation == "token_generation":
        token["attempt_generation"] = 1
    elif mutation == "token_scheduled":
        token["provider_task_scheduled"] = True
    elif mutation == "dispatch_generation":
        dispatch.metadata["attempt_generation"] = 1
    elif mutation == "dispatch_task":
        dispatch.task_id = "mutated-task"
    elif mutation == "dispatch_agent":
        dispatch.agent_id = "mutated-agent"
    elif mutation == "duplicate_registry":
        orchestrator._campaign_reservations[("duplicate-task", agent.id, 0)] = token
    elif mutation == "raising_pool_attestation":
        pool.owns_reservation = MagicMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("attestation failed")
        )
    else:  # pragma: no cover - parametrization is closed above
        raise AssertionError(mutation)

    ticket = orchestrator._prepare_campaign_before_effect_recovery(
        dispatch,
        agent.id,
        token,
        allow_uninstalled_active=False,
    )

    assert ticket is None
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}
    assert pool._reservation_tokens[agent.id] == (task.id, token)
    assert agent.status is AgentStatus.BUSY
    assert agent.current_task == task.id
    assert task.status is TaskStatus.ASSIGNED
    assert "campaign_dispatch_recovery" not in task.metadata
    assert board.updates == []


@pytest.mark.asyncio
async def test_campaign_release_loss_precedes_and_prevents_board_recovery() -> None:
    (
        orchestrator,
        board,
        pool,
        task,
        agent,
        dispatch,
        token,
        _,
    ) = _installed_campaign_recovery_fixture()
    assert await pool.reserve(
        agent.id,
        task.id,
        reservation_token=token,
    ) is True
    key = (task.id, agent.id, 0)
    orchestrator._campaign_reservations[key] = token
    orchestrator._active_dispatches[task.id] = dispatch
    original_release = pool.release_reservation
    release_entered = asyncio.Event()
    release_allowed = asyncio.Event()

    async def interleaved_release(agent_id, task_id, *, reservation_token=None):
        release_entered.set()
        await release_allowed.wait()
        return await original_release(
            agent_id,
            task_id,
            reservation_token=reservation_token,
        )

    pool.release_reservation = interleaved_release  # type: ignore[method-assign]
    ticket = orchestrator._prepare_campaign_before_effect_recovery(
        dispatch,
        agent.id,
        token,
        allow_uninstalled_active=False,
    )
    assert ticket is not None
    pending = asyncio.create_task(
        orchestrator._finish_campaign_before_effect_recovery(token, ticket)
    )
    await asyncio.wait_for(release_entered.wait(), timeout=2)
    foreign_token = {
        "reservation_id": "foreign-release-race",
        "attempt_generation": 1,
        "provider_task_scheduled": False,
    }
    pool._reservation_tokens[agent.id] = (task.id, foreign_token)
    release_allowed.set()

    assert await asyncio.wait_for(pending, timeout=2) is False
    assert task.status is TaskStatus.ASSIGNED
    assert "campaign_dispatch_recovery" not in task.metadata
    assert board.updates == []
    assert pool._reservation_tokens[agent.id] == (task.id, foreign_token)
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}
    assert list(orchestrator._campaign_recovery_owners) == [id(token)]

    summary = await orchestrator.graceful_stop(0.01)
    assert summary["live_task_ids"] == [task.id]
    assert summary["campaign_recovery_task_ids"] == [task.id]
    assert orchestrator._campaign_recovery_owners[id(token)][1] is token


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    ["token_scheduled", "dispatch_generation", "dispatch_task", "dispatch_agent"],
)
async def test_campaign_outer_recovery_is_disarmed_after_coordinate_mutation(
    mutation: str,
) -> None:
    (
        orchestrator,
        board,
        pool,
        task,
        agent,
        _,
        _,
        _,
    ) = _installed_campaign_recovery_fixture()
    task.status = TaskStatus.PENDING
    task.assigned_to = None
    installed_token = None

    async def mutate_then_raise(
        dispatch,
        *,
        authenticated_principal_id="",
        reservation_token=None,
        campaign_effect_fence=None,
    ):
        nonlocal installed_token
        installed_token = reservation_token
        assert await pool.reserve(
            agent.id,
            task.id,
            reservation_token=reservation_token,
        ) is True
        key = (task.id, agent.id, 0)
        orchestrator._campaign_reservations[key] = reservation_token
        orchestrator._active_dispatches[task.id] = dispatch
        dispatch.metadata["_campaign_active_owner_installed"] = True
        task.status = TaskStatus.ASSIGNED
        task.assigned_to = agent.id
        if mutation == "token_scheduled":
            reservation_token["provider_task_scheduled"] = True
        elif mutation == "dispatch_generation":
            dispatch.metadata["attempt_generation"] = 1
        elif mutation == "dispatch_task":
            dispatch.task_id = "mutated-task"
        elif mutation == "dispatch_agent":
            dispatch.agent_id = "mutated-agent"
        else:  # pragma: no cover - parametrization is closed above
            raise AssertionError(mutation)
        raise RuntimeError("mutated pre-effect coordinates")

    orchestrator._assign_dispatch = mutate_then_raise  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="mutated pre-effect coordinates"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=agent.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    assert installed_token is not None
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}
    assert pool._reservation_tokens[agent.id] == (task.id, installed_token)
    assert task.status is TaskStatus.ASSIGNED
    assert "campaign_dispatch_recovery" not in task.metadata
    assert board.updates == []


@pytest.mark.asyncio
async def test_campaign_repeated_cancellation_cannot_rearm_outer_recovery() -> None:
    (
        orchestrator,
        _,
        pool,
        task,
        agent,
        _,
        _,
        _,
    ) = _installed_campaign_recovery_fixture()
    task.status = TaskStatus.PENDING
    task.assigned_to = None
    assignment_entered = asyncio.Event()
    assignment_never_finishes = asyncio.Event()
    release_entered = asyncio.Event()
    release_allowed = asyncio.Event()
    recovery_finished = asyncio.Event()
    original_release = pool.release_reservation
    original_resolve = orchestrator._board.resolve_campaign_pre_effect_failure

    async def blocked_release(agent_id, task_id, *, reservation_token=None):
        release_entered.set()
        await release_allowed.wait()
        return await original_release(
            agent_id,
            task_id,
            reservation_token=reservation_token,
        )

    async def observed_resolve(*args, **kwargs):
        outcome = await original_resolve(*args, **kwargs)
        recovery_finished.set()
        return outcome

    pool.release_reservation = blocked_release  # type: ignore[method-assign]
    orchestrator._board.resolve_campaign_pre_effect_failure = (  # type: ignore[method-assign]
        observed_resolve
    )

    async def install_then_block(
        dispatch,
        *,
        authenticated_principal_id="",
        reservation_token=None,
        campaign_effect_fence=None,
    ):
        assert await pool.reserve(
            agent.id,
            task.id,
            reservation_token=reservation_token,
        ) is True
        orchestrator._campaign_reservations[(task.id, agent.id, 0)] = (
            reservation_token
        )
        orchestrator._active_dispatches[task.id] = dispatch
        dispatch.metadata["_campaign_active_owner_installed"] = True
        task.status = TaskStatus.ASSIGNED
        task.assigned_to = agent.id
        assignment_entered.set()
        await assignment_never_finishes.wait()
        return True

    orchestrator._assign_dispatch = install_then_block  # type: ignore[method-assign]
    pending = asyncio.create_task(
        orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=agent.id,
            campaign_effect_fence=_allow_campaign_effect,
        )
    )
    await asyncio.wait_for(assignment_entered.wait(), timeout=2)
    pending.cancel()
    await asyncio.wait_for(release_entered.wait(), timeout=2)
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert task.status is TaskStatus.ASSIGNED
    assert recovery_finished.is_set() is False

    release_allowed.set()
    await asyncio.wait_for(recovery_finished.wait(), timeout=2)
    assert task.status is TaskStatus.CANCELLED
    assert task.metadata["campaign_dispatch_recovery"]["state"] == (
        "dispatch_indeterminate"
    )
    assert agent.status is AgentStatus.IDLE
    assert agent.current_task is None


@pytest.mark.asyncio
@pytest.mark.parametrize("substitution", ["pool", "active", "active_removed"])
async def test_campaign_early_assign_failure_never_mutates_foreign_custody(
    substitution: str,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-early-failure",
        title="Read-only campaign early failure",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-early-failure",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    runner = MagicMock()
    runner.state = exact
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(exact.id, runner)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    foreign_token = {
        "reservation_id": "foreign-early-owner",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    foreign_dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=exact.id,
        metadata={"attempt_generation": 0, "foreign": True},
    )
    original_token = None

    async def fail_after_assigned(td, *, task, status, **kwargs):
        nonlocal original_token
        if status != "claimed":
            return
        original_token = pool._reservation_tokens[exact.id][1]
        if substitution == "pool":
            pool._reservation_tokens[exact.id] = (td.task_id, foreign_token)
        elif substitution == "active":
            orchestrator._active_dispatches[td.task_id] = foreign_dispatch
        else:
            orchestrator._active_dispatches.pop(td.task_id, None)
        raise RuntimeError("early assigned fixture failure")

    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock(
        side_effect=fail_after_assigned
    )
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()

    with pytest.raises(RuntimeError, match="early assigned fixture failure"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    assert original_token is not None
    assert task.status is TaskStatus.ASSIGNED
    assert "campaign_dispatch_recovery" not in task.metadata
    assert [fields.get("status") for _, fields in board.updates] == [
        TaskStatus.ASSIGNED
    ]
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._running_tasks == {}
    runner.run_task.assert_not_awaited()
    if substitution == "pool":
        assert pool._reservation_tokens[exact.id] == (task.id, foreign_token)
        assert task.id not in orchestrator._active_dispatches
    else:
        assert pool._reservation_tokens[exact.id] == (task.id, original_token)
    if substitution == "active":
        assert orchestrator._active_dispatches[task.id] is foreign_dispatch
    elif substitution == "active_removed":
        assert task.id not in orchestrator._active_dispatches


@pytest.mark.asyncio
async def test_campaign_assigned_cas_failure_preserves_preinstall_foreign_active() -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-cas-failure",
        title="Read-only campaign CAS failure",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-cas-failure",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    runner = MagicMock()
    runner.state = exact
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(exact.id, runner)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    foreign_dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=exact.id,
        metadata={"attempt_generation": 0, "foreign": True},
    )
    original_cas = board.compare_and_swap_campaign_status

    async def commit_assigned_then_substitute_active(
        expected,
        *,
        new_status,
        assigned_to,
        metadata,
    ):
        await original_cas(
            expected,
            new_status=new_status,
            assigned_to=assigned_to,
            metadata=metadata,
        )
        orchestrator._active_dispatches[expected.id] = foreign_dispatch
        raise RuntimeError("post-ASSIGNED CAS fixture failure")

    board.compare_and_swap_campaign_status = (  # type: ignore[method-assign]
        commit_assigned_then_substitute_active
    )

    with pytest.raises(RuntimeError, match="post-ASSIGNED CAS fixture failure"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    original_token = pool._reservation_tokens[exact.id][1]
    assert task.status is TaskStatus.ASSIGNED
    assert "campaign_dispatch_recovery" not in task.metadata
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches[task.id] is foreign_dispatch
    assert pool._reservation_tokens[exact.id] == (task.id, original_token)
    assert original_token["provider_task_scheduled"] is False
    assert orchestrator._running_tasks == {}
    runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("substitution", ["registry", "pool", "active", "runner"])
async def test_campaign_final_prebackground_custody_recheck_blocks_substitution(
    substitution: str,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-final-hook",
        title="Read-only campaign final-hook fixture",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-final-hook",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    original_runner = MagicMock()
    original_runner.state = exact
    original_runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(exact.id, original_runner)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    foreign_token = {
        "reservation_id": "foreign-final-hook",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    foreign_dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=exact.id,
        metadata={"attempt_generation": 0, "foreign": True},
    )
    foreign_runner = MagicMock()
    foreign_runner.state = exact
    foreign_runner.run_task = AsyncMock(return_value="foreign must not run")
    original_token = None

    async def mutate_at_final_hook(event, *, task_id, agent_id, extra=None):
        nonlocal original_token
        if event != "task_started":
            return
        original_token = pool._reservation_tokens[exact.id][1]
        key = (task.id, exact.id, 0)
        if substitution == "registry":
            orchestrator._campaign_reservations[key] = foreign_token
        elif substitution == "pool":
            pool._reservation_tokens[exact.id] = (task.id, foreign_token)
        elif substitution == "active":
            orchestrator._active_dispatches[task.id] = foreign_dispatch
        elif substitution == "runner":
            pool.set_runner(exact.id, foreign_runner)
        else:  # pragma: no cover - parametrization is closed above
            raise AssertionError(substitution)

    orchestrator._emit_lifecycle_event = AsyncMock(  # type: ignore[method-assign]
        side_effect=mutate_at_final_hook
    )
    orchestrator._spine_dispatch_enabled = lambda: False  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="lost exact custody"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    assert original_token is not None
    assert original_token["provider_task_scheduled"] is False
    assert task.status is TaskStatus.RUNNING
    assert "campaign_dispatch_recovery" not in task.metadata
    assert orchestrator._running_tasks == {}
    original_runner.run_task.assert_not_awaited()
    foreign_runner.run_task.assert_not_awaited()
    key = (task.id, exact.id, 0)
    if substitution == "registry":
        assert orchestrator._campaign_reservations[key] is foreign_token
    else:
        assert key not in orchestrator._campaign_reservations
    if substitution == "active":
        assert orchestrator._active_dispatches[task.id] is foreign_dispatch
    else:
        assert task.id not in orchestrator._active_dispatches
    assert pool._reservation_tokens[exact.id] == (
        (task.id, foreign_token)
        if substitution == "pool"
        else (task.id, original_token)
    )
    if substitution == "runner":
        assert pool._runners[exact.id] is foreign_runner


@pytest.mark.asyncio
async def test_campaign_reacquires_runner_bound_by_reservation_before_execution(
    tmp_path: Path,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-runner-capture-race",
        title="Read-only campaign runner capture fixture",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-runner-capture-race",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([exact])
    stale_runner = MagicMock()
    stale_runner.state = exact
    stale_runner.run_task = AsyncMock(return_value="stale must not run")
    bound_runner = MagicMock()
    bound_runner.state = exact
    bound_runner._config = None

    async def run_bound(
        _task,
        *,
        campaign_effect_fence,
        campaign_effect_ready,
    ):
        await campaign_effect_fence()
        campaign_effect_ready()
        return "bound runner result"

    bound_runner.run_task = AsyncMock(side_effect=run_bound)
    pool.set_runner(exact.id, stale_runner)
    original_reserve = pool.reserve

    async def replace_after_guard_capture(
        agent_id,
        task_id,
        *,
        reservation_token=None,
    ):
        pool.set_runner(agent_id, bound_runner)
        return await original_reserve(
            agent_id,
            task_id,
            reservation_token=reservation_token,
        )

    pool.reserve = replace_after_guard_capture  # type: ignore[method-assign]
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        runtime_db_path=tmp_path / "campaign-runner-race-runtime.db",
    )
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]

    dispatches = await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=exact.id,
        campaign_effect_fence=_allow_campaign_effect,
    )
    await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=2)

    assert [dispatch.agent_id for dispatch in dispatches] == [exact.id]
    stale_runner.run_task.assert_not_awaited()
    bound_runner.run_task.assert_awaited_once()
    assert pool._runners[exact.id] is bound_runner


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault_status", "resolved_status"),
    [
        (TaskStatus.ASSIGNED, TaskStatus.PENDING),
        (TaskStatus.RUNNING, TaskStatus.CANCELLED),
    ],
)
async def test_campaign_board_write_failure_never_schedules_provider(
    fault_status: TaskStatus,
    resolved_status: TaskStatus,
) -> None:
    exact = AgentState(
        id="campaign-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    task = Task(
        id="campaign-task",
        title="Read-only campaign task",
        metadata=_owner_stamped_campaign_metadata(
            exact.id,
            "campaign-task",
            provider=exact.provider,
            model=exact.model,
        ),
    )
    board = MockTaskBoard()
    board.tasks = [task]
    original_update = board.update_task

    async def fail_exact_write(task_id, **fields):
        if fields.get("status") is fault_status:
            raise RuntimeError(f"{fault_status.value} write failed")
        await original_update(task_id, **fields)

    board.update_task = fail_exact_write  # type: ignore[method-assign]
    pool = MockAgentPool([exact])
    runner = MagicMock()
    runner.state = exact
    runner.run_task = AsyncMock()
    pool.set_runner(exact.id, runner)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()

    with pytest.raises(RuntimeError, match="write failed"):
        await orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=exact.id,
            campaign_effect_fence=_allow_campaign_effect,
        )

    assert task.status is resolved_status
    if fault_status is TaskStatus.RUNNING:
        assert task.metadata["campaign_dispatch_recovery"]["state"] == "dispatch_indeterminate"
    assert exact.status is AgentStatus.IDLE
    assert exact.current_task is None
    runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_board_identity_is_persisted_before_provider_effect(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm.task_board import TaskBoard

    agent = AgentState(
        id="campaign-identity-agent",
        name="campaign-seat",
        role=AgentRole.CODER,
        status=AgentStatus.IDLE,
        provider="ollama",
        model="fixture-model:cloud",
    )
    monkeypatch.setattr(
        "dharma_swarm.task_board._new_id",
        lambda: "campaign-identity-task",
    )
    board = TaskBoard(tmp_path / "campaign-tasks.db")
    await board.init_db()
    task = await board.create(
        "Campaign identity fixture",
        metadata=_owner_stamped_campaign_metadata(
            agent.id,
            "campaign-identity-task",
            provider=agent.provider,
            model=agent.model,
        ),
    )
    pool = MockAgentPool([agent])
    provider_effect_checked = asyncio.Event()

    class _IdentityRunner:
        state = agent

        async def run_task(
            self,
            _task,
            *,
            campaign_effect_fence,
            campaign_effect_ready,
        ):
            await campaign_effect_fence()
            campaign_effect_ready()
            provider_effect_checked.set()
            return "identity-bound result"

    pool.set_runner(agent.id, _IdentityRunner())
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        runtime_db_path=tmp_path / "campaign-identity-runtime.db",
    )

    async def enrich(_task, _td, metadata):
        return {**metadata, "context_enriched_after_identity": True}

    orchestrator._attach_context_bundle = enrich  # type: ignore[method-assign]
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]

    async def fence() -> None:
        observed = await board.get(task.id)
        assert observed is not None
        assert observed.status is TaskStatus.RUNNING
        assert observed.assigned_to == agent.id
        identity = observed.metadata["execution_identity"]
        assert set(identity) == {
            "trace_id", "correlation_id", "task_id", "run_id", "claim_id",
            "idempotency_key", "causation_id", "parent_run_id", "agent_id",
            "session_id", "external_a2a_task_id", "message_id", "event_id",
            "artifact_id", "proposal_id", "metadata",
        }
        assert observed.metadata["context_enriched_after_identity"] is True
        assert observed.metadata["execution_identity_surface"] == "orchestrator"
        for key in (
            "trace_id", "correlation_id", "run_id", "claim_id",
            "idempotency_key", "agent_id", "session_id",
        ):
            assert observed.metadata[key] == identity[key]

    dispatches = await orchestrator.dispatch(
        task,
        TopologyType.PIPELINE,
        authenticated_principal_id=agent.id,
        campaign_effect_fence=fence,
    )
    await asyncio.wait_for(provider_effect_checked.wait(), timeout=2)
    with pytest.raises(
        RuntimeError,
        match="completion projection is not durable on Board",
    ):
        await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=2)

    assert [dispatch.agent_id for dispatch in dispatches] == [agent.id]
    dispatch = dispatches[0]
    token = pool._reservation_tokens[agent.id][1]
    retained = await board.get(task.id)
    assert retained is not None and retained.status is TaskStatus.RUNNING
    assert agent.status is AgentStatus.BUSY and agent.current_task == task.id
    assert orchestrator._active_dispatches[task.id] is dispatch
    assert orchestrator._campaign_recovery_owners[id(token)] == [
        dispatch,
        token,
        None,
        False,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("fault_status", [TaskStatus.ASSIGNED, TaskStatus.RUNNING])
@pytest.mark.parametrize("fault_mode", ["write", "readback"])
async def test_generic_board_failure_retains_owner_when_readback_is_unproven(
    fault_status: TaskStatus,
    fault_mode: str,
) -> None:
    agent = AgentState(
        id="generic-exact-agent",
        name="generic-exact-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="generic-exact-task", title="Generic exact Board fixture")
    board = MockTaskBoard()
    board.tasks = [task]
    original_update = board.update_task
    original_get = board.get
    faulted = False

    async def faulting_update(task_id, **fields):
        nonlocal faulted
        if fields.get("status") is fault_status:
            faulted = True
            if fault_mode == "write":
                raise RuntimeError(f"{fault_status.value} write failed")
        await original_update(task_id, **fields)

    async def faulting_get(task_id):
        observed = await original_get(task_id)
        if faulted and fault_mode == "readback":
            return SimpleNamespace(
                id=task_id,
                status=fault_status,
                assigned_to=agent.id,
                metadata={"forged": True},
            )
        return observed

    board.update_task = faulting_update  # type: ignore[method-assign]
    board.get = faulting_get  # type: ignore[method-assign]
    pool = MockAgentPool([agent])
    runner = MagicMock()
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(agent.id, runner)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()

    with pytest.raises(RuntimeError, match="write failed|lacks exact readback"):
        await orchestrator.dispatch(task, TopologyType.PIPELINE)

    if fault_mode == "write":
        assert agent.status is AgentStatus.IDLE
        assert agent.current_task is None
        assert agent.id not in pool._reservation_tokens
        assert orchestrator._active_dispatches == {}
    else:
        assert agent.status is AgentStatus.BUSY
        assert agent.current_task == task.id
        assert pool._reservation_tokens[agent.id][0] == task.id
        assert orchestrator._active_dispatches[task.id].agent_id == agent.id
    assert orchestrator._running_tasks == {}
    runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_generic_assigned_failure_never_releases_substituted_pool_owner() -> None:
    agent = AgentState(
        id="generic-race-agent",
        name="generic-race-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="generic-race-task", title="Generic custody race fixture")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    runner = MagicMock()
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(agent.id, runner)
    foreign = TaskDispatch(task_id=task.id, agent_id=agent.id)

    async def substitute_then_fail(task_id, **fields):
        if fields.get("status") is TaskStatus.ASSIGNED:
            pool._reservation_tokens[agent.id] = (task.id, foreign)
            raise RuntimeError("ASSIGNED write failed after owner substitution")

    board.update_task = substitute_then_fail  # type: ignore[method-assign]
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )

    with pytest.raises(RuntimeError, match="owner substitution"):
        await orchestrator.dispatch(task, TopologyType.PIPELINE)

    assert pool._reservation_tokens[agent.id] == (task.id, foreign)
    assert agent.status is AgentStatus.BUSY
    assert agent.current_task == task.id
    assert orchestrator._active_dispatches == {}
    assert len(orchestrator._generic_recovery_owners) == 1
    recovery = next(iter(orchestrator._generic_recovery_owners.values()))
    assert recovery[0].task_id == task.id
    assert orchestrator._running_tasks == {}
    runner.run_task.assert_not_awaited()

    summary = await orchestrator.graceful_stop(0)
    assert summary["live_task_ids"] == [task.id]
    assert summary["indeterminate_custody_task_ids"] == [task.id]


@pytest.mark.asyncio
async def test_exact_release_completion_does_not_pop_interleaved_active_owner() -> None:
    from dharma_swarm.orchestrator_execution import release_generic_dispatch

    agent = AgentState(
        id="exact-release-race-agent",
        name="exact-release-race-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    pool = MockAgentPool([agent])
    orchestrator = Orchestrator(agent_pool=pool)
    stale = TaskDispatch(task_id="exact-release-race-task", agent_id=agent.id)
    foreign = TaskDispatch(task_id=stale.task_id, agent_id=agent.id)
    assert await pool.reserve(agent.id, stale.task_id, reservation_token=stale)
    orchestrator._active_dispatches[stale.task_id] = stale
    original_release = pool.release_reservation

    async def release_then_reassign(agent_id, task_id, *, reservation_token=None):
        assert await original_release(
            agent_id, task_id, reservation_token=reservation_token
        )
        assert await pool.reserve(agent_id, task_id, reservation_token=foreign)
        orchestrator._active_dispatches[task_id] = foreign
        return True

    pool.release_reservation = release_then_reassign  # type: ignore[method-assign]

    assert await release_generic_dispatch(orchestrator, stale) is True
    assert orchestrator._active_dispatches[stale.task_id] is foreign
    assert pool._reservation_tokens[agent.id] == (stale.task_id, foreign)
    assert agent.status is AgentStatus.BUSY and agent.current_task == stale.task_id


@pytest.mark.asyncio
async def test_legacy_pool_dispatch_lifecycle_uses_local_opaque_owner(
    monkeypatch,
) -> None:
    agent = AgentState(
        id="legacy-agent",
        name="legacy-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="legacy-task", title="Legacy pool lifecycle")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = LegacyDispatchPool(agent, DummyRunner(result="legacy complete"))
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )

    def exact_identity_without_receipt(td, *, task=None, require=False):
        identity = _ensure_fixture_execution_identity(td, task=task, require=require)
        td.metadata.pop("evidence_receipt_id", None)
        return identity

    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=exact_identity_without_receipt
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: False  # type: ignore[method-assign]
    sidecar = MagicMock()
    sidecar.consolidate_knowledge = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "dharma_swarm.sleep_time_agent.SleepTimeAgent",
        MagicMock(return_value=sidecar),
    )

    dispatches = await orchestrator.dispatch(task, TopologyType.PIPELINE)
    dispatch = dispatches[0]
    assert orchestrator._legacy_dispatch_owners[agent.id] is dispatch
    await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=2)

    assert pool.assignments == [(agent.id, task.id)]
    assert pool.releases == [agent.id]
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert orchestrator._legacy_dispatch_owners == {}
    assert orchestrator._active_dispatches == {}
    assert (await board.get(task.id)).status is TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_legacy_owner_is_installed_before_assign_can_yield() -> None:
    from dharma_swarm.orchestrator_execution import reserve_generic_dispatch

    agent = AgentState(
        id="legacy-blocked-agent",
        name="legacy-blocked-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    pool = LegacyDispatchPool(agent, block_assign=True)
    orchestrator = Orchestrator(agent_pool=pool)
    dispatch = TaskDispatch(task_id="legacy-blocked-task", agent_id=agent.id)
    pending = asyncio.create_task(reserve_generic_dispatch(orchestrator, dispatch))
    await asyncio.wait_for(pool.assign_entered.wait(), timeout=2)

    assert orchestrator._legacy_dispatch_owners[agent.id] is dispatch
    assert orchestrator._active_dispatches[dispatch.task_id] is dispatch

    pool.assign_continue.set()
    assert await asyncio.wait_for(pending, timeout=2) is True


@pytest.mark.asyncio
async def test_legacy_stale_dispatch_cannot_release_foreign_local_owner() -> None:
    from dharma_swarm.orchestrator_execution import (
        release_generic_dispatch,
        reserve_generic_dispatch,
    )

    agent = AgentState(
        id="legacy-stale-agent",
        name="legacy-stale-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    pool = LegacyDispatchPool(agent)
    orchestrator = Orchestrator(agent_pool=pool)
    stale = TaskDispatch(task_id="legacy-stale-task", agent_id=agent.id)
    foreign = TaskDispatch(task_id=stale.task_id, agent_id=agent.id)
    assert await reserve_generic_dispatch(orchestrator, stale) is True
    orchestrator._legacy_dispatch_owners[agent.id] = foreign
    orchestrator._active_dispatches[stale.task_id] = foreign

    assert await release_generic_dispatch(orchestrator, stale) is False
    assert pool.releases == []
    assert orchestrator._legacy_dispatch_owners[agent.id] is foreign
    assert orchestrator._active_dispatches[stale.task_id] is foreign


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_legacy_release_failure_retains_opaque_owner(error_type) -> None:
    from dharma_swarm.orchestrator_execution import (
        release_generic_dispatch,
        reserve_generic_dispatch,
    )

    agent = AgentState(
        id="legacy-release-agent",
        name="legacy-release-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    pool = LegacyDispatchPool(agent)
    orchestrator = Orchestrator(agent_pool=pool)
    dispatch = TaskDispatch(task_id="legacy-release-task", agent_id=agent.id)
    assert await reserve_generic_dispatch(orchestrator, dispatch) is True
    pool.release_error = error_type("release interrupted")

    with pytest.raises(error_type, match="release interrupted"):
        await release_generic_dispatch(orchestrator, dispatch)

    assert orchestrator._legacy_dispatch_owners[agent.id] is dispatch
    assert orchestrator._active_dispatches[dispatch.task_id] is dispatch


@pytest.mark.asyncio
async def test_generic_dispatch_cancellation_before_background_quarantines_and_releases() -> None:
    agent = AgentState(
        id="cancel-setup-agent",
        name="cancel-setup-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="cancel-setup-task", title="Cancel before background")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    pool.set_runner(agent.id, DummyRunner(result="must not run"))
    send_entered = asyncio.Event()

    class _BlockingBus:
        async def send(self, message):
            send_entered.set()
            await asyncio.Event().wait()

    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        message_bus=_BlockingBus(),
    )
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    pending = asyncio.create_task(
        orchestrator.dispatch(task, TopologyType.PIPELINE)
    )
    await asyncio.wait_for(send_entered.wait(), timeout=2)
    pending.cancel()

    with pytest.raises(asyncio.CancelledError):
        await pending

    recovered = await board.get(task.id)
    assert recovered.status is TaskStatus.FAILED
    assert recovered.metadata["dispatch_setup_recovery"] == {
        "schema_version": "dharma.dispatch_setup_recovery.v1",
        "state": "quarantined",
        "prior_status": "assigned",
        "cause": "CancelledError",
    }
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert agent.id not in pool._reservation_tokens
    assert orchestrator._active_dispatches == {}
    assert orchestrator._running_tasks == {}


@pytest.mark.asyncio
async def test_generic_dispatch_cancellation_from_running_board_quarantines_and_releases() -> None:
    agent = AgentState(
        id="cancel-running-agent",
        name="cancel-running-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="cancel-running-task", title="Cancel from running Board")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    pool.set_runner(agent.id, DummyRunner(result="must not run"))
    running_claim_entered = asyncio.Event()

    async def block_running_claim(td, *, task=None, status, **kwargs):
        if status == "running":
            running_claim_entered.set()
            await asyncio.Event().wait()

    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = block_running_claim
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    pending = asyncio.create_task(orchestrator.dispatch(task, TopologyType.PIPELINE))
    await asyncio.wait_for(running_claim_entered.wait(), timeout=2)
    pending.cancel()

    with pytest.raises(asyncio.CancelledError):
        await pending

    recovered = await board.get(task.id)
    assert recovered.status is TaskStatus.FAILED
    assert recovered.metadata["dispatch_setup_recovery"]["prior_status"] == "running"
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert agent.id not in pool._reservation_tokens
    assert orchestrator._active_dispatches == {}
    assert orchestrator._running_tasks == {}


@pytest.mark.asyncio
async def test_legacy_assign_cancellation_shield_releases_local_owner() -> None:
    agent = AgentState(
        id="legacy-cancel-agent",
        name="legacy-cancel-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="legacy-cancel-task", title="Cancel legacy assign")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = LegacyDispatchPool(agent, block_assign=True)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    pending = asyncio.create_task(orchestrator.dispatch(task, TopologyType.PIPELINE))
    await asyncio.wait_for(pool.assign_entered.wait(), timeout=2)
    pending.cancel()

    with pytest.raises(asyncio.CancelledError):
        await pending

    assert pool.releases == [agent.id]
    assert orchestrator._legacy_dispatch_owners == {}
    assert orchestrator._active_dispatches == {}
    assert (await board.get(task.id)).status is TaskStatus.PENDING


@pytest.mark.asyncio
async def test_graceful_stop_recovers_exact_active_owner_without_running_task() -> None:
    agent = AgentState(
        id="orphan-setup-agent",
        name="orphan-setup-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(
        id="orphan-setup-task",
        title="Orphaned pre-background owner",
        status=TaskStatus.ASSIGNED,
        assigned_to=agent.id,
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    assert await pool.reserve(agent.id, task.id, reservation_token=dispatch)
    orchestrator._active_dispatches[task.id] = dispatch

    summary = await orchestrator.graceful_stop(0)

    assert summary == {"cancelled": 0, "completed": 0, "recovered": 1}
    assert (await board.get(task.id)).status is TaskStatus.FAILED
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert agent.id not in pool._reservation_tokens
    assert orchestrator._active_dispatches == {}


@pytest.mark.asyncio
async def test_graceful_stop_cancels_assignment_before_background_and_quarantines() -> None:
    agent = AgentState(
        id="stop-setup-agent",
        name="stop-setup-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="stop-setup-task", title="Stop during assignment")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    runner = MagicMock()
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(agent.id, runner)
    send_entered = asyncio.Event()

    class _BlockingBus:
        async def send(self, message):
            send_entered.set()
            await asyncio.Event().wait()

    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        message_bus=_BlockingBus(),
    )
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    pending = asyncio.create_task(orchestrator.dispatch(task, TopologyType.PIPELINE))
    await asyncio.wait_for(send_entered.wait(), timeout=2)

    summary = await orchestrator.graceful_stop(timeout=1)
    outcome = await asyncio.gather(pending, return_exceptions=True)

    assert isinstance(outcome[0], asyncio.CancelledError)
    assert summary == {
        "cancelled": 0,
        "completed": 0,
        "assignment_cancelled": 1,
    }
    recovered = await board.get(task.id)
    assert recovered.status is TaskStatus.FAILED
    assert recovered.metadata["dispatch_setup_recovery"]["prior_status"] == "assigned"
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert orchestrator._assignment_tasks == {}
    assert orchestrator._active_dispatches == {}
    assert orchestrator._running_tasks == {}
    runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_graceful_stop_reports_cancellation_resistant_assignment_live() -> None:
    agent = AgentState(
        id="stubborn-setup-agent",
        name="stubborn-setup-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="stubborn-setup-task", title="Stubborn assignment")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    provider_started = asyncio.Event()
    provider_never_finishes = asyncio.Event()
    cancellation_seen = asyncio.Event()
    release_bus = asyncio.Event()

    class _BlockedRunner:
        async def run_task(self, _task):
            provider_started.set()
            await provider_never_finishes.wait()

    class _CancellationResistantBus:
        async def send(self, message):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancellation_seen.set()
                await release_bus.wait()

    pool.set_runner(agent.id, _BlockedRunner())
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        message_bus=_CancellationResistantBus(),
    )
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    pending = asyncio.create_task(orchestrator.dispatch(task, TopologyType.PIPELINE))
    while task.id not in orchestrator._assignment_tasks:
        await asyncio.sleep(0)
    while (await board.get(task.id)).status is not TaskStatus.ASSIGNED:
        await asyncio.sleep(0)

    summary = await orchestrator.graceful_stop(timeout=0.01)

    await asyncio.wait_for(cancellation_seen.wait(), timeout=2)
    assert summary["live"] == 1
    assert summary["live_task_ids"] == [task.id]
    assert summary["assignment_cancelled"] == 1
    assert orchestrator._active_dispatches[task.id].agent_id == agent.id
    assert pending.done() is False

    release_bus.set()
    await asyncio.gather(pending, return_exceptions=True)
    assert provider_started.is_set() is False
    cleanup = await orchestrator.graceful_stop(timeout=1)
    assert cleanup.get("live", 0) == 0
    assert (await board.get(task.id)).status is TaskStatus.FAILED
    assert orchestrator._assignment_tasks == {}
    assert orchestrator._active_dispatches == {}
    assert orchestrator._running_tasks == {}
    assert orchestrator._running_dispatch_owners == {}


@pytest.mark.asyncio
async def test_concurrent_graceful_stop_shares_one_legacy_release() -> None:
    agent = AgentState(
        id="legacy-stop-agent",
        name="legacy-stop-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(
        id="legacy-stop-task",
        title="Concurrent stop",
        status=TaskStatus.ASSIGNED,
        assigned_to=agent.id,
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = LegacyDispatchPool(agent)
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    from dharma_swarm.orchestrator_execution import reserve_generic_dispatch

    assert await reserve_generic_dispatch(orchestrator, dispatch) is True

    first, second = await asyncio.gather(
        orchestrator.graceful_stop(1),
        orchestrator.graceful_stop(1),
    )

    assert first == second == {"cancelled": 0, "completed": 0, "recovered": 1}
    assert pool.releases == [agent.id]
    assert orchestrator._active_dispatches == {}
    assert orchestrator._legacy_dispatch_owners == {}


@pytest.mark.asyncio
async def test_tracked_owner_cannot_synchronously_stop_itself() -> None:
    orchestrator = Orchestrator()
    current = asyncio.current_task()
    assert current is not None
    orchestrator._assignment_tasks["self-stop"] = current

    with pytest.raises(RuntimeError, match="cannot synchronously stop itself"):
        await orchestrator.graceful_stop(0)

    assert orchestrator._stopping is False
    assert orchestrator._stop_operation is None


@pytest.mark.asyncio
async def test_assignment_owner_cannot_nest_a_second_dispatch() -> None:
    orchestrator = Orchestrator()
    current = asyncio.current_task()
    assert current is not None
    orchestrator._assignment_tasks["outer-dispatch"] = current
    nested = TaskDispatch(task_id="nested-dispatch", agent_id="nested-agent")

    with pytest.raises(RuntimeError, match="already owns an in-progress assignment"):
        await orchestrator._assign_dispatch(nested)

    assert list(orchestrator._assignment_tasks) == ["outer-dispatch"]
    assert orchestrator._active_dispatches == {}


@pytest.mark.asyncio
async def test_graceful_stop_clears_done_running_owner_after_exact_recovery() -> None:
    agent = AgentState(
        id="done-owner-agent",
        name="done-owner-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(
        id="done-owner-task",
        title="Done owner recovery",
        status=TaskStatus.ASSIGNED,
        assigned_to=agent.id,
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    assert await pool.reserve(agent.id, task.id, reservation_token=dispatch)
    completed = asyncio.create_task(asyncio.sleep(0))
    await completed
    orchestrator._active_dispatches[task.id] = dispatch
    orchestrator._running_tasks[task.id] = completed
    orchestrator._running_dispatch_owners[task.id] = (completed, dispatch)

    summary = await orchestrator.graceful_stop(1)

    assert summary == {"cancelled": 0, "completed": 1, "recovered": 1}
    assert orchestrator._active_dispatches == {}
    assert orchestrator._running_tasks == {}
    assert orchestrator._running_dispatch_owners == {}


@pytest.mark.asyncio
async def test_graceful_stop_bounds_hung_orphan_recovery_and_keeps_it_live() -> None:
    agent = AgentState(
        id="hung-recovery-agent",
        name="hung-recovery-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(
        id="hung-recovery-task",
        title="Hung recovery",
        status=TaskStatus.ASSIGNED,
        assigned_to=agent.id,
    )
    board = MockTaskBoard()
    board.tasks = [task]
    allow_read = asyncio.Event()
    original_get = board.get

    async def blocking_get(task_id):
        await allow_read.wait()
        return await original_get(task_id)

    board.get = blocking_get  # type: ignore[method-assign]
    pool = MockAgentPool([agent])
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    assert await pool.reserve(agent.id, task.id, reservation_token=dispatch)
    orchestrator._active_dispatches[task.id] = dispatch

    summary = await asyncio.wait_for(orchestrator.graceful_stop(0.01), timeout=0.2)

    assert summary["live_task_ids"] == [task.id]
    assert summary["recovery_pending_task_ids"] == [task.id]
    assert orchestrator._active_dispatches[task.id] is dispatch
    assert any(not pending.done() for pending in orchestrator._recovery_tasks.values())

    allow_read.set()
    cleanup = await asyncio.wait_for(orchestrator.graceful_stop(1), timeout=2)
    assert cleanup.get("live", 0) == 0
    assert (await original_get(task.id)).status is TaskStatus.FAILED
    assert orchestrator._recovery_tasks == {}
    assert orchestrator._active_dispatches == {}


@pytest.mark.asyncio
async def test_generic_reserve_cancellation_keeps_provisional_owner_visible() -> None:
    agent = AgentState(
        id="opaque-reserve-agent",
        name="opaque-reserve-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="opaque-reserve-task", title="Opaque reserve cancellation")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    pool.owns_reservation = None  # type: ignore[method-assign]
    reserve_entered = asyncio.Event()
    original_reserve = pool.reserve

    async def acquire_then_block(agent_id, task_id, *, reservation_token=None):
        assert await original_reserve(
            agent_id, task_id, reservation_token=reservation_token
        )
        reserve_entered.set()
        await asyncio.Event().wait()

    pool.reserve = acquire_then_block  # type: ignore[method-assign]
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    pending = asyncio.create_task(orchestrator.dispatch(task, TopologyType.PIPELINE))
    await asyncio.wait_for(reserve_entered.wait(), timeout=2)

    summary = await orchestrator.graceful_stop(1)
    outcome = await asyncio.gather(pending, return_exceptions=True)

    assert isinstance(outcome[0], asyncio.CancelledError)
    assert summary.get("live", 0) == 0
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert pool._reservation_tokens == {}
    assert orchestrator._active_dispatches == {}
    assert orchestrator._generic_recovery_owners == {}


@pytest.mark.asyncio
async def test_campaign_reserve_cancellation_recovers_provisional_tombstone(
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    task = _campaign_task(config)
    board = MockTaskBoard()
    board.tasks = [task]
    agent = AgentState(
        id=config.id,
        name=config.name,
        role=config.role,
        status=AgentStatus.IDLE,
        provider=config.provider,
        model=config.model,
    )
    pool = MockAgentPool([agent])
    runner = MagicMock()
    runner.state = agent
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(agent.id, runner)
    reserve_entered = asyncio.Event()
    original_reserve = pool.reserve

    async def acquire_then_block(agent_id, task_id, *, reservation_token=None):
        assert await original_reserve(
            agent_id, task_id, reservation_token=reservation_token
        )
        reserve_entered.set()
        await asyncio.Event().wait()

    pool.reserve = acquire_then_block  # type: ignore[method-assign]
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    pending = asyncio.create_task(
        orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=agent.id,
            campaign_effect_fence=_allow_campaign_effect,
        )
    )
    await asyncio.wait_for(reserve_entered.wait(), timeout=2)

    summary = await orchestrator.graceful_stop(1)
    outcome = await asyncio.gather(pending, return_exceptions=True)

    assert isinstance(outcome[0], asyncio.CancelledError)
    assert summary.get("live", 0) == 0
    assert summary["recovered"] == 1
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert orchestrator._campaign_recovery_owners == {}
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}
    assert (await board.get(task.id)).status is TaskStatus.PENDING
    runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_cancellation_resistant_reserve_hits_admission_fence(
    tmp_path: Path,
) -> None:
    config = _campaign_config(tmp_path)
    task = _campaign_task(config, task_id="campaign-stubborn-reserve")
    board = MockTaskBoard()
    board.tasks = [task]
    agent = AgentState(
        id=config.id,
        name=config.name,
        role=config.role,
        status=AgentStatus.IDLE,
        provider=config.provider,
        model=config.model,
    )
    pool = MockAgentPool([agent])
    runner = MagicMock()
    runner.state = agent
    runner.run_task = AsyncMock(return_value="must not run")
    pool.set_runner(agent.id, runner)
    reserve_entered = asyncio.Event()
    cancellation_seen = asyncio.Event()
    finish_reserve = asyncio.Event()
    original_reserve = pool.reserve

    async def acquire_then_resist_cancel(
        agent_id, task_id, *, reservation_token=None
    ):
        assert await original_reserve(
            agent_id, task_id, reservation_token=reservation_token
        )
        reserve_entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellation_seen.set()
            await finish_reserve.wait()
            return True

    pool.reserve = acquire_then_resist_cancel  # type: ignore[method-assign]
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    pending = asyncio.create_task(
        orchestrator.dispatch(
            task,
            TopologyType.PIPELINE,
            authenticated_principal_id=agent.id,
            campaign_effect_fence=_allow_campaign_effect,
        )
    )
    await asyncio.wait_for(reserve_entered.wait(), timeout=2)

    first = await orchestrator.graceful_stop(0.01)

    await asyncio.wait_for(cancellation_seen.wait(), timeout=2)
    assert first["live_task_ids"] == [task.id]
    assert first["assignment_cancelled"] == 1
    assert (await board.get(task.id)).status is TaskStatus.PENDING
    assert agent.status is AgentStatus.BUSY and agent.current_task == task.id
    assert pending.done() is False

    finish_reserve.set()
    outcome = await asyncio.gather(pending, return_exceptions=True)
    assert isinstance(outcome[0], asyncio.CancelledError)
    cleanup = await orchestrator.graceful_stop(1)

    assert cleanup.get("live", 0) == 0
    assert (await board.get(task.id)).status is TaskStatus.PENDING
    assert agent.status is AgentStatus.IDLE and agent.current_task is None
    assert orchestrator._campaign_recovery_owners == {}
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._active_dispatches == {}
    runner.run_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_after_graceful_stop_has_no_pool_or_board_effects() -> None:
    agent = AgentState(
        id="fenced-agent",
        name="fenced-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="fenced-task", title="Admission fenced")
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    assert await orchestrator.graceful_stop(0) == {"cancelled": 0, "completed": 0}

    assert await orchestrator.dispatch(task, TopologyType.PIPELINE) == []
    assert board.updates == []
    assert pool._assignments == []
    assert orchestrator._active_dispatches == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    ["genome", "_dispatch_swarm", "_dispatch_supervisor", "_dispatch_subagents_as_tools"],
)
async def test_topology_helpers_do_not_report_rejected_dispatch(mode) -> None:
    agent = AgentState(
        id="rejected-topology-agent",
        name="rejected-topology-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="rejected-topology-task", title="Rejected topology")
    pool = MockAgentPool([agent])
    orchestrator = Orchestrator(agent_pool=pool)
    orchestrator._assign_dispatch = AsyncMock(return_value=False)  # type: ignore[method-assign]

    if mode == "genome":
        genome = SimpleNamespace(
            genome_id="rejected-genome",
            entrypoints=["root"],
            nodes=[SimpleNamespace(node_id="root")],
            validate_structure=MagicMock(),
            incoming_edge_ids=MagicMock(return_value=[]),
        )
        result = await orchestrator._dispatch_topology_genome(task, genome)
    else:
        result = await getattr(orchestrator, mode)(task, [agent])

    assert result == []


@pytest.mark.asyncio
async def test_route_next_does_not_report_rejected_dispatch() -> None:
    agent = AgentState(
        id="rejected-route-agent",
        name="rejected-route-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(id="rejected-route-task", title="Rejected route")
    board = MockTaskBoard()
    board.tasks = [task]
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=MockAgentPool([agent]),
    )
    orchestrator._assign_dispatch = AsyncMock(return_value=False)  # type: ignore[method-assign]

    assert await orchestrator.route_next() == []


@pytest.mark.asyncio
async def test_campaign_provider_failure_never_uses_generic_retry_requeue(
    monkeypatch,
) -> None:
    task = Task(
        id="campaign-provider-failure",
        title="Read-only campaign task",
        status=TaskStatus.RUNNING,
        assigned_to="campaign-agent",
        metadata={
            **_campaign_metadata(
                "campaign-agent",
                task_id="campaign-provider-failure",
            ),
            "max_retries": 5,
            "retry_count": 0,
        },
    )
    board = MockTaskBoard()
    board.tasks = [task]
    orchestrator = Orchestrator(task_board=board, agent_pool=MockAgentPool())
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="campaign-agent",
        topology=TopologyType.PIPELINE,
    )
    project = AsyncMock()
    monkeypatch.setattr(
        "dharma_swarm.orchestrator_execution.record_terminal_projection",
        project,
    )

    await orchestrator._handle_task_failure(
        td=dispatch,
        task=task,
        error="provider failed after scheduling",
        source="execution",
    )

    project.assert_awaited_once()
    assert project.await_args.kwargs["status"] == "failed"
    assert project.await_args.kwargs["action"] == "quarantine"
    assert board.updates == []


@pytest.mark.asyncio
async def test_campaign_failure_authority_survives_runner_metadata_stripping(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm import orchestrator_execution

    agent = AgentState(
        id="campaign-strip-agent",
        name="campaign-strip-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(
        id="campaign-strip-task",
        title="Immutable campaign failure authority",
        status=TaskStatus.RUNNING,
        assigned_to=agent.id,
        metadata={
            **_campaign_metadata(agent.id, task_id="campaign-strip-task"),
            "max_retries": 9,
            "retry_count": 0,
        },
    )
    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    _ensure_fixture_execution_identity(dispatch, task=task, require=True)
    dispatch.metadata.pop("evidence_receipt_id", None)
    token = {
        "reservation_id": "campaign-strip-reservation",
        "attempt_generation": 0,
        "provider_task_scheduled": False,
    }
    fence = AsyncMock()
    ready = MagicMock(
        side_effect=lambda: token.__setitem__("provider_task_scheduled", True)
    )

    class _MetadataStrippingRunner:
        _config = None

        async def run_task(self, affected_task, **kwargs):
            await kwargs["campaign_effect_fence"]()
            kwargs["campaign_effect_ready"]()
            affected_task.metadata.clear()
            raise RuntimeError("provider failed after stripping campaign authority")

    runner = _MetadataStrippingRunner()
    pool = MockAgentPool([agent])
    pool.set_runner(agent.id, runner)
    assert await pool.reserve(agent.id, task.id, reservation_token=token)
    board = MockTaskBoard()
    board.tasks = [task]
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        runtime_db_path=tmp_path / "campaign-strip-runtime.db",
    )
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    orchestrator._active_dispatches[task.id] = dispatch
    project = AsyncMock()
    monkeypatch.setattr(orchestrator_execution, "record_terminal_projection", project)

    with pytest.raises(
        RuntimeError,
        match="execution failure retained indeterminate custody",
    ):
        await orchestrator._execute_campaign_task(
            runner,
            task,
            dispatch,
            campaign_effect_fence=fence,
            campaign_effect_ready=ready,
            campaign_principal=agent.id,
            campaign_reservation_token=token,
        )

    fence.assert_awaited_once()
    ready.assert_called_once()
    project.assert_awaited_once()
    assert project.await_args.kwargs["status"] == "failed"
    assert project.await_args.kwargs["action"] == "receipt"
    assert task.metadata.get("retry_count", 0) == 0
    assert task.status is TaskStatus.RUNNING
    assert agent.status is AgentStatus.BUSY and agent.current_task == task.id
    assert pool._reservation_tokens[agent.id] == (task.id, token)
    assert orchestrator._active_dispatches[task.id] is dispatch
    assert orchestrator._campaign_recovery_owners[id(token)] == [
        dispatch,
        token,
        None,
        False,
    ]


@pytest.mark.asyncio
async def test_route_next(agents, tasks):
    board = MockTaskBoard()
    board.tasks = tasks
    pool = MockAgentPool(agents)
    orch = Orchestrator(task_board=board, agent_pool=pool)
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

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
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

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
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

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
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

    dispatches = await orch.route_next()

    assert len(dispatches) == 1
    assert dispatches[0].agent_id == "a-cyber-codex"


@pytest.mark.asyncio
async def test_fan_in(agents):
    pool = MockAgentPool(agents)
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t1",
            title="First fan-in branch",
            status=TaskStatus.COMPLETED,
            result="result from agent 1",
        ),
        Task(
            id="t2",
            title="Second fan-in branch",
            status=TaskStatus.COMPLETED,
            result="result from agent 2",
        ),
    ]
    orch = Orchestrator(task_board=board, agent_pool=pool)
    dispatches = [
        TaskDispatch(task_id="t1", agent_id="a1"),
        TaskDispatch(task_id="t2", agent_id="a2"),
    ]
    for dispatch in dispatches:
        background = asyncio.create_task(asyncio.sleep(0))
        await background
        orch._running_tasks[dispatch.task_id] = background
        orch._running_dispatch_owners[dispatch.task_id] = (background, dispatch)

    combined = await orch.fan_in(dispatches)

    assert "result from agent 1" in combined
    assert "result from agent 2" in combined


@pytest.mark.asyncio
async def test_fan_in_real_pool_none_result_never_releases_live_runner() -> None:
    config = AgentConfig(
        id="fan-in-live-agent",
        name="fan-in-live-seat",
        role=AgentRole.GENERAL,
        provider=ProviderType.OLLAMA,
        model="fixture-model",
    )
    runner = AgentRunner(config, advanced_memory=AsyncMock())
    await runner.start()
    pool = AgentPool()
    pool._agents[config.id] = runner
    task = Task(id="fan-in-live-task", title="Live fan-in branch")
    board = MockTaskBoard()
    board.tasks = [task]
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    dispatch = TaskDispatch(task_id=task.id, agent_id=config.id)
    assert await pool.reserve(
        config.id, task.id, reservation_token=dispatch
    ) is True
    orchestrator._active_dispatches[task.id] = dispatch
    execution_entered = asyncio.Event()
    finish_execution = asyncio.Event()

    async def exact_background_execution() -> None:
        execution_entered.set()
        await finish_execution.wait()
        task.status = TaskStatus.COMPLETED
        task.result = "terminal fan-in result"
        assert await pool.release_reservation(
            config.id,
            task.id,
            reservation_token=dispatch,
        ) is True
        orchestrator._active_dispatches.pop(task.id, None)

    background = asyncio.create_task(exact_background_execution())
    orchestrator._running_tasks[task.id] = background
    orchestrator._running_dispatch_owners[task.id] = (background, dispatch)
    await asyncio.wait_for(execution_entered.wait(), timeout=2)

    fan_in = asyncio.create_task(orchestrator.fan_in([dispatch]))
    await asyncio.sleep(0)

    assert await pool.get_result(config.id) is None
    assert fan_in.done() is False
    assert runner.state.status is AgentStatus.BUSY
    assert runner.state.current_task == task.id
    assert await pool.reserve(
        config.id,
        "illicit-second-task",
        reservation_token=TaskDispatch(
            task_id="illicit-second-task",
            agent_id=config.id,
        ),
    ) is False

    finish_execution.set()
    assert await asyncio.wait_for(fan_in, timeout=2) == "terminal fan-in result"
    assert runner.state.status is AgentStatus.IDLE
    assert runner.state.current_task is None


@pytest.mark.asyncio
async def test_fan_in_rejects_entire_mixed_campaign_batch_before_release(agents):
    campaign = Task(
        id="campaign-fan-in",
        title="Campaign fan-in denial",
        metadata=_campaign_metadata(agents[1].id, task_id="campaign-fan-in"),
    )
    generic = Task(id="generic-fan-in", title="Generic fan-in fixture")
    board = MockTaskBoard()
    board.tasks = [generic, campaign]
    pool = MockAgentPool(agents)
    pool.get_result = AsyncMock(return_value="must not read")  # type: ignore[method-assign]
    pool.release = AsyncMock()  # type: ignore[method-assign]
    orchestrator = Orchestrator(task_board=board, agent_pool=pool)
    dispatches = [
        TaskDispatch(task_id=generic.id, agent_id=agents[0].id),
        TaskDispatch(task_id=campaign.id, agent_id=agents[1].id),
    ]

    with pytest.raises(RuntimeError, match="owner-token completion"):
        await orchestrator.fan_in(dispatches)

    pool.get_result.assert_not_awaited()  # type: ignore[attr-defined]
    pool.release.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_tick(agents, tasks):
    board = MockTaskBoard()
    board.tasks = tasks
    pool = MockAgentPool(agents)
    orch = Orchestrator(task_board=board, agent_pool=pool)

    async def accept(td):
        pool._assignments.append((td.agent_id, td.task_id))
        return True

    orch._assign_dispatch = accept  # type: ignore[method-assign]

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
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A false runtime control must not enter the native constructor."""
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


async def _build_outbox_orchestrator(
    tmp_path: Path,
    monkeypatch,
    *,
    result: str = "outbox completion",
    error: Exception | None = None,
    max_retries: int = 0,
):
    from dharma_swarm.task_board import TaskBoard

    runtime_path = tmp_path / "runtime.db"
    board = TaskBoard(tmp_path / "tasks.db")
    await board.init_db()
    task = await board.create(
        "Runtime-first outbox fixture",
        metadata={"max_retries": max_retries, "retry_count": 0},
    )
    agent = AgentState(
        id="outbox-agent",
        name="outbox-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    retry_agent = AgentState(
        id="outbox-retry-agent",
        name="outbox-retry-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    runner = DummyRunner(result=result, error=error)
    pool = MockAgentPool([agent, retry_agent])
    pool.set_runner(agent.id, runner)
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=runtime_path,
        shared_dir=tmp_path / "shared",
        stigmergy_dir=tmp_path / "stigmergy",
    )
    await orchestrator._runtime_lifecycle._runtime_state_store().init_db()
    orchestrator._telic_seam = None
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    sidecar = MagicMock()
    sidecar.consolidate_knowledge = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "dharma_swarm.sleep_time_agent.SleepTimeAgent",
        MagicMock(return_value=sidecar),
    )
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")
    monkeypatch.delenv("DHARMA_SPINE_DISPATCH", raising=False)
    return orchestrator, board, pool, task, agent, runner


@pytest.mark.asyncio
async def test_swallowed_board_completion_replays_from_runtime_outbox(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm.graph import reconcile_board
    from dharma_swarm.graph.reconciler import ReconcileReport

    orchestrator, board, pool, task, agent, _runner = (
        await _build_outbox_orchestrator(tmp_path, monkeypatch)
    )
    real_settle = reconcile_board.settle_task_board
    swallowed = AsyncMock(return_value=None)
    monkeypatch.setattr(reconcile_board, "settle_task_board", swallowed)

    dispatches = await orchestrator.dispatch(task, TopologyType.PIPELINE)
    dispatch = dispatches[0]
    with pytest.raises(
        RuntimeError,
        match="completion projection is not durable on Board",
    ):
        await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=5)

    pending = await board.get(task.id)
    assert pending is not None and pending.status is TaskStatus.RUNNING
    assert agent.status is AgentStatus.BUSY and agent.current_task == task.id
    assert pool._reservation_tokens[agent.id] == (task.id, dispatch)
    assert orchestrator._active_dispatches[task.id] is dispatch
    assert orchestrator._generic_recovery_owners[id(dispatch)] == [
        dispatch,
        "terminal projection or release raised before proof",
    ]
    run_id = dispatch.metadata["execution_identity"]["run_id"]
    store = orchestrator._runtime_lifecycle._runtime_state_store()
    run = await store.get_delegation_run(run_id)
    intent = run.metadata["task_board_projection_intent"]
    assert (run.status, intent["action"], intent["result"]) == (
        "completed", "receipt", "outbox completion"
    )
    swallowed.assert_awaited_once()

    report = ReconcileReport()
    await real_settle(
        runtime_state=store,
        task_board=board,
        report=report,
        now=datetime.now(timezone.utc),
        logger=MagicMock(),
        run_id=run_id,
    )
    replayed = await board.get(task.id)
    assert report.errors == []
    assert replayed is not None and replayed.status is TaskStatus.COMPLETED
    assert replayed.result == "outbox completion"
    assert replayed.metadata["graph_reconcile_projection"]["run_id"] == run_id


@pytest.mark.asyncio
async def test_swallowed_failure_projection_replays_exact_intent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm.graph import reconcile_board
    from dharma_swarm.graph.reconciler import ReconcileReport

    error = RuntimeError("provider exploded exactly")
    orchestrator, board, pool, task, agent, _runner = (
        await _build_outbox_orchestrator(
            tmp_path,
            monkeypatch,
            error=error,
        )
    )
    real_settle = reconcile_board.settle_task_board
    monkeypatch.setattr(reconcile_board, "settle_task_board", AsyncMock())

    dispatch = (await orchestrator.dispatch(task, TopologyType.PIPELINE))[0]
    with pytest.raises(
        RuntimeError,
        match="execution failure retained indeterminate custody",
    ):
        await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=5)

    run_id = dispatch.metadata["execution_identity"]["run_id"]
    store = orchestrator._runtime_lifecycle._runtime_state_store()
    run = await store.get_delegation_run(run_id)
    intent = run.metadata["task_board_projection_intent"]
    assert run.metadata["error"] == "provider exploded exactly"
    assert (intent["action"], intent["result"]) == (
        "receipt", "provider exploded exactly"
    )
    assert dispatch.metadata["evidence_receipt_status"] == "failed"
    assert dispatch.metadata["evidence_receipt_error_source"] == "internal_error"
    assert dispatch.metadata["evidence_receipt_error_detail"] == intent["result"]
    assert (await board.get(task.id)).status is TaskStatus.RUNNING
    assert agent.status is AgentStatus.BUSY and agent.current_task == task.id
    assert pool._reservation_tokens[agent.id] == (task.id, dispatch)
    assert orchestrator._active_dispatches[task.id] is dispatch
    assert orchestrator._generic_recovery_owners[id(dispatch)] == [
        dispatch,
        "execution_error projection is indeterminate",
    ]

    report = ReconcileReport()
    await real_settle(
        runtime_state=store,
        task_board=board,
        report=report,
        now=datetime.now(timezone.utc),
        logger=MagicMock(),
        run_id=run_id,
    )
    replayed = await board.get(task.id)
    assert report.errors == []
    assert replayed is not None and replayed.status is TaskStatus.FAILED
    assert replayed.result == "provider exploded exactly"


@pytest.mark.asyncio
async def test_honors_rejection_is_durable_before_release_crash_and_replay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from dharma_swarm.graph.durable_invoker import claim_idempotency_key
    from dharma_swarm.graph.reconciler import GraphReconciler

    orchestrator, board, _pool, task, agent, runner = (
        await _build_outbox_orchestrator(tmp_path, monkeypatch)
    )
    task.metadata["completion_contract"] = {
        "mode": "honors",
        "minimum_file_references": 1,
    }
    dispatch = TaskDispatch(task_id=task.id, agent_id=agent.id)
    identity = orchestrator._runtime_lifecycle.ensure_execution_identity(
        dispatch, task=task
    )
    await board.update_task(
        task.id,
        status=TaskStatus.ASSIGNED,
        assigned_to=agent.id,
        metadata=task.metadata,
    )
    await board.update_task(task.id, status=TaskStatus.RUNNING, metadata=task.metadata)
    task = await board.get(task.id)
    assert task is not None
    await orchestrator._runtime_lifecycle.record_task_claim(
        dispatch, task=task, status="running", require_identity=True
    )
    await orchestrator._runtime_lifecycle.record_delegation_run(
        dispatch, task=task, status="running", require_identity=True
    )

    with pytest.raises(RuntimeError, match="Honors checkpoint"):
        await orchestrator._run_task_via_spine(runner, task, dispatch, 2)

    run_id = identity.run_id
    store = orchestrator._runtime_lifecycle._runtime_state_store()
    run = await store.get_delegation_run(run_id)
    side_effect_key = f"invoke_agent:{task.id}:{dispatch.agent_id}"
    idempotency = await store.get_idempotency_record(
        claim_idempotency_key(side_effect_key), side_effect_key
    )
    assert dispatch.metadata["evidence_receipt_status"] == "failed"
    assert dispatch.metadata["evidence_receipt_error_source"] == "guardrail_blocked"
    assert idempotency is not None and idempotency.status == "failed"
    assert run is not None and run.status == "running"
    assert (await board.get(task.id)).status is TaskStatus.RUNNING

    replay_board = MockTaskBoard()
    replay_board.tasks = [task.model_copy(deep=True)]
    report = await GraphReconciler(store, task_board=replay_board).reconcile()
    replayed = await replay_board.get(task.id)
    assert report.errors == []
    assert replayed is not None and replayed.status is TaskStatus.FAILED
    assert replayed.status is not TaskStatus.COMPLETED
    recovered_run = await store.get_delegation_run(run_id)
    assert recovered_run is not None and recovered_run.status == "failed"
    await orchestrator._collect_completed()


@pytest.mark.asyncio
async def test_chained_retry_history_closes_older_pending_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    orchestrator, board, pool, task, agent, _runner = (
        await _build_outbox_orchestrator(
            tmp_path,
            monkeypatch,
            error=RuntimeError("first attempt failed"),
            max_retries=1,
        )
    )
    first = (await orchestrator.dispatch(task, TopologyType.PIPELINE))[0]
    await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=5)
    retry = await board.get(task.id)
    assert retry is not None and retry.status is TaskStatus.PENDING
    first_identity = first.metadata["execution_identity"]

    pool.set_runner(
        "outbox-retry-agent",
        DummyRunner(result="second attempt completed"),
    )
    second = (await orchestrator.dispatch(retry, TopologyType.PIPELINE))[0]
    await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=5)
    completed = await board.get(task.id)
    assert completed is not None and completed.status is TaskStatus.COMPLETED
    second_identity = second.metadata["execution_identity"]
    assert (first.agent_id, second.agent_id) == (
        agent.id,
        "outbox-retry-agent",
    )
    for field in ("run_id", "claim_id", "idempotency_key"):
        assert first_identity[field] != second_identity[field]
    assert second_identity["parent_run_id"] == first_identity["run_id"]
    history = completed.metadata["graph_reconcile_projection_history"]
    assert set(history) == {
        first_identity["run_id"],
        second_identity["run_id"],
    }
    assert history[first_identity["run_id"]]["action"] == "retry"
    assert history[second_identity["run_id"]]["action"] == "receipt"


@pytest.mark.asyncio
async def test_generic_completion_still_schedules_sleep_time_sidecar(
    monkeypatch,
    tmp_path: Path,
) -> None:
    agent = AgentState(
        id="generic-agent",
        name="generic-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    task = Task(
        id="generic-sidecar-task",
        title="Generic sidecar fixture",
        description="Write results to ~/generic-legacy-output.md",
        metadata={"allow_free_text_result_path": True},
    )
    board = MockTaskBoard()
    board.tasks = [task]
    pool = MockAgentPool([agent])
    pool.set_runner(agent.id, DummyRunner(result="generic completion " * 20))
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledger",
    )
    orchestrator._telic_seam = None
    orchestrator._attach_context_bundle = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda task, td, metadata: metadata
    )
    orchestrator._runtime_lifecycle.ensure_execution_identity = MagicMock(
        side_effect=_ensure_fixture_execution_identity
    )
    orchestrator._runtime_lifecycle.record_task_claim = AsyncMock()
    orchestrator._runtime_lifecycle.record_delegation_run = AsyncMock()
    orchestrator._emit_lifecycle_event = AsyncMock()  # type: ignore[method-assign]
    orchestrator._emit_completion_trace = AsyncMock()  # type: ignore[method-assign]
    orchestrator._persist_result = AsyncMock()  # type: ignore[method-assign]
    orchestrator._spine_dispatch_enabled = lambda: False  # type: ignore[method-assign]
    sidecar = MagicMock()
    sidecar.consolidate_knowledge = AsyncMock(return_value=[])
    sidecar_constructor = MagicMock(return_value=sidecar)
    monkeypatch.setattr(
        "dharma_swarm.sleep_time_agent.SleepTimeAgent",
        sidecar_constructor,
    )
    original_expanduser = Path.expanduser

    def fixture_expanduser(path: Path) -> Path:
        if str(path) == "~/generic-legacy-output.md":
            return tmp_path / "generic-legacy-output.md"
        return original_expanduser(path)

    monkeypatch.setattr(Path, "expanduser", fixture_expanduser)

    dispatches = await orchestrator.dispatch(task, TopologyType.PIPELINE)
    await asyncio.wait_for(orchestrator._running_tasks[task.id], timeout=5)
    await asyncio.sleep(0)

    assert [dispatch.agent_id for dispatch in dispatches] == [agent.id]
    sidecar_constructor.assert_called_once_with()
    sidecar.consolidate_knowledge.assert_awaited_once()
    assert (tmp_path / "generic-legacy-output.md").is_file()


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
    attempts=600,
    delay_seconds=0.05,
):
    """Poll until *expected_event* lands in the task ledger.

    The budget must be much larger than the work it waits for, not equal to
    it. The old 100 x 0.01s (1s nominal) sat right on top of the real
    latency: an instrumented run reached `result_persisted` at iteration 71
    of 100, so any runner a little slower than this box ran out of
    iterations and the test failed with `progress_events: ['task_started']`
    — a flake on a REQUIRED check (`pytest (3.11)`), reproduced 4 times in
    6 local runs. 600 x 0.05s (30s nominal) has real headroom; the loop
    still returns the instant the event appears, so a healthy run costs
    nothing, and a genuinely stuck task still exits early on any terminal
    progress event.
    """
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
    pool.set_runner("a1", DummyRunner(result="pipeline result"))
    board = MockTaskBoard()
    board.tasks = tasks
    orch = Orchestrator(task_board=board, agent_pool=pool)

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
    """fan_in should collect only successful terminal Board results."""
    pool = MockAgentPool(agents)
    board = MockTaskBoard()
    board.tasks = [
        Task(
            id="t1",
            title="Successful branch",
            status=TaskStatus.COMPLETED,
            result="good result",
        ),
        Task(
            id="t2",
            title="Failed branch",
            status=TaskStatus.FAILED,
            result="failure detail",
        ),
    ]
    orch = Orchestrator(task_board=board, agent_pool=pool)
    dispatches = [
        TaskDispatch(task_id="t1", agent_id="a1"),
        TaskDispatch(task_id="t2", agent_id="a2"),
    ]
    for dispatch in dispatches:
        background = asyncio.create_task(asyncio.sleep(0))
        await background
        orch._running_tasks[dispatch.task_id] = background
        orch._running_dispatch_owners[dispatch.task_id] = (background, dispatch)

    combined = await orch.fan_in(dispatches)

    assert "good result" in combined
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
    board.tasks = [tasks[0]]
    bus = MockMessageBus()
    orch = Orchestrator(task_board=board, agent_pool=pool, message_bus=bus)
    orch._handle_task_failure = AsyncMock()  # type: ignore[method-assign]

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
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

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
async def test_orchestrator_failure_runtime_precedes_progress_projection(
    tmp_path,
    monkeypatch,
):
    """Failure progress is emitted only after durable runtime terminalization."""
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
        await asyncio.wait_for(runtime_write_started.wait(), timeout=2)
        rows = (
            [json.loads(line) for line in progress_path.read_text().splitlines()]
            if progress_path.exists()
            else []
        )
        assert not any(
            row.get("event") in {"task_failed", "task_retry_scheduled"}
            for row in rows
        )
        assert orch._running_tasks
        runtime_block.set()
        await _drain_running_tasks(orch)
        rows = [json.loads(line) for line in progress_path.read_text().splitlines()]
        assert any(
            row.get("event") in {"task_failed", "task_retry_scheduled"}
            for row in rows
        )
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
    assert not failed_seen
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
    assert task.metadata["last_failure_class"] == "internal_error"
    assert task.metadata["last_failure_diagnostic_class"] == "connection_transient"
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
    assert task.metadata["last_failure_class"] == "timeout"
    assert task.metadata["last_failure_diagnostic_class"] == "long_timeout"
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
    orch._assign_dispatch = AsyncMock(return_value=True)  # type: ignore[method-assign]

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
    dispatch = TaskDispatch(
        task_id="t-straggler",
        agent_id="a1",
        metadata={"claim_id": "claim-straggler"},
    )
    _ensure_fixture_execution_identity(dispatch, task=board.tasks[0], require=True)
    assert await pool.reserve(
        "a1",
        "t-straggler",
        reservation_token=dispatch,
    )

    async def never_finishes():
        await asyncio.sleep(3600)

    running = asyncio.create_task(never_finishes())
    orch._running_tasks["t-straggler"] = running
    orch._running_dispatch_owners["t-straggler"] = (running, dispatch)
    orch._active_dispatches["t-straggler"] = dispatch

    settled, recovered = await orch._collect_completed_with_barrier()

    assert settled == 0
    assert recovered == 1
    assert running.cancelled()
    assert "t-straggler" not in orch._running_tasks
    assert "t-straggler" not in orch._active_dispatches
    assert pool.released == []
    assert "a1" not in pool._reservation_tokens
    assert pool._agents[0].status is AgentStatus.IDLE
    assert any(
        task_id == "t-straggler"
        and fields.get("status") == TaskStatus.PENDING
        and "active_claim" not in fields.get("metadata", {})
        and fields.get("metadata", {}).get("last_failure_source") == "bsp_barrier_timeout"
        for task_id, fields in board.updates
    )


@pytest.mark.asyncio
async def test_bsp_barrier_retains_cancellation_resistant_exact_owner() -> None:
    from dharma_swarm.orchestrator_bsp import _settle_cancelled_straggler

    agent = AgentState(
        id="bsp-live-agent",
        name="bsp-live-seat",
        role=AgentRole.GENERAL,
        status=AgentStatus.IDLE,
    )
    pool = MockAgentPool([agent])
    orchestrator = Orchestrator(agent_pool=pool)
    dispatch = TaskDispatch(task_id="bsp-live-task", agent_id=agent.id)
    assert await pool.reserve(
        agent.id,
        dispatch.task_id,
        reservation_token=dispatch,
    )
    cancellation_seen = asyncio.Event()
    release_work = asyncio.Event()

    async def stubborn_work():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellation_seen.set()
            await release_work.wait()

    running = asyncio.create_task(stubborn_work())
    orchestrator._running_tasks[dispatch.task_id] = running
    orchestrator._running_dispatch_owners[dispatch.task_id] = (
        running,
        dispatch,
    )
    orchestrator._active_dispatches[dispatch.task_id] = dispatch
    orchestrator._handle_task_failure = AsyncMock()  # type: ignore[method-assign]
    await asyncio.sleep(0)
    running.cancel()
    await cancellation_seen.wait()

    try:
        recovered = await _settle_cancelled_straggler(
            orchestrator,
            dispatch.task_id,
            running,
            0.0,
        )

        assert recovered == 0
        assert orchestrator._running_tasks[dispatch.task_id] is running
        assert orchestrator._active_dispatches[dispatch.task_id] is dispatch
        assert pool._reservation_tokens[agent.id] == (dispatch.task_id, dispatch)
        orchestrator._handle_task_failure.assert_not_awaited()  # type: ignore[attr-defined]
    finally:
        release_work.set()
        await running
        assert await pool.release_reservation(
            agent.id,
            dispatch.task_id,
            reservation_token=dispatch,
        )
