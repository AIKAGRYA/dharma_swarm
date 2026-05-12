from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.knowledge_ops.cli import main
from dharma_swarm.knowledge_ops.extractor import ExtractorConfig, KnowledgeOpsExtractor
from dharma_swarm.knowledge_ops.memory_conflict_review import (
    render_memory_conflict_review_markdown,
    review_memory_conflicts,
)
from dharma_swarm.knowledge_ops.memory_intake import (
    MemoryKernelIntake,
    MemoryKernelIntakeConfig,
    memory_atoms_to_snapshot,
    render_memory_evidence_review_markdown,
    review_memory_atoms,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    build_memory_promotion_queue,
    render_memory_promotion_queue_markdown,
)
from dharma_swarm.knowledge_ops.projections import (
    default_mode_schedule,
    render_agent_context_bundle,
    render_concept_card,
)
from dharma_swarm.knowledge_ops.schema import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeOpsMode,
    LifecycleStatus,
    NodeKind,
)
from dharma_swarm.memory_kernel import MemoryAtom, MemoryAtomType, ReadMode, TruthState
from dharma_swarm.memory_kernel.census import CensusConfig, MemorySurfaceCensus


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    wiki = tmp_path / "wiki"
    _write(repo / "CLAUDE.md", "# CLAUDE\n\nBehavioral guardrails.\n")
    _write(
        repo / "docs/MEGAFILE_INDEX.md",
        "# MEGAFILE INDEX\n\n"
        "### Slot 1 — Vision Synthesis\n"
        "See `dharma_swarm/context_compiler.py`.\n",
    )
    _write(
        repo / "docs/governance/CANONICAL_DOC_STACK.md",
        "# CANONICAL DOC STACK\n\nsource of truth for docs.\n",
    )
    _write(
        repo / "docs/governance/SOVEREIGN_MANIFEST.md",
        "# SOVEREIGN MANIFEST\n\ncanonical architecture truth.\n",
    )
    _write(repo / "docs/governance/BUILD_SESSION_ENTRYPOINT.md", "# Build\n")
    _write(repo / "docs/governance/REPO_GOVERNANCE_AUDIT.md", "# Audit\n")
    _write(repo / "docs/architecture/NAVIGATION.md", "# Navigation\n")
    _write(repo / "docs/architecture/WIRING_AND_LOOPS.md", "# Wiring\n")
    _write(repo / "docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md", "# Memory\n")
    _write(
        repo / "docs/state/BROKEN_REGISTER.md",
        "# Broken Register\n\n- BR-001 Cron split-brain.\n- BR-002 Loop open.\n",
    )
    _write(repo / "docs/state/LIVE_OPS_DASHBOARD.md", "# Live Ops\n")
    _write(
        repo / "reports/system_map/latest.json",
        json.dumps({"organs": [{"name": "central_loop", "coherence_state": "partial"}]}),
    )
    _write(repo / "dharma_swarm/context_compiler.py", '"""Context compiler."""\n')
    _write(repo / "dharma_swarm/ontology.py", '"""Ontology."""\n')
    _write(
        wiki / "concepts/recognition-closure.md",
        "---\nstatus: trusted\n---\n# Recognition Closure\n\nLinks [[central-loop]].\n",
    )
    return repo, wiki


def test_stable_node_ids_are_deterministic() -> None:
    a = KnowledgeNode.build(NodeKind.CONCEPT, "Recognition Closure", id_parts=["x"])
    b = KnowledgeNode.build(NodeKind.CONCEPT, "Recognition Closure", id_parts=["x"])
    c = KnowledgeNode.build(NodeKind.CONCEPT, "Recognition Closure", id_parts=["y"])

    assert a.node_id == b.node_id
    assert a.node_id != c.node_id


