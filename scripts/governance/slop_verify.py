#!/usr/bin/env python3
"""Read-only slop score wrapper for normalized findings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.slop import (  # noqa: E402
    SlopFinding,
    SlopLedgerEntry,
    score_module,
    route_probability,
)


def load_findings(path: Path) -> list[SlopFinding]:
    findings: list[SlopFinding] = []
    if not path.exists():
        return findings
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        findings.append(SlopFinding.model_validate(json.loads(line)))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="Module path to score")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="JSONL file of normalized SlopFinding rows",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )
    args = parser.parse_args()

    findings = load_findings(args.input) if args.input else []
    module = score_module(args.path, findings)
    decision = route_probability(
        module.slop_probability,
        introduced=module.introduced,
    )
    entry = SlopLedgerEntry(module=module, decision=decision)

    if args.format == "json":
        print(entry.model_dump_json(indent=2))
    else:
        print(
            f"{module.path}: p={module.slop_probability:.2f} "
            f"action={decision.action.value} blocks={decision.blocks}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
