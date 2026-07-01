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
    load_zeitgeist_inbox,
    run_zeitgeist_promotion,
)


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
    assert proposal.truth_state == "unverified"


def test_every_proposal_requires_human_review() -> None:
    queue = build_zeitgeist_promotion_queue([_signal("world-1"), _signal("world-2")])
    for proposal in queue.proposals:
        assert MemoryPromotionGate.HUMAN_REVIEW.value in proposal.required_gates
        assert MemoryPromotionGate.PROVENANCE_REVIEW.value in proposal.required_gates


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
