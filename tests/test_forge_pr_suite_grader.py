from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.forge_v1.forge_v2 import (
    fresh_task_oracle,
    pr_suite_execution,
    pr_suite_grader,
    pr_suite_validator_runtime,
    taskbed_ledger,
)
from dharma_swarm.forge_v1.run_real import compute_unified_diff


_VALIDATOR_KEY = Ed25519PrivateKey.generate()
_VALIDATOR_KEY_ID = "pytest-validator"
_VALIDATOR_PUBLIC = _VALIDATOR_KEY.public_key().public_bytes(
    serialization.Encoding.Raw,
    serialization.PublicFormat.Raw,
)


def _test_profile(setup_template: str = "") -> pr_suite_execution.ExecutionProfile:
    return pr_suite_execution.ExecutionProfile(
        profile_id="pytest-local-explicit",
        backend="docker",
        runtime="/bin/false",
        image=f"example.invalid/forge-tests@sha256:{'0' * 64}",
        user="65534:65534",
        python=sys.executable,
        setup_command=pr_suite_execution.normalized_template_tokens(
            setup_template, python=sys.executable
        ),
    )


class _ExplicitTestExecutor:
    """Test-only dependency injection; production has no local fallback."""

    def __init__(self, workspace_root: Path, total_timeout_seconds: int, setup_template: str = "") -> None:
        self.workspace_root = workspace_root
        self.profile = _test_profile(setup_template)
        self._deadline = time.monotonic() + total_timeout_seconds

    def _render(self, tokens: Sequence[str], cwd: Path, targets: Sequence[str]) -> list[str]:
        rendered: list[str] = []
        for token in tokens:
            if token == "{targets}":
                rendered.extend(targets)
            else:
                rendered.append(
                    token.format(
                        python=sys.executable,
                        checkout=str(cwd),
                        target=targets[0] if targets else "",
                        targets=" ".join(targets),
                    )
                )
        return rendered

    def test_argv(self, *, cwd: Path, targets: Sequence[str]) -> list[str]:
        return self._render(self.profile.test_command, cwd, targets)

    def setup_argv(self, *, cwd: Path) -> list[str] | None:
        return self._render(self.profile.setup_command, cwd, ()) if self.profile.setup_command else None

    def run(
        self,
        argv: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        stdin: str | None = None,
    ) -> pr_suite_execution.CommandResult:
        remaining = max(0.01, self._deadline - time.monotonic())
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                input=stdin,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=min(timeout_seconds, remaining),
                check=False,
                env={
                    "PATH": os.defpath,
                    "HOME": str(cwd),
                    "PYTHONPATH": os.pathsep.join(
                        part for part in (str(cwd), os.environ.get("PYTHONPATH", "")) if part
                    ),
                },
                start_new_session=True,
            )
            return pr_suite_execution.CommandResult(
                list(argv), str(cwd), proc.returncode, proc.stdout, proc.stderr,
                profile_sha256=self.profile.sha256,
            )
        except subprocess.TimeoutExpired as exc:
            return pr_suite_execution.CommandResult(
                list(argv), str(cwd), 124, str(exc.stdout or ""), str(exc.stderr or ""), True,
                profile_sha256=self.profile.sha256,
            )


def _executor_factory(setup_template: str = ""):
    def factory(*, workspace_root: Path, total_timeout_seconds: int, **_kwargs: object) -> _ExplicitTestExecutor:
        return _ExplicitTestExecutor(workspace_root, total_timeout_seconds, setup_template)

    return factory


def _install_executor(monkeypatch, setup_template: str = "") -> None:
    monkeypatch.setattr(pr_suite_execution, "build_executor", _executor_factory(setup_template))
    monkeypatch.setattr(
        pr_suite_execution,
        "load_validator_trust_root",
        lambda _path=None: {_VALIDATOR_KEY_ID: _VALIDATOR_PUBLIC},
    )


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


