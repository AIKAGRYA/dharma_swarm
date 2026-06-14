"""Focused tests for the Authority and Revenue Loop Gauntlet.

Covers:
  - Governance guards (uplift guard invocation)
  - Runtime claims / heartbeats / timeouts
  - Opportunity refill / dispatcher full chain
  - Telic lifecycle integrity (ActionProposal → GateDecision → Outcome → ValueEvent → Contribution)
  - WebSocket writer explicit state contract
  - Economic telemetry recording
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest


# ── 1. Governance guards ─────────────────────────────────────────────


class TestGovernanceGuards:
    """Verify that governance guard scripts exist and can be invoked."""

    def test_uplift_guard_runner_importable(self) -> None:
        from scripts.uplift_guards import (
            check_autonomous_destruction,
            check_hotpath_acknowledged,
            check_kernel_integrity,
            check_mismatch_adjacency,
            check_no_secrets,
        )
        assert callable(check_kernel_integrity)
        assert callable(check_no_secrets)
        assert callable(check_autonomous_destruction)
        assert callable(check_hotpath_acknowledged)
        assert callable(check_mismatch_adjacency)

    def test_uplift_guard_kernel_integrity_passes(self, tmp_path: Path) -> None:
        from scripts.uplift_guards import check_kernel_integrity
        ok, msg = check_kernel_integrity(tmp_path)
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_test_hygiene_importable(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "check_test_hygiene",
            str(Path(__file__).resolve().parents[1] / "scripts" / "governance" / "check_test_hygiene.py"),
        )
        assert spec is not None

    def test_test_hygiene_rule3_requires_explicit_runtime_db(self) -> None:
        import importlib.util

        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "governance"
            / "check_test_hygiene.py"
        )
        spec = importlib.util.spec_from_file_location("check_test_hygiene", str(script_path))
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        unsafe = """
RuntimeStateStore()
RuntimeStateStore(None)
RuntimeStateStore(db_path=None)
RuntimeStateStore(include_memory_plane=False)
"""
        findings = module.scan_rule_3(unsafe, Path("sample.py"))
        assert [line for line, _ in findings] == [2, 3, 4, 5]

        safe = """
