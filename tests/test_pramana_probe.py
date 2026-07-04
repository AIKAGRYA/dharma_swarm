"""Tests for the tiered pramana verification conductor (scripts/governance/pramana_probe.py).

The pure core (gate-outcome -> pramana -> composite -> evidence tier) is tested
with an INJECTED fake runner so the tests are deterministic and never shell out
to the real engines. The arthapatti blocking floor is the load-bearing safety
property for unattended self-improvement, so it gets the most coverage.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "pramana_probe", REPO_ROOT / "scripts" / "governance" / "pramana_probe.py"
)
pp = importlib.util.module_from_spec(_spec)
# Register before exec so dataclass annotation resolution (with
# `from __future__ import annotations`) can find the module in sys.modules.
sys.modules["pramana_probe"] = pp
_spec.loader.exec_module(pp)  # type: ignore[union-attr]


def _runner_from(table):
    """Build a fake runner returning (exit_code, duration_ms, detail) keyed by argv[0]+argv[1]."""
    def run(argv, cwd):
        key = " ".join(argv[:2])
        code = table.get(key, table.get(argv[0], 0))
        return code, 5, f"fake:{key}"
    return run


FAST_OK = pp.GateSpec("ruff", pp.ANUMANA, "fast", ["ruff", "check"])
FAST_FAIL = pp.GateSpec("ruff", pp.ANUMANA, "fast", ["ruff", "check"])
BLOCK = pp.GateSpec("inv", pp.ARTHAPATTI, "deep", ["pytest", "x"], blocking=True)


# --- tier selection --------------------------------------------------------- #


def test_select_gates_is_cumulative():
    gates = pp.default_gates()
    fast = pp.select_gates(gates, "fast")
    deep = pp.select_gates(gates, "deep")
    assert all(g.tier == "fast" for g in fast)
    assert len(deep) >= len(fast)          # deep includes the cheaper tiers
    assert any(g.tier == "deep" for g in deep)


def test_select_gates_rejects_unknown_tier():
    import pytest
    with pytest.raises(ValueError):
        pp.select_gates(pp.default_gates(), "ludicrous")


# --- evidence tiers --------------------------------------------------------- #


def test_all_green_is_verified():
    report = pp.run_probe([FAST_OK], tier="fast", runner=_runner_from({}))
    assert report.verdict == pp.VERIFIED
    assert report.all_gates_passed is True
    assert report.overall_score >= 0.9


def test_non_blocking_failure_degrades_not_refutes():
    # A MIX of mostly-passing gates with one failed NON-blocking gate lowers
    # the score (degrade) but does not breach the blocking floor: not REFUTED.
    passing = [pp.GateSpec(f"ok{i}", pp.ANUMANA, "fast", ["ok", str(i)]) for i in range(5)]
    failing = pp.GateSpec("ruff", pp.ANUMANA, "fast", ["ruff", "check"])  # non-blocking
    report = pp.run_probe(passing + [failing], tier="fast", runner=_runner_from({"ruff check": 1}))
    assert report.verdict in (pp.WEAK, pp.SUPPORTED)   # degraded, not refuted
    assert not report.blocking_failures                # floor intact
    assert report.all_gates_passed is False             # CI still sees a failure
    assert report.blocking_floor_held is True          # but the blocking floor held


# --- the arthapatti BLOCKING floor (the safety-critical property) ----------- #


def test_blocking_failure_refutes_regardless_of_green():
    # Many green gates + one failed BLOCKING gate => REFUTED, score 0.
    greens = [pp.GateSpec(f"g{i}", pp.ANUMANA, "fast", ["ok", str(i)]) for i in range(8)]
    report = pp.run_probe(greens + [BLOCK], tier="deep", runner=_runner_from({"pytest x": 1}))
    assert report.verdict == pp.REFUTED
    assert report.all_gates_passed is False
    assert report.blocking_floor_held is False
    assert report.overall_score == 0.0
    assert report.blocking_failures  # the floor recorded the breach


def test_blocking_gate_passing_does_not_refute():
    report = pp.run_probe([FAST_OK, BLOCK], tier="deep", runner=_runner_from({}))
    assert report.verdict in (pp.VERIFIED, pp.SUPPORTED)
    assert report.all_gates_passed is True
    assert report.blocking_floor_held is True


# --- receipt projection ----------------------------------------------------- #


def test_receipt_is_a_projection_not_authority():
    report = pp.run_probe([FAST_OK, BLOCK], tier="deep", runner=_runner_from({}))
    receipt = report.to_receipt()
    assert receipt["schema"] == "dharma.pramana_probe.receipt.v1"
    assert "projection" in receipt["note"]
    assert receipt["verdict"] == report.verdict
    assert {g["name"] for g in receipt["gates"]} == {"ruff", "inv"}
    # every gate carries its pramana + tier provenance
    assert all("pramana" in g and "tier" in g for g in receipt["gates"])


def test_gate_to_pramana_maps_pass_and_fail():
    ok = pp.GateOutcome("t", pp.PRATYAKSHA, "fast", True, 0, 3, False)
    bad = pp.GateOutcome("t", pp.PRATYAKSHA, "fast", False, 1, 3, False)
    assert pp.gate_to_pramana(ok).passed is True and pp.gate_to_pramana(ok).confidence == 1.0
    assert pp.gate_to_pramana(bad).passed is False and pp.gate_to_pramana(bad).confidence == 0.0
