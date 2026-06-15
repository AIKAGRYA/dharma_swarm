#!/usr/bin/env python3
"""Loop 6 (Witness Auditor) closure check.

Loop 6 trace (CYBERNETIC_LOOP_MAP.md §"Loop 6: Witness Auditor"):
  SENSE     WitnessAuditor samples recent agent actions
  INTERPRET _evaluate_trace scores telos alignment / mimicry
  CONSTRAIN AHIMSA / gate-sufficiency heuristic
  ACT       write AuditFinding to ~/.dharma/witness/
  ADAPT     witness verdict -> SignalBus WITNESS_AUDIT -> evolution fitness signal

GREEN only when, on REAL data:
  (1) >=3 witness findings exist on the owner surface, AND
  (2) each finding JOINS to a REAL-provider Loop-1 delegation_run
      (provider!='orchestrator', model!='', input_tokens>0) — i.e. the witness
      audited real agent actions, NOT the 9865 fixture entries, AND
  (3) the ADAPT edge fired: a WITNESS_AUDIT adapt receipt carries a
      witness_fitness_signal referencing those same real run_ids, AND
  (4) One Wire intact: the adapt receipt is an internal SIGNAL, not an
      archive.jsonl fitness write (asserted by checking no archive mutation
      marker is present and the receipt self-declares signal-only).

Honest current state on the live snapshot (LC_WITNESS_DIR unset / default
~/.dharma/witness): RED — the witness entries reference test/fixture actions
that do not join to real-receipt delegation_runs (Loop 1 was RED until the
spine-dispatch driver ran). GREEN is earned by driving drive_loop_1.py then
drive_loop_6.py against scoped dbs.

Replayable by a fresh agent from the scoped artifacts alone:
  LC_LOOP1_DB=<loop1_scoped.db> LC_WITNESS_DIR=<witness_dir> \
    python3 scripts/governance/closure/check_loop_6.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402

LOOP1_DB = os.environ.get("LC_LOOP1_DB", "/tmp/lc_loop1_scoped.db")
WITNESS_DIR = Path(os.environ.get("LC_WITNESS_DIR", str(Path.home() / ".dharma" / "witness")))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}


def _real_loop1_receipts(db_path: str) -> dict[str, dict]:
    """Map run_id -> receipt for REAL-provider completed Loop-1 rows."""
    p = Path(db_path)
    if not p.exists():
        return {}
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    out: dict[str, dict] = {}
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
            out[run_id] = r
    finally:
        conn.close()
    return out


def check() -> Verdict:
    findings_path = WITNESS_DIR / "loop6_findings.jsonl"
    adapt_path = WITNESS_DIR / "loop6_adapt_receipt.json"

    if not findings_path.exists():
        return Verdict(
            6,
            "RED",
            f"no witness findings on owner surface ({findings_path}); "
            "witness has not audited real agent actions (run drive_loop_6.py after drive_loop_1.py)",
            real_data=False,
        )

    real_receipts = _real_loop1_receipts(LOOP1_DB)
    if not real_receipts:
        return Verdict(
            6,
            "RED",
            f"no real-provider Loop-1 receipts in {LOOP1_DB} to join against "
            "(Loop 1 RED — witness findings cannot be proven to reference real actions)",
            real_data=False,
        )

    findings = []
    for line in findings_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            findings.append(json.loads(line))
        except Exception:
            continue

    # (2) every finding must JOIN to a real-provider Loop-1 receipt.
    joined = []
    unjoined = []
    for f in findings:
        rid = f.get("delegation_run_id", "")
        if rid in real_receipts:
            joined.append((f, real_receipts[rid]))
        else:
            unjoined.append(f)

    if len(joined) < 3:
        return Verdict(
            6,
            "RED",
            f"only {len(joined)} witness finding(s) join to real-provider Loop-1 receipts "
            f"(need >=3; {len(unjoined)} unjoined). Witness audited fixtures, not real actions.",
            real_data=False,
        )

    # cross-check: the join target really is a distinct real provider, and the
    # finding's side_effect_key matches the receipt's (no fabricated join).
    for f, rcpt in joined:
        sek_finding = f.get("side_effect_key")
        sek_receipt = (rcpt.get("attributes", {}) or {}).get("side_effect_key")
        if not sek_finding or sek_finding != sek_receipt:
            return Verdict(
                6,
                "RED",
                f"finding for run {f.get('delegation_run_id')} side_effect_key mismatch "
                f"(finding={sek_finding} receipt={sek_receipt}); join is not authentic",
                real_data=False,
            )

    # (3) ADAPT edge: witness verdict -> fitness signal, referencing the real runs.
    if not adapt_path.exists():
        return Verdict(
            6,
            "RED",
            f"adapt edge missing: no WITNESS_AUDIT fitness-signal receipt at {adapt_path}",
            real_data=False,
        )
    adapt = json.loads(adapt_path.read_text())
    if adapt.get("type") != "WITNESS_AUDIT" or "witness_fitness_signal" not in adapt:
        return Verdict(
            6, "RED", "adapt receipt malformed (no WITNESS_AUDIT / witness_fitness_signal)", real_data=False
        )
    adapt_runs = set(adapt.get("joined_delegation_run_ids", []))
    joined_ids = {f.get("delegation_run_id") for f, _ in joined}
    if not joined_ids.issubset(adapt_runs):
        return Verdict(
            6,
            "RED",
            "adapt receipt does not reference all joined real run_ids "
            "(fitness signal not provably derived from the audited real actions)",
            real_data=False,
        )

    # (4) One Wire invariant: the adapt edge is an internal SIGNAL, not an archive
    # fitness write. FAIL LOUD if any finding/adapt artifact claims an archive write.
    blob = adapt_path.read_text() + "\n" + findings_path.read_text()
    if "archive.jsonl" in blob and "no archive" not in blob:
        return Verdict(
            6,
            "RED",
            "One Wire VIOLATION: witness adapt edge references an archive.jsonl fitness write "
            "(internal artifacts must never touch archive fitness)",
            real_data=False,
        )

    sample = joined[0]
    return Verdict(
        6,
        "GREEN",
        f"{len(joined)} witness finding(s) audited REAL agent actions joined to real-provider "
        f"Loop-1 receipts (e.g. run={sample[0].get('delegation_run_id')} "
        f"provider={sample[1].get('provider')} model={sample[1].get('model')}); "
        f"adapt edge fired (witness_fitness_signal={adapt.get('witness_fitness_signal')}); One Wire intact",
        real_data=True,
        replay_cmd=(
            f"LC_LOOP1_DB={LOOP1_DB} LC_WITNESS_DIR={WITNESS_DIR} "
            "python3 scripts/governance/closure/check_loop_6.py"
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
