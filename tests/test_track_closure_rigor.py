"""Tests for the rigorous track-closure predicates added to check_track_status.py.

The point: "all completion criteria pass" must NOT mean shippable when the
criteria are existence-only (file_exists / file_contains) or when blocker
next-items are still open. Closure is computed from evidence strength + blocker
state — the antidote to existence-grep sign-off."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from check_track_status import (  # type: ignore  # noqa: E402
    EXISTENCE_KINDS,
    RIGOROUS_KINDS,
    check_commit_on_main,
    check_receipt_valid,
    check_test_passes,
    evaluate_criterion,
    evaluate_track,
)


# --------------------------------------------------------------- new predicates
def test_commit_on_main_true_for_ancestor():
    # The first commit in repo history is an ancestor of HEAD/origin/main.
    import subprocess

    root = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    ).stdout.split()[0]
    assert check_commit_on_main(root).passed is True


def test_commit_on_main_false_for_unknown_commit():
    # A non-existent commit cannot be proven on main -> conservative fail.
    assert check_commit_on_main("0000000000000000000000000000000000000000").passed is False


def test_test_passes_runs_and_distinguishes_pass_from_fail(tmp_path):
    good = tmp_path / "test_good.py"
    good.write_text("def test_ok():\n    assert 1 == 1\n")
    bad = tmp_path / "test_bad.py"
    bad.write_text("def test_no():\n    assert 1 == 2\n")
    assert check_test_passes(f"{good}::test_ok").passed is True
    # A failing (or trivially-passing-but-wrong) test must NOT pass.
    assert check_test_passes(f"{bad}::test_no").passed is False


def test_test_passes_marks_unverified_when_pytest_absent(monkeypatch):
    """When the test RUNNER itself is missing (minimal-deps governance gate),
    a test_passes check is unverified — executed=False, passed=False — not a
    hard failure. A missing runner is not evidence the code regressed."""
    import subprocess as _sp

    import check_track_status as cts  # type: ignore

    class _FakeProc:
        returncode = 1
        stdout = ""
        stderr = "/usr/bin/python3: No module named pytest\n"

    monkeypatch.setattr(cts.subprocess, "run", lambda *a, **k: _FakeProc())
    r = cts.check_test_passes("tests/test_whatever.py")
    assert r.passed is False
    assert r.executed is False
    assert "could not execute" in r.detail
    del _sp  # silence unused-import lint in some configs


def test_test_passes_executed_true_on_real_run(tmp_path):
    good = tmp_path / "test_good.py"
    good.write_text("def test_ok():\n    assert True\n")
    r = check_test_passes(f"{good}::test_ok")
    assert r.passed is True and r.executed is True


def test_unverified_test_runs_do_not_block_the_gate(monkeypatch):
    """End-to-end against the REAL portfolio: when every test_passes criterion
    can only report 'could not execute' (the minimal-deps governance gate has
    no pytest), the checker must still exit 0 — a missing runner is not a
    regression and must not manufacture a false CI failure. Authority for this
    is the unverified-vs-regression split in run()."""
    import argparse

    import check_track_status as cts  # type: ignore

    # Mark every rigorous test_passes criterion as previously-passing so the
    # regression path is exercised, then force it unverified now.
    raw = cts.load_active_track(cts.ACTIVE_TRACK_PATH)
    portfolio = cts.normalize_portfolio(raw)
    prior: dict[str, set[str]] = {}
    for t in portfolio["active_tracks"]:
        ids = {c.get("id") for c in (t.get("completion_criteria") or [])
               if c.get("kind") == "test_passes"}
        if ids:
            prior[t["id"]] = ids
    assert prior, "expected at least one test_passes criterion in the portfolio"

    def _unverified(_target, timeout=180):
        return cts.CriterionResult(id="", kind="test_passes", passed=False,
                                   executed=False,
                                   detail="pytest not installed (could not execute)")

    monkeypatch.setattr(cts, "check_test_passes", _unverified)
    monkeypatch.setattr(cts, "_load_prior_passed", lambda: prior)
    monkeypatch.setattr(cts, "emit_reports", lambda *_a, **_k: None)
    args = argparse.Namespace(enforce_ttl=False)
    assert cts.run(args) == 0  # unverified must not block


def test_receipt_valid_requires_keys(tmp_path):
    receipt = tmp_path / "r.json"
    receipt.write_text('{"closeout_state": "positive_lift_candidate", "score": 1.0}')
    assert check_receipt_valid(str(receipt), ["closeout_state", "score"]).passed is True
    assert check_receipt_valid(str(receipt), ["missing_key"]).passed is False
    assert check_receipt_valid(str(tmp_path / "nope.json"), []).passed is False


def test_new_kinds_dispatch_through_evaluate_criterion():
    r = evaluate_criterion({"id": "x", "kind": "commit_on_main", "commit": "deadbeef"})
    assert r.kind == "commit_on_main" and r.passed is False
    # malformed -> failing result, never an exception
    assert evaluate_criterion({"id": "y", "kind": "test_passes"}).passed is False
    assert evaluate_criterion({"id": "z", "kind": "receipt_valid"}).passed is False


# ------------------------------------------------------------------ rigor gate
def _track(criteria, *, next_items=None, status="ACTIVE"):
    return {
        "id": "t",
        "status": status,
        "completion_criteria": criteria,
        "next_items": next_items or [],
    }


def test_existence_only_criteria_are_not_shippable():
    """All file_exists/file_contains pass -> criteria_pass True, but NOT shippable
    (no rigorous evidence). This is the core anti-theater invariant."""
    t = _track([
        {"id": "a", "kind": "file_exists", "file": "CLAUDE.md"},
        {"id": "b", "kind": "file_contains", "file": "CLAUDE.md", "pattern": "dharma"},
    ])
    r = evaluate_track(t)
    assert r["criteria_pass"] is True
    assert r["shippable"] is False
    assert r["has_rigorous_evidence"] is False
    assert any("existence-only" in b for b in r["ship_blocks"])


def _root_commit() -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    ).stdout.split()[0]


def test_open_blocker_blocks_shippable_even_with_rigorous_evidence():
    t = _track(
        [{"id": "c", "kind": "commit_on_main", "commit": _root_commit()}],
        next_items=[{"id": 1, "what": "do the thing", "blocker": True}],
    )
    r = evaluate_track(t)
    assert r["has_rigorous_evidence"] is True  # the commit IS on main
    assert r["open_blocker_count"] == 1
    assert r["shippable"] is False  # ...but an open blocker still blocks it
    assert any("open blocker" in b for b in r["ship_blocks"])


def test_rigorous_evidence_plus_no_blockers_earns_shippable():
    t = _track(
        [
            {"id": "a", "kind": "file_exists", "file": "CLAUDE.md"},
            {"id": "b", "kind": "commit_on_main", "commit": _root_commit()},
        ],
        next_items=[{"id": 1, "what": "polish", "blocker": False}],
    )
    r = evaluate_track(t)
    assert r["has_rigorous_evidence"] is True
    assert r["ship_blocks"] == []
    assert r["shippable"] is True


def test_rigor_kind_sets_are_disjoint_and_sane():
    assert RIGOROUS_KINDS.isdisjoint(EXISTENCE_KINDS)
    assert "test_passes" in RIGOROUS_KINDS and "commit_on_main" in RIGOROUS_KINDS
    assert "file_exists" in EXISTENCE_KINDS and "file_contains" in EXISTENCE_KINDS


def test_provider_routing_track_earns_rigorous_shippable():
    """Integration: the real provider-routing track in ACTIVE_TRACK.yaml now
    carries rigorous evidence (passing precedence test + commit_on_main) and no
    open blockers -> SHIPPABLE under the rigorous bar."""
    from check_track_status import _parse_minimal_yaml, normalize_portfolio

    raw = _parse_minimal_yaml((REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml").read_text())
    portfolio = normalize_portfolio(raw)
    track = next(
        t for t in portfolio["active_tracks"]
        if t.get("id") == "provider-routing-consolidation-2026-06"
    )
    r = evaluate_track(track)
    assert r["has_rigorous_evidence"] is True, r["ship_blocks"]
    assert r["shippable"] is True, r["ship_blocks"]


def test_provider_routing_track_eval_is_repo_root_anchored(tmp_path, monkeypatch):
    """Track criteria are authored as repo-relative paths and pytest targets.
    Evaluation must not depend on the caller's current working directory."""
    from check_track_status import _parse_minimal_yaml, normalize_portfolio

    monkeypatch.chdir(tmp_path)
    raw = _parse_minimal_yaml((REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml").read_text())
    portfolio = normalize_portfolio(raw)
    track = next(
        t for t in portfolio["active_tracks"]
        if t.get("id") == "provider-routing-consolidation-2026-06"
    )
    r = evaluate_track(track)
    assert r["criteria_pass"] is True, [c.detail for c in r["completion"] if not c.passed]
    assert r["shippable"] is True, r["ship_blocks"]
