#!/usr/bin/env python3
"""Loop 2 (Organism Heartbeat) closure check.

GREEN only when a REAL heartbeat cycle emitted a `heartbeat_cycle` receipt to
its declared owner surface (OrganismMemory entities.jsonl) that:

  (1) carries the cycle's sense/interpret/constrain output
      (tcs/live_score, blended/regime, gnani_decision) — proving the
      sense->interpret->constrain path ran, and
  (2) references >=1 real Loop-1 completion run_id, AND each referenced run_id
      joins back to a delegation_runs row in the same scoped runtime.db whose
      receipt proves a REAL LLM provider answered (provider not in the
      orchestrator/mock set, model non-empty, input_tokens>0) — proving the
      act/adapt edge fired on real data, not the 89 fixture organism_memory
      entries, and
  (3) the cycle did NOT write archive fitness (One Wire invariant, G4).

Honest current state on the LIVE snapshot: RED — the existing organism_memory
entities are heartbeat `decision` rows whose metadata carries no real-provider
run_id references (act/adapt was blocked on running agents per the loop map).
The closure surface is exercised by drive_loop_2.py, which drives real Loop-1
completions into a scoped state_dir and runs a real heartbeat against it.

Verifier (replayable by a fresh agent):
  DHARMA_SPINE_DISPATCH=1 LC_LOOP2_STATE_DIR=/tmp/lc_loop2_state \\
      python3 scripts/governance/closure/drive_loop_2.py
  LC_LOOP2_STATE_DIR=/tmp/lc_loop2_state \\
      python3 scripts/governance/closure/check_loop_2.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402

_BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}


def _state_dir() -> Path:
    # Loop 2 is scoped-state-dir driven (heartbeat reads its own state_dir).
    # Default to the production state dir for the honest RED floor when unset.
    sd = os.environ.get("LC_LOOP2_STATE_DIR")
    if sd:
        return Path(sd)
    return Path(os.path.expanduser("~/.dharma"))


def _real_run_ids_in_db(db_path: Path) -> set[str]:
    """run_ids of real-provider completed delegation_runs in the scoped db."""
    if not db_path.exists():
        return set()
    out: set[str] = set()
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        for run_id, rj in conn.execute(
            "SELECT run_id, receipt_json FROM delegation_runs "
            "WHERE status='completed' AND receipt_json IS NOT NULL AND receipt_json!=''"
        ):
            try:
                rec = json.loads(rj)
            except Exception:
                continue
            if str(rec.get("provider", "")).strip().lower() in _BAD_PROVIDERS:
                continue
            if not str(rec.get("model", "")).strip():
                continue
            itok = rec.get("input_tokens")
            if not isinstance(itok, (int, float)) or itok <= 0:
                continue
            out.add(run_id)
    except sqlite3.DatabaseError:
        return set()
    finally:
        if conn is not None:
            conn.close()
    return out


def _heartbeat_receipts(entities_path: Path) -> list[dict]:
    """Valid (non-invalidated) heartbeat_cycle entities from entities.jsonl."""
    if not entities_path.exists():
        return []
    out: list[dict] = []
    for line in entities_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("entity_type") != "heartbeat_cycle":
            continue
        if e.get("temporal_valid_to"):  # soft-invalidated
            continue
        out.append(e)
    return out


def _archive_untouched(state_dir: Path) -> bool:
    """One Wire (G4): the heartbeat must not write archive fitness.

    A scoped run that never created an evolution/archive.jsonl is clean by
    construction. If one exists, it must carry zero rows attributable to a
    heartbeat_cycle.
    """
    arch = state_dir / "evolution" / "archive.jsonl"
    if not arch.exists():
        return True
    try:
        for line in arch.read_text(encoding="utf-8", errors="replace").splitlines():
            if "heartbeat_cycle" in line:
                return False
    except Exception:
        return True
    return True


def check() -> Verdict:
    sd = _state_dir()
    entities_path = sd / "organism_memory" / "entities.jsonl"
    db_path = sd / "runtime.db"

    receipts = _heartbeat_receipts(entities_path)
    if not receipts:
        return Verdict(
            2,
            "RED",
            f"no heartbeat_cycle receipt at {entities_path} "
            "(act/adapt edge has not fired on real data). "
            "Drive it: DHARMA_SPINE_DISPATCH=1 LC_LOOP2_STATE_DIR=<dir> "
            "python3 scripts/governance/closure/drive_loop_2.py",
            real_data=False,
        )

    real_ids = _real_run_ids_in_db(db_path)

    for e in receipts:
        md = e.get("metadata", {}) or {}
        # (1) sense/interpret/constrain present
        has_sic = (
            md.get("tcs") is not None
            and md.get("blended") is not None
            and md.get("regime")
            and md.get("gnani_decision") is not None
        )
        if not has_sic:
            continue
        # (2) references real run_ids that join to real-provider receipts
        sensed = [str(r) for r in (md.get("sensed_run_ids") or [])]
        joined = [r for r in sensed if r in real_ids]
        if not joined:
            continue
        # (3) One Wire: no archive fitness write
        if not _archive_untouched(sd):
            return Verdict(
                2,
                "RED",
                "ONE WIRE VIOLATION: heartbeat_cycle attributed to archive fitness — "
                "quarantine required (G4).",
                real_data=True,
            )
        return Verdict(
            2,
            "GREEN",
            f"heartbeat_cycle receipt cycle={md.get('cycle')} "
            f"regime={md.get('regime')} gnani={md.get('gnani_decision')} "
            f"sensed {len(joined)} real-provider completion(s) "
            f"(e.g. run_id={joined[0]}); sense->interpret->constrain->act->adapt "
            "on real data, archive untouched",
            real_data=True,
            replay_cmd=(
                f"LC_LOOP2_STATE_DIR={sd} "
                "python3 scripts/governance/closure/check_loop_2.py"
            ),
        )

    return Verdict(
        2,
        "RED",
        f"{len(receipts)} heartbeat_cycle receipt(s) found but none reference a real "
        "Loop-1 completion that joins to a real-provider delegation_runs row "
        "(act/adapt not proven on real data). "
        "Real blocker: real Loop-1 completions in the sensed state_dir.",
        real_data=False,
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
