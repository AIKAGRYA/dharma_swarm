"""Human and agent-facing projections from KnowledgeOps records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dharma_swarm.knowledge_ops.schema import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    KnowledgeOpsMode,
    NodeKind,
)


def render_concept_card(
    node: KnowledgeNode,
    *,
    related_edges: tuple[KnowledgeEdge, ...] = (),
) -> str:
    """Render a compact concept card with provenance and boundaries."""
    refs = [
        f"- `{ref.path}`"
        + (f":{ref.lines}" if ref.lines else "")
        + f" ({ref.role})"
        for ref in node.source_refs
    ] or ["- No source refs attached."]
    related = [
        f"- {edge.kind.value}: `{edge.target_id}`"
        for edge in related_edges
        if edge.source_id == node.node_id
    ][:7] or ["- No related edges in this projection."]
    title = node.title.strip() or node.node_id
    return "\n".join(
        [
            f"# {title}",
            "",
            f"Kind: `{node.kind.value}`",
            f"Status: `{node.status.value}`",
            f"Confidence: `{node.confidence:.2f}`",
            "",
            "Core claim:",
            f"- {title}",
            "",
            "Operational meaning:",
            "- Use this card as a compact pointer, not as authority by itself.",
            "- Verify source refs before promotion into canonical docs or runtime policy.",
            "",
            "Boundaries:",
            "- Do not infer beyond the attached source refs.",
            "- Do not treat staged or candidate cards as doctrine.",
            "",
            "Related:",
            *related,
            "",
            "Provenance:",
            *refs,
            "",
        ]
    )


def render_agent_context_bundle(
    *,
    bundle_id: str,
    role: str,
    objective: str,
    nodes: tuple[KnowledgeNode, ...],
    edges: tuple[KnowledgeEdge, ...],
    token_budget: int = 12000,
) -> str:
    """Render a task-specific, disposable agent context bundle."""
    now = datetime.now(UTC)
    expires = now + timedelta(hours=12)
    node_lines = [
        f"- `{node.node_id}` [{node.kind.value}/{node.status.value}] {node.title}"
        for node in nodes[:20]
    ]
    stale_lines = [
        f"- `{node.node_id}` {node.title} stale_after={node.stale_after}"
        for node in nodes
        if node.stale_after
    ][:10]
    edge_counts: dict[str, int] = {}
    for edge in edges:
        edge_counts[edge.kind.value] = edge_counts.get(edge.kind.value, 0) + 1
    edge_lines = [
        f"- {kind}: {count}" for kind, count in sorted(edge_counts.items())
    ] or ["- none"]
    return "\n".join(
        [
            f"# Agent Context Bundle: {bundle_id}",
            "",
            f"Role: {role}",
            f"Generated: {now.isoformat()}",
            f"Expires: {expires.isoformat()}",
            f"Token budget: {token_budget}",
            "",
            "Objective:",
            objective,
            "",
            "Authority:",
            "- This bundle is a projection. Source refs outrank summaries.",
            "- Canonical docs and human/operator approvals outrank generated cards.",
            "",
            "Relevant nodes:",
            *node_lines,
            "",
            "Edge summary:",
            *edge_lines,
            "",
            "Stale or time-bound sources:",
            *(stale_lines or ["- none in selected nodes"]),
            "",
            "Evidence to return:",
            "- Source paths inspected.",
            "- Any contradictions or stale claims found.",
            "- Tests or commands run, if implementation follows.",
            "",
            "Anti-drift:",
            "- Do not create new authority docs from this bundle.",
            "- Do not promote dream/synthesis candidates without evidence and review.",
            "",
        ]
    )


def default_mode_schedule() -> list[dict[str, object]]:
    """Return the advisory KnowledgeOps mode schedule.

    The schedule is data only.  It deliberately does not register cron jobs.
    """
    return [
        {
            "mode": KnowledgeOpsMode.WAKE.value,
            "cadence": "daily 04:30",
            "inputs": ["live_ops_dashboard", "broken_register", "active_tasks"],
            "outputs": ["morning_context_bundle"],
            "may_mutate_authority": False,
        },
        {
            "mode": KnowledgeOpsMode.SENSE.value,
            "cadence": "hourly",
            "inputs": ["repo_changes", "wiki_changes", "runtime_events", "external_feeds"],
            "outputs": ["episode_candidates"],
            "may_mutate_authority": False,
        },
        {
            "mode": KnowledgeOpsMode.LEARNING.value,
            "cadence": "after work packet",
            "inputs": ["tests", "reviews", "outcomes", "agentops"],
            "outputs": ["lesson_candidates", "procedure_candidates"],
            "may_mutate_authority": False,
        },
        {
            "mode": KnowledgeOpsMode.REFLECTION.value,
            "cadence": "daily",
            "inputs": ["episodes", "claims", "evidence", "outcomes"],
            "outputs": ["claim_candidates", "contradiction_candidates"],
            "may_mutate_authority": False,
        },
        {
            "mode": KnowledgeOpsMode.SLEEP.value,
            "cadence": "nightly",
            "inputs": ["nodes", "edges", "retrieval_logs", "wiki_atoms"],
            "outputs": ["dedupe_report", "stale_report", "graph_refresh"],
            "may_mutate_authority": False,
        },
        {
            "mode": KnowledgeOpsMode.DREAM.value,
            "cadence": "weekly",
            "inputs": ["distant_concepts", "open_questions", "low_connected_subgraphs"],
            "outputs": ["synthesis_candidates"],
            "may_mutate_authority": False,
            "promotion_rule": "candidate_only_until_evidence_review",
        },
        {
            "mode": KnowledgeOpsMode.IMMUNE.value,
            "cadence": "daily",
            "inputs": ["authority_docs", "docops_findings", "broken_links"],
            "outputs": ["duplicate_authority_findings", "unsupported_claim_findings"],
            "may_mutate_authority": False,
        },
        {
            "mode": KnowledgeOpsMode.PROMOTION.value,
            "cadence": "manual or reviewed PR",
            "inputs": ["trusted_candidates", "evidence", "owner_approval"],
            "outputs": ["promotion_pr"],
            "may_mutate_authority": True,
            "requires_human_review": True,
        },
        {
            "mode": KnowledgeOpsMode.FORGETTING.value,
            "cadence": "weekly reviewed PR",
            "inputs": ["stale_docs", "superseded_cards", "archive_candidates"],
            "outputs": ["archive_pr_with_tombstones"],
            "may_mutate_authority": True,
            "requires_human_review": True,
        },
    ]


def candidate_edges(edges: tuple[KnowledgeEdge, ...]) -> tuple[KnowledgeEdge, ...]:
    return tuple(
        edge
        for edge in edges
        if edge.kind
        in {
            EdgeKind.CONTRADICTS,
            EdgeKind.SYNTHESIZES,
            EdgeKind.SUPERSEDES,
            EdgeKind.PROMOTES,
        }
    )
