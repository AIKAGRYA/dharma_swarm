"""PR 2 verifier — normalize all source lanes into idea_spark_candidate.v0.

Deterministic, no-network. Proves operator receipts, conversation idea shards,
and world-radar movements/rows all project into one candidate object that embeds
the existing idea_spark_triage.v0 tuple, and that candidates are idempotent by
candidate_id.
"""

from __future__ import annotations

from dharma_swarm.idea_spark.fixtures import NOTE_FIXTURE
from dharma_swarm.idea_spark.projection import (
    candidate_from_idea_shard,
    candidate_from_operator_receipt,
    candidate_from_world_movement,
    candidates_from_world_rows,
)
from dharma_swarm.idea_spark.schemas import IdeaSparkCandidate
from dharma_swarm.idea_spark.store import append_candidate, load_candidates
from dharma_swarm.world_radar.analysis import build_world_signal_board

FIXED_NOW = "2026-06-26T00:00:00Z"


def test_operator_receipt_projects_and_embeds_triage() -> None:
    receipt = NOTE_FIXTURE.build_receipt()
    candidate = candidate_from_operator_receipt(
        receipt, claim=NOTE_FIXTURE.content, domain="tooling", now=FIXED_NOW
    )
    assert candidate.schema_version == "idea_spark_candidate.v0"
    assert candidate.correlation_id == receipt.correlation_id
    assert candidate.triage.get("schema_version") == "idea_spark_triage.v0"
    assert set(candidate.triage) >= {
        "decision",
        "novelty",
        "telos_fit",
        "tractability",
        "source_confidence",
        "triage_score",
    }
    assert candidate.promotion_status in {
        "rejected",
        "watchlist",
        "incubating",
        "promotion_ready",
    }
    # source receipt id preserved for the lifecycle backlink.
    assert receipt.input_id in candidate.source_refs


def test_candidate_id_is_idempotent() -> None:
    receipt = NOTE_FIXTURE.build_receipt()
    a = candidate_from_operator_receipt(receipt, claim=NOTE_FIXTURE.content, now=FIXED_NOW)
    b = candidate_from_operator_receipt(receipt, claim=NOTE_FIXTURE.content, now=FIXED_NOW)
    assert a.candidate_id == b.candidate_id
    # Whitespace/case-different claim text normalizes to the same id.
    c = candidate_from_operator_receipt(
        receipt, claim="  " + NOTE_FIXTURE.content.upper() + "  ", now=FIXED_NOW
    )
    assert c.candidate_id == a.candidate_id


def test_reject_keyword_yields_rejected_status() -> None:
    receipt = NOTE_FIXTURE.build_receipt()
    candidate = candidate_from_operator_receipt(
        receipt,
        claim="Spam casino gambling scam promo malware phishing pitch.",
        now=FIXED_NOW,
    )
    assert candidate.triage.get("decision") == "reject"
    assert candidate.promotion_status == "rejected"
    assert candidate.authority_level == "observation"


def test_idea_shard_projection_preserves_shard_id() -> None:
    shard = {
        "shard_id": "shd_abc123",
        "turn_id": "turn_xyz",
        "session_id": "sess_1",
        "task_id": "task_9",
        "shard_kind": "proposal",
        "text": "Prototype a deterministic agent runtime memory tool for governed retrieval.",
        "salience": 0.8,
        "novelty": 0.6,
    }
    candidate = candidate_from_idea_shard(shard, now=FIXED_NOW)
    assert "shd_abc123" in candidate.source_refs
    assert candidate.domain == "conversation"
    # proposal-kind shard becomes a task candidate authority.
    assert candidate.authority_level == "task_candidate"
    assert candidate.triage.get("schema_version") == "idea_spark_triage.v0"


def test_world_movement_reuses_embedded_triage_without_drift() -> None:
    rows = [
        {
            "id": "sig-1",
            "source": "github",
            "category": "tool_release",
            "title": "Open-source agent runtime benchmark released",
            "description": "New agentic runtime tool with public github repo and evaluation benchmark.",
            "relevance_score": 0.8,
            "keywords": ["agent", "runtime", "benchmark"],
            "url": "https://github.com/example/agent-runtime",
            "metadata": {"movement_key": "agent-runtime"},
        }
    ]
    board = build_world_signal_board(rows, now=FIXED_NOW)
    movement = board["movements"][0]
    candidate = candidate_from_world_movement(movement, now=FIXED_NOW)
    # The candidate embeds the SAME triage dict the board produced (no re-score).
    assert candidate.triage == movement["triage"]
    assert candidate.domain == movement["category"]


def test_candidates_from_world_rows() -> None:
    rows = [
        {
            "id": "sig-2",
            "source": "arxiv",
            "category": "research",
            "title": "Agent memory governance paper",
            "description": "Research on governed memory runtime for agents with open benchmark.",
            "relevance_score": 0.75,
            "keywords": ["memory", "governance", "research"],
            "url": "https://arxiv.org/abs/0000.0000",
            "metadata": {"movement_key": "agent-memory-paper"},
        }
    ]
    candidates = candidates_from_world_rows(rows, now=FIXED_NOW)
    assert len(candidates) == 1
    assert all(isinstance(c, IdeaSparkCandidate) for c in candidates)
    assert candidates[0].triage.get("schema_version") == "idea_spark_triage.v0"


def test_append_and_load_candidates_dedupes_by_id(tmp_path) -> None:
    receipt = NOTE_FIXTURE.build_receipt()
    candidate = candidate_from_operator_receipt(receipt, claim=NOTE_FIXTURE.content, now=FIXED_NOW)
    append_candidate(candidate, tmp_path)
    # Re-project + append the same candidate (latest-wins dedupe).
    updated = candidate.model_copy(update={"routing_status": "routed"})
    append_candidate(updated, tmp_path)
    loaded = load_candidates(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].candidate_id == candidate.candidate_id
    assert loaded[0].routing_status == "routed"
