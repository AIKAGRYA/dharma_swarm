"""Tests for ring-1 tripwires — they must actually catch the known hacks."""

from __future__ import annotations

from dharma_swarm.foundry.evaluator import Candidate, EvalReceipt
from dharma_swarm.foundry.tripwires import (
    check_determinism,
    check_timing,
    scan_tripwires,
    validate_diff_paths,
)


def _cand(diff: str) -> Candidate:
    return Candidate(candidate_id="c", target_id="t", diff=diff)


def _diff(path: str, added: str, removed: str = "OLD = 0") -> str:
    return (
        f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n"
        f"-{removed}\n+{added}\n"
    )


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
    for diff in ("", "   \n  ", _diff("kernels/x.py", "", "")):
        report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
        assert "no_op_diff" in report.fired, f"missed no-op: {diff!r}"


def test_header_only_is_malformed_not_a_genuine_no_op():
    report = scan_tripwires(
        _cand("--- a/kernels/x.py\n+++ b/kernels/x.py\n"),
        allowed_paths=["kernels/*.py"],
    )
    assert report.fired == ("malformed_diff",)


def test_real_change_does_not_fire_no_op():
    diff = _diff("kernels/x.py", "x = 1")
    assert "no_op_diff" not in scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"]).fired
    # raw non-diff blob with content is also a real change
    assert "no_op_diff" not in scan_tripwires(_cand("x = fast_path(y)")).fired


def test_out_of_scope_diff_fires():
    diff = _diff("evaluator.py", "cheat = True")
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "out_of_scope_diff" in report.fired
    assert not report.clean


def test_in_scope_diff_is_clean():
    diff = _diff("kernels/attn.py", "x = 1")
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert report.clean


def test_forbidden_import_fires():
    diff = _diff("kernels/attn.py", "import os\nos.system('echo hack > run.log')")
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_forbidden_eval_call_fires():
    diff = _diff("kernels/attn.py", "result = eval(user_input)")
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_indented_import_and_attribute_escape_cannot_evade_ast_gate():
    indented = _diff("kernels/attn.py", "if enabled:\n+    import os")
    assert "forbidden_primitive" in scan_tripwires(
        _cand(indented), allowed_paths=["kernels/*.py"]
    ).fired
    attribute = _diff("kernels/attn.py", "result = helper.eval(user_input)")
    assert "forbidden_primitive" in scan_tripwires(
        _cand(attribute), allowed_paths=["kernels/*.py"]
    ).fired


def test_unparseable_python_addition_fails_closed_before_evaluator():
    broken = _diff("kernels/attn.py", "def broken(:")
    report = scan_tripwires(_cand(broken), allowed_paths=["kernels/*.py"])
    assert report.fired == ("static_source_invalid",)


def test_fully_applied_source_is_scanned_when_proposer_supplies_it():
    candidate = _cand(_diff("kernels/attn.py", "result = fast(x)"))
    candidate.metadata["applied_source"] = "import os\nresult = fast(x)\n"
    report = scan_tripwires(candidate, allowed_paths=["kernels/*.py"])
    assert "forbidden_primitive" in report.fired


def test_benign_python_is_clean():
    diff = _diff("kernels/attn.py", "def faster(x):\n+    return x * 2")
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.py"])
    assert report.clean


def test_non_python_diff_does_not_crash():
    diff = _diff("kernels/attn.cu", "__global__ void k() { /* cuda */ }")
    report = scan_tripwires(_cand(diff), allowed_paths=["kernels/*.cu"])
    assert report.clean


def test_path_parser_rejects_traversal_absolute_and_mismatched_headers():
    traversal = "--- a/../grader.py\n+++ b/../grader.py\n@@ -1 +1 @@\n-x\n+y\n"
    absolute = "--- /etc/passwd\n+++ /etc/passwd\n@@ -1 +1 @@\n-x\n+y\n"
    mismatch = "--- a/kernel.py\n+++ b/grader.py\n@@ -1 +1 @@\n-x\n+y\n"
    assert validate_diff_paths(traversal).category == "unsafe_diff_path"
    assert validate_diff_paths(absolute).category == "unsafe_diff_path"
    assert validate_diff_paths(mismatch).category == "mismatched_diff_headers"


def test_path_parser_rejects_symlink_component_before_apply(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "target"
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    report = validate_diff_paths(
        _diff("link/payload.py", "x = 1"), tree_root=root
    )
    assert report.category == "symlink_escape"


def test_plain_file_scope_does_not_admit_fake_child_path():
    report = scan_tripwires(
        _cand(_diff("prog.py/child", "x = 1")), allowed_paths=["prog.py"]
    )
    assert report.fired == ("out_of_scope_diff",)


def test_determinism_tripwire():
    assert check_determinism(_receipt(1.0, 0.5), _receipt(1.0, 0.5)) is None
    assert check_determinism(_receipt(1.0, 0.5), _receipt(1.4, 0.5)) == "nondeterministic_score"


def test_timing_tripwire():
    assert check_timing(_receipt(1.0, 0.5), floor_s=0.01) is None
    assert check_timing(_receipt(1.0, 0.0001), floor_s=0.01) == "suspicious_fast_eval"
