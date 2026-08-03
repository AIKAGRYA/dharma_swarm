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


# --- registry integrity (the 2026-07-04 phantom-gate fix) -------------------- #


def test_default_registry_has_no_phantom_targets():
    # Every declared target of every default gate must exist on THIS checkout.
    # This is the regression test for the 2026-07-04 audit: three gates pointed
    # at review-branch-only files and the probe reported REFUTED 0.0 on main.
    assert pp.validate_gates(pp.default_gates()) == []


def test_default_corral_gate_uses_exact_strict_argv():
    gate = next(g for g in pp.default_gates() if g.name == "verify-corral")

    assert list(gate.argv) == [
        "python3",
        "scripts/governance/verify_corral_findings.py",
        "--strict",
    ]


def test_strict_corral_gate_rejects_stale_line_receipt(tmp_path):
    corral = tmp_path / "DE_BUG_CORRAL"
    corral.mkdir()
    (corral / "01.md").write_text(
        """# Stale line fixture

### MAJOR · TC-01 · stale Pramana line reference

- Detail: `scripts/governance/pramana_probe.py:9999999` is past EOF.
- Status: OPEN
""",
        encoding="utf-8",
    )
    gate = next(g for g in pp.default_gates() if g.name == "verify-corral")
    expected_argv = [
        "python3",
        "scripts/governance/verify_corral_findings.py",
        "--strict",
    ]

    def run_strict_fixture(argv, cwd):
        assert list(argv) == expected_argv
        return pp.subprocess_runner(
            [sys.executable, *argv[1:], "--dir", str(corral)], cwd
        )

    report = pp.run_probe([gate], tier="medium", runner=run_strict_fixture)
    receipt = report.to_receipt()

    assert report.all_gates_passed is False
    assert report.outcomes[0].exit_code == 1
    assert "STALE-LINES-PAST-EOF" in report.outcomes[0].detail
    assert receipt["gates"][0]["ok"] is False
    assert receipt["gates"][0]["exit_code"] == 1


def test_default_registry_covers_pratyaksha():
    # The highest-weighted pramana (0.30, direct perception) previously had NO
    # gate at all; the registry must keep one.
    modes = {g.mode for g in pp.default_gates()}
    assert pp.PRATYAKSHA in modes
    assert pp.ARTHAPATTI in modes


def test_default_blocking_gate_targets_exist():
    blocking = [g for g in pp.default_gates() if g.blocking]
    assert blocking, "registry must keep a blocking arthapatti floor"
    for g in blocking:
        assert g.requires, "blocking gates must declare their targets"
        for req in g.requires:
            assert (REPO_ROOT / req).exists(), f"blocking gate target missing: {req}"


def test_cargo_gates_are_existence_guarded():
    has_crate = (REPO_ROOT / "native" / "dharma_kernels" / "Cargo.toml").is_file()
    cargo_gates = [g for g in pp.default_gates() if g.name.startswith("cargo-")]
    assert bool(cargo_gates) == has_crate


def test_validate_gates_flags_missing_target_and_cwd():
    phantom = pp.GateSpec("ghost", pp.ARTHAPATTI, "deep",
                          ["pytest", "tests/no_such_file.py"],
                          blocking=True, requires=("tests/no_such_file.py",))
    lost = pp.GateSpec("lost-cwd", pp.UPAMANA, "fast", ["cargo", "test"],
                       cwd=REPO_ROOT / "no" / "such" / "dir")
    errors = pp.validate_gates([phantom, lost])
    assert len(errors) == 2
    assert any("ghost" in e and "tests/no_such_file.py" in e for e in errors)
    assert any("lost-cwd" in e and "cwd" in e for e in errors)


def test_main_refuses_phantom_registry_with_config_exit(monkeypatch, capsys):
    phantom = pp.GateSpec("ghost", pp.ARTHAPATTI, "deep",
                          ["pytest", "tests/no_such_file.py"],
                          blocking=True, requires=("tests/no_such_file.py",))
    monkeypatch.setattr(pp, "default_gates", lambda target="dharma_swarm/": [phantom])
    rc = pp.main(["--tier", "deep"])
    assert rc == 3  # distinct config-error exit: no verdict was produced
    err = capsys.readouterr().err
    assert "CONFIG ERROR" in err and "ghost" in err


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
