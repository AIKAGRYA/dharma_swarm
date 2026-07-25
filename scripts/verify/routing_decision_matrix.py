#!/usr/bin/env python3
"""Write the hermetic routing decision matrix receipt."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.routing_decision_matrix import write_routing_decision_matrix


def _default_output() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "reports/model_routing/routing_decision_matrix" / f"{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output(),
        help="Path for the JSON receipt.",
    )
    args = parser.parse_args()
    payload = write_routing_decision_matrix(args.output)
    print(
        f"routing decision matrix {payload['status']}: "
        f"{payload['counts']['passed']} passed, {payload['counts']['failed']} failed"
    )
    print(args.output)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
