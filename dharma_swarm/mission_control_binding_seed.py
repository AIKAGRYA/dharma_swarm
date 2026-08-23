"""Fail-closed validation of immutable SADHANA bootstrap task seeds."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from dharma_swarm.mission_control_authority import (
    CAMPAIGN_AUTHORITY_METADATA_KEY,
    SADHANA_BOOTSTRAP_SCHEMA_VERSION,
    SADHANA_GOAL_CONTRACT_SCHEMA_VERSION,
)
from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION,
    TASK_SCAN_LIMIT,
    MissionControlError,
    stable_id,
)
from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.operator_core.execution_lease import parse_time
from dharma_swarm.task_board import TaskBoard

_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_GOAL_PRIORITIES = {
    "P0": TaskPriority.URGENT,
    "P1": TaskPriority.HIGH,
    "P2": TaskPriority.NORMAL,
    "P3": TaskPriority.LOW,
}
_SEED_CREATION_METADATA_FIELDS = (
    "sadhana_bootstrap_schema",
    "goal_contract_schema",
    "goal_contract_sha256",
    "portfolio_contract_sha256",
    "campaign_id",
    "goal_id",
    "goal_dependencies",
    "goal_priority",
    "goal_deadline",
    "attempt_ceiling",
    "cash_ceiling_usd",
    "concurrency_ceiling",
    "default_attempt_policy",
    "dispatch_ready",
    "dispatch_blocker",
    "schema_version",
    "mission_id",
    "mission_task_idempotency_key",
)


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise MissionControlError("seed task must be canonical JSON") from exc


def _canonical_time(value: Any, label: str) -> datetime:
    _need(isinstance(value, str) and value, f"{label} must be a timestamp")
    parsed = parse_time(value)
    _need(
        parsed is not None
        and parsed.tzinfo is not None
        and parsed.isoformat() == value,
        f"{label} must be a canonical timezone-aware ISO timestamp",
    )
    return parsed


def _zero_usd(value: Any, label: str) -> None:
    _need(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and float(value) == 0.0,
        f"{label} must be exactly zero",
    )


def _seed_creation_hash(task: Task) -> str:
    metadata = {
        key: task.metadata[key]
        for key in _SEED_CREATION_METADATA_FIELDS
        if key in task.metadata
    }
    payload = {
        "title": task.title,
        "description": task.description,
        "priority": task.priority.value,
        "created_by": task.created_by,
        "depends_on": sorted(task.depends_on),
        "metadata": metadata,
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _validate_seed_task(task: Task, manifest: Any, goal: Any) -> datetime:
    metadata = task.metadata
    expected = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": manifest.mission_id,
        "sadhana_bootstrap_schema": SADHANA_BOOTSTRAP_SCHEMA_VERSION,
        "goal_contract_schema": SADHANA_GOAL_CONTRACT_SCHEMA_VERSION,
        "campaign_id": manifest.campaign_id,
        "goal_id": goal.goal_id,
        "portfolio_contract_sha256": manifest.goal_contract_sha256,
        "goal_contract_sha256": goal.goal_contract_sha256,
        "cash_ceiling_usd": 0.0,
        "dispatch_ready": False,
        "dispatch_blocker": "authority_unbound",
    }
    for key, value in expected.items():
        _need(metadata.get(key) == value, f"goal {goal.goal_id} seed {key} conflicts")
    _zero_usd(metadata.get("cash_ceiling_usd"), f"goal {goal.goal_id} cash ceiling")
    _need(task.id == goal.task_id, f"goal {goal.goal_id} task identity conflicts")
    _need(task.title == goal.goal_id, f"goal {goal.goal_id} title conflicts")
    _need(task.created_by == "sadhana-bootstrap", f"goal {goal.goal_id} creator conflicts")
    _need(
        metadata.get("mission_task_idempotency_key")
        == stable_id(
            "sadhana_goal",
            manifest.campaign_id,
            manifest.goal_contract_sha256,
            goal.goal_id,
        ),
        f"goal {goal.goal_id} idempotency identity conflicts",
    )
    creation_hash = metadata.get("mission_task_creation_hash")
    _need(
        isinstance(creation_hash, str)
        and _RAW_SHA256_RE.fullmatch(creation_hash) is not None
        and creation_hash == goal.task_creation_hash == _seed_creation_hash(task),
        f"goal {goal.goal_id} creation hash conflicts",
    )
    dependencies = metadata.get("goal_dependencies")
    _need(
        type(dependencies) is list
        and len(set(dependencies)) == len(dependencies)
        and all(isinstance(item, str) and item for item in dependencies),
        f"goal {goal.goal_id} dependencies are invalid",
    )
    _need(
        metadata.get("goal_priority") in _GOAL_PRIORITIES
        and task.priority is _GOAL_PRIORITIES[metadata["goal_priority"]],
        f"goal {goal.goal_id} priority conflicts",
    )
    deadline = _canonical_time(metadata.get("goal_deadline"), f"goal {goal.goal_id} deadline")
    _need(deadline <= manifest.campaign_end, f"goal {goal.goal_id} exceeds campaign end")
    for key in ("attempt_ceiling", "concurrency_ceiling"):
        value = metadata.get(key)
        _need(
            isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"goal {goal.goal_id} {key.replace('_', ' ')} is invalid",
        )
    _need(
        metadata.get("attempt_ceiling") == goal.max_attempts,
        f"goal {goal.goal_id} max attempts conflicts with its goal contract",
    )
    policy = metadata.get("default_attempt_policy")
    _need(
        isinstance(policy, str) and policy == policy.strip() and bool(policy),
        f"goal {goal.goal_id} attempt policy is invalid",
    )
    if task.status is TaskStatus.PENDING:
        _need(task.assigned_to is None, f"goal {goal.goal_id} pending assignee conflicts")
    else:
        _need(
            isinstance(metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY), dict),
            f"goal {goal.goal_id} non-pending state has no prior authority",
        )
    if task.status in {TaskStatus.ASSIGNED, TaskStatus.RUNNING}:
        _need(bool(task.assigned_to), f"goal {goal.goal_id} active assignee is missing")
    return deadline


async def validate_campaign_tasks(board: TaskBoard, manifest: Any) -> dict[str, Task]:
    """Resolve exactly this campaign's immutable seeds and validate its DAG."""
    scanned = await board.list_tasks(limit=TASK_SCAN_LIMIT + 1)
    _need(len(scanned) <= TASK_SCAN_LIMIT, "campaign task scan saturated")
    goals = {goal.goal_id: goal for goal in manifest.goals}
    expected_keys = {
        stable_id("sadhana_goal", manifest.campaign_id, manifest.goal_contract_sha256, goal_id)
        for goal_id in goals
    }
    tasks: dict[str, Task] = {}
    deadlines: list[datetime] = []
    for task in scanned:
        metadata = task.metadata
        in_namespace = bool(
            metadata.get("mission_id") == manifest.mission_id
            or metadata.get("campaign_id") == manifest.campaign_id
            or metadata.get("mission_task_idempotency_key") in expected_keys
        )
        if not in_namespace:
            continue
        goal_id = metadata.get("goal_id")
        _need(
            isinstance(goal_id, str) and goal_id in goals,
            f"foreign task {task.id!r} occupies campaign namespace",
        )
        _need(goal_id not in tasks, f"goal {goal_id} maps to multiple tasks")
        deadlines.append(_validate_seed_task(task, manifest, goals[goal_id]))
        tasks[goal_id] = task
    _need(set(tasks) == set(goals), "campaign tasks do not exactly match manifest goals")
    task_ids = {goal_id: task.id for goal_id, task in tasks.items()}
    for goal_id, task in tasks.items():
        dependencies = task.metadata["goal_dependencies"]
        _need(
            all(dep in task_ids and dep != goal_id for dep in dependencies)
            and sorted(task.depends_on)
            == sorted(task_ids[dep] for dep in dependencies),
            f"goal {goal_id} dependency graph conflicts",
        )
    _need(max(deadlines) == manifest.campaign_end, "campaign end must equal the maximum goal deadline")
    return tasks


__all__ = ["validate_campaign_tasks"]
