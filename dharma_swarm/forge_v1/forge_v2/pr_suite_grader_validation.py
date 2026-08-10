"""Validator-receipt authentication and replay binding for the grader."""
from __future__ import annotations

import hmac
import json
import os
import stat
from pathlib import Path
from typing import Any

from . import pr_suite_execution as execution
from .pr_suite_execution import ExecutionProfile
from .pr_suite_validator_runtime import (
    SCHEMA_VERSION as VALIDATOR_SCHEMA_VERSION,
    candidate_targets as validator_candidate_targets,
)
from .signals import canonical_sha256


def _load_validation_receipt(row: dict[str, Any]) -> dict[str, Any]:
    path = str(row.get("validation_receipt") or "").strip()
    if not path:
        return {}
    receipt_path = Path(path).expanduser()
    try:
        receipt_stat = receipt_path.lstat()
    except OSError:
        return {}
    if (
        receipt_path.is_symlink()
        or not stat.S_ISREG(receipt_stat.st_mode)
        or receipt_stat.st_size > 2 * 1024 * 1024
        or receipt_stat.st_mode & 0o022
        or receipt_stat.st_uid not in {0, os.geteuid()}
    ):
        return {}
    try:
        return json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _require_validation_profile_binding(
    row: dict[str, Any],
    *,
    profile: ExecutionProfile,
    targets: list[str],
    trusted_public_keys: dict[str, bytes | str] | None,
) -> dict[str, Any]:
    """Bind grading to the validator receipt and its exact command profile."""

    receipt = _load_validation_receipt(row)
    if not receipt:
        raise execution.ProfileTampered(
            "validated task is missing its validation receipt"
        )
    internal_digest = str(receipt.get("receipt_sha256") or "")
    row_digest = str(row.get("validation_receipt_sha256") or "")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    computed = canonical_sha256(unsigned)
    if (
        not internal_digest
        or not row_digest
        or not hmac.compare_digest(internal_digest, computed)
    ):
        raise execution.ProfileTampered("validation receipt digest mismatch")
    if not hmac.compare_digest(row_digest, computed):
        raise execution.ProfileTampered(
            "task row is not bound to its validation receipt"
        )
    if receipt.get("schema") != VALIDATOR_SCHEMA_VERSION:
        raise execution.ProfileTampered("validation receipt schema is invalid")
    execution.verify_validator_receipt_signature(
        receipt,
        trusted_public_keys=trusted_public_keys,
    )
    if receipt.get("status") != "fail_to_pass_validated":
        raise execution.ProfileTampered(
            "validation receipt did not validate FAIL_TO_PASS"
        )
    binding = receipt.get("source_binding")
    if not isinstance(binding, dict):
        raise execution.ProfileTampered("validation receipt has no source binding")
    expected_locators = {
        key: row.get(key)
        for key in ("repo_path", "clone_url", "repo_url", "local_repo")
        if row.get(key) is not None
    }
    expected_repo = row.get("repo") or row.get("repository") or ""
    if binding != {
        "source_row_sha256": row.get("validation_source_row_sha256"),
        "task_hint": row.get("validation_task_hint"),
        "repo": expected_repo,
        "repository_locators": expected_locators,
        "pr_number": row.get("pr_number"),
        "candidate_targets": validator_candidate_targets(row),
        "resolved_refs": dict(receipt.get("resolved_refs") or {}),
    }:
        raise execution.ProfileTampered(
            "validation receipt source/task binding disagrees"
        )
    task_id = str(row.get("task_id") or row.get("instance_id") or "")
    pr_number = row.get("pr_number")
    if task_id.startswith("pr::") and expected_repo and pr_number is not None:
        expected_task_id = f"pr::{str(expected_repo).strip('/')}#{pr_number}"
        if task_id != expected_task_id:
            raise execution.ProfileTampered(
                "validation receipt was replayed across task identity"
            )
    declared_profile = str(receipt.get("execution_profile_sha256") or "")
    row_profile = str(row.get("validation_execution_profile_sha256") or "")
    try:
        receipt_profile = ExecutionProfile.from_mapping(
            dict(receipt.get("execution_profile") or {})
        )
    except (TypeError, execution.ProfileTampered) as exc:
        raise execution.ProfileTampered(
            "validation receipt has no valid execution profile"
        ) from exc
    if receipt_profile.sha256 != declared_profile:
        raise execution.ProfileTampered(
            "validation execution profile digest mismatch"
        )
    if (
        not declared_profile
        or declared_profile != row_profile
        or declared_profile != profile.sha256
    ):
        raise execution.ProfileTampered("grader profile differs from validator profile")
    validated = {str(target) for target in receipt.get("validated_fail_to_pass") or []}
    if not set(targets).issubset(validated):
        raise execution.ProfileTampered(
            "task FAIL_TO_PASS targets are not validator-bound"
        )
    receipt_refs = dict(receipt.get("resolved_refs") or {})
    if row.get("validated_base_sha") != receipt_refs.get("base_sha"):
        raise execution.ProfileTampered(
            "validated base SHA differs from validation receipt"
        )
    if row.get("validated_fixed_sha") != receipt_refs.get("fixed_sha"):
        raise execution.ProfileTampered(
            "validated fixed SHA differs from validation receipt"
        )
    return receipt


__all__ = []
