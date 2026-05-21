#!/usr/bin/env python3
"""Run a Goodworks DGM dry-run or shadow tick.

Default behavior is one dry-run tick. No live mutation mode is exposed here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dharma_swarm.goodworks_dgm.models import MutationMode
from dharma_swarm.goodworks_dgm.runtime import (
    run_goodworks_dgm_loop,
    run_goodworks_dgm_tick,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Goodworks DGM tick loop.")
    parser.add_argument("--state-dir", type=Path, default=None)
    parser.add_argument("--ledger-root", type=Path, default=None)
    parser.add_argument("--shadow", action="store_true", help="Run DGM in shadow mode.")
    parser.add_argument("--seed-pilot", action="store_true", help="Seed local pilot MRV rows first.")
    parser.add_argument("--loop", action="store_true", help="Run multiple ticks.")
    parser.add_argument("--ticks", type=int, default=1)
    parser.add_argument("--interval-seconds", type=float, default=900.0)
    args = parser.parse_args()

    mode = MutationMode.SHADOW if args.shadow else MutationMode.DRY_RUN
    if args.loop:
        payload = asyncio.run(
            run_goodworks_dgm_loop(
                interval_seconds=args.interval_seconds,
                max_ticks=max(1, args.ticks),
                mutation_mode=mode,
                state_dir=args.state_dir,
                ledger_root=args.ledger_root,
                seed_pilot=args.seed_pilot,
            )
        )
    else:
        payload = asyncio.run(
            run_goodworks_dgm_tick(
                mutation_mode=mode,
                state_dir=args.state_dir,
                ledger_root=args.ledger_root,
                seed_pilot=args.seed_pilot,
            )
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
