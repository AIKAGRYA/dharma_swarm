"""Candidate -> proposal / frontier task / BetCard bridges (authority-gated).

Makes routed candidates actionable WITHOUT bypassing existing gates:

- experiment/evolution claim -> Darwin pending proposal (reuses
  ``pending_proposals.append_pending_proposal``; metadata mirrors
  ``insight_evolution_bridge._candidate_to_proposal``).
- bounded implementation task -> ``frontier_tasks_pending.jsonl`` (reuses
  ``opportunity_refill._append_frontier_rows``).
- falsifiable improvement claim -> a ``BetCard`` that EXTENDS
  ``self_research.Hypothesis`` (the Verified Experiment Loop primitive) — no new
  standalone BetCard class.

Every emitted action carries ``dispatch_authority = False`` unless an explicit
owner gate grants it; generated code never flips it to True.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.opportunity_refill import _append_frontier_rows
from dharma_swarm.pending_proposals import append_pending_proposal
from dharma_swarm.self_research import Hypothesis

from .paths import idea_spark_root
from .schemas import IdeaSparkCandidate
from .store import append_candidate, update_lifecycle_receipt

_BAD_COMPONENT_CHARS = set('<>:"|?*')


@dataclass(slots=True)
class BetCard(Hypothesis):
    """A Verified Experiment Loop bet — extends Hypothesis (no new class).

    Falsifiable improvement claim with a correlation backlink and an explicit
    dispatch-authority flag (off by default).
    """

    correlation_id: str = ""
    candidate_id: str = ""
    bet_id: str = ""
    stake: str = ""
    verifier: str = "verified_experiment_loop"
    dispatch_authority: bool = False


@dataclass(frozen=True)
class ActionRoute:
    correlation_id: str
    candidate_id: str
    lane: str  # proposal | task | bet | none
    proposal_id: str = ""
    task_id: str = ""
    bet_id: str = ""
    dispatch_authority: bool = False
    reason: str = ""


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _safe_component(owner_surface: str) -> str:
    value = (owner_surface or "").strip()
    if not value or any(char in _BAD_COMPONENT_CHARS for char in value):
        return "dharma_swarm/idea_spark/__init__.py"
    return value


def _base_metadata(candidate: IdeaSparkCandidate, *, dispatch_authority: bool) -> dict[str, Any]:
    return {
        "source": "operator_idea_spark",
        "candidate_id": candidate.candidate_id,
        "correlation_id": candidate.correlation_id,
        "title": candidate.title,
        "domain": candidate.domain,
        "authority_level": candidate.authority_level,
        "owner_surface": candidate.owner_surface,
        "dispatch_authority": dispatch_authority,
        "triage_score": candidate.triage.get("triage_score") if candidate.triage else None,
        "source_refs": list(candidate.source_refs),
    }


def candidate_to_proposal_row(
    candidate: IdeaSparkCandidate,
    *,
    dispatch_authority: bool = False,
) -> dict[str, Any]:
    """Build a Darwin pending-proposal row (validates against evolution.Proposal)."""
    proposal_id = f"idea-spark-prop-{_hash(candidate.candidate_id, candidate.correlation_id)}"
    metadata = _base_metadata(candidate, dispatch_authority=dispatch_authority)
    metadata.update(
        {
            "apply_authority": "darwin_sandbox_only",
            "cross_test_status": "pending",
            "promotion_status": candidate.promotion_status,
        }
    )
    return {
        "id": proposal_id,
        "component": _safe_component(candidate.owner_surface),
        "change_type": "idea_spark_proposal",
        "description": f"{candidate.title}: {candidate.claim}"[:1000],
        "diff": "",
        "spec_ref": "docs/specs/OPERATOR_IDEA_SPARK_INGEST_LONGRUN_BUILD.md",
        "metadata": metadata,
    }


def emit_proposal(
    candidate: IdeaSparkCandidate,
    *,
    state_root: Path | None = None,
    proposals_path: Path | None = None,
    dispatch_authority: bool = False,
) -> dict[str, Any]:
    """Append a non-dispatching Darwin pending proposal for the candidate."""
    row = candidate_to_proposal_row(candidate, dispatch_authority=dispatch_authority)
    append_pending_proposal(row, path=proposals_path)
    update_lifecycle_receipt(
        candidate.correlation_id,
        state_root,
        candidate_id=candidate.candidate_id,
        proposal_id=row["id"],
        evidence_paths=[str(proposals_path)] if proposals_path else [],
    )
    return row


def candidate_to_frontier_row(
    candidate: IdeaSparkCandidate,
    *,
    dispatch_authority: bool = False,
    priority: str = "normal",
) -> dict[str, Any]:
    task_id = f"idea-spark-task-{_hash(candidate.candidate_id)}"
    metadata = _base_metadata(candidate, dispatch_authority=dispatch_authority)
    metadata["task_id"] = task_id
    return {
        "title": candidate.title or candidate.claim[:120],
        "description": candidate.claim,
        "priority": priority,
        "created_by": "idea_spark",
        "metadata": metadata,
    }


def emit_frontier_task(
    candidate: IdeaSparkCandidate,
    *,
    state_root: Path | None = None,
    frontier_path: Path | None = None,
    dispatch_authority: bool = False,
    priority: str = "normal",
) -> dict[str, Any]:
    """Append a bounded implementation task to frontier_tasks_pending.jsonl."""
    row = candidate_to_frontier_row(
        candidate, dispatch_authority=dispatch_authority, priority=priority
    )
    _append_frontier_rows([row], frontier_path=frontier_path)
    update_lifecycle_receipt(
        candidate.correlation_id,
        state_root,
        status="tasked",
        candidate_id=candidate.candidate_id,
        task_id=row["metadata"]["task_id"],
        evidence_paths=[str(frontier_path)] if frontier_path else [],
    )
    return row


def open_betcard(
    candidate: IdeaSparkCandidate,
    *,
    models: tuple[str, ...] = (),
    dispatch_authority: bool = False,
) -> BetCard:
    """Build a BetCard (Verified Experiment Loop) wrapping a Hypothesis."""
    bet_id = f"bet_{_hash(candidate.candidate_id)}"
    stake = str(candidate.triage.get("triage_score")) if candidate.triage else ""
    return BetCard(
        id=bet_id,
        question=candidate.title or candidate.claim[:160],
        rationale=candidate.why_now or candidate.claim,
        task_type="idea_spark_experiment",
        models=models,
        correlation_id=candidate.correlation_id,
        candidate_id=candidate.candidate_id,
        bet_id=bet_id,
        stake=stake,
        dispatch_authority=dispatch_authority,
    )


def emit_betcard(
    candidate: IdeaSparkCandidate,
    *,
    state_root: Path | None = None,
    models: tuple[str, ...] = (),
    dispatch_authority: bool = False,
) -> BetCard:
    """Open a BetCard and persist a receipt; link bet_id into the lifecycle."""
    bet = open_betcard(candidate, models=models, dispatch_authority=dispatch_authority)
    bet_dir = idea_spark_root(state_root) / "betcards"
    bet_dir.mkdir(parents=True, exist_ok=True)
    bet_path = bet_dir / f"{bet.bet_id}.json"
    payload = {"schema_version": "idea_spark_betcard.v0", **asdict(bet)}
    payload["models"] = list(bet.models)
    tmp = bet_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, bet_path)
    update_lifecycle_receipt(
        candidate.correlation_id,
        state_root,
        candidate_id=candidate.candidate_id,
        bet_id=bet.bet_id,
        evidence_paths=[str(bet_path)],
    )
    return bet


_LANE_FOR_AUTHORITY = {
    "proposal": "proposal",
    "task_candidate": "task",
    "experiment_candidate": "bet",
}


def route_action(
    candidate: IdeaSparkCandidate,
    *,
    state_root: Path | None = None,
    proposals_path: Path | None = None,
    frontier_path: Path | None = None,
    grant_authority: bool = False,
    persist_candidate: bool = True,
) -> ActionRoute:
    """Dispatch a routed candidate to the lane its authority_level implies.

    ``grant_authority`` is the only way to set dispatch_authority True and is an
    explicit owner gate; it defaults False.
    """
    lane = _LANE_FOR_AUTHORITY.get(candidate.authority_level, "none")
    proposal_id = task_id = bet_id = ""

    if lane == "proposal":
        row = emit_proposal(
            candidate,
            state_root=state_root,
            proposals_path=proposals_path,
            dispatch_authority=grant_authority,
        )
        proposal_id = row["id"]
        routing_status = "proposal_queued"
    elif lane == "task":
        row = emit_frontier_task(
            candidate,
            state_root=state_root,
            frontier_path=frontier_path,
            dispatch_authority=grant_authority,
        )
        task_id = row["metadata"]["task_id"]
        routing_status = "task_queued"
    elif lane == "bet":
        bet = emit_betcard(candidate, state_root=state_root, dispatch_authority=grant_authority)
        bet_id = bet.bet_id
        routing_status = "bet_opened"
    else:
        routing_status = candidate.routing_status
        reason = f"authority_level={candidate.authority_level} routes to no action lane"
        if persist_candidate:
            append_candidate(candidate.model_copy(update={"routing_status": routing_status}), state_root)
        return ActionRoute(
            correlation_id=candidate.correlation_id,
            candidate_id=candidate.candidate_id,
            lane="none",
            dispatch_authority=False,
            reason=reason,
        )

    if persist_candidate:
        append_candidate(candidate.model_copy(update={"routing_status": routing_status}), state_root)

    return ActionRoute(
        correlation_id=candidate.correlation_id,
        candidate_id=candidate.candidate_id,
        lane=lane,
        proposal_id=proposal_id,
        task_id=task_id,
        bet_id=bet_id,
        dispatch_authority=grant_authority,
        reason=f"routed to {lane} lane",
    )
