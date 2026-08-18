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
from pathlib import Path

from tests.antithesis_support.seam_ledger import (
    LEDGER_PATH,
    REPO_ROOT,
    _module_to_path,
    build_ledger,
    render_ledger,
)

# Phase A baseline (2026-07-18, tree at PR #1030 merge). Phase B PRs lower
# this in the same PR that mediates a bypass family; it never goes up.
# 232 -> 230 (PR #1129): deleting the pairwise idea-link clique writer removed
# its sqlite3.connect and uuid.uuid4 effect sites from the workload's reach.
BYPASS_BASELINE = 230

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
    assert ledger["schema_version"] == 2
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
    assert bypass_total == BYPASS_BASELINE, (
        f"bypass count is {bypass_total}, stored baseline is {BYPASS_BASELINE}. "
        "Higher: a new unmediated effect entered the workload's reach — route "
        "it through EffectsProvider (dharma_swarm/graph/effects.py) or record "
        "the ownership blocker; never raise this baseline. Lower: a seam was "
        "mediated — lower BYPASS_BASELINE in the SAME PR so the ratchet holds "
        "with no slack (Codex review 2026-07-18)."
    )
    committed = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    assert committed["summary"]["bypass_total"] == bypass_total


# --- Codex review round (2026-07-18) — one regression test per finding ---


def test_module_resolution_is_case_exact(monkeypatch):
    """Imported symbols must not become modules on case-insensitive hosts."""
    expected = (
        REPO_ROOT / "packages" / "telos-kernel" / "telos_kernel" / "manifest.py"
    )
    assert _module_to_path("telos_kernel.manifest") == expected

    # Make the old ``Path.is_file`` implementation behave as it does on a
    # case-insensitive filesystem even when this test runs on Linux.  The
    # resolver must use exact directory-entry names instead of trusting that
    # aliased lookup.
    aliased = expected.with_name("Manifest.py")
    real_is_file = Path.is_file

    def case_insensitive_is_file(path):
        return path == aliased or real_is_file(path)

    monkeypatch.setattr(Path, "is_file", case_insensitive_is_file)
    assert _module_to_path("telos_kernel.Manifest") is None


def test_package_init_relative_imports_resolve_to_package():
    """`from .artifacts import X` in dharma_swarm/engine/__init__.py must
    resolve to dharma_swarm.engine.artifacts, not dharma_swarm.artifacts."""
    import ast

    from tests.antithesis_support.seam_ledger import _ImportCollector

    tree = ast.parse("from .artifacts import ExecutionArtifact\n")
    collector = _ImportCollector("dharma_swarm.engine", is_package=True)
    collector.visit(tree)
    assert "dharma_swarm.engine.artifacts" in collector.imports
    assert "dharma_swarm.artifacts" not in collector.imports

    # A plain module keeps the original semantics.
    collector = _ImportCollector("dharma_swarm.graph.executor", is_package=False)
    collector.visit(ast.parse("from .effects import EffectsProvider\n"))
    assert "dharma_swarm.graph.effects" in collector.imports


def test_closure_includes_package_siblings_and_repo_local_packages():
    """The committed closure must include the surfaces the Codex review
    proved reachable: engine package siblings and telos_kernel."""
    ledger = build_ledger()
    modules = {m["module"] for m in ledger["modules"]}
    assert "dharma_swarm.engine.artifacts" in modules
    assert any(m.startswith("telos_kernel") for m in modules), sorted(modules)[:5]


def test_scanner_resolves_import_aliases():
    from tests.antithesis_support.effect_scan import scan_source

    sites = scan_source(
        "import time as clock\n"
        "import random as rng\n"
        "from uuid import uuid4 as make_id\n"
        "def f():\n"
        "    a = clock.time()\n"
        "    b = rng.random()\n"
        "    return make_id(), a, b\n",
        "dharma_swarm/graph/_alias_probe.py",
    )
    symbols = {(s["symbol"], s["category"]) for s in sites}
    assert ("time.time", "time") in symbols, symbols
    assert ("random.random", "rng") in symbols, symbols
    assert ("uuid.uuid4", "rng") in symbols, symbols


def test_scanner_counts_network_call_sites():
    from tests.antithesis_support.effect_scan import scan_source

    sites = scan_source(
        "import requests\n"
        "import httpx\n"
        "def f(url):\n"
        "    requests.get(url)\n"
        "    return httpx.AsyncClient()\n",
        "dharma_swarm/graph/_network_probe.py",
    )
    network = [s for s in sites if s["category"] == "network"]
    assert len(network) == 2, sites
    assert all(s["classification"] == "bypass" for s in network)
