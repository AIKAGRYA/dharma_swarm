#!/usr/bin/env python3
"""arena_truth_report.py — read-only governance report surface for Arena v1.

Track ``orchestration-arena-v1-2026-06`` next-items 1 + 3: wire the arena
scorecard + DPI receipts into a governance-visible report surface, and connect
arena winners to the cold-start trace corpus (labels only, zero weights).

READ-ONLY doctrine: this script consumes only the frozen hermetic fixture pool
and deterministic scorer. It mutates no production state, no archive fitness,
no routing. Everything is seeded and replayable: ``--check`` re-derives the
entire report in memory and fails if the committed surface disagrees — a
receipt that cannot replay is not evidence.

NO CAPABILITY CLAIM: numbers here are hermetic-harness lift on the frozen
synthetic taskpack — a falsifiable existence proof that the control machinery
(best-single gate, budget parity, significance, Council corroboration) works.
They are NOT a production benchmark result. Capability claims stay forbidden
until live-lane arena runs carry the same controls (track non-goal 1); trust
gate C2 remains owned by real benchmark evidence, never by this surface.

Usage:
    python3 scripts/governance/arena_truth_report.py            # write surface
    python3 scripts/governance/arena_truth_report.py --check    # verify replay
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json  # noqa: E402

from dharma_swarm.coordination.arena.corpus import (  # noqa: E402
    build_cold_start_corpus,
    corpus_sha256,
    render_corpus_jsonl,
)
from dharma_swarm.coordination.arena.runner import render_decision_packet  # noqa: E402
from dharma_swarm.coordination.arena.taskpack import TASK_PACK_ID  # noqa: E402
from dharma_swarm.coordination.orchestrator_v1 import (  # noqa: E402
    ZeroWeightOrchestratorV1,
)
from dharma_swarm.memory_kernel.write_receipts import (  # noqa: E402
    stable_digest,
    utc_now,
)

REPORT_SCHEMA = "arena_truth_report.v1"
DEFAULT_OUT_DIR = ROOT / "reports" / "governance" / "arena"
RECEIPT_NAME = "arena_truth_receipt.json"
MARKDOWN_NAME = "ARENA_TRUTH.md"
CORPUS_NAME = "cold_start_corpus.jsonl"

# Frozen replay parameters — changing them is a new report epoch, not drift.
SEED = 0
GENERATIONS = 12

CAPABILITY_CLAIM = (
    "none — hermetic fixture harness only. The fixture pool is CONSTRUCTED so "
    "that specialist routing beats best-single (Krogh-Vedelsby by design), so "
    "the lift shown is a control-machinery existence proof on the frozen "
    "synthetic taskpack, NOT a production capability claim (track non-goal 1) "
    "and NOT commensurable with trust-gate C2 (which reads only live "
    "benchmark runs). Live-lane runs must carry the same best-single + "
    "budget-parity + significance controls before any claim."
)

# Volatile receipt fields excluded from replay comparison (never from digest).
_VOLATILE_KEYS = ("generated_at", "digest")


def build_report() -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Deterministically derive (receipt_core, corpus_rows, decision_packet_md)."""
    orch = ZeroWeightOrchestratorV1(seed=SEED)
    result = orch.evolve(generations=GENERATIONS)
    best = result.best
    if best is None:  # 24-task pack + seeded search always yields elites
        raise RuntimeError("arena evolution produced no archive elites")
    run = orch.runner.run(best.genome)
    power = run["_power_index"]
    corpus_rows = build_cold_start_corpus(orch.runner, result.archive.winners())

    receipt_core: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "hermetic": True,
        "capability_claim": CAPABILITY_CLAIM,
        "seed": SEED,
        "generations": GENERATIONS,
        "evaluated": result.evaluated,
        "archive_cells": len(result.archive.cells),
        "winners": len(result.archive.winners()),
        "task_pack_id": TASK_PACK_ID,
        "task_manifest_hash": run["task_manifest_hash"],
        "scorer_hash": run["scorer_hash"],
        "sealed_oracle_hash": run["sealed_oracle_hash"],
        "best": {
            "genome_id": best.genome.genome_id,
            "adjudication_rule": best.genome.adjudication_rule,
            "roster": [m.member_id for m in best.genome.roster],
            "behavioral_cell": list(best.genome.behavioral_descriptors.bin_key()),
            "closeout_state": run["closeout_state"],
            "council_verdict": run["council_verdict"],
            "arm_scores": run["arm_scores"],
            "budget_ref": run["budget_ref"],
            "budget_parity": run["budget_parity"],
            "significance": run["significance"],
            "scorecard_hash": run["scorecard_hash"],
            "dpi": {
                "dpi": power["dpi"],
                "verified_capability_delta": power["verified_capability_delta"],
                "decorrelation_bonus": power["decorrelation_bonus"],
                "trust_multiplier": power["trust_multiplier"],
                "final_correct": power["final_correct"],
                "learning_active": power["learning_active"],
            },
        },
        "corpus": {
            "path": CORPUS_NAME,
            "rows": len(corpus_rows),
            "sha256": corpus_sha256(corpus_rows),
        },
    }
    packet_md = render_decision_packet(run, power)
    return receipt_core, corpus_rows, packet_md


