#!/usr/bin/env python3
"""Write DharmaVerifier-Ranker v0 schema artifacts from package constants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.verifier_ranker_v0.schemas import (  # noqa: E402
    MODEL_OUTPUT_SCHEMA,
    SEMANTIC_RECEIPT_GRAPH_SCHEMA,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="reports/agentops/verifier_ranker_v0")
    args = parser.parse_args()
    out_dir = REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        "DHARMA_SEMANTIC_RECEIPT_GRAPH_V0.schema.json": SEMANTIC_RECEIPT_GRAPH_SCHEMA,
        "DHARMA_VERIFIER_RANKER_OUTPUT_V0.schema.json": MODEL_OUTPUT_SCHEMA,
    }
    for name, schema in targets.items():
        path = out_dir / name
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
