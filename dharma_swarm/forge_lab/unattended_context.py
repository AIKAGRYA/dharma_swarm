"""Release-bound, no-pull source context for the unattended EXPLORE lane."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from dharma_swarm.forge_lab import unattended_judge as _unattended_judge
from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_lab.unattended_judge import (
    JUDGE_BINDING_SCHEMA,
    JUDGE_FIELDS,
)
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256

CONTEXT_BINDING_SCHEMA = "rsi_lab.unattended_context_binding.v1"
MAX_CONTEXT_CHARS = 400_000
PROMPT_TASK_FIELDS = (
    "task_id",
    "instance_id",
    "repo",
    "base_commit",
    "problem_statement",
)
ADMITTED_TASK_IMAGES: dict[str, dict[str, Any]] = {
    "django__django-12209": {
        "task_sha256": "1367c9eb0b844691ab687e20b74a0ff901a7e33ce81169e177a4fe8afe1ab2a8",
        "task_sha256_fields": (
            "FAIL_TO_PASS",
            "base_commit",
            "instance_id",
            "problem_statement",
            "repo",
        ),
        "task_payload_digest": "sha256:b357feb2dfba76ec654c2ad8a4ce8ada2b3e9e0a335be5a2649b6281a4f30eec",
        "repo": "django/django",
        "base_commit": "5a68f024987e6d16c2626a31bf653a2edddea579",
        "source": "official_swebench_search_only",
        "taskbed": "search_only_public_swebench",
        "image_reference": "swebench/sweb.eval.x86_64.django_1776_django-12209:latest",
        "image_id": "sha256:6781fe1de96e581d385aa7797a580274023f7a625a891f1ecd751ff303e6a256",
        "repo_digest": "swebench/sweb.eval.x86_64.django_1776_django-12209@sha256:6781fe1de96e581d385aa7797a580274023f7a625a891f1ecd751ff303e6a256",
        "os": "linux",
        "architecture": "amd64",
        "target_paths": ("django/db/models/base.py",),
        "judge_dataset_name": "princeton-nlp/SWE-bench_Verified",
        "judge_dataset_revision": "c104f840cc67f8b6eec6f759ebc8b2693d585d4a",
        "judge_dataset_split": "test",
        "judge_dataset_rows": 500,
        "judge_fields": JUDGE_FIELDS,
        "judge_cache_file_digest": "sha256:a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd",
        "judge_row_sha256": "939d1c36810a3400bab68d472d01ac5be33d18939f2cc0b96486ef7db997411c",
    }
}


class UnattendedContextError(RuntimeError):
    """A typed refusal before any model call or budget reservation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def sanitize_unattended_docker_env() -> None:
    """Pin Docker and the judge cache after runtime credential bootstrap."""

    for name in ("DOCKER_API_VERSION", "DOCKER_CERT_PATH", "DOCKER_TLS_VERIFY"):
        os.environ.pop(name, None)
    if platform.system() == "Linux":
        os.environ["DOCKER_CONTEXT"] = "default"
        os.environ["FORGE_DOCKER_CONTEXT"] = "default"
        os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    home = Path(os.environ.get("HOME", "/nonexistent")).expanduser().resolve()
    hf_home = home / ".cache" / "huggingface"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HF_DATASETS_CACHE"] = str(hf_home / "datasets")
    os.environ["HF_HUB_CACHE"] = str(hf_home / "hub")
    os.environ["RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE"] = "1"


def admitted_task_image(task_id: str) -> dict[str, Any]:
    try:
        return dict(ADMITTED_TASK_IMAGES[task_id])
    except KeyError as exc:
        raise UnattendedContextError(
            "TASK_IMAGE_NOT_ADMITTED",
            f"no release-bound image fixture exists for {task_id}",
        ) from exc


def _task_for_id(task_id: str, db_path: Path) -> dict[str, Any]:
    from dharma_swarm.forge_v1.forge_v2.taskbed_allocation import task_for_id

    return task_for_id(task_id, db_path=db_path)


