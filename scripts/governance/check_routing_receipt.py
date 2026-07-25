#!/usr/bin/env python3
"""check_routing_receipt.py — hermetic gate for orchestrator route receipts
(spec §6.7, §10 step 4).

Proves two things about the zero-weight orchestrator:
  * Every evaluated genome leaves a well-formed route receipt — routing cannot
    hide failures (§6.7): each receipt carries genome_id, lineage, adjudication,
    roster, closeout_state, and the behavioral cell.
  * NO production-router mutation: the orchestrator module must not import the
    production routing surfaces (provider_policy / model_hierarchy / model_pool /
    orchestrator.py / the routers). It consults the arena roster registry only.

Hermetic, no keys/GPU/network. Exit non-zero on any violation.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.coordination.orchestrator_v1 import ZeroWeightOrchestratorV1  # noqa: E402

_ORCH_SRC = ROOT / "dharma_swarm" / "coordination" / "orchestrator_v1.py"
_FORBIDDEN_IMPORTS = (
    "provider_policy",
    "model_hierarchy",
    "model_pool",
    "model_defaults",
    "runtime_provider",
    "smart_router",
    "router_v1",
    "decision_router",
)
_REQUIRED_RECEIPT_FIELDS = (
    "generation",
    "genome_id",
    "parent_genome_id",
    "mutation_op",
    "adjudication_rule",
    "roster",
    "closeout_state",
    "score",
    "archived",
    "behavioral_cell",
)


def _imported_modules(src: str) -> list[str]:
    tree = ast.parse(src)
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
        elif isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
    return mods


def check() -> list[str]:
    findings: list[str] = []

    # 1. No production-router mutation: import boundary.
    mods = _imported_modules(_ORCH_SRC.read_text(encoding="utf-8"))
    for mod in mods:
        for bad in _FORBIDDEN_IMPORTS:
            if bad in mod:
                findings.append(f"orchestrator imports production routing surface: {mod}")
        if mod.endswith("dharma_swarm.orchestrator"):
            findings.append(f"orchestrator imports the production orchestrator: {mod}")

    # 2. Route receipts well-formed for every evaluated genome.
    result = ZeroWeightOrchestratorV1(seed=11).evolve(generations=6)
    if not result.route_receipts:
        findings.append("orchestrator produced no route receipts")
    if len(result.route_receipts) != result.evaluated:
        findings.append("route receipts do not cover every evaluated genome (failures hidden?)")
    for r in result.route_receipts:
        for fld in _REQUIRED_RECEIPT_FIELDS:
            if fld not in r:
                findings.append(f"route receipt missing field '{fld}'")
                break
    return findings


def main() -> int:
    findings = check()
    if findings:
        print("check_routing_receipt: FAIL")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("check_routing_receipt: OK — receipts complete; no production-router mutation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
