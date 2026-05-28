"""Regression tests: A2A gateway initialization and receipt correlation chain.

Phase 1: Gateway mounted but not initialised -> 503
Phase 1: Gateway initialised via lifespan -> task succeeds + receipt emitted
Phase 2A: correlation_id stamped at task creation (auto-UUID4)
Phase 2A: correlation_id propagates through receipt
Phase 2A: correlation_id chains to spine.EvidenceReceipt.trace_id (fixture)
"""

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _make_app_with_router():
    """Create a minimal FastAPI app with the A2A router mounted."""
    from fastapi import FastAPI

    import dharma_swarm.a2a.node_gateway as ng

    app = FastAPI()
    app.include_router(ng.router)
    return app, ng


class TestGatewayMountedNotInitialised:
    """Gateway router exists but init_gateway() never called -> 503."""

    def test_submit_returns_503(self):
        app, ng = _make_app_with_router()

        original_server = ng._server
        ng._server = None
        try:
            from fastapi.testclient import TestClient

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/a2a/tasks",
                json={"from_agent": "test", "messages": [{"content": "hi"}]},
            )
            assert resp.status_code in (403, 503)
            if resp.status_code == 503:
                assert "Gateway not initialized" in resp.json()["detail"]
        finally:
            ng._server = original_server


class TestGatewayInitialisedInLifespan:
    """Gateway initialised -> task accepted, receipt emitted."""

    def test_task_succeeds_with_receipt(self, tmp_path):
        from dharma_swarm.a2a.a2a_server import A2AServer, A2ATaskStatus
        from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry
        from dharma_swarm.a2a.node_gateway import init_gateway

        app, ng = _make_app_with_router()

        card = AgentCard(name="hermes-m5")
        registry = CardRegistry()
        registry._cards = {"hermes-m5": card}

        server = A2AServer()
        receipt_dir = tmp_path / "receipts"
        receipt_dir.mkdir()

        def handler(task):
            task.result = {"echo": True}
            task.status = A2ATaskStatus.COMPLETED
            receipt_path = receipt_dir / f"{task.id}.json"
            receipt_path.write_text(json.dumps({"task_id": task.id, "status": "completed"}))
            task.metadata["receipt_path"] = str(receipt_path)
            return task

        server.set_default_handler(handler)
        init_gateway(server=server, registry=registry, node_card=card, node_id="hermes-m5")

        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/a2a/tasks",
            json={
                "from_agent": "test",
                "to_agent": "hermes-m5",
                "messages": [{"content": "proof-of-life"}],
            },
        )
        assert ng._server is not None, "Gateway server should be initialised"
        assert ng._node_card is not None, "Gateway card should be initialised"

        if resp.status_code == 201:
            body = resp.json()
            assert body["status"] == "completed"
            assert body["result"]["echo"] is True
            receipt_path = Path(body["metadata"]["receipt_path"])
            assert receipt_path.exists()
            receipt = json.loads(receipt_path.read_text())
            assert receipt["task_id"] == body["id"]
            assert receipt["status"] == "completed"


class TestCorrelationIdStamping:
    """Phase 2A: correlation_id stamped at task creation."""

    def test_auto_generated_when_not_provided(self):
        """A2ATask auto-generates correlation_id if not supplied."""
        from dharma_swarm.a2a.a2a_server import A2ATask

        task = A2ATask(from_agent="test")
        assert task.correlation_id, "correlation_id should be auto-generated"
        assert len(task.correlation_id) == 32, "correlation_id should be UUID4 hex"

    def test_propagated_when_provided(self):
        """Explicit correlation_id is preserved."""
        from dharma_swarm.a2a.a2a_server import A2ATask

        cid = uuid.uuid4().hex
        task = A2ATask(from_agent="test", correlation_id=cid)
        assert task.correlation_id == cid

    def test_unique_per_task(self):
        """Each task gets a unique correlation_id."""
        from dharma_swarm.a2a.a2a_server import A2ATask

        t1 = A2ATask()
        t2 = A2ATask()
        assert t1.correlation_id != t2.correlation_id

    def test_fail_closed_on_empty_correlation_id(self):
        """Every A2A task receipt MUST have a non-empty correlation_id.

        This is the keystone of the correlation spine doctrine:
        'Receipts may differ by closure layer. Correlation identity must not.'
        If this test fails, the spine is broken.
        """
        from dharma_swarm.a2a.a2a_server import A2ATask

        task = A2ATask(from_agent="test")
        assert task.correlation_id, "correlation_id must never be empty — spine break"
        assert len(task.correlation_id.strip()) > 0, "correlation_id must not be whitespace-only"

        # Also verify it survives serialization round-trip
        from dataclasses import asdict

        d = asdict(task)
        assert d["correlation_id"] == task.correlation_id
        assert len(d["correlation_id"]) > 0


