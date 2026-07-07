"""Tests for the slop ratchet gate (Stop-the-Slop probe delta-ratchet)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "slop_ratchet", REPO_ROOT / "scripts" / "governance" / "slop_ratchet.py")
assert _SPEC is not None and _SPEC.loader is not None
slop_ratchet = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(slop_ratchet)


def _sig(grade="GREEN", confidence="HIGH", count=0, measured="0"):
    return {"grade": grade, "confidence": confidence, "count": count, "measured": measured}


def _scoped(signals):
    return {"dharma_swarm": {"composite": "X", "signals": signals}}


def test_pass_when_unchanged():
    base = _scoped({"Silent swallows": _sig("AMBER", "HIGH", 10)})
    cur = _scoped({"Silent swallows": _sig("AMBER", "HIGH", 10)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"] and not v["regressions"]


def test_count_regression_fails():
    base = _scoped({"Silent swallows": _sig("AMBER", "HIGH", 10)})
    cur = _scoped({"Silent swallows": _sig("AMBER", "HIGH", 11)})
    v = slop_ratchet.evaluate(cur, base)
    assert not v["passed"]
    assert "Silent swallows" in v["regressions"][0]


def test_grade_regression_fails_even_with_none_count():
    base = _scoped({"Import cycles": _sig("AMBER", "HIGH", None)})
    cur = _scoped({"Import cycles": _sig("RED", "HIGH", None)})
    v = slop_ratchet.evaluate(cur, base)
    assert not v["passed"]


def test_improvement_reported_and_passes():
    base = _scoped({"God objects": _sig("RED", "HIGH", 8)})
    cur = _scoped({"God objects": _sig("RED", "HIGH", 7)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"]
    assert v["improvements"]


def test_low_confidence_regression_is_advisory():
    base = _scoped({"Narrative comments": _sig("GREEN", "LOW", 40)})
    cur = _scoped({"Narrative comments": _sig("AMBER", "LOW", 90)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"]
    assert v["advisory"]


def test_low_confidence_baseline_regression_is_advisory():
    # proxy baseline vs real instrument now present: incomparable counts
    base = _scoped({"Complexity inflation": _sig("AMBER", "LOW", 253)})
    cur = _scoped({"Complexity inflation": _sig("RED", "HIGH", 300)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"]
    assert v["advisory"]


def test_confidence_flip_regression_is_advisory():
    base = _scoped({"Dead code": _sig("AMBER", "MEDIUM", 50)})
    cur = _scoped({"Dead code": _sig("RED", "HIGH", 80)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"]
    assert v["advisory"]


def test_time_windowed_regression_is_advisory():
    base = _scoped({"Churn/revert": _sig("GREEN", "HIGH", 2)})
    cur = _scoped({"Churn/revert": _sig("RED", "HIGH", 60)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"]
    assert v["advisory"]


def test_unassessed_axis_skipped_not_failed():
    base = _scoped({"Dead code": _sig("AMBER", "MEDIUM", 50)})
    cur = _scoped({"Dead code": _sig("—", "UNASSESSED", None)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"]
    assert any("UNASSESSED" in s for s in v["skipped"])


def test_missing_scope_in_baseline_skipped():
    base = {}
    cur = _scoped({"God objects": _sig("RED", "HIGH", 8)})
    v = slop_ratchet.evaluate(cur, base)
    assert v["passed"]
    assert v["skipped"]


def test_digest_round_trip():
    payload = {"generated_at": "t", "scopes": _scoped({"God objects": _sig()})}
    payload["digest"] = slop_ratchet._digest(payload)
    assert slop_ratchet._digest(payload) == payload["digest"]
    payload["scopes"]["dharma_swarm"]["signals"]["God objects"]["count"] = 99
    assert slop_ratchet._digest(payload) != payload["digest"]


def test_committed_baseline_replays_digest():
    baseline_path = slop_ratchet.BASELINE_PATH
    if not baseline_path.exists():
        import pytest
        pytest.skip("baseline not committed yet")
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert payload["digest"] == slop_ratchet._digest(payload)
