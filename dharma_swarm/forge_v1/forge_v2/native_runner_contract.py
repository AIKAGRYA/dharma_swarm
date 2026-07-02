"""Native/x86_64 grading runner contract for RSI Lab Workstream 6.

This module is deliberately a *contract layer*, not a remote executor.  It lets a
local Mac orchestrator produce a sealed request packet for a native/x86_64 worker
and safely ingest worker receipts later without letting the worker mutate any
source of truth.

Workstream 6 objective mapping:

* input: candidate packet + task allocation -> ``write_native_runner_request``;
* output: grade receipts -> ``sync_remote_receipts``;
* no source-of-truth mutation -> manifest/receipt validation fails closed;
* prewarm repos/images/caches -> ``build_prewarm_manifest``;
* resume/retry -> ``plan_resume`` skips completed receipts, retries infra
  failures, and quarantines exhausted/flaky tasks.

Promotion remains owned by ``verify_promotion``.  A synced native receipt is
shadow evidence only until normal packet guard + promotion gates consume it.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.daemon_config import dharma_state_dir

from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.native_runner_contract.v1"
REQUEST_SCHEMA = f"{SCHEMA_VERSION}.request"
PREWARM_SCHEMA = f"{SCHEMA_VERSION}.prewarm"
RESUME_SCHEMA = f"{SCHEMA_VERSION}.resume_plan"
SYNC_SCHEMA = f"{SCHEMA_VERSION}.sync_manifest"

DEFAULT_RUN_ROOT = dharma_state_dir() / "forge_v1" / "native_runner"
DEFAULT_SYNC_ROOT = DEFAULT_RUN_ROOT / "synced_receipts"
PROMOTION_GATE = "verify_promotion_only"

# Worker task-result statuses.  The exact resolver may still use project-local
# closeouts, but the contract needs a small common vocabulary for resume/retry.
COMPLETED_STATUSES = frozenset({"resolved", "unresolved", "passed", "failed", "done"})
INFRA_RETRYABLE_STATUSES = frozenset(
    {"infra_failed", "timeout", "worker_lost", "dependency_failed", "docker_failed"}
)
QUARANTINE_STATUSES = frozenset({"flaky", "flaky_quarantined", "quarantined"})


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normal_task_id(row: dict[str, Any]) -> str:
    return str(row.get("task_id") or row.get("instance_id") or "").strip()


def _task_ids_from_allocation(task_allocation: dict[str, Any]) -> list[str]:
    task_ids = [str(item).strip() for item in task_allocation.get("task_ids", []) if str(item).strip()]
    if not task_ids:
        raise ValueError("task_allocation must include non-empty task_ids")
    return task_ids


def repo_slug_from_task_id(task_id: str) -> str | None:
    """Return ``owner/repo`` for PR-suite ids like ``pr::pallets/click#3208``."""
    text = str(task_id or "")
    if not text.startswith("pr::") or "#" not in text:
        return None
    slug = text[len("pr::") :].split("#", 1)[0].strip()
    return slug or None


