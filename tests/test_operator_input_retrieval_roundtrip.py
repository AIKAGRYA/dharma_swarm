"""PR 7 verifier — retrieval reconstructs the whole chain by correlation_id.

Deterministic, no-network. Builds a full lifecycle in a temp state root, then
proves the chain is findable by correlation_id, source text, candidate title,
and semantic route.
"""

from __future__ import annotations

from dharma_swarm.idea_spark.action_routing import emit_proposal
from dharma_swarm.idea_spark.fixtures import NOTE_FIXTURE
from dharma_swarm.idea_spark.memory_bridge import emit_memory_kernel_receipt
from dharma_swarm.idea_spark.projection import candidate_from_operator_receipt
from dharma_swarm.idea_spark.retrieval import (
    probe_by_correlation_id,
    probe_by_semantic_route,
    probe_by_text,
    probe_by_title,
    retrieve,
)
from dharma_swarm.idea_spark.store import (
    append_candidate,
    update_lifecycle_receipt,
    write_input_receipt,
)

FIXED_NOW = "2026-06-26T00:00:00Z"
OWNER = "dharma_swarm/idea_spark/"
ROUTE = "route.idea_spark_campaign"


def _full_chain(tmp_path):
    receipt = NOTE_FIXTURE.build_receipt()
    write_input_receipt(receipt, tmp_path)
    candidate = candidate_from_operator_receipt(
        receipt, claim=NOTE_FIXTURE.content, domain="tooling", now=FIXED_NOW
    ).model_copy(update={"authority_level": "proposal", "owner_surface": OWNER})
    append_candidate(candidate, tmp_path)

    update_lifecycle_receipt(
        candidate.correlation_id,
        tmp_path,
        status="captured",
        input_id=receipt.input_id,
        candidate_id=candidate.candidate_id,
    )
    update_lifecycle_receipt(
        candidate.correlation_id, tmp_path, status="staged", chetana_staged_atom_id="atom-uuid-123"
    )
    mem = emit_memory_kernel_receipt(candidate, state_root=tmp_path, created_at=FIXED_NOW)
    update_lifecycle_receipt(
        candidate.correlation_id, tmp_path, status="routed", semantic_route=ROUTE, owner_surface=OWNER
    )
    prop = emit_proposal(
        candidate,
        state_root=tmp_path,
        proposals_path=tmp_path / "evolution" / "pending_proposals.jsonl",
    )
    update_lifecycle_receipt(
        candidate.correlation_id,
        tmp_path,
        status="implemented",
        implementation_receipt_id="impl-receipt-1",
    )
    return receipt, candidate, mem, prop


def test_probe_by_correlation_id_reconstructs_chain(tmp_path) -> None:
    receipt, candidate, mem, prop = _full_chain(tmp_path)
    probe = probe_by_correlation_id(candidate.correlation_id, tmp_path)
    assert probe.found is True
    assert probe.input_receipt == receipt
    assert probe.candidate is not None and probe.candidate.candidate_id == candidate.candidate_id

    summary = probe.to_summary()
    assert summary["input_id"] == receipt.input_id
    assert summary["candidate_id"] == candidate.candidate_id
    assert summary["chetana_staged_atom_id"] == "atom-uuid-123"
    assert summary["memory_canonical_receipt_id"] == mem.canonical_receipt_id
    assert summary["memory_write_receipt_id"] == mem.write_receipt_id
    assert summary["semantic_route"] == ROUTE
    assert summary["owner_surface"] == OWNER
    assert summary["proposal_id"] == prop["id"]
    assert summary["implementation_receipt_id"] == "impl-receipt-1"
    assert summary["status"] == "implemented"
    assert probe.retrieval_probe_id.startswith("probe_")


def test_probe_by_text_title_and_route(tmp_path) -> None:
    _receipt, candidate, _mem, _prop = _full_chain(tmp_path)

    by_text = probe_by_text("memory kernel retrieval", tmp_path)
    assert any(p.correlation_id == candidate.correlation_id for p in by_text)

    by_title = probe_by_title(candidate.title[:20], tmp_path)
    assert any(p.correlation_id == candidate.correlation_id for p in by_title)

    by_route = probe_by_semantic_route(ROUTE, tmp_path)
    assert any(p.correlation_id == candidate.correlation_id for p in by_route)

    by_owner = probe_by_semantic_route(OWNER, tmp_path)
    assert any(p.correlation_id == candidate.correlation_id for p in by_owner)


def test_unified_retrieve_dedupes(tmp_path) -> None:
    _receipt, candidate, _mem, _prop = _full_chain(tmp_path)
    results = retrieve(
        correlation_id=candidate.correlation_id,
        text="memory kernel",
        title=candidate.title[:20],
        semantic_route=ROUTE,
        state_root=tmp_path,
    )
    # Same lifecycle matched by four handles, returned once.
    assert len(results) == 1
    assert results[0].correlation_id == candidate.correlation_id


def test_unknown_correlation_id_fails_safely(tmp_path) -> None:
    probe = probe_by_correlation_id("corr_does_not_exist", tmp_path)
    assert probe.found is False
    assert "lifecycle_receipt_not_found" in probe.blockers