def test_extractor_builds_docs_concepts_broken_items_and_runtime_facts(tmp_path: Path) -> None:
    repo, wiki = _fixture_repo(tmp_path)

    snapshot = KnowledgeOpsExtractor(
        ExtractorConfig(repo_root=repo, wiki_root=wiki, wiki_limit=10)
    ).extract()

    counts = snapshot.node_count_by_kind()
    assert counts["doc"] >= 10
    assert counts["concept"] >= 2
    assert counts["broken_register_item"] == 2
    assert counts["runtime_fact"] == 1
    assert counts["code_surface"] >= 1
    assert snapshot.edge_count_by_kind()["extracts_concept"] >= 1
    assert snapshot.edge_count_by_kind()["tracks_brokenness_of"] == 2
    assert any(edge.kind == EdgeKind.REFERENCES for edge in snapshot.edges)


def test_snapshot_write_jsonl_is_machine_readable(tmp_path: Path) -> None:
    repo, wiki = _fixture_repo(tmp_path)
    snapshot = KnowledgeOpsExtractor(ExtractorConfig(repo_root=repo, wiki_root=wiki)).extract()
    out = tmp_path / "out"

    snapshot.write_jsonl(out)

    nodes = [json.loads(line) for line in (out / "nodes.jsonl").read_text().splitlines()]
    edges = [json.loads(line) for line in (out / "edges.jsonl").read_text().splitlines()]
    summary = json.loads((out / "summary.json").read_text())
    assert len(nodes) == summary["node_count"]
    assert len(edges) == summary["edge_count"]


def test_concept_card_preserves_provenance_and_boundaries() -> None:
    node = KnowledgeNode.build(
        NodeKind.CONCEPT,
        "Dream Mode",
        id_parts=["dream"],
        status=LifecycleStatus.STAGED,
    )
    edge = KnowledgeEdge.build(EdgeKind.SYNTHESIZES, node.node_id, "other")

    card = render_concept_card(node, related_edges=(edge,))

    assert "# Dream Mode" in card
    assert "Do not treat staged or candidate cards as doctrine" in card
    assert "synthesizes" in card


def test_agent_context_bundle_is_projection_not_authority() -> None:
    node = KnowledgeNode.build(NodeKind.DOC, "Sovereign Manifest", id_parts=["manifest"])

    bundle = render_agent_context_bundle(
        bundle_id="test",
        role="reviewer",
        objective="Audit KnowledgeOps",
        nodes=(node,),
        edges=(),
    )

    assert "This bundle is a projection" in bundle
    assert "Audit KnowledgeOps" in bundle
    assert "Do not create new authority docs" in bundle


def test_mode_schedule_keeps_dream_candidate_only_and_promotion_reviewed() -> None:
    schedule = default_mode_schedule()
    modes = {item["mode"]: item for item in schedule}

    assert KnowledgeOpsMode.DREAM.value in modes
    assert modes[KnowledgeOpsMode.DREAM.value]["outputs"] == ["synthesis_candidates"]
    assert modes[KnowledgeOpsMode.DREAM.value]["may_mutate_authority"] is False
    assert modes[KnowledgeOpsMode.PROMOTION.value]["requires_human_review"] is True
    assert modes[KnowledgeOpsMode.FORGETTING.value]["requires_human_review"] is True


def test_cli_dry_run_and_report_generation(tmp_path: Path, capsys) -> None:
    repo, wiki = _fixture_repo(tmp_path)
    out = tmp_path / "reports"

    assert main(["--repo-root", str(repo), "--wiki-root", str(wiki), "--dry-run"]) == 0
    dry_output = capsys.readouterr().out
    assert "node_count" in dry_output

    assert main(["--repo-root", str(repo), "--wiki-root", str(wiki), "--output-dir", str(out)]) == 0
    assert (out / "nodes.jsonl").exists()
    assert (out / "edges.jsonl").exists()
    assert (out / "mode_schedule.json").exists()
    assert (out / "sample_concept_card.md").exists()
    assert (out / "sample_agent_context_bundle.md").exists()


