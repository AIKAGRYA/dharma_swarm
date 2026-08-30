"""Exact offline SWE-bench judge custody for unattended EXPLORE."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256

JUDGE_BINDING_SCHEMA = "rsi_lab.swebench_judge_binding.v1"
JUDGE_FIELDS = (
    "repo",
    "instance_id",
    "base_commit",
    "patch",
    "test_patch",
    "problem_statement",
    "hints_text",
    "created_at",
    "version",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "environment_setup_commit",
    "difficulty",
)


@dataclass(frozen=True)
class JudgeReleaseContract:
    """Release fixtures and the shared typed-refusal constructor."""

    fixtures: Mapping[str, Mapping[str, Any]]
    fixture_for_task: Callable[[str], dict[str, Any]]
    error_factory: Callable[[str, str], Exception]


def _load_release_dataset(
    name: str,
    split: str,
    revision: str,
) -> tuple[list[dict[str, Any]], list[str], Path, Path]:
    """Read the exact Hub snapshot's Parquet without a processed-cache fallback."""

    from huggingface_hub import snapshot_download
    import pyarrow.parquet as parquet

    snapshot = Path(
        snapshot_download(
            repo_id=name,
            repo_type="dataset",
            revision=revision,
            local_files_only=True,
        )
    )
    files = sorted((snapshot / "data").glob(f"{split}-*.parquet"))
    if len(files) != 1:
        raise ValueError("release snapshot must contain one split parquet")
    table = parquet.read_table(files[0])
    return table.to_pylist(), list(table.column_names), snapshot, files[0]


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def validate_admitted_judge_instance(
    instance: Any,
    *,
    contract: JudgeReleaseContract,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Validate all judge bytes without returning gold fields in the proof."""

    if not isinstance(instance, dict):
        raise contract.error_factory(
            "JUDGE_ROW_INVALID",
            "release-bound judge row is not a dictionary",
        )
    resolved_id = str(task_id or instance.get("instance_id") or "")
    fixture = contract.fixture_for_task(resolved_id)
    if (
        set(instance) != set(fixture["judge_fields"])
        or instance.get("instance_id") != resolved_id
        or instance.get("repo") != fixture["repo"]
        or instance.get("base_commit") != fixture["base_commit"]
    ):
        raise contract.error_factory(
            "JUDGE_ROW_FIXTURE_MISMATCH",
            "judge row identity or fields differ from the release fixture",
        )
    row_sha256 = canonical_sha256(instance)
    if row_sha256 != fixture["judge_row_sha256"]:
        raise contract.error_factory(
            "JUDGE_ROW_DIGEST_MISMATCH",
            "judge row bytes differ from the release fixture",
        )
    try:
        fail_to_pass = json.loads(instance["FAIL_TO_PASS"])
        pass_to_pass = json.loads(instance["PASS_TO_PASS"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise contract.error_factory(
            "JUDGE_TEST_LIST_INVALID",
            "judge test lists are not canonical JSON arrays",
        ) from exc
    if not all(
        isinstance(values, list)
        and all(isinstance(item, str) and item for item in values)
        for values in (fail_to_pass, pass_to_pass)
    ):
        raise contract.error_factory(
            "JUDGE_TEST_LIST_INVALID",
            "judge test lists are not nonempty-string arrays",
        )
    return {
        "instance_id": resolved_id,
        "row_sha256": row_sha256,
        "fail_to_pass_sha256": canonical_sha256(fail_to_pass),
        "fail_to_pass_count": len(fail_to_pass),
        "pass_to_pass_sha256": canonical_sha256(pass_to_pass),
        "pass_to_pass_count": len(pass_to_pass),
    }


def _attested_judge_dataset(
    name: str,
    split: str,
    instance_ids: list[str] | None,
    *,
    contract: JudgeReleaseContract,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load only the release revision and attest its cached Parquet authority."""

    fixtures = {
        task_id: contract.fixture_for_task(task_id) for task_id in contract.fixtures
    }
    allowed_ids = {
        task_id
        for task_id, fixture in fixtures.items()
        if fixture["judge_dataset_name"] == name
        and fixture["judge_dataset_split"] == split
    }
    requested_ids = (
        set(map(str, instance_ids)) if instance_ids is not None else allowed_ids
    )
    if not requested_ids or not requested_ids.issubset(allowed_ids):
        raise contract.error_factory(
            "JUDGE_DATASET_NOT_ADMITTED",
            "dataset, split, or instance selection is not release-bound",
        )
    fixture = fixtures[sorted(requested_ids)[0]]
    if any(
        fixtures[task_id][field] != fixture[field]
        for task_id in requested_ids
        for field in (
            "judge_dataset_revision",
            "judge_dataset_rows",
            "judge_fields",
            "judge_cache_file_digest",
        )
    ):
        raise contract.error_factory(
            "JUDGE_DATASET_FIXTURE_INCONSISTENT",
            "admitted task fixtures disagree about judge dataset custody",
        )
    if (
        os.environ.get("HF_DATASETS_OFFLINE") != "1"
        or os.environ.get("HF_HUB_OFFLINE") != "1"
    ):
        raise contract.error_factory(
            "JUDGE_DATASET_OFFLINE_REQUIRED",
            "judge dataset access must be offline",
        )
    try:
        rows, column_names, snapshot, cache_file = _load_release_dataset(
            name,
            split,
            fixture["judge_dataset_revision"],
        )
        row_count = len(rows)
    except Exception as exc:
        raise contract.error_factory(
            "JUDGE_DATASET_LOAD_FAILED",
            "release-bound judge dataset is unavailable from offline cache",
        ) from exc
    if row_count != fixture["judge_dataset_rows"] or column_names != list(
        fixture["judge_fields"]
    ):
        raise contract.error_factory(
            "JUDGE_DATASET_SHAPE_MISMATCH",
            "judge dataset shape differs from the release fixture",
        )
    try:
        cache_root = Path(os.environ["HF_HUB_CACHE"]).resolve(strict=True)
        snapshot_root = snapshot.resolve(strict=True)
        resolved_cache_file = cache_file.resolve(strict=True)
        cache_digest = _file_digest(resolved_cache_file)
    except (KeyError, OSError) as exc:
        raise contract.error_factory(
            "JUDGE_CACHE_IDENTITY_UNAVAILABLE",
            "judge cache file identity could not be established",
        ) from exc
    if (
        snapshot.name != fixture["judge_dataset_revision"]
        or not snapshot_root.is_relative_to(cache_root)
        or not cache_file.is_relative_to(snapshot)
        or not resolved_cache_file.is_relative_to(cache_root)
        or cache_digest != fixture["judge_cache_file_digest"]
    ):
        raise contract.error_factory(
            "JUDGE_CACHE_DIGEST_MISMATCH",
            "judge cache file is outside or differs from the release fixture",
        )
    selected = [dict(row) for row in rows if row.get("instance_id") in requested_ids]
    if len(selected) != len(requested_ids):
        raise contract.error_factory(
            "JUDGE_ROW_MISSING",
            "release-bound judge row is absent from the offline cache",
        )
    row_proofs = {
        row["instance_id"]: validate_admitted_judge_instance(row, contract=contract)
        for row in selected
    }
    proof = {
        "schema": JUDGE_BINDING_SCHEMA,
        "dataset_name": name,
        "dataset_revision": fixture["judge_dataset_revision"],
        "split": split,
        "row_count": row_count,
        "cache_file_digest": cache_digest,
        "offline": True,
        "rows": row_proofs,
    }
    proof["binding_digest"] = content_digest(proof)
    return selected, proof


def load_admitted_judge_dataset(
    name: str,
    split: str,
    instance_ids: list[str] | None = None,
    *,
    contract: JudgeReleaseContract,
) -> list[dict[str, Any]]:
    """SWE-bench loader replacement restricted to the admitted cached rows."""

    rows, _proof = _attested_judge_dataset(
        name,
        split,
        instance_ids,
        contract=contract,
    )
    return rows


def admitted_judge_binding(
    task_id: str,
    *,
    contract: JudgeReleaseContract,
) -> dict[str, Any]:
    fixture = contract.fixture_for_task(task_id)
    _rows, proof = _attested_judge_dataset(
        fixture["judge_dataset_name"],
        fixture["judge_dataset_split"],
        [task_id],
        contract=contract,
    )
    return proof


__all__ = [
    "JUDGE_BINDING_SCHEMA",
    "JUDGE_FIELDS",
    "JudgeReleaseContract",
    "admitted_judge_binding",
    "load_admitted_judge_dataset",
    "validate_admitted_judge_instance",
]
