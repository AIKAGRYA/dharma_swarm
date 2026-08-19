#!/usr/bin/env python3
"""Operator entrypoint for the non-stop Foundry engine.

Runs the bounded-continuous loop on an always-on host. Halts on the kill-switch,
on budget exhaustion, or on any KILL kill-metric verdict; writes a kill-metrics
snapshot + walking-brief fragment every cycle. Default is the hermetic dry-run
cycle (no keys/network) so it is safe to stand up immediately; live model
generation is enabled by wiring provider keys and a live cycle (see
docs/foundry/RUNNING_NONSTOP.md).

    python3 scripts/foundry/foundry_daemon.py --max-cycles 0 --interval-seconds 300
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dharma_swarm.foundry.daemon import DaemonConfig, run_daemon, state_json  # noqa: E402
from dharma_swarm.foundry.targets import TARGET_REGISTRY  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", default=",".join(TARGET_REGISTRY),
                        help="comma-separated target ids to rotate")
    parser.add_argument("--cycle-generations", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--max-cycles", type=int, default=0, help="0 = run forever until a HALT")
    parser.add_argument("--budget", type=float, default=300.0)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--mode", choices=["dry", "live", "campaign"], default="dry",
                        help="dry = synthetic proposer (default); live = heartbeat benchmark "
                             "with real model calls; campaign = REAL bounded campaigns per "
                             "cycle (pinned target, docker oracle, live army, receipts)")
    args = parser.parse_args(argv)

    cycle_fn = None
    if args.mode == "live":
        from dharma_swarm.foundry.live import live_daemon_cycle  # noqa: PLC0415
        cycle_fn = live_daemon_cycle
    elif args.mode == "campaign":
        from dharma_swarm.foundry.campaign_cycle import real_campaign_cycle  # noqa: PLC0415
        cycle_fn = real_campaign_cycle

    config = DaemonConfig(
        targets=[t.strip() for t in args.targets.split(",") if t.strip()],
        cycle_generations=args.cycle_generations,
        interval_seconds=args.interval_seconds,
        max_cycles=args.max_cycles,
        budget_cap_usd=args.budget,
        state_root=args.state_root,
    )
    state = run_daemon(config) if cycle_fn is None else run_daemon(config, cycle_fn=cycle_fn)
    print(state_json(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
