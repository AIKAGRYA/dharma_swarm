#!/usr/bin/env python3
"""Loop 4 (Consolidation / Memory) closure check.

Loop 4 trace (CYBERNETIC_LOOP_MAP.md §"Loop 4: Consolidation Loop (Memory)"):
  SENSE     read recent agent outputs (Loop-1 completed delegation_runs)
  ACT       SleepTimeAgent.consolidate_knowledge(): KnowledgeExtractor (REAL LLM)
            decomposes each output into Propositions + Prescriptions, stored in a
            KnowledgeStore
  EVALUATE  dedup / outcome scoring
  ADAPT     consolidated units become searchable memory keyed by the real run_id;
            a consolidation_cycle receipt feeds the next agent's context

GREEN only when, on REAL data:
  (1) the runtime db holds >=3 REAL-provider completed Loop-1 rows
      (provider!='orchestrator', model!='', input_tokens>0) carrying real
      provider output text — i.e. there were real agent outputs to consolidate, AND
  (2) the KnowledgeStore contains >=3 knowledge units (propositions/prescriptions)
      whose provenance JOINS back to those real Loop-1 run_ids (consolidation
      actually ran on real outputs, not fixtures), AND
  (3) the ADAPT edge fired: a CONSOLIDATION_CYCLE receipt references the same real
      run_ids and the same knowledge_db, AND
  (4) One Wire intact: the consolidation artifacts are internal memory writes, not
      archive.jsonl fitness writes (fail loud on any archive-fitness reference).

Honest current state with no scoped dbs present: RED — no real agent outputs to
consolidate (Loop 1 produced no knowledge-bearing outputs in this scope). GREEN is
earned by running drive_loop_4.py (which drives real free-provider dispatches and
runs the real consolidation pipeline over them).

Replayable by a fresh agent from the scoped artifacts alone:
  LC_LOOP4_RUNTIME_DB=<runtime.db> LC_LOOP4_KNOWLEDGE_DB=<knowledge.db> \
    LC_LOOP4_DIR=<dir> python3 scripts/governance/closure/check_loop_4.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402

RUNTIME_DB = os.environ.get("LC_LOOP4_RUNTIME_DB", "/tmp/lc_loop4_runtime.db")
KNOWLEDGE_DB = os.environ.get("LC_LOOP4_KNOWLEDGE_DB", "/tmp/lc_loop4_knowledge.db")
LOOP4_DIR = Path(os.environ.get("LC_LOOP4_DIR", "/tmp/lc_loop4"))

BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}


def _real_loop1_run_ids(db_path: str) -> dict[str, dict]:
    """SENSE side: map run_id -> receipt for REAL-provider completed rows that
    carried real provider output text (the data Loop 4 consolidates)."""
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
            attrs = r.get("attributes", {}) or {}
            if not str(attrs.get("agent_output", "")).strip():
                continue
            out[run_id] = r
    finally:
        conn.close()
    return out


def _knowledge_units(db_path: str) -> list[dict]:
    """Read all stored propositions + prescriptions with their provenance."""
    p = Path(db_path)
    if not p.exists():
        return []
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    units: list[dict] = []
    try:
        for table, kind in (("propositions", "proposition"), ("prescriptions", "prescription")):
            try:
                rows = conn.execute(
                    f"SELECT id, content, provenance_event_id, provenance_context FROM {table}"
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for row in rows:
                units.append(
                    {
                        "kind": kind,
                        "id": row["id"],
                        "content": row["content"],
                        "provenance_event_id": row["provenance_event_id"] or "",
                        "provenance_context": row["provenance_context"] or "",
                    }
                )
    finally:
        conn.close()
    return units


def check() -> Verdict:
    # (1) real Loop-1 outputs to consolidate
    real_runs = _real_loop1_run_ids(RUNTIME_DB)
    if len(real_runs) < 3:
        return Verdict(
            4,
            "RED",
            f"only {len(real_runs)} real-provider Loop-1 output(s) with text in {RUNTIME_DB} "
            "(need >=3 to consolidate; run drive_loop_4.py)",
            real_data=False,
        )

    # (2) knowledge units that JOIN back to those real run_ids
    units = _knowledge_units(KNOWLEDGE_DB)
    if not units:
        return Verdict(
            4,
            "RED",
            f"no consolidated knowledge units in {KNOWLEDGE_DB} "
            "(consolidation has not run on real outputs)",
            real_data=False,
        )

    joined_runs: set[str] = set()
    joined_units = 0
    for u in units:
        # the unit joins if any real run_id appears in its provenance fields.
        prov_blob = f"{u['provenance_event_id']} {u['provenance_context']}"
        matched = next((rid for rid in real_runs if rid in prov_blob), None)
        if matched:
            joined_runs.add(matched)
            joined_units += 1

    if joined_units < 3:
        return Verdict(
            4,
            "RED",
            f"only {joined_units} knowledge unit(s) join to real Loop-1 run_ids "
            f"(need >=3; {len(units)} total units, {len(joined_runs)} distinct runs). "
            "Consolidation did not provably run on real agent outputs.",
            real_data=False,
        )

    # (3) ADAPT edge: consolidation_cycle receipt referencing the same real run_ids
    adapt_path = LOOP4_DIR / "loop4_adapt_receipt.json"
    if not adapt_path.exists():
        return Verdict(
            4,
            "RED",
            f"adapt edge missing: no CONSOLIDATION_CYCLE receipt at {adapt_path}",
            real_data=False,
        )
    adapt = json.loads(adapt_path.read_text())
    if adapt.get("type") != "CONSOLIDATION_CYCLE":
        return Verdict(4, "RED", "adapt receipt malformed (type != CONSOLIDATION_CYCLE)", real_data=False)
    adapt_runs = set(adapt.get("joined_delegation_run_ids", []))
    if not joined_runs.issubset(adapt_runs):
        return Verdict(
            4,
            "RED",
            "adapt receipt does not reference all joined real run_ids "
            "(consolidated memory not provably derived from the audited real outputs)",
            real_data=False,
        )
    if adapt.get("knowledge_db") != KNOWLEDGE_DB:
        return Verdict(
            4,
            "RED",
            f"adapt receipt knowledge_db mismatch ({adapt.get('knowledge_db')} != {KNOWLEDGE_DB})",
            real_data=False,
        )

    # (4) One Wire invariant: internal memory write only, never archive fitness.
    blob = adapt_path.read_text()
    if "archive.jsonl" in blob and "no archive" not in blob:
        return Verdict(
            4,
            "RED",
            "One Wire VIOLATION: consolidation adapt edge references an archive.jsonl "
            "fitness write (internal memory must never touch archive fitness)",
            real_data=False,
        )

    sample_run = sorted(joined_runs)[0]
    sample = real_runs[sample_run]
    return Verdict(
        4,
        "GREEN",
        f"{joined_units} knowledge unit(s) consolidated from {len(joined_runs)} REAL Loop-1 "
        f"agent output(s) joined by provenance run_id (e.g. run={sample_run} "
        f"provider={sample.get('provider')} model={sample.get('model')}); "
        f"adapt edge fired (CONSOLIDATION_CYCLE: {adapt.get('total_propositions')} props + "
        f"{adapt.get('total_prescriptions')} prescs); One Wire intact",
        real_data=True,
        replay_cmd=(
            f"LC_LOOP4_RUNTIME_DB={RUNTIME_DB} LC_LOOP4_KNOWLEDGE_DB={KNOWLEDGE_DB} "
            f"LC_LOOP4_DIR={LOOP4_DIR} python3 scripts/governance/closure/check_loop_4.py"
        ),
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
