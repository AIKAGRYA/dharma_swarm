"""Smoke tests for the debug-corral projector (it must never crash; it must be honest)."""
import importlib.util
import subprocess
import sys
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / "scripts/governance/debug_corral.py"
spec = importlib.util.spec_from_file_location("debug_corral", SPEC)
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)


def test_signals_return_grades():
    for fn in (dc.signal_god_objects, dc.signal_wildcards, dc.signal_load_time_cycles):
        out = fn()
        assert "grade" in out and out["grade"] in {"RED", "AMBER", "GREEN"}


def test_load_time_cycles_uses_repo_relative_module_names(tmp_path):
    # Regression guard: absolute-path module naming once produced
    # dharma_swarm.dharma_swarm.* and MISSED package-local cycles (false-clean).
    pkg = tmp_path / "dharma_swarm"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "providers.py").write_text("from dharma_swarm import router_v1\n", encoding="utf-8")
    (pkg / "router_v1.py").write_text("from dharma_swarm import providers\n", encoding="utf-8")

    old_repo, old_pkg = dc.REPO, dc.PKG
    dc.REPO, dc.PKG = tmp_path, pkg
    try:
        cyc = dc.signal_load_time_cycles()
    finally:
        dc.REPO, dc.PKG = old_repo, old_pkg

    assert cyc["count"] == 1
    assert cyc["grade"] == "RED"
    assert "providers" in cyc["worst"] and "router_v1" in cyc["worst"]


def test_ratchet_parse_failure_is_red(monkeypatch, tmp_path):
    script = tmp_path / "scripts/governance/hygiene/ratchet.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")

    def bad_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="", stderr="boom")

    old_repo = dc.REPO
    dc.REPO = tmp_path
    monkeypatch.setattr(dc.subprocess, "run", bad_run)
    try:
        out = dc.ratchet_status()
    finally:
        dc.REPO = old_repo

    assert out["grade"] == "RED"
    assert out["green"] is False
    assert "boom" in out["raw"]


def test_strict_gates_use_current_python():
    assert all(cmd[0] == sys.executable for _, cmd in dc.CORE_GATES)
    assert not any("--max-baseline-age-days" in cmd for _, cmd in dc.CORE_GATES)


def test_render_never_crashes_and_states_projection_not_authority():
    d = dc.gather(deep=False, strict=False, fast=True, probes=False)
    text = dc.render(d)
    assert "DE-BUG CORRAL" in text and "creates no new authority" in text
    assert d["verdict"]["state"] in {"CLEAN", "ELEVATED"}


def test_probe_runner_marks_undergraded_advisory_as_warning(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="10 active track(s); 5 undergraded (below required evidence grade).\n",
            stderr="",
        )

    old_battery = dc.PROBE_BATTERY
    dc.PROBE_BATTERY = [
        dc.Probe(
            "claim-evidence-binding",
            "graded anti-slop bar",
            ["fake-claim-evidence"],
            warn_undergraded=True,
        )
    ]
    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    try:
        out = dc.run_probes()
    finally:
        dc.PROBE_BATTERY = old_battery

    assert out[0]["status"] == "WARN"
    assert out[0]["undergraded"] == 5


def test_full_mode_enables_deep_strict_and_probes(monkeypatch):
    seen = {}

    def fake_gather(*, deep, strict, fast, probes):
        seen.update({"deep": deep, "strict": strict, "fast": fast, "probes": probes})
        return {
            "slop": {"god_objects": {"grade": "GREEN"}, "load_time_cycles": {"grade": "GREEN"}, "wildcard_imports": {"grade": "GREEN"}},
            "debt": {
                "broken_register": {"present": False},
                "interface_mismatch": {"note": "", "present": False},
                "cybernetic_loops": {"note": "", "present": False},
                "corral_findings": {"note": ""},
            },
            "verdict": {
                "red_signals": 0,
                "open_debt": 0,
                "gate_failures": 0,
                "probe_failures": 0,
                "probe_warnings": 0,
                "state": "CLEAN",
            },
        }

    monkeypatch.setattr(dc, "gather", fake_gather)
    assert dc.main(["--full", "--json"]) == 0
    assert seen == {"deep": True, "strict": True, "fast": False, "probes": True}
