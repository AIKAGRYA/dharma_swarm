from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import fresh_task_oracle, pr_suite_validator


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
    _git(repo, "-c", "user.name=Forge Validator", "-c", "user.email=forge@example.test", "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _init_repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    return repo


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _merge_fixing_pr_repo(tmp_path: Path) -> dict[str, str]:
    repo = _init_repo(tmp_path, "merge-fix")
    _write(repo / "calculator.py", "def answer():\n    return 1\n")
    base_sha = _commit(repo, "base bug")

    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo / "calculator.py", "def answer():\n    return 2\n")
    _write(
        repo / "tests" / "test_calculator.py",
        "from calculator import answer\n\n\ndef test_answer_regression():\n    assert answer() == 2\n",
    )
    head_sha = _commit(repo, "fix answer and add regression test")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "-c", "user.name=Forge Validator", "-c", "user.email=forge@example.test", "merge", "--no-ff", "feature", "-m", "merge feature")
    merge_sha = _git(repo, "rev-parse", "HEAD")
    return {"repo": str(repo), "base_sha": base_sha, "head_sha": head_sha, "merge_sha": merge_sha}


def _non_regression_repo(tmp_path: Path) -> dict[str, str]:
    repo = _init_repo(tmp_path, "already-fixed")
    _write(repo / "calculator.py", "def answer():\n    return 2\n")
    base_sha = _commit(repo, "base already fixed")

    _git(repo, "checkout", "-q", "-b", "feature")
    _write(
        repo / "tests" / "test_calculator.py",
        "from calculator import answer\n\n\ndef test_answer_regression():\n    assert answer() == 2\n",
    )
    head_sha = _commit(repo, "add passing test only")
    return {"repo": str(repo), "base_sha": base_sha, "head_sha": head_sha}


def test_validator_proves_new_pr_test_fails_on_merge_parent_and_passes_on_merge(tmp_path: Path) -> None:
    refs = _merge_fixing_pr_repo(tmp_path)
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 7,
        "created_at": "2026-07-01T00:00:00Z",
        "merged_at": "2026-07-02T00:00:00Z",
        # Deliberately stale/drifted.  The validator should prefer merge^1.
        "base_sha": refs["merge_sha"],
        "head_sha": refs["head_sha"],
        "merge_commit_sha": refs["merge_sha"],
        "test_files": ["tests/test_calculator.py"],
        "fail_to_pass": [],
        "validation_state": "needs_fail_to_pass_validation",
        "contamination_state": "fresh_post_cutoff",
    }

    summary = pr_suite_validator.validate_rows(
        [row],
        work_root=tmp_path / "work",
        receipt_root=tmp_path / "receipts",
        python=sys.executable,
        timeout_seconds=30,
    )

    assert summary["validated_count"] == 1
    assert summary["failed_count"] == 0
    assert len(summary["output_rows"]) == 1
    out = summary["output_rows"][0]
    assert out["fail_to_pass"] == ["tests/test_calculator.py"]
    assert out["validation_state"] == "fail_to_pass_validated"
    assert out["requires_fail_to_pass_validation"] is False
    assert out["validated_base_sha"] != row["base_sha"]

    receipt = json.loads(Path(out["validation_receipt"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "fail_to_pass_validated"
    assert receipt["contamination_state_trusted"] is False
    assert receipt["validated_fail_to_pass"] == ["tests/test_calculator.py"]
    assert [target["validated_fail_to_pass"] for target in receipt["target_results"]] == [True]
    assert "materialize_fixed_test_on_base" in {command["phase"] for command in receipt["commands"]}

    imported = fresh_task_oracle.import_fresh_tasks(
        summary["output_rows"],
        model_cutoff="2026-06-01T00:00:00Z",
        db_path=tmp_path / "taskbed.db",
    )
    assert imported["imported_count"] == 1
    assert imported["derived_state_counts"] == {"fresh_post_cutoff": 1}


def test_validator_rejects_test_that_does_not_fail_on_base(tmp_path: Path) -> None:
    refs = _non_regression_repo(tmp_path)
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 8,
        "created_at": "2026-07-01T00:00:00Z",
        "base_sha": refs["base_sha"],
        "head_sha": refs["head_sha"],
        "test_files": ["tests/test_calculator.py"],
        "fail_to_pass": [],
    }

    summary = pr_suite_validator.validate_rows(
        [row],
        work_root=tmp_path / "work",
        receipt_root=tmp_path / "receipts",
        python=sys.executable,
        timeout_seconds=30,
    )

    assert summary["validated_count"] == 0
    assert summary["failed_count"] == 1
    assert summary["output_rows"] == []
    result = summary["results"][0]
    assert "no_targets_failed_on_base_and_passed_on_fixed" in result["blockers"]

    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    assert receipt["target_results"] == [
        {
            "target": "tests/test_calculator.py",
            "base_returncode": 0,
            "fixed_returncode": 0,
            "base_outcome": "passed_on_base",
            "base_failed": False,
            "fixed_passed": True,
            "validated_fail_to_pass": False,
        }
    ]


def test_validator_can_write_jsonl_for_oracle(tmp_path: Path) -> None:
    refs = _merge_fixing_pr_repo(tmp_path)
    manifest = tmp_path / "candidates.jsonl"
    output = tmp_path / "validated.jsonl"
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 9,
        "created_at": "2026-07-01T00:00:00Z",
        "merged_at": "2026-07-02T00:00:00Z",
        "base_sha": refs["base_sha"],
        "head_sha": refs["head_sha"],
        "merge_commit_sha": refs["merge_sha"],
        "test_files": ["tests/test_calculator.py"],
        "fail_to_pass": [],
    }
    manifest.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

    rc = pr_suite_validator.main(
        [
            "--manifest",
            str(manifest),
            "--out",
            str(output),
            "--receipt-root",
            str(tmp_path / "receipts"),
            "--work-root",
            str(tmp_path / "work"),
            "--python",
            sys.executable,
            "--timeout-seconds",
            "30",
            "--json",
        ]
    )

    assert rc == 0
    rows = fresh_task_oracle.read_manifest(output)
    assert len(rows) == 1
    assert rows[0]["fail_to_pass"] == ["tests/test_calculator.py"]
    assert rows[0]["validation_state"] == "fail_to_pass_validated"


def _import_error_regression_repo(tmp_path: Path) -> dict[str, str]:
    """A real FAIL_TO_PASS shape: the new test imports an API missing on base.

    On the base commit the test collection raises ImportError -> pytest exit 2.
    On the fixed commit the symbol exists and the test passes -> exit 0.
    """

    repo = _init_repo(tmp_path, "import-error-fix")
    _write(repo / "calculator.py", "def answer():\n    return 1\n")
    base_sha = _commit(repo, "base without new api")

    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo / "calculator.py", "def answer():\n    return 1\n\n\ndef doubled():\n    return 2\n")
    _write(
        repo / "tests" / "test_doubled.py",
        "from calculator import doubled\n\n\ndef test_doubled():\n    assert doubled() == 2\n",
    )
    head_sha = _commit(repo, "add doubled() and its regression test")
    _git(repo, "checkout", "-q", "main")
    return {"repo": str(repo), "base_sha": base_sha, "head_sha": head_sha}


