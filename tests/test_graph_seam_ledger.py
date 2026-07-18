"""Seam ledger schema + ratchet tests — DharmaGraph Antithesis v0, Phase A.

Guards three properties of ``tests/antithesis_support/seam_ledger.py`` and its
committed artifact ``reports/governance/dharmagraph_parity/seam_ledger.json``:

1. Determinism — two generations on the same tree are byte-identical, and
   the committed ledger matches a fresh generation (a graph edit that adds
   or moves an effect site must regenerate the ledger in the same PR).
2. Schema — every effect entry carries a resolvable ``file:line`` citation
   and closed-vocabulary category/classification values.
3. Ratchet — the bypass count only moves DOWN. Lowering the baseline is a
   deliberate edit in the same PR that mediates a seam (Phase B rule);
   raising it fails here, not in review.

Spec: docs/prompts/DHARMAGRAPH_ANTITHESIS_V0_GOAL_2026-07-18.md §Phase A.
"""

from __future__ import annotations

import json

from tests.antithesis_support.seam_ledger import (
    LEDGER_PATH,
    REPO_ROOT,
    build_ledger,
    render_ledger,
)

# Phase A baseline (2026-07-18, tree at PR #1030 merge). Phase B PRs lower
# this in the same PR that mediates a bypass family; it never goes up.
BYPASS_BASELINE = 148

CATEGORIES = {
    "time",
    "rng",
    "ordering",
    "filesystem",
    "sqlite",
    "env",
    "process",
    "network",
}
CLASSIFICATIONS = {"mediated", "bypass"}
SCOPES = {"module", "runtime"}


def test_ledger_regenerates_byte_identically():
    assert render_ledger() == render_ledger()


def test_committed_ledger_matches_tree():
    assert LEDGER_PATH.is_file(), (
        "seam_ledger.json missing; run "
        "python3 tests/antithesis_support/seam_ledger.py --write"
    )
    committed = LEDGER_PATH.read_text(encoding="utf-8")
    assert committed == render_ledger(), (
        "committed seam_ledger.json is stale relative to the tree; "
        "regenerate with python3 tests/antithesis_support/seam_ledger.py --write "
        "and commit it in the same PR as the code change"
    )


def test_ledger_schema():
    ledger = build_ledger()
    assert ledger["schema_version"] == 1
    assert ledger["workload"]["roots"] == ["dharma_swarm.graph"]
    assert ledger["modules"], "empty import closure"
    for module in ledger["modules"]:
        assert (REPO_ROOT / module["file"]).is_file(), module
    assert ledger["effects"], "empty effect inventory"
    for entry in ledger["effects"]:
        assert entry["category"] in CATEGORIES, entry
        assert entry["classification"] in CLASSIFICATIONS, entry
        assert entry["scope"] in SCOPES, entry
        cited = REPO_ROOT / entry["file"]
        assert cited.is_file(), entry
        line_count = len(
            cited.read_text(encoding="utf-8").splitlines()
        )
        assert 1 <= entry["line"] <= line_count, entry
        assert entry["id"] == f"{entry['file']}:{entry['line']}:{entry['col']}"
    summary = ledger["summary"]
    assert summary["effect_site_count"] == len(ledger["effects"])
    assert (
        summary["mediated_total"] + summary["bypass_total"]
        == summary["effect_site_count"]
    )
    assert summary["bypass_total"] == sum(
        summary["bypass_by_category"].values()
    )


def test_detector_sees_known_seam_sites():
    """Blindness control: if the scanner regresses to finding nothing, the
    known mediated seam consumers must make this fail loudly."""
    ledger = build_ledger()
    mediated_ids = {
        e["id"] for e in ledger["effects"] if e["classification"] == "mediated"
    }
    mediated_files = {i.rsplit(":", 2)[0] for i in mediated_ids}
    # The three mediated consumer surfaces named by the spec's Phase A entry
    # points, plus the seam implementation itself.
    for expected in (
        "dharma_swarm/graph/executor.py",  # effects.dispatch_order
        "dharma_swarm/graph/scheduler.py",  # effects.random() run-id mint
        "dharma_swarm/graph/durable_invoker.py",  # effects.now staleness
        "dharma_swarm/graph/effects.py",  # provider implementation
    ):
        assert expected in mediated_files, (expected, sorted(mediated_files))


def test_bypass_count_ratchets_down_only():
    ledger = build_ledger()
    bypass_total = ledger["summary"]["bypass_total"]
    assert bypass_total <= BYPASS_BASELINE, (
        f"bypass count rose from {BYPASS_BASELINE} to {bypass_total}: a new "
        "unmediated effect entered the workload's reach. Route it through "
        "EffectsProvider (dharma_swarm/graph/effects.py) or record the "
        "ownership blocker — never raise this baseline."
    )
    committed = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    assert committed["summary"]["bypass_total"] == bypass_total
