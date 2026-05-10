"""CLI for read-only KnowledgeOps projections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.knowledge_ops.extractor import ExtractorConfig, KnowledgeOpsExtractor
from dharma_swarm.knowledge_ops.projections import (
    default_mode_schedule,
    render_agent_context_bundle,
    render_concept_card,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--wiki-root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/knowledge_ops"))
    parser.add_argument("--wiki-limit", type=int, default=250)
    parser.add_argument("--bundle-objective", default="Inventory KnowledgeOps substrate.")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ExtractorConfig(
        repo_root=args.repo_root,
        wiki_root=args.wiki_root,
        wiki_limit=args.wiki_limit,
    )
    snapshot = KnowledgeOpsExtractor(config).extract()
    summary = {
        "node_count": len(snapshot.nodes),
        "edge_count": len(snapshot.edges),
        "node_count_by_kind": snapshot.node_count_by_kind(),
        "edge_count_by_kind": snapshot.edge_count_by_kind(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = args.repo_root / output_dir
    snapshot.write_jsonl(output_dir)
    (output_dir / "mode_schedule.json").write_text(
        json.dumps(default_mode_schedule(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if snapshot.nodes:
        first_concept = next(
            (node for node in snapshot.nodes if node.kind.value == "concept"),
            snapshot.nodes[0],
        )
        (output_dir / "sample_concept_card.md").write_text(
            render_concept_card(first_concept, related_edges=snapshot.edges),
            encoding="utf-8",
        )
    (output_dir / "sample_agent_context_bundle.md").write_text(
        render_agent_context_bundle(
            bundle_id="knowledgeops.v0.sample",
            role="knowledge-ops-reviewer",
            objective=args.bundle_objective,
            nodes=snapshot.nodes,
            edges=snapshot.edges,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
