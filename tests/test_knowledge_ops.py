from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.knowledge_ops.cli import main
from dharma_swarm.knowledge_ops.extractor import ExtractorConfig, KnowledgeOpsExtractor
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
