"""Semantic knowledge and RAG commands."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    DHARMA_SWARM,
    _run,
)

# Restored after being lost in the dgc_cli → terminal_commands extraction
# (8a5a8cd52); original definition recovered from d7af817ac.
_DEFAULT_GRAPH_PATH = DHARMA_STATE / "semantic" / "concept_graph.json"


def _resolve_graph_path(graph_path: str | None) -> Path:
    return Path(graph_path) if graph_path else _DEFAULT_GRAPH_PATH


def cmd_semantic_digest(
    *,
    root: str,
    output: str | None = None,
    include_tests: bool = False,
    max_files: int = 500,
) -> None:
    """Phase 1: Read codebase files and build the ConceptGraph."""
    from dharma_swarm.semantic_digester import SemanticDigester

    root_path = Path(root)
    out_path = Path(output) if output else _DEFAULT_GRAPH_PATH

    # Digest the dharma_swarm package directory
    package_dir = root_path / "dharma_swarm"
    if not package_dir.is_dir():
        package_dir = root_path  # Fall back to root itself

    print(f"[semantic digest] Scanning {package_dir}")
    digester = SemanticDigester()
    graph = digester.digest_directory(
        package_dir,
        include_tests=include_tests,
        max_files=max_files,
    )

    print(f"  nodes: {graph.node_count}  edges: {graph.edge_count}")
    _run(graph.save(out_path))
    print(f"  graph saved to: {out_path}")


def cmd_semantic_research(*, graph_path: str | None = None) -> None:
    """Phase 2: Annotate the graph with external research connections."""
    from dharma_swarm.semantic_gravity import ConceptGraph
    from dharma_swarm.semantic_researcher import SemanticResearcher

    gp = _resolve_graph_path(graph_path)
    graph = _run(ConceptGraph.load(gp))
    if graph.node_count == 0:
        print("[semantic research] Empty graph — run 'dgc semantic digest' first.")
        return

    researcher = SemanticResearcher()
    annotations = researcher.annotate_graph(graph)
    for ann in annotations:
        graph.add_annotation(ann)
    print(f"[semantic research] {len(annotations)} annotations added")

    coverage = researcher.coverage_report(graph)
    print(f"  coverage: {coverage.get('coverage_pct', 0):.1f}%")

    _run(graph.save(gp))
    print(f"  graph updated: {gp}")


def cmd_semantic_synthesize(
    *, graph_path: str | None = None, max_clusters: int = 10,
) -> None:
    """Phase 3: Generate file cluster specs from concept intersections."""
    from dharma_swarm.semantic_gravity import ConceptGraph
    from dharma_swarm.semantic_synthesizer import SemanticSynthesizer

    gp = _resolve_graph_path(graph_path)
    graph = _run(ConceptGraph.load(gp))
    if graph.node_count == 0:
        print("[semantic synthesize] Empty graph — run digest first.")
        return

    synth = SemanticSynthesizer(max_clusters=max_clusters)
    clusters = synth.synthesize(graph)

    print(f"[semantic synthesize] {len(clusters)} cluster specs generated")
    for c in clusters:
        print(f"  • {c.name}: {len(c.files)} files ({c.intersection_type})")

    gaps = synth.gap_analysis(graph)
    if gaps.get("structures_uncovered"):
        print(f"  uncovered structures: {', '.join(gaps['structures_uncovered'][:5])}")


def cmd_semantic_harden(
    *, graph_path: str | None = None, root: str = str(DHARMA_SWARM),
) -> None:
    """Phase 4: Run 6-angle hardening on synthesized clusters."""
    from dharma_swarm.semantic_gravity import ConceptGraph
    from dharma_swarm.semantic_hardener import SemanticHardener
    from dharma_swarm.semantic_synthesizer import SemanticSynthesizer

    gp = _resolve_graph_path(graph_path)
    graph = _run(ConceptGraph.load(gp))
    if graph.node_count == 0:
        print("[semantic harden] Empty graph — run digest first.")
        return

    synth = SemanticSynthesizer()
    clusters = synth.synthesize(graph)
    if not clusters:
        print("[semantic harden] No clusters to harden.")
        return

    hardener = SemanticHardener(project_root=Path(root))
    reports = hardener.harden_batch(clusters, graph)
    summary = hardener.summary(reports)

    print(f"[semantic harden] {summary['total']} clusters tested")
    print(f"  passed: {summary['passed']}  failed: {summary['failed']}")
    print(f"  avg_score: {summary.get('avg_score', 0):.3f}")
    for angle, stats in summary.get("angle_stats", {}).items():
        print(f"  {angle}: score={stats['avg_score']:.3f} pass_rate={stats['pass_rate']:.0%}")


def cmd_semantic_brief(
    *,
    graph_path: str | None = None,
    root: str = str(DHARMA_SWARM),
    max_briefs: int = 3,
    json_output: str | None = None,
    markdown_output: str | None = None,
    state_dir: str | None = None,
    campaign_path: str | None = None,
) -> None:
    """Compile hardened semantic clusters into campaign-grade briefs."""
    from dharma_swarm.mission_contract import (
        CampaignArtifact,
        build_campaign_state,
        default_campaign_state_path,
        load_active_campaign_state,
        load_active_mission_state,
        save_campaign_state,
    )
    from dharma_swarm.semantic_briefs import build_brief_packet, write_brief_packet
    from dharma_swarm.semantic_gravity import ConceptGraph
    from dharma_swarm.semantic_hardener import SemanticHardener
    from dharma_swarm.semantic_synthesizer import SemanticSynthesizer

    gp = _resolve_graph_path(graph_path)
    graph = _run(ConceptGraph.load(gp))
    if graph.node_count == 0:
        print("[semantic brief] Empty graph — run digest first.")
        return

    synth = SemanticSynthesizer(max_clusters=max(max_briefs * 2, max_briefs))
    clusters = synth.synthesize(graph)
    if not clusters:
        print("[semantic brief] No clusters available — run research/synthesize first.")
        return

    hardener = SemanticHardener(project_root=Path(root))
    reports = hardener.harden_batch(clusters, graph)
    packet = build_brief_packet(
        graph=graph,
        clusters=clusters,
        reports=reports,
        graph_path=str(gp),
        project_root=str(Path(root)),
        max_briefs=max_briefs,
    )

    json_target = Path(json_output) if json_output else gp.with_name("semantic_brief_packet.json")
    markdown_target = (
        Path(markdown_output)
        if markdown_output
        else json_target.with_suffix(".md")
    )
    json_path, markdown_path = write_brief_packet(
        packet,
        json_path=json_target,
        markdown_path=markdown_target,
    )

    state_root = Path(state_dir).expanduser() if state_dir else DHARMA_STATE
    mission_artifact = load_active_mission_state(state_dir=state_root)
    if mission_artifact is not None:
        try:
            previous_campaign_artifact = load_active_campaign_state(
                state_dir=state_root,
                path=campaign_path,
            )
        except ValueError:
            previous_campaign_artifact = None
        campaign_state = build_campaign_state(
            mission_state=mission_artifact.state,
            previous=previous_campaign_artifact.state if previous_campaign_artifact else None,
            semantic_briefs=packet.semantic_briefs,
            execution_briefs=packet.execution_briefs,
            artifacts=[
                CampaignArtifact(
                    artifact_kind="semantic_brief_packet_json",
                    title="semantic brief packet json",
                    path=str(json_path),
                    summary=f"{len(packet.semantic_briefs)} semantic briefs",
                    source="cmd_semantic_brief",
                ),
                CampaignArtifact(
                    artifact_kind="semantic_brief_packet_markdown",
                    title="semantic brief packet markdown",
                    path=str(markdown_path) if markdown_path else "",
                    summary=f"{len(packet.execution_briefs)} execution briefs",
                    source="cmd_semantic_brief",
                ),
            ],
            evidence_paths=[str(gp), str(json_path), str(markdown_path) if markdown_path else ""],
            metrics=dict(packet.metrics),
        )
        target_campaign = (
            Path(campaign_path).expanduser()
            if campaign_path
            else default_campaign_state_path(state_root)
        )
        save_campaign_state(target_campaign, campaign_state)
        print(f"[semantic brief] campaign updated: {target_campaign}")

    print(f"[semantic brief] semantic briefs: {len(packet.semantic_briefs)}")
    print(f"[semantic brief] execution briefs: {len(packet.execution_briefs)}")
    print(f"  json: {json_path}")
    if markdown_path:
        print(f"  markdown: {markdown_path}")


def cmd_semantic_proof(*, root: str = str(DHARMA_SWARM)) -> None:
    """Run live end-to-end proof of the Semantic Evolution Engine."""

    script = Path(root).parent / "scripts" / "semantic_proof.py"
    if not script.exists():
        script = Path(root) / "scripts" / "semantic_proof.py"
    if not script.exists():
        print(f"[semantic proof] Script not found: {script}")
        raise SystemExit(2)

    print(f"[semantic proof] Running {script}")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(Path(root).parent if (Path(root).parent / "scripts").is_dir() else root),
    )
    raise SystemExit(result.returncode)


def cmd_semantic_status(*, graph_path: str | None = None) -> None:
    """Show semantic graph status overview."""
    from dharma_swarm.semantic_gravity import ConceptGraph

    gp = _resolve_graph_path(graph_path)
    if not gp.exists():
        print(f"[semantic status] No graph found at {gp}")
        print("  Run 'dgc semantic digest' to build one.")
        return

    graph = _run(ConceptGraph.load(gp))
    components = graph.connected_components()

    print(f"[semantic status] Graph: {gp}")
    print(f"  nodes: {graph.node_count}")
    print(f"  edges: {graph.edge_count}")
    print(f"  annotations: {graph.annotation_count}")
    print(f"  density: {graph.density():.4f}")
    print(f"  connected components: {len(components)}")

    # Category breakdown
    categories: dict[str, int] = {}
    for node in graph.all_nodes():
        cat = node.category or "uncategorized"
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")

    # High salience concepts
    top = graph.high_salience_nodes(threshold=0.7)[:10]
    if top:
        print(f"  top concepts:")
        for n in top:
            print(f"    {n.name} (salience={n.salience:.2f}, {n.category})")


def cmd_rag_health(service: str = "rag", check_dependencies: bool = True) -> None:
    """Check NVIDIA RAG health."""

    async def _health():
        from dharma_swarm.integrations import NvidiaRagClient

        client = NvidiaRagClient()
        payload = await client.health(
            service=service,
            check_dependencies=check_dependencies,
        )
        print(json.dumps(payload, indent=2))

    _run(_health())


def cmd_rag_search(query: str, top_k: int = 5, collection: str | None = None) -> None:
    """Query NVIDIA RAG search endpoint."""

    async def _search():
        from dharma_swarm.integrations import NvidiaRagClient

        client = NvidiaRagClient()
        payload = await client.search(
            query=query,
            top_k=top_k,
            collection_name=collection,
        )
        print(json.dumps(payload, indent=2))

    _run(_search())


def cmd_rag_chat(prompt: str, model: str | None = None) -> None:
    """Run grounded chat via NVIDIA RAG."""

    async def _chat():
        from dharma_swarm.integrations import NvidiaRagClient

        client = NvidiaRagClient()
        payload = await client.chat(prompt=prompt, model=model)
        print(json.dumps(payload, indent=2))

    _run(_chat())
