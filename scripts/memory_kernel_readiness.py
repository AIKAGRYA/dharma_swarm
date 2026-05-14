#!/usr/bin/env python3
"""Run a CI-friendly MemoryKernel adapter readiness report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.memory_kernel import CensusConfig, MemoryKernel, MemoryKernelConfig
from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--require-surface", action="append", default=[])
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--probe-counts", action="store_true")
    parser.add_argument("--default-limit", type=int, default=100)
    parser.add_argument("--max-files", type=int, default=100)
    parser.add_argument("--max-lines-per-file", type=int, default=100)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--fail-on-missing-adapter", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=args.repo_root,
                home=args.home,
                include_discovered=args.discover,
                probe_sqlite_counts=args.probe_counts,
            ),
            adapter=ReadOnlyAdapterConfig(
                default_limit=args.default_limit,
                max_files=args.max_files,
                max_lines_per_file=args.max_lines_per_file,
            ),
        )
    )
    report = kernel.adapter_readiness_report(
        required_surface_ids=tuple(args.require_surface) or None
    )
    payload_text = json.dumps(report.to_json(), indent=2, sort_keys=True)
    print(payload_text)

    if not args.dry_run and args.output_json:
        output_json = _resolve_output(args.output_json, args.repo_root)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(payload_text + "\n", encoding="utf-8")

    if args.strict and report.status != "ready":
        return 5
    if (
        args.fail_on_missing_adapter
        and report.summary.get("missing_adapter_count", 0) > 0
    ):
        return 5
    return 0


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