def render_markdown(receipt: dict[str, Any], packet_md: str) -> str:
    best = receipt["best"]
    sig = best["significance"]
    lines = [
        "# Arena Truth — governance report surface (read-only)",
        "",
        f"**Schema:** `{receipt['schema']}` · **Generated:** {receipt['generated_at']}",
        f"**Replay:** `python3 scripts/governance/arena_truth_report.py --check`",
        "",
        "> **NO CAPABILITY CLAIM.** " + receipt["capability_claim"],
        "",
        "## Search summary (zero-weight, seeded, hermetic)",
        "",
        f"- seed `{receipt['seed']}` · generations {receipt['generations']} · "
        f"genomes evaluated {receipt['evaluated']}",
        f"- MAP-Elites cells illuminated: {receipt['archive_cells']} · "
        f"winners (positive_lift_candidate): {receipt['winners']}",
        f"- best genome: `{best['genome_id']}` "
        f"({best['adjudication_rule']} over {', '.join(best['roster'])})",
        f"- observed lift vs best-single at parity: {sig['observed_lift']:.4f} "
        f"(p={sig['p_value']:.4f}, significant={sig['significant']}, n={sig['n']})",
        f"- cold-start corpus: {receipt['corpus']['rows']} labeled trace rows "
        f"(`{receipt['corpus']['path']}`, sha256 `{receipt['corpus']['sha256'][:16]}…`) "
        "— labels only, zero training (v1 doctrine)",
        "",
        "---",
        "",
        packet_md.rstrip(),
        "",
    ]
    return "\n".join(lines) + "\n"


def write_surface(out_dir: Path) -> dict[str, Any]:
    """Write receipt + markdown + corpus. Returns the stamped receipt."""
    receipt_core, corpus_rows, packet_md = build_report()
    receipt = dict(receipt_core)
    receipt["generated_at"] = utc_now()
    receipt["digest"] = stable_digest(
        {k: v for k, v in receipt.items() if k != "digest"}
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / CORPUS_NAME).write_text(
        render_corpus_jsonl(corpus_rows), encoding="utf-8"
    )
    (out_dir / MARKDOWN_NAME).write_text(
        render_markdown(receipt, packet_md), encoding="utf-8"
    )
    return receipt


def check(out_dir: Path) -> list[str]:
    """Verify the committed surface replays exactly. Empty list == verified."""
    findings: list[str] = []
    receipt_path = out_dir / RECEIPT_NAME
    corpus_path = out_dir / CORPUS_NAME
    md_path = out_dir / MARKDOWN_NAME
    if not receipt_path.exists():
        return [f"receipt missing: {receipt_path}"]
    try:
        committed = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"receipt is not valid JSON: {receipt_path}"]

    stored = str(committed.get("digest", ""))
    recomputed = stable_digest({k: v for k, v in committed.items() if k != "digest"})
    if stored != recomputed:
        findings.append("receipt digest mismatch (tampered or hand-edited)")

    fresh_core, fresh_rows, _ = build_report()
    for key, fresh_value in fresh_core.items():
        if committed.get(key) != fresh_value:
            findings.append(
                f"receipt field {key!r} does not replay (committed surface is stale "
                "— rerun scripts/governance/arena_truth_report.py)"
            )
    for key in committed:
        if key not in fresh_core and key not in _VOLATILE_KEYS:
            findings.append(f"receipt carries unknown field {key!r}")

    if not corpus_path.exists():
        findings.append(f"corpus missing: {corpus_path}")
    elif corpus_path.read_text(encoding="utf-8") != render_corpus_jsonl(fresh_rows):
        findings.append("cold-start corpus does not replay byte-for-byte")

    if not md_path.exists():
        findings.append(f"markdown surface missing: {md_path}")
    else:
        md = md_path.read_text(encoding="utf-8")
        if fresh_core["best"]["genome_id"] not in md:
            findings.append("markdown surface does not name the replayed best genome")
        if "NO CAPABILITY CLAIM" not in md:
            findings.append("markdown surface lost the no-capability-claim boundary")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="verify the committed surface replays exactly (write nothing)",
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT_DIR,
        help="report surface directory (default: reports/governance/arena)",
    )
    args = parser.parse_args(argv)

    if args.check:
        findings = check(args.out)
        if findings:
            print("arena_truth_report --check: FAIL")
            for f in findings:
                print(f"  - {f}")
            return 1
        print("arena_truth_report --check: OK — surface replays exactly (hermetic).")
        return 0

    receipt = write_surface(args.out)
    best = receipt["best"]
    print(f"arena_truth_report: wrote {args.out / RECEIPT_NAME}")
    print(
        f"  best={best['genome_id']} closeout={best['closeout_state']} "
        f"lift={best['significance']['observed_lift']:.4f} "
        f"(p={best['significance']['p_value']:.4f}) "
        f"corpus_rows={receipt['corpus']['rows']}"
    )
    print(f"  capability_claim: {receipt['capability_claim'][:60]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
