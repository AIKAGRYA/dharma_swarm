#!/usr/bin/env python3
"""Direct live model-routing verifier.

Default mode is a dry run: build the plan from the canonical model-status
projection and write a receipt without model calls. Live mode is fail-closed
unless ``DHARMA_LIVE_MODEL_E2E=1`` is set.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.model_routing_live_probe import (  # noqa: E402
    LIVE_MODEL_E2E_ENV,
    build_live_probe_matrix,
    write_live_probe_matrix,
)


def _default_output() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "reports/model_routing/live_probe" / f"{stamp}.json"


def _refresh_keys() -> None:
    for cmd in (["dkeys", "test"], [str(Path.home() / "bin" / "dkeys"), "test"]):
        try:
            subprocess.run(cmd, timeout=180, capture_output=True, text=True, check=False)
            return
        except (FileNotFoundError, subprocess.SubprocessError):
            continue


async def _amain() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="write a plan receipt without live calls")
    parser.add_argument("--live", action="store_true", help="make live model calls; requires opt-in env")
    parser.add_argument("--no-refresh", action="store_true", help="skip dkeys refresh before live planning")
    parser.add_argument("--output", type=Path, default=_default_output(), help="JSON receipt path")
    parser.add_argument("--profile", choices=("pong", "standard", "full"), default="standard")
    parser.add_argument("--limit", type=int, default=None, help="maximum number of live floor models to probe")
    parser.add_argument("--model", action="append", dest="models", help="logical model id to include")
    parser.add_argument("--timeout", type=int, default=90, help="per-call timeout in seconds")
    args = parser.parse_args()

    if args.live and args.dry_run:
        print("--dry-run and --live are mutually exclusive")
        return 2
    live_enabled = os.environ.get(LIVE_MODEL_E2E_ENV) == "1"
    if args.live and not live_enabled:
        print(f"refusing live model E2E: set {LIVE_MODEL_E2E_ENV}=1 to opt in")
        return 2
    if not args.live and not args.dry_run:
        args.dry_run = True

    if live_enabled and not args.no_refresh:
        _refresh_keys()
    elif not args.no_refresh:
        print(f"skipping `dkeys test`; set {LIVE_MODEL_E2E_ENV}=1 to refresh live key status")

    payload = await build_live_probe_matrix(
        live_calls_enabled=args.live,
        profile=args.profile,
        limit=args.limit,
        model_ids=args.models,
        timeout_seconds=args.timeout,
        working_dir=str(REPO_ROOT),
    )
    write_live_probe_matrix(payload, args.output)

    counts = payload["counts"]
    print(
        f"model_routing_live_probe [{payload['mode']}/{payload['profile']}] "
        f"{payload['status']}: planned={counts['planned_models']} "
        f"skipped={counts['skipped_models']} attempted={counts['live_calls_attempted']} "
        f"ok={counts['ok']} failed={counts['failed']}"
    )
    try:
        print(args.output.relative_to(REPO_ROOT))
    except ValueError:
        print(args.output)
    if args.live and payload["status"] != "passed":
        return 1
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
