"""Tests for the real oracle evaluator — apply, score, gate, tamper-check.

These run the ACTUAL path (git apply + subprocess oracle) in degraded/local
mode (docker_ok=False), which is hermetic (no network, no docker) but real:
a genuine diff is applied to a genuine tree and a genuine Python oracle runs.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from dharma_swarm.foundry.evaluator import Candidate
from dharma_swarm.foundry.oracle_evaluator import (
    OracleEvaluator,
    apply_diff,
    sentinel_metrics_parser,
)
from dharma_swarm.foundry.runner_isolation import IsolationPolicy


def _make_target(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    (root / "prog.py").write_text("VALUE = 1.0\n", encoding="utf-8")
    (root / "oracle.py").write_text(textwrap.dedent("""\
        import json
        import prog
        print("FOUNDRY_METRICS " + json.dumps({"combined_score": prog.VALUE}))
    """), encoding="utf-8")
    return root


def _evaluator(root: Path, tmp_path: Path) -> OracleEvaluator:
    return OracleEvaluator(
        evaluator_id="test-oracle",
        pinned_root=root,
        oracle_cmd=["python3", "oracle.py"],
        evolve_paths=["prog.py"],
        metric_parser=sentinel_metrics_parser(),
        policy=IsolationPolicy(timeout_s=30.0),
        scratch_root=tmp_path / "scratch",
        docker_ok=False,  # degraded local mode: hermetic, promotion blocked
    )


def _cand(diff: str) -> Candidate:
    return Candidate(candidate_id="c1", target_id="t", diff=diff)


IMPROVE_DIFF = (
    "--- a/prog.py\n+++ b/prog.py\n@@ -1 +1 @@\n-VALUE = 1.0\n+VALUE = 2.0\n"
)


def test_prepare_captures_baseline(tmp_path):
    ev = _evaluator(_make_target(tmp_path), tmp_path)
    ev.prepare()
    assert ev.baseline is not None
    assert ev.baseline.correctness_passed
    assert ev.baseline.primary_score == 1.0


def test_prepare_refuses_broken_target(tmp_path):
    root = _make_target(tmp_path)
    (root / "oracle.py").write_text("raise SystemExit(2)\n", encoding="utf-8")
    ev = _evaluator(root, tmp_path)
    with pytest.raises(RuntimeError, match="baseline oracle failed"):
        ev.prepare()


def test_apply_and_score_improvement(tmp_path):
    ev = _evaluator(_make_target(tmp_path), tmp_path)
    ev.prepare()
    metrics = ev.evaluate(_cand(IMPROVE_DIFF), seed=0)
    assert metrics.correctness_passed
    assert metrics.primary_score == 2.0
    assert "isolation=local_restricted" in metrics.notes
    assert metrics.metrics["promotion_allowed"] == 0.0  # degraded can never promote


def test_malformed_diff_scores_zero(tmp_path):
    ev = _evaluator(_make_target(tmp_path), tmp_path)
    ev.prepare()
    metrics = ev.evaluate(_cand("this is not a diff"), seed=0)
    assert not metrics.correctness_passed
    assert "apply_failed" in metrics.notes


def test_regression_gates_fitness(tmp_path):
    ev = _evaluator(_make_target(tmp_path), tmp_path)
    ev.prepare()
    breaking = (
        "--- a/prog.py\n+++ b/prog.py\n@@ -1 +1 @@\n-VALUE = 1.0\n+raise SystemExit(3)\n"
    )
    metrics = ev.evaluate(_cand(breaking), seed=0)
    assert not metrics.correctness_passed
    assert metrics.primary_score == 0.0


def test_tampering_with_oracle_zeroes_score(tmp_path):
    ev = _evaluator(_make_target(tmp_path), tmp_path)
    ev.prepare()
    # The evolved file plants a write OUTSIDE the evolve scope at import time —
    # the classic "rewrite the grader / plant evidence" move.
    tamper = (
        "--- a/prog.py\n+++ b/prog.py\n@@ -1 +1,2 @@\n-VALUE = 1.0\n"
        "+VALUE = 9.9\n+open('planted.txt', 'w').write('x')\n"
    )
    metrics = ev.evaluate(_cand(tamper), seed=0)
    assert not metrics.correctness_passed
    assert "oracle_tampered" in metrics.notes


def test_apply_diff_helper_roundtrip(tmp_path):
    root = _make_target(tmp_path)
    assert apply_diff(root, IMPROVE_DIFF) is None
    assert (root / "prog.py").read_text() == "VALUE = 2.0\n"
    assert apply_diff(root, "") == "empty diff"


def test_fuzz_fallback_applies_shifted_diff(tmp_path):
    # LLM diffs often carry slightly-wrong line numbers; git apply rejects
    # them, patch --fuzz recovers them. 74/78 ring-1 deaths was the lesson.
    root = tmp_path / "t2"
    root.mkdir()
    (root / "prog.py").write_text(
        "# header comment\n# another line\nVALUE = 1.0\n# trailer\n", encoding="utf-8")
    # Hunk claims line 1 but the change is really at line 3 (shifted context).
    shifted = (
        "--- a/prog.py\n+++ b/prog.py\n@@ -1,2 +1,2 @@\n # header comment\n"
        "-VALUE = 1.0\n+VALUE = 3.0\n"
    )
    from dharma_swarm.foundry.oracle_evaluator import apply_diff
    assert apply_diff(root, shifted, check_only=True) is None
    assert apply_diff(root, shifted) is None
    assert "VALUE = 3.0" in (root / "prog.py").read_text()
