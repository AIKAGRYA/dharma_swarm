#!/usr/bin/env python3
"""Plan/apply lossless quarantine of broken pre-v2 Foundry evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dharma_swarm.foundry.receipts import quarantine_legacy_state  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="move evidence losslessly and write QUARANTINE; default is plan-only",
    )
    args = parser.parse_args(argv)
    plan = quarantine_legacy_state(args.state_root, apply=args.apply)
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0 if not plan["needed"] or args.apply else 1


if __name__ == "__main__":
    raise SystemExit(main())
