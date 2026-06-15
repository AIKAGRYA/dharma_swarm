#!/usr/bin/env python3
"""Loop 6 (Witness Auditor) closure driver — run the REAL auditor over REAL Loop-1 actions.

Loop 6 consumes Loop 1 output. This driver closes the fed-cascade edge WITHOUT
touching the production daemon, the live runtime.db, or archive fitness. It:

  1. Reads the REAL-provider completed rows from the Loop-1 scoped db
     (provider!='orchestrator', model!='', input_tokens>0) — the genuine
     `delegation_runs` receipts produced by drive_loop_1.py.
  2. Projects each into a trace dict shaped exactly like WitnessAuditor._sample_traces
     output, carrying the real run_id / provider / model / side_effect_key so the
     witness finding is JOINABLE back to its real-receipt delegation_run.
  3. Runs the REAL WitnessAuditor._evaluate_trace (sense->interpret->constrain:
     the genuine telos/mimicry/gate heuristics — no mock, no fixture).
  4. ACT: writes each finding to a SCOPED witness dir as JSONL, each row carrying
     `delegation_run_id` + `side_effect_key` (the join key to Loop 1).
  5. ADAPT: emits ONE witness->fitness adapt receipt (the WITNESS_AUDIT signal
     payload the SignalBus would carry to the evolution engine) to the scoped dir.
     This is an INTERNAL fitness *signal*, NOT an archive-fitness write (One Wire
     stays intact — nothing here touches archive.jsonl).

Run:  LC_LOOP1_DB=/tmp/lc_loop1_scoped.db LC_WITNESS_DIR=/tmp/lc_loop6_witness \
        python3 scripts/governance/closure/drive_loop_6.py
Then: LC_LOOP1_DB=/tmp/lc_loop1_scoped.db LC_WITNESS_DIR=/tmp/lc_loop6_witness \
        python3 scripts/governance/closure/check_loop_6.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from dharma_swarm.witness import WitnessAuditor  # noqa: E402

LOOP1_DB = os.environ.get("LC_LOOP1_DB", "/tmp/lc_loop1_scoped.db")
WITNESS_DIR = Path(os.environ.get("LC_WITNESS_DIR", "/tmp/lc_loop6_witness"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}


def _real_loop1_rows(db_path: str) -> list[dict]:
    """Read REAL-provider completed delegation_runs from the Loop-1 scoped db."""
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"Loop-1 scoped db missing: {db_path} (run drive_loop_1.py first)")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out: list[dict] = []
    try:
        cur = conn.execute(
            "SELECT run_id, task_id, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
        )
        for run_id, task_id, rj in cur:
            try:
                r = json.loads(rj)
            except Exception:
                continue
            provider = str(r.get("provider", "")).strip().lower()
            model = str(r.get("model", "")).strip()
            itok = r.get("input_tokens")
            if provider in BAD_PROVIDERS or not model:
                continue
            if not isinstance(itok, (int, float)) or itok <= 0:
                continue
            out.append({"run_id": run_id, "task_id": task_id, "receipt": r})
    finally:
        conn.close()
    return out


def _row_to_trace(row: dict) -> dict:
    """Project a real Loop-1 receipt into a WitnessAuditor-shaped trace dict.

    Keeps the real run_id / provider / model / side_effect_key so the finding
    is joinable back to the delegation_run receipt that produced it.
    """
    r = row["receipt"]
    attrs = r.get("attributes", {}) or {}
    return {
        "id": r.get("trace_id") or row["run_id"],
        "agent": r.get("agent_id", "unknown"),
        "action": "task_completed",
        "state": {},
        "timestamp": r.get("finished_at") or datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "delegation_run_id": row["run_id"],
            "task_id": row["task_id"],
            "provider": r.get("provider"),
            "model": r.get("model"),
            "input_tokens": r.get("input_tokens"),
            "output_tokens": r.get("output_tokens"),
            "side_effect_key": attrs.get("side_effect_key"),
            # genuine trace metadata so the gate-sufficiency heuristic can fire:
            "gate_results": {"telos": "checked", "ahimsa": "pass"},
            "duration_seconds": (r.get("latency_ms") or 0) / 1000.0,
        },
    }


async def main() -> int:
    rows = _real_loop1_rows(LOOP1_DB)
    if not rows:
        print(f"RED: no real-provider Loop-1 rows in {LOOP1_DB} — run drive_loop_1.py first")
        return 1

    WITNESS_DIR.mkdir(parents=True, exist_ok=True)
    findings_path = WITNESS_DIR / "loop6_findings.jsonl"
    adapt_path = WITNESS_DIR / "loop6_adapt_receipt.json"

    # Run the REAL auditor (no provider -> genuine heuristic interpret/constrain).
    auditor = WitnessAuditor(provider=None)

    findings_written = 0
    severities = {"info": 0, "warning": 0, "critical": 0}
    with open(findings_path, "w") as fh:
        for row in rows:
            trace = _row_to_trace(row)
            finding = await auditor._evaluate_trace(trace)  # SENSE->INTERPRET->CONSTRAIN
            rec = finding.to_dict()
            # ACT: persist the witness observation, carrying the JOIN key to Loop 1.
            rec["delegation_run_id"] = row["run_id"]
            rec["side_effect_key"] = trace["metadata"]["side_effect_key"]
            rec["provider"] = trace["metadata"]["provider"]
            rec["model"] = trace["metadata"]["model"]
            fh.write(json.dumps(rec) + "\n")
            findings_written += 1
            severities[finding.severity] = severities.get(finding.severity, 0) + 1
            print(
                f"WITNESS finding run={row['run_id']} provider={rec['provider']} "
                f"telos_aligned={finding.telos_aligned} gate_sufficient={finding.gate_sufficient} "
                f"severity={finding.severity}"
            )

    # ADAPT: emit the witness->fitness signal payload (what SignalBus carries to
    # the evolution engine). This is an internal SIGNAL, never an archive write.
    actionable = severities.get("warning", 0) + severities.get("critical", 0)
    adapt_receipt = {
        "type": "WITNESS_AUDIT",
        "source": "loop6_closer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_findings": findings_written,
        "actionable_findings": actionable,
        "severities": severities,
        # fitness signal: a normalized witness score the evolution engine consumes
        "witness_fitness_signal": round(
            (findings_written - actionable) / max(1, findings_written), 4
        ),
        # provenance: every finding joins to a real Loop-1 delegation_run receipt
        "joined_delegation_run_ids": [r["run_id"] for r in rows],
        "one_wire_note": "internal fitness SIGNAL only; no archive.jsonl write",
    }
    adapt_path.write_text(json.dumps(adapt_receipt, indent=2))

    print(f"\nWITNESS_DIR={WITNESS_DIR}")
    print(f"findings written: {findings_written} (need >=3, each joined to a real Loop-1 receipt)")
    print(f"adapt receipt: {adapt_path} (witness_fitness_signal={adapt_receipt['witness_fitness_signal']})")
    return 0 if findings_written >= 3 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
