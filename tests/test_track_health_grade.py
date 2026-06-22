"""Tests for scripts/governance/track_health_grade.py — the sign-off-gated,
quality-aggregated track grader.

Reviewer policy (operator, 2026-06-22): auditors must be Opus 4.8+ caliber.
The quorum is formed by INDEPENDENT RUNS of floor-meeting auditors; lower-tier
models (sonnet/haiku, pre-4.8 opus) are recorded but never counted.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_MOD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "track_health_grade.py"
_spec = importlib.util.spec_from_file_location("track_health_grade", _MOD_PATH)
thg = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
# Register before exec so @dataclass can resolve cls.__module__ during decoration.
sys.modules["track_health_grade"] = thg
_spec.loader.exec_module(thg)


def _signoff(grader: str, axes: dict[str, int], verdict: str,
             family: str = "claude-opus", model: str = "claude-opus-4-8",
             track_id: str = "t1") -> dict:
    return {
        "schema": thg.SIGNOFF_SCHEMA,
        "grader": grader,
        "model_family": family,
        "model": model,
        "tracks": {track_id: {"axes": axes, "verdict": verdict, "rationale": "x",
                              "evidence_refs": []}},
    }


def _axes(w, p, l, wc, b) -> dict[str, int]:
    return {"wired": w, "proven": p, "live": l, "world_class": wc, "balanced": b}


# --- capability floor -------------------------------------------------------

def test_capability_floor_accepts_opus_48_and_above():
    assert thg.meets_capability_floor("claude-opus", "claude-opus-4-8")
    assert thg.meets_capability_floor("claude-opus", "claude-opus-4-9")
    assert thg.meets_capability_floor("claude-opus", "opus-5.0")
    # Family named without a version id is trusted as the current opus.
    assert thg.meets_capability_floor("claude-opus", "")


def test_capability_floor_rejects_lower_tier_and_old_opus():
    assert not thg.meets_capability_floor("claude-sonnet", "claude-sonnet-4-6")
    assert not thg.meets_capability_floor("claude-haiku", "claude-haiku-4-5")
    assert not thg.meets_capability_floor("claude-opus", "claude-opus-4-6")
    assert not thg.meets_capability_floor("unknown", "")


def test_capability_floor_honors_allowlist(monkeypatch):
    monkeypatch.setattr(thg, "GRADER_ALLOWLIST", {"some-frontier-model-x"})
    assert thg.meets_capability_floor("other-family", "some-frontier-model-x")


# --- quorum -----------------------------------------------------------------

def test_no_signoffs_is_ungraded_not_crash():
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, [])
    assert th.grade == "UNGRADED"
    assert th.score is None
    assert th.attested_shippable is False
    assert any("no floor-meeting sign-offs" in n for n in th.notes)


def test_three_independent_opus_runs_form_quorum():
    receipts = [
        _signoff("opus-run-A", _axes(4, 4, 3, 4, 3), "SHIPPABLE"),
        _signoff("opus-run-B", _axes(3, 3, 3, 3, 2), "SHIPPABLE"),
        _signoff("opus-run-C", _axes(4, 3, 2, 3, 2), "SHIPPABLE"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    assert th.quorum_met is True          # single family is fine now — capability gates
    assert th.signoff_count == 3
    assert th.median_axes["wired"] >= thg.SHIPPABLE_WIRED_FLOOR
    assert th.attested_shippable is True


def test_below_floor_signoffs_recorded_but_not_counted():
    receipts = [
        _signoff("opus-run-A", _axes(4, 4, 3, 4, 3), "SHIPPABLE"),
        _signoff("sonnet-run", _axes(4, 4, 4, 4, 4), "SHIPPABLE",
                 family="claude-sonnet", model="claude-sonnet-4-6"),
        _signoff("haiku-run", _axes(4, 4, 4, 4, 4), "SHIPPABLE",
                 family="claude-haiku", model="claude-haiku-4-5"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    # Only the opus run counts -> below quorum; the two lighter ones are noted.
    assert th.signoff_count == 1
    assert th.quorum_met is False
    assert len(th.below_floor) == 2
    assert any("below-capability-floor" in n for n in th.notes)


def test_two_opus_runs_below_quorum():
    receipts = [
        _signoff("opus-run-A", _axes(4, 4, 4, 4, 2), "SHIPPABLE"),
        _signoff("opus-run-B", _axes(4, 4, 4, 4, 2), "SHIPPABLE"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    assert th.quorum_met is False
    assert th.grade.startswith("PROVISIONAL")
    assert th.attested_shippable is False


def test_overstated_when_file_green_but_quorum_withholds():
    receipts = [
        _signoff("opus-run-A", _axes(1, 1, 1, 2, 1), "OVERSTATED"),
        _signoff("opus-run-B", _axes(2, 1, 1, 2, 1), "OVERSTATED"),
        _signoff("opus-run-C", _axes(1, 2, 1, 1, 1), "IN_PROGRESS"),
    ]
    th = thg.grade_track("t1", {"passed": 7, "total": 7, "shippable": True}, receipts)
    assert th.quorum_met is True
    assert th.attested_shippable is False
    assert th.consensus_verdict in {"OVERSTATED", "IN_PROGRESS"}
    assert any("OVERSTATED" in n for n in th.notes)


def test_median_is_robust_to_one_outlier():
    receipts = [
        _signoff("opus-run-A", _axes(4, 4, 3, 3, 2), "SHIPPABLE"),
        _signoff("opus-run-B", _axes(4, 4, 3, 3, 2), "SHIPPABLE"),
        _signoff("opus-run-C", _axes(0, 0, 0, 0, 0), "BLOCKED"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    assert th.median_axes["wired"] == 4
    assert th.attested_shippable is True
    assert "opus-run-C:BLOCKED" in th.dissent


def test_incomplete_axes_are_ignored():
    bad = _signoff("opus-run-A", {"wired": 4, "proven": 4}, "SHIPPABLE")  # missing axes
    receipts = [
        bad,
        _signoff("opus-run-B", _axes(3, 3, 3, 3, 3), "SHIPPABLE"),
        _signoff("opus-run-C", _axes(3, 3, 3, 3, 3), "SHIPPABLE"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    assert th.signoff_count == 2          # malformed dropped -> below quorum
    assert th.quorum_met is False


# --- portfolio --------------------------------------------------------------

def test_portfolio_coverage_cap_penalizes_monothematic():
    strong = thg.TrackHealth(id="x", score=95.0, serves="substrate-nativeness")
    pg = thg.portfolio_grade([strong, strong], {"substrate-nativeness"}, total_objectives=3)
    assert pg["objective_coverage"] < 0.5
    assert pg["coverage_cap"] <= 84.9
    assert pg["portfolio_score"] <= 84.9
    assert pg["portfolio_grade"] in {"B", "C", "D", "F"}


def test_full_coverage_lifts_cap():
    strong = thg.TrackHealth(id="x", score=95.0, serves="o1")
    pg = thg.portfolio_grade([strong], {"o1", "o2", "o3"}, total_objectives=3)
    assert pg["coverage_cap"] == 100.0
    assert pg["portfolio_score"] == 95.0


def test_load_signoffs_skips_wrong_schema(tmp_path: Path):
    good = tmp_path / "a.signoff.json"
    good.write_text(json.dumps(_signoff("opus-run-A", _axes(3, 3, 3, 3, 3), "SHIPPABLE")))
    bad = tmp_path / "b.signoff.json"
    bad.write_text(json.dumps({"schema": "something_else", "tracks": {}}))
    loaded = thg.load_signoffs(tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["grader"] == "opus-run-A"
