"""Governed taskbed intake around the repository-owned fresh-task oracle."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, TypeAlias

from dharma_swarm.forge_lab.model_onboarding import activation_status
from dharma_swarm.forge_lab.source_guard import (
    CANONICAL_REPOSITORY,
    require_execution_source,
)
from dharma_swarm.forge_lab.taskpack_apply import (
    ACTION_SCHEMA,
    INTENT_SCHEMA,
    apply_taskpack_impl,
)
from dharma_swarm.forge_lab.taskpack_validation import (
    FRESH_SOURCE,
    FRESH_TASKBED,
    MAX_MANIFEST_BYTES,
    MAX_MANIFEST_ROWS,
    MODE_GOVERNED_FRESH,
    MODE_SEARCH_ONLY_PUBLIC_SWEBENCH,
    ORACLE_SCHEMA,
    POLICY_MAX_USES_PER_EPOCH,
    SEARCH_SOURCE,
    SEARCH_TASKBED,
    SHA_RE as _SHA,
    TaskpackError,
    TaskpackMode,
    mode_policy as _policy,
    oracle_preflight as _preflight,
    raw_digest as _digest,
    read_regular_file as _read_file,
    sealed_manifest as _manifest,
)
from dharma_swarm.forge_lab.state_io import (
    content_digest,
    dharma_home,
)
from dharma_swarm.forge_v1.forge_v2.fresh_task_oracle import parse_cutoff

TaskpackPlan: TypeAlias = dict[str, Any]
_POLICY_EXPORTS = (
    ACTION_SCHEMA,
    FRESH_SOURCE,
    FRESH_TASKBED,
    INTENT_SCHEMA,
    MAX_MANIFEST_BYTES,
    MAX_MANIFEST_ROWS,
    ORACLE_SCHEMA,
    POLICY_MAX_USES_PER_EPOCH,
    SEARCH_SOURCE,
    SEARCH_TASKBED,
)

DEFAULT_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS = 90, 300
STATUS_SCHEMA, PLAN_SCHEMA = "rsi_lab.taskpack_status.v1", "rsi_lab.taskpack_plan.v1"
_TASK_COLUMNS = {
    "task_id",
    "task_json",
    "source",
    "taskbed",
    "contamination_state",
    "provenance_json",
    "created_at",
    "first_seen_at",
    "active",
    "max_uses_per_epoch",
}
_ALLOCATION_COLUMNS = {
    "allocation_id",
    "task_id",
    "split",
    "epoch_id",
    "lane_id",
    "candidate_id",
    "allocated_at",
    "status",
}


def anchored_taskbed_db() -> Path:
    return dharma_home() / "forge_v1" / "taskbed.db"


def _taskbed_path(value: Path | str | None) -> Path:
    raw = anchored_taskbed_db()
    if raw.is_symlink():
        raise TaskpackError(
            "TASKBED_PATH_UNSAFE", "anchored taskbed must not be a symlink"
        )
    anchor = raw.resolve(strict=False)
    if not anchor.is_relative_to(dharma_home()):
        raise TaskpackError("TASKBED_PATH_UNSAFE", "taskbed escaped DHARMA_HOME")
    candidate_raw = Path(value).expanduser() if value is not None else raw
    if candidate_raw.is_symlink():
        raise TaskpackError("TASKBED_PATH_UNSAFE", "taskbed path must not be a symlink")
    candidate = candidate_raw.resolve(strict=False)
    if candidate != anchor:
        raise TaskpackError("TASKBED_PATH_NOT_ANCHORED", f"taskbed must equal {anchor}")
    if candidate.exists() and not candidate.is_file():
        raise TaskpackError("TASKBED_PATH_UNSAFE", "taskbed is not a regular file")
    return candidate


def taskpack_status(*, taskbed_db: Path | str | None = None) -> dict[str, Any]:
    from dharma_swarm.forge_v1.forge_v2.pr_suite_grader import is_pr_suite_task_id

    path = _taskbed_path(taskbed_db)
    result: dict[str, Any] = {
        "schema": STATUS_SCHEMA,
        "ready": False,
        "taskbed_db": str(path),
        "exists": path.is_file(),
        "sqlite_mode": "mode=ro",
        "task_count": 0,
        "active_task_count": 0,
        "eligible_explore_task_count": 0,
        "next_explore_task_id": None,
        "contamination_state_counts": {},
        "source_counts": {},
        "taskbed_counts": {},
        "reasons": [],
    }
    if not path.is_file():
        result["reasons"] = ["taskbed_missing"]
        return result
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("PRAGMA busy_timeout=2000")
            tables = {
                str(row[0])
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not {"taskbed_tasks", "taskbed_allocations"} <= tables:
                result["reasons"] = ["taskbed_schema_missing"]
                return result
            task_columns = {
                row[1] for row in db.execute("PRAGMA table_info(taskbed_tasks)")
            }
            allocation_columns = {
                row[1] for row in db.execute("PRAGMA table_info(taskbed_allocations)")
            }
            if not (
                _TASK_COLUMNS <= task_columns
                and _ALLOCATION_COLUMNS <= allocation_columns
            ):
                result["reasons"] = ["taskbed_schema_incompatible"]
                return result
            total, active = db.execute(
                "SELECT COUNT(*),COALESCE(SUM(CASE WHEN active=1 THEN 1 ELSE 0 END),0) "
                "FROM taskbed_tasks"
            ).fetchone()
            result["task_count"], result["active_task_count"] = int(total), int(active)
            eligible_rows = db.execute(
                """
                SELECT task.task_id FROM taskbed_tasks task
                 WHERE task.active=1
                   AND NOT EXISTS (
                     SELECT 1 FROM taskbed_allocations prior
                      WHERE prior.task_id=task.task_id AND prior.split='confirm'
                   )
                 ORDER BY task.created_at ASC, task.first_seen_at ASC, task.task_id ASC
                """
            ).fetchall()
            eligible_ids = [
                str(row[0])
                for row in eligible_rows
                if not is_pr_suite_task_id(str(row[0]))
            ]
            result["eligible_explore_task_count"] = len(eligible_ids)
            result["next_explore_task_id"] = eligible_ids[0] if eligible_ids else None
            for column, key in (
                ("contamination_state", "contamination_state_counts"),
                ("source", "source_counts"),
                ("taskbed", "taskbed_counts"),
            ):
                rows = db.execute(
                    f"SELECT {column},COUNT(*) FROM taskbed_tasks GROUP BY {column}"  # noqa: S608
                )
                result[key] = {str(name or ""): int(count) for name, count in rows}
    except sqlite3.Error:
        result["reasons"] = ["taskbed_unreadable"]
        return result
    if not result["eligible_explore_task_count"]:
        result["reasons"] = ["zero_eligible_isolated_swebench_tasks"]
        return result
    result["ready"] = True
    return result


def _source(repo: Path | None) -> tuple[dict[str, str], Path, str]:
    try:
        status = require_execution_source(repo)
    except RuntimeError as exc:
        raise TaskpackError("SOURCE_NOT_ADMITTED", str(exc)) from exc
    root, commit = (
        Path(str(status.get("repo") or "")).resolve(strict=False),
        str(status.get("commit") or ""),
    )
    valid = (
        status.get("ready")
        and root.is_dir()
        and _SHA.fullmatch(commit)
        and status.get("canonical_repository") == CANONICAL_REPOSITORY
        and (repo is None or root == repo.expanduser().resolve(strict=False))
    )
    if not valid:
        raise TaskpackError(
            "SOURCE_NOT_ADMITTED", "execution source evidence is incomplete"
        )
    raw = root / "scripts/runtime/forge_fresh_task_oracle.py"
    if raw.is_symlink():
        raise TaskpackError("IMPORTER_UNSAFE", "importer must not be a symlink")
    importer = raw.resolve(strict=False)
    if not importer.is_relative_to(root):
        raise TaskpackError("IMPORTER_UNSAFE", "importer escaped repository")
    digest = _digest(_read_file(importer, 1024 * 1024, "IMPORTER"))
    return (
        {
            "repo": str(root),
            "commit": commit,
            "canonical_repository": CANONICAL_REPOSITORY,
        },
        importer,
        digest,
    )


def _model_cutoff_authority() -> dict[str, Any]:
    try:
        active = activation_status()
    except Exception:
        active = {}
    return {
        "active_profile_digest": (
            active.get("current_profile_digest") if active.get("active") else None
        ),
        "role_bindings": active.get("role_bindings") if active.get("active") else [],
        "cutoff_authority": "operator_supplied_unverified",
        "all_role_cutoffs_authoritative": False,
        "minimum_safe_cutoff": None,
    }


def _custody(mode: TaskpackMode, model_authority: Mapping[str, Any]) -> dict[str, Any]:
    search = mode == MODE_SEARCH_ONLY_PUBLIC_SWEBENCH
    authoritative = bool(model_authority.get("all_role_cutoffs_authoritative"))
    return {
        "epistemic_modality": (
            "EXPLORE_ONLY" if search else "ORACLE_FRESH_TASK_INTAKE"
        ),
        "promotion_eligible": bool(not search and authoritative),
        "confirm_eligible": bool(not search and authoritative),
        "public_pretraining_contamination_possible": bool(search or not authoritative),
        "model_cutoff_authoritative": authoritative,
        "custody_reason": (
            "public_swebench_possible_pretrain"
            if search
            else "active_role_model_cutoffs_authoritatively_bounded"
        ),
    }


def plan_taskpack(
    manifest: Path | str,
    *,
    manifest_digest: str,
    model_cutoff: str,
    mode: TaskpackMode = MODE_GOVERNED_FRESH,
    taskbed_db: Path | str | None = None,
    source: str | None = None,
    taskbed: str | None = None,
    max_uses_per_epoch: int = 1,
    repo: Path | None = None,
) -> TaskpackPlan:
    """Return a deterministic, side-effect-free plan bound to exact bytes and argv."""
    path, data, rows, ids = _manifest(manifest, manifest_digest)
    try:
        cutoff = parse_cutoff(model_cutoff)
    except (TypeError, ValueError) as exc:
        raise TaskpackError("MODEL_CUTOFF_INVALID", "invalid ISO model cutoff") from exc
    cutoff_text = cutoff.isoformat().replace("+00:00", "Z")
    model_authority = _model_cutoff_authority()
    if mode == MODE_GOVERNED_FRESH:
        if not model_authority.get("all_role_cutoffs_authoritative"):
            raise TaskpackError(
                "MODEL_CUTOFF_AUTHORITY_REQUIRED",
                "governed-fresh intake requires authoritative cutoffs for every active role",
            )
        try:
            minimum_cutoff = parse_cutoff(str(model_authority["minimum_safe_cutoff"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise TaskpackError(
                "MODEL_CUTOFF_AUTHORITY_INVALID",
                "authoritative cutoff evidence is invalid",
            ) from exc
        if cutoff < minimum_cutoff:
            raise TaskpackError(
                "MODEL_CUTOFF_TOO_EARLY",
                "requested cutoff precedes the authoritative active-role cutoff",
            )
    policy = _policy(mode, source, taskbed, max_uses_per_epoch)
    preflight = _preflight(rows, ids, cutoff, policy, mode)
    db, (binding, importer, importer_digest) = _taskbed_path(taskbed_db), _source(repo)
    argv = [
        str(Path(sys.executable).resolve(strict=False)),
        str(importer),
        "--manifest",
        str(path),
        "--model-cutoff",
        cutoff_text,
        "--taskbed-db",
        str(db),
        "--source",
        policy["source"],
        "--taskbed",
        policy["taskbed"],
        "--max-uses-per-epoch",
        "1",
    ]
    if policy["include_ineligible"]:
        argv.append("--include-ineligible")
    argv.append("--json")
    custody = _custody(mode, model_authority)
    unsigned = {
        "schema": PLAN_SCHEMA,
        "mode": mode,
        "manifest": {
            "path": str(path),
            "digest": _digest(data),
            "size_bytes": len(data),
            "row_count": len(rows),
            "task_ids_digest": content_digest(ids),
        },
        "model_cutoff": cutoff_text,
        "taskbed_db": str(db),
        "policy": policy,
        "model_cutoff_authority": model_authority,
        "custody": custody,
        **{
            key: custody[key]
            for key in ("epistemic_modality", "promotion_eligible", "confirm_eligible")
        },
        "oracle_preflight": preflight,
        "execution_source": binding,
        "importer": {"path": str(importer), "digest": importer_digest},
        "importer_argv": argv,
    }
    return {**unsigned, "plan_digest": content_digest(unsigned)}


def apply_taskpack(
    plan: Mapping[str, Any],
    *,
    plan_digest: str,
    request_id: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Revalidate and invoke only the sealed repository importer, at most once."""
    return apply_taskpack_impl(
        plan,
        plan_digest=plan_digest,
        request_id=request_id,
        timeout_seconds=timeout_seconds,
        max_timeout_seconds=MAX_TIMEOUT_SECONDS,
        plan_builder=plan_taskpack,
        importer_runner=subprocess.run,
        executable=sys.executable,
    )
