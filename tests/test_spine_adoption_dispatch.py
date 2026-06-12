"""Tests for the first Spine adoption slice: A2A bridge → invoke_agent().

Proves four invariants:
    1. One dispatch → exactly one EvidenceReceipt (not zero, not two).
    2. Identity preserved across ExecutionIdentity / receipt / trace_id /
       correlation_id / proposal_id / task_id.
    3. Failure source recorded correctly on handler error.
    4. Double-submit does not emit a second EvidenceReceipt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.a2a.agent_card import CardRegistry
from dharma_swarm.a2a.a2a_server import (
    A2AMessage,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.a2a_bridge import A2ABridge
from dharma_swarm.spine.receipt import EvidenceReceipt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cards_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cards"
    d.mkdir()
    return d


@pytest.fixture
def registry(cards_dir: Path) -> CardRegistry:
    return CardRegistry(cards_dir=cards_dir)


def _success_handler(task: A2ATask) -> A2ATask:
    task.result = "processed"
    return task


def _failure_handler(task: A2ATask) -> A2ATask:
    raise RuntimeError("handler exploded")


def _no_handler_server() -> A2AServer:
    return A2AServer()


def _make_bridge(
    registry: CardRegistry,
    handler=_success_handler,
    *,
    trishula_outbox: Path | None = None,
) -> tuple[A2ABridge, A2AServer]:
    server = A2AServer()
    if handler is not None:
        server.set_default_handler(handler)
    bridge = A2ABridge(
        server=server,
        registry=registry,
        trishula_outbox=trishula_outbox or Path("/tmp/nonexistent"),
    )
    return bridge, server


def _sample_task(
    *,
    trace_id: str = "",
    proposal_id: str = "",
    correlation_id: str = "",
) -> A2ATask:
    meta: dict = {"source": "test"}
    if proposal_id:
        meta["proposal_id"] = proposal_id
    if correlation_id:
        meta["correlation_id"] = correlation_id
    return A2ATask(
        from_agent="orchestrator",
        to_agent="coder",
        capability="code_review",
        history=[A2AMessage.text("Review this PR")],
        trace_id=trace_id,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# 1. Exactly-one-receipt invariant
# ---------------------------------------------------------------------------


async def test_a2a_bridge_dispatch_emits_exactly_one_evidence_receipt(
    registry: CardRegistry,
):
    bridge, _ = _make_bridge(registry)
    task = _sample_task()

    result, receipt = await bridge.submit_via_spine(task)

    assert isinstance(receipt, EvidenceReceipt)
    assert receipt.status == "ok"
    assert receipt.error_source == "none"
    assert receipt.provider == "a2a"
    assert receipt.operation == "invoke_agent"
    assert receipt.provider_attempted is True
    assert receipt.agent_id == "coder"
    assert result.status == A2ATaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# 2. Identity-preservation invariant
# ---------------------------------------------------------------------------


async def test_a2a_bridge_receipt_preserves_execution_identity(
    registry: CardRegistry,
):
    bridge, _ = _make_bridge(registry)
    task = _sample_task(
        trace_id="trace_abc",
        correlation_id="corr_xyz",
        proposal_id="prop_42",
    )

    result, receipt = await bridge.submit_via_spine(task)

    # trace_id set on task propagates
    assert receipt.trace_id == "trace_abc"
    # correlation_id preserved in attributes
    assert receipt.attributes["correlation_id"] == "corr_xyz"
    # proposal_id preserved in attributes
    assert receipt.attributes["proposal_id"] == "prop_42"
    # task_id matches what the server assigned
    identity_dict = result.metadata.get("execution_identity", {})
    assert receipt.task_id == identity_dict["task_id"]
    # span_id = run_id from identity
    assert receipt.span_id == identity_dict["run_id"]


# ---------------------------------------------------------------------------
# 3. Failure-source recording
# ---------------------------------------------------------------------------


async def test_a2a_bridge_receipt_records_failure_source(
    registry: CardRegistry,
):
    bridge, _ = _make_bridge(registry, handler=_failure_handler)
    task = _sample_task()

    result, receipt = await bridge.submit_via_spine(task)

    assert receipt.status == "failed"
    assert receipt.error_source == "provider_failed"
    assert receipt.error_detail is not None
    assert "handler exploded" in receipt.error_detail
    assert result.status == A2ATaskStatus.FAILED


async def test_a2a_bridge_receipt_records_no_handler_failure(
    registry: CardRegistry,
):
    bridge, _ = _make_bridge(registry, handler=None)
    task = _sample_task()

    result, receipt = await bridge.submit_via_spine(task)

    assert receipt.status == "failed"
    assert receipt.error_source in ("provider_failed", "internal_error")
    assert result.status == A2ATaskStatus.FAILED


# ---------------------------------------------------------------------------
# 4. No double-emit invariant
# ---------------------------------------------------------------------------


async def test_a2a_bridge_does_not_double_emit_receipts(
    registry: CardRegistry,
):
    """Two calls to submit_via_spine produce two independent receipts,
    each with a distinct receipt_id — proving one-receipt-per-dispatch.
    """
    bridge, _ = _make_bridge(registry)

    task1 = _sample_task(trace_id="t1")
    task2 = _sample_task(trace_id="t2")

    _, receipt1 = await bridge.submit_via_spine(task1)
    _, receipt2 = await bridge.submit_via_spine(task2)

    assert receipt1.receipt_id != receipt2.receipt_id
    assert receipt1.trace_id == "t1"
    assert receipt2.trace_id == "t2"


# ---------------------------------------------------------------------------
# 5. Cost/token fields are null (A2A does not carry them)
# ---------------------------------------------------------------------------


async def test_a2a_bridge_receipt_cost_fields_null(
    registry: CardRegistry,
):
    bridge, _ = _make_bridge(registry)
    task = _sample_task()

    _, receipt = await bridge.submit_via_spine(task)

    assert receipt.input_tokens is None
    assert receipt.output_tokens is None
    assert receipt.cost_usd is None
    assert receipt.latency_ms is not None
    assert receipt.latency_ms >= 0


# ---------------------------------------------------------------------------
# 6. Routing decision linked to receipt
# ---------------------------------------------------------------------------


async def test_a2a_bridge_receipt_links_routing_decision(
    registry: CardRegistry,
):
    bridge, _ = _make_bridge(registry)
    task = _sample_task()

    _, receipt = await bridge.submit_via_spine(task)

    assert receipt.routing_decision_id is not None
    assert receipt.attributes["capability"] == "code_review"
    assert receipt.attributes["a2a_task_id"]


# ---------------------------------------------------------------------------
# 7. Bypass report script is importable and classifies correctly
# ---------------------------------------------------------------------------


def test_spine_bypass_report_classifies_known_sites():
    """Bypass report must run without errors and find zero unknowns."""
    # Import locally so test failure points at the script
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "spine_bypass_report",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "governance"
        / "spine_bypass_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    entries = mod._scan_production_submits()
    unknowns = [e for e in entries if e.classification == "unknown"]
    assert unknowns == [], (
        f"Bypass report found {len(unknowns)} unclassified .submit() site(s): "
        + ", ".join(f"{e.file}:{e.line}" for e in unknowns)
    )


# ---------------------------------------------------------------------------
# 8. Track completion criteria (ACTIVE_TRACK: runtime-truth-spine-adoption)
# ---------------------------------------------------------------------------


async def test_every_dispatch_emits_exactly_one_evidence_receipt(
    registry: CardRegistry, monkeypatch,
):
    """Criterion `dispatch_emits_evidence_receipt`: for every dispatch through a
    spine-adopted production surface, exactly ONE EvidenceReceipt is produced —
    not zero, not two. Counts actual invoke_agent traversals instead of trusting
    the return type. (The orchestrator surface has its own equivalent suite:
    tests/test_orchestrator_spine_dispatch.py.)
    """
    from dharma_swarm.a2a import a2a_bridge as bridge_mod

    traversals: list[EvidenceReceipt] = []
    real_invoke = bridge_mod.invoke_agent

    async def counting_invoke(*args, **kwargs):
        receipt = await real_invoke(*args, **kwargs)
        traversals.append(receipt)
        return receipt

    monkeypatch.setattr(bridge_mod, "invoke_agent", counting_invoke)

    bridge, _ = _make_bridge(registry)
    n_dispatches = 3
    returned: list[EvidenceReceipt] = []
    for _ in range(n_dispatches):
        result, receipt = await bridge.submit_via_spine(_sample_task())
        assert isinstance(receipt, EvidenceReceipt)
        assert result.status == A2ATaskStatus.COMPLETED
        returned.append(receipt)

    # Exactly one spine traversal per dispatch...
    assert len(traversals) == n_dispatches
    # ...each producing the receipt the caller got back...
    assert [r.receipt_id for r in traversals] == [r.receipt_id for r in returned]
    # ...and every receipt distinct (no reuse across dispatches).
    assert len({r.receipt_id for r in returned}) == n_dispatches


def test_no_dropoff_sources_remain():
    """Criterion `zero_dropoff_sources`: no production dispatch source drops off
    the spine UNACCOUNTED. Every A2AServer.submit() call site must be either
    spine-adopted or an explicitly declared intentional bypass — and the
    declared allowlist must not have rotted (each entry still matches a real,
    currently-scanned site; stale entries hide drift).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "spine_bypass_report",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "governance"
        / "spine_bypass_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    entries = mod._scan_production_submits()

    # 1. No unaccounted drop-off sources.
    unknowns = [e for e in entries if e.classification == "unknown"]
    assert unknowns == [], (
        f"{len(unknowns)} unaccounted dispatch drop-off(s): "
        + ", ".join(f"{e.file}:{e.line}" for e in unknowns)
    )

    # 2. Allowlist freshness: every declared intentional bypass corresponds to a
    #    site the scan still finds at that exact (file, line). A mismatch means
    #    code moved and the allowlist silently rotted.
    scanned_allowlisted = {
        (e.file, e.line) for e in entries if e.classification == "intentional"
    }
    declared = set(mod._INTENTIONAL_BYPASS.keys())
    stale = declared - scanned_allowlisted
    assert stale == set(), (
        "Stale allowlist entries (declared but no matching site found): "
        + ", ".join(f"{f}:{ln}" for f, ln in sorted(stale))
    )
