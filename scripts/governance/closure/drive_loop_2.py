#!/usr/bin/env python3
"""Loop 2 (Organism Heartbeat) closure driver.

This is the close-unit's Generator+Evaluator. It does NOT touch the production
daemon, the live runtime.db, or archive fitness. It:

  1. Builds a SCOPED state_dir under /tmp with its own runtime.db.
  2. Drives N REAL Loop-1 completions into that scoped runtime.db by dispatching
     through the spine to a LIVE FREE provider (reusing drive_loop_1's blessed
     real-provider invoker). Those rows are the real organism state the heartbeat
     senses — no fixtures.
  3. Runs a REAL OrganismRuntime.heartbeat() pointed at the scoped state_dir.
     The heartbeat's ADAPT edge emits a `heartbeat_cycle` receipt to the scoped
     OrganismMemory that references those real run_ids (sense->interpret->
     constrain->act->adapt over real data).

The heartbeat sense (tcs/live), interpret (blended/regime), and constrain
(gnani verdict) are computed by the real organism code. The adapt-edge receipt
references the real-provider run_ids the cycle sensed. That is exactly what
check_loop_2 demands. No mock provider anywhere in the closure path.

Run:  DHARMA_SPINE_DISPATCH=1 LC_LOOP2_STATE_DIR=/tmp/lc_loop2_state python3 scripts/governance/closure/drive_loop_2.py
Then: LC_LOOP2_STATE_DIR=/tmp/lc_loop2_state python3 scripts/governance/closure/check_loop_2.py
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
    os.environ.get("LC_LOOP2_STATE_DIR", f"/tmp/lc_loop2_state_{int(time.time())}")
)

# FREE-first decorrelated candidates (live-confirmed). Same family set Loop 1 uses.
FREE_CANDIDATES: list[tuple[ProviderType, str | None]] = [
    (ProviderType.GOOGLE_AI, None),
    (ProviderType.OLLAMA, None),
    (ProviderType.GOOGLE_AI, "gemini-2.5-flash"),
    (ProviderType.OLLAMA, "deepseek-v3.2"),
]

TASKS = [
    "Reply with exactly one word: HEARTBEAT",
    "Reply with exactly one word: ORGANISM",
    "Reply with exactly one word: PULSE",
]


def _scoped_runtime_db(state_dir: Path) -> str:
    state_dir.mkdir(parents=True, exist_ok=True)
    return str(state_dir / "runtime.db")


async def _seed_real_completions(db_path: str) -> list[str]:
    """Drive REAL Loop-1 completions into the scoped runtime.db. Returns run_ids."""
    task_ids = [f"task_loop2_{uuid4().hex[:12]}" for _ in TASKS]
    L1._seed_scoped_db(db_path, task_ids)

    successes = 0
    for i, prompt in enumerate(TASKS):
        pt, model_hint = FREE_CANDIDATES[i % len(FREE_CANDIDATES)]
        trace_id = f"trace_loop2_{uuid4().hex[:12]}"
        try:
            r = await L1._dispatch_one(db_path, task_ids[i], trace_id, prompt, pt, model_hint)
            successes += 1
            print(
                f"COMPLETION OK task={task_ids[i]} provider={r.provider} "
                f"model={r.model} in_tok={r.input_tokens}"
            )
        except Exception as e:  # noqa: BLE001
            print(f"COMPLETION ERR task={task_ids[i]} {pt.value}: {type(e).__name__}: {str(e)[:120]}")

    # Return the run_ids of the real-provider completions now in the db.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    bad = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}
    run_ids: list[str] = []
    for run_id, rj in conn.execute(
        "SELECT run_id, receipt_json FROM delegation_runs "
        "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
    ):
        try:
            rec = json.loads(rj)
        except Exception:
            continue
        if str(rec.get("provider", "")).strip().lower() in bad:
            continue
        if not str(rec.get("model", "")).strip():
            continue
        itok = rec.get("input_tokens")
        if not isinstance(itok, (int, float)) or itok <= 0:
            continue
        run_ids.append(run_id)
    conn.close()
    print(f"\nREAL completions sensible to heartbeat: {len(run_ids)} (need >=1)")
    return run_ids


async def main() -> int:
    if os.environ.get("DHARMA_SPINE_DISPATCH") != "1":
        print("DHARMA_SPINE_DISPATCH must be set to 1 for real dispatch")
        return 1

    db_path = _scoped_runtime_db(STATE_DIR)
    real_run_ids = await _seed_real_completions(db_path)
    if not real_run_ids:
        print("RED: no real Loop-1 completions in scoped db — heartbeat has nothing real to sense")
        return 1

    # Run a REAL heartbeat against the scoped state_dir. Its adapt edge records
    # the heartbeat_cycle receipt referencing the real run_ids it senses.
    from dharma_swarm.organism import OrganismRuntime

    org = OrganismRuntime(state_dir=STATE_DIR)
    result = await org.heartbeat()
    print(
        f"\nHEARTBEAT cycle={result.cycle} tcs={result.tcs} live={result.live_score} "
        f"blended={result.blended} regime={result.regime} "
        f"gnani={result.gnani_verdict.decision if result.gnani_verdict else 'NA'}"
    )
    print(f"STATE_DIR={STATE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
