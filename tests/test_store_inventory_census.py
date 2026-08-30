"""Ratchet + determinism guard for the store-inventory census.

Guards ``scripts/store_inventory_census.py`` and its committed artifact
``reports/governance/store_inventory_census.json``:

1. Determinism — two renders are byte-identical, and the committed artifact
   matches a fresh render (adding/removing a store must regenerate it in the
   same PR).
2. Ratchet — the distinct-store counts only move DOWN. A new database, JSONL
   target, or ledger raises a count and fails here, not in review; a
   consolidation lowers it deliberately in the same PR.

The ratchet is the point: proliferation cannot silently grow, and every
consolidation shows up as a falling number.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.store_inventory_census import (  # noqa: E402
    ARTIFACT_PATH,
    build_inventory,
    render_inventory,
)

# Exact committed baselines (2026-07-19 at origin/main). The ratchet is EXACT,
# not `<=`: any count change — up or down — must edit these in the same PR, so
# a consolidation that removes a store cannot leave stale headroom for a later
# PR to silently re-grow into. Consolidation LOWERS a baseline; a genuinely new
# store must be justified in review before RAISING one.
BASELINE_DB_NAMES = 39
# 216 -> 217 (2026-07-24): episode_ledger.jsonl — the session ledger's Episode
# Ledger producer file (B1 producer slice; schema landed in #1062). One new
# versioned validated store, not proliferation of an unversioned one.
# 217 -> 218 (2026-07-25, PR #1135): MANIFEST.jsonl — the signed wiki trust
# manifest (chetana staging boundary, #1140 slice). The manifest IS the
# admission gate for the trusted wiki projection; it is a signed receipt
# surface, not a second content store.
# 218 -> 219 (2026-08-05, PR #1235): {cycle_id}.tasks.jsonl — one per-cycle
# local A2A task-log target for the autocatalytic witness. It records task
# envelopes for replay/inspection and does not claim an authority upgrade.
# 219 -> 221 (2026-08-18, PR #1379): .first_fire_archive.jsonl and
# .first_fire_predictor.jsonl — scratch-worktree artifacts of the one-shot
# first-fire plumbing cycle (experiments/first_fire/COMMAND_PACKET.md). Both
# live only inside the disposable evolution worktree the runner copies into;
# neither is an organism store, and the runner refuses live checkouts.
# 221 -> 222 (2026-08-18, PR #1380): predictions.public.jsonl — the Ginko L0
# forecast ledger's PUBLIC full-store snapshot (yes-sheet 2026-08-18 line 7).
# It is the durable published projection of the existing predictions.jsonl
# store on generated/forecast-ledger, not a second private store.
# 222 -> 223 (2026-08-19): YYYY-MM.jsonl — the Forge monthly spend meter's
# per-month ledger filename template (forge_v2/monthly_ledger.py; yes-sheet
# 2026-08-18 row 1). One runtime-state file per month under
# ~/.dharma/forge_v1/spend/ (e.g. 2026-08.jsonl), never in git; it aggregates
# per-run Budget spend against the $200/month benchmark compute cap.
# 223 -> 225 (2026-08-30, PR #1493): +events.jsonl (forge_lab campaign event
# chain — the hermetic five-run pilot's lifecycle ledger), +history.v1.jsonl
# (forge_lab operator-history projection rows), +assurance_guard_unavailable.jsonl
# (the assurance-diff fail-open witness flag; reviewed write-baseline entry in
# memory_kernel/write_policy.py), -flickers.jsonl (retired by the 11->9 gate
# silvering). Three merge-introduced stores, one consolidation removal.
# 225 -> 226 (2026-08-30, PR #1498): run.jsonl — the RUDRA v0 per-attempt
# journal (Journal in rudra/workcell.py; written by runner.py and
# goal_gate_admission.py under the attempt dir). One append-only witness
# ledger per attempt, not a second content store.
BASELINE_JSONL_NAMES = 226
# 11 -> 12 (2026-07-19): episode_ledger.py — THE_KEEL §6 Episode Ledger
# schema slice, the justified new organ this ratchet exists to make explicit.
# 12 -> 13 (2026-08-19): monthly_ledger.py — the Forge monthly spend meter
# (forge_v2; yes-sheet 2026-08-18 row 1). It aggregates per-run Budget spend
# across runs against the $200/month benchmark compute cap; a genuine new
# ledger, deliberately named as one rather than dodging this ratchet.
# 13 -> 14 (2026-08-30, PR #1493): forge_lab/unattended_ledger.py — the UTC
# day/month budget-reservation ledger for the bounded unattended EXPLORE
# runner; reserves spend before any provider call and fails closed.
BASELINE_LEDGER_MODULES = 14
BASELINE_LEDGER_CLASSES = 11


def test_census_renders_deterministically():
    assert render_inventory() == render_inventory()


def test_committed_artifact_matches_tree():
    assert ARTIFACT_PATH.is_file(), (
        "store_inventory_census.json missing; run "
        "python3 scripts/store_inventory_census.py --write"
    )
    assert ARTIFACT_PATH.read_text(encoding="utf-8") == render_inventory(), (
        "committed store_inventory_census.json is stale; regenerate with "
        "python3 scripts/store_inventory_census.py --write and commit it in "
        "the same PR as the store change"
    )


def test_store_counts_match_exact_baseline():
    summary = build_inventory()["summary"]
    assert summary["distinct_db_names"] == BASELINE_DB_NAMES, (
        f"distinct SQLite databases is {summary['distinct_db_names']} but the "
        f"exact baseline is {BASELINE_DB_NAMES}; update the baseline in this PR "
        "(lower it for a consolidation; raising it needs a justified new store)"
    )
    assert summary["distinct_jsonl_names"] == BASELINE_JSONL_NAMES, (
        f"distinct JSONL targets is {summary['distinct_jsonl_names']} "
        f"(exact baseline {BASELINE_JSONL_NAMES})"
    )
    assert summary["ledger_modules"] == BASELINE_LEDGER_MODULES, (
        f"ledger modules is {summary['ledger_modules']} "
        f"(exact baseline {BASELINE_LEDGER_MODULES})"
    )
    assert summary["ledger_classes"] == BASELINE_LEDGER_CLASSES, (
        f"ledger classes is {summary['ledger_classes']} "
        f"(exact baseline {BASELINE_LEDGER_CLASSES})"
    )


def test_inventory_schema():
    inv = build_inventory()
    assert inv["schema_version"] == 1
    assert sorted(inv["databases"]) == inv["databases"], "databases must be sorted"
    assert sorted(inv["jsonl_targets"]) == inv["jsonl_targets"]
    assert inv["summary"]["distinct_db_names"] == len(inv["databases"])
    # runtime.db and ontology.db are the two core stores the sync bridge names;
    # their presence is a cheap sanity check that the scan reached live source.
    assert "runtime.db" in inv["databases"]
    assert "ontology.db" in inv["databases"]
