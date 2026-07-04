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

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from dharma_swarm.daemon_config import dharma_state_dir

from . import taskbed_ledger
from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.native_runner_contract.v1"
REQUEST_SCHEMA = f"{SCHEMA_VERSION}.request"
PREWARM_SCHEMA = f"{SCHEMA_VERSION}.prewarm"
RESUME_SCHEMA = f"{SCHEMA_VERSION}.resume_plan"
SYNC_SCHEMA = f"{SCHEMA_VERSION}.sync_manifest"
TASK_RECEIPT_SCHEMA = f"{SCHEMA_VERSION}.task_receipt"
WORKER_RESULT_SCHEMA = f"{SCHEMA_VERSION}.worker_result_manifest"

DEFAULT_RUN_ROOT = dharma_state_dir() / "forge_v1" / "native_runner"
DEFAULT_SYNC_ROOT = DEFAULT_RUN_ROOT / "synced_receipts"
PROMOTION_GATE = "verify_promotion_only"
GradeFn = Callable[[dict[str, Any]], dict[str, Any]]

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


def _safe_task_fragment(task_id: str) -> str:
    text = str(task_id or "task").strip() or "task"
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)


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


def is_swebench_task_id(task_id: str) -> bool:
    """Best-effort check for standard SWE-bench ids like ``django__django-12209``."""
    text = str(task_id or "").strip()
    if text.startswith("pr::"):
        return False
    if "__" not in text or "-" not in text:
        return False
    repo_part, issue_part = text.rsplit("-", 1)
    return bool(repo_part and issue_part.isdigit())


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
    worker_config: dict[str, Any] | None = None,
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
        "worker_config": dict(worker_config or {}),
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
        try:
            receipt = _read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            # Fail closed against an untrusted/native worker.  This function is
            # the single ingestion point for both sync_remote_receipts and
            # worker-side resume, so an unparseable receipt file must raise a
            # controlled ValueError naming the offending file -- not crash the
            # local orchestrator with an uncontrolled exception type, and not be
            # silently skipped (which would let a worker hide evidence).
            raise ValueError(f"malformed_task_receipt_json:{path.name}:{exc}") from exc
        if not isinstance(receipt, dict):
            # A JSON array/scalar receipt is an integrity failure: every
            # legitimate producer writes an object.  Reject rather than let the
            # later ``receipt.get(...)`` / ``setdefault(...)`` calls raise
            # AttributeError deep inside sync/resume.
            raise ValueError(f"task_receipt_not_object:{path.name}")
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
    if _asserts_true(payload.get("official_score_claimed")):
        # Invariant #5 (no model self-report is evidence) + Workstream 7 ladder
        # (nothing is promotable/official before Level 3).  A native worker
        # receipt or result manifest that positively claims an official score is
        # exactly the self-report this boundary must reject, symmetric with the
        # official_score_claimed check already enforced on the request authority.
        raise ValueError(f"{label}:official_score_claimed")
    if payload.get("promotion_decision") in {"accepted", "promoted", "live_apply"}:
        raise ValueError(f"{label}:remote_promotion_decision_forbidden")
    gate = payload.get("promotion_gate")
    if gate not in (None, "", PROMOTION_GATE):
        raise ValueError(f"{label}:unexpected_promotion_gate:{gate}")


def validate_request_authority(request: dict[str, Any]) -> None:
    """Fail closed if a native request grants a worker source-of-truth authority."""
    if request.get("schema") != REQUEST_SCHEMA:
        raise ValueError(f"request:unexpected_schema:{request.get('schema')}")
    validate_no_source_mutation(request, label="request")
    authority = dict(request.get("authority") or {})
    if not _asserts_true(authority.get("no_source_of_truth_mutation")):
        raise ValueError("request_authority:no_source_of_truth_mutation_not_asserted")
    for field in (
        "source_of_truth_mutation_allowed",
        "live_apply_allowed",
        "archive_fitness_mutated",
        "official_score_claimed",
    ):
        if _asserts_true(authority.get(field)):
            raise ValueError(f"request_authority:{field}")
    if authority.get("promotion_gate") != PROMOTION_GATE:
        raise ValueError(f"request_authority:unexpected_promotion_gate:{authority.get('promotion_gate')}")


