"""Tests for the DharmaGraph -> Titanium Telos bridge."""

from __future__ import annotations

from dharma_swarm.graph.telos_bridge import (
    GATE_GRAPH_RECEIPT_ANCHOR,
    GraphTelosBridge,
)
from dharma_swarm.merkle_log import MemoryBackend, MerkleLog
from dharma_swarm.spine.receipt import EvidenceReceipt


def _receipt(status: str = "ok") -> EvidenceReceipt:
    return EvidenceReceipt(
        task_id="task-1",
        agent_id="agent-1",
        provider_attempted=True,
        status=status,  # type: ignore[arg-type]
    )


def test_bridge_anchors_ok_receipt_as_warn_without_manifest():
    log = MerkleLog(backend=MemoryBackend())
    result = GraphTelosBridge(log).record_dispatch_receipt(
        _receipt(),
        side_effect_key="invoke_agent:task-1:agent-1",
        operation_hash="a" * 64,
        proposal_id="11111111-1111-4111-8111-111111111111",
    )

    assert result.verdict == "WARN"
    assert result.reason == "manifest_not_supplied"
    assert result.root_uri.startswith("sha256:")
    assert result.leaf_index == 0
    assert log.verify_chain()[0] is True

    leaf = log.leaf_at(0)
    assert leaf["gate"] == GATE_GRAPH_RECEIPT_ANCHOR
    assert leaf["measure"]["receipt_hash"].startswith("sha256:")
    assert leaf["measure"]["side_effect_key_hash"].startswith("sha256:")
    assert leaf["measure"]["operation_hash"] == f"sha256:{'a' * 64}"


def test_bridge_blocks_without_appending_when_chain_is_broken():
    log = MerkleLog(backend=MemoryBackend())
    log.append({"n": 1})
    log.hashes[0] = b"\xff" * 32

    result = GraphTelosBridge(log).record_dispatch_receipt(
        _receipt(),
        side_effect_key="invoke_agent:task-1:agent-1",
        proposal_id="22222222-2222-4222-8222-222222222222",
    )

    assert result.verdict == "BLOCK"
    assert result.reason == "titanium_chain_not_verified"
    assert result.leaf_index is None
    assert result.first_broken_index == 0
    assert log.get_chain_length() == 1


def test_bridge_records_block_leaf_when_side_effect_key_missing():
    log = MerkleLog(backend=MemoryBackend())
    result = GraphTelosBridge(log).record_dispatch_receipt(
        _receipt(),
        side_effect_key="",
        proposal_id="33333333-3333-4333-8333-333333333333",
    )

    assert result.verdict == "BLOCK"
    assert result.reason == "missing_side_effect_key"
    assert result.leaf_index == 0
    assert log.leaf_at(0)["verdict"] == "BLOCK"
