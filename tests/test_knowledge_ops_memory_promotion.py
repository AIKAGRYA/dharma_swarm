from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.knowledge_ops.cli import main as knowledge_ops_main
from dharma_swarm.knowledge_ops.memory_conflict_review import review_memory_conflicts
from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecision,
    MemoryPromotionDecisionKind,
    build_memory_decision_ledger,
)
from dharma_swarm.knowledge_ops.memory_intake import review_memory_atoms
from dharma_swarm.knowledge_ops.memory_promotion_executor import (
    append_memory_promotion_artifacts,
    execute_memory_promotion_dry_run,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import build_memory_promotion_queue
from dharma_swarm.memory_kernel import (
    AdapterMode,
    AuthorityLevel,
    MemoryAtom,
    MemoryAtomType,
    MemoryScope,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    TruthState,
    WriteMode,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _surface(
    *,
    surface_id: str = "fixture.runtime_state",
    category: SurfaceCategory = SurfaceCategory.RUNTIME_CONTROL,
    role: MemorySurfaceRole = MemorySurfaceRole.RUNTIME_STATE,
    authority_level: AuthorityLevel = AuthorityLevel.HIGH,
    projection_of: tuple[str, ...] = (),
    canon_risk: RiskLevel = RiskLevel.LOW,
    pii_risk: RiskLevel = RiskLevel.LOW,
) -> MemorySurface:
    return MemorySurface(
        surface_id=surface_id,
        path="/fixture/.dharma/state/runtime.db",
        owner_module="fixture",
        role=role,
        category=category,
        authority_level=authority_level,
        write_mode=WriteMode.READ_WRITE,
        adapter_mode=AdapterMode.READ_ONLY,
        active_status=SurfaceStatus.SNAPSHOT,
        health=MemorySurfaceHealth(exists=True),
        provenance_quality="fixture",
        canon_risk=canon_risk,
        pii_secrets_risk=pii_risk,
        latency_risk=RiskLevel.LOW,
        projection_of=projection_of,
    )


def _atom(
    *,
    surface: MemorySurface | None = None,
    atom_type: MemoryAtomType = MemoryAtomType.RUNTIME_EVENT,
    content_ref: str = "runtime_event:1",
    truth_state: TruthState = TruthState.OBSERVED,
    promotion_allowed: bool = True,
) -> MemoryAtom:
    resolved_surface = surface or _surface()
    return MemoryAtom.build(
        surface=resolved_surface,
        atom_type=atom_type,
        content_ref=content_ref,
        timestamp="2026-05-13T00:00:00Z",
        source_path=content_ref,
        adapter_name="fixture_knowledge_ops",
        read_mode=ReadMode.READ_ONLY,
        scope=MemoryScope.PROJECT,
        truth_state=truth_state,
        promotion_allowed=promotion_allowed,
    )


def _queue_for(*atoms: MemoryAtom):
    return build_memory_promotion_queue(
        review_memory_conflicts(review_memory_atoms(atoms))
    )


def _valid_accept(proposal, *, reviewer: str = "human") -> MemoryPromotionDecision:
    return MemoryPromotionDecision(
        proposal_id=proposal.proposal_id,
        atom_id=proposal.atom_id,
        surface_id=proposal.surface_id,
        decision=MemoryPromotionDecisionKind.ACCEPT,
        reviewer=reviewer,
        rationale="reviewed provenance, conflicts, privacy, and canon policy",
        approved_gates=proposal.required_gates,
    )


def test_promotion_dry_run_emits_request_receipt_and_appends_jsonl(tmp_path: Path) -> None:
    queue = _queue_for(_atom(content_ref="runtime_event:safe"))
    proposal = queue.proposals[0]
    decision = MemoryPromotionDecision(
        proposal_id=proposal.proposal_id,
        atom_id=proposal.atom_id,
        surface_id=proposal.surface_id,
        decision=MemoryPromotionDecisionKind.ACCEPT,
        reviewer="human /Users/dhyana/.dharma/operator.log",
        rationale="approved after SECRET_TOKEN=abc123 review at /private/tmp/raw.txt",
        approved_gates=proposal.required_gates,
    )
    ledger = build_memory_decision_ledger(queue, (decision,))

    result = execute_memory_promotion_dry_run(
        queue,
        ledger,
        target_authority_surface="knowledge_authority.shadow_canon",
    )

    assert result.request_count == 1
    assert result.receipt_count == 1
    request = result.requests[0]
    receipt = result.receipts[0]
    assert request.source_atom_ids == (proposal.atom_id,)
    assert request.target_authority_surface == "knowledge_authority.shadow_canon"
    assert request.idempotency_key.startswith("memory_promotion_idempotency:")
    assert request.rollback_metadata.tombstone_required is True
    assert request.tombstone_metadata.applies_to_request_id == request.request_id
    assert receipt.request_id == request.request_id
    assert receipt.mutation_performed is False

    request_path = tmp_path / "requests.jsonl"
    receipt_path = tmp_path / "receipts.jsonl"
    append_memory_promotion_artifacts(
        result,
        request_path=request_path,
        receipt_path=receipt_path,
    )
    append_memory_promotion_artifacts(
        result,
        request_path=request_path,
        receipt_path=receipt_path,
    )

    request_lines = request_path.read_text(encoding="utf-8").splitlines()
    receipt_lines = receipt_path.read_text(encoding="utf-8").splitlines()
    assert len(request_lines) == 2
    assert len(receipt_lines) == 2
    combined = "\n".join((*request_lines, *receipt_lines))
    assert "SECRET_TOKEN" not in combined
    assert "/Users/dhyana" not in combined
    assert "/private/tmp" not in combined


def test_promotion_dry_run_accepts_once_and_skips_reject_defer_invalid_duplicate() -> None:
    queue = _queue_for(_atom(content_ref="runtime_event:safe"))
    proposal = queue.proposals[0]
    valid_accept = _valid_accept(proposal)
    duplicate_accept = _valid_accept(proposal)
    invalid_accept = MemoryPromotionDecision(
        proposal_id=proposal.proposal_id,
        atom_id=proposal.atom_id,
        surface_id=proposal.surface_id,
        decision=MemoryPromotionDecisionKind.ACCEPT,
        reviewer="human",
        rationale="missing gates",
        approved_gates=("human_review",),
    )
    reject = MemoryPromotionDecision(
        proposal_id=proposal.proposal_id,
        atom_id=proposal.atom_id,
        surface_id=proposal.surface_id,
        decision=MemoryPromotionDecisionKind.REJECT,
        reviewer="human",
        rationale="not ready",
    )
    defer = MemoryPromotionDecision(
        proposal_id=proposal.proposal_id,
        atom_id=proposal.atom_id,
        surface_id=proposal.surface_id,
        decision=MemoryPromotionDecisionKind.DEFER,
        reviewer="human",
        rationale="needs review",
    )
    ledger = build_memory_decision_ledger(
        queue,
        (valid_accept, duplicate_accept, invalid_accept, reject, defer),
    )

    result = execute_memory_promotion_dry_run(
        queue,
        ledger,
        target_authority_surface="knowledge_authority.shadow_canon",
    )

    assert result.accepted_decision_count == 3
    assert result.request_count == 1
    assert result.receipt_count == 1
    assert result.duplicate_accept_count == 1
    assert result.skipped_decision_count == 4


def test_rejected_superseded_projection_and_high_risk_atoms_do_not_promote() -> None:
    rejected = _atom(content_ref="runtime_event:rejected", truth_state=TruthState.REJECTED)
    superseded = _atom(
        content_ref="runtime_event:superseded",
        truth_state=TruthState.SUPERSEDED,
    )
    high_risk = _atom(
        surface=_surface(surface_id="fixture.high_risk", canon_risk=RiskLevel.HIGH),
        content_ref="runtime_event:high-risk",
    )
    projection = _atom(
        surface=_surface(
            surface_id="fixture.projection",
            category=SurfaceCategory.PROJECTION,
            role=MemorySurfaceRole.PROJECTION_INDEX,
            authority_level=AuthorityLevel.LOW,
            projection_of=("fixture.runtime_state",),
        ),
        atom_type=MemoryAtomType.SOURCE_CHUNK,
        content_ref="source_chunk:projection",
        truth_state=TruthState.DERIVED,
    )

    evidence = review_memory_atoms((rejected, superseded, high_risk, projection))
    conflict = review_memory_conflicts(evidence)
    queue = build_memory_promotion_queue(conflict)
    ledger = build_memory_decision_ledger(queue, ())
    result = execute_memory_promotion_dry_run(
        queue,
        ledger,
        target_authority_surface="knowledge_authority.shadow_canon",
    )
    finding_kinds = {finding.kind for finding in conflict.findings}

    assert queue.promotion_proposal_count == 0
    assert result.request_count == 0
    assert result.receipt_count == 0
    assert "contested_atom" in finding_kinds
    assert "superseded_atom" in finding_kinds
    assert "high_canon_risk" in finding_kinds
    assert "projection_not_authority" in finding_kinds


def test_promotion_artifact_writer_rejects_memory_surface_paths(tmp_path: Path) -> None:
    queue = _queue_for(_atom(content_ref="runtime_event:safe"))
    ledger = build_memory_decision_ledger(queue, (_valid_accept(queue.proposals[0]),))
    result = execute_memory_promotion_dry_run(
        queue,
        ledger,
        target_authority_surface="knowledge_authority.shadow_canon",
    )
    memory_root = tmp_path / "home" / ".dharma"
    blocked_path = memory_root / "promotions.jsonl"

    with pytest.raises(ValueError, match="memory surfaces"):
        append_memory_promotion_artifacts(
            result,
            request_path=blocked_path,
            receipt_path=None,
            forbidden_roots=(memory_root,),
        )

    assert not blocked_path.exists()


def test_knowledge_ops_cli_rejects_promotion_artifacts_under_memory_surfaces(
    capsys,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    decisions = tmp_path / "decisions.json"
    out_jsonl = repo / ".dharma" / "promotion_requests.jsonl"
    _write(home / ".dharma/conversation_log/2026-05-13.jsonl", "{}\n")
    _write(decisions, json.dumps({"decisions": []}))

    assert (
        knowledge_ops_main(
            [
                "--repo-root",
                str(repo),
                "--memory-home",
                str(home),
                "--include-memory-kernel",
                "--memory-surface",
                "home.conversation_log",
                "--memory-decision-in",
                str(decisions),
                "--memory-promotion-target-surface",
                "knowledge_authority.shadow_canon",
                "--memory-promotion-request-out",
                str(out_jsonl),
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert "output paths under memory surfaces are not allowed" in payload["error"]
    assert not out_jsonl.exists()