def _empty_test_file_repo(tmp_path: Path) -> dict[str, str]:
    """A false-positive trap: the PR adds a test *file* that collects NO tests.

    On base the file is absent; we materialize the fixed file, but it has no test
    functions, so pytest exits 5 (no tests collected) on BOTH base and fixed.
    That must never be minted as a FAIL_TO_PASS regression.
    """

    repo = _init_repo(tmp_path, "empty-test-file")
    _write(repo / "calculator.py", "def answer():\n    return 1\n")
    base_sha = _commit(repo, "base")

    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo / "calculator.py", "def answer():\n    return 2\n")
    _write(repo / "tests" / "test_empty.py", "# a docs/refactor PR that touches a test file but adds no test\nX = 1\n")
    head_sha = _commit(repo, "touch a test file with no collectable tests")
    _git(repo, "checkout", "-q", "main")
    return {"repo": str(repo), "base_sha": base_sha, "head_sha": head_sha}


def test_classify_base_outcome_covers_pytest_exit_codes() -> None:
    def _cr(returncode: int, *, timed_out: bool = False) -> pr_suite_validator.CommandResult:
        return pr_suite_validator.CommandResult(
            argv=["pytest"], cwd=".", returncode=returncode, stdout="", stderr="", timed_out=timed_out
        )

    assert pr_suite_validator.classify_base_outcome(_cr(0)) == "passed_on_base"
    # Real failing test and real collection error are the only honest base fails.
    assert pr_suite_validator.classify_base_outcome(_cr(1)) == "failed_on_base"
    assert pr_suite_validator.classify_base_outcome(_cr(2)) == "failed_on_base"
    # "Never really ran" codes must not be read as regressions.
    assert pr_suite_validator.classify_base_outcome(_cr(3)) == "inconclusive_no_real_run_on_base"
    assert pr_suite_validator.classify_base_outcome(_cr(4)) == "inconclusive_no_real_run_on_base"
    assert pr_suite_validator.classify_base_outcome(_cr(5)) == "inconclusive_no_real_run_on_base"
    assert pr_suite_validator.classify_base_outcome(_cr(124, timed_out=True)) == "inconclusive_timeout_on_base"


def test_validator_keeps_import_error_regression_as_fail_to_pass(tmp_path: Path) -> None:
    refs = _import_error_regression_repo(tmp_path)
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 11,
        "created_at": "2026-07-01T00:00:00Z",
        "base_sha": refs["base_sha"],
        "head_sha": refs["head_sha"],
        "test_files": ["tests/test_doubled.py"],
        "fail_to_pass": [],
    }

    summary = pr_suite_validator.validate_rows(
        [row],
        work_root=tmp_path / "work",
        receipt_root=tmp_path / "receipts",
        python=sys.executable,
        timeout_seconds=30,
    )

    assert summary["validated_count"] == 1
    out = summary["output_rows"][0]
    assert out["fail_to_pass"] == ["tests/test_doubled.py"]
    receipt = json.loads(Path(out["validation_receipt"]).read_text(encoding="utf-8"))
    target = receipt["target_results"][0]
    assert target["base_outcome"] == "failed_on_base"
    assert target["base_returncode"] == 2  # ImportError -> pytest collection error
    assert target["validated_fail_to_pass"] is True


