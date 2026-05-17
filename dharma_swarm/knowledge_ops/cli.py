"""KnowledgeOps read-only MemoryKernel intake CLI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dharma_swarm.knowledge_ops.memory_conflict_review import (
    render_memory_conflict_review_markdown,
    review_memory_conflicts,
)
from dharma_swarm.knowledge_ops.memory_decision_ledger import (
    build_memory_decision_ledger,
    load_memory_promotion_decisions,
    render_memory_decision_ledger_markdown,
)
from dharma_swarm.knowledge_ops.memory_intake import (
    MemoryKernelIntake,
    MemoryKernelIntakeConfig,
    render_memory_evidence_review_markdown,
)
from dharma_swarm.knowledge_ops.memory_promotion_queue import (
    build_memory_promotion_queue,
    render_memory_promotion_queue_markdown,
)
from dharma_swarm.knowledge_ops.memory_promotion_executor import (
    append_memory_promotion_artifacts,
    execute_memory_promotion_dry_run,
)
from dharma_swarm.knowledge_ops.memory_kernel_promotion_bridge import (
    DEFAULT_BRIDGE_WRITE_RECEIPT_TARGET,
    append_memory_kernel_promotion_bridge_artifacts,
    execute_memory_kernel_promotion_bridge,
)
from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig
from dharma_swarm.memory_kernel.context_admission import redact_context_text


MEMORY_HOME_ENV_VAR = "DHARMA_MEMORY_KERNEL_HOME"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--memory-home", type=Path)
    parser.add_argument("--include-memory-kernel", action="store_true")
    parser.add_argument("--memory-surface", action="append", default=[])
    parser.add_argument("--memory-limit-total", type=int, default=100)
    parser.add_argument("--memory-limit-per-surface", type=int, default=25)
    parser.add_argument("--memory-review-out", type=Path)
    parser.add_argument("--memory-review-md-out", type=Path)
    parser.add_argument("--memory-conflict-review-out", type=Path)
    parser.add_argument("--memory-conflict-review-md-out", type=Path)
    parser.add_argument("--memory-promotion-queue-out", type=Path)
    parser.add_argument("--memory-promotion-queue-md-out", type=Path)
    parser.add_argument("--memory-decision-in", type=Path)
    parser.add_argument("--memory-decision-ledger-out", type=Path)
    parser.add_argument("--memory-decision-ledger-md-out", type=Path)
    parser.add_argument("--memory-promotion-target-surface")
    parser.add_argument("--memory-promotion-request-out", type=Path)
    parser.add_argument("--memory-promotion-receipt-out", type=Path)
    parser.add_argument("--memory-kernel-promotion-bridge", action="store_true")
    parser.add_argument(
        "--memory-kernel-write-receipt-target",
        default=DEFAULT_BRIDGE_WRITE_RECEIPT_TARGET,
    )
    parser.add_argument("--memory-kernel-write-receipt-out", type=Path)
    parser.add_argument("--memory-kernel-promotion-decision-out", type=Path)
    parser.add_argument("--memory-kernel-canonical-receipt-out", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    home_error = _resolve_memory_home(args)
    if home_error:
        print(_safe_json_text({"error": home_error}))
        return 2
    validation_error = _validate_args(args)
    if validation_error:
        print(_safe_json_text({"error": validation_error}))
        return 2

    payload: dict[str, object] = {
        "include_memory_kernel": bool(args.include_memory_kernel),
        "warnings": ("read_only_no_canon_or_memory_writes",),
    }
    outputs: list[tuple[Path | None, str]] = []

    if args.include_memory_kernel:
        memory_kernel = MemoryKernel(
            MemoryKernelConfig(
                census=CensusConfig(
                    repo_root=args.repo_root,
                    home=args.memory_home,
                    include_discovered=False,
                )
            )
        )
        intake = MemoryKernelIntake(
            memory_kernel,
            MemoryKernelIntakeConfig(
                surface_ids=tuple(args.memory_surface),
                limit_total=args.memory_limit_total,
                limit_per_surface=args.memory_limit_per_surface,
            ),
        )
        evidence_review = intake.review()
        conflict_review = review_memory_conflicts(evidence_review)
        queue = build_memory_promotion_queue(conflict_review)
        decisions = (
            load_memory_promotion_decisions(args.memory_decision_in)
            if args.memory_decision_in
            else ()
        )
        ledger = build_memory_decision_ledger(queue, decisions)
        bridge_result = None
        if args.memory_kernel_promotion_bridge:
            bridge_result = execute_memory_kernel_promotion_bridge(
                queue,
                ledger,
                target_authority_surface=args.memory_promotion_target_surface,
                write_receipt_target_surface=args.memory_kernel_write_receipt_target,
            )
            promotion_result = bridge_result.dry_run_result
        else:
            promotion_result = (
                execute_memory_promotion_dry_run(
                    queue,
                    ledger,
                    target_authority_surface=args.memory_promotion_target_surface,
                )
                if args.memory_promotion_target_surface
                else None
            )
        payload.update(
            {
                "memory_review": evidence_review.to_json(),
                "memory_conflict_review": conflict_review.to_json(),
                "memory_promotion_queue": queue.to_json(),
                "memory_decision_ledger": ledger.to_json(),
            }
        )
        if promotion_result is not None:
            payload["memory_promotion_dry_run"] = promotion_result.to_json()
        if bridge_result is not None:
            payload["memory_kernel_promotion_bridge"] = bridge_result.to_json()
        outputs.extend(
            [
                (args.memory_review_out, _safe_json_text(evidence_review.to_json())),
                (
                    args.memory_review_md_out,
                    _safe_text(render_memory_evidence_review_markdown(evidence_review)),
                ),
                (
                    args.memory_conflict_review_out,
                    _safe_json_text(conflict_review.to_json()),
                ),
                (
                    args.memory_conflict_review_md_out,
                    _safe_text(render_memory_conflict_review_markdown(conflict_review)),
                ),
                (args.memory_promotion_queue_out, _safe_json_text(queue.to_json())),
                (
                    args.memory_promotion_queue_md_out,
                    _safe_text(render_memory_promotion_queue_markdown(queue)),
                ),
                (args.memory_decision_ledger_out, _safe_json_text(ledger.to_json())),
                (
                    args.memory_decision_ledger_md_out,
                    _safe_text(render_memory_decision_ledger_markdown(ledger)),
                ),
            ]
        )

    payload_text = _safe_json_text(payload)
    print(payload_text)
    if not args.dry_run:
        for output_path, text in outputs:
            if output_path is None:
                continue
            resolved = _resolve_output(output_path, args.repo_root)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(text + "\n", encoding="utf-8")
        if (
            args.include_memory_kernel
            and args.memory_promotion_target_surface
            and not args.memory_kernel_promotion_bridge
        ):
            append_memory_promotion_artifacts(
                promotion_result,
                request_path=(
                    _resolve_output(args.memory_promotion_request_out, args.repo_root)
                    if args.memory_promotion_request_out
                    else None
                ),
                receipt_path=(
                    _resolve_output(args.memory_promotion_receipt_out, args.repo_root)
                    if args.memory_promotion_receipt_out
                    else None
                ),
                forbidden_roots=_memory_surface_roots(args),
            )
        if args.include_memory_kernel and args.memory_kernel_promotion_bridge:
            append_memory_kernel_promotion_bridge_artifacts(
                bridge_result,
                write_receipt_path=(
                    _resolve_output(args.memory_kernel_write_receipt_out, args.repo_root)
                    if args.memory_kernel_write_receipt_out
                    else None
                ),
                decision_path=(
                    _resolve_output(
                        args.memory_kernel_promotion_decision_out,
                        args.repo_root,
                    )
                    if args.memory_kernel_promotion_decision_out
                    else None
                ),
                canonical_receipt_path=(
                    _resolve_output(
                        args.memory_kernel_canonical_receipt_out,
                        args.repo_root,
                    )
                    if args.memory_kernel_canonical_receipt_out
                    else None
                ),
                dry_run_request_path=(
                    _resolve_output(args.memory_promotion_request_out, args.repo_root)
                    if args.memory_promotion_request_out
                    else None
                ),
                dry_run_receipt_path=(
                    _resolve_output(args.memory_promotion_receipt_out, args.repo_root)
                    if args.memory_promotion_receipt_out
                    else None
                ),
                forbidden_roots=_memory_surface_roots(args),
            )
    return 0


def _validate_args(args: argparse.Namespace) -> str:
    promotion_requested = _promotion_requested(args)
    if args.include_memory_kernel:
        if args.memory_home is None:
            return (
                "--include-memory-kernel requires explicit --memory-home "
                f"or {MEMORY_HOME_ENV_VAR}"
            )
        if not args.memory_surface:
            return "--include-memory-kernel requires at least one --memory-surface"
    elif any(_output_paths(args)):
        return "memory review outputs require --include-memory-kernel"
    elif promotion_requested:
        return "memory promotion dry-run requires --include-memory-kernel"
    if promotion_requested:
        if not args.memory_promotion_target_surface:
            return "memory promotion dry-run requires --memory-promotion-target-surface"
        if args.memory_decision_in is None:
            return "memory promotion dry-run requires --memory-decision-in"
    for output_path in _output_paths(args):
        if output_path and _is_memory_surface_output(output_path, args):
            return "output paths under memory surfaces are not allowed"
    return ""


def _resolve_memory_home(args: argparse.Namespace) -> str:
    configured = os.environ.get(MEMORY_HOME_ENV_VAR, "").strip()
    env_home = Path(configured).expanduser() if configured else None
    if args.memory_home is None:
        args.memory_home = env_home
        return ""
    if env_home is None:
        return ""
    cli_home = args.memory_home.expanduser()
    if cli_home.resolve() != env_home.resolve():
        return (
            "--memory-home must match "
            f"{MEMORY_HOME_ENV_VAR} when both are configured"
        )
    return ""


def _output_paths(args: argparse.Namespace) -> tuple[Path | None, ...]:
    return (
        args.memory_review_out,
        args.memory_review_md_out,
        args.memory_conflict_review_out,
        args.memory_conflict_review_md_out,
        args.memory_promotion_queue_out,
        args.memory_promotion_queue_md_out,
        args.memory_decision_ledger_out,
        args.memory_decision_ledger_md_out,
        args.memory_promotion_request_out,
        args.memory_promotion_receipt_out,
        args.memory_kernel_write_receipt_out,
        args.memory_kernel_promotion_decision_out,
        args.memory_kernel_canonical_receipt_out,
    )


def _promotion_requested(args: argparse.Namespace) -> bool:
    return bool(
        args.memory_promotion_target_surface
        or args.memory_promotion_request_out
        or args.memory_promotion_receipt_out
        or args.memory_kernel_promotion_bridge
        or args.memory_kernel_write_receipt_out
        or args.memory_kernel_promotion_decision_out
        or args.memory_kernel_canonical_receipt_out
    )


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _is_memory_surface_output(path: Path, args: argparse.Namespace) -> bool:
    resolved = _resolve_output(path, args.repo_root).expanduser().resolve()
    for root in _memory_surface_roots(args):
        if _is_relative_to(resolved, root.expanduser().resolve()):
            return True
    return False


def _memory_surface_roots(args: argparse.Namespace) -> tuple[Path, ...]:
    home_roots = [Path.home()]
    if args.memory_home is not None:
        home_roots.append(args.memory_home)
    roots: list[Path] = []
    for home in home_roots:
        roots.extend(
            [
                home / ".dharma",
                home / ".smriti",
                home / ".codex" / "memories",
            ]
        )
    roots.extend([args.repo_root / ".dharma", args.repo_root / ".swarm"])
    return tuple(roots)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_json_text(payload: object) -> str:
    return _safe_text(json.dumps(payload, indent=2, sort_keys=True))


def _safe_text(text: str) -> str:
    return redact_context_text(text)


if __name__ == "__main__":
    raise SystemExit(main())