def prediction_for_task(candidate_packet: dict[str, Any], task_id: str, *, task_count: int = 1) -> str:
    """Extract the model patch/prediction for ``task_id`` from a candidate packet.

    Supported packet shapes are intentionally simple and deterministic:

    * ``task_predictions`` / ``predictions`` / ``patches`` mapping task_id -> patch;
    * a single global ``patch`` or ``model_patch`` only when the request has one
      task (avoids accidentally applying one task's patch to a multi-task run).
    """
    for field in ("task_predictions", "predictions", "patches"):
        mapping = candidate_packet.get(field)
        if isinstance(mapping, dict) and task_id in mapping:
            return str(mapping.get(task_id) or "")
    if task_count == 1:
        for field in ("patch", "model_patch"):
            if field in candidate_packet:
                return str(candidate_packet.get(field) or "")
    return ""


def _unresolved_grade(*, task_id: str, error: str, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": "unresolved",
        "resolved": False,
        "grade_error": error,
        "blockers": list(blockers or [error]),
        "grader": "native_contract_default",
        "grade_seconds": 0.0,
        "task_id": task_id,
    }


def default_native_grade(payload: dict[str, Any]) -> dict[str, Any]:
    """Default worker grade function for native requests.

    This bridges the contract harness to the existing PR-suite grader for current
    fresh taskbed rows.  It never trusts model self-report: it grades only the
    concrete patch extracted from the candidate packet.  Missing predictions are
    deterministic unresolved results, not infra failures, so they are not retried
    forever.  Unsupported task families fail closed as unresolved until a real
    SWE-bench worker integration is added.
    """
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return _unresolved_grade(task_id="", error="missing_task_id")
    request = dict(payload.get("request") or {})
    candidate_packet = dict(payload.get("candidate_packet") or request.get("candidate_packet") or {})
    task_count = len(request.get("task_ids") or [task_id])
    model_patch = prediction_for_task(candidate_packet, task_id, task_count=task_count)
    if not model_patch.strip():
        return _unresolved_grade(task_id=task_id, error="missing_task_prediction")

    worker_config = dict(request.get("worker_config") or {})
    taskbed_db = worker_config.get("taskbed_db") or taskbed_ledger.DEFAULT_DB
    timeout = int(worker_config.get("grade_timeout", 1800) or 1800)
    receipt_root = worker_config.get("receipt_root")
    work_root = worker_config.get("work_root")
    python = str(worker_config.get("python") or sys.executable)
    keep_workdir = bool(worker_config.get("keep_workdir", False))
    setup_command_template = str(worker_config.get("setup_command_template") or "")
    setup_timeout_seconds = worker_config.get("setup_timeout_seconds")
    setup_timeout = int(setup_timeout_seconds) if setup_timeout_seconds else None

    from . import pr_suite_grader

    if pr_suite_grader.is_pr_suite_task_id(task_id):
        instance = pr_suite_grader.task_row_for_id(task_id, db_path=taskbed_db)
        result = pr_suite_grader.grade_pr_suite_prediction(
            instance,
            model_patch,
            timeout=timeout,
            receipt_root=receipt_root or pr_suite_grader.DEFAULT_RECEIPT_ROOT,
            work_root=Path(work_root).expanduser() if work_root else None,
            python=python,
            keep_workdir=keep_workdir,
            setup_command_template=setup_command_template,
            setup_timeout_seconds=setup_timeout,
        )
        return {
            "status": "resolved" if result.resolved else "unresolved",
            "resolved": bool(result.resolved),
            "grade_seconds": float(result.seconds),
            "grade_error": result.error,
            "grader": "pr_suite",
            "grader_receipt_path": result.receipt_path,
            "grader_receipt_sha256": result.receipt_sha256,
            "patch_len": len(model_patch),
            "patch_sha256": canonical_sha256({"patch": model_patch}),
            "task_id": task_id,
        }

    if is_swebench_task_id(task_id):
        from dharma_swarm.forge_v1 import swebench_real

        task_instances = candidate_packet.get("task_instances")
        instance: dict[str, Any] | None = None
        if isinstance(task_instances, dict) and isinstance(task_instances.get(task_id), dict):
            instance = dict(task_instances[task_id])
        if instance is None:
            instances = swebench_real.verified_instances(instance_ids=[task_id])
            if not instances:
                return _unresolved_grade(task_id=task_id, error="swebench_instance_not_found")
            instance = dict(instances[0])
        instance.setdefault("instance_id", task_id)
        namespace_value = worker_config.get("swebench_namespace", swebench_real.DEFAULT_NAMESPACE)
        namespace = None if namespace_value in (None, "", "none", "None") else str(namespace_value)
        force_rebuild = bool(worker_config.get("swebench_force_rebuild", False))
        keep_logs = bool(worker_config.get("swebench_keep_logs", True))
        max_workers = int(worker_config.get("swebench_max_workers", 1) or 1)
        run_id = str(worker_config.get("swebench_run_id") or f"{request.get('run_id', 'native')}_{_safe_task_fragment(task_id)}")
        started = time.time()
        resolved = swebench_real.verify_prediction(
            instance,
            model_patch,
            namespace=namespace,
            timeout=timeout,
            force_rebuild=force_rebuild,
            run_id=run_id,
            keep_logs=keep_logs,
            max_workers=max_workers,
        )
        return {
            "status": "resolved" if resolved else "unresolved",
            "resolved": bool(resolved),
            "grade_seconds": round(time.time() - started, 1),
            "grade_error": None,
            "grader": "swebench",
            "swebench_run_id": run_id,
            "swebench_namespace": namespace,
            "patch_len": len(model_patch),
            "patch_sha256": canonical_sha256({"patch": model_patch}),
            "task_id": task_id,
        }

    return _unresolved_grade(task_id=task_id, error="unsupported_task_family")