def test_memory_kernel_atoms_enter_knowledge_ops_as_staged_evidence(tmp_path: Path) -> None:
    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=tmp_path / "repo", home=tmp_path / "home")
        ).run()
    }
    atom = MemoryAtom.build(
        surface=surfaces["home.memory_plane"],
        atom_type=MemoryAtomType.FACT,
        content_ref="memory_facts/1",
        adapter_name="test_adapter",
        read_mode=ReadMode.IMMUTABLE_SNAPSHOT,
        truth_state=TruthState.CLAIMED,
        metadata={"redaction_status": "content_omitted"},
    )

    snapshot = memory_atoms_to_snapshot((atom,))
    atom_node = next(
        node
        for node in snapshot.nodes
        if node.metadata.get("memory_atom_id") == atom.atom_id
    )

    assert atom_node.kind is NodeKind.RUNTIME_FACT
    assert atom_node.status is LifecycleStatus.STAGED
    assert atom_node.authority_tier == "medium"
    assert atom_node.metadata["truth_state"] == "claimed"
    assert atom_node.metadata["promotion_allowed"] is False
    assert atom_node.metadata["context_admissible"] is False
    assert atom_node.metadata["has_content"] is False
    assert "content" not in atom_node.metadata
    assert any(edge.kind is EdgeKind.DERIVED_FROM for edge in snapshot.edges)


def test_memory_evidence_review_counts_risk_without_leaking_content(tmp_path: Path) -> None:
    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=tmp_path / "repo", home=tmp_path / "home")
        ).run()
    }
    atom = MemoryAtom.build(
        surface=surfaces["home.conversation_log"],
        atom_type=MemoryAtomType.EPISODE,
        content_ref="conversation/1",
        content="private raw transcript",
        adapter_name="test_adapter",
        read_mode=ReadMode.METADATA_ONLY,
        metadata={"redaction_status": "redacted"},
    )

    snapshot = memory_atoms_to_snapshot((atom,))
    review = review_memory_atoms((atom,), snapshot=snapshot)
    markdown = render_memory_evidence_review_markdown(review)

    assert review.total_atoms == 1
    assert review.content_bearing_count == 1
    assert review.redacted_count == 1
    assert review.by_canon_risk["high"] == 1
    assert review.by_pii_risk["high"] == 1
    assert review.sample_evidence[0]["has_content"] is True
    assert "private raw transcript" not in json.dumps(review.to_json())
    assert "private raw transcript" not in markdown
    assert "high or critical canon risk" in " ".join(review.warnings)


def test_memory_conflict_review_detects_conflicts_without_leaking_content(
    tmp_path: Path,
) -> None:
    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=tmp_path / "repo", home=tmp_path / "home")
        ).run()
    }
    private_text = "private contradiction payload"
    claimed = MemoryAtom.build(
        surface=surfaces["home.memory_plane"],
        atom_type=MemoryAtomType.FACT,
        content_ref="shared/fact/1",
        content=private_text,
        adapter_name="test_adapter",
        read_mode=ReadMode.IMMUTABLE_SNAPSHOT,
        truth_state=TruthState.CLAIMED,
    )
    observed = MemoryAtom.build(
        surface=surfaces["home.runtime_state"],
        atom_type=MemoryAtomType.FACT,
        content_ref="shared/fact/1",
        adapter_name="test_adapter",
        read_mode=ReadMode.READ_ONLY,
        truth_state=TruthState.OBSERVED,
    )

    review = review_memory_conflicts((claimed, observed), finding_limit=1)
    markdown = render_memory_conflict_review_markdown(review)
    payload = json.dumps(review.to_json())

    assert review.finding_truncated is True
    assert review.conflict_candidate_count == 2
    assert review.by_finding_kind["truth_state_conflict_candidate"] == 1
    assert review.by_finding_kind["authority_conflict_candidate"] == 1
    assert review.by_finding_kind["content_present"] == 1
    assert "private" not in payload
    assert "private" not in markdown
    assert "structural conflict candidates" in " ".join(review.warnings)


