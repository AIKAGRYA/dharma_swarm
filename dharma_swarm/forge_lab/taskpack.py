"""Content-addressed, receipted admission of official SWE-bench tasks.

This module never edits SQLite directly.  It validates a sealed taskpack and
delegates registration to the canonical Forge taskbed ledger API.  Gold patches
and test patches are deliberately excluded from candidate-visible taskpacks.
"""

from __future__ import annotations

import json
import fcntl
import os
import re
import stat
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.forge_lab.state_io import (
    content_digest,
    atomic_json,
    _fsync_directory,
    dharma_home,
    safe_json,
    validate_digest,
    validate_safe_id,
    write_json_exclusive,
)

TASKPACK_SCHEMA = "rsi_lab.official_swebench_taskpack.v1"
IMPORT_RECEIPT_SCHEMA = "rsi_lab.taskpack_import_receipt.v1"
DEFAULT_INSTANCE_IDS = ("django__django-12209",)
ALLOWED_PROFILES = frozenset({"offline", "django-control", "official-django-12209"})
FORBIDDEN_GOLD_FIELDS = frozenset({"patch", "test_patch", "gold_patch", "solution_patch"})
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_INSTANCE_RE = re.compile(r"^[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-[0-9]+$")
_IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REPO_DIGEST_RE = re.compile(r"^swebench/sweb\.eval\.[^@]+@sha256:[0-9a-f]{64}$")


class TaskpackError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@contextmanager
def _import_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise TaskpackError("TASKPACK_IMPORT_LOCK_UNSAFE", str(path)) from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise TaskpackError("TASKPACK_IMPORT_LOCK_UNSAFE", str(path))
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _fsync_directory(path.parent)
        yield
    finally:
        os.close(descriptor)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def taskpack_root() -> Path:
    return dharma_home() / "forge_lab" / "taskpacks"


def _read_source(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise TaskpackError("SOURCE_MANIFEST_UNSAFE", str(path))
    if path.stat().st_size > 16 * 1024 * 1024:
        raise TaskpackError("SOURCE_MANIFEST_TOO_LARGE", str(path))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaskpackError("SOURCE_MANIFEST_INVALID", str(path)) from exc
    if isinstance(payload, dict):
        payload = payload.get("tasks") or payload.get("instances")
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise TaskpackError("SOURCE_MANIFEST_INVALID", "expected a task list")
    return [dict(row) for row in payload]


def _load_official_instances(instance_ids: list[str]) -> list[dict[str, Any]]:
    try:
        from dharma_swarm.forge_v1.swebench_real import verified_instances

        rows = verified_instances(instance_ids=instance_ids)
    except Exception as exc:
        raise TaskpackError(
            "OFFICIAL_DATASET_UNAVAILABLE",
            f"official SWE-bench Verified loader failed: {type(exc).__name__}",
        ) from exc
    return [dict(row) for row in rows]


def _list_field(row: dict[str, Any], *names: str) -> list[str]:
    for name in names:
        value = row.get(name)
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def _image_key(row: dict[str, Any]) -> str:
    explicit = str(row.get("image_key") or row.get("docker_image") or "").strip()
    if explicit:
        return explicit
    try:
        from dharma_swarm.forge_v1.swebench_real import instance_image_key

        return str(instance_image_key(row))
    except Exception as exc:
        raise TaskpackError("OFFICIAL_IMAGE_ID_UNAVAILABLE", type(exc).__name__) from exc


def official_source_row_digest(row: dict[str, Any]) -> str:
    """Pin the selected official row without exposing gold patch contents."""

    return content_digest(
        {
            "dataset": "princeton-nlp/SWE-bench_Verified",
            "split": "test",
            "instance_id": str(row.get("instance_id") or ""),
            "repo": str(row.get("repo") or ""),
            "base_commit": str(row.get("base_commit") or ""),
            "image_key": _image_key(row),
            "patch_digest": content_digest(str(row.get("patch") or "")),
            "test_patch_digest": content_digest(str(row.get("test_patch") or "")),
            "fail_to_pass": _list_field(row, "FAIL_TO_PASS", "fail_to_pass"),
            "pass_to_pass": _list_field(row, "PASS_TO_PASS", "pass_to_pass"),
        }
    )


def _inspect_local_image(image_key: str) -> dict[str, Any]:
    """Read immutable local Docker identity without pulling or running an image."""

    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image_key],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise TaskpackError("OFFICIAL_IMAGE_NOT_LOCAL", type(exc).__name__) from exc
    if result.returncode != 0:
        raise TaskpackError("OFFICIAL_IMAGE_NOT_LOCAL", image_key)
    try:
        rows = json.loads(result.stdout)
        row = rows[0]
        image_id = str(row["Id"])
        repo_digests = sorted(str(value) for value in row.get("RepoDigests") or [])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise TaskpackError("OFFICIAL_IMAGE_INSPECT_INVALID", image_key) from exc
    if not _IMAGE_ID_RE.fullmatch(image_id) or not repo_digests:
        raise TaskpackError("OFFICIAL_IMAGE_ID_INVALID", image_key)
    if not all(_REPO_DIGEST_RE.fullmatch(value) for value in repo_digests):
        raise TaskpackError("OFFICIAL_IMAGE_REPODIGEST_INVALID", image_key)
    requested_repository = image_key.rsplit(":", 1)[0] if ":" in image_key.rsplit("/", 1)[-1] else image_key
    if requested_repository not in {value.split("@", 1)[0] for value in repo_digests}:
        raise TaskpackError("OFFICIAL_IMAGE_REPODIGEST_MISMATCH", image_key)
    return {"local_image_id": image_id, "local_image_repo_digests": repo_digests}