def build_prewarm_manifest(
    task_ids: Iterable[str],
    *,
    repos: Iterable[str] = (),
    docker_images: Iterable[str] = (),
    dependency_cache_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a deterministic prewarm manifest for a remote/native worker.

    Repos are inferred from PR-suite task ids and unioned with explicit repos.
    Docker images are explicit because exact SWE-bench image names are produced by
    the harness/test spec; the contract records the image namespace expectation
    without guessing per-task image names.
    """
    task_ids = [str(task_id).strip() for task_id in task_ids if str(task_id).strip()]
    inferred_repos = [repo for task_id in task_ids for repo in [repo_slug_from_task_id(task_id)] if repo]
    return {
        "schema": PREWARM_SCHEMA,
        "generated_at": utc_now(),
        "task_count": len(task_ids),
        "task_ids": task_ids,
        "repos": sorted(set([*inferred_repos, *(str(repo).strip() for repo in repos if str(repo).strip())])),
        "docker_namespace": "swebench",
        "docker_images": sorted(set(str(image).strip() for image in docker_images if str(image).strip())),
        "dependency_cache_keys": sorted(
            set(str(key).strip() for key in dependency_cache_keys if str(key).strip())
        ),
    }


def write_native_runner_request(
    *,
    run_id: str,
    candidate_packet: dict[str, Any],
    task_allocation: dict[str, Any],
    output_root: Path | str,
    split: str,
    budget: dict[str, Any] | None = None,
    runner_label: str = "native_x86_64",
    max_infra_retries: int = 2,
    prewarm: dict[str, Any] | None = None,
    sync_back_target: Path | str | None = None,
) -> dict[str, Any]:
    """Write a native runner request packet and return its manifest.

    The packet is intentionally authority-limited: a remote worker may grade and
    emit receipts only.  It cannot mutate live source, write archive fitness, or
    claim promotion.
    """
    run_id = str(run_id).strip()
    if not run_id:
        raise ValueError("run_id is required")
    if split not in {"explore", "confirm"}:
        raise ValueError("split must be explore or confirm")
    if max_infra_retries < 0:
        raise ValueError("max_infra_retries must be non-negative")
    if not isinstance(candidate_packet, dict) or not candidate_packet:
        raise ValueError("candidate_packet must be a non-empty dict")
    task_ids = _task_ids_from_allocation(task_allocation)

    root = Path(output_root).expanduser() / run_id
    candidate_id = str(
        candidate_packet.get("candidate_id")
        or candidate_packet.get("id")
        or task_allocation.get("candidate_id")
        or run_id
    )
    prewarm_manifest = prewarm or build_prewarm_manifest(task_ids)
    request = {
        "schema": REQUEST_SCHEMA,
        "generated_at": utc_now(),
        "run_id": run_id,
        "runner_label": runner_label,
        "candidate_id": candidate_id,
        "split": split,
        "candidate_packet": dict(candidate_packet),
        "task_allocation": dict(task_allocation),
        "task_ids": task_ids,
        "budget": dict(budget or {}),
        "max_infra_retries": int(max_infra_retries),
        "prewarm_manifest": prewarm_manifest,
        "sync_back_target": str(sync_back_target or (DEFAULT_SYNC_ROOT / run_id)),
        "authority": {
            "no_source_of_truth_mutation": True,
            "source_of_truth_mutation_allowed": False,
            "live_apply_allowed": False,
            "archive_fitness_mutated": False,
            "official_score_claimed": False,
            "promotion_gate": PROMOTION_GATE,
        },
        "worker_outputs_required": [
            "result_manifest.json",
            "task_receipts/*.json",
        ],
    }
    request["request_sha256"] = canonical_sha256(request)

    task_rows = [
        {
            "schema": f"{SCHEMA_VERSION}.task_row",
            "run_id": run_id,
            "candidate_id": candidate_id,
            "split": split,
            "task_id": task_id,
            "status": "pending_native_grade",
        }
        for task_id in task_ids
    ]
    _write_json(root / "native_runner_request.json", request)
    _write_json(root / "prewarm_manifest.json", prewarm_manifest)
    _write_jsonl(root / "tasks.jsonl", task_rows)
    (root / "README.md").write_text(
        "# Forge v2 native runner request\n\n"
        "This packet grants grade-only authority. Return result_manifest.json "
        "and task_receipts/*.json; do not mutate source, archive fitness, or "
        "promotion state.\n",
        encoding="utf-8",
    )
    return {
        "schema": f"{SCHEMA_VERSION}.request_write",
        "run_id": run_id,
        "request_dir": str(root),
        "request_path": str(root / "native_runner_request.json"),
        "task_rows": len(task_rows),
        "prewarm_repos": prewarm_manifest.get("repos", []),
        "request_sha256": request["request_sha256"],
    }


def _receipt_status(receipt: dict[str, Any]) -> str:
    return str(receipt.get("status") or receipt.get("closeout") or receipt.get("result") or "").strip()


# Truthy tokens a remote/native worker might use to *assert* it did something
# forbidden.  The mutation guard is a fail-closed boundary against an untrusted
# worker, so it must treat these JSON-y encodings as an assertion, not only the
# exact Python ``True`` object.
_ASSERTED_TRUE_STRINGS = frozenset({"true", "1", "yes", "y", "on"})


def _asserts_true(value: Any) -> bool:
    """Return True iff ``value`` positively asserts a forbidden action.

    Absent/None/falsey values are allowed (absence of a claim is fine); any
    recognizable positive assertion — bool ``True``, a truthy int, or a truthy
    string like ``"true"``/``"1"``/``"yes"`` — fails closed.  This makes the
    guard robust to real JSON receipts, where booleans routinely arrive as
    strings or ints, instead of only catching the exact Python ``True``.
    """
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _ASSERTED_TRUE_STRINGS
    if isinstance(value, (int, float)):
        return value != 0
    return False


def plan_resume(
    request: dict[str, Any],
    task_receipts: Iterable[dict[str, Any]],
    *,
    max_infra_retries: int | None = None,
) -> dict[str, Any]:
    """Return a deterministic resume/retry plan for a native runner request."""
    task_ids = [str(task_id) for task_id in request.get("task_ids", []) if str(task_id).strip()]
    if not task_ids:
        raise ValueError("request must include task_ids")
    retry_budget = int(max_infra_retries if max_infra_retries is not None else request.get("max_infra_retries", 2))
    receipts_by_task: dict[str, list[dict[str, Any]]] = {task_id: [] for task_id in task_ids}
    for receipt in task_receipts:
        if not isinstance(receipt, dict):
            continue
        task_id = _normal_task_id(receipt)
        if task_id in receipts_by_task:
            receipts_by_task[task_id].append(dict(receipt))

    completed: list[str] = []
    remaining: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for task_id in task_ids:
        receipts = receipts_by_task[task_id]
        statuses = [_receipt_status(receipt) for receipt in receipts]
        if any(status in COMPLETED_STATUSES for status in statuses):
            completed.append(task_id)
            continue
        if any(status in QUARANTINE_STATUSES for status in statuses):
            quarantined.append({"task_id": task_id, "reason": "worker_quarantined_or_flaky", "statuses": statuses})
            continue
        infra_failures = sum(1 for status in statuses if status in INFRA_RETRYABLE_STATUSES)
        # Count EVERY prior non-terminal attempt toward the budget, not only the
        # infra-classified ones.  Otherwise a task whose receipts carry a status
        # outside the three modeled vocabularies (e.g. a worker "error", or a
        # real forge closeout like measured_negative) is returned as fresh
        # forever and resume never converges.  Convergence is required by the
        # Workstream 6 "resume without redoing completed grades / quarantine
        # flaky tasks" done-when.
        prior_attempts = len(statuses)
        if prior_attempts > retry_budget:
            if infra_failures > retry_budget:
                quarantined.append(
                    {
                        "task_id": task_id,
                        "reason": "infra_retry_budget_exhausted",
                        "infra_failures": infra_failures,
                        "max_infra_retries": retry_budget,
                    }
                )
            else:
                quarantined.append(
                    {
                        "task_id": task_id,
                        "reason": "attempts_exhausted",
                        "attempts": prior_attempts,
                        "infra_failures": infra_failures,
                        "statuses": statuses,
                        "max_infra_retries": retry_budget,
                    }
                )
            continue
        remaining.append(
            {
                "task_id": task_id,
                "next_attempt": prior_attempts + 1,
                "prior_infra_failures": infra_failures,
            }
        )

    return {
        "schema": RESUME_SCHEMA,
        "generated_at": utc_now(),
        "run_id": request.get("run_id", ""),
        "candidate_id": request.get("candidate_id", ""),
        "task_count": len(task_ids),
        "completed_task_ids": completed,
        "remaining_tasks": remaining,
        "quarantined_tasks": quarantined,
        "skip_completed_grades": True,
        "retry_infra_failures": True,
        "no_source_of_truth_mutation": True,
        "promotion_gate": PROMOTION_GATE,
    }


def _task_receipt_paths(remote_result_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for subdir in ("task_receipts", "receipts"):
        base = remote_result_root / subdir
        if base.exists():
            candidates.extend(sorted(path for path in base.glob("*.json") if path.is_file()))
    return candidates


def load_task_receipts(remote_result_root: Path | str) -> list[dict[str, Any]]:
    root = Path(remote_result_root).expanduser()
    receipts: list[dict[str, Any]] = []
    for path in _task_receipt_paths(root):
        receipt = _read_json(path)
        receipt.setdefault("_source_path", str(path))
        receipts.append(receipt)
    return receipts


def validate_no_source_mutation(payload: dict[str, Any], *, label: str) -> None:
    """Fail closed if a remote/native result claims any source-of-truth mutation."""
    if _asserts_true(payload.get("source_of_truth_mutated")):
        raise ValueError(f"{label}:source_of_truth_mutated")
    if _asserts_true(payload.get("live_apply_performed")):
        raise ValueError(f"{label}:live_apply_performed")
    if _asserts_true(payload.get("archive_fitness_mutated")):
        raise ValueError(f"{label}:archive_fitness_mutated")
    if payload.get("promotion_decision") in {"accepted", "promoted", "live_apply"}:
        raise ValueError(f"{label}:remote_promotion_decision_forbidden")
    gate = payload.get("promotion_gate")
    if gate not in (None, "", PROMOTION_GATE):
        raise ValueError(f"{label}:unexpected_promotion_gate:{gate}")


def sync_remote_receipts(
    *,
    remote_result_root: Path | str,
    local_sync_root: Path | str = DEFAULT_SYNC_ROOT,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    """Validate and sync remote/native task receipts into a local receipt mirror."""
    remote_root = Path(remote_result_root).expanduser()
    manifest_path = remote_root / "result_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing result manifest: {manifest_path}")
    manifest = _read_json(manifest_path)
    validate_no_source_mutation(manifest, label="result_manifest")
    run_id = str(manifest.get("run_id") or expected_run_id or remote_root.name)
    if expected_run_id and run_id != expected_run_id:
        raise ValueError(f"run_id_mismatch: expected={expected_run_id} actual={run_id}")

    receipts = load_task_receipts(remote_root)
    if not receipts:
        raise ValueError("no_task_receipts_to_sync")
    for receipt in receipts:
        validate_no_source_mutation(receipt, label=f"task_receipt:{_normal_task_id(receipt) or 'unknown'}")
        if not _normal_task_id(receipt):
            raise ValueError("task_receipt_missing_task_id")

    sync_dir = Path(local_sync_root).expanduser() / run_id
    receipt_dir = sync_dir / "task_receipts"
    written: list[str] = []
    for receipt in receipts:
        canonical = {k: v for k, v in receipt.items() if k != "_source_path"}
        digest = canonical_sha256(canonical)[:16]
        task_id = _normal_task_id(canonical).replace("/", "_").replace(":", "_")
        out = receipt_dir / f"{task_id}_{digest}.json"
        _write_json(out, canonical)
        written.append(str(out))

    sync_manifest = {
        "schema": SYNC_SCHEMA,
        "synced_at": utc_now(),
        "run_id": run_id,
        "remote_result_root": str(remote_root),
        "local_sync_dir": str(sync_dir),
        "receipt_count": len(written),
        "synced_receipts": written,
        "source_of_truth_mutated": False,
        "live_apply_performed": False,
        "promotion_gate": PROMOTION_GATE,
        "result_manifest_sha256": canonical_sha256(manifest),
    }
    sync_manifest["sync_sha256"] = canonical_sha256(sync_manifest)
    _write_json(sync_dir / "sync_manifest.json", sync_manifest)
    return sync_manifest


__all__ = [
    "COMPLETED_STATUSES",
    "DEFAULT_RUN_ROOT",
    "DEFAULT_SYNC_ROOT",
    "INFRA_RETRYABLE_STATUSES",
    "PROMOTION_GATE",
    "QUARANTINE_STATUSES",
    "REQUEST_SCHEMA",
    "RESUME_SCHEMA",
    "SCHEMA_VERSION",
    "SYNC_SCHEMA",
    "build_prewarm_manifest",
    "load_task_receipts",
    "plan_resume",
    "repo_slug_from_task_id",
    "sync_remote_receipts",
    "validate_no_source_mutation",
    "write_native_runner_request",
]
