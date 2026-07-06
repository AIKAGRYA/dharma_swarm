"""Prompt/context loading for validated PR-suite tasks."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from . import taskbed_ledger
from .pr_suite_grader import (
    _changed_files,
    _checkout_ref,
    _clone_repo,
    _is_test_path,
    _list_field,
    _repo_url_for_row,
    _resolve_refs,
    fail_to_pass_targets,
)

def task_row_for_id(task_id: str, *, db_path: Path | str = taskbed_ledger.DEFAULT_DB) -> dict[str, Any]:
    row = taskbed_ledger.task_for_id(task_id, db_path=db_path)
    task = dict(row["task"])
    task.setdefault("task_id", row["task_id"])
    task.setdefault("instance_id", row["task_id"])
    task.setdefault("source", row.get("source", ""))
    task.setdefault("taskbed", row.get("taskbed", ""))
    task.setdefault("contamination_state", row.get("contamination_state", ""))
    task.setdefault("provenance", row.get("provenance", {}))
    task.setdefault("sealed_provenance", row.get("provenance", {}))
    return task


def load_pr_suite_context(
    task_id: str,
    *,
    db_path: Path | str = taskbed_ledger.DEFAULT_DB,
    work_root: Path | None = None,
    timeout_seconds: int = 180,
    max_file_chars: int = 400_000,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Load prompt context for a validated PR-suite taskbed row."""
    row = task_row_for_id(task_id, db_path=db_path)
    if not fail_to_pass_targets(row):
        raise ValueError(f"PR-suite task {task_id} has no explicit fail_to_pass targets")
    temp: tempfile.TemporaryDirectory[str] | None = None
    if work_root is None:
        temp = tempfile.TemporaryDirectory(prefix="forge-pr-suite-context-")
        root = Path(temp.name)
    else:
        root = Path(work_root).expanduser()
        root.mkdir(parents=True, exist_ok=True)
    checkout = root / "repo"
    try:
        clone = _clone_repo(_repo_url_for_row(row), checkout, timeout_seconds=timeout_seconds)
        if not clone.passed:
            raise RuntimeError(f"git clone failed: {clone.stderr or clone.stdout}")
        refs = _resolve_refs(checkout, row, timeout_seconds=timeout_seconds)
        commands = _checkout_ref(checkout, refs["base_sha"], timeout_seconds=timeout_seconds)
        if not all(command.passed for command in commands):
            raise RuntimeError("base checkout failed")
        changed = _changed_files(checkout, refs, timeout_seconds=timeout_seconds)
        context_files = _list_field(row, "context_files", "source_files")
        if not context_files:
            context_files = [path for path in changed if not _is_test_path(path)]
        ctx: dict[str, str] = {}
        for path in context_files:
            file_path = checkout / path
            if file_path.exists() and file_path.is_file():
                content = file_path.read_text(encoding="utf-8", errors="replace")
                ctx[path] = content[:max_file_chars]
        if not ctx:
            raise ValueError(f"PR-suite task {task_id} has no source context files")
        problem = str(row.get("problem_statement") or row.get("title") or "").strip()
        inst = {
            **row,
            "instance_id": task_id,
            "task_id": task_id,
            "repo": row.get("repo") or row.get("repository") or "",
            "base_commit": refs["base_sha"],
            "fixed_commit": refs["fixed_sha"],
            "problem_statement": problem or f"Fix validated post-cutoff PR task {task_id}",
            "FAIL_TO_PASS": fail_to_pass_targets(row),
            "source_kind": row.get("source_kind") or row.get("source") or "post_cutoff_pr_suite",
            "contamination_state": row.get("contamination_state") or "fresh_heldout",
            "sealed_provenance": row.get("sealed_provenance") or row.get("provenance") or {},
            "pr_suite_refs": refs,
            "pr_suite_context_files": list(ctx),
        }
        return inst, ctx
    finally:
        if temp is not None:
            temp.cleanup()