def _repo_with_validated_pr(tmp_path: Path, *, setup_template: str = "") -> tuple[Path, dict]:
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

    row = {
        "repo": "fake/pkg",
        "repo_path": str(repo),
        "pr_number": 1,
        "created_at": "2026-07-01T00:00:00Z",
        "merged_at": "2026-07-02T00:00:00Z",
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_commit_sha": merge_sha,
        "title": "Fix answer",
        "source_kind": "post_cutoff_pr_suite_candidate",
        "test_files": ["tests/test_pkg.py"],
        "fail_to_pass": ["tests/test_pkg.py"],
    }
    profile = _test_profile(setup_template)
    row_sha = pr_suite_grader.canonical_sha256(row)
    refs = {"base_sha": base_sha, "fixed_sha": merge_sha}
    receipt_payload = {
        "schema": pr_suite_validator_runtime.SCHEMA_VERSION,
        "run_id": "pytest-validation-0001",
        "status": "fail_to_pass_validated",
        "task_hint": "1",
        "row_sha256": row_sha,
        "source_binding": {
            "source_row_sha256": row_sha,
            "task_hint": "1",
            "repo": "fake/pkg",
            "repository_locators": {"repo_path": str(repo)},
            "pr_number": 1,
            "candidate_targets": ["tests/test_pkg.py"],
            "resolved_refs": refs,
        },
        "repo": "fake/pkg",
        "validated_fail_to_pass": ["tests/test_pkg.py"],
        "resolved_refs": refs,
        "execution_profile": profile.to_mapping(),
        "execution_profile_sha256": profile.sha256,
    }
    receipt_payload = pr_suite_execution.sign_validator_receipt(
        receipt_payload,
        signing_key=_VALIDATOR_KEY,
        key_id=_VALIDATOR_KEY_ID,
        nonce="pytest-validation-0001",
    )
    receipt_payload["receipt_sha256"] = pr_suite_grader.canonical_sha256(receipt_payload)
    receipt = tmp_path / "validation.json"
    receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
    row.update({
        "validated_base_sha": base_sha,
        "validated_fixed_sha": merge_sha,
        "validation_state": "fail_to_pass_validated",
        "requires_fail_to_pass_validation": False,
        "validation_receipt": str(receipt),
        "validation_receipt_sha256": receipt_payload["receipt_sha256"],
        "validation_execution_profile_sha256": profile.sha256,
        "validation_source_row_sha256": row_sha,
        "validation_task_hint": "1",
    })
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


def test_load_pr_suite_context_reads_changed_source_not_tests(tmp_path: Path, monkeypatch) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    db = tmp_path / "taskbed.db"
    task_id = _register(row, db)

    monkeypatch.setattr(
        pr_suite_execution,
        "build_executor",
        lambda *, workspace_root, total_timeout_seconds, **_kwargs: _ExplicitTestExecutor(
            workspace_root, total_timeout_seconds
        ),
    )

    inst, ctx = pr_suite_grader.load_pr_suite_context(task_id, db_path=db)

    assert inst["instance_id"] == "pr::fake/pkg#1"
    assert inst["FAIL_TO_PASS"] == ["tests/test_pkg.py"]
    assert inst["contamination_state"] == "fresh_post_cutoff"
    assert ctx == {"pkg.py": "def answer():\n    return 1\n"}


def test_grade_pr_suite_prediction_resolves_valid_patch(tmp_path: Path, monkeypatch) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    _install_executor(monkeypatch)

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        execution_profile=_test_profile(),
    )

    assert result.resolved is True
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["resolved"] is True
    assert receipt["blockers"] == []
    assert len(receipt["execution_profile_sha256"]) == 64
    assert {
        command["execution_profile_sha256"] for command in receipt["commands"]
    } == {receipt["execution_profile_sha256"]}
    assert Path(result.receipt_path).stat().st_mode & 0o777 == 0o600


def test_grade_pr_suite_prediction_refuses_missing_isolation_profile(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv(pr_suite_execution.PROFILE_ENV, raising=False)
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
    )

    assert result.resolved is False
    assert result.error is not None and "IsolationUnavailable" in result.error
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["commands"] == []
    assert "isolation_unavailable" in receipt["blockers"]


def test_task_row_cannot_tamper_with_digest_bound_command_profile(tmp_path: Path) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {
        **row,
        "instance_id": "pr::fake/pkg#1",
        "task_id": "pr::fake/pkg#1",
        "grade_command_template": "/bin/sh -c 'exit 0'",
    }

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
    )

    assert result.resolved is False
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["commands"] == []
    assert "execution_profile_tampered" in receipt["blockers"]