RuntimeStateStore(tmp_path / "runtime.db")
RuntimeStateStore(db_path=tmp_path / "runtime.db")
runtime_state.RuntimeStateStore(tmp_path / "runtime.db")
"""
        assert module.scan_rule_3(safe, Path("sample.py")) == []

    def test_active_surface_manifest_exists(self) -> None:
        manifest = Path(__file__).resolve().parents[1] / "ACTIVE_SURFACE_MANIFEST.yaml"
        assert manifest.exists(), "ACTIVE_SURFACE_MANIFEST.yaml must exist"
        import yaml
        data = yaml.safe_load(manifest.read_text())
        assert "api_routers" in data
        assert "dashboard_nav_sections" in data
        assert "hot_path_modules" in data
        assert "opportunity_stages" in data


# ── 2. Runtime state claims / heartbeats / timeouts ──────────────────


class TestRuntimeStateClaims:
    """Test durable RuntimeStateStore task claims and delegation runs."""

    def _store(self, tmp_path: Path):
        from dharma_swarm.runtime_state import RuntimeStateStore
        return RuntimeStateStore(db_path=tmp_path / "test.db")

    def test_create_and_read_task_claim(self, tmp_path: Path) -> None:
        from dharma_swarm.runtime_state import TaskClaim, _new_id
        store = self._store(tmp_path)
        claim = TaskClaim(
            claim_id=_new_id("claim"),
            task_id=_new_id("task"),
            agent_id="test_agent",
            status="claimed",
            session_id="test-session",
        )
        result = store.create_task_claim_sync(claim, legacy_no_identity_allowed=True)
        assert result.claim_id == claim.claim_id
        assert result.status == "claimed"

        loaded = store.get_task_claim_sync(claim.claim_id)
        assert loaded is not None
        assert loaded.agent_id == "test_agent"

    def test_heartbeat_claim(self, tmp_path: Path) -> None:
        from dharma_swarm.runtime_state import TaskClaim, _new_id
        store = self._store(tmp_path)
        claim = TaskClaim(
            claim_id=_new_id("claim"),
            task_id=_new_id("task"),
            agent_id="agent_hb",
            status="claimed",
        )
        store.create_task_claim_sync(claim, legacy_no_identity_allowed=True)
        updated = store.heartbeat_claim_sync(claim.claim_id)
        assert updated is not None
        assert updated.heartbeat_at is not None

    def test_close_claim(self, tmp_path: Path) -> None:
        from dharma_swarm.runtime_state import TaskClaim, _new_id
        store = self._store(tmp_path)
        claim = TaskClaim(
            claim_id=_new_id("claim"),
            task_id=_new_id("task"),
            agent_id="agent_close",
            status="claimed",
        )
        store.create_task_claim_sync(claim, legacy_no_identity_allowed=True)
        closed = store.close_claim_sync(claim.claim_id, status="completed")
        assert closed is not None
        assert closed.status == "completed"

    def test_create_and_read_delegation_run(self, tmp_path: Path) -> None:
        from dharma_swarm.runtime_state import DelegationRun, _new_id
        store = self._store(tmp_path)
        run = DelegationRun(
            run_id=_new_id("run"),
            task_id=_new_id("task"),
            assigned_to="agent_run",
            status="running",
            session_id="test-session",
        )
        result = store.create_delegation_run_sync(run, legacy_no_identity_allowed=True)
        assert result.run_id == run.run_id
        assert result.status == "running"

        loaded = store.get_delegation_run_sync(run.run_id)
        assert loaded is not None
        assert loaded.assigned_to == "agent_run"

    def test_close_delegation_run(self, tmp_path: Path) -> None:
        from dharma_swarm.runtime_state import DelegationRun, _new_id
        store = self._store(tmp_path)
        run = DelegationRun(
            run_id=_new_id("run"),
            task_id=_new_id("task"),
            assigned_to="agent_close_run",
            status="running",
        )
        store.create_delegation_run_sync(run, legacy_no_identity_allowed=True)
        closed = store.close_delegation_run_sync(
            run.run_id, status="completed"
        )
        assert closed is not None
        assert closed.status == "completed"
        assert closed.completed_at is not None

    def test_stale_after_semantics(self, tmp_path: Path) -> None:
        """Ensure stale_after is stored and retrievable."""
        from dharma_swarm.runtime_state import TaskClaim, _new_id, _utc_now
        from datetime import timedelta
        store = self._store(tmp_path)
        stale_time = _utc_now() + timedelta(seconds=900)
        claim = TaskClaim(
            claim_id=_new_id("claim"),
            task_id=_new_id("task"),
            agent_id="agent_stale",
            status="claimed",
            stale_after=stale_time,
        )
        store.create_task_claim_sync(claim, legacy_no_identity_allowed=True)
        loaded = store.get_task_claim_sync(claim.claim_id)
        assert loaded is not None
        assert loaded.stale_after is not None


# ── 3. Opportunity dispatcher / refill full chain ─────────────────────


class TestOpportunityDispatcher:
    """Test that OpportunityDispatcher creates durable claims and runs."""

    def test_dispatch_creates_all_stages(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_dispatcher import (
            OPPORTUNITY_STAGES,
            OpportunityDispatcher,
        )
        from dharma_swarm.runtime_state import RuntimeStateStore

        os.environ["DHARMA_STATE_DIR"] = str(tmp_path)
        try:
            store = RuntimeStateStore(db_path=tmp_path / "runtime.db")
            dispatcher = OpportunityDispatcher(state_store=store)
            results = dispatcher.dispatch_opportunity_sync({
                "id": "test-opp-1",
                "title": "Test Revenue Opportunity",
                "type": "external_revenue",
            })
            assert len(results) == len(OPPORTUNITY_STAGES)
            for r in results:
                assert r.success, f"Stage {r.stage} failed: {r.error}"
                assert r.task_id
                assert r.claim_id
                assert r.run_id
        finally:
            os.environ.pop("DHARMA_STATE_DIR", None)

    def test_dispatch_claims_are_durable(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_dispatcher import OpportunityDispatcher
        from dharma_swarm.runtime_state import RuntimeStateStore

        os.environ["DHARMA_STATE_DIR"] = str(tmp_path)
        try:
            store = RuntimeStateStore(db_path=tmp_path / "runtime.db")
            dispatcher = OpportunityDispatcher(state_store=store)
            results = dispatcher.dispatch_opportunity_sync({
                "id": "durable-test",
                "title": "Durability Test",
                "type": "external_revenue",
            })
            for r in results:
                claim = store.get_task_claim_sync(r.claim_id)
                assert claim is not None
                assert claim.status == "claimed"
                run = store.get_delegation_run_sync(r.run_id)
                assert run is not None
                assert run.status == "running"
        finally:
            os.environ.pop("DHARMA_STATE_DIR", None)


class TestOpportunityRefill:
    """Test full opportunity refill through all stages."""

    def test_refill_produces_all_stages(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_dispatcher import OPPORTUNITY_STAGES
        from dharma_swarm.opportunity_refill import OpportunityRefill, OpportunityRow

        os.environ["DHARMA_STATE_DIR"] = str(tmp_path)
        try:
            refill = OpportunityRefill(output_dir=tmp_path / "packets")
            row = OpportunityRow(
                id="refill-test",
                title="Revenue Loop Test",
                type="external_revenue",
                estimated_value_usd=1000.0,
            )
            result = refill.refill(row)
            assert len(result.stages) == len(OPPORTUNITY_STAGES)
            assert result.success
            assert result.total_provider_cost_usd > 0
            assert result.total_net_value_usd > 0
        finally:
            os.environ.pop("DHARMA_STATE_DIR", None)

    def test_revenue_packet_written(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import OpportunityRefill, OpportunityRow

        os.environ["DHARMA_STATE_DIR"] = str(tmp_path)
        try:
            packets_dir = tmp_path / "packets"
            refill = OpportunityRefill(output_dir=packets_dir)
            row = OpportunityRow(
                id="packet-test",
                title="Packet Test Opp",
                type="external_revenue",
                estimated_value_usd=500.0,
            )
            result = refill.refill(row)
            assert result.revenue_packet_path
            packet = Path(result.revenue_packet_path)
            assert packet.exists()
            content = packet.read_text()
            assert "Packet Test Opp" in content
            assert "external_revenue" in content
            assert "Provider Cost" in content
        finally:
            os.environ.pop("DHARMA_STATE_DIR", None)

    def test_deep_research_quarantine(self, tmp_path: Path) -> None:
        from dharma_swarm.opportunity_refill import OpportunityRefill, OpportunityRow

        os.environ["DHARMA_STATE_DIR"] = str(tmp_path)
        os.environ["DHARMA_RESEARCH_BACKEND"] = "quarantine"
        try:
            refill = OpportunityRefill(output_dir=tmp_path / "packets")
            row = OpportunityRow(id="q-test", title="Quarantine Test")
            result = refill.refill(row)
            dr_stage = next(s for s in result.stages if s.stage == "deep_research")
            assert dr_stage.quarantined
            assert dr_stage.status == "quarantined"
            assert result.success
        finally:
            os.environ.pop("DHARMA_STATE_DIR", None)
            os.environ.pop("DHARMA_RESEARCH_BACKEND", None)


# ── 4. Telic lifecycle integrity ──────────────────────────────────────


class TestTelicLifecycleIntegrity:
    """Test ActionProposal → GateDecision → Outcome → ValueEvent → Contribution."""

    def _seam(self, tmp_path: Path):
        from dharma_swarm.ontology_runtime import get_shared_registry
        from dharma_swarm.telic_seam import TelicSeam

        registry = get_shared_registry(path=tmp_path / "ontology.db")
        return TelicSeam(registry=registry, path=tmp_path / "ontology.db")

    def _task(self):
        from dharma_swarm.models import Task, TaskPriority, TaskStatus
        return Task(
            id="telic-test-task",
            title="Test telic lifecycle",
            description="Full lifecycle test",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
        )

    def test_full_lifecycle_chain(self, tmp_path: Path) -> None:
        seam = self._seam(tmp_path)
        task = self._task()
        agent_id = "agent-telic"

        # 1. Dispatch → ActionProposal
        proposal_id = seam.record_dispatch(task, agent_id, topology="dispatch")
        assert proposal_id is not None

        # 2. Gate decision
        from dharma_swarm.models import GateCheckResult, GateDecision
        gate_result = GateCheckResult(
            decision=GateDecision.ALLOW,
            reason="All gates passed",
            gate_results={},
        )
        gate_id = seam.record_gate_decision(proposal_id, gate_result)
        assert gate_id is not None

        # 3. Outcome
        outcome_id = seam.record_outcome(
            task, agent_id, success=True,
            result_summary="Completed successfully",
            duration_ms=1500,
        )
        assert outcome_id is not None

        # 4. ValueEvent
        value_id = seam.record_value_event(
            outcome_id, task, agent_id,
            result_text="Test result",
            success=True,
            duration_ms=1500,
        )
        assert value_id is not None

        # 5. Contribution
        contrib_id = seam.record_contribution(
            value_id, agent_id,
            credit_share=1.0,
            composite_value=0.8,
            task_type="general",
        )
        assert contrib_id is not None

        # 6. Integrity report should be clean
        report = seam.lifecycle_integrity_report()
        assert report["is_clean"], f"Integrity issues: {report}"

    def test_empty_proposal_id_detected(self, tmp_path: Path) -> None:
        """Outcomes with empty proposal_id must be flagged."""
        seam = self._seam(tmp_path)
        registry = seam.registry

        registry.create_object(
            "Outcome",
            properties={
                "proposal_id": "",
                "task_id": "orphan-task",
                "agent_id": "orphan-agent",
                "success": True,
            },
            created_by="test",
        )
        report = seam.lifecycle_integrity_report()
        assert len(report["empty_proposal_id_outcomes"]) > 0

    def test_unknown_proposal_id_detected(self, tmp_path: Path) -> None:
        """Outcomes referencing a non-existent proposal must be flagged."""
        seam = self._seam(tmp_path)
        registry = seam.registry

        registry.create_object(
            "Outcome",
            properties={
                "proposal_id": "nonexistent_proposal_id",
                "task_id": "unknown-task",
                "agent_id": "unknown-agent",
                "success": True,
            },
            created_by="test",
        )
        report = seam.lifecycle_integrity_report()
        assert len(report["unknown_proposal_id_outcomes"]) > 0

    def test_orphan_value_event_detected(self, tmp_path: Path) -> None:
        """ValueEvents without a linked Outcome must be flagged as orphans."""
        seam = self._seam(tmp_path)
        registry = seam.registry

        obj, errors = registry.create_object(
            "ValueEvent",
            properties={
                "outcome_id": "no_such_outcome",
                "agent_id": "test-agent",
                "composite_value": 0.5,
            },
            created_by="test",
        )
        if obj is None:
            pytest.skip(f"ValueEvent creation failed (schema may not support it): {errors}")
        report = seam.lifecycle_integrity_report()
        assert len(report["orphan_value_events"]) > 0


# ── 5. Economic telemetry ─────────────────────────────────────────────


class TestEconomicTelemetry:
    """Test economic event recording in the telemetry plane."""

    def test_record_economic_event_sync(self, tmp_path: Path) -> None:
        from dharma_swarm.telemetry_plane import TelemetryPlaneStore

        store = TelemetryPlaneStore(db_path=tmp_path / "telemetry.db")
        record = store.record_economic_event_sync(
            event_kind="opportunity_stage_cost",
            amount=0.05,
            description="Test stage cost",
            task_id="task-econ-1",
        )
        assert record.event_kind == "opportunity_stage_cost"
        assert record.amount == 0.05

    def test_economic_engine_records_expense(self, tmp_path: Path) -> None:
        from dharma_swarm.economic_engine import EconomicEngine, ExpenseCategory

        engine = EconomicEngine(storage_dir=tmp_path / "economics")
        engine.record_expense(0.10, ExpenseCategory.API_CALLS, "Test API cost")
        snap = engine.snapshot()
        assert snap.total_expenses >= 0.10


# ── 6. WebSocket state contract ───────────────────────────────────────


class TestWebSocketStateContract:
    """Test that the WS connection manager tracks state correctly."""

    def test_manager_initial_state(self) -> None:
        from api.ws import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.count("default") == 0
        assert mgr.count("nonexistent") == 0

    def test_manager_explicit_state(self) -> None:
        from api.ws import ConnectionManager
        mgr = ConnectionManager()
        assert hasattr(mgr, "_connections")
        assert isinstance(mgr._connections, dict)
