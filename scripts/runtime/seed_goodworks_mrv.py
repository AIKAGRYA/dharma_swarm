#!/usr/bin/env python3
"""Seed local Goodworks MRV pilot rows without writing secrets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.goodworks_dgm.seed import seed_goodworks_mrv_pilot


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed local Goodworks MRV pilot rows.")
    parser.add_argument("--ledger-root", type=Path, default=None)
    args = parser.parse_args()
    result = seed_goodworks_mrv_pilot(ledger_root=args.ledger_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
