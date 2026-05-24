#!/usr/bin/env python3
"""Run the MemoryKernel M0 surface census."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.memory_kernel import CensusConfig, MemorySurfaceCensus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Opt into bounded discovery of additional SQLite/JSONL surfaces.",
    )
    parser.add_argument("--no-discovery", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--probe-counts", action="store_true")
    parser.add_argument("--max-discovered", type=int, default=256)
    parser.add_argument("--max-discovery-entries", type=int, default=4096)
    parser.add_argument("--max-dir-entries", type=int, default=2048)
    parser.add_argument("--max-dir-depth", type=int, default=2)
    parser.add_argument(
        "--allow-memory-surface-output",
        action="store_true",
        help="Allow report output paths inside known memory roots.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = CensusConfig(
        repo_root=args.repo_root,
        home=args.home,
        include_discovered=args.discover and not args.no_discovery,
        probe_sqlite_counts=args.probe_counts,
        max_discovered=args.max_discovered,
        max_discovery_entries=args.max_discovery_entries,
        max_dir_entries=args.max_dir_entries,
        max_dir_depth=args.max_dir_depth,
        allow_memory_surface_output=args.allow_memory_surface_output,
    )
    census = MemorySurfaceCensus(config)
    result = census.run_result()
    summary = census.summarize_surface_health(result)
    print(json.dumps(summary, indent=2, sort_keys=True))

    if args.dry_run:
        return 0

    if args.output_json:
        census.write_json(_resolve_output(args.output_json, args.repo_root), result)
    if args.output_md:
        census.write_markdown(_resolve_output(args.output_md, args.repo_root), result)
    return 0


def _resolve_output(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


if __name__ == "__main__":
    raise SystemExit(main())