def _revalidate_official_content(content: dict[str, Any]) -> str:
    """Re-derive every eligible row from the official loader and local image."""

    tasks = content.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise TaskpackError("TASKPACK_EMPTY", "official revalidation")
    instance_ids = [str(task.get("instance_id") or "") for task in tasks]
    official_rows = _load_official_instances(instance_ids)
    by_id = {str(row.get("instance_id") or ""): row for row in official_rows}
    if set(by_id) != set(instance_ids):
        raise TaskpackError("OFFICIAL_DATASET_SELECTION_MISMATCH", ",".join(instance_ids))
    expected_tasks: list[dict[str, Any]] = []
    for instance_id in instance_ids:
        row = by_id[instance_id]
        enriched = {**row, "official_source_row_digest": official_source_row_digest(row)}
        expected_tasks.append(
            _normalize_task(enriched, official_eligible=True, inspect_images=True)
        )
    expected_tasks.sort(key=lambda row: row["instance_id"])
    if expected_tasks != tasks:
        raise TaskpackError("OFFICIAL_DATASET_CONTENT_MISMATCH", ",".join(instance_ids))
    return content_digest(
        {
            "authority": "official_dataset_loader_plus_local_docker_identity.v1",
            "dataset": content.get("dataset"),
            "split": content.get("split"),
            "task_digests": [task["task_digest"] for task in expected_tasks],
            "official_selection_digest": content.get("official_selection_digest"),
        }
    )


