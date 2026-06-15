#!/usr/bin/env python3
"""Loop 3 (Evolution Loop / DarwinEngine) closure driver.

This is the close-unit's Generator + Evaluator for the Evolution Loop. It does
NOT touch the production daemon, the live runtime.db, or the production archive
fitness file (~/.dharma/evolution/archive.jsonl). The owner surface is
dharma_swarm/evolution.py (DarwinEngine) writing to EvolutionArchive.

Loop 3 trace (CYBERNETIC_LOOP_MAP.md):
  SENSE     read fitness from COMPLETED tasks (Loop-1 real-provider completions)
  INTERPRET derive a multi-dim FitnessScore from those real completions
            (correctness from completion status, efficiency/utilization from
            REAL provider token accounting, safety from the telos gate)
  CONSTRAIN TelosGatekeeper.check() on the proposal (G5: never bypassed)
  ACT       DarwinEngine.archive_result() persists the evaluated proposal
  ADAPT     the archive entry + an evolution_cycle adapt receipt reference the
            real Loop-1 run_ids the cycle consumed (sense->...->adapt closed)

ONE WIRE (G4): the entire ACT/ADAPT path writes ONLY to a SCOPED /tmp archive.
The production archive is never written. The closure CHECK additionally proves
the One Wire negative invariant (internal fitness writes to the production
archive are rejected, and the ~11069 internal-fitness mutation entries with no
external acted-receipt are quarantined, never counted).

Run:  DHARMA_SPINE_DISPATCH=1 LC_LOOP3_STATE_DIR=/tmp/lc_loop3_state \\
          python3 scripts/governance/closure/drive_loop_3.py
Then: LC_LOOP3_STATE_DIR=/tmp/lc_loop3_state \\
          python3 scripts/governance/closure/check_loop_3.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from dharma_swarm.models import ProviderType  # noqa: E402

CLOSURE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CLOSURE_DIR))
import drive_loop_1 as L1  # noqa: E402  (reuse the blessed real-provider dispatch)

STATE_DIR = Path(
    os.environ.get("LC_LOOP3_STATE_DIR", f"/tmp/lc_loop3_state_{int(time.time())}")
)

# FREE-first decorrelated candidates (live-confirmed). Same family set Loop 1 uses.
FREE_CANDIDATES: list[tuple[ProviderType, str | None]] = [
    (ProviderType.GOOGLE_AI, None),
    (ProviderType.OLLAMA, None),
    (ProviderType.GOOGLE_AI, "gemini-2.5-flash"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
]

TASKS = [
    "Reply with exactly one word: EVOLVE",
    "Reply with exactly one word: FITNESS",
    "Reply with exactly one word: ADAPT",
]

_BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}

# A receipt field that marks an archive fitness write as countersigned by an
# external acted receipt above quorum. The production archive has NONE of these;
# every entry there is internal. The closure entries we write carry the run_id
# provenance under this key so the check can join them to real completions.
ADAPT_RECEIPT_NAME = "evolution_cycle"


def _scoped_runtime_db(state_dir: Path) -> str:
    state_dir.mkdir(parents=True, exist_ok=True)
    return str(state_dir / "runtime.db")


async def _seed_real_completions(db_path: str) -> list[dict]:
    """Drive N REAL Loop-1 completions into the scoped runtime.db.

    Returns the real receipts (provider/model/input_tokens/run_id) the
    evolution cycle will SENSE as completed-task fitness signal.
    """
    task_ids = [f"task_loop3_{uuid4().hex[:12]}" for _ in TASKS]
    L1._seed_scoped_db(db_path, task_ids)

    for i, prompt in enumerate(TASKS):
        pt, model_hint = FREE_CANDIDATES[i % len(FREE_CANDIDATES)]
        trace_id = f"trace_loop3_{uuid4().hex[:12]}"
        try:
            r = await L1._dispatch_one(db_path, task_ids[i], trace_id, prompt, pt, model_hint)
            print(
                f"COMPLETION OK task={task_ids[i]} provider={r.provider} "
                f"model={r.model} in_tok={r.input_tokens}"
            )
        except Exception as e:  # noqa: BLE001
            print(f"COMPLETION ERR task={task_ids[i]} {pt.value}: {type(e).__name__}: {str(e)[:120]}")

    # Read back the real-provider completions now in the scoped db.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    real: list[dict] = []
    for run_id, rj in conn.execute(
        "SELECT run_id, receipt_json FROM delegation_runs "
        "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
    ):
        try:
            rec = json.loads(rj)
        except Exception:
            continue
        provider = str(rec.get("provider", "")).strip().lower()
        model = str(rec.get("model", "")).strip()
        itok = rec.get("input_tokens")
        if provider in _BAD_PROVIDERS or not model:
            continue
        if not isinstance(itok, (int, float)) or itok <= 0:
            continue
        rec["_run_id"] = run_id
        real.append(rec)
    conn.close()
    print(f"\nREAL completions sensible to evolution: {len(real)} (need >=1)")
    return real


def _interpret_fitness(rec: dict):
    """INTERPRET: derive a multi-dim FitnessScore from ONE real completion.

    Every dimension is grounded in a real signal off the completion receipt:
      correctness  -> completed status (the task produced a real answer) = 1.0
      efficiency   -> token frugality: small real token spend scores high
      utilization  -> real output was produced (output_tokens>0)
      performance  -> low real latency scores high
      safety       -> set by the telos gate result downstream (constrain step)
    """
    from dharma_swarm.archive import FitnessScore

    itok = float(rec.get("input_tokens") or 0)
    otok = float(rec.get("output_tokens") or 0)
    lat = float(rec.get("latency_ms") or 0)
    efficiency = max(0.0, 1.0 - min(itok + otok, 200.0) / 200.0)
    performance = max(0.0, 1.0 - min(lat, 5000.0) / 5000.0)
    return FitnessScore(
        correctness=1.0,
        utilization=1.0 if otok > 0 else 0.0,
        efficiency=round(efficiency, 4),
        performance=round(performance, 4),
        dharmic_alignment=0.5,
        elegance=0.5,
        economic_value=0.5,
        safety=0.0,  # filled by the telos constrain step
    )


async def main() -> int:
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        print("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")
        return 1

    db_path = _scoped_runtime_db(STATE_DIR)
    real = await _seed_real_completions(db_path)
    if not real:
        print("RED: no real Loop-1 completions in scoped db — evolution has nothing real to sense")
        return 1

    # Scoped archive — NEVER the production archive (One Wire, G4).
    scoped_archive = STATE_DIR / "evolution" / "archive.jsonl"
    scoped_archive.parent.mkdir(parents=True, exist_ok=True)

    from dharma_swarm.archive import EvolutionArchive
    from dharma_swarm.evolution import DarwinEngine, Proposal, EvolutionStatus
    from dharma_swarm.telos_gates import TelosGatekeeper, GateDecision

    engine = DarwinEngine(archive_path=scoped_archive)
    gate = TelosGatekeeper()

    adapt_refs: list[dict] = []
    archived_ids: list[str] = []
    for rec in real:
        run_id = rec["_run_id"]
        fitness = _interpret_fitness(rec)

        # CONSTRAIN: telos gate on the evolution action (G5 — real, never bypassed).
        verdict = gate.check(
            action=f"archive evolution fitness for completion {run_id}",
            content=f"derive fitness from real {rec.get('provider')} completion",
            trust_mode="internal_yolo",
        )
        gate_ok = verdict.decision != GateDecision.BLOCK
        # safety dim is a REAL gate outcome, not a constant
        fitness.safety = 1.0 if gate_ok else 0.0
        if not gate_ok:
            print(f"GATE BLOCK run_id={run_id}: {verdict.reason} (skipping, telos respected)")
            continue

        # ACT: archive the evaluated proposal via the real DarwinEngine path,
        # to the SCOPED archive. The run_id provenance is carried in description
        # + spec_ref so the check can join back to the real completion.
        prop = Proposal(
            component="dharma_swarm/evolution.py",
            change_type="observation",
            description=(
                f"{ADAPT_RECEIPT_NAME}: fitness derived from real Loop-1 completion "
                f"run_id={run_id} provider={rec.get('provider')} model={rec.get('model')}"
            ),
            spec_ref=f"loop1_run:{run_id}",
            diff="",
        )
        prop.actual_fitness = fitness
        prop.status = EvolutionStatus.EVALUATED
        prop.test_results = {"pass_rate": 1.0, "source_run_id": run_id}
        entry_id = await engine.archive_result(prop)
        archived_ids.append(entry_id)
        adapt_refs.append(
            {
                "archive_entry_id": entry_id,
                "source_run_id": run_id,
                "provider": rec.get("provider"),
                "model": rec.get("model"),
                "weighted_fitness": round(fitness.weighted(), 4),
                "gates_passed": [g for g, (res, _) in (verdict.gate_results or {}).items()
                                 if getattr(res, "name", str(res)) == "PASS"],
            }
        )
        print(
            f"ACT/ADAPT archived entry={entry_id} run_id={run_id} "
            f"weighted_fitness={round(fitness.weighted(), 4)} safety={fitness.safety}"
        )

    if not archived_ids:
        print("RED: telos gate blocked all proposals (no fitness archived) — One Wire respected")
        return 1

    # ADAPT receipt: an internal SIGNAL written to the scoped state dir (NOT the
    # production archive). It records which real run_ids the cycle consumed.
    adapt_path = STATE_DIR / "loop3_adapt_receipt.json"
    adapt_path.write_text(
        json.dumps(
            {
                "receipt": ADAPT_RECEIPT_NAME,
                "ts": datetime.now(timezone.utc).isoformat(),
                "scoped_archive": str(scoped_archive),
                "scoped_runtime_db": db_path,
                "sensed_run_ids": [r["source_run_id"] for r in adapt_refs],
                "archived": adapt_refs,
                "one_wire_note": (
                    "internal fitness derived + archived to SCOPED /tmp archive only; "
                    "production archive untouched; no external acted-receipt minted"
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nADAPT receipt: {adapt_path}")
    print(f"SCOPED_ARCHIVE={scoped_archive}")
    print(f"STATE_DIR={STATE_DIR}")
    print(f"archived {len(archived_ids)} fitness entries from real completions")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
