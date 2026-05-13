#!/usr/bin/env python3
"""Run the MemoryKernel M3B/M3C context safety eval harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.memory_kernel.context_admission import redact_context_text
from dharma_swarm.memory_kernel import (
    CensusConfig,
    ContextEvalConfig,
    MemoryContextBudget,
    MemoryKernel,
    MemoryKernelConfig,
    default_context_eval_cases,
    render_context_eval_markdown,
    run_default_context_eval_cases,
    run_context_eval,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--list-cases", action="store_true")
    parser.add_argument("--run-default-cases", action="store_true")
    parser.add_argument("--run-parity-eval", action="store_true")
    parser.add_argument("--include-current-context", action="store_true")
    parser.add_argument("--current-context-text")
    parser.add_argument("--current-context-file", type=Path)
    parser.add_argument("--allow-current-semantic-search", action="store_true")
    parser.add_argument("--memory-home", type=Path)
    parser.add_argument("--memory-surface", action="append", default=[])
    parser.add_argument("--memory-limit-total", type=int, default=50)
    parser.add_argument("--memory-limit-per-surface", type=int, default=25)
    parser.add_argument("--max-candidate-atoms", type=int, default=50)
    parser.add_argument("--max-admitted-atoms", type=int, default=8)
    parser.add_argument("--include-content", action="store_true")
    parser.add_argument("--allow-projections", action="store_true")
    parser.add_argument("--allow-high-risk", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--allow-memory-surface-output", action="store_true")
    parser.add_argument("--fail-on-hard-failure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_cases:
        print(
            json.dumps(
                {
                    "cases": [
                        {
                            "case_id": case.case_id,
                            "title": case.title,
                            "description": case.description,
                        }
                        for case in default_context_eval_cases()
                    ]
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    validation_error = _validate_args(args)
    if validation_error:
        print(json.dumps({"error": validation_error}, indent=2, sort_keys=True))
        return 2

    if args.run_default_cases:
        return _run_default_cases(args)
    if args.run_parity_eval:
        return _run_parity_eval(args)

    current_context_text = _current_context_text(args)
    include_current = bool(
        args.include_current_context or current_context_text is not None
    )
    memory_kernel = _memory_kernel(args)
    config = _context_eval_config(
        args,
        include_current=include_current,
        include_memory_kernel=memory_kernel is not None,
    )
    report = run_context_eval(
        config=config,
        current_context_text=current_context_text,
        state_dir=args.state_dir,
        memory_kernel=memory_kernel,
    )
    payload = report.to_json()
    payload_text = _safe_json_text(payload)
    print(payload_text)

    if not args.dry_run:
        if args.output_json:
            output_json = _resolve_output(args.output_json, args.repo_root)
            output_json.parent.mkdir(parents=True, exist_ok=True)
            output_json.write_text(payload_text + "\n", encoding="utf-8")
        if args.output_md:
            output_md = _resolve_output(args.output_md, args.repo_root)
            output_md.parent.mkdir(parents=True, exist_ok=True)
            output_md.write_text(
                _safe_text(render_context_eval_markdown(report)),
                encoding="utf-8",
            )

    if args.fail_on_hard_failure and report.hard_failure_count > 0:
        return 6
    return 0


def _run_parity_eval(args: argparse.Namespace) -> int:
    try:
        (
            run_context_parity_eval,
            render_context_parity_markdown,
        ) = _load_context_parity_api()
    except ModuleNotFoundError as exc:
        if exc.name != "dharma_swarm.memory_kernel.context_parity":
            raise
        print(
            json.dumps(
                {
                    "error": (
                        "dharma_swarm.memory_kernel.context_parity is not available"
                    )
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    current_context_text = _current_context_text(args)
    memory_kernel = _memory_kernel(args)
    report = run_context_parity_eval(
        query=args.query,
        current_context_text=current_context_text,
        state_dir=args.state_dir,
        memory_kernel=memory_kernel,
        memory_surface_ids=tuple(args.memory_surface),
        budget=MemoryContextBudget(
            max_candidate_atoms=args.max_candidate_atoms,
            max_admitted_atoms=args.max_admitted_atoms,
            include_content=args.include_content,
            allow_projections=args.allow_projections,
            allow_high_risk=args.allow_high_risk,
        ),
        allow_current_semantic_search=args.allow_current_semantic_search,
    )
    payload = report.to_json()
    payload_text = _safe_json_text(payload)
    print(payload_text)

    if not args.dry_run:
        if args.output_json:
            output_json = _resolve_output(args.output_json, args.repo_root)
            output_json.parent.mkdir(parents=True, exist_ok=True)
            output_json.write_text(payload_text + "\n", encoding="utf-8")
        if args.output_md:
            output_md = _resolve_output(args.output_md, args.repo_root)
            output_md.parent.mkdir(parents=True, exist_ok=True)
            output_md.write_text(
                _safe_text(render_context_parity_markdown(report)),
                encoding="utf-8",
            )

    if args.fail_on_hard_failure and report.hard_failure_count > 0:
        return 6
    return 0


def _run_default_cases(args: argparse.Namespace) -> int:
    results = run_default_context_eval_cases()
    payload = {
        "case_count": len(results),
        "passed": all(result.passed for result in results),
        "failure_count": sum(len(result.failures) for result in results),
        "hard_failure_count": sum(
            result.report.hard_failure_count for result in results
        ),
        "warning_count": sum(result.report.warning_count for result in results),
        "cases": [result.to_json() for result in results],
    }
    payload_text = _safe_json_text(payload)
    print(payload_text)
    if not args.dry_run:
        if args.output_json:
            output_json = _resolve_output(args.output_json, args.repo_root)
            output_json.parent.mkdir(parents=True, exist_ok=True)
            output_json.write_text(payload_text + "\n", encoding="utf-8")
        if args.output_md:
            output_md = _resolve_output(args.output_md, args.repo_root)
            output_md.parent.mkdir(parents=True, exist_ok=True)
            output_md.write_text(
                _safe_text(_render_case_results_markdown(results)),
                encoding="utf-8",
            )
    if args.fail_on_hard_failure and (
        not payload["passed"] or payload["hard_failure_count"] > 0
    ):
        return 6
    return 0


def _validate_args(args: argparse.Namespace) -> str:
    if args.run_default_cases and args.run_parity_eval:
        return "use either --run-default-cases or --run-parity-eval, not both"
    if args.current_context_file and args.current_context_text:
        return "use either --current-context-file or --current-context-text, not both"
    if args.include_current_context and not (
        args.state_dir or args.current_context_file or args.current_context_text
    ):
        return "--include-current-context requires --state-dir or explicit context text"
    if (
        args.allow_current_semantic_search
        and not args.include_current_context
        and not args.run_parity_eval
    ):
        return "--allow-current-semantic-search requires --include-current-context"
    if args.memory_surface and args.memory_home is None:
        return "--memory-surface requires explicit --memory-home"
    if args.memory_home is not None and not args.memory_surface:
        return "--memory-home requires at least one --memory-surface"
    if not args.allow_memory_surface_output:
        for output_path in (args.output_json, args.output_md):
            if output_path and _is_memory_surface_output(output_path, args):
                return "output paths under memory surfaces require --allow-memory-surface-output"
    return ""


def _context_eval_config(
    args: argparse.Namespace,
    *,
    include_current: bool,
    include_memory_kernel: bool,
) -> ContextEvalConfig:
    return ContextEvalConfig(
        query=args.query,
        limit=args.limit,
        memory_surface_ids=tuple(args.memory_surface),
        memory_limit_total=args.memory_limit_total,
        memory_limit_per_surface=args.memory_limit_per_surface,
        include_current_context=include_current,
        include_memory_kernel=include_memory_kernel,
        allow_current_semantic_search=args.allow_current_semantic_search,
        budget=MemoryContextBudget(
            max_candidate_atoms=args.max_candidate_atoms,
            max_admitted_atoms=args.max_admitted_atoms,
            include_content=args.include_content,
            allow_projections=args.allow_projections,
            allow_high_risk=args.allow_high_risk,
        ),
    )


def _current_context_text(args: argparse.Namespace) -> str | None:
    if args.current_context_text is not None:
        return args.current_context_text
    if args.current_context_file is not None:
        return args.current_context_file.read_text(encoding="utf-8")
    return None


def _memory_kernel(args: argparse.Namespace) -> MemoryKernel | None:
    if args.memory_home is None:
        return None
    return MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=args.repo_root,
                home=args.memory_home,
                include_discovered=False,
            )
        )
    )


def _load_context_parity_api():
    from dharma_swarm.memory_kernel.context_parity import (  # noqa: PLC0415
        render_context_parity_markdown,
        run_context_parity_eval,
    )

    return run_context_parity_eval, render_context_parity_markdown


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _safe_json_text(payload: object) -> str:
    return _safe_text(json.dumps(payload, indent=2, sort_keys=True))


def _safe_text(text: str) -> str:
    return redact_context_text(text)


def _render_case_results_markdown(results) -> str:
    lines = [
        "# Memory Context Eval Cases",
        "",
        "Synthetic shadow-mode cases. They do not read live memory or write retrieval feedback.",
        "",
        "## Summary",
        "",
        f"- Cases: `{len(results)}`",
        f"- Passed: `{str(all(result.passed for result in results)).lower()}`",
        f"- Failures: `{sum(len(result.failures) for result in results)}`",
        "",
        "## Cases",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result.case.case_id}` passed=`{str(result.passed).lower()}` "
            f"hard_failures=`{result.report.hard_failure_count}` "
            f"warnings=`{result.report.warning_count}`"
        )
        for failure in result.failures:
            lines.append(f"  - failure: `{failure}`")
    lines.append("")
    return "\n".join(lines)


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


if __name__ == "__main__":
    raise SystemExit(main())
