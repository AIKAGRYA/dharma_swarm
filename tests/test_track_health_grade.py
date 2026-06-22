"""Tests for scripts/governance/track_health_grade.py — the sign-off-gated,
quality-aggregated track grader.

The grader's core functions are pure (no global path reads), so we test the
quorum discipline, median aggregation, overstated detection, and portfolio
coverage cap directly with synthetic sign-offs.
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


def _signoff(grader: str, family: str, axes: dict[str, int], verdict: str,
             track_id: str = "t1") -> dict:
    return {
        "schema": thg.SIGNOFF_SCHEMA,
        "grader": grader,
        "model_family": family,
        "tracks": {track_id: {"axes": axes, "verdict": verdict, "rationale": "x",
                              "evidence_refs": []}},
    }


def _axes(w, p, l, wc, b) -> dict[str, int]:
    return {"wired": w, "proven": p, "live": l, "world_class": wc, "balanced": b}


def test_no_signoffs_is_ungraded_not_crash():
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, [])
    assert th.grade == "UNGRADED"
    assert th.score is None
    assert th.attested_shippable is False
    assert any("no sign-offs" in n for n in th.notes)


def test_quorum_requires_three_graders_and_two_families():
    # Two graders, even strong ones, do not reach quorum -> provisional.
    receipts = [
        _signoff("A", "opus", _axes(4, 4, 4, 4, 2), "SHIPPABLE"),
        _signoff("B", "sonnet", _axes(4, 4, 4, 4, 2), "SHIPPABLE"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    assert th.quorum_met is False
    assert th.grade.startswith("PROVISIONAL")
    assert th.attested_shippable is False


def test_single_family_three_graders_fails_decorrelation():
    receipts = [
        _signoff("A", "opus", _axes(4, 4, 4, 4, 2), "SHIPPABLE"),
        _signoff("B", "opus", _axes(4, 4, 4, 4, 2), "SHIPPABLE"),
        _signoff("C", "opus", _axes(4, 4, 4, 4, 2), "SHIPPABLE"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    # 3 graders but 1 family -> below MIN_FAMILIES -> not attested.
    assert th.quorum_met is False
    assert th.attested_shippable is False


def test_attested_shippable_on_quorum_and_floors():
    receipts = [
        _signoff("A", "opus", _axes(4, 4, 3, 4, 3), "SHIPPABLE"),
        _signoff("B", "sonnet", _axes(3, 3, 3, 3, 2), "SHIPPABLE"),
        _signoff("C", "haiku", _axes(4, 3, 2, 3, 2), "SHIPPABLE"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    assert th.quorum_met is True
    assert th.median_axes["wired"] >= thg.SHIPPABLE_WIRED_FLOOR
    assert th.median_axes["proven"] >= thg.SHIPPABLE_PROVEN_FLOOR
    assert th.attested_shippable is True
    assert th.grade in {"A", "B", "C", "D", "F"}


def test_overstated_when_file_green_but_quorum_withholds():
    # File grade says SHIPPABLE, but graders see low wired/proven -> OVERSTATED.
    receipts = [
        _signoff("A", "opus", _axes(1, 1, 1, 2, 1), "OVERSTATED"),
        _signoff("B", "sonnet", _axes(2, 1, 1, 2, 1), "OVERSTATED"),
        _signoff("C", "haiku", _axes(1, 2, 1, 1, 1), "IN_PROGRESS"),
    ]
    th = thg.grade_track("t1", {"passed": 7, "total": 7, "shippable": True}, receipts)
    assert th.quorum_met is True
    assert th.attested_shippable is False
    assert th.consensus_verdict in {"OVERSTATED", "IN_PROGRESS"}
    assert any("OVERSTATED" in n for n in th.notes)


def test_median_is_robust_to_one_outlier():
    # Two graders say wired=4, one outlier says 0 -> median stays 4.
    receipts = [
        _signoff("A", "opus", _axes(4, 4, 3, 3, 2), "SHIPPABLE"),
        _signoff("B", "sonnet", _axes(4, 4, 3, 3, 2), "SHIPPABLE"),
        _signoff("C", "haiku", _axes(0, 0, 0, 0, 0), "BLOCKED"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    assert th.median_axes["wired"] == 4
    # Majority SHIPPABLE (2 of 3) and floors hold -> attested.
    assert th.attested_shippable is True
    assert "C:BLOCKED" in th.dissent


def test_incomplete_axes_are_ignored():
    bad = _signoff("A", "opus", {"wired": 4, "proven": 4}, "SHIPPABLE")  # missing axes
    receipts = [
        bad,
        _signoff("B", "sonnet", _axes(3, 3, 3, 3, 3), "SHIPPABLE"),
        _signoff("C", "haiku", _axes(3, 3, 3, 3, 3), "SHIPPABLE"),
    ]
    th = thg.grade_track("t1", {"passed": 5, "total": 5, "shippable": True}, receipts)
    # The malformed grader is dropped -> only 2 valid -> below quorum.
    assert th.signoff_count == 2
    assert th.quorum_met is False


def test_portfolio_coverage_cap_penalizes_monothematic():
    # All tracks strong, but only 1 of 3 spine objectives covered -> capped < A.
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
    good.write_text(json.dumps(_signoff("A", "opus", _axes(3, 3, 3, 3, 3), "SHIPPABLE")))
    bad = tmp_path / "b.signoff.json"
    bad.write_text(json.dumps({"schema": "something_else", "tracks": {}}))
    loaded = thg.load_signoffs(tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["grader"] == "A"