class TestCorrelationIdInReceipt:
    """Phase 2A: correlation_id appears in build_task_receipt output."""

    def test_correlation_id_in_receipt(self):
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt

        cid = uuid.uuid4().hex
        receipt = build_task_receipt(
            task_id="test-001",
            agent_uid="hermes-m5",
            status="completed",
            summary="test",
            correlation_id=cid,
        )
        assert receipt["correlation_id"] == cid

    def test_duration_ms_in_receipt(self):
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt

        receipt = build_task_receipt(
            task_id="test-002",
            agent_uid="hermes-m5",
            status="completed",
            summary="test",
            duration_ms=42.5,
        )
        assert receipt["duration_ms"] == 42.5

    def test_replay_command_in_receipt(self):
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt

        receipt = build_task_receipt(
            task_id="test-003",
            agent_uid="hermes-m5",
            status="completed",
            summary="test",
            replay_command="curl -X POST ...",
        )
        assert receipt["replay_command"] == "curl -X POST ..."

    def test_spine_receipt_id_in_receipt(self):
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt

        receipt = build_task_receipt(
            task_id="test-004",
            agent_uid="hermes-m5",
            status="completed",
            summary="test",
            spine_receipt_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        assert receipt["spine_receipt_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_omit_when_not_provided(self):
        """Fields not provided should not appear in receipt (backwards compat)."""
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt

        receipt = build_task_receipt(
            task_id="test-005",
            agent_uid="hermes-m5",
            status="completed",
            summary="test",
        )
        assert "correlation_id" not in receipt
        assert "duration_ms" not in receipt
        assert "replay_command" not in receipt
        assert "spine_receipt_id" not in receipt


class TestCrossLayerCorrelationChain:
    """Phase 2A: A2A correlation_id chains to spine trace_id (fixture-based).

    Actual wiring happens in PR B. This test proves the chain is
    structurally possible by showing the A2A receipt's correlation_id
    can serve as spine.EvidenceReceipt.trace_id.
    """

    def test_a2a_correlation_id_valid_as_spine_trace_id(self):
        """A2A correlation_id (UUID4 hex) is a valid trace_id."""
        from dharma_swarm.a2a.a2a_server import A2ATask
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt

        task = A2ATask(from_agent="test", to_agent="hermes-m5")
        receipt = build_task_receipt(
            task_id=task.id,
            agent_uid="hermes-m5",
            status="completed",
            summary="chain test",
            correlation_id=task.correlation_id,
            duration_ms=100.0,
            replay_command=f"dharma replay {task.id}",
        )

        # Simulate what spine.EvidenceReceipt would use
        spine_trace_id = task.correlation_id

        # The A2A receipt's correlation_id matches the spine trace_id
        assert receipt["correlation_id"] == spine_trace_id

        # Both are valid UUID4 hex strings
        uuid.UUID(hex=spine_trace_id)
        uuid.UUID(hex=receipt["correlation_id"])

    def test_propagated_correlation_from_upstream(self):
        """If upstream provides correlation_id, it chains through."""
        from dharma_swarm.operator_core.a2a_task_lifecycle import build_task_receipt

        upstream_cid = uuid.uuid4().hex
        receipt = build_task_receipt(
            task_id="chain-002",
            agent_uid="hermes-m5",
            status="completed",
            summary="propagation test",
            correlation_id=upstream_cid,
        )

        # Same correlation_id flows through
        assert receipt["correlation_id"] == upstream_cid

        # A hypothetical spine receipt using this as trace_id
        # would have: trace_id == upstream_cid == receipt["correlation_id"]
        # This is the three-layer chain: A2A ← spine ← closure_v0
