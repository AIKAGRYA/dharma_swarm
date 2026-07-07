from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import fresh_task_oracle, pr_suite_grader, taskbed_ledger
from dharma_swarm.forge_v1.run_real import compute_unified_diff


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return proc.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=Forge Grader", "-c", "user.email=forge@example.test", "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_with_validated_pr(tmp_path: Path) -> tuple[Path, dict]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write(repo / "pkg.py", "def answer():\n    return 1\n")
    base_sha = _commit(repo, "base bug")

    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo / "pkg.py", "def answer():\n    return 2\n")
    _write(repo / "tests" / "test_pkg.py", "from pkg import answer\n\n\ndef test_answer():\n    assert answer() == 2\n")
    head_sha = _commit(repo, "fix answer")
    _git(repo, "checkout", "-q", "main")
    _git(
        repo,
        "-c",
        "user.name=Forge Grader",
        "-c",
        "user.email=forge@example.test",
        "merge",
        "--no-ff",
        "feature",
        "-m",
        "merge feature",
    )
    merge_sha = _git(repo, "rev-parse", "HEAD")

    receipt = tmp_path / "validation.json"
    receipt.write_text(
        json.dumps(
            {
                "test_command_template": "env PYTHONPATH={checkout} {python} -m pytest -q {targets}",
                "status": "fail_to_pass_validated",
            }
        ),
        encoding="utf-8",
    )
    row = {
        "repo": "fake/pkg",
        "repo_path": str(repo),
        "pr_number": 1,
        "created_at": "2026-07-01T00:00:00Z",
        "merged_at": "2026-07-02T00:00:00Z",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_commit_sha": merge_sha,
        "validated_base_sha": base_sha,
        "validated_fixed_sha": merge_sha,
        "title": "Fix answer",
        "source_kind": "post_cutoff_pr_suite_candidate",
        "test_files": ["tests/test_pkg.py"],
        "fail_to_pass": ["tests/test_pkg.py"],
        "validation_state": "fail_to_pass_validated",
        "requires_fail_to_pass_validation": False,
        "validation_receipt": str(receipt),
    }
    return repo, row


def _register(row: dict, db: Path) -> str:
    summary = fresh_task_oracle.import_fresh_tasks(
        [row],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=db,
    )
    assert summary["imported_count"] == 1
    return summary["imported_task_ids"][0]


def _fix_patch() -> str:
    return compute_unified_diff(
        {"pkg.py": "def answer():\n    return 1\n"},
        {"pkg.py": "def answer():\n    return 2\n"},
    )


def test_taskbed_task_for_id_returns_registered_task(tmp_path: Path) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    db = tmp_path / "taskbed.db"
    task_id = _register(row, db)

    stored = taskbed_ledger.task_for_id(task_id, db_path=db)

    assert stored["task_id"] == "pr::fake/pkg#1"
    assert stored["task"]["fail_to_pass"] == ["tests/test_pkg.py"]
    assert stored["contamination_state"] == "fresh_post_cutoff"


def test_load_pr_suite_context_reads_changed_source_not_tests(tmp_path: Path) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    db = tmp_path / "taskbed.db"
    task_id = _register(row, db)

    inst, ctx = pr_suite_grader.load_pr_suite_context(task_id, db_path=db)

    assert inst["instance_id"] == "pr::fake/pkg#1"
    assert inst["FAIL_TO_PASS"] == ["tests/test_pkg.py"]
    assert inst["contamination_state"] == "fresh_post_cutoff"
    assert ctx == {"pkg.py": "def answer():\n    return 1\n"}


def test_grade_pr_suite_prediction_resolves_valid_patch(tmp_path: Path) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
    )

    assert result.resolved is True
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["resolved"] is True
    assert receipt["blockers"] == []


def test_grade_pr_suite_prediction_runs_setup_before_test(tmp_path: Path) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    sentinel = tmp_path / "grade_setup_hits.log"
    setup_template = f"{sys.executable} -c " + repr(
        f"open({str(sentinel)!r}, 'a').write('hit\\n')"
    )

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        setup_command_template=setup_template,
    )

    assert result.resolved is True
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    phases = [c.get("phase") for c in receipt["commands"]]
    assert "setup_after_patch" in phases
    assert phases.index("setup_after_patch") < phases.index("test_after_patch")
    assert receipt["setup_command_template"] == setup_template
    assert sentinel.read_text(encoding="utf-8").count("hit") == 1


def test_grade_pr_suite_prediction_setup_failure_fails_closed(tmp_path: Path) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    setup_template = f"{sys.executable} -c " + repr("import sys; sys.exit(7)")

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        setup_command_template=setup_template,
    )

    assert result.resolved is False
    assert result.error == "patch_environment_setup_failed"
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    phases = [c.get("phase") for c in receipt["commands"]]
    assert "setup_after_patch" in phases
    assert "test_after_patch" not in phases
    assert "patch_environment_setup_failed" in receipt["blockers"]


def test_grade_pr_suite_prediction_blocks_test_patch(tmp_path: Path) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    test_patch = compute_unified_diff(
        {"tests/test_pkg.py": "from pkg import answer\n\n\ndef test_answer():\n    assert answer() == 2\n"},
        {"tests/test_pkg.py": "from pkg import answer\n\n\ndef test_answer():\n    assert True\n"},
    )

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        test_patch,
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
    )

    assert result.resolved is False
    assert result.error == "patch_touches_test_file"
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert "patch_touches_test_file" in receipt["blockers"]


def test_patch_touches_tests_blocks_root_conftest_creation() -> None:
    patch = """diff --git a/conftest.py b/conftest.py
new file mode 100644
--- /dev/null
+++ b/conftest.py
@@ -0,0 +1 @@
+pytest_plugins = []
"""
    assert pr_suite_grader._patch_touches_tests(patch, ["tests/test_pkg.py"]) is True


def test_patch_touches_tests_blocks_pure_test_deletion() -> None:
    patch = """diff --git a/tests/test_pkg.py b/tests/test_pkg.py
deleted file mode 100644
--- a/tests/test_pkg.py
+++ /dev/null
@@ -1 +0,0 @@
-def test_pkg(): pass
"""
    assert pr_suite_grader._patch_touches_tests(patch, ["tests/test_pkg.py"]) is True
