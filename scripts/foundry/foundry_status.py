#!/usr/bin/env python3
"""Validate Foundry health from current evidence, never a stale best score."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dharma_swarm.foundry.status import assess_status  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inferred_repo = Path(__file__).resolve().parents[2]
    parser.add_argument("--repo-root", type=Path, default=inferred_repo)
    parser.add_argument(
        "--expected-sha",
        default=os.environ.get("FOUNDRY_EXPECTED_SHA", ""),
        help="exact 40-character release SHA installed by install_service.sh",
    )
    parser.add_argument(
        "--state-root", type=Path, default=Path.home() / ".dharma" / "foundry"
    )
    parser.add_argument("--max-heartbeat-age-seconds", type=float, default=900.0)
    parser.add_argument("--max-receipt-age-seconds", type=float, default=86_400.0)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    payload, exit_code = assess_status(
        repo_root=args.repo_root,
        state_root=args.state_root,
        expected_sha=args.expected_sha,
        max_heartbeat_age_seconds=args.max_heartbeat_age_seconds,
        max_receipt_age_seconds=args.max_receipt_age_seconds,
    )
    print(json.dumps(
        payload,
        indent=None if args.compact else 2,
        sort_keys=True,
        allow_nan=False,
    ))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