def _judge_contract() -> _unattended_judge.JudgeReleaseContract:
    return _unattended_judge.JudgeReleaseContract(
        fixtures=ADMITTED_TASK_IMAGES,
        fixture_for_task=admitted_task_image,
        error_factory=UnattendedContextError,
    )


def validate_admitted_judge_instance(
    instance: Any,
    *,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Validate all judge bytes without returning gold fields in the proof."""

    return _unattended_judge.validate_admitted_judge_instance(
        instance,
        task_id=task_id,
        contract=_judge_contract(),
    )


def load_admitted_judge_dataset(
    name: str,
    split: str,
    instance_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Load only release-bound rows from the exact offline judge snapshot."""

    return _unattended_judge.load_admitted_judge_dataset(
        name,
        split,
        instance_ids,
        contract=_judge_contract(),
    )


def admitted_judge_binding(task_id: str) -> dict[str, Any]:
    return _unattended_judge.admitted_judge_binding(
        task_id,
        contract=_judge_contract(),
    )


def _docker_env() -> dict[str, str]:
    host = os.environ.get("DOCKER_HOST", "").strip()
    if not host:
        raise UnattendedContextError(
            "DOCKER_HOST_UNPINNED",
            "unattended Docker host is not pinned",
        )
    return {
        "DOCKER_HOST": host,
        "HOME": os.environ.get("HOME", "/nonexistent"),
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
    }


def _inspect_image(fixture: dict[str, Any]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", fixture["image_reference"]],
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
            env=_docker_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UnattendedContextError(
            "TASK_IMAGE_INSPECT_FAILED",
            "cached task image could not be inspected",
        ) from exc
    try:
        rows = json.loads(result.stdout) if result.returncode == 0 else []
        image = rows[0] if isinstance(rows, list) and len(rows) == 1 else None
    except json.JSONDecodeError:
        image = None
    valid = bool(
        isinstance(image, dict)
        and image.get("Id") == fixture["image_id"]
        and image.get("Os") == fixture["os"]
        and image.get("Architecture") == fixture["architecture"]
        and fixture["image_reference"] in (image.get("RepoTags") or [])
        and fixture["repo_digest"] in (image.get("RepoDigests") or [])
    )
    if not valid:
        raise UnattendedContextError(
            "TASK_IMAGE_IDENTITY_MISMATCH",
            "cached task image does not match the release-bound fixture",
        )
    return image


def _safe_target_path(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or str(path) != value:
        raise UnattendedContextError(
            "TASK_CONTEXT_PATH_UNSAFE",
            "release-bound context path is unsafe",
        )
    return value


def _read_context_file(image_id: str, relative: str) -> str:
    command = [
        "docker",
        "run",
        "--pull=never",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--pids-limit",
        "32",
        "--memory",
        "256m",
        "--cpus",
        "1",
        "--platform",
        "linux/amd64",
        "--entrypoint",
        "cat",
        image_id,
        f"/testbed/{relative}",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
            env=_docker_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UnattendedContextError(
            "TASK_CONTEXT_READ_FAILED",
            "cached task context could not be read",
        ) from exc
    content = result.stdout if result.returncode == 0 else ""
    if not content or len(content) > MAX_CONTEXT_CHARS:
        raise UnattendedContextError(
            "TASK_CONTEXT_EMPTY_OR_OVERSIZE",
            "cached task context is empty or exceeds the fixed ceiling",
        )
    return content


def load_admitted_task_context(
    task_id: str,
    *,
    state_root: Path,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    """Read one task only from its exact cached image, with no pull or network."""

    fixture = admitted_task_image(task_id)
    db_path = state_root / ".dharma" / "forge_v1" / "taskbed.db"
    row = _task_for_id(task_id, db_path)
    task = row.get("task") if isinstance(row.get("task"), dict) else {}
    provenance = (
        row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    )
    valid_task = bool(
        row.get("active") == 1
        and row.get("source") == fixture["source"]
        and row.get("taskbed") == fixture["taskbed"]
        and provenance.get("task_sha256") == fixture["task_sha256"]
        and task.get("task_id") == task_id
        and task.get("instance_id") == task_id
        and task.get("repo") == fixture["repo"]
        and task.get("base_commit") == fixture["base_commit"]
        and str(task.get("problem_statement") or "").strip()
        and task.get("provenance") == provenance
        and task.get("sealed_provenance") == provenance
        and all(field in task for field in fixture["task_sha256_fields"])
        and all(field in task for field in PROMPT_TASK_FIELDS)
    )
    if not valid_task:
        raise UnattendedContextError(
            "TASK_FIXTURE_MISMATCH",
            "taskbed row does not match the release-bound task fixture",
        )
    oracle_payload = {field: task[field] for field in fixture["task_sha256_fields"]}
    oracle_sha256 = canonical_sha256(oracle_payload)
    if oracle_sha256 != provenance.get("task_sha256"):
        raise UnattendedContextError(
            "TASK_ORACLE_DIGEST_MISMATCH",
            "task payload no longer reproduces its sealed oracle digest",
        )
    task_payload_digest = content_digest(task)
    if task_payload_digest != fixture["task_payload_digest"]:
        raise UnattendedContextError(
            "TASK_PAYLOAD_DIGEST_MISMATCH",
            "stored task payload differs from the release fixture",
        )
    judge_binding = admitted_judge_binding(task_id)
    prompt_task = {field: task[field] for field in PROMPT_TASK_FIELDS}
    prompt_task_sha256 = canonical_sha256(prompt_task)
    task_fail_to_pass = task.get("FAIL_TO_PASS")
    if isinstance(task_fail_to_pass, str):
        try:
            task_fail_to_pass = json.loads(task_fail_to_pass)
        except json.JSONDecodeError as exc:
            raise UnattendedContextError(
                "TASK_TEST_LIST_INVALID",
                "task FAIL_TO_PASS is not a canonical list",
            ) from exc
    judge_row = judge_binding["rows"][task_id]
    if (
        not isinstance(task_fail_to_pass, list)
        or canonical_sha256(task_fail_to_pass) != judge_row["fail_to_pass_sha256"]
    ):
        raise UnattendedContextError(
            "TASK_JUDGE_CROSSLINK_MISMATCH",
            "task and judge FAIL_TO_PASS evidence disagree",
        )
    _inspect_image(fixture)
    context = {
        path: _read_context_file(fixture["image_id"], path)
        for path in map(_safe_target_path, fixture["target_paths"])
    }
    binding = {
        "schema": CONTEXT_BINDING_SCHEMA,
        "task_id": task_id,
        "task_sha256": fixture["task_sha256"],
        "task_payload_digest": task_payload_digest,
        "prompt_task_sha256": prompt_task_sha256,
        "judge_dataset": judge_binding,
        "image_reference": fixture["image_reference"],
        "image_id": fixture["image_id"],
        "repo_digest": fixture["repo_digest"],
        "os": fixture["os"],
        "architecture": fixture["architecture"],
        "target_paths": list(fixture["target_paths"]),
        "context_digests": {
            path: "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
            for path, value in context.items()
        },
        "pull_allowed": False,
        "container_network_disabled": True,
        "judge_row_loaded_for_digest": True,
        "judge_row_exposed_to_model": False,
        "gold_patch_exposed_to_model": False,
    }
    binding["binding_digest"] = content_digest(binding)
    return prompt_task, context, binding


__all__ = [
    "ADMITTED_TASK_IMAGES",
    "CONTEXT_BINDING_SCHEMA",
    "JUDGE_BINDING_SCHEMA",
    "UnattendedContextError",
    "admitted_judge_binding",
    "admitted_task_image",
    "load_admitted_judge_dataset",
    "load_admitted_task_context",
    "sanitize_unattended_docker_env",
    "validate_admitted_judge_instance",
]
