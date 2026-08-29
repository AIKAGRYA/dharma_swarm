#!/usr/bin/env python3
"""Run a hermetic five-cycle Foundry supervisor pilot (zero provider calls)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dharma_swarm.foundry.pilot import run_five_cycle_pilot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--max-proposals-per-run", type=int, default=2)
    parser.add_argument("--max-spend-usd", type=float, default=0.0)
    args = parser.parse_args(argv)
    summary = run_five_cycle_pilot(
        state_root=args.state_root,
        repo_root=args.repo_root,
        runs=args.runs,
        max_proposals_per_run=args.max_proposals_per_run,
        max_spend_usd=args.max_spend_usd,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