def _task_receipt_path(receipt_dir: Path, task_id: str, receipt: dict[str, Any]) -> Path:
    digest = canonical_sha256(receipt)[:16]
    return receipt_dir / f"{_safe_task_fragment(task_id)}_{digest}.json"


def _worker_receipt(
    *,
    request: dict[str, Any],
    task_id: str,
    attempt: int,
    worker_label: str,
    grade_result: dict[str, Any],
) -> dict[str, Any]:
    status = str(grade_result.get("status") or "").strip()
    resolved_value = grade_result.get("resolved")
    if not status:
        if resolved_value is True:
            status = "resolved"
        elif resolved_value is False:
            status = "unresolved"
        else:
            status = "done"
    receipt = {
        **dict(grade_result),
        "schema": TASK_RECEIPT_SCHEMA,
        "generated_at": utc_now(),
        "run_id": request["run_id"],
        "candidate_id": request["candidate_id"],
        "task_id": task_id,
        "split": request["split"],
        "attempt": int(attempt),
        "worker_label": worker_label,
        "status": status,
        "source_of_truth_mutated": False,
        "live_apply_performed": False,
        "archive_fitness_mutated": False,
        "promotion_gate": PROMOTION_GATE,
        "request_sha256": request.get("request_sha256", canonical_sha256(request)),
        "candidate_packet_sha256": canonical_sha256(request.get("candidate_packet", {})),
    }
    validate_no_source_mutation(receipt, label=f"worker_receipt:{task_id}")
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def run_native_runner_request(
    *,
    request_dir: Path | str,
    grade_fn: GradeFn | None = None,
    result_root: Path | str | None = None,
    worker_label: str = "native_contract_worker",
) -> dict[str, Any]:
    """Consume a native runner request and write worker result receipts.

    This is still not a model runner or a Docker implementation; it is the
    worker-side contract harness.  A real native/x86_64 worker plugs in
    ``grade_fn`` to perform one task grade.  The harness owns authority checks,
    resume planning, receipt shape, and result-manifest production so workers
    cannot silently redo completed tasks or mutate source-of-truth state.
    """
    request_path = Path(request_dir).expanduser() / "native_runner_request.json"
    if not request_path.exists():
        raise FileNotFoundError(f"missing native runner request: {request_path}")
    request = _read_json(request_path)
    validate_request_authority(request)
    grade_fn = grade_fn or default_native_grade
    if not callable(grade_fn):
        raise ValueError("grade_fn must be callable")

    output_root = Path(result_root).expanduser() if result_root is not None else Path(request_dir).expanduser() / "worker_result"
    receipt_dir = output_root / "task_receipts"
    existing_receipts = load_task_receipts(output_root) if output_root.exists() else []
    for receipt in existing_receipts:
        validate_no_source_mutation(receipt, label=f"existing_task_receipt:{_normal_task_id(receipt) or 'unknown'}")
        if not _normal_task_id(receipt):
            raise ValueError("existing_task_receipt_missing_task_id")

    resume_before = plan_resume(request, existing_receipts)
    written: list[str] = []
    for item in resume_before["remaining_tasks"]:
        task_id = str(item["task_id"])
        attempt = int(item["next_attempt"])
        payload = {
            "run_id": request["run_id"],
            "candidate_id": request["candidate_id"],
            "task_id": task_id,
            "split": request["split"],
            "attempt": attempt,
            "candidate_packet": dict(request.get("candidate_packet") or {}),
            "task_allocation": dict(request.get("task_allocation") or {}),
            "request": request,
        }
        try:
            grade_result = dict(grade_fn(payload))
            validate_no_source_mutation(grade_result, label=f"grade_result:{task_id}")
        except Exception as exc:  # noqa: BLE001 - worker infra failures must receipt.
            grade_result = {
                "status": "infra_failed",
                "resolved": None,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        receipt = _worker_receipt(
            request=request,
            task_id=task_id,
            attempt=attempt,
            worker_label=worker_label,
            grade_result=grade_result,
        )
        out = _task_receipt_path(receipt_dir, task_id, receipt)
        _write_json(out, receipt)
        written.append(str(out))

    all_receipts = load_task_receipts(output_root) if output_root.exists() else []
    resume_after = plan_resume(request, all_receipts)
    manifest = {
        "schema": WORKER_RESULT_SCHEMA,
        "generated_at": utc_now(),
        "run_id": request["run_id"],
        "candidate_id": request["candidate_id"],
        "request_sha256": request.get("request_sha256", canonical_sha256(request)),
        "worker_label": worker_label,
        "result_root": str(output_root),
        "task_count": len(request.get("task_ids") or []),
        "existing_receipt_count": len(existing_receipts),
        "written_receipts": written,
        "written_receipt_count": len(written),
        "resume_plan_before": resume_before,
        "resume_plan_after": resume_after,
        "source_of_truth_mutated": False,
        "live_apply_performed": False,
        "archive_fitness_mutated": False,
        "promotion_gate": PROMOTION_GATE,
    }
    manifest["result_manifest_sha256"] = canonical_sha256(manifest)
    _write_json(output_root / "result_manifest.json", manifest)
    return manifest


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
        "archive_fitness_mutated": False,
        "promotion_gate": PROMOTION_GATE,
        "result_manifest_sha256": canonical_sha256(manifest),
    }
    sync_manifest["sync_sha256"] = canonical_sha256(sync_manifest)
    _write_json(sync_dir / "sync_manifest.json", sync_manifest)
    return sync_manifest


