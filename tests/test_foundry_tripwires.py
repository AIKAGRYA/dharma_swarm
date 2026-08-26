"""Tests for ring-1 tripwires — they must actually catch the known hacks."""

from __future__ import annotations

from dharma_swarm.foundry.evaluator import Candidate, EvalReceipt
from dharma_swarm.foundry.tripwires import (
    check_determinism,
    check_timing,
    scan_tripwires,
)


def _cand(diff: str) -> Candidate:
    return Candidate(candidate_id="c", target_id="t", diff=diff)


def _receipt(fitness: float, wall_clock_s: float) -> EvalReceipt:
    return EvalReceipt(
        candidate_id="c", target_id="t", evaluator_id="e", seed=0,
        fitness=fitness, correctness_passed=True, tripwires_fired=(),
        metrics={}, wall_clock_s=wall_clock_s,
        promotion_allowed=False, isolation_proof=None,
        sealed_at="now", digest="sha256:x",
    )


def test_empty_diff_fires_no_op():
    # The "vacuous fitness" hack: an empty candidate scores baseline fitness
    # and enters the archive as a win. Must trip.
    for diff in ("", "   \n  ", "--- a/kernels/x.py\n+++ b/kernels/x.py\n",
                 "--- a/kernels/x.py\n+++ b/kernels/x.py\n+\n-\n"):
        report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
        assert "no_op_diff" in report.fired, f"missed no-op: {diff!r}"


def test_real_change_does_not_fire_no_op():
    diff = "--- a/kernels/x.py\n+++ b/kernels/x.py\n+x = 1\n"
    assert "no_op_diff" not in scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"]).fired
    # raw non-diff blob with content is also a real change
    assert "no_op_diff" not in scan_tripwires(_cand("x = fast_path(y)")).fired


def test_out_of_scope_diff_fires():
    diff = "--- a/evaluator.py\n+++ b/evaluator.py\n+cheat = True\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "out_of_scope_diff" in report.fired
    assert not report.clean


def test_in_scope_diff_is_clean():
    diff = "--- a/kernels/attn.py\n+++ b/kernels/attn.py\n+x = 1\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert report.clean


def test_forbidden_import_fires():
    diff = "+++ b/kernels/attn.py\n+import os\n+os.system('echo hack > run.log')\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_forbidden_eval_call_fires():
    diff = "+++ b/kernels/attn.py\n+result = eval(user_input)\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_benign_python_is_clean():
    diff = "+++ b/kernels/attn.py\n+def faster(x):\n+    return x * 2\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert report.clean


def test_non_python_diff_does_not_crash():
    diff = "+++ b/kernels/attn.cu\n+__global__ void k() { /* cuda */ }\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.cu"])
    assert report.clean


def test_determinism_tripwire():
    assert check_determinism(_receipt(1.0, 0.5), _receipt(1.0, 0.5)) is None
    assert check_determinism(_receipt(1.0, 0.5), _receipt(1.4, 0.5)) == "nondeterministic_score"


def test_timing_tripwire():
    assert check_timing(_receipt(1.0, 0.5), floor_s=0.01) is None
    assert check_timing(_receipt(1.0, 0.0001), floor_s=0.01) == "suspicious_fast_eval"
