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
        "contamination_state": "fresh_heldout",
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
    assert imported["derived_state_counts"] == {"fresh_heldout": 1}


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
