#!/usr/bin/env python3
"""check_arena_replay.py — hermetic replay gate for Arena v1 (spec §3, §6).

Proves the arena is FROZEN and REPLAYABLE: running the same candidate genome
against the same frozen taskpack twice yields the identical scorecard hash,
closeout state, significance, and budget-parity ledger. No keys, no GPU, no
network — the default fixture-pool path is fully deterministic.

This is the anti-corruption guarantee (§6.1, §6.3): if the arena were not
byte-stable across runs, fitness could silently drift. Exit non-zero on any
divergence so CI catches a non-replayable arena.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.coordination.arena import ArenaRunner  # noqa: E402
from dharma_swarm.coordination.genome import OrchestrationGenome  # noqa: E402


def _candidate() -> OrchestrationGenome:
    return OrchestrationGenome(
        roster=[
            {"role_id": "r1", "member_id": "alpha-math", "kind": "model"},
            {"role_id": "r2", "member_id": "beta-code", "kind": "model"},
            {"role_id": "r3", "member_id": "gamma-logic", "kind": "model"},
        ],
        adjudication_rule="synthesize",
    )


def check() -> list[str]:
    """Return a list of findings (empty == replay is byte-stable)."""
    findings: list[str] = []
    candidate = _candidate()
    r1 = ArenaRunner().run(candidate)
    r2 = ArenaRunner().run(candidate)

    if r1["scorecard_hash"] != r2["scorecard_hash"]:
        findings.append(
            f"scorecard_hash diverged: {r1['scorecard_hash']} != {r2['scorecard_hash']}"
        )
    if r1["closeout_state"] != r2["closeout_state"]:
        findings.append(
            f"closeout_state diverged: {r1['closeout_state']} != {r2['closeout_state']}"
        )
    if r1["significance"] != r2["significance"]:
        findings.append("significance diverged across replays")
    if r1["budget_parity"] != r2["budget_parity"]:
        findings.append("budget_parity ledger diverged across replays")
    if r1["scorer_hash"] != r2["scorer_hash"]:
        findings.append("scorer_hash diverged (scorer is not frozen)")
    if r1["task_manifest_hash"] != r2["task_manifest_hash"]:
        findings.append("task_manifest_hash diverged (frozen slice moved)")
    if r1["sealed_oracle_hash"] != r2["sealed_oracle_hash"]:
        findings.append("sealed_oracle_hash diverged (sealed labels drifted)")
    # Budget parity must be logged for the candidate AND every control (§6.3).
    for arm in (
        "candidate",
        "best_single_full_budget",
        "same_budget_self_moa",
        "random_or_static_ensemble",
    ):
        if arm not in r1["budget_parity"]:
            findings.append(f"budget parity not logged for arm: {arm}")
    return findings


def main() -> int:
    findings = check()
    if findings:
        print("check_arena_replay: FAIL")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("check_arena_replay: OK — arena is frozen and replayable (hermetic).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
