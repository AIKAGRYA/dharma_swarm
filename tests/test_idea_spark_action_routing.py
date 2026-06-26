"""PR 6 verifier — candidate -> proposal / frontier task / BetCard bridges.

Deterministic, no-network. Proves routed candidates become actionable through
existing owners with dispatch_authority off by default, the proposal row is a
valid evolution.Proposal, and BetCard extends Hypothesis (no new class).
"""

from __future__ import annotations

import json

from dharma_swarm.evolution import Proposal
from dharma_swarm.idea_spark.action_routing import (
    BetCard,
    candidate_to_proposal_row,
    emit_betcard,
    emit_frontier_task,
    emit_proposal,
    route_action,
)
from dharma_swarm.idea_spark.fixtures import NOTE_FIXTURE
from dharma_swarm.idea_spark.projection import candidate_from_operator_receipt
from dharma_swarm.idea_spark.store import load_lifecycle_receipt
from dharma_swarm.self_research import Hypothesis

FIXED_NOW = "2026-06-26T00:00:00Z"


def _candidate(authority_level="proposal", owner_surface="dharma_swarm/idea_spark/"):
    receipt = NOTE_FIXTURE.build_receipt()
    candidate = candidate_from_operator_receipt(
        receipt, claim=NOTE_FIXTURE.content, domain="tooling", now=FIXED_NOW
    )
    return candidate.model_copy(
        update={"authority_level": authority_level, "owner_surface": owner_surface}
    )


def test_betcard_extends_hypothesis_no_new_class() -> None:
    assert issubclass(BetCard, Hypothesis)
    bet = BetCard(id="b1", question="q", rationale="r")
    assert isinstance(bet, Hypothesis)
    assert bet.dispatch_authority is False


def test_proposal_row_is_valid_evolution_proposal() -> None:
    candidate = _candidate("proposal")
    row = candidate_to_proposal_row(candidate)
    # Must rehydrate as an evolution.Proposal without error.
    proposal = Proposal(**row)
    assert proposal.component == "dharma_swarm/idea_spark/"
    assert row["metadata"]["dispatch_authority"] is False
    assert row["metadata"]["apply_authority"] == "darwin_sandbox_only"
    assert row["metadata"]["correlation_id"] == candidate.correlation_id


def test_emit_proposal_appends_and_links_lifecycle(tmp_path) -> None:
    candidate = _candidate("proposal")
    proposals_path = tmp_path / "evolution" / "pending_proposals.jsonl"
    row = emit_proposal(candidate, state_root=tmp_path, proposals_path=proposals_path)
    assert proposals_path.exists()
    written = [json.loads(line) for line in proposals_path.read_text().splitlines() if line.strip()]
    assert written[0]["id"] == row["id"]
    lifecycle = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert lifecycle is not None and lifecycle.proposal_id == row["id"]


def test_emit_frontier_task_appends_and_links_lifecycle(tmp_path) -> None:
    candidate = _candidate("task_candidate")
    frontier_path = tmp_path / "meta" / "frontier_tasks_pending.jsonl"
    row = emit_frontier_task(candidate, state_root=tmp_path, frontier_path=frontier_path)
    assert frontier_path.exists()
    written = [json.loads(line) for line in frontier_path.read_text().splitlines() if line.strip()]
    assert written[0]["created_by"] == "idea_spark"
    assert written[0]["metadata"]["dispatch_authority"] is False
    lifecycle = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert lifecycle is not None
    assert lifecycle.task_id == row["metadata"]["task_id"]
    assert lifecycle.status == "tasked"


def test_emit_betcard_persists_receipt_and_links_lifecycle(tmp_path) -> None:
    candidate = _candidate("experiment_candidate")
    bet = emit_betcard(candidate, state_root=tmp_path)
    assert isinstance(bet, Hypothesis)
    assert bet.dispatch_authority is False
    assert bet.correlation_id == candidate.correlation_id
    bet_path = tmp_path / "meta" / "idea_spark" / "betcards" / f"{bet.bet_id}.json"
    assert bet_path.exists()
    payload = json.loads(bet_path.read_text())
    assert payload["schema_version"] == "idea_spark_betcard.v0"
    lifecycle = load_lifecycle_receipt(candidate.correlation_id, tmp_path)
    assert lifecycle is not None and lifecycle.bet_id == bet.bet_id


def test_route_action_dispatches_by_authority_level(tmp_path) -> None:
    proposals_path = tmp_path / "evolution" / "pending_proposals.jsonl"
    frontier_path = tmp_path / "meta" / "frontier_tasks_pending.jsonl"

    prop = route_action(
        _candidate("proposal"), state_root=tmp_path, proposals_path=proposals_path
    )
    assert prop.lane == "proposal" and prop.proposal_id and prop.dispatch_authority is False

    task = route_action(
        _candidate("task_candidate"), state_root=tmp_path, frontier_path=frontier_path
    )
    assert task.lane == "task" and task.task_id

    bet = route_action(_candidate("experiment_candidate"), state_root=tmp_path)
    assert bet.lane == "bet" and bet.bet_id

    none = route_action(_candidate("observation"), state_root=tmp_path)
    assert none.lane == "none" and none.dispatch_authority is False


def test_grant_authority_is_explicit_and_off_by_default(tmp_path) -> None:
    proposals_path = tmp_path / "evolution" / "pending_proposals.jsonl"
    # Default: authority off.
    default_row = emit_proposal(
        _candidate("proposal"), state_root=tmp_path, proposals_path=proposals_path
    )
    assert default_row["metadata"]["dispatch_authority"] is False
    # Explicit grant flips it (operator gate only).
    granted = route_action(
        _candidate("proposal"),
        state_root=tmp_path,
        proposals_path=proposals_path,
        grant_authority=True,
    )
    assert granted.dispatch_authority is True
