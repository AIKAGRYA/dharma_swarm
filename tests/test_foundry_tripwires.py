"""Tests for ring-1 tripwires — they must actually catch the known hacks."""

from __future__ import annotations

import pytest

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
        metrics={}, wall_clock_s=wall_clock_s, promotion_allowed=False,
        isolation_proof=None, run_identity=None, sealed_at="now", digest="sha256:x",
    )


def test_out_of_scope_diff_fires():
    diff = "--- a/evaluator.py\n+++ b/evaluator.py\n+cheat = True\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "out_of_scope_diff" in report.fired
    assert not report.clean


def test_in_scope_diff_is_clean():
    diff = "--- a/kernels/attn.py\n+++ b/kernels/attn.py\n+x = 1\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert report.clean


def test_raw_blob_cannot_bypass_declared_path_scope():
    report = scan_tripwires(_cand("x = 1\n"), allowed_paths=["kernels/*.py"])
    assert "out_of_scope_diff" in report.fired


def test_parent_traversal_path_cannot_match_evolve_glob():
    diff = "--- a/kernels/../grader.py\n+++ b/kernels/../grader.py\n+cheat = True\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "out_of_scope_diff" in report.fired


@pytest.mark.parametrize(
    "hidden_section",
    [
        (
            "diff --git a/grader.py b/grader-renamed.py\n"
            "similarity index 100%\n"
            "rename from grader.py\n"
            "rename to grader-renamed.py\n"
        ),
        (
            "diff --git a/grader.bin b/grader.bin\n"
            "new file mode 100644\n"
            "Binary files /dev/null and b/grader.bin differ\n"
        ),
        (
            "diff --git a/grader.py b/grader.py\n"
            "old mode 100644\n"
            "new mode 100755\n"
        ),
    ],
)
def test_structural_git_sections_cannot_hide_out_of_scope_paths(hidden_section):
    allowed = (
        "--- a/kernels/a.py\n"
        "+++ b/kernels/a.py\n"
        "@@ -1 +1 @@\n"
        "-old = 1\n"
        "+new = 2\n"
    )
    report = scan_tripwires(
        _cand(allowed + hidden_section),
        allowed_paths=["kernels/*.py"],
    )
    assert "out_of_scope_diff" in report.fired


def test_unbound_mode_metadata_fails_closed():
    diff = (
        "--- a/kernels/a.py\n"
        "+++ b/kernels/a.py\n"
        "+new = 2\n"
        "old mode 100644\n"
        "new mode 100755\n"
    )
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "out_of_scope_diff" in report.fired
    assert "lacks a bound" in report.details["out_of_scope_diff"]


def test_forbidden_import_fires():
    diff = "+++ b/kernels/attn.py\n+import os\n+os.system('echo hack > run.log')\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_forbidden_eval_call_fires():
    diff = "+++ b/kernels/attn.py\n+result = eval(user_input)\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_indented_added_fragment_cannot_hide_forbidden_eval():
    diff = "+++ b/kernels/attn.py\n+    return eval(user_input)\n"
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_attribute_call_through_preexisting_forbidden_module_fires():
    diff = "+++ b/kernels/attn.py\n+result = os.system('id')\n"
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


@pytest.mark.parametrize(
    "diff",
    ["", "   \n", "--- a/k.py\n+++ b/k.py\n", "--- a/k.py\n+++ b/k.py\n+   \n"],
)
def test_no_effective_change_fires(diff):
    report = scan_tripwires(_cand(diff), allowed_paths=["k.py"])
    assert "no_op_diff" in report.fired


def test_provider_error_is_typed_separately_from_noop():
    candidate = Candidate(
        candidate_id="c",
        target_id="t",
        diff="",
        metadata={"proposal_status": "provider_error", "provider_error": "timeout"},
    )
    report = scan_tripwires(candidate)
    assert "provider_error" in report.fired
    assert "no_op_diff" not in report.fired
    assert report.details["provider_error"] == "timeout"


def test_determinism_tripwire():
    assert check_determinism(_receipt(1.0, 0.5), _receipt(1.0, 0.5)) is None
    assert check_determinism(_receipt(1.0, 0.5), _receipt(1.4, 0.5)) == "nondeterministic_score"
    assert (
        check_determinism(_receipt(float("inf"), 0.5), _receipt(float("inf"), 0.5))
        == "nondeterministic_score"
    )


def test_timing_tripwire():
    assert check_timing(_receipt(1.0, 0.5), floor_s=0.01) is None
    assert check_timing(_receipt(1.0, 0.0001), floor_s=0.01) == "suspicious_fast_eval"
    assert check_timing(_receipt(1.0, float("nan")), floor_s=0.01) == "suspicious_fast_eval"
