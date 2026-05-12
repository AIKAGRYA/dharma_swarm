"""CLI for read-only KnowledgeOps projections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.knowledge_ops.extractor import ExtractorConfig, KnowledgeOpsExtractor
from dharma_swarm.knowledge_ops.memory_conflict_review import (
    MemoryConflictProjectionReview,
    render_memory_conflict_review_markdown,
    review_memory_conflicts,
)
from dharma_swarm.knowledge_ops.memory_intake import (
    MemoryEvidenceReview,
    MemoryKernelIntake,
    MemoryKernelIntakeConfig,
    memory_atoms_to_snapshot,
    merge_snapshots,
    render_memory_evidence_review_markdown,
    review_memory_atoms,
)
from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    MemoryPromotionDecisionLedger,
    build_memory_decision_ledger,
    load_memory_promotion_decisions,
    render_memory_decision_ledger_markdown,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    MemoryPromotionProposalQueue,
    build_memory_promotion_queue,
    render_memory_promotion_queue_markdown,
)
from dharma_swarm.knowledge_ops.projections import (
    default_mode_schedule,
    render_agent_context_bundle,
    render_concept_card,
)
from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--wiki-root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/knowledge_ops"))
    parser.add_argument("--wiki-limit", type=int, default=250)
    parser.add_argument("--bundle-objective", default="Inventory KnowledgeOps substrate.")
    parser.add_argument(
        "--include-memory-kernel",
        action="store_true",
        help="Include a read-only MemoryKernel atom intake projection.",
    )
    parser.add_argument(
        "--memory-home",
        type=Path,
        help="Home directory to use for MemoryKernel census/adapters.",
    )
    parser.add_argument(
        "--memory-surface",
        action="append",
        default=[],
        help="MemoryKernel surface ID to include. May be passed multiple times.",
    )
    parser.add_argument("--memory-limit-total", type=int, default=100)
    parser.add_argument("--memory-limit-per-surface", type=int, default=25)
    parser.add_argument("--memory-include-content", action="store_true")
    parser.add_argument("--memory-include-metadata-payloads", action="store_true")
    parser.add_argument("--memory-review-out", type=Path)
    parser.add_argument("--memory-review-md-out", type=Path)
    parser.add_argument("--memory-conflict-review-out", type=Path)
    parser.add_argument("--memory-conflict-review-md-out", type=Path)
    parser.add_argument("--memory-promotion-queue-out", type=Path)
    parser.add_argument("--memory-promotion-queue-md-out", type=Path)
    parser.add_argument("--memory-decision-in", type=Path)
    parser.add_argument("--memory-decision-ledger-out", type=Path)
    parser.add_argument("--memory-decision-ledger-md-out", type=Path)
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
    memory_review: MemoryEvidenceReview | None = None
    memory_conflict_review: MemoryConflictProjectionReview | None = None
    memory_promotion_queue: MemoryPromotionProposalQueue | None = None
    memory_decision_ledger: MemoryPromotionDecisionLedger | None = None
    if args.include_memory_kernel:
        census_kwargs: dict[str, object] = {
            "repo_root": args.repo_root,
            "include_discovered": False,
        }
        if args.memory_home is not None:
            census_kwargs["home"] = args.memory_home
        memory_kernel = MemoryKernel(
            MemoryKernelConfig(census=CensusConfig(**census_kwargs))
        )
        memory_intake = MemoryKernelIntake(
            memory_kernel,
            MemoryKernelIntakeConfig(
                surface_ids=tuple(args.memory_surface),
                limit_total=args.memory_limit_total,
                limit_per_surface=args.memory_limit_per_surface,
                include_content=args.memory_include_content,
                include_metadata_payloads=args.memory_include_metadata_payloads,
            ),
        )
        memory_atoms = memory_intake.collect_atoms()
        memory_snapshot = memory_atoms_to_snapshot(
            memory_atoms,
            include_surface_nodes=memory_intake.config.include_surface_nodes,
        )
        memory_review = review_memory_atoms(
            memory_atoms,
            snapshot=memory_snapshot,
            query=memory_intake.config.to_query(),
            surface_ids=memory_intake.config.surface_ids or None,
            sample_limit=memory_intake.config.review_sample_limit,
        )
        memory_conflict_review = review_memory_conflicts(memory_atoms)
        memory_promotion_queue = build_memory_promotion_queue(
            memory_atoms,
            conflict_review=memory_conflict_review,
        )
        memory_decisions = (
            load_memory_promotion_decisions(
                _resolve_output_path(args.repo_root, args.memory_decision_in)
            )
            if args.memory_decision_in
            else ()
        )
        memory_decision_ledger = build_memory_decision_ledger(
            memory_promotion_queue,
            decisions=memory_decisions,
        )
        snapshot = merge_snapshots(snapshot, memory_snapshot)
    summary = {
        "node_count": len(snapshot.nodes),
        "edge_count": len(snapshot.edges),
        "node_count_by_kind": snapshot.node_count_by_kind(),
        "edge_count_by_kind": snapshot.edge_count_by_kind(),
    }
    if memory_review is not None:
        summary["memory_review"] = {
            "total_atoms": memory_review.total_atoms,
            "projection_atom_count": memory_review.projection_atom_count,
            "context_admissible_count": memory_review.context_admissible_count,
            "promotion_allowed_count": memory_review.promotion_allowed_count,
            "redacted_count": memory_review.redacted_count,
            "content_bearing_count": memory_review.content_bearing_count,
            "warning_count": len(memory_review.warnings),
        }
    if memory_conflict_review is not None:
        summary["memory_conflict_review"] = {
            "finding_count": memory_conflict_review.finding_count,
            "displayed_finding_count": memory_conflict_review.displayed_finding_count,
            "finding_truncated": memory_conflict_review.finding_truncated,
            "conflict_candidate_count": memory_conflict_review.conflict_candidate_count,
            "projection_blocker_count": memory_conflict_review.projection_blocker_count,
            "promotion_candidate_count": memory_conflict_review.promotion_candidate_count,
            "displayed_promotion_candidate_count": (
                memory_conflict_review.displayed_promotion_candidate_count
            ),
            "promotion_candidate_truncated": (
                memory_conflict_review.promotion_candidate_truncated
            ),
            "promotion_blocked_atom_count": (
                memory_conflict_review.promotion_blocked_atom_count
            ),
            "promotion_blocker_count": memory_conflict_review.promotion_blocker_count,
        }
    if memory_promotion_queue is not None:
        summary["memory_promotion_queue"] = {
            "proposal_count": memory_promotion_queue.proposal_count,
            "displayed_proposal_count": memory_promotion_queue.displayed_proposal_count,
            "proposal_truncated": memory_promotion_queue.proposal_truncated,
            "blocked_atom_count": memory_promotion_queue.blocked_atom_count,
            "blocker_count": memory_promotion_queue.blocker_count,
            "warning_count": len(memory_promotion_queue.warnings),
        }
    if memory_decision_ledger is not None:
        summary["memory_decision_ledger"] = {
            "decision_count": memory_decision_ledger.decision_count,
            "valid_decision_count": memory_decision_ledger.valid_decision_count,
            "invalid_decision_count": memory_decision_ledger.invalid_decision_count,
            "accepted_count": memory_decision_ledger.accepted_count,
            "rejected_count": memory_decision_ledger.rejected_count,
            "deferred_count": memory_decision_ledger.deferred_count,
            "undecided_count": memory_decision_ledger.undecided_count,
            "warning_count": len(memory_decision_ledger.warnings),
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
    if memory_review is not None:
        if args.memory_review_out:
            review_path = _resolve_output_path(args.repo_root, args.memory_review_out)
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(
                json.dumps(memory_review.to_json(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if args.memory_review_md_out:
            review_md_path = _resolve_output_path(args.repo_root, args.memory_review_md_out)
            review_md_path.parent.mkdir(parents=True, exist_ok=True)
            review_md_path.write_text(
                render_memory_evidence_review_markdown(memory_review),
                encoding="utf-8",
            )
        if args.memory_conflict_review_out:
            conflict_path = _resolve_output_path(args.repo_root, args.memory_conflict_review_out)
            conflict_path.parent.mkdir(parents=True, exist_ok=True)
            conflict_path.write_text(
                json.dumps(memory_conflict_review.to_json(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if args.memory_conflict_review_md_out:
            conflict_md_path = _resolve_output_path(
                args.repo_root,
                args.memory_conflict_review_md_out,
            )
            conflict_md_path.parent.mkdir(parents=True, exist_ok=True)
            conflict_md_path.write_text(
                render_memory_conflict_review_markdown(memory_conflict_review),
                encoding="utf-8",
            )
        if args.memory_promotion_queue_out:
            queue_path = _resolve_output_path(args.repo_root, args.memory_promotion_queue_out)
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            queue_path.write_text(
                json.dumps(memory_promotion_queue.to_json(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if args.memory_promotion_queue_md_out:
            queue_md_path = _resolve_output_path(
                args.repo_root,
                args.memory_promotion_queue_md_out,
            )
            queue_md_path.parent.mkdir(parents=True, exist_ok=True)
            queue_md_path.write_text(
                render_memory_promotion_queue_markdown(memory_promotion_queue),
                encoding="utf-8",
            )
        if args.memory_decision_ledger_out:
            ledger_path = _resolve_output_path(args.repo_root, args.memory_decision_ledger_out)
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text(
                json.dumps(memory_decision_ledger.to_json(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if args.memory_decision_ledger_md_out:
            ledger_md_path = _resolve_output_path(
                args.repo_root,
                args.memory_decision_ledger_md_out,
            )
            ledger_md_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_md_path.write_text(
                render_memory_decision_ledger_markdown(memory_decision_ledger),
                encoding="utf-8",
            )
    return 0


def _resolve_output_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
