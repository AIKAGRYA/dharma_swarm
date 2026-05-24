#!/usr/bin/env python3
"""Render a read-only Memory Kernel context pack."""

from __future__ import annotations

import argparse
from pathlib import Path

from dharma_swarm.memory_kernel import (
    CensusConfig,
    MemoryContextBudget,
    MemoryKernel,
    MemoryKernelConfig,
    MemoryQuery,
    TruthState,
    render_memory_context_pack_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--surface-id", action="append", default=[])
    parser.add_argument("--candidate-limit", type=int, default=24)
    parser.add_argument("--admitted-limit", type=int, default=8)
    parser.add_argument("--include-discovered", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=Path(args.repo_root),
                home=Path(args.home).expanduser(),
                include_discovered=bool(args.include_discovered),
            )
        )
    )
    pack = kernel.preview_memory_pack(
        surface_ids=tuple(args.surface_id) or None,
        query=MemoryQuery(
            limit_total=max(1, args.candidate_limit),
            limit_per_surface=max(1, args.candidate_limit),
            include_content=True,
            include_high_risk=False,
            include_projections=False,
            include_unsafe=False,
            require_source_digest=True,
            require_source_row_key=True,
        ),
        budget=MemoryContextBudget(
            max_candidate_atoms=max(1, args.candidate_limit),
            max_admitted_atoms=max(1, args.admitted_limit),
            max_total_chars=4000,
            max_atom_chars=600,
            include_content=True,
            require_context_admissible=False,
            allow_projections=False,
            allow_high_risk=False,
            allowed_truth_states=(
                TruthState.OBSERVED,
                TruthState.CLAIMED,
                TruthState.CURATED,
                TruthState.CANONICAL,
            ),
        ),
    )
    if args.query:
        print(f"# Memory Kernel Context Query\n\nQuery: `{args.query}`\n")
    print(render_memory_context_pack_markdown(pack))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
