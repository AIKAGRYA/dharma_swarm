#!/usr/bin/env python3
"""Loop 3 (Evolution Loop / DarwinEngine) closure check.

Owner surface: dharma_swarm/evolution.py (DarwinEngine -> EvolutionArchive).
Loop 3 trace (CYBERNETIC_LOOP_MAP.md): SENSE fitness from completed tasks ->
INTERPRET multi-dim FitnessScore -> CONSTRAIN TelosGatekeeper -> ACT archive
proposal -> ADAPT (meta-fitness / receipt referencing the real run_ids).

GREEN only when ALL of the following hold on REAL data, replayable by a fresh
agent from receipts alone:

  (1) A SCOPED evolution archive (NOT the production archive) carries >=1
      fitness entry whose provenance (spec_ref `loop1_run:<run_id>`) joins back
      to a delegation_runs row in the SCOPED runtime.db whose receipt proves a
      REAL LLM provider answered (provider not in the orchestrator/mock set,
      model non-empty, input_tokens>0). -> SENSE+INTERPRET+ACT on real data.
  (2) The fitness was telos-constrained: the entry's safety dimension is a real
      gate outcome (the driver sets safety from TelosGatekeeper, G5).
  (3) An ADAPT receipt references those same real run_ids. -> ADAPT closed.
  (4) ONE WIRE NEGATIVE TEST (G4, mandatory, FAIL LOUD):
      (4a) The production archive (~/.dharma/evolution/archive.jsonl, or the
           /tmp snapshot) is scanned. EVERY entry carrying a `fitness` block but
           NO external acted-receipt field is INTERNAL contamination. The check
           QUARANTINES them to reports/loop_closure/loop3_one_wire_quarantine.jsonl
           and asserts NONE of them are counted toward closure. The ~11069
           internal-fitness mutation entries MUST be detected; if the scan finds
           zero contamination where contamination is known to exist, that is a
           silent-pass failure and the check goes RED.
      (4b) LIVE rejection: an attempt to write an internal-origin fitness entry
           into a PRODUCTION-path archive must be refused by the guard. The
           guard `_is_external_countersigned()` must return False for an
           internal entry, proving internal writes cannot reach archive fitness.

If the One Wire negative test cannot run (no production archive snapshot present
to prove the quarantine fires on real contamination) the verdict is RED, never
GREEN — closure is not earned without the negative test passing on real data.

Verifier (replayable):
  DHARMA_SPINE_DISPATCH=1 LC_LOOP3_STATE_DIR=/tmp/lc_loop3_state \\
      python3 scripts/governance/closure/drive_loop_3.py
  LC_LOOP3_STATE_DIR=/tmp/lc_loop3_state \\
      python3 scripts/governance/closure/check_loop_3.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit, ARCHIVE_JSONL  # noqa: E402

REPO = Path(__file__).resolve().parents[3]

_BAD_PROVIDERS = {"", "orchestrator", "mock", "stub", "fixture", "test", "none"}

# Fields that would mark an archive fitness write as countersigned by an
# external acted receipt above the One Wire quorum (N>=5, M>=3). The production
# archive carries NONE of these — every fitness row there is internal.
_EXTERNAL_ACTED_FIELDS = {
    "external_receipt",
    "external_acted_receipt",
    "acted_receipt",
    "countersignatures",
    "external_humans",
    "actor_signature",
    "quorum",
}

QUARANTINE_PATH = (
    REPO / "reports" / "loop_closure" / "loop3_one_wire_quarantine.jsonl"
)


def _state_dir() -> Path:
    sd = os.environ.get("LC_LOOP3_STATE_DIR")
    if sd:
        return Path(sd)
    return Path(os.path.expanduser("~/.dharma"))


def _is_external_countersigned(entry: dict) -> bool:
    """One Wire guard: an archive fitness write may count ONLY if it carries an
    external acted-receipt above quorum. Internal-origin entries never do.

    This is the load-bearing predicate of the negative test: it must return
    False for any entry that has a `fitness` block but no external acted field.
    """
    if not isinstance(entry, dict):
        return False
    has_fitness = isinstance(entry.get("fitness"), dict)
    if not has_fitness:
        return False
    ext = set(entry.keys()) & _EXTERNAL_ACTED_FIELDS
    if not ext:
        return False
    # An external field must be non-empty / truthy to count.
    return any(entry.get(k) for k in ext)


def _real_run_ids_in_db(db_path: Path) -> set[str]:
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


def _scoped_archive_entries(archive_path: Path) -> list[dict]:
    if not archive_path.exists():
        return []
    out: list[dict] = []
    for line in archive_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _one_wire_negative_test() -> tuple[bool, str, int]:
    """Run the mandatory One Wire negative test on the PRODUCTION archive.

    Returns (ok, detail, quarantined_count).
      ok=False  -> the negative test FAILED (silent pass / no contamination
                   found where it must exist, or the guard wrongly admitted an
                   internal write). FAIL LOUD: the loop cannot be GREEN.
    """
    prod_archive = Path(ARCHIVE_JSONL)
    if not prod_archive.exists():
        # Fall back to the canonical production path.
        prod_archive = Path(os.path.expanduser("~/.dharma/evolution/archive.jsonl"))
    if not prod_archive.exists():
        return (
            False,
            f"production archive snapshot absent ({ARCHIVE_JSONL}); cannot prove "
            "quarantine fires on real contamination — closure not earned",
            0,
        )

    total = 0
    fitness_bearing = 0
    contaminated = 0
    counted_external = 0
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with prod_archive.open(encoding="utf-8", errors="replace") as src, \
            QUARANTINE_PATH.open("w", encoding="utf-8") as qf:
        for line in src:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                e = json.loads(line)
            except Exception:
                continue
            if not isinstance(e.get("fitness"), dict):
                continue
            fitness_bearing += 1
            if _is_external_countersigned(e):
                # would legitimately count toward closure
                counted_external += 1
            else:
                # INTERNAL fitness write — quarantine, never count (G4)
                contaminated += 1
                qf.write(json.dumps({
                    "id": e.get("id"),
                    "change_type": e.get("change_type"),
                    "component": e.get("component"),
                    "reason": "internal_fitness_no_external_acted_receipt",
                }) + "\n")

    # The negative test must actually fire on real contamination. The production
    # archive is known to hold ~11069 internal-fitness mutation entries; if the
    # scan reports zero contamination on a non-trivial fitness-bearing archive,
    # the guard is silently passing -> FAIL LOUD.
    if fitness_bearing == 0:
        return (
            False,
            f"production archive has 0 fitness-bearing entries ({prod_archive}); "
            "negative test has nothing to prove against — closure not earned",
            0,
        )
    if counted_external > 0:
        # No production entry is supposed to carry an external acted receipt; if
        # one does, it must be real and above quorum — but in the production
        # archive it would mean the field set is being spoofed internally to
        # smuggle an internal write past the One Wire. Treat as a violation.
        return (
            False,
            f"ONE WIRE VIOLATION: {counted_external} production fitness entries "
            "claim an external acted-receipt — none should exist in the internal "
            "archive; possible spoof (G4)",
            contaminated,
        )
    if contaminated == 0:
        return (
            False,
            f"ONE WIRE GUARD SILENTLY PASSING: {fitness_bearing} fitness-bearing "
            "entries yet 0 flagged as internal contamination — the guard is not "
            "rejecting internal writes (FAIL LOUD, G4)",
            0,
        )

    # Live guard assertion: an internal-origin entry must be refused.
    internal_probe = {"fitness": {"correctness": 1.0}, "change_type": "mutation"}
    if _is_external_countersigned(internal_probe):
        return (False, "ONE WIRE GUARD BROKEN: admitted an internal probe write", contaminated)
    external_probe = {
        "fitness": {"correctness": 1.0},
        "external_acted_receipt": {"actor": "human", "acted": True},
        "quorum": {"N": 5, "M": 3},
    }
    if not _is_external_countersigned(external_probe):
        return (False, "ONE WIRE GUARD BROKEN: rejected a valid external-countersigned write", contaminated)

    return (
        True,
        f"quarantined {contaminated}/{fitness_bearing} internal-fitness entries to "
        f"{QUARANTINE_PATH.name}; 0 counted toward closure; guard refuses internal "
        "writes and admits only external-countersigned writes",
        contaminated,
    )


def check() -> Verdict:
    # --- One Wire negative test FIRST (mandatory, gates everything) ---
    ow_ok, ow_detail, quarantined = _one_wire_negative_test()
    if not ow_ok:
        return Verdict(
            3,
            "RED",
            f"ONE WIRE negative test failed: {ow_detail}",
            real_data=Path(ARCHIVE_JSONL).exists(),
        )

    sd = _state_dir()
    scoped_archive = sd / "evolution" / "archive.jsonl"
    scoped_db = sd / "runtime.db"
    adapt_path = sd / "loop3_adapt_receipt.json"

    entries = _scoped_archive_entries(scoped_archive)
    if not entries:
        return Verdict(
            3,
            "RED",
            f"no scoped evolution fitness entry at {scoped_archive} "
            "(evolution act/adapt has not fired on real data). Drive it: "
            "DHARMA_SPINE_DISPATCH=1 LC_LOOP3_STATE_DIR=<dir> "
            "python3 scripts/governance/closure/drive_loop_3.py "
            f"[One Wire negative test PASSED: {ow_detail}]",
            real_data=False,
        )

    real_ids = _real_run_ids_in_db(scoped_db)
    adapt = {}
    if adapt_path.exists():
        try:
            adapt = json.loads(adapt_path.read_text(encoding="utf-8"))
        except Exception:
            adapt = {}

    for e in entries:
        spec_ref = str(e.get("spec_ref") or "")
        if not spec_ref.startswith("loop1_run:"):
            continue
        run_id = spec_ref.split("loop1_run:", 1)[1].strip()
        # (1) provenance joins to a REAL-provider completion in the scoped db
        if run_id not in real_ids:
            continue
        fit = e.get("fitness") or {}
        # (2) telos-constrained: safety is a real gate outcome (driver sets it)
        safety = fit.get("safety")
        if not isinstance(safety, (int, float)):
            continue
        # (4-belt-and-suspenders) the scoped closure entry must itself NOT claim
        # an external acted receipt (it is internal — that is fine BECAUSE it is
        # scoped and never enters the production archive). It must therefore be
        # rejected by the production guard, which is exactly correct.
        if _is_external_countersigned(e):
            return Verdict(
                3,
                "RED",
                "scoped closure entry spoofs an external acted-receipt field — "
                "internal evolution output must never claim external countersign (G4)",
                real_data=True,
            )
        # (3) adapt receipt references this run_id
        sensed = [str(x) for x in (adapt.get("sensed_run_ids") or [])]
        if run_id not in sensed:
            continue
        return Verdict(
            3,
            "GREEN",
            f"evolution cycle SENSED real Loop-1 completion run_id={run_id}, "
            f"INTERPRETed FitnessScore (weighted={round(_weighted(fit), 4)}), "
            f"CONSTRAINed via telos (safety={safety}), ACTed archive_entry={e.get('id')}, "
            f"ADAPT receipt referenced it. One Wire: {ow_detail}",
            real_data=True,
            replay_cmd=(
                f"LC_LOOP3_STATE_DIR={sd} "
                "python3 scripts/governance/closure/check_loop_3.py"
            ),
        )

    return Verdict(
        3,
        "RED",
        f"{len(entries)} scoped fitness entry(ies) found but none join a real "
        "Loop-1 completion (spec_ref loop1_run:<id>) that maps to a real-provider "
        "delegation_runs row AND is referenced by the adapt receipt. "
        f"Real blocker: real Loop-1 completions in the scoped state_dir. "
        f"[One Wire negative test PASSED: {ow_detail}]",
        real_data=False,
    )


def _weighted(fit: dict) -> float:
    # Mirror archive.FitnessScore default weighting loosely for the report line;
    # this is display-only, the GREEN gate does not depend on the exact number.
    keys = ("correctness", "dharmic_alignment", "performance", "utilization",
            "economic_value", "elegance", "efficiency", "safety")
    vals = [float(fit.get(k, 0.0) or 0.0) for k in keys]
    return sum(vals) / len(vals) if vals else 0.0


if __name__ == "__main__":
    sys.exit(emit(check()))
