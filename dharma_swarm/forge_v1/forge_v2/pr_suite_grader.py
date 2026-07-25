"""Fresh PR-suite grader for Forge taskbed rows.

SWE-bench instance ids still route to the official SWE-bench harness.  This
module handles the separate post-cutoff PR-suite task format minted by
``pr_suite_validator``: clone repo, checkout validated base, materialize the
fixed revision's test artifact, apply the model patch, then run the validated
FAIL_TO_PASS target.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir

from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.pr_suite_grader.v1"
DEFAULT_RECEIPT_ROOT = dharma_state_dir() / "forge_v1" / "task_harvests" / "pr_suite_grade_receipts"
DEFAULT_TEST_COMMAND_TEMPLATE = "{python} -m pytest -q {targets}"


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_receipt(self, *, max_output_chars: int = 4000) -> dict[str, Any]:
        return {
            "argv": self.argv,
            "cwd": self.cwd,
            "returncode": self.returncode,
            "passed": self.passed,
            "timed_out": self.timed_out,
            "stdout_tail": self.stdout[-max_output_chars:],
            "stderr_tail": self.stderr[-max_output_chars:],
        }


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


def _run(argv: list[str], *, cwd: Path, timeout_seconds: int, stdin: str | None = None) -> CommandResult:
    try:
        proc = subprocess.run(  # noqa: S603 - argv is constructed without shell=True.
            argv,
            cwd=str(cwd),
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            argv=list(argv),
            cwd=str(cwd),
            returncode=int(proc.returncode),
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=list(argv),
            cwd=str(cwd),
            returncode=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            timed_out=True,
        )


def _git(checkout: Path, *args: str, timeout_seconds: int = 120, stdin: str | None = None) -> CommandResult:
    return _run(["git", *args], cwd=checkout, timeout_seconds=timeout_seconds, stdin=stdin)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _repo_url_for_row(row: dict[str, Any]) -> str:
    for key in ("repo_path", "clone_url", "repo_url", "local_repo"):
        value = str(row.get(key) or "").strip()
        if value:
            return str(Path(value).expanduser()) if key in {"repo_path", "local_repo"} else value
    repo = str(row.get("repo") or row.get("repository") or "").strip().strip("/")
    if not repo:
        raise ValueError("PR-suite task row must include repo, repo_path, clone_url, repo_url, or local_repo")
    expanded = Path(repo).expanduser()
    if expanded.exists():
        return str(expanded)
    return f"https://github.com/{repo}.git"


def _clone_repo(repo_url: str, checkout: Path, *, timeout_seconds: int) -> CommandResult:
    checkout.parent.mkdir(parents=True, exist_ok=True)
    return _run(
        ["git", "clone", "--quiet", "--no-hardlinks", repo_url, str(checkout)],
        cwd=checkout.parent,
        timeout_seconds=timeout_seconds,
    )


def _rev_parse(checkout: Path, ref: str, *, timeout_seconds: int) -> str:
    result = _git(checkout, "rev-parse", "--verify", ref, timeout_seconds=timeout_seconds)
    if not result.passed:
        raise RuntimeError(f"could not resolve git ref {ref!r}: {result.stderr or result.stdout}")
    return result.stdout.strip()


def _resolve_refs(checkout: Path, row: dict[str, Any], *, timeout_seconds: int) -> dict[str, str]:
    fixed_ref = str(
        row.get("validated_fixed_sha")
        or row.get("merge_commit_sha")
        or row.get("head_sha")
        or row.get("fixed_sha")
        or ""
    ).strip()
    base_ref = str(row.get("validated_base_sha") or row.get("validation_base_sha") or row.get("base_sha") or "").strip()
    if not fixed_ref:
        raise ValueError("PR-suite task row must include validated_fixed_sha, merge_commit_sha, or head_sha")
    if not base_ref:
        merge = str(row.get("merge_commit_sha") or "").strip()
        if merge:
            base_ref = f"{_rev_parse(checkout, merge, timeout_seconds=timeout_seconds)}^1"
    if not base_ref:
        raise ValueError("PR-suite task row must include validated_base_sha/base_sha or merge_commit_sha")
    return {
        "base_ref": base_ref,
        "fixed_ref": fixed_ref,
        "base_sha": _rev_parse(checkout, base_ref, timeout_seconds=timeout_seconds),
        "fixed_sha": _rev_parse(checkout, fixed_ref, timeout_seconds=timeout_seconds),
    }


def _checkout_ref(checkout: Path, ref: str, *, timeout_seconds: int) -> list[CommandResult]:
    return [
        _git(checkout, "reset", "--hard", timeout_seconds=timeout_seconds),
        _git(checkout, "clean", "-ffdx", timeout_seconds=timeout_seconds),
        _git(checkout, "checkout", "--force", ref, timeout_seconds=timeout_seconds),
    ]


def _target_path(target: str) -> str:
    return str(target).split("::", 1)[0].strip()


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (
        lowered.startswith("tests/")
        or "/tests/" in lowered
        or lowered.startswith("testing/")
        or "/testing/" in lowered
        or name == "conftest.py"
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
    )


def _list_field(row: dict[str, Any], *names: str) -> list[str]:
    for name in names:
        value = row.get(name)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def fail_to_pass_targets(row: dict[str, Any]) -> list[str]:
    return _list_field(row, "fail_to_pass", "FAIL_TO_PASS")


def _load_validation_receipt(row: dict[str, Any]) -> dict[str, Any]:
    path = str(row.get("validation_receipt") or "").strip()
    if not path:
        return {}
    receipt_path = Path(path).expanduser()
    if not receipt_path.exists():
        return {}
    try:
        return json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _command_template(row: dict[str, Any]) -> str:
    if row.get("grade_command_template"):
        return str(row["grade_command_template"])
    receipt = _load_validation_receipt(row)
    if receipt.get("test_command_template"):
        return str(receipt["test_command_template"])
    return os.environ.get("FORGE_PR_SUITE_TEST_COMMAND_TEMPLATE", DEFAULT_TEST_COMMAND_TEMPLATE)


def _command_for_targets(template: str, *, python: str, targets: list[str], checkout: Path) -> list[str]:
    if not targets:
        raise ValueError("no FAIL_TO_PASS targets supplied")
    quoted_targets = " ".join(shlex.quote(target) for target in targets)
    command = template.format(
        python=shlex.quote(python),
        target=shlex.quote(targets[0]),
        targets=quoted_targets,
        checkout=shlex.quote(str(checkout)),
    )
    argv = shlex.split(command)
    if not argv:
        raise ValueError("test command template rendered to an empty command")
    return argv


def _setup_command(template: str, *, python: str, checkout: Path) -> list[str] | None:
    text = str(template or "").strip()
    if not text:
        return None
    command = text.format(
        python=shlex.quote(python),
        checkout=shlex.quote(str(checkout)),
    )
    argv = shlex.split(command)
    if not argv:
        raise ValueError("setup command template rendered to an empty command")
    return argv


def _changed_files(checkout: Path, refs: dict[str, str], *, timeout_seconds: int) -> list[str]:
    result = _git(checkout, "diff", "--name-only", refs["base_sha"], refs["fixed_sha"], timeout_seconds=timeout_seconds)
    if not result.passed:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _materialize_fixed_tests(
    checkout: Path,
    *,
    fixed_ref: str,
    targets: list[str],
    timeout_seconds: int,
) -> list[CommandResult]:
    commands: list[CommandResult] = []
    for path in sorted({_target_path(target) for target in targets if _target_path(target)}):
        result = _git(checkout, "show", f"{fixed_ref}:{path}", timeout_seconds=timeout_seconds)
        commands.append(result)
        if result.passed:
            destination = checkout / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(result.stdout, encoding="utf-8")
    return commands


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
) -> GradeResult:
    """Grade a model patch on a validated PR-suite task."""
    task_id = str(instance.get("task_id") or instance.get("instance_id") or "")
    row = dict(instance)
    run_id = f"pr_suite_grade_{now_stamp()}_{time.time_ns()}_{canonical_sha256({'task_id': task_id, 'patch': model_patch})[:12]}"
    receipt_path = Path(receipt_root).expanduser() / f"{run_id}.json"
    root = Path(work_root).expanduser() / run_id if work_root else Path(tempfile.mkdtemp(prefix="forge-pr-suite-grade-"))
    checkout = root / "repo"
    started = time.time()
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    resolved = False
    grade_error: str | None = None
    refs: dict[str, str] = {}
    targets = fail_to_pass_targets(row)
    repo_url = ""

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
        repo_url = _repo_url_for_row(row)
        clone = _clone_repo(repo_url, checkout, timeout_seconds=min(timeout, 600))
        commands.append({"phase": "clone", **clone.to_receipt()})
        if not clone.passed:
            blockers.append("clone_failed")
            grade_error = "clone_failed"
            raise RuntimeError("git clone failed")
        refs = _resolve_refs(checkout, row, timeout_seconds=min(timeout, 180))
        checkout_commands = _checkout_ref(checkout, refs["base_sha"], timeout_seconds=min(timeout, 180))
        commands.extend({"phase": "checkout_base", **command.to_receipt()} for command in checkout_commands)
        if not all(command.passed for command in checkout_commands):
            blockers.append("base_checkout_failed")
            grade_error = "base_checkout_failed"
            raise RuntimeError("base checkout failed")
        materialize = _materialize_fixed_tests(
            checkout,
            fixed_ref=refs["fixed_sha"],
            targets=targets,
            timeout_seconds=min(timeout, 180),
        )
        commands.extend({"phase": "materialize_fixed_test", **command.to_receipt()} for command in materialize)
        if not materialize or not all(command.passed for command in materialize):
            blockers.append("fixed_test_materialization_failed")
            grade_error = "fixed_test_materialization_failed"
            raise RuntimeError("could not materialize fixed FAIL_TO_PASS tests")
        apply_result = _git(
            checkout,
            "apply",
            "--whitespace=nowarn",
            "-",
            timeout_seconds=min(timeout, 180),
            stdin=model_patch,
        )
        commands.append({"phase": "apply_model_patch", **apply_result.to_receipt()})
        if not apply_result.passed:
            blockers.append("patch_apply_failed")
            grade_error = "patch_apply_failed"
            raise RuntimeError("patch apply failed")
        setup_argv = _setup_command(setup_command_template, python=python, checkout=checkout)
        if setup_argv is not None:
            setup_timeout = int(setup_timeout_seconds) if setup_timeout_seconds is not None else max(min(timeout, 900), 600)
            setup = _run(setup_argv, cwd=checkout, timeout_seconds=setup_timeout)
            commands.append({"phase": "setup_after_patch", **setup.to_receipt()})
            if not setup.passed:
                blockers.append("patch_environment_setup_failed")
                grade_error = "patch_environment_setup_failed"
                raise RuntimeError("patch environment setup failed")
        command = _command_for_targets(_command_template(row), python=python, targets=targets, checkout=checkout)
        test_result = _run(command, cwd=checkout, timeout_seconds=timeout)
        commands.append({"phase": "test_after_patch", **test_result.to_receipt()})
        resolved = test_result.passed
        if not resolved:
            blockers.append("fail_to_pass_not_resolved")
            grade_error = f"test_returncode={test_result.returncode}"
    except Exception as exc:  # noqa: BLE001 - receipt-first grader.
        if grade_error is None:
            grade_error = f"{type(exc).__name__}: {exc}"

    receipt = {
        "schema": SCHEMA_VERSION,
        "run_id": run_id,
        "task_id": task_id,
        "repo": row.get("repo") or row.get("repository") or "",
        "repo_url": repo_url,
        "started_at": now_stamp(),
        "finished_at": now_stamp(),
        "resolved": resolved,
        "grade_error": grade_error,
        "blockers": blockers,
        "fail_to_pass": targets,
        "patch_len": len(model_patch or ""),
        "patch_sha256": canonical_sha256({"patch": model_patch or ""}),
        "setup_command_template": str(setup_command_template or ""),
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
