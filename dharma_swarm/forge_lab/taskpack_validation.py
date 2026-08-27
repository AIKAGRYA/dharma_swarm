"""Pure validation primitives for governed RSI taskpack intake."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Literal, Mapping

from dharma_swarm.forge_lab.state_io import (
    content_digest,
    validate_digest,
    validate_safe_id,
)
from dharma_swarm.forge_v1.forge_v2.fresh_task_oracle import (
    CLEAN_ORACLE_STATES,
    DEFAULT_SOURCE,
    derive_task_provenance,
)

TaskpackMode = Literal["governed_fresh", "search_only_public_swebench"]

MODE_GOVERNED_FRESH: TaskpackMode = "governed_fresh"
MODE_SEARCH_ONLY_PUBLIC_SWEBENCH: TaskpackMode = "search_only_public_swebench"
FRESH_SOURCE, FRESH_TASKBED = DEFAULT_SOURCE, "fresh_pr_suite"
SEARCH_SOURCE = "official_swebench_search_only"
SEARCH_TASKBED = "search_only_public_swebench"
POLICY_MAX_USES_PER_EPOCH = 1
MAX_MANIFEST_BYTES, MAX_MANIFEST_ROWS = 8 * 1024 * 1024, 5_000
ORACLE_SCHEMA = "forge_v2.fresh_task_oracle.v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SWE_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-[1-9][0-9]*$")


class TaskpackError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        receipt_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.receipt_path = receipt_path


def raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_regular_file(path: Path, limit: int, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise TaskpackError(f"{label}_UNREADABLE", f"cannot read {path}") from exc
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise TaskpackError(f"{label}_UNSAFE", f"{path} is not a regular file")
        data = handle.read(limit + 1)
        after = os.fstat(descriptor)
    if len(data) > limit:
        raise TaskpackError(f"{label}_TOO_LARGE", f"{path} exceeds {limit} bytes")
    before_id = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_id = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_id != after_id or len(data) != before.st_size:
        raise TaskpackError(f"{label}_CHANGED", f"{path} changed while read")
    return data


def sealed_manifest(
    path_value: Path | str,
    claimed_digest: str,
) -> tuple[Path, bytes, list[dict[str, Any]], list[str]]:
    try:
        validate_digest(claimed_digest)
    except (TypeError, ValueError) as exc:
        raise TaskpackError("MANIFEST_DIGEST_INVALID", str(exc)) from exc
    raw = Path(path_value).expanduser()
    if raw.suffix.lower() != ".jsonl" or raw.is_symlink():
        raise TaskpackError(
            "MANIFEST_NOT_JSONL", "manifest must be a regular .jsonl file"
        )
    try:
        path = raw.resolve(strict=True)
    except OSError as exc:
        raise TaskpackError(
            "MANIFEST_UNREADABLE", f"manifest does not exist: {raw}"
        ) from exc
    data = read_regular_file(path, MAX_MANIFEST_BYTES, "MANIFEST")
    if raw_digest(data) != claimed_digest:
        raise TaskpackError(
            "MANIFEST_DIGEST_MISMATCH", "manifest bytes do not match digest"
        )
    if not data or not data.endswith(b"\n"):
        raise TaskpackError(
            "MANIFEST_NOT_SEALED", "sealed JSONL must end with a newline"
        )
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise TaskpackError(
            "MANIFEST_ENCODING_INVALID", "manifest must be UTF-8"
        ) from exc

    rows: list[dict[str, Any]] = []
    task_ids: list[str] = []
    seen: set[str] = set()
    for number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TaskpackError(
                "MANIFEST_JSONL_INVALID", f"invalid JSON line {number}"
            ) from exc
        if not line.strip() or not isinstance(row, dict):
            raise TaskpackError(
                "MANIFEST_JSONL_INVALID", f"line {number} must be an object"
            )
        task_id, instance_id = row.get("task_id"), row.get("instance_id")
        if task_id is not None and (
            not isinstance(task_id, str) or not task_id.strip()
        ):
            raise TaskpackError(
                "MANIFEST_TASK_ID_INVALID", f"invalid task_id line {number}"
            )
        if instance_id is not None and (
            not isinstance(instance_id, str) or not instance_id.strip()
        ):
            raise TaskpackError(
                "MANIFEST_TASK_ID_INVALID", f"invalid instance_id line {number}"
            )
        if task_id and instance_id and task_id.strip() != instance_id.strip():
            raise TaskpackError(
                "MANIFEST_TASK_ID_AMBIGUOUS", f"IDs disagree line {number}"
            )
        explicit = str(task_id or instance_id or "").strip()
        if not explicit:
            raise TaskpackError(
                "MANIFEST_TASK_ID_REQUIRED", f"explicit ID required line {number}"
            )
        if explicit.lower().startswith("pr::"):
            raise TaskpackError(
                "MANIFEST_PR_TASK_ID_FORBIDDEN", f"pr:: ID line {number}"
            )
        if explicit in seen:
            raise TaskpackError(
                "MANIFEST_TASK_ID_DUPLICATE", f"duplicate ID {explicit}"
            )
        uses = row.get("max_uses_per_epoch", POLICY_MAX_USES_PER_EPOCH)
        if (
            not isinstance(uses, int)
            or isinstance(uses, bool)
            or uses != POLICY_MAX_USES_PER_EPOCH
        ):
            raise TaskpackError(
                "MANIFEST_MAX_USES_POLICY", f"max uses override line {number}"
            )
        seen.add(explicit)
        rows.append(dict(row))
        task_ids.append(explicit)
        if len(rows) > MAX_MANIFEST_ROWS:
            raise TaskpackError("MANIFEST_TOO_MANY_ROWS", "manifest row limit exceeded")
    return path, data, rows, task_ids


def mode_policy(
    mode: TaskpackMode,
    source: str | None,
    taskbed: str | None,
    max_uses_per_epoch: int,
) -> dict[str, Any]:
    if mode == MODE_GOVERNED_FRESH:
        expected = (FRESH_SOURCE, FRESH_TASKBED, False)
    elif mode == MODE_SEARCH_ONLY_PUBLIC_SWEBENCH:
        expected = (SEARCH_SOURCE, SEARCH_TASKBED, True)
    else:
        raise TaskpackError("MODE_INVALID", f"unsupported mode: {mode}")
    actual = (
        expected[0] if source is None else source,
        expected[1] if taskbed is None else taskbed,
    )
    try:
        validate_safe_id(actual[0], field="source")
        validate_safe_id(actual[1], field="taskbed")
    except ValueError as exc:
        raise TaskpackError("POLICY_INVALID", str(exc)) from exc
    if actual != expected[:2]:
        raise TaskpackError("POLICY_NOT_ADMITTED", f"{mode} policy is fixed")
    if (
        not isinstance(max_uses_per_epoch, int)
        or isinstance(max_uses_per_epoch, bool)
        or max_uses_per_epoch != POLICY_MAX_USES_PER_EPOCH
    ):
        raise TaskpackError("MAX_USES_POLICY", "max_uses_per_epoch must equal 1")
    return {
        "source": actual[0],
        "taskbed": actual[1],
        "max_uses_per_epoch": POLICY_MAX_USES_PER_EPOCH,
        "include_ineligible": expected[2],
    }


def oracle_preflight(
    rows: list[dict[str, Any]],
    task_ids: list[str],
    cutoff: Any,
    policy: Mapping[str, Any],
    mode: TaskpackMode,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for number, (row, task_id) in enumerate(zip(rows, task_ids, strict=True), 1):
        proof = derive_task_provenance(
            row,
            model_cutoff=cutoff,
            source=str(policy["source"]),
        )
        state = str(proof["contamination_state"])
        blockers = list(proof.get("blockers", []))
        counts[state] = counts.get(state, 0) + 1
        if mode == MODE_GOVERNED_FRESH and state not in CLEAN_ORACLE_STATES:
            raise TaskpackError(
                "MANIFEST_NOT_ORACLE_FRESH", f"line {number} derived {state}"
            )
        if mode == MODE_SEARCH_ONLY_PUBLIC_SWEBENCH:
            repo = str(row.get("repo") or "")
            base_commit = str(row.get("base_commit") or "")
            official = (
                row.get("instance_id") == task_id
                and _SWE_ID_RE.fullmatch(task_id)
                and repo.count("/") == 1
                and task_id.rpartition("-")[0] == repo.replace("/", "__")
                and SHA_RE.fullmatch(base_commit)
                and str(row.get("problem_statement") or "").strip()
                and int(proof.get("fail_to_pass_count") or 0) > 0
            )
            if not official:
                raise TaskpackError(
                    "SEARCH_TASK_NOT_OFFICIAL_SWEBENCH", f"invalid line {number}"
                )
            if (
                state != "possible_pretrain"
                or "public_swebench_possible_pretrain" not in blockers
            ):
                raise TaskpackError(
                    "SEARCH_TASK_CUSTODY_INVALID", f"unsafe line {number}"
                )
        evidence.append(
            {
                "task_id": task_id,
                "state": state,
                "blockers": blockers,
                "task_sha256": proof.get("task_sha256"),
            }
        )
    return {
        "oracle_schema": ORACLE_SCHEMA,
        "derived_state_counts": counts,
        "evidence_digest": content_digest(evidence),
        "all_rows_admitted": True,
    }


__all__ = [
    "FRESH_SOURCE",
    "FRESH_TASKBED",
    "MAX_MANIFEST_BYTES",
    "MAX_MANIFEST_ROWS",
    "MODE_GOVERNED_FRESH",
    "MODE_SEARCH_ONLY_PUBLIC_SWEBENCH",
    "ORACLE_SCHEMA",
    "POLICY_MAX_USES_PER_EPOCH",
    "SEARCH_SOURCE",
    "SEARCH_TASKBED",
    "SHA_RE",
    "TaskpackError",
    "TaskpackMode",
    "mode_policy",
    "oracle_preflight",
    "raw_digest",
    "read_regular_file",
    "sealed_manifest",
]
