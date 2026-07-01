#!/usr/bin/env python3
"""Write the DharmaVerifier-Ranker v0 metadata-only data inventory receipt."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.verifier_ranker_v0.inventory import build_inventory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/agentops/verifier_ranker_v0/DATA_INVENTORY_RECEIPT_20260701.json")
    args = parser.parse_args()

    inventory = build_inventory(repo_root=REPO_ROOT)
    inventory["created_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    inventory["repo_root"] = str(REPO_ROOT)
    inventory["raw_private_body_readout"] = False
    inventory["status"] = "pass_metadata_inventory_written"
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