def test_memory_conflict_review_separates_candidates_from_blockers(
    tmp_path: Path,
) -> None:
    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=tmp_path / "repo", home=tmp_path / "home")
        ).run()
    }
    candidate = MemoryAtom.build(
        surface=surfaces["home.runtime_state"],
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="runtime/session/1",
        adapter_name="test_adapter",
        read_mode=ReadMode.READ_ONLY,
        truth_state=TruthState.OBSERVED,
        promotion_allowed=True,
    )
    blocked = MemoryAtom.build(
        surface=surfaces["home.vectors"],
        atom_type=MemoryAtomType.SOURCE_CHUNK,
        content_ref="vectors/private/1",
        content="private vector payload",
        adapter_name="test_adapter",
        read_mode=ReadMode.METADATA_ONLY,
        promotion_allowed=True,
    )

    review = review_memory_conflicts((candidate, blocked))
    markdown = render_memory_conflict_review_markdown(review)

    assert review.promotion_candidate_count == 1
    assert review.promotion_candidates[0].atom_id == candidate.atom_id
    assert review.promotion_blocked_atom_count == 1
    assert review.promotion_blockers_by_reason["projection_atom"] == 1
    assert review.promotion_blockers_by_reason["high_canon_risk"] == 1
    assert review.promotion_blockers_by_reason["content_present"] == 1
    assert "private" not in json.dumps(review.to_json())
    assert "private" not in markdown


def test_memory_promotion_queue_is_read_only_gated_and_redacted(
    tmp_path: Path,
) -> None:
    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=tmp_path / "repo", home=tmp_path / "home")
        ).run()
    }
    candidate = MemoryAtom.build(
        surface=surfaces["home.runtime_state"],
        atom_type=MemoryAtomType.RUNTIME_EVENT,
        content_ref="/private/runtime/session/1",
        adapter_name="test_adapter",
        read_mode=ReadMode.READ_ONLY,
        truth_state=TruthState.OBSERVED,
        promotion_allowed=True,
    )
    blocked = MemoryAtom.build(
        surface=surfaces["home.conversation_log"],
        atom_type=MemoryAtomType.EPISODE,
        content_ref="/private/conversation/1",
        content="private promotion payload",
        adapter_name="test_adapter",
        read_mode=ReadMode.METADATA_ONLY,
        promotion_allowed=True,
    )

    queue = build_memory_promotion_queue((candidate, blocked))
    markdown = render_memory_promotion_queue_markdown(queue)
    payload = json.dumps(queue.to_json())

    assert queue.proposal_count == 1
    assert queue.displayed_proposal_count == 1
    assert queue.blocked_atom_count == 1
    assert queue.proposals[0].atom_id == candidate.atom_id
    assert queue.proposals[0].status.value == "ready_for_review"
    assert "human_review" in queue.required_gates_by_gate
    assert "canon_policy_review" in queue.required_gates_by_gate
    assert queue.blockers_by_reason["high_canon_risk"] == 1
    assert queue.blockers_by_reason["content_present"] == 1
    assert "private" not in payload
    assert "/private" not in payload
    assert "private" not in markdown
    assert "/private" not in markdown
    assert "does not promote" in markdown


