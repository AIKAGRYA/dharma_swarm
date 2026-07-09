"""Unit tests for the governance gate aggregator classifier.

These exercise the pure classifier on in-code fixtures (no network). They lock
in the anti-deadlock contract: a gate that did not run is NOT a failure, and an
unrelated failing check is ignored.

Final proof of the CI *behavior* (that this workflow always runs and gates
merges) requires one real PR — that cannot be exercised locally.
"""

import importlib.util
import pathlib

_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts" / "governance" / "aggregate_gate_verdicts.py"
)
_spec = importlib.util.spec_from_file_location("aggregate_gate_verdicts", _SCRIPT)
agg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agg)


def _run(name, **kw):
    base = {"id": 1, "name": name, "status": "completed", "conclusion": "success"}
    base.update(kw)
    return base


def test_all_allowlisted_success_exits_zero():
    runs = [_run(n) for n in agg.ALLOWLIST]
    code, rows = agg.classify(runs)
    assert code == 0
    assert all(v == "PASS" for _, v, _ in rows)


def test_one_allowlisted_failure_exits_one():
    runs = [_run(n) for n in agg.ALLOWLIST]
    # flip semgrep to a failing conclusion
    runs[0] = _run("semgrep", conclusion="failure")
    code, rows = agg.classify(runs)
    assert code == 1
    verdicts = {n: v for n, v, _ in rows}
    assert verdicts["semgrep"] == "FAIL"


def test_gate_that_did_not_run_is_not_a_failure():
    # Only ONE allowlisted gate ran (path filter excluded the rest). No deadlock.
    runs = [_run("semgrep")]
    code, rows = agg.classify(runs)
    assert code == 0
    verdicts = {n: v for n, v, _ in rows}
    assert verdicts["semgrep"] == "PASS"
    assert verdicts["Fourfold Shakti Warrant"] == "NOT-RUN"


def test_empty_check_runs_exits_zero():
    # No gates ran at all -> nothing to fail on.
    code, rows = agg.classify([])
    assert code == 0
    assert all(v == "NOT-RUN" for _, v, _ in rows)


def test_unrelated_failure_is_ignored():
    runs = [_run("some-other-check", conclusion="failure"), _run("semgrep")]
    code, _ = agg.classify(runs)
    assert code == 0


def test_in_progress_allowlisted_gate_is_not_run_not_failure():
    # A gate that started but has not concluded must not block (anti-deadlock).
    runs = [_run("semgrep", status="in_progress", conclusion=None)]
    code, rows = agg.classify(runs)
    assert code == 0
    verdicts = {n: v for n, v, _ in rows}
    assert verdicts["semgrep"] == "NOT-RUN"


def test_non_success_terminal_conclusion_fails():
    # cancelled/timed_out are terminal but not passing -> real failure.
    for concl in ("cancelled", "timed_out", "action_required"):
        runs = [_run("Fourfold Shakti Warrant", conclusion=concl)]
        code, _ = agg.classify(runs)
        assert code == 1, concl


def test_neutral_and_skipped_pass():
    runs = [
        _run("semgrep", conclusion="neutral"),
        _run("TCB import & AST boundary", conclusion="skipped"),
    ]
    code, _ = agg.classify(runs)
    assert code == 0


def test_latest_rerun_wins():
    # An older failing run superseded by a newer successful re-run passes.
    runs = [
        _run("semgrep", id=1, conclusion="failure"),
        _run("semgrep", id=2, conclusion="success"),
    ]
    code, rows = agg.classify(runs)
    assert code == 0
    verdicts = {n: v for n, v, _ in rows}
    assert verdicts["semgrep"] == "PASS"


def test_latest_rerun_can_flip_to_fail():
    runs = [
        _run("semgrep", id=1, conclusion="success"),
        _run("semgrep", id=2, conclusion="failure"),
    ]
    code, _ = agg.classify(runs)
    assert code == 1


def test_self_test_mode_passes():
    assert agg.run_self_test() == 0