ORCHESTRATION_SCHEMA = f"{SCHEMA_VERSION}.orchestration"


def orchestrate_native_request(
    *,
    run_id: str,
    candidate_packet: dict[str, Any],
    split: str,
    count: int,
    epoch_id: str,
    lane_id: str | None = None,
    output_root: Path | str = DEFAULT_RUN_ROOT,
    taskbed_db: Path | str = taskbed_ledger.DEFAULT_DB,
    task_ids: list[str] | None = None,
    budget: dict[str, Any] | None = None,
    runner_label: str = "native_x86_64",
    max_infra_retries: int = 2,
    prewarm: dict[str, Any] | None = None,
    sync_back_target: Path | str | None = None,
    worker_config: dict[str, Any] | None = None,
    allocation_id: str | None = None,
    min_count: int | None = None,
) -> dict[str, Any]:
    """Allocate a real taskbed slice and write a grade-only native request.

    This is the local-Mac ORCHESTRATION half of Workstream 6: it turns a
    candidate genome/packet + an epoch into a sealed native runner request by
    pulling task ids from the durable ``taskbed_ledger`` (the same allocation
    authority the conductor uses), rather than requiring a caller to hand-roll a
    ``task_allocation`` dict.  It performs no grading and no model calls, so it
    runs without provider budget; the actual grading is delegated to a native
    worker via ``run_native_runner_request``.

    EXPLORE and CONFIRM stay separated because allocation goes through the ledger,
    which refuses to reuse an EXPLORE task for CONFIRM and enforces the clean
    contamination / minimum-N rules for CONFIRM.  Promotion remains owned by
    ``verify_promotion``; this request is grade-only.
    """
    if split not in {"explore", "confirm"}:
        raise ValueError("split must be explore or confirm")
    task_ids = [str(item) for item in (task_ids or []) if str(item).strip()]
    if count <= 0 and not task_ids:
        raise ValueError("count must be positive unless task_ids are provided")
    candidate_id = str(
        candidate_packet.get("candidate_id")
        or candidate_packet.get("id")
        or run_id
    )
    lane = lane_id or f"native_{run_id}"
    if task_ids:
        allocation = taskbed_ledger.allocate_task_ids(
            split=split,  # type: ignore[arg-type]
            task_ids=task_ids,
            epoch_id=epoch_id,
            lane_id=lane,
            db_path=taskbed_db,
            allocation_id=allocation_id,
            candidate_id=candidate_id,
            min_count=min_count,
        )
    else:
        allocation = taskbed_ledger.allocate_tasks(
            split=split,  # type: ignore[arg-type]
            count=count,
            epoch_id=epoch_id,
            lane_id=lane,
            db_path=taskbed_db,
            allocation_id=allocation_id,
            candidate_id=candidate_id,
            min_count=min_count,
        )
    write_result = write_native_runner_request(
        run_id=run_id,
        candidate_packet=candidate_packet,
        task_allocation=allocation,
        output_root=output_root,
        split=split,
        budget=budget,
        runner_label=runner_label,
        max_infra_retries=max_infra_retries,
        prewarm=prewarm,
        sync_back_target=sync_back_target,
        worker_config={"taskbed_db": str(taskbed_db), **dict(worker_config or {})},
    )
    orchestration = {
        "schema": ORCHESTRATION_SCHEMA,
        "generated_at": utc_now(),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "split": split,
        "epoch_id": epoch_id,
        "lane_id": lane,
        "taskbed_db": str(taskbed_db),
        "explicit_task_ids": task_ids,
        "allocation_id": allocation.get("allocation_id"),
        "allocation_receipt": allocation,
        "request": write_result,
        "source_of_truth_mutated": False,
        "live_apply_performed": False,
        "archive_fitness_mutated": False,
        "promotion_gate": PROMOTION_GATE,
    }
    orchestration["orchestration_sha256"] = canonical_sha256(orchestration)
    request_dir = Path(write_result["request_dir"])
    _write_json(request_dir / "orchestration.json", orchestration)
    return orchestration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Orchestrate or execute a grade-only native runner request",
    )
    parser.add_argument("--execute-request-dir", default="", help="Worker mode: execute an existing request dir")
    parser.add_argument("--result-root", default=None, help="Worker mode: where to write result_manifest/task_receipts")
    parser.add_argument("--worker-label", default="native_contract_worker")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--candidate-id", default="", help="Scaffold/code candidate id to grade")
    parser.add_argument("--candidate-json", default="", help="Inline JSON candidate packet (merged with --candidate-id)")
    parser.add_argument("--split", choices=["explore", "confirm"], default="explore")
    parser.add_argument("--count", type=int, default=0)
    parser.add_argument("--task-ids", default="", help="Comma-separated explicit task ids to allocate")
    parser.add_argument("--epoch-id", default="epoch_0")
    parser.add_argument("--lane-id", default=None)
    parser.add_argument("--output-root", default=str(DEFAULT_RUN_ROOT))
    parser.add_argument("--taskbed-db", default=str(taskbed_ledger.DEFAULT_DB))
    parser.add_argument("--max-infra-retries", type=int, default=2)
    parser.add_argument("--allocation-id", default=None)
    parser.add_argument("--min-count", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Print the orchestration receipt as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.execute_request_dir:
        result = run_native_runner_request(
            request_dir=args.execute_request_dir,
            result_root=args.result_root,
            worker_label=args.worker_label,
        )
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True, default=str))
        else:
            print(
                "[native_runner_contract] executed run_id={run_id} wrote={written} result_root={root}".format(
                    run_id=result.get("run_id"),
                    written=result.get("written_receipt_count", 0),
                    root=result.get("result_root"),
                ),
                flush=True,
            )
        return 0
    if not args.run_id:
        parser.error("--run-id is required unless --execute-request-dir is used")
    if not args.candidate_id:
        parser.error("--candidate-id is required unless --execute-request-dir is used")
    task_ids = [item.strip() for item in args.task_ids.split(",") if item.strip()]
    if args.count <= 0 and not task_ids:
        parser.error("--count must be positive unless --task-ids or --execute-request-dir is used")
    candidate_packet: dict[str, Any] = {}
    if args.candidate_json.strip():
        candidate_packet = json.loads(args.candidate_json)
        if not isinstance(candidate_packet, dict):
            raise TypeError("--candidate-json must decode to a JSON object")
    candidate_packet.setdefault("candidate_id", args.candidate_id)
    result = orchestrate_native_request(
        run_id=args.run_id,
        candidate_packet=candidate_packet,
        split=args.split,
        count=args.count,
        epoch_id=args.epoch_id,
        lane_id=args.lane_id,
        output_root=args.output_root,
        taskbed_db=args.taskbed_db,
        task_ids=task_ids,
        max_infra_retries=args.max_infra_retries,
        allocation_id=args.allocation_id,
        min_count=args.min_count,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        request = result.get("request", {})
        print(
            "[native_runner_contract] orchestrated run_id={run_id} split={split} "
            "tasks={tasks} request_dir={dir}".format(
                run_id=result.get("run_id"),
                split=result.get("split"),
                tasks=request.get("task_rows", 0),
                dir=request.get("request_dir"),
            ),
            flush=True,
        )
    return 0


__all__ = [
    "COMPLETED_STATUSES",
    "DEFAULT_RUN_ROOT",
    "DEFAULT_SYNC_ROOT",
    "INFRA_RETRYABLE_STATUSES",
    "ORCHESTRATION_SCHEMA",
    "PROMOTION_GATE",
    "QUARANTINE_STATUSES",
    "REQUEST_SCHEMA",
    "RESUME_SCHEMA",
    "SCHEMA_VERSION",
    "SYNC_SCHEMA",
    "TASK_RECEIPT_SCHEMA",
    "WORKER_RESULT_SCHEMA",
    "build_prewarm_manifest",
    "build_parser",
    "default_native_grade",
    "is_swebench_task_id",
    "load_task_receipts",
    "main",
    "orchestrate_native_request",
    "plan_resume",
    "prediction_for_task",
    "repo_slug_from_task_id",
    "run_native_runner_request",
    "sync_remote_receipts",
    "validate_no_source_mutation",
    "validate_request_authority",
    "write_native_runner_request",
]


if __name__ == "__main__":
    sys.exit(main())
