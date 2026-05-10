#!/usr/bin/env python3
"""Run BhedGnanMonitor v0 on resident-intelligence text artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.bhed_gnan_monitor import BhedGnanMonitor, DEFAULT_WITNESS_DIR  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run BhedGnanMonitor v0.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--witness-dir", type=Path, default=DEFAULT_WITNESS_DIR)
    parser.add_argument("--write-witness", action="store_true")
    parser.add_argument(
        "--resolution",
        choices=("whole", "section", "paragraph", "all"),
        default="whole",
        help="Analyze whole files, markdown sections, paragraphs, or all three.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    monitor = BhedGnanMonitor(witness_dir=args.witness_dir)
    resolutions = (
        ("whole", "section", "paragraph")
        if args.resolution == "all"
        else (args.resolution,)
    )
    results = [
        result
        for path in args.paths
        for result in monitor.analyze_file_segments(path, resolutions=resolutions)
    ]
    if args.write_witness:
        witness_path = monitor.write_witness(results)
    else:
        witness_path = None
    payload = {
        "witness_path": str(witness_path) if witness_path else "",
        "results": [result.to_json() for result in results],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
