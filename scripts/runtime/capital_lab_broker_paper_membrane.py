#!/usr/bin/env python3
"""Emit Goal B broker-paper membrane fixture receipts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.capital_lab.broker_paper_membrane import run_goal_b_proof_loop


DEFAULT_OUTPUT_DIR = Path(
    "reports/capital_lab/goal-b-broker-paper-execution-membrane-continuation-20260605T141918Z"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for builder packets and receipts.",
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=None,
        help="Optional durable ledger path. Defaults inside output-dir.",
    )
    args = parser.parse_args()
    result = run_goal_b_proof_loop(args.output_dir, ledger_path=args.ledger_path)
    print(json.dumps(result["manifest"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
