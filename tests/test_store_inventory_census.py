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

import json
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

# Baselines captured 2026-07-19 at origin/main. Lower them in the same PR that
# consolidates a store; they must never rise.
BASELINE_DB_NAMES = 35
BASELINE_JSONL_NAMES = 216
BASELINE_LEDGER_MODULES = 11
BASELINE_LEDGER_CLASSES = 10


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


def test_store_counts_only_ratchet_down():
    summary = build_inventory()["summary"]
    assert summary["distinct_db_names"] <= BASELINE_DB_NAMES, (
        f"distinct SQLite databases rose to {summary['distinct_db_names']} "
        f"(baseline {BASELINE_DB_NAMES}); a new store must be justified and the "
        "baseline lowered deliberately, never raised"
    )
    assert summary["distinct_jsonl_names"] <= BASELINE_JSONL_NAMES, (
        f"distinct JSONL targets rose to {summary['distinct_jsonl_names']} "
        f"(baseline {BASELINE_JSONL_NAMES})"
    )
    assert summary["ledger_modules"] <= BASELINE_LEDGER_MODULES, (
        f"ledger modules rose to {summary['ledger_modules']} "
        f"(baseline {BASELINE_LEDGER_MODULES})"
    )
    assert summary["ledger_classes"] <= BASELINE_LEDGER_CLASSES, (
        f"ledger classes rose to {summary['ledger_classes']} "
        f"(baseline {BASELINE_LEDGER_CLASSES})"
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
