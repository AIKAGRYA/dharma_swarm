"""Fresh PR-suite grader for Forge taskbed rows.

The public API and monkeypatch seams stay here; Git/receipt support lives in
focused sibling modules.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

from . import pr_suite_execution as execution
from .pr_suite_execution import (
    CommandExecutor,
    CommandResult as CommandResult,
    ExecutionProfile,
)
from .pr_suite_grader_support import (
    DEFAULT_TEST_COMMAND_TEMPLATE,
    _changed_files as _changed_files,
    _checkout_ref,
    _clone_repo,
    _command_for_targets as _command_for_targets,
    _command_template as _command_template,
    _git,
    _is_test_path,
    _list_field as _list_field,
    _materialize_fixed_tests,
    _model_changed_files,
    _repo_url_for_row,
    _resolve_refs,
    _rev_parse as _rev_parse,
    _run,
    _setup_command as _setup_command,
    _target_path,
    _write_json,
    fail_to_pass_targets,
)
from .pr_suite_grader_validation import (
    _load_validation_receipt as _load_validation_receipt,
    _require_validation_profile_binding,
)
from .signals import canonical_sha256


SCHEMA_VERSION = "forge_v2.pr_suite_grader.v1"
DEFAULT_RECEIPT_ROOT = (
    dharma_state_dir() / "forge_v1" / "task_harvests" / "pr_suite_grade_receipts"
)


@dataclass(frozen=True)
class GradeResult:
    resolved: bool
    seconds: float
    error: str | None
    receipt_path: str
    receipt_sha256: str


def now_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def is_pr_suite_task_id(task_id: str) -> bool:
    return str(task_id or "").startswith("pr::")


def is_pr_suite_task(instance: dict[str, Any]) -> bool:
    source_kind = str(instance.get("source_kind") or "").lower()
    task_id = str(instance.get("instance_id") or instance.get("task_id") or "")
    return is_pr_suite_task_id(task_id) or "post_cutoff_pr_suite" in source_kind


def _patch_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in (patch or "").splitlines():
        if line.startswith("+++ b/"):
            path = line[len("+++ b/") :].strip()
        elif line.startswith("--- a/"):
            path = line[len("--- a/") :].strip()
        else:
            continue
        if path and path != "/dev/null" and path not in paths:
            paths.append(path)
    return paths


def _patch_touches_tests(patch: str, targets: list[str]) -> bool:
    target_paths = {_target_path(target) for target in targets}
    for path in _patch_paths(patch):
        if path in target_paths or _is_test_path(path):
            return True
    return False


from .pr_suite_context import load_pr_suite_context, task_row_for_id  # noqa: E402


def grade_pr_suite_prediction(
    instance: dict[str, Any],
    model_patch: str,
    *,
    timeout: int = 1800,
    receipt_root: Path | str = DEFAULT_RECEIPT_ROOT,
    work_root: Path | None = None,
    python: str = sys.executable,
    keep_workdir: bool = False,
    setup_command_template: str = "",
    setup_timeout_seconds: int | None = None,
    execution_profile: ExecutionProfile | Path | str | None = None,
    validation_trusted_public_keys: dict[str, bytes | str] | None = None,
) -> GradeResult:
    """Grade a model patch on a validated PR-suite task."""
    task_id = str(instance.get("task_id") or instance.get("instance_id") or "")
    row = dict(instance)
    run_id = (
        f"pr_suite_grade_{now_stamp()}_{time.time_ns()}_"
        f"{canonical_sha256({'task_id': task_id, 'patch': model_patch})[:12]}"
    )
    receipt_path = Path(receipt_root).expanduser() / f"{run_id}.json"
    root = (
        Path(work_root).expanduser() / run_id
        if work_root
        else Path(tempfile.mkdtemp(prefix="forge-pr-suite-grade-"))
    )
    checkout = root / "repo"
    started = time.time()
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    resolved = False
    grade_error: str | None = None
    refs: dict[str, str] = {}
    targets = fail_to_pass_targets(row)
    model_changed_paths: list[str] = []
    repo_url = ""
    executor: CommandExecutor | None = None

    try:
        if not is_pr_suite_task(row):
            raise ValueError("grade_pr_suite_prediction received a non PR-suite task")
        if not targets:
            blockers.append("missing_fail_to_pass")
            grade_error = "missing_fail_to_pass"
            raise RuntimeError("PR-suite task has no fail_to_pass targets")
        if not str(model_patch or "").strip():
            blockers.append("empty_patch")
            grade_error = "empty_patch"
            raise RuntimeError("empty patch")
        if _patch_touches_tests(model_patch, targets):
            blockers.append("patch_touches_test_file")
            grade_error = "patch_touches_test_file"
            raise RuntimeError("patch touches test files")
        for target in targets:
            execution.validated_target_path(target, checkout)
        if row.get("grade_command_template"):
            raise execution.ProfileTampered("task row cannot select a grade command")
        repo_url = _repo_url_for_row(row)
        source_roots = [Path(repo_url)] if Path(repo_url).expanduser().exists() else []
        executor = execution.build_executor(
            profile=execution_profile,
            workspace_root=root,
            source_roots=source_roots,
            total_timeout_seconds=timeout,
        )
        execution.require_command_contract(
            executor.profile,
            test_command_template=DEFAULT_TEST_COMMAND_TEMPLATE,
            setup_command_template=setup_command_template,
            python=python,
        )
        _require_validation_profile_binding(
            row,
            profile=executor.profile,
            targets=targets,
            trusted_public_keys=validation_trusted_public_keys,
        )
        clone = _clone_repo(
            repo_url,
            checkout,
            timeout_seconds=min(timeout, 600),
            executor=executor,
        )
        commands.append({"phase": "clone", **clone.to_receipt()})
        if not clone.passed:
            blockers.append("clone_failed")
            grade_error = "clone_failed"
            raise RuntimeError("git clone failed")
        refs = _resolve_refs(
            checkout,
            row,
            timeout_seconds=min(timeout, 180),
            executor=executor,
        )
        checkout_commands = _checkout_ref(
            checkout,
            refs["base_sha"],
            timeout_seconds=min(timeout, 180),
            executor=executor,
        )
        commands.extend(
            {"phase": "checkout_base", **command.to_receipt()}
            for command in checkout_commands
        )
        if not all(command.passed for command in checkout_commands):
            blockers.append("base_checkout_failed")
            grade_error = "base_checkout_failed"
            raise RuntimeError("base checkout failed")
        apply_result = _git(
            checkout,
            "apply",
            "--whitespace=nowarn",
            "-",
            timeout_seconds=min(timeout, 180),
            stdin=model_patch,
            executor=executor,
        )
        commands.append({"phase": "apply_model_patch", **apply_result.to_receipt()})
        if not apply_result.passed:
            blockers.append("patch_apply_failed")
            grade_error = "patch_apply_failed"
            raise RuntimeError("patch apply failed")
        try:
            model_changed_paths, path_commands = _model_changed_files(
                checkout,
                timeout_seconds=min(timeout, 180),
                executor=executor,
            )
        except RuntimeError:
            blockers.append("patch_path_scan_failed")
            grade_error = "patch_path_scan_failed"
            raise
        commands.extend(
            {"phase": "inspect_model_patch_paths", **path_result.to_receipt()}
            for path_result in path_commands
        )
        target_paths = {_target_path(target) for target in targets}
        if any(
            path in target_paths or _is_test_path(path)
            for path in model_changed_paths
        ):
            blockers.append("patch_touches_test_file")
            grade_error = "patch_touches_test_file"
            raise RuntimeError("applied patch changes test files")
        materialize = _materialize_fixed_tests(
            checkout,
            fixed_ref=refs["fixed_sha"],
            targets=targets,
            timeout_seconds=min(timeout, 180),
            executor=executor,
        )
        commands.extend(
            {"phase": "materialize_fixed_test", **command.to_receipt()}
            for command in materialize
        )
        if not materialize or not all(command.passed for command in materialize):
            blockers.append("fixed_test_materialization_failed")
            grade_error = "fixed_test_materialization_failed"
            raise RuntimeError("could not materialize fixed FAIL_TO_PASS tests")
        setup_argv = executor.setup_argv(cwd=checkout)
        if setup_argv is not None:
            setup_timeout = (
                int(setup_timeout_seconds)
                if setup_timeout_seconds is not None
                else max(min(timeout, 900), 600)
            )
            setup = _run(
                setup_argv,
                cwd=checkout,
                timeout_seconds=setup_timeout,
                executor=executor,
            )
            commands.append({"phase": "setup_after_patch", **setup.to_receipt()})
            if not setup.passed:
                blockers.append("patch_environment_setup_failed")
                grade_error = "patch_environment_setup_failed"
                raise RuntimeError("patch environment setup failed")
        command = executor.test_argv(cwd=checkout, targets=targets)
        test_result = _run(
            command,
            cwd=checkout,
            timeout_seconds=timeout,
            executor=executor,
        )
        commands.append({"phase": "test_after_patch", **test_result.to_receipt()})
        resolved = test_result.passed
        if not resolved:
            blockers.append("fail_to_pass_not_resolved")
            grade_error = f"test_returncode={test_result.returncode}"
    except Exception as exc:  # noqa: BLE001 - receipt-first grader.
        if isinstance(exc, execution.IsolationUnavailable):
            blockers.append("isolation_unavailable")
        elif isinstance(exc, execution.ProfileTampered):
            blockers.append("execution_profile_tampered")
        elif isinstance(exc, execution.UnsafeTargetPath):
            blockers.append("unsafe_test_target")
        if grade_error is None:
            grade_error = f"{type(exc).__name__}: {exc}"

    receipt = {
        "schema": SCHEMA_VERSION,
        "run_id": run_id,
        "task_id": task_id,
        "repo": row.get("repo") or row.get("repository") or "",
        "repo_url": execution.redact_secret_text(repo_url),
        "started_at": now_stamp(),
        "finished_at": now_stamp(),
        "resolved": resolved,
        "grade_error": grade_error,
        "blockers": blockers,
        "fail_to_pass": targets,
        "patch_len": len(model_patch or ""),
        "patch_sha256": canonical_sha256({"patch": model_patch or ""}),
        "model_changed_paths": model_changed_paths,
        "setup_command_template": str(setup_command_template or ""),
        "execution_profile": executor.profile.to_mapping() if executor is not None else {},
        "execution_profile_sha256": executor.profile.sha256 if executor is not None else "",
        "resolved_refs": refs,
        "validation_receipt": row.get("validation_receipt", ""),
        "checkout_path": str(checkout) if keep_workdir else "",
        "kept_workdir": keep_workdir,
        "commands": commands,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _write_json(receipt_path, receipt)
    if not keep_workdir:
        shutil.rmtree(root, ignore_errors=True)
    return GradeResult(
        resolved=resolved,
        seconds=round(time.time() - started, 1),
        error=grade_error,
        receipt_path=str(receipt_path),
        receipt_sha256=receipt["receipt_sha256"],
    )


__all__ = [
    "DEFAULT_RECEIPT_ROOT",
    "GradeResult",
    "SCHEMA_VERSION",
    "fail_to_pass_targets",
    "grade_pr_suite_prediction",
    "is_pr_suite_task",
    "is_pr_suite_task_id",
    "load_pr_suite_context",
    "task_row_for_id",
]
