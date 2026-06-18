#!/usr/bin/env python3
"""Receipt-producing A2A model-council verifier.

Default mode is a dry run that plans a three-stage A2A council from canonical
model status. Live mode requires ``DHARMA_LIVE_MODEL_E2E=1`` before any model
runtime is constructed or called.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.model_council_e2e import (  # noqa: E402
    build_model_council_receipt,
    write_model_council_receipt,
)
from dharma_swarm.model_status import LIVE_MODEL_E2E_ENV  # noqa: E402


def _default_output() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "reports/model_routing/model_council" / f"{stamp}.json"


def _refresh_keys() -> None:
    for cmd in (["dkeys", "test"], [str(Path.home() / "bin" / "dkeys"), "test"]):
        try:
            subprocess.run(cmd, timeout=180, capture_output=True, text=True, check=False)
            return
        except (FileNotFoundError, subprocess.SubprocessError):
            continue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="write a plan receipt without live calls")
    parser.add_argument("--live", action="store_true", help="run the live A2A council; requires opt-in env")
    parser.add_argument("--no-refresh", action="store_true", help="skip dkeys refresh before planning")
    parser.add_argument("--output", type=Path, default=_default_output(), help="JSON receipt path")
    parser.add_argument("--timeout", type=int, default=120, help="per-model timeout in seconds")
    parser.add_argument("--model", action="append", dest="models", help="logical model id to include")
    parser.add_argument(
        "--topic",
        default="Assess whether DharmaSwarm model routing is ready to advertise current floor models.",
        help="Council task topic.",
    )
    args = parser.parse_args()

    if args.live and args.dry_run:
        print("--dry-run and --live are mutually exclusive")
        return 2
    live_enabled = os.environ.get(LIVE_MODEL_E2E_ENV) == "1"
    if args.live and not live_enabled:
        print(f"refusing live model council E2E: set {LIVE_MODEL_E2E_ENV}=1 to opt in")
        return 2
    if not args.live and not args.dry_run:
        args.dry_run = True

    if live_enabled and not args.no_refresh:
        _refresh_keys()
    elif not args.no_refresh:
        print(f"skipping `dkeys test`; set {LIVE_MODEL_E2E_ENV}=1 to refresh live key status")

    payload = build_model_council_receipt(
        live_calls_enabled=args.live,
        topic=args.topic,
        timeout_seconds=args.timeout,
        working_dir=str(REPO_ROOT),
        model_ids=args.models,
    )
    write_model_council_receipt(payload, args.output)
    counts = payload["counts"]
    print(
        f"model_council_e2e [{payload['mode']}] {payload['status']}: "
        f"planned={counts['planned_agents']} unique_providers={counts['unique_planned_providers']} "
        f"attempted={counts['live_calls_attempted']} completed={counts['completed_stages']} "
        f"failed={counts['failed_stages']}"
    )
    try:
        print(args.output.relative_to(REPO_ROOT))
    except ValueError:
        print(args.output)
    if args.live and payload["status"] != "passed":
        return 1
    if payload["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