def test_grade_rejects_validation_profile_binding_tamper(tmp_path: Path, monkeypatch) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {
        **row,
        "instance_id": "pr::fake/pkg#1",
        "task_id": "pr::fake/pkg#1",
        "validation_execution_profile_sha256": "f" * 64,
    }
    _install_executor(monkeypatch)

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        execution_profile=_test_profile(),
    )

    assert result.resolved is False
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert "execution_profile_tampered" in receipt["blockers"]
    assert not any(command.get("phase") == "clone" for command in receipt["commands"])


def test_grade_pr_suite_prediction_runs_setup_before_test(tmp_path: Path, monkeypatch) -> None:
    sentinel = tmp_path / "grade_setup_hits.log"
    setup_template = f"{sys.executable} -c " + repr(
        f"open({str(sentinel)!r}, 'a').write('hit\\n')"
    )
    _repo, row = _repo_with_validated_pr(tmp_path, setup_template=setup_template)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    _install_executor(monkeypatch, setup_template)

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        setup_command_template=setup_template,
        execution_profile=_test_profile(setup_template),
    )

    assert result.resolved is True
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    phases = [c.get("phase") for c in receipt["commands"]]
    assert "setup_after_patch" in phases
    assert phases.index("setup_after_patch") < phases.index("test_after_patch")
    assert receipt["setup_command_template"] == setup_template
    assert sentinel.read_text(encoding="utf-8").count("hit") == 1


def test_grade_pr_suite_prediction_setup_failure_fails_closed(tmp_path: Path, monkeypatch) -> None:
    setup_template = f"{sys.executable} -c " + repr("import sys; sys.exit(7)")
    _repo, row = _repo_with_validated_pr(tmp_path, setup_template=setup_template)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    _install_executor(monkeypatch, setup_template)

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        setup_command_template=setup_template,
        execution_profile=_test_profile(setup_template),
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


def test_post_apply_scan_blocks_when_textual_prefilter_is_bypassed(
    tmp_path: Path, monkeypatch
) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    patch = """diff --git a/conftest.py b/conftest.py
new file mode 100644
--- /dev/null
+++ b/conftest.py
@@ -0,0 +1 @@
+pytest_plugins = []
"""
    _install_executor(monkeypatch)
    monkeypatch.setattr(pr_suite_grader, "_patch_touches_tests", lambda *_args: False)

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        patch,
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        execution_profile=_test_profile(),
    )

    assert result.resolved is False
    assert result.error == "patch_touches_test_file"
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["model_changed_paths"] == ["conftest.py"]
    assert "inspect_model_patch_paths" in {
        command["phase"] for command in receipt["commands"]
    }


def test_forged_validator_receipt_is_rejected_even_with_recomputed_digest(
    tmp_path: Path, monkeypatch
) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    receipt_path = Path(row["validation_receipt"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    attacker = Ed25519PrivateKey.generate()
    forged_body = dict(receipt)
    forged_body.pop("receipt_sha256")
    forged_body = pr_suite_execution.sign_validator_receipt(
        forged_body,
        signing_key=attacker,
        key_id=_VALIDATOR_KEY_ID,
        nonce="attacker-validation-0001",
    )
    forged_body["receipt_sha256"] = pr_suite_grader.canonical_sha256(forged_body)
    receipt_path.write_text(json.dumps(forged_body), encoding="utf-8")
    row["validation_receipt_sha256"] = forged_body["receipt_sha256"]
    inst = {**row, "instance_id": "pr::fake/pkg#1", "task_id": "pr::fake/pkg#1"}
    _install_executor(monkeypatch)

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        execution_profile=_test_profile(),
    )

    assert result.resolved is False
    assert result.error is not None and "signer is not trusted" in result.error


def test_validator_receipt_cannot_replay_across_repository_or_task(
    tmp_path: Path, monkeypatch
) -> None:
    _repo, row = _repo_with_validated_pr(tmp_path)
    inst = {
        **row,
        "repo": "fake/other",
        "instance_id": "pr::fake/other#1",
        "task_id": "pr::fake/other#1",
    }
    _install_executor(monkeypatch)

    result = pr_suite_grader.grade_pr_suite_prediction(
        inst,
        _fix_patch(),
        timeout=60,
        receipt_root=tmp_path / "grade_receipts",
        python=sys.executable,
        execution_profile=_test_profile(),
    )

    assert result.resolved is False
    assert result.error is not None and "source/task binding" in result.error
