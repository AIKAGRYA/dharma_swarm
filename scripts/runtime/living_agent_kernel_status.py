#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.operator_core.living_agent_kernel_status import living_agent_os_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Print LivingAgentKernel OS status.")
    parser.add_argument("--store-dir", type=Path, default=None)
    parser.add_argument("--now", default=None)
    parser.add_argument("--latest-limit", type=int, default=20)
    parser.add_argument("--stale-after-seconds", type=int, default=120)
    parser.add_argument("--offline-after-seconds", type=int, default=3600)
    args = parser.parse_args()

    status = living_agent_os_status(
        store_dir=args.store_dir,
        now=args.now,
        latest_limit=args.latest_limit,
        stale_after_seconds=args.stale_after_seconds,
        offline_after_seconds=args.offline_after_seconds,
    )
    print(json.dumps(status.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
