#!/usr/bin/env python3
"""Run MemoryKernel M3 burn-in and append proof receipts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.memory_kernel import (  # noqa: E402
    DEFAULT_BURN_IN_RECEIPT_PATH,
    DEFAULT_BURN_IN_SUMMARY_PATH,
    CensusConfig,
    MemoryKernel,
    MemoryKernelConfig,
    append_burn_in_receipt,
    build_burn_in_receipt,
    load_burn_in_status,
    run_default_context_eval_cases,
    write_burn_in_summary,
)
from dharma_swarm.operator_core.control_surface_memory import (  # noqa: E402
    ROLLBACK_ENV_VAR,
    project_context_canary_report,
)
from scripts.memory_context_shadow_sweep import (  # noqa: E402
    _memory_kernel,
    _payload,
    _run_scenario,
    _selected_scenarios,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--memory-home", type=Path)
    parser.add_argument("--memory-surface", action="append", default=[])
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--max-candidate-atoms", type=int, default=50)
    parser.add_argument("--max-admitted-atoms", type=int, default=8)
    parser.add_argument("--receipt-out", type=Path, default=DEFAULT_BURN_IN_RECEIPT_PATH)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_BURN_IN_SUMMARY_PATH)
    parser.add_argument("--min-run-count", type=int, default=1)
    parser.add_argument("--max-age-seconds", type=int, default=86_400)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validation_error = _validate_args(args)
    if validation_error:
        print(json.dumps({"error": validation_error}, indent=2, sort_keys=True))
        return 2

    readiness = _strict_readiness_ready(args)
    context_results = run_default_context_eval_cases()
    scenarios = _selected_scenarios(args.scenario)
    shadow_reports = [
        _run_scenario(args, scenario, memory_kernel=_memory_kernel(args))
        for scenario in scenarios
    ]
    shadow_payload = _payload(shadow_reports)
    canary = project_context_canary_report()
    receipt = build_burn_in_receipt(
        strict_readiness_ready=readiness,
        synthetic_canary_detected=int(canary.get("hard_failure_count", 0) or 0) > 0,
        rollback_available=not _truthy(os.environ.get(ROLLBACK_ENV_VAR, "")),
        context_case_count=len(context_results),
        context_case_failure_count=sum(len(result.failures) for result in context_results),
        context_case_hard_failure_count=sum(
            result.report.hard_failure_count for result in context_results
        ),
        shadow_scenario_count=int(shadow_payload["scenario_count"]),
        parity_hard_failure_count=int(shadow_payload["hard_failure_count"]),
        warning_count=sum(result.report.warning_count for result in context_results)
        + int(shadow_payload["warning_count"]),
        warnings=("burn_in_receipt_is_append_only_artifact",),
    )
    receipt_path = _resolve_output(args.receipt_out, args.repo_root)
    if not args.dry_run:
        append_burn_in_receipt(
            receipt_path,
            receipt,
            forbidden_roots=_memory_surface_roots(args),
        )
    status = load_burn_in_status(
        receipt_path,
        min_run_count=args.min_run_count,
        max_age_seconds=args.max_age_seconds,
    )
    if args.dry_run:
        status = load_burn_in_status(
            Path("__dry_run_missing_receipt_log__"),
            min_run_count=args.min_run_count,
            max_age_seconds=args.max_age_seconds,
        )
    elif args.summary_out:
        write_burn_in_summary(_resolve_output(args.summary_out, args.repo_root), status)
    payload = {
        "receipt": receipt.to_json(),
        "status": status.to_json(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.fail_on_blocked and (
        receipt.status != "passed" or not status.burn_in_ready
    ):
        return 6
    return 0


def _strict_readiness_ready(args: argparse.Namespace) -> bool:
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=args.repo_root,
                home=args.memory_home or _env_memory_home() or Path.home(),
                include_discovered=False,
                probe_sqlite_counts=False,
            )
        )
    )
    report = kernel.adapter_readiness_report().to_json()
    summary = report.get("summary", {})
    return (
        report.get("status") == "ready"
        and summary.get("required_ready_count") == summary.get("required_surface_count")
        and int(summary.get("degraded_count", 0) or 0) == 0
        and int(summary.get("missing_adapter_count", 0) or 0) == 0
        and int(summary.get("uncovered_count", 0) or 0) == 0
        and int(summary.get("warning_count", 0) or 0) == 0
    )


def _validate_args(args: argparse.Namespace) -> str:
    if args.memory_surface and args.memory_home is None and _env_memory_home() is None:
        return "--memory-surface requires --memory-home or DHARMA_MEMORY_KERNEL_HOME"
    if args.memory_home is not None and not args.memory_surface:
        return "--memory-home requires at least one --memory-surface"
    if args.receipt_out and _is_memory_surface_output(args.receipt_out, args):
        return "burn-in receipt output paths under memory surfaces are not allowed"
    if args.summary_out and _is_memory_surface_output(args.summary_out, args):
        return "burn-in summary output paths under memory surfaces are not allowed"
    return ""


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _is_memory_surface_output(path: Path, args: argparse.Namespace) -> bool:
    resolved = _resolve_output(path, args.repo_root).expanduser().resolve()
    for root in _memory_surface_roots(args):
        try:
            resolved.relative_to(root.expanduser().resolve())
            return True
        except ValueError:
            continue
    return False


def _memory_surface_roots(args: argparse.Namespace) -> tuple[Path, ...]:
    home_roots = [Path.home()]
    env_home = _env_memory_home()
    if env_home is not None:
        home_roots.append(env_home)
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


def _env_memory_home() -> Path | None:
    raw = os.environ.get("DHARMA_MEMORY_KERNEL_HOME", "").strip()
    return Path(raw).expanduser() if raw else None


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "rollback"}


if __name__ == "__main__":
    raise SystemExit(main())
