"""Tests for scripts/governance/criterion_lint.py — the criterion smell linter.

Verifies it catches the gameable patterns the Opus 4.8 audit found by hand, and
that it does NOT false-positive on the hardened content/witness criteria.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "criterion_lint.py"
_spec = importlib.util.spec_from_file_location("criterion_lint", _MOD)
cl = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules["criterion_lint"] = cl
_spec.loader.exec_module(cl)


def _smells(crit: dict, paired: set[str] | None = None) -> set[str]:
    return {s.smell for s in cl.lint_criterion("t", crit, paired or set())}


# --- catches the gameable patterns ------------------------------------------

def test_catches_tautological_grep():
    crit = {"id": "nats_transport_landed", "kind": "file_contains",
            "file": "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md", "pattern": "NATS"}
    assert "tautological_grep" in _smells(crit)


def test_catches_import_only_check():
    crit = {"id": "agent_runner_calls_spine", "kind": "file_contains",
            "file": "dharma_swarm/agent_runner.py",
            "pattern": r"(?m)^\s*from dharma_swarm\.spine"}
    assert "import_only_check" in _smells(crit)


def test_catches_operator_local_path():
    crit = {"id": "x", "kind": "file_contains",
            "file": "reports/x.md", "pattern": "/Users/dhyana/.dharma"}
    assert "operator_local_path" in _smells(crit)


def test_catches_presence_proxy_for_run_when_unpaired():
    crit = {"id": "composer_wake_witness_pending", "kind": "file_exists",
            "file": "reports/sovereign_holons/COMPOSER_WAKE_WITNESSED.md"}
    assert "presence_proxy_for_run" in _smells(crit)


def test_missing_owned_surface_flags_nonexistent_py():
    smells = cl.lint_track_surfaces(
        {"id": "t", "owned_surfaces": ["dharma_swarm/definitely_not_here.py"]})
    assert any(s.smell == "missing_owned_surface" for s in smells)


# --- does NOT false-positive on hardened / legitimate criteria --------------

def test_status_assertion_is_not_tautological():
    # "VERDICT: CLOSED" reads a real status (has whitespace/colon) -> clean.
    crit = {"id": "loop1_closure_verdict_closed", "kind": "file_contains",
            "file": "reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md",
            "pattern": "VERDICT: CLOSED"}
    assert _smells(crit) == set()


def test_file_not_contains_is_never_flagged():
    crit = {"id": "gate1_witness_repo_checkable", "kind": "file_not_contains",
            "file": "reports/governance/GATE1_WITNESSED.md", "pattern": "/Users/"}
    assert _smells(crit) == set()


def test_presence_proxy_suppressed_when_paired():
    crit = {"id": "gate1_witnessed", "kind": "file_exists",
            "file": "reports/governance/GATE1_WITNESSED.md"}
    paired = {"reports/governance/GATE1_WITNESSED.md"}
    assert "presence_proxy_for_run" not in _smells(crit, paired)


def test_existing_owned_surface_is_clean():
    smells = cl.lint_track_surfaces(
        {"id": "t", "owned_surfaces": ["scripts/governance/criterion_lint.py"]})
    assert smells == []


def test_glob_owned_surface_is_not_flagged():
    smells = cl.lint_track_surfaces(
        {"id": "t", "owned_surfaces": ["dharma_swarm/holon_*.py"]})
    assert smells == []


def test_live_portfolio_lints_without_crash():
    # The real ACTIVE_TRACK.yaml must lint cleanly to a result (exit 0 advisory).
    import argparse
    rc = cl.run(argparse.Namespace(strict=False))
    assert rc == 0
    assert cl.OUT_JSON.exists() and cl.OUT_MD.exists()
