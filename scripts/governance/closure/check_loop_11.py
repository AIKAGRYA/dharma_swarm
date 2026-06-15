#!/usr/bin/env python3
"""Loop 11 (Replication Monitor) closure check.

Owner surface: dharma_swarm/replication_protocol.py +
orchestrate_live._run_replication_monitor_loop (CYBERNETIC_LOOP_MAP.md row 11).

Loop 11 trace:
  SENSE     get_pending_proposals() drains proposals.jsonl; the proposal's
            evidence is grounded in REAL Loop-1 completed runs.
  INTERPRET G1 _validate_proposal + S _assess_need (population/budget/severity).
  CONSTRAIN G2 _check_gates: 11 REAL telos gates + REAL kernel SHA-256 integrity.
  ACT       M _materialize: REAL GenomeInheritance composes a child AgentSpec;
            child registered + added to roster; probation started.
  ADAPT     M_MATERIALIZED witness + materialized proposals.jsonl entry +
            AGENT_REPLICATED signal; child tracked for probation.

GREEN only when, on REAL data:
  (1) the scoped runtime db holds >=3 REAL-provider completed Loop-1 rows
      (provider!='orchestrator'/'mock', model!='', input_tokens>0) — i.e. there
      was real evidence of a capability gap to trigger replication, AND
  (2) the witness trail shows the full real pipeline fired:
      G1_PASS, S_PASS, G2_PASS, M_MATERIALIZED all present, AND
  (3) a child agent actually materialized: proposals.jsonl has a row with
      status='materialized' and a non-empty child_agent_name, AND
  (4) the ADAPT edge fired: a REPLICATION_CYCLE receipt references the same real
      Loop-1 run_ids and the materialized child, with child_in_roster True, AND
  (5) the telos gate was NOT bypassed: gate_decision is present and != BLOCK
      (G5 — a loop is never closed by weakening a gate), AND
  (6) One Wire intact: nothing in the replication path wrote archive.jsonl
      fitness (fail loud on any archive-fitness reference).

Honest current state with no scoped artifacts present: RED — no real Loop-1
evidence and no materialized replication. GREEN is earned by running
drive_loop_11.py (real free-provider Loop-1 dispatch + the REAL ReplicationProtocol
pipeline materializing a child).

Replayable by a fresh agent from the scoped artifacts alone:
  LC_LOOP11_RUNTIME_DB=<runtime.db> LC_LOOP11_STATE_DIR=<state_dir> \
    python3 scripts/governance/closure/check_loop_11.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402

RUNTIME_DB = os.environ.get("LC_LOOP11_RUNTIME_DB", "/tmp/lc_loop11_runtime.db")
STATE_DIR = Path(os.environ.get("LC_LOOP11_STATE_DIR", "/tmp/lc_loop11_state"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}
REQUIRED_STAGES = {"G1_PASS", "S_PASS", "G2_PASS", "M_MATERIALIZED"}


def _real_loop1_run_ids(db_path: str) -> set[str]:
    p = Path(db_path)
    if not p.exists():
        return set()
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    out: set[str] = set()
    try:
        cur = conn.execute(
            "SELECT run_id, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
        )
        for run_id, rj in cur:
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
            out.add(run_id)
    finally:
        conn.close()
    return out


def _witness_stages(state_dir: Path) -> list[str]:
    wf = state_dir / "witness" / "replication.jsonl"
    if not wf.exists():
        return []
    stages: list[str] = []
    for line in wf.read_text().splitlines():
        try:
            stages.append(json.loads(line).get("type", ""))
        except Exception:
            continue
    return stages


def _materialized_proposals(state_dir: Path) -> list[dict]:
    pf = state_dir / "replication" / "proposals.jsonl"
    if not pf.exists():
        return []
    out: list[dict] = []
    for line in pf.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if entry.get("status") == "materialized" and entry.get("child_agent_name"):
            out.append(entry)
    return out


def check() -> Verdict:
    # (1) real Loop-1 evidence
    real_runs = _real_loop1_run_ids(RUNTIME_DB)
    if len(real_runs) < 3:
        return Verdict(
            11,
            "RED",
            f"only {len(real_runs)} real-provider Loop-1 completed run(s) in {RUNTIME_DB} "
            "(need >=3 as replication evidence; run drive_loop_11.py)",
            real_data=False,
        )

    # (2) full real pipeline witness trail
    stages = set(_witness_stages(STATE_DIR))
    missing = REQUIRED_STAGES - stages
    if missing:
        return Verdict(
            11,
            "RED",
            f"replication witness incomplete in {STATE_DIR}/witness/replication.jsonl "
            f"(missing stages: {sorted(missing)}; have {sorted(stages)})",
            real_data=False,
        )

    # (3) a child actually materialized
    mats = _materialized_proposals(STATE_DIR)
    if not mats:
        return Verdict(
            11,
            "RED",
            f"no materialized proposal in {STATE_DIR}/replication/proposals.jsonl "
            "(no child agent was spawned)",
            real_data=False,
        )

    # (4) ADAPT edge: REPLICATION_CYCLE receipt referencing the same real run_ids
    adapt_path = STATE_DIR / "loop11_adapt_receipt.json"
    if not adapt_path.exists():
        return Verdict(
            11,
            "RED",
            f"adapt edge missing: no REPLICATION_CYCLE receipt at {adapt_path}",
            real_data=False,
        )
    adapt = json.loads(adapt_path.read_text())
    if adapt.get("type") != "REPLICATION_CYCLE":
        return Verdict(11, "RED", "adapt receipt malformed (type != REPLICATION_CYCLE)", real_data=False)

    adapt_runs = set(adapt.get("evidence_loop1_run_ids", []))
    if not adapt_runs or not adapt_runs.issubset(real_runs):
        return Verdict(
            11,
            "RED",
            "adapt receipt does not reference the audited real Loop-1 run_ids "
            "(replication not provably triggered by the real evidence)",
            real_data=False,
        )

    child = adapt.get("child_agent_name")
    mat_children = {m.get("child_agent_name") for m in mats}
    if child not in mat_children:
        return Verdict(
            11,
            "RED",
            f"adapt receipt child '{child}' not among materialized proposals {sorted(mat_children)}",
            real_data=False,
        )
    if not adapt.get("child_in_roster"):
        return Verdict(
            11,
            "RED",
            f"materialized child '{child}' not present in roster (ACT edge did not land)",
            real_data=False,
        )

    # (5) telos gate NOT bypassed (G5)
    gate_decision = str(adapt.get("gate_decision", "")).upper()
    if not gate_decision:
        return Verdict(11, "RED", "adapt receipt missing gate_decision (gate provenance unproven)", real_data=False)
    if gate_decision == "BLOCK":
        return Verdict(
            11,
            "RED",
            "telos gate BLOCKED replication — a loop is never closed by bypassing a gate (G5)",
            real_data=False,
        )

    # (6) One Wire invariant: replication is internal state, never archive fitness.
    blob = adapt_path.read_text()
    if "archive.jsonl" in blob and "no archive" not in blob:
        return Verdict(
            11,
            "RED",
            "One Wire VIOLATION: replication adapt edge references an archive.jsonl "
            "fitness write (replication must never touch archive fitness)",
            real_data=False,
        )

    return Verdict(
        11,
        "GREEN",
        f"child '{child}' materialized through the REAL G1->S->G2->M pipeline "
        f"(gate_decision={gate_decision}, not BLOCK) triggered by {len(adapt_runs)} REAL "
        f"Loop-1 run(s); witness stages {sorted(stages & REQUIRED_STAGES)} all fired; "
        f"child in roster; One Wire intact",
        real_data=True,
        replay_cmd=(
            f"LC_LOOP11_RUNTIME_DB={RUNTIME_DB} LC_LOOP11_STATE_DIR={STATE_DIR} "
            f"python3 scripts/governance/closure/check_loop_11.py"
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