def test_memory_kernel_intake_applies_query_budget_and_surface_filter(tmp_path: Path) -> None:
    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=tmp_path / "repo", home=tmp_path / "home")
        ).run()
    }
    atom = MemoryAtom.build(
        surface=surfaces["home.witness"],
        atom_type=MemoryAtomType.WITNESS_EVENT,
        content_ref="witness/1",
        adapter_name="test_adapter",
        read_mode=ReadMode.STREAMING,
    )

    class FakeKernel:
        def __init__(self) -> None:
            self.surface_ids = None
            self.query = None

        def iter_memory_atoms(self, *, surface_ids=None, query=None):
            self.surface_ids = surface_ids
            self.query = query
            return iter((atom,))

    fake_kernel = FakeKernel()
    snapshot = MemoryKernelIntake(
        fake_kernel,
        MemoryKernelIntakeConfig(
            surface_ids=("home.witness",),
            limit_total=1,
            limit_per_surface=1,
        ),
    ).extract()

    assert fake_kernel.surface_ids == ("home.witness",)
    assert fake_kernel.query.limit_total == 1
    assert fake_kernel.query.limit_per_surface == 1
    assert snapshot.node_count_by_kind()["evidence"] >= 1


def test_cli_writes_memory_evidence_review_reports(tmp_path: Path, capsys) -> None:
    repo, wiki = _fixture_repo(tmp_path)
    home = tmp_path / "home"
    _write(home / ".dharma/conversation_log/2026-05-12.jsonl", '{"message": "private"}\n')
    out = tmp_path / "reports"
    review_json = tmp_path / "memory_review.json"
    review_md = tmp_path / "memory_review.md"
    conflict_json = tmp_path / "memory_conflict_review.json"
    conflict_md = tmp_path / "memory_conflict_review.md"
    queue_json = tmp_path / "memory_promotion_queue.json"
    queue_md = tmp_path / "memory_promotion_queue.md"

    assert (
        main(
            [
                "--repo-root",
                str(repo),
                "--wiki-root",
                str(wiki),
                "--output-dir",
                str(out),
                "--include-memory-kernel",
                "--memory-home",
                str(home),
                "--memory-surface",
                "home.conversation_log",
                "--memory-limit-total",
                "5",
                "--memory-limit-per-surface",
                "5",
                "--memory-review-out",
                str(review_json),
                "--memory-review-md-out",
                str(review_md),
                "--memory-conflict-review-out",
                str(conflict_json),
                "--memory-conflict-review-md-out",
                str(conflict_md),
                "--memory-promotion-queue-out",
                str(queue_json),
                "--memory-promotion-queue-md-out",
                str(queue_md),
            ]
        )
        == 0
    )
    cli_output = capsys.readouterr().out
    payload = json.loads(review_json.read_text(encoding="utf-8"))
    markdown = review_md.read_text(encoding="utf-8")
    conflict_payload = json.loads(conflict_json.read_text(encoding="utf-8"))
    conflict_markdown = conflict_md.read_text(encoding="utf-8")
    queue_payload = json.loads(queue_json.read_text(encoding="utf-8"))
    queue_markdown = queue_md.read_text(encoding="utf-8")

    assert "memory_review" in cli_output
    assert "memory_conflict_review" in cli_output
    assert "memory_promotion_queue" in cli_output
    assert payload["total_atoms"] >= 1
    assert payload["query"]["surface_ids"] == ["home.conversation_log"]
    assert conflict_payload["total_atoms"] >= 1
    assert "promotion_blockers_by_reason" in conflict_payload
    assert queue_payload["total_atoms"] >= 1
    assert "blockers_by_reason" in queue_payload
    assert "MemoryKernel Evidence Review" in markdown
    assert "MemoryKernel Conflict Projection Review" in conflict_markdown
    assert "MemoryKernel Promotion Proposal Queue" in queue_markdown
    assert "private" not in json.dumps(payload)
    assert "/private" not in json.dumps(payload)
    assert "private" not in json.dumps(conflict_payload)
    assert "/private" not in json.dumps(conflict_payload)
    assert "private" not in json.dumps(queue_payload)
    assert "/private" not in json.dumps(queue_payload)
    assert "private" not in markdown
    assert "/private" not in markdown
    assert "private" not in conflict_markdown
    assert "/private" not in conflict_markdown
    assert "private" not in queue_markdown
    assert "/private" not in queue_markdown
