"""Tests for the zeitgeist-inbox -> MemoryKernel promotion-proposal bridge."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionGate,
    MemoryPromotionQueueStatus,
)
from dharma_swarm.knowledge_ops.zeitgeist_promotion import (
    build_zeitgeist_promotion_queue,
    load_settled_atom_ids,
    load_zeitgeist_inbox,
    run_zeitgeist_promotion,
)


def _decision(atom_id: str, kind: str) -> dict[str, object]:
    return {
        "proposal_id": f"p-{atom_id}",
        "atom_id": atom_id,
        "surface_id": "world_zeitgeist",
        "decision": kind,
        "reviewer": "operator",
        "rationale": "test",
    }


def _signal(signal_id: str, **over: object) -> dict[str, object]:
    row = {
        "id": signal_id,
        "source": "world_zeitgeist",
        "category": "opportunity",
        "title": f"title {signal_id}",
        "description": f"desc {signal_id}",
        "relevance_score": 0.71,
        "keywords": ["agentic", "patterns"],
        "url": f"https://example.com/{signal_id}",
        "metadata": {
            "promotion_status": "promotion_ready",
            "promotion_reason": "independent sources agree",
            "source_count": 3,
        },
    }
    row.update(over)
    return row


def test_signal_becomes_ready_for_review_proposal() -> None:
    queue = build_zeitgeist_promotion_queue([_signal("world-1")])
    assert queue.promotion_proposal_count == 1
    proposal = queue.proposals[0]
    assert proposal.status is MemoryPromotionQueueStatus.READY_FOR_REVIEW
    assert proposal.atom_id == "world-1"
    assert proposal.surface_id == "world_zeitgeist"
    # OBSERVED is the honest state for an external observation AND is required
    # for the proposal to be promotable at all (regression guard for the bug
    # where "unverified" silently blocked every proposal).
    assert proposal.truth_state == "observed"


def test_every_proposal_requires_the_full_external_gate_battery() -> None:
    queue = build_zeitgeist_promotion_queue([_signal("world-1"), _signal("world-2")])
    required = {
        MemoryPromotionGate.HUMAN_REVIEW.value,
        MemoryPromotionGate.PROVENANCE_REVIEW.value,
        MemoryPromotionGate.CONFLICT_REVIEW.value,
        MemoryPromotionGate.PRIVACY_REVIEW.value,
        MemoryPromotionGate.CANON_POLICY_REVIEW.value,
        MemoryPromotionGate.KNOWLEDGEOPS_LINKING.value,
    }
    for proposal in queue.proposals:
        # external public content must not be promotable without privacy + canon
        assert required <= set(proposal.required_gates)


def test_proposals_are_promotable_and_receipt_compatible() -> None:
    # Guards the two Codex-review bugs: non-promotable truth_state, and a
    # proposal-id prefix the MemoryKernel receipt check would not recognize.
    from dharma_swarm.knowledge_ops.memory_promotion_executor import (
        _PROMOTABLE_TRUTH_STATES,
    )

    proposal = build_zeitgeist_promotion_queue([_signal("world-1")]).proposals[0]
    assert proposal.truth_state in _PROMOTABLE_TRUTH_STATES
    assert proposal.proposal_id.startswith("memory_promotion_proposal:")
    assert proposal.has_content is False


def test_rows_without_id_are_blocked_not_promoted() -> None:
    queue = build_zeitgeist_promotion_queue([_signal(""), _signal("world-ok")])
    assert queue.promotion_proposal_count == 1
    assert queue.blocked_atom_count == 1


def test_duplicate_signal_ids_collapse() -> None:
    queue = build_zeitgeist_promotion_queue([_signal("world-1"), _signal("world-1")])
    assert queue.promotion_proposal_count == 1


def test_queue_declares_read_only_no_mutation() -> None:
    queue = build_zeitgeist_promotion_queue([_signal("world-1")])
    assert "no_canon_or_memory_writes" in queue.warnings
    assert "read_only_queue_not_authority" in queue.warnings


def test_load_inbox_is_defensive(tmp_path: Path) -> None:
    inbox = tmp_path / "world_zeitgeist_inbox.jsonl"
    inbox.write_text(
        json.dumps(_signal("world-1")) + "\n"
        + "not json\n"
        + "\n"
        + json.dumps(_signal("world-2")) + "\n",
        encoding="utf-8",
    )
    rows = load_zeitgeist_inbox(inbox)
    assert len(rows) == 2  # garbled + blank lines skipped


def test_missing_inbox_yields_empty(tmp_path: Path) -> None:
    assert load_zeitgeist_inbox(tmp_path / "nope.jsonl") == []


def test_accounting_invariant_holds() -> None:
    # total == proposals + blocker_occurrence_count, counting no-id, settled, dups
    rows = [
        _signal("world-1"),
        _signal("world-1"),  # duplicate
        _signal(""),  # blocked
        _signal("world-2"),
        _signal("world-3"),  # will be settled
    ]
    queue = build_zeitgeist_promotion_queue(rows, settled_atom_ids=frozenset({"world-3"}))
    assert queue.total_atoms_reviewed == (
        queue.promotion_proposal_count + queue.blocker_occurrence_count
    )
    assert queue.promotion_proposal_count == 2  # world-1, world-2


def test_settled_signals_are_not_reproposed() -> None:
    rows = [_signal("world-1"), _signal("world-2"), _signal("world-3")]
    queue = build_zeitgeist_promotion_queue(
        rows, settled_atom_ids=frozenset({"world-1", "world-2"})
    )
    ids = {p.atom_id for p in queue.proposals}
    assert ids == {"world-3"}
    assert "prior_operator_decisions_honored" in queue.warnings


def test_load_settled_reads_accept_and_reject_not_defer(tmp_path: Path) -> None:
    ledger = tmp_path / "zeitgeist_promotion_decisions.json"
    ledger.write_text(
        json.dumps(
            {
                "decisions": [
                    _decision("world-accepted", "accept"),
                    _decision("world-rejected", "reject"),
                    _decision("world-deferred", "defer"),
                ]
            }
        ),
        encoding="utf-8",
    )
    settled = load_settled_atom_ids(ledger)
    assert settled == frozenset({"world-accepted", "world-rejected"})
    # DEFER intentionally resurfaces
    assert "world-deferred" not in settled


def test_missing_decision_ledger_is_empty(tmp_path: Path) -> None:
    assert load_settled_atom_ids(tmp_path / "nope.json") == frozenset()


def test_run_honors_prior_decisions_across_cycles(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    (meta / "knowledge_ops").mkdir(parents=True)
    (meta / "world_zeitgeist_inbox.jsonl").write_text(
        json.dumps(_signal("world-1")) + "\n" + json.dumps(_signal("world-2")) + "\n",
        encoding="utf-8",
    )
    # operator rejected world-1 in a prior cycle
    (meta / "knowledge_ops" / "zeitgeist_promotion_decisions.json").write_text(
        json.dumps({"decisions": [_decision("world-1", "reject")]}), encoding="utf-8"
    )
    summary = run_zeitgeist_promotion(tmp_path)
    assert summary["proposal_count"] == 1  # only world-2 re-proposed
    assert summary["settled_skipped"] == 1


def test_settled_skipped_counts_only_rows_present_in_this_batch(tmp_path: Path) -> None:
    # Greptile finding: settled_skipped must reflect settled ids actually
    # present in THIS inbox run, not every accept/reject ever recorded.
    meta = tmp_path / "meta"
    (meta / "knowledge_ops").mkdir(parents=True)
    (meta / "world_zeitgeist_inbox.jsonl").write_text(
        json.dumps(_signal("world-1")) + "\n" + json.dumps(_signal("world-2")) + "\n",
        encoding="utf-8",
    )
    # Ledger carries decisions for world-1 (still in the inbox) AND for three
    # ids that have since scrolled out of the inbox entirely.
    (meta / "knowledge_ops" / "zeitgeist_promotion_decisions.json").write_text(
        json.dumps(
            {
                "decisions": [
                    _decision("world-1", "reject"),
                    _decision("stale-a", "accept"),
                    _decision("stale-b", "reject"),
                    _decision("stale-c", "accept"),
                ]
            }
        ),
        encoding="utf-8",
    )
    summary = run_zeitgeist_promotion(tmp_path)
    assert summary["proposal_count"] == 1  # only world-2 re-proposed
    # Old buggy behaviour would report 4 (len of the whole settled set).
    assert summary["settled_skipped"] == 1


def test_run_writes_review_artifacts_but_not_memory(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    meta.mkdir(parents=True)
    (meta / "world_zeitgeist_inbox.jsonl").write_text(
        json.dumps(_signal("world-1")) + "\n", encoding="utf-8"
    )
    summary = run_zeitgeist_promotion(tmp_path)
    assert summary["proposal_count"] == 1
    review_json = Path(summary["review_json"])
    review_md = Path(summary["review_md"])
    assert review_json.exists() and review_md.exists()
    # Read-only: writes ONLY under meta/knowledge_ops, never a memory store.
    assert review_json.parent == meta / "knowledge_ops"
    payload = json.loads(review_json.read_text(encoding="utf-8"))
    assert payload["promotion_proposal_count"] == 1