def _normalize_task(
    row: dict[str, Any],
    *,
    official_eligible: bool,
    inspect_images: bool,
) -> dict[str, Any]:
    instance_id = str(row.get("instance_id") or row.get("task_id") or "").strip()
    repo = str(row.get("repo") or row.get("repository") or "").strip()
    base_commit = str(row.get("base_commit") or "").strip()
    problem = str(row.get("problem_statement") or "").strip()
    fail_to_pass = _list_field(row, "FAIL_TO_PASS", "fail_to_pass")
    pass_to_pass = _list_field(row, "PASS_TO_PASS", "pass_to_pass")
    image_key = _image_key(row)
    missing = [
        name
        for name, value in (
            ("instance_id", instance_id),
            ("repo", repo),
            ("base_commit", base_commit),
            ("problem_statement", problem),
            ("FAIL_TO_PASS", fail_to_pass),
            ("image_key", image_key),
        )
        if not value
    ]
    if missing:
        raise TaskpackError("TASK_FIELDS_MISSING", f"{instance_id or 'unknown'}:{','.join(missing)}")
    if instance_id.startswith("pr::"):
        raise TaskpackError("TASK_NOT_OFFICIAL_SWEBENCH", instance_id)
    if not _INSTANCE_RE.fullmatch(instance_id):
        raise TaskpackError("TASK_INSTANCE_ID_INVALID", instance_id)
    if not image_key.startswith("swebench/sweb.eval."):
        raise TaskpackError("TASK_IMAGE_NOT_OFFICIAL", image_key)
    if not _COMMIT_RE.fullmatch(base_commit):
        raise TaskpackError("TASK_BASE_COMMIT_INVALID", instance_id)
    image_attestation: dict[str, Any] = {}
    if official_eligible:
        image_attestation = (
            _inspect_local_image(image_key)
            if inspect_images
            else {
                "local_image_id": row.get("local_image_id"),
                "local_image_repo_digests": row.get("local_image_repo_digests"),
            }
        )
        if (
            not _IMAGE_ID_RE.fullmatch(str(image_attestation.get("local_image_id") or ""))
            or not isinstance(image_attestation.get("local_image_repo_digests"), list)
            or not image_attestation["local_image_repo_digests"]
            or not all(
                _REPO_DIGEST_RE.fullmatch(str(value))
                for value in image_attestation["local_image_repo_digests"]
            )
        ):
            raise TaskpackError("TASK_IMAGE_ATTESTATION_INVALID", instance_id)
        source_row_digest = str(row.get("official_source_row_digest") or "")
        try:
            validate_digest(source_row_digest)
        except ValueError as exc:
            raise TaskpackError("TASK_OFFICIAL_SOURCE_DIGEST_INVALID", instance_id) from exc
        image_attestation["official_source_row_digest"] = source_row_digest
    task = {
        "instance_id": instance_id,
        "task_id": instance_id,
        "repo": repo,
        "base_commit": base_commit,
        "problem_statement": problem,
        "FAIL_TO_PASS": fail_to_pass,
        "PASS_TO_PASS": pass_to_pass,
        "image_key": image_key,
        "dataset": "princeton-nlp/SWE-bench_Verified",
        "split": "test",
        "source_kind": (
            "official_swebench_verified" if official_eligible else "fixture_noneligible"
        ),
        "official_eligible": official_eligible,
        "official_harness_required": True,
        "candidate_network_disabled": True,
        **image_attestation,
    }
    if FORBIDDEN_GOLD_FIELDS.intersection(task):  # pragma: no cover - construction invariant
        raise TaskpackError("TASKPACK_GOLD_LEAK", instance_id)
    task["task_digest"] = content_digest(task)
    return task