def test_validator_rejects_no_tests_collected_as_false_positive(tmp_path: Path) -> None:
    refs = _empty_test_file_repo(tmp_path)
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 12,
        "created_at": "2026-07-01T00:00:00Z",
        "base_sha": refs["base_sha"],
        "head_sha": refs["head_sha"],
        "test_files": ["tests/test_empty.py"],
        "fail_to_pass": [],
    }

    summary = pr_suite_validator.validate_rows(
        [row],
        work_root=tmp_path / "work",
        receipt_root=tmp_path / "receipts",
        python=sys.executable,
        timeout_seconds=30,
    )

    assert summary["validated_count"] == 0
    assert summary["output_rows"] == []
    result = summary["results"][0]
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    target = receipt["target_results"][0]
    # No tests collected on base (exit 5) must be inconclusive, NOT a regression.
    assert target["base_returncode"] == 5
    assert target["base_outcome"] == "inconclusive_no_real_run_on_base"
    assert target["validated_fail_to_pass"] is False
    assert any(b.startswith("base_test_inconclusive:") for b in result["blockers"])


def test_setup_command_runs_before_base_and_fixed_and_is_recorded(tmp_path: Path) -> None:
    refs = _merge_fixing_pr_repo(tmp_path)
    sentinel = tmp_path / "setup_hits.log"
    # A portable setup command: append a line to a sentinel file. Proves the
    # setup phase executes once per checkout (base + fixed) before the tests.
    setup_template = f"{sys.executable} -c " + repr(
        f"open({str(sentinel)!r}, 'a').write('hit\\n')"
    )
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 11,
        "base_sha": refs["base_sha"],
        "head_sha": refs["head_sha"],
        "merge_commit_sha": refs["merge_sha"],
        "test_files": ["tests/test_calculator.py"],
        "fail_to_pass": [],
    }

    summary = pr_suite_validator.validate_rows(
        [row],
        work_root=tmp_path / "work",
        receipt_root=tmp_path / "receipts",
        python=sys.executable,
        timeout_seconds=30,
        setup_command_template=setup_template,
    )

    result = summary["results"][0]
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    phases = [c.get("phase") for c in receipt["commands"]]
    assert "setup_base" in phases
    assert "setup_fixed" in phases
    # setup_base must precede test_base; setup_fixed must precede test_fixed.
    assert phases.index("setup_base") < phases.index("test_base")
    assert phases.index("setup_fixed") < phases.index("test_fixed")
    assert receipt["setup_command_template"] == setup_template
    assert sentinel.read_text(encoding="utf-8").count("hit") == 2


def test_setup_failure_fails_closed_without_minting_task(tmp_path: Path) -> None:
    refs = _merge_fixing_pr_repo(tmp_path)
    # A setup command that always fails must block validation, never validate.
    setup_template = f"{sys.executable} -c " + repr("import sys; sys.exit(7)")
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 12,
        "base_sha": refs["base_sha"],
        "head_sha": refs["head_sha"],
        "merge_commit_sha": refs["merge_sha"],
        "test_files": ["tests/test_calculator.py"],
        "fail_to_pass": [],
    }

    summary = pr_suite_validator.validate_rows(
        [row],
        work_root=tmp_path / "work",
        receipt_root=tmp_path / "receipts",
        python=sys.executable,
        timeout_seconds=30,
        setup_command_template=setup_template,
    )

    result = summary["results"][0]
    assert summary["validated_count"] == 0
    assert result["validated"] is False
    assert any(b.startswith("base_setup_failed:") for b in result["blockers"])
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    phases = [c.get("phase") for c in receipt["commands"]]
    # Setup failed on base, so the base test must never have run.
    assert "setup_base" in phases
    assert "test_base" not in phases


def test_empty_setup_template_preserves_bare_clone_behaviour(tmp_path: Path) -> None:
    refs = _merge_fixing_pr_repo(tmp_path)
    row = {
        "repo": "fake/calculator",
        "repo_path": refs["repo"],
        "pr_number": 13,
        "base_sha": refs["base_sha"],
        "head_sha": refs["head_sha"],
        "merge_commit_sha": refs["merge_sha"],
        "test_files": ["tests/test_calculator.py"],
        "fail_to_pass": [],
    }

    summary = pr_suite_validator.validate_rows(
        [row],
        work_root=tmp_path / "work",
        receipt_root=tmp_path / "receipts",
        python=sys.executable,
        timeout_seconds=30,
    )

    result = summary["results"][0]
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    phases = [c.get("phase") for c in receipt["commands"]]
    assert "setup_base" not in phases
    assert "setup_fixed" not in phases
    assert receipt["setup_command_template"] == ""
