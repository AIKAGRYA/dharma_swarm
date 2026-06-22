"""Focused tests for the hardening predicate added to check_track_status.py.

`file_not_contains` asserts a pattern is ABSENT from an EXISTING file — the
content/witness check that hardens gameable file_exists proxies (a closure
receipt must not say "VERDICT: NOT CLOSED"; a witness must not cite an
operator-local "/Users/" path). A missing file is a FAIL, never a pass.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "check_track_status.py"
_spec = importlib.util.spec_from_file_location("check_track_status", _MOD)
cts = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules["check_track_status"] = cts
_spec.loader.exec_module(cts)


def test_file_not_contains_passes_when_absent(tmp_path: Path):
    f = tmp_path / "receipt.md"
    f.write_text("VERDICT: CLOSED\nall good\n")
    res = cts.check_file_not_contains(str(f), "VERDICT: NOT CLOSED")
    assert res.passed is True


def test_file_not_contains_fails_when_present(tmp_path: Path):
    f = tmp_path / "receipt.md"
    f.write_text("VERDICT: NOT CLOSED\n")
    res = cts.check_file_not_contains(str(f), "VERDICT: NOT CLOSED")
    assert res.passed is False


def test_file_not_contains_fails_on_missing_file(tmp_path: Path):
    # Absence cannot be verified on a missing file -> FAIL (not a free pass).
    res = cts.check_file_not_contains(str(tmp_path / "nope.md"), "/Users/")
    assert res.passed is False
    assert "missing" in res.detail


def test_file_not_contains_wired_into_evaluate(tmp_path: Path):
    f = tmp_path / "witness.md"
    f.write_text("db: /Users/dhyana/.dharma/state/runtime.db\n")
    res = cts.evaluate_criterion(
        {"id": "repo_checkable", "kind": "file_not_contains",
         "file": str(f), "pattern": "/Users/"})
    assert res.id == "repo_checkable"
    assert res.passed is False        # operator-local path present -> fails


def test_file_not_contains_malformed_is_finding_not_crash():
    res = cts.evaluate_criterion(
        {"id": "bad", "kind": "file_not_contains", "file": "x"})  # no pattern
    assert res.passed is False
    assert "malformed" in res.detail
