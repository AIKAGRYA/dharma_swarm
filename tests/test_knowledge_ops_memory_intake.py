from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.knowledge_ops.cli import main as knowledge_ops_main
from dharma_swarm.knowledge_ops.memory_conflict_review import review_memory_conflicts
from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecision,
    MemoryPromotionDecisionKind,
    build_memory_decision_ledger,
)
from dharma_swarm.knowledge_ops.memory_intake import (
    render_memory_evidence_review_markdown,
    review_memory_atoms,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    build_memory_promotion_queue,
)
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
    content: str | None = None,
    truth_state: TruthState = TruthState.OBSERVED,
    promotion_allowed: bool = False,
    context_admissible: bool = False,
) -> MemoryAtom:
    resolved_surface = surface or _surface()
    return MemoryAtom.build(
        surface=resolved_surface,
        atom_type=atom_type,
        content_ref=content_ref,
        content=content,
        timestamp="2026-05-13T00:00:00Z",
        source_path=content_ref,
        adapter_name="fixture_knowledge_ops",
        read_mode=ReadMode.READ_ONLY,
        scope=MemoryScope.PROJECT,
        truth_state=truth_state,
        promotion_allowed=promotion_allowed,
        context_admissible=context_admissible,
    )


def test_memory_atoms_project_to_evidence_without_content_or_raw_paths() -> None:
    synthetic_secret = "SECRET" + "_TOKEN=abc123"
    atom = _atom(
        content_ref="/Users/dhyana/.dharma/db/memory_plane.db",
        content=f"do not serialize me {synthetic_secret}",
    )

    review = review_memory_atoms((atom,))
    payload = json.dumps(review.to_json(), sort_keys=True)
    markdown = render_memory_evidence_review_markdown(review)

    assert review.total_atoms == 1
    assert review.evidence_node_count == 1
    assert review.derived_from_edge_count == 1
    assert review.content_bearing_count == 1
    assert review.snapshot.evidence_nodes[0].has_content is True
    assert "do not serialize me" not in payload
    assert synthetic_secret not in payload
    assert "/Users/dhyana" not in payload
    assert "/Users/dhyana" not in markdown
    assert "redacted_ref:" in payload


def test_conflict_review_blocks_projection_and_promotes_only_safe_candidate() -> None:
    safe_atom = _atom(
        content_ref="runtime_event:safe",
        promotion_allowed=True,
        truth_state=TruthState.OBSERVED,
    )
    projection_atom = _atom(
        surface=_surface(
            surface_id="fixture.vector_projection",
            category=SurfaceCategory.PROJECTION,
            role=MemorySurfaceRole.PROJECTION_INDEX,
            authority_level=AuthorityLevel.LOW,
            projection_of=("fixture.runtime_state",),
            canon_risk=RiskLevel.HIGH,
            pii_risk=RiskLevel.HIGH,
        ),
        atom_type=MemoryAtomType.SOURCE_CHUNK,
        content_ref="source_chunk:projection",
        truth_state=TruthState.DERIVED,
        promotion_allowed=True,
    )

    evidence_review = review_memory_atoms((safe_atom, projection_atom))
    conflict_review = review_memory_conflicts(evidence_review)
    queue = build_memory_promotion_queue(conflict_review)

    assert conflict_review.promotion_candidate_count == 1
    assert conflict_review.promotion_blocked_atom_count == 1
    assert conflict_review.promotion_blocker_count >= 1
    assert queue.promotion_proposal_count == 1
    assert len(queue.proposals) == 1
    assert queue.proposals[0].atom_id == safe_atom.atom_id


def test_decision_ledger_validates_accept_gate_completeness() -> None:
    safe_atom = _atom(
        content_ref="runtime_event:safe",
        promotion_allowed=True,
        truth_state=TruthState.OBSERVED,
    )
    conflict_review = review_memory_conflicts(review_memory_atoms((safe_atom,)))
    queue = build_memory_promotion_queue(conflict_review)
    proposal = queue.proposals[0]
    valid_decision = MemoryPromotionDecision(
        proposal_id=proposal.proposal_id,
        atom_id=proposal.atom_id,
        surface_id=proposal.surface_id,
        decision=MemoryPromotionDecisionKind.ACCEPT,
        reviewer="human",
        rationale="reviewed provenance and conflict state",
        approved_gates=proposal.required_gates,
    )
    invalid_decision = MemoryPromotionDecision(
        proposal_id=proposal.proposal_id,
        atom_id=proposal.atom_id,
        surface_id=proposal.surface_id,
        decision=MemoryPromotionDecisionKind.ACCEPT,
        reviewer="human",
        rationale="missing gates",
        approved_gates=("human_review",),
    )

    ledger = build_memory_decision_ledger(queue, (valid_decision, invalid_decision))

    assert ledger.valid_decision_count == 1
    assert ledger.invalid_decision_count == 1
    assert ledger.accept_count == 1
    assert any("missing_required_gates" in ",".join(review.errors) for review in ledger.reviews)


def test_knowledge_ops_cli_requires_explicit_home_and_surface(capsys) -> None:
    assert knowledge_ops_main(["--include-memory-kernel"]) == 2

    payload = json.loads(capsys.readouterr().out)

    assert "--include-memory-kernel requires explicit --memory-home" in payload["error"]


def test_knowledge_ops_cli_writes_redacted_read_only_reports(capsys, tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    out_json = tmp_path / "memory_review.json"
    out_md = tmp_path / "memory_review.md"
    _write(home / ".dharma/conversation_log/2026-05-13.jsonl", '{"content": "hidden"}\n')

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
                "--memory-review-out",
                str(out_json),
                "--memory-review-md-out",
                str(out_md),
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    payload_text = out_json.read_text(encoding="utf-8")
    markdown = out_md.read_text(encoding="utf-8")
    payload = json.loads(stdout)

    assert payload["memory_review"]["total_atoms"] == 1
    for text in (stdout, payload_text, markdown):
        assert str(home) not in text
        assert "hidden" not in text
    assert "# MemoryKernel KnowledgeOps Evidence Review" in markdown


def test_knowledge_ops_cli_rejects_memory_surface_outputs(capsys, tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    out_json = repo / ".dharma" / "memory_review.json"
    _write(home / ".dharma/conversation_log/2026-05-13.jsonl", "{}\n")

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
                "--memory-review-out",
                str(out_json),
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert "output paths under memory surfaces are not allowed" in payload["error"]
    assert not out_json.exists()
