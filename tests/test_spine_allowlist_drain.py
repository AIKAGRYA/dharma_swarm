"""Tests for spine-adoption item 4: bypass allowlist drained to zero.

Every formerly-allowlisted production A2A submit surface now dispatches
through the shared spine adapter (``a2a_bridge.submit_task_via_spine``):

    1. node_gateway ``POST /tasks``        (was allowlist entry #1)
    2. node_gateway ``POST /a2a/tasks``    (was allowlist entry #2)
    3. a2a_client ``_dispatch_local``      (was allowlist entry #3)
    4. nats_transport ``consume_message``  (was allowlist entry #4)

Each proves the one-dispatch → exactly-one-EvidenceReceipt invariant by
counting actual ``invoke_agent()`` traversals, plus the standing
allow-list-at-zero guard (uplift_guards + ratchet baseline).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dharma_swarm.a2a import spine_adapter as adapter_mod
from dharma_swarm.a2a.a2a_client import A2AClient
from dharma_swarm.a2a.a2a_server import A2AMessage, A2AServer, A2ATask, A2ATaskStatus
from dharma_swarm.a2a.agent_card import AgentCapability, AgentCard, AgentSkill, CardRegistry
from dharma_swarm.a2a.node_gateway import init_gateway, router
from dharma_swarm.spine.receipt import EvidenceReceipt

_REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_bypass_report():
    spec = importlib.util.spec_from_file_location(
        "spine_bypass_report",
        _REPO_ROOT / "scripts" / "governance" / "spine_bypass_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def registry(tmp_path: Path) -> CardRegistry:
    d = tmp_path / "cards"
    d.mkdir()
    return CardRegistry(cards_dir=d)


@pytest.fixture
def server() -> A2AServer:
    srv = A2AServer()

    def _handler(task: A2ATask) -> A2ATask:
        task.result = "done"
        return task

    srv.set_default_handler(_handler)
    return srv


@pytest.fixture
def counting_invoke(monkeypatch) -> list[EvidenceReceipt]:
    """Count actual invoke_agent() traversals through the shared adapter."""
    traversals: list[EvidenceReceipt] = []
    real_invoke = adapter_mod.invoke_agent

    async def _counting(*args, **kwargs):
        receipt = await real_invoke(*args, **kwargs)
        traversals.append(receipt)
        return receipt

    monkeypatch.setattr(adapter_mod, "invoke_agent", _counting)
    return traversals


@pytest.fixture
def gateway_client(server: A2AServer, registry: CardRegistry) -> TestClient:
    from dharma_swarm.a2a import node_gateway

    app = FastAPI()
    card = AgentCard(
        name="drain-test-node",
        description="Allowlist drain test node",
        skills=[AgentSkill(name="code_review", description="Review code")],
    )
    init_gateway(server, registry, card, node_id="drain-test-node")
    node_gateway._allowed_keys = {"test-key"}
    app.include_router(router)
    return TestClient(app)


_TASK_BODY = {
    "from_agent": "remote-node",
    "to_agent": "coder",
    "capability": "code_review",
    "messages": [{"role": "user", "content": "Review this"}],
}
_AUTH = {"X-A2A-Key": "test-key"}


# ---------------------------------------------------------------------------
# 1+2. node_gateway endpoints (former allowlist entries #1, #2)
# ---------------------------------------------------------------------------


def test_gateway_submit_v1_emits_exactly_one_receipt(
    gateway_client: TestClient, counting_invoke: list[EvidenceReceipt],
):
    resp = gateway_client.post("/tasks", json=_TASK_BODY, headers=_AUTH)

    assert resp.status_code == 201
    assert resp.json()["status"] == "completed"
    assert len(counting_invoke) == 1
    receipt = counting_invoke[0]
    assert receipt.provider == "a2a"
    assert receipt.operation == "invoke_agent"
    assert receipt.status == "ok"


def test_gateway_submit_legacy_emits_exactly_one_receipt(
    gateway_client: TestClient, counting_invoke: list[EvidenceReceipt],
):
    resp = gateway_client.post("/a2a/tasks", json=_TASK_BODY, headers=_AUTH)

    assert resp.status_code == 201
    assert resp.json()["status"] == "completed"
    assert len(counting_invoke) == 1
    assert counting_invoke[0].status == "ok"


def test_gateway_failed_task_still_emits_one_receipt_and_422(
    gateway_client: TestClient,
    server: A2AServer,
    counting_invoke: list[EvidenceReceipt],
):
    def _boom(task: A2ATask) -> A2ATask:
        raise RuntimeError("handler exploded")

    server.set_default_handler(_boom)

    resp = gateway_client.post("/tasks", json=_TASK_BODY, headers=_AUTH)

    assert resp.status_code == 422
    assert resp.json()["status"] == "failed"
    assert len(counting_invoke) == 1
    assert counting_invoke[0].status == "failed"
    assert counting_invoke[0].error_source == "provider_failed"


# ---------------------------------------------------------------------------
# 3. a2a_client local delegation (former allowlist entry #3)
# ---------------------------------------------------------------------------


def test_client_local_dispatch_emits_exactly_one_receipt(
    server: A2AServer, registry: CardRegistry, counting_invoke: list[EvidenceReceipt],
):
    registry.register(AgentCard(
        name="local-coder",
        capabilities=[AgentCapability("code_review", "Review code")],
    ))
    client = A2AClient(registry=registry, server=server, default_from="tester")

    result = client.delegate_to("local-coder", "Review this PR")

    assert result.success
    assert result.task is not None
    assert result.task.status == A2ATaskStatus.COMPLETED
    assert len(counting_invoke) == 1
    assert counting_invoke[0].agent_id == "local-coder"
    assert counting_invoke[0].status == "ok"


def test_client_local_dispatch_preserves_trace_contract(
    server: A2AServer, registry: CardRegistry,
):
    """Auto-generated traces keep the legacy trc_ format (submit() contract)."""
    registry.register(AgentCard(
        name="trace-agent",
        capabilities=[AgentCapability("testing", "Test")],
    ))
    client = A2AClient(registry=registry, server=server, default_from="tester")

    result = client.delegate_to("trace-agent", "Run")

    assert result.success
    assert result.task.trace_id.startswith("trc_")


# ---------------------------------------------------------------------------
# 4. nats_transport consume ingress (former allowlist entry #4)
# ---------------------------------------------------------------------------


async def test_nats_consume_emits_exactly_one_receipt(
    tmp_path: Path, counting_invoke: list[EvidenceReceipt],
):
    from dharma_swarm.a2a.nats_transport import A2ANatsTransport
    from dharma_swarm.runtime_state import RuntimeStateStore
    from dharma_swarm.spine.identity import ExecutionIdentity

    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    identity = ExecutionIdentity.new(
        task_id="task-drain",
        agent_id="worker",
        session_id="session-drain",
        trace_id="trace-drain",
        correlation_id="corr-drain",
        run_id="run-drain",
        claim_id="claim-drain",
        idempotency_key="idem-drain",
    )
    srv = A2AServer(
        runtime_state=runtime, persist=False, require_execution_identity=True,
    )

    def handler(task: A2ATask) -> A2ATask:
        task.status = A2ATaskStatus.COMPLETED
        return task

    srv.register_handler("probe", handler)

    class _FakeJS:
        def __init__(self) -> None:
            self.published: list[bytes] = []

        async def publish(self, subject, payload, *, headers=None, timeout=None):
            self.published.append(payload)

            class _Ack:
                stream = "DHARMA_A2A"
                seq = 1

            return _Ack()

    class _FakeMsg:
        def __init__(self, data: bytes) -> None:
            self.subject = "dharma.a2a.task.worker.probe"
            self.data = data
            self.acked = 0
            self.nacked = 0

        async def ack(self) -> None:
            self.acked += 1

        async def nak(self) -> None:
            self.nacked += 1

    fake_js = _FakeJS()
    transport = A2ANatsTransport(
        runtime_state=runtime, server=srv, jetstream=fake_js,
    )
    task = A2ATask(
        id="a2a-drain",
        from_agent="operator",
        to_agent="worker",
        capability="probe",
        history=[A2AMessage.text("run probe")],
        metadata=identity.to_metadata(),
    )
    await transport.publish_task(task, identity=identity)
    msg = _FakeMsg(fake_js.published[0])

    ack = await transport.consume_message(msg)

    assert ack.action == "ack"
    assert ack.status == "ack"
    assert msg.acked == 1
    assert msg.nacked == 0
    assert len(counting_invoke) == 1
    assert counting_invoke[0].status == "ok"
    assert counting_invoke[0].agent_id == "worker"


# ---------------------------------------------------------------------------
# 5. Allow-list-at-zero: report empty + guard green
# ---------------------------------------------------------------------------


def test_intentional_bypass_allowlist_is_empty():
    """The drained allowlist stays a literal empty dict (onboard criterion
    `bypass_allowlist_empty`); the scan confirms zero intentional/unknown."""
    mod = _load_bypass_report()

    assert mod._INTENTIONAL_BYPASS == {}

    entries = mod._scan_production_submits()
    by_class: dict[str, int] = {}
    for e in entries:
        by_class[e.classification] = by_class.get(e.classification, 0) + 1
    assert by_class.get("intentional", 0) == 0
    assert by_class.get("unknown", 0) == 0
    # The single blessed dispatch site remains inside invoke_agent()
    assert by_class.get("spine-adopted", 0) == 1


def test_uplift_guard_holds_allowlist_at_ratchet_baseline():
    """check_spine_ownership enforces allow-list-at-zero fail-closed in the
    uplift_guards composition, deferring to the governed ratchet baseline."""
    import sys

    sys.path.insert(0, str(_REPO_ROOT))
    try:
        from scripts.uplift_guards.check_spine_ownership import (
            _check_bypass_allowlist_at_zero,
            check_spine_ownership,
        )
    finally:
        sys.path.remove(str(_REPO_ROOT))

    assert _check_bypass_allowlist_at_zero(_REPO_ROOT) == []
    ok, msg = check_spine_ownership(_REPO_ROOT)
    assert ok, msg
    assert "bypass allowlist at baseline" in msg