def _pack_content(
    profile: str,
    tasks: Iterable[dict[str, Any]],
    *,
    official_eligible: bool,
    source_mode: str,
    inspect_images: bool,
) -> dict[str, Any]:
    rows = sorted(
        (
            _normalize_task(
                dict(row),
                official_eligible=official_eligible,
                inspect_images=inspect_images,
            )
            for row in tasks
        ),
        key=lambda row: row["instance_id"],
    )
    if not rows:
        raise TaskpackError("TASKPACK_EMPTY", profile)
    ids = [row["instance_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise TaskpackError("TASKPACK_DUPLICATE_ID", ",".join(ids))
    content = {
        "schema": TASKPACK_SCHEMA,
        "profile": profile,
        "dataset": "princeton-nlp/SWE-bench_Verified",
        "split": "test",
        "candidate_view_excludes_gold": True,
        "official_docker_harness_required": True,
        "official_eligible": official_eligible,
        "source_mode": source_mode,
        "tasks": rows,
    }
    if official_eligible:
        content["official_selection_digest"] = content_digest(
            {
                "dataset": content["dataset"],
                "split": content["split"],
                "row_digests": [row["official_source_row_digest"] for row in rows],
            }
        )
        content["dataset_revision_policy"] = "selected_official_rows_content_addressed.v1"
    return content


def _validate_manifest(payload: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    content = payload.get("content")
    if not isinstance(content, dict) or content.get("schema") != TASKPACK_SCHEMA:
        raise TaskpackError("TASKPACK_SCHEMA", str(path or "payload"))
    expected = content_digest(content)
    if payload.get("taskpack_digest") != expected:
        raise TaskpackError("TASKPACK_DIGEST", str(path or "payload"))
    if path is not None and payload.get("manifest_path") != str(path):
        raise TaskpackError("TASKPACK_PATH_BINDING", str(path))
    official_eligible = content.get("official_eligible") is True
    source_mode = str(content.get("source_mode") or "")
    if official_eligible != (source_mode == "official_dataset_loader"):
        raise TaskpackError("TASKPACK_ELIGIBILITY_BINDING", str(path or "payload"))
    rebuilt = _pack_content(
        str(content.get("profile") or ""),
        content.get("tasks") or [],
        official_eligible=official_eligible,
        source_mode=source_mode,
        inspect_images=False,
    )
    if rebuilt != content:
        raise TaskpackError("TASKPACK_CONTENT_INVALID", str(path or "payload"))
    return payload


def build_taskpack(
    *,
    profile: str,
    source_manifest: Path | None = None,
    instance_ids: list[str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    profile = str(profile).strip().lower()
    if profile not in ALLOWED_PROFILES:
        raise TaskpackError("TASKPACK_PROFILE", profile)
    requested = [str(item).strip() for item in (instance_ids or DEFAULT_INSTANCE_IDS) if str(item).strip()]
    if not requested or len(set(requested)) != len(requested):
        raise TaskpackError("TASKPACK_INSTANCE_IDS", "instance IDs must be non-empty and unique")
    source_rows = _read_source(source_manifest) if source_manifest else _load_official_instances(requested)
    if source_manifest is None:
        source_rows = [
            {**row, "official_source_row_digest": official_source_row_digest(row)}
            for row in source_rows
        ]
    by_id = {
        str(row.get("instance_id") or row.get("task_id") or "").strip(): row
        for row in source_rows
    }
    missing = sorted(set(requested) - set(by_id))
    if missing:
        raise TaskpackError("TASKPACK_INSTANCE_MISSING", ",".join(missing))
    official_eligible = source_manifest is None
    source_mode = "official_dataset_loader" if official_eligible else "fixture_manifest"
    content = _pack_content(
        profile,
        [by_id[instance_id] for instance_id in requested],
        official_eligible=official_eligible,
        source_mode=source_mode,
        inspect_images=official_eligible,
    )
    digest = content_digest(content)
    destination_root = (root or taskpack_root()).expanduser().resolve(strict=False)
    path = destination_root / digest.removeprefix("sha256:") / "manifest.json"
    existing = safe_json(path)
    if existing is not None:
        return _validate_manifest(existing, path=path)
    manifest = {
        "taskpack_digest": digest,
        "created_at": _now(),
        "manifest_path": str(path),
        "source_manifest": str(source_manifest) if source_manifest else "official_dataset_loader",
        "content": content,
    }
    try:
        write_json_exclusive(path, manifest)
    except FileExistsError:
        existing = safe_json(path)
        if existing is None:
            raise TaskpackError("TASKPACK_WRITE_RACE", str(path))
        return _validate_manifest(existing, path=path)
    return manifest


def load_taskpack(reference: str | Path, *, root: Path | None = None) -> dict[str, Any]:
    text = str(reference)
    if text.startswith("sha256:"):
        digest = validate_digest(text)
        path = (root or taskpack_root()) / digest.removeprefix("sha256:") / "manifest.json"
    else:
        path = Path(text).expanduser().resolve(strict=False)
    if path.is_symlink() or not path.is_file():
        raise TaskpackError("TASKPACK_MISSING_OR_UNSAFE", str(path))
    payload = safe_json(path)
    if payload is None:
        raise TaskpackError("TASKPACK_UNREADABLE", str(path))
    return _validate_manifest(payload, path=path)


def import_taskpack(
    reference: str | Path,
    *,
    request_id: str,
    apply: bool,
    db_path: Path | None = None,
    root: Path | None = None,
    require_anchored_db: bool = True,
) -> dict[str, Any]:
    request_id = validate_safe_id(request_id, field="request_id")
    manifest = load_taskpack(reference, root=root)
    digest = str(manifest["taskpack_digest"])
    canonical_manifest_path = (
        (root or taskpack_root()).expanduser().resolve(strict=False)
        / digest.removeprefix("sha256:")
        / "manifest.json"
    )
    if manifest.get("manifest_path") != str(canonical_manifest_path):
        raise TaskpackError("TASKPACK_NOT_CANONICAL_PATH", str(manifest.get("manifest_path")))
    if manifest["content"].get("official_eligible") is not True:
        raise TaskpackError(
            "TASKPACK_NOT_OFFICIAL_ELIGIBLE",
            "fixture manifests can exercise validation but cannot enter the taskbed",
        )
    official_revalidation_digest = _revalidate_official_content(manifest["content"])
    target_db = (db_path or (dharma_home() / "forge_v1" / "taskbed.db")).expanduser().resolve(strict=False)
    expected_db = (dharma_home() / "forge_v1" / "taskbed.db").resolve(strict=False)
    if require_anchored_db and target_db != expected_db:
        raise TaskpackError("TASKBED_NOT_STATE_ANCHORED", str(target_db))
    plan = {
        "schema": "rsi_lab.taskpack_import_plan.v1",
        "taskpack_digest": digest,
        "manifest_path": manifest["manifest_path"],
        "taskbed_db": str(target_db),
        "task_ids": [row["instance_id"] for row in manifest["content"]["tasks"]],
        "registration_api": "dharma_swarm.forge_v1.forge_v2.taskbed_ledger.register_task",
        "direct_sqlite_edits": False,
        "official_revalidation_digest": official_revalidation_digest,
    }
    plan["plan_digest"] = content_digest(plan)
    if not apply:
        return {"ok": True, "applied": False, "plan": plan, "taskpack": manifest}

    return _apply_taskpack_import(
        manifest=manifest,
        plan=plan,
        request_id=request_id,
        target_db=target_db,
        root=(root or taskpack_root()),
        official_revalidation_digest=official_revalidation_digest,
    )


def _registration_exact(
    stored: dict[str, Any] | None,
    *,
    intended_task: dict[str, Any],
    provenance: dict[str, Any],
) -> bool:
    return bool(
        stored
        and stored.get("task") == intended_task
        and stored.get("provenance") == provenance
        and stored.get("source") == "official_swebench_verified_taskpack"
        and stored.get("taskbed") == "official_swebench_verified_shadow"
        and stored.get("contamination_state") == "possible_pretrain"
        and type(stored.get("active")) is int
        and stored.get("active") == 1
        and type(stored.get("max_uses_per_epoch")) is int
        and stored.get("max_uses_per_epoch") == 1
    )


def _journal_payload(
    *,
    request_id: str,
    plan_digest: str,
    status: str,
    task_states: dict[str, str],
    path: Path,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "rsi_lab.taskpack_import_transaction.v1",
        "request_id": request_id,
        "plan_digest": plan_digest,
        "status": status,
        "task_states": task_states,
        "recovery_policy": "roll_forward_exact_rows; unreceipted rows remain doctor-ineligible",
        "transaction_path": str(path),
        "direct_sqlite_edits": False,
    }
    payload["transaction_digest"] = content_digest(payload)
    return payload


def _apply_taskpack_import(
    *,
    manifest: dict[str, Any],
    plan: dict[str, Any],
    request_id: str,
    target_db: Path,
    root: Path,
    official_revalidation_digest: str,
) -> dict[str, Any]:
    from dharma_swarm.forge_v1.forge_v2 import taskbed_ledger

    root = root.expanduser().resolve(strict=False)
    receipt_path = root / "import_receipts" / f"{request_id}.json"
    transaction_path = root / "import_transactions" / f"{request_id}.json"
    lock_path = root / "import.lock"
    digest = str(manifest["taskpack_digest"])
    with _import_lock(lock_path):
        registrations: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
        for task in manifest["content"]["tasks"]:
            instance_id = str(task["instance_id"])
            provenance = {
                "schema": "rsi_lab.taskpack_task_provenance.v1",
                "taskpack_digest": digest,
                "task_digest": task["task_digest"],
                "manifest_path": manifest["manifest_path"],
                "dataset": task["dataset"],
                "split": task["split"],
                "image_key": task["image_key"],
                "local_image_id": task["local_image_id"],
                "local_image_repo_digests": task["local_image_repo_digests"],
                "official_source_row_digest": task["official_source_row_digest"],
                "official_selection_digest": manifest["content"]["official_selection_digest"],
                "dataset_revision_policy": manifest["content"]["dataset_revision_policy"],
                "official_harness_required": True,
                "candidate_network_disabled": True,
                "import_request_id": request_id,
            }
            intended = {**task, "provenance": provenance, "sealed_provenance": provenance}
            registrations.append((task, provenance, intended))

        journal = safe_json(transaction_path)
        if journal is not None:
            unsigned = {key: value for key, value in journal.items() if key != "transaction_digest"}
            expected_task_ids = {
                str(task["instance_id"]) for task, _, _ in registrations
            }
            if (
                journal.get("transaction_digest") != content_digest(unsigned)
                or journal.get("plan_digest") != plan["plan_digest"]
                or journal.get("request_id") != request_id
                or not isinstance(journal.get("task_states"), dict)
                or set(journal.get("task_states") or {}) != expected_task_ids
                or any(
                    state not in {"pending", "registered"}
                    for state in (journal.get("task_states") or {}).values()
                )
                or journal.get("status") not in {"prepared", "registering", "committed"}
                or journal.get("transaction_path") != str(transaction_path)
                or journal.get("direct_sqlite_edits") is not False
            ):
                raise TaskpackError("TASKPACK_TRANSACTION_CONFLICT", request_id)
            task_states = dict(journal["task_states"])
        else:
            task_states = {str(task["instance_id"]): "pending" for task, _, _ in registrations}
            atomic_json(
                transaction_path,
                _journal_payload(
                    request_id=request_id,
                    plan_digest=plan["plan_digest"],
                    status="prepared",
                    task_states=task_states,
                    path=transaction_path,
                ),
            )

        def load_stored(instance_id: str) -> dict[str, Any] | None:
            try:
                return taskbed_ledger.task_for_id(instance_id, db_path=target_db)
            except taskbed_ledger.TaskbedLedgerError as exc:
                if "unknown_task_id" in str(exc):
                    return None
                raise TaskpackError("TASKBED_PREFLIGHT_FAILED", instance_id) from exc

        # Full preflight happens before any UPSERT. Exact rows from this same
        # transaction are safe crash-retry state; every other existing row is a
        # conflict and is never overwritten.
        existing_by_id: dict[str, dict[str, Any] | None] = {}
        for task, provenance, intended in registrations:
            instance_id = str(task["instance_id"])
            existing = load_stored(instance_id)
            if existing is not None and not _registration_exact(
                existing, intended_task=intended, provenance=provenance
            ):
                raise TaskpackError("TASKBED_EXISTING_TASK_CONFLICT", instance_id)
            existing_by_id[instance_id] = existing

        prior = safe_json(receipt_path)
        if prior is not None:
            unsigned = {key: value for key, value in prior.items() if key != "receipt_digest"}
            expected_ids = [str(task["instance_id"]) for task, _, _ in registrations]
            registered_rows = prior.get("registered")
            expected_registered = {
                str(task["instance_id"]): {
                    "task_digest": task["task_digest"],
                    "stored_task_digest": content_digest(intended),
                }
                for task, _, intended in registrations
            }
            if (
                prior.get("schema") != IMPORT_RECEIPT_SCHEMA
                or prior.get("request_id") != request_id
                or prior.get("taskpack_digest") != digest
                or prior.get("manifest_path") != manifest["manifest_path"]
                or prior.get("plan_digest") != plan["plan_digest"]
                or prior.get("receipt_digest") != content_digest(unsigned)
                or prior.get("official_revalidation_digest") != official_revalidation_digest
                or prior.get("taskbed_db") != str(target_db)
                or prior.get("receipt_path") != str(receipt_path)
                or prior.get("transaction_path") != str(transaction_path)
                or prior.get("registration_api") != plan["registration_api"]
                or prior.get("direct_sqlite_edits") is not False
                or not isinstance(registered_rows, list)
                or [row.get("task_id") for row in registered_rows] != expected_ids
                or prior.get("registered_count") != len(expected_ids)
                or any(
                    not isinstance(row, dict)
                    or row.get("task_digest")
                    != expected_registered.get(str(row.get("task_id")), {}).get("task_digest")
                    or row.get("stored_task_digest")
                    != expected_registered.get(str(row.get("task_id")), {}).get(
                        "stored_task_digest"
                    )
                    or row.get("registration_state")
                    not in {"registered", "recovered_exact"}
                    for row in (registered_rows or [])
                )
                or any(existing_by_id[task_id] is None for task_id in expected_ids)
            ):
                raise TaskpackError("TASKPACK_REQUEST_CONFLICT", request_id)
            atomic_json(
                transaction_path,
                _journal_payload(
                    request_id=request_id,
                    plan_digest=plan["plan_digest"],
                    status="committed",
                    task_states={task_id: "registered" for task_id in expected_ids},
                    path=transaction_path,
                ),
            )
            return {"ok": True, "applied": True, "idempotent": True, "receipt": prior}

        registered: list[dict[str, Any]] = []
        for task, provenance, intended in registrations:
            instance_id = str(task["instance_id"])
            was_present = existing_by_id[instance_id] is not None
            if not was_present:
                # Recheck immediately before the canonical UPSERT while holding
                # the importer singleton. This prevents all supported importers
                # from racing a conflicting replacement.
                late = load_stored(instance_id)
                if late is not None:
                    if not _registration_exact(late, intended_task=intended, provenance=provenance):
                        raise TaskpackError("TASKBED_EXISTING_TASK_CONFLICT", instance_id)
                    was_present = True
                else:
                    taskbed_ledger.register_task(
                        intended,
                        db_path=target_db,
                        task_id=instance_id,
                        source="official_swebench_verified_taskpack",
                        taskbed="official_swebench_verified_shadow",
                        contamination_state="possible_pretrain",
                        provenance=provenance,
                        active=True,
                        max_uses_per_epoch=1,
                    )
            stored = load_stored(instance_id)
            if not _registration_exact(stored, intended_task=intended, provenance=provenance):
                raise TaskpackError("TASKBED_POSTCONDITION", instance_id)
            task_states[instance_id] = "registered"
            atomic_json(
                transaction_path,
                _journal_payload(
                    request_id=request_id,
                    plan_digest=plan["plan_digest"],
                    status="registering",
                    task_states=task_states,
                    path=transaction_path,
                ),
            )
            registered.append(
                {
                    "task_id": instance_id,
                    "task_digest": task["task_digest"],
                    "stored_task_digest": content_digest(stored["task"]),
                    "registration_state": "recovered_exact" if was_present else "registered",
                }
            )

        receipt: dict[str, Any] = {
            "schema": IMPORT_RECEIPT_SCHEMA,
            "at": _now(),
            "request_id": request_id,
            "taskpack_digest": digest,
            "manifest_path": manifest["manifest_path"],
            "plan_digest": plan["plan_digest"],
            "taskbed_db": str(target_db),
            "registered": registered,
            "registered_count": len(registered),
            "registration_api": plan["registration_api"],
            "direct_sqlite_edits": False,
            "official_revalidation_digest": official_revalidation_digest,
            "transaction_path": str(transaction_path),
            "receipt_path": str(receipt_path),
        }
        receipt["receipt_digest"] = content_digest(receipt)
        write_json_exclusive(receipt_path, receipt)
        atomic_json(
            transaction_path,
            _journal_payload(
                request_id=request_id,
                plan_digest=plan["plan_digest"],
                status="committed",
                task_states=task_states,
                path=transaction_path,
            ),
        )
        return {"ok": True, "applied": True, "idempotent": False, "receipt": receipt}


__all__ = [
    "ALLOWED_PROFILES",
    "DEFAULT_INSTANCE_IDS",
    "IMPORT_RECEIPT_SCHEMA",
    "TASKPACK_SCHEMA",
    "TaskpackError",
    "build_taskpack",
    "import_taskpack",
    "load_taskpack",
    "official_source_row_digest",
    "taskpack_root",
]
