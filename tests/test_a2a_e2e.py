"""End-to-end integration tests for the A2A subsystem.

Verifies the full lifecycle with trace identity propagation:
    1. Register agents → publish cards → discover → delegate → result
    2. CorrelationContext trace_id flows through local + bridge paths
    3. JSONL task persistence produces durable audit records
    4. TRISHULA bridge round-trip preserves trace_id
    5. Gateway HTTP layer propagates trace_id across node boundaries
"""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm.a2a.agent_card import (
    AgentCapability,
    AgentCard,
    CardRegistry,
)
from dharma_swarm.a2a.a2a_server import (
    A2AMessage,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.a2a_client import A2AClient, DelegationResult
from dharma_swarm.a2a.a2a_bridge import A2ABridge
from dharma_swarm.a2a import node_gateway
from dharma_swarm.correlation_context import (
    CorrelationContext,
    set_correlation,
    reset_correlation,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def cards_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cards"
    d.mkdir()
    return d


@pytest.fixture
def task_log_path(tmp_path: Path) -> Path:
    return tmp_path / "task_log.jsonl"


@pytest.fixture
def registry(cards_dir: Path) -> CardRegistry:
    return CardRegistry(cards_dir=cards_dir)


@pytest.fixture
def server(task_log_path: Path) -> A2AServer:
    return A2AServer(task_log_path=task_log_path, persist=True)


@pytest.fixture
def client(registry: CardRegistry, server: A2AServer) -> A2AClient:
    return A2AClient(registry=registry, server=server, default_from="test-orchestrator")


def _echo_handler(task: A2ATask) -> A2ATask:
    """Handler that echoes back the first message content as result."""
    content = ""
    for msg in task.messages:
        for part in msg.parts:
            content += part.content
    task.result = f"echo: {content}"
    task.status = A2ATaskStatus.COMPLETED
    return task


# ===========================================================================
# E2E: Full local lifecycle with trace propagation
# ===========================================================================


class TestA2ALocalLifecycleE2E:
    """Full register → discover → delegate → result with trace_id."""

    def test_full_lifecycle_with_trace(
        self,
        registry: CardRegistry,
        server: A2AServer,
        client: A2AClient,
        task_log_path: Path,
    ) -> None:
        coder_card = AgentCard(
            name="e2e-coder",
            description="Test coder for E2E",
            role="coder",
            capabilities=[AgentCapability("code_review", "Reviews code")],
        )
        registry.register(coder_card)
        server.register_handler("code_review", _echo_handler)

        ctx = CorrelationContext(
            trace_id="trc_e2e_lifecycle_001",
            session_id="sess_e2e",
        )
        token = set_correlation(ctx)
        try:
            discovered = client.discover("code_review")
            assert len(discovered) == 1
            assert discovered[0].name == "e2e-coder"

            result = client.delegate(
                "code_review",
                "Review the auth module",
            )
            assert result.success
            assert result.agent_name == "e2e-coder"
            assert "echo: Review the auth module" in result.result_text

            task = result.task
            assert task is not None
            assert task.trace_id == "trc_e2e_lifecycle_001"
            assert task.status == A2ATaskStatus.COMPLETED
        finally:
            reset_correlation(token)

        assert task_log_path.exists()
        log_entries = server.load_task_log()
        assert len(log_entries) == 1
        entry = log_entries[0]
        assert entry["trace_id"] == "trc_e2e_lifecycle_001"
        assert entry["from_agent"] == "test-orchestrator"
        assert entry["to_agent"] == "e2e-coder"
        assert entry["status"] == "completed"
        assert entry["capability"] == "code_review"

    def test_lifecycle_without_context_generates_trace(
        self,
        registry: CardRegistry,
        server: A2AServer,
        client: A2AClient,
    ) -> None:
        registry.register(AgentCard(
            name="auto-trace-agent",
            capabilities=[AgentCapability("testing", "Test agent")],
        ))
        server.register_handler("testing", _echo_handler)

        result = client.delegate("testing", "Run tests")
        assert result.success
        assert result.task is not None
        assert result.task.trace_id.startswith("trc_")
        assert len(result.task.trace_id) > 4

    def test_multiple_tasks_share_trace_in_same_context(
        self,
        registry: CardRegistry,
        server: A2AServer,
        client: A2AClient,
    ) -> None:
        registry.register(AgentCard(
            name="multi-agent",
            capabilities=[
                AgentCapability("code_review", "Review code"),
                AgentCapability("testing", "Run tests"),
            ],
        ))
        server.register_handler("code_review", _echo_handler)
        server.register_handler("testing", _echo_handler)

        ctx = CorrelationContext(trace_id="trc_shared_trace_42")
        token = set_correlation(ctx)
        try:
            r1 = client.delegate("code_review", "Review step 1")
            r2 = client.delegate("testing", "Test step 2")
        finally:
            reset_correlation(token)

        assert r1.success and r2.success
        assert r1.task is not None and r2.task is not None
        assert r1.task.trace_id == "trc_shared_trace_42"
        assert r2.task.trace_id == "trc_shared_trace_42"
        assert r1.task.id != r2.task.id

    def test_failed_task_still_persisted_with_trace(
        self,
        registry: CardRegistry,
        server: A2AServer,
        client: A2AClient,
        task_log_path: Path,
    ) -> None:
        registry.register(AgentCard(
            name="failing-agent",
            capabilities=[AgentCapability("risky_op", "Might fail")],
        ))

        def _failing_handler(task: A2ATask) -> A2ATask:
            raise RuntimeError("Simulated failure")

        server.register_handler("risky_op", _failing_handler)

        ctx = CorrelationContext(trace_id="trc_failure_case")
        token = set_correlation(ctx)
        try:
            result = client.delegate("risky_op", "Do risky thing")
        finally:
            reset_correlation(token)

        assert not result.success
        assert "Simulated failure" in (result.error or "")

        log = server.load_task_log()
        assert len(log) == 1
        assert log[0]["trace_id"] == "trc_failure_case"
        assert log[0]["status"] == "failed"
        assert "Simulated failure" in log[0]["error"]


# ===========================================================================
# E2E: TRISHULA bridge with trace propagation
# ===========================================================================


class TestBridgeTraceE2E:
    """Verify trace_id survives TRISHULA ↔ A2A round-trip."""

    def test_trishula_inbound_preserves_trace(
        self,
        registry: CardRegistry,
        server: A2AServer,
        tmp_path: Path,
    ) -> None:
        server.register_handler("task_execution", _echo_handler)
        bridge = A2ABridge(server=server, registry=registry)

        trishula_msg = {
            "id": "trish_001",
            "from": "hermes-m5",
            "to": "devin-roaming",
            "type": "task",
            "priority": "high",
            "subject": "Review PR #42",
            "body": "Please check the auth changes",
            "created_at": "2026-05-28T05:00:00Z",
            "trace_id": "trc_hermes_bridge_001",
        }

        task = bridge.trishula_message_to_a2a_task(trishula_msg)
        assert task.trace_id == "trc_hermes_bridge_001"
        assert task.from_agent == "hermes-m5"
        assert task.capability == "task_execution"

        submitted = server.submit(task)
        assert submitted.trace_id == "trc_hermes_bridge_001"
        assert submitted.status == A2ATaskStatus.COMPLETED

    def test_trishula_outbound_includes_trace(
        self,
        registry: CardRegistry,
        server: A2AServer,
    ) -> None:
        bridge = A2ABridge(server=server, registry=registry)

        task = A2ATask(
            from_agent="orchestrator",
            to_agent="devin-roaming",
            capability="code_review",
            trace_id="trc_outbound_round_trip",
            messages=[A2AMessage.text("Review completed")],
            status=A2ATaskStatus.COMPLETED,
            result="All good",
        )

        trishula_msg = bridge.a2a_task_to_trishula_message(task)
        assert trishula_msg["trace_id"] == "trc_outbound_round_trip"

    def test_trishula_without_trace_gets_auto_trace(
        self,
        registry: CardRegistry,
        server: A2AServer,
    ) -> None:
        server.register_handler("task_execution", _echo_handler)
        bridge = A2ABridge(server=server, registry=registry)

        trishula_msg = {
            "id": "trish_no_trace",
            "from": "opus-composer",
            "to": "devin-roaming",
            "type": "task",
            "subject": "No trace test",
            "body": "This message has no trace_id",
        }

        task = bridge.trishula_message_to_a2a_task(trishula_msg)
        assert task.trace_id == ""

        submitted = server.submit(task)
        assert submitted.trace_id.startswith("trc_")

    def test_inbox_ingestion_preserves_trace(
        self,
        registry: CardRegistry,
        server: A2AServer,
        tmp_path: Path,
    ) -> None:
        server.register_handler("task_execution", _echo_handler)
        bridge = A2ABridge(server=server, registry=registry)

        inbox = tmp_path / "inbox"
        inbox.mkdir()

        msg_data = {
            "id": "inbox_msg_001",
            "from": "codex-composer",
            "to": "devin",
            "type": "task",
            "subject": "Verify chain",
            "body": "Check the 11-step chain",
            "trace_id": "trc_inbox_e2e",
        }
        (inbox / "msg_001.json").write_text(
            json.dumps(msg_data), encoding="utf-8",
        )

        tasks = bridge.ingest_trishula_inbox(inbox_path=inbox)
        assert len(tasks) == 1
        assert tasks[0].trace_id == "trc_inbox_e2e"
        assert tasks[0].status == A2ATaskStatus.COMPLETED

    def test_send_result_writes_trace_to_outbox(
        self,
        registry: CardRegistry,
        server: A2AServer,
        tmp_path: Path,
    ) -> None:
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        bridge = A2ABridge(
            server=server,
            registry=registry,
            trishula_outbox=outbox,
        )

        task = A2ATask(
            from_agent="orchestrator",
            to_agent="devin",
            capability="testing",
            trace_id="trc_file_write_test",
            status=A2ATaskStatus.COMPLETED,
            result="Tests pass",
        )

        path = bridge.send_result_to_trishula(task)
        assert path is not None
        assert path.exists()

        written = json.loads(path.read_text(encoding="utf-8"))
        assert written["trace_id"] == "trc_file_write_test"


# ===========================================================================
# E2E: Gateway trace propagation (HTTP boundary)
# ===========================================================================


class TestGatewayTraceE2E:
    """Verify trace_id crosses the HTTP boundary via node gateway."""

    @pytest.fixture
    def gateway_app(self, server: A2AServer, registry: CardRegistry) -> FastAPI:
        test_card = AgentCard(
            name="gateway-node",
            description="Test gateway node",
            capabilities=[AgentCapability("code_review", "Reviews code")],
        )
        app = FastAPI()
        app.include_router(node_gateway.router)
        node_gateway.init_gateway(
            server=server,
            registry=registry,
            node_card=test_card,
            node_id="test-gateway",
        )
        node_gateway._allowed_keys = {"test-key"}
        return app

    @pytest.fixture
    def http_client(self, gateway_app: FastAPI) -> TestClient:
        return TestClient(gateway_app)

    def test_submit_with_trace_id(
        self,
        http_client: TestClient,
        server: A2AServer,
    ) -> None:
        server.register_handler("code_review", _echo_handler)

        resp = http_client.post(
            "/a2a/tasks",
            json={
                "from_agent": "remote-hub",
                "capability": "code_review",
                "messages": [{"role": "user", "content": "Review PR #99"}],
                "trace_id": "trc_gateway_http_001",
            },
            headers={"X-A2A-Key": "test-key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["trace_id"] == "trc_gateway_http_001"
        assert data["status"] == "completed"

    def test_submit_without_trace_gets_auto_trace(
        self,
        http_client: TestClient,
        server: A2AServer,
    ) -> None:
        server.register_handler("code_review", _echo_handler)

        resp = http_client.post(
            "/a2a/tasks",
            json={
                "from_agent": "remote-hub",
                "capability": "code_review",
                "messages": [{"role": "user", "content": "No trace"}],
            },
            headers={"X-A2A-Key": "test-key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["trace_id"].startswith("trc_")

    def test_task_status_includes_trace(
        self,
        http_client: TestClient,
        server: A2AServer,
    ) -> None:
        server.register_handler("code_review", _echo_handler)
        headers = {"X-A2A-Key": "test-key"}

        resp = http_client.post(
            "/a2a/tasks",
            json={
                "from_agent": "poller",
                "capability": "code_review",
                "messages": [{"role": "user", "content": "Status check"}],
                "trace_id": "trc_status_check",
            },
            headers=headers,
        )
        task_id = resp.json()["id"]

        status_resp = http_client.get(f"/a2a/tasks/{task_id}", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["trace_id"] == "trc_status_check"


# ===========================================================================
# E2E: Persistence audit trail
# ===========================================================================


class TestPersistenceAuditE2E:
    """Verify JSONL persistence creates a complete audit trail."""

    def test_multi_task_audit_log(
        self,
        registry: CardRegistry,
        server: A2AServer,
        client: A2AClient,
        task_log_path: Path,
    ) -> None:
        registry.register(AgentCard(
            name="audit-agent",
            capabilities=[AgentCapability("work", "Does work")],
        ))
        server.register_handler("work", _echo_handler)

        ctx = CorrelationContext(trace_id="trc_audit_batch")
        token = set_correlation(ctx)
        try:
            for i in range(5):
                result = client.delegate("work", f"Task {i}")
                assert result.success
        finally:
            reset_correlation(token)

        log = server.load_task_log()
        assert len(log) == 5
        for i, entry in enumerate(log):
            assert entry["trace_id"] == "trc_audit_batch"
            assert entry["status"] == "completed"
            assert entry["capability"] == "work"

    def test_persistence_disabled(self, tmp_path: Path) -> None:
        log_path = tmp_path / "nolog.jsonl"
        srv = A2AServer(task_log_path=log_path, persist=False)
        srv.register_handler("test", _echo_handler)

        task = A2ATask(
            from_agent="x",
            to_agent="y",
            capability="test",
            messages=[A2AMessage.text("no log")],
        )
        srv.submit(task)

        assert not log_path.exists()

    def test_log_survives_server_restart(self, tmp_path: Path) -> None:
        log_path = tmp_path / "durable.jsonl"
        srv1 = A2AServer(task_log_path=log_path, persist=True)
        srv1.register_handler("work", _echo_handler)

        task = A2ATask(
            from_agent="a",
            to_agent="b",
            capability="work",
            messages=[A2AMessage.text("before restart")],
            trace_id="trc_durable_001",
        )
        srv1.submit(task)

        srv2 = A2AServer(task_log_path=log_path, persist=True)
        log = srv2.load_task_log()
        assert len(log) == 1
        assert log[0]["trace_id"] == "trc_durable_001"
