"""Immutable four-way evaluation plans for Forge Lab campaigns.

The taskbed retains its historic two physical pools (``explore`` and
``confirm``).  A plan freezes the scientific four-way overlay used by a single
campaign: mutation feedback on ``train``, selection on ``explore``, a frozen
challenger comparison on ``confirm``, and one final ``holdout`` read.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from dharma_swarm.forge_lab.ids import content_digest

PLAN_SCHEMA = "forge_lab.evaluation_plan.v1"
LOGICAL_SPLITS = ("train", "explore", "confirm", "holdout")
LOGICAL_TO_PHYSICAL = {
    "train": "explore",
    "explore": "explore",
    "confirm": "confirm",
    "holdout": "confirm",
}
CLEAN_CONFIRM_STATES = frozenset({"fresh_post_cutoff", "fresh_private_local_generated"})


class EvaluationPlanError(ValueError):
    """The requested plan is malformed or differs from frozen evidence."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_parts(record: Mapping[str, Any]) -> tuple[str, Any, dict[str, Any]]:
    task = record.get("task", record)
    if not isinstance(task, Mapping):
        raise EvaluationPlanError("task content must be a mapping")
    task_id = str(record.get("task_id") or task.get("task_id") or task.get("instance_id") or "").strip()
    if not task_id:
        raise EvaluationPlanError("task record is missing task_id or instance_id")
    provenance = {
        key: record.get(key)
        for key in (
            "source",
            "taskbed",
            "contamination_state",
            "provenance",
            "created_at",
            "active",
            "max_uses_per_epoch",
        )
        if key in record
    }
    return task_id, dict(task), provenance


@dataclass(frozen=True)
class FrozenTask:
    """A task identity plus hashes of its executable content and provenance."""

    task_id: str
    content_sha256: str
    provenance_sha256: str

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "FrozenTask":
        task_id, task, provenance = _task_parts(record)
        return cls(
            task_id=task_id,
            content_sha256=content_digest(task),
            provenance_sha256=content_digest(provenance),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FrozenTask":
        task = cls(
            task_id=str(value.get("task_id") or ""),
            content_sha256=str(value.get("content_sha256") or ""),
            provenance_sha256=str(value.get("provenance_sha256") or ""),
        )
        if not task.task_id or not _is_sha256(task.content_sha256) or not _is_sha256(task.provenance_sha256):
            raise EvaluationPlanError("invalid frozen task record")
        return task

    def to_dict(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "content_sha256": self.content_sha256,
            "provenance_sha256": self.provenance_sha256,
        }


@dataclass(frozen=True)
class EvaluationPlan:
    schema: str
    campaign_id: str
    created_at: str
    baseline_candidate_id: str
    baseline_genome_sha256: str
    repeat_seeds: tuple[int, ...]
    train: tuple[FrozenTask, ...]
    explore: tuple[FrozenTask, ...]
    confirm: tuple[FrozenTask, ...]
    holdout: tuple[FrozenTask, ...]
    evaluator_identity_json: str
    plan_sha256: str

    @property
    def evaluator_identity(self) -> dict[str, Any]:
        return json.loads(self.evaluator_identity_json)

    def tasks(self, split: str) -> tuple[FrozenTask, ...]:
        if split not in LOGICAL_SPLITS:
            raise KeyError(f"unknown logical split: {split}")
        return getattr(self, split)

    def task_ids(self, split: str) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.tasks(split))

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema": self.schema,
            "campaign_id": self.campaign_id,
            "created_at": self.created_at,
            "baseline_candidate_id": self.baseline_candidate_id,
            "baseline_genome_sha256": self.baseline_genome_sha256,
            "repeat_seeds": list(self.repeat_seeds),
            "logical_to_physical": dict(LOGICAL_TO_PHYSICAL),
            "splits": {
                split: [task.to_dict() for task in self.tasks(split)]
                for split in LOGICAL_SPLITS
            },
            "evaluator_identity": self.evaluator_identity,
        }
        if include_digest:
            value["plan_sha256"] = self.plan_sha256
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvaluationPlan":
        if value.get("schema") != PLAN_SCHEMA:
            raise EvaluationPlanError(f"unsupported evaluation plan schema: {value.get('schema')!r}")
        split_values = value.get("splits")
        if not isinstance(split_values, Mapping) or set(split_values) != set(LOGICAL_SPLITS):
            raise EvaluationPlanError("plan must contain exactly train/explore/confirm/holdout splits")
        mapping = value.get("logical_to_physical")
        if mapping != LOGICAL_TO_PHYSICAL:
            raise EvaluationPlanError("logical_to_physical mapping is invalid")
        repeats = _validate_repeat_seeds(value.get("repeat_seeds", ()))
        evaluator = value.get("evaluator_identity")
        if not isinstance(evaluator, Mapping):
            raise EvaluationPlanError("evaluator_identity must be a mapping")
        evaluator_json = _canonical_json(dict(evaluator))
        tasks = {
            split: tuple(FrozenTask.from_dict(item) for item in split_values[split])
            for split in LOGICAL_SPLITS
        }
        _validate_disjoint(tasks)
        plan = cls(
            schema=PLAN_SCHEMA,
            campaign_id=str(value.get("campaign_id") or ""),
            created_at=str(value.get("created_at") or ""),
            baseline_candidate_id=str(value.get("baseline_candidate_id") or ""),
            baseline_genome_sha256=str(value.get("baseline_genome_sha256") or ""),
            repeat_seeds=repeats,
            train=tasks["train"],
            explore=tasks["explore"],
            confirm=tasks["confirm"],
            holdout=tasks["holdout"],
            evaluator_identity_json=evaluator_json,
            plan_sha256=str(value.get("plan_sha256") or ""),
        )
        _validate_plan_header(plan)
        expected = content_digest(plan.to_dict(include_digest=False))
        if plan.plan_sha256 != expected:
            raise EvaluationPlanError("evaluation plan digest mismatch")
        return plan


def build_evaluation_plan(
    *,
    campaign_id: str,
    split_tasks: Mapping[str, Iterable[Mapping[str, Any]]],
    repeat_seeds: Iterable[int],
    baseline_candidate_id: str,
    baseline_genome_sha256: str,
    evaluator_identity: Mapping[str, Any],
    created_at: str | None = None,
    allow_empty_splits: bool = False,
) -> EvaluationPlan:
    """Build an immutable plan without touching the taskbed or filesystem."""
    if set(split_tasks) != set(LOGICAL_SPLITS):
        raise EvaluationPlanError("split_tasks must contain exactly train/explore/confirm/holdout")
    records_by_split = {
        split: tuple(split_tasks[split])
        for split in LOGICAL_SPLITS
    }
    tasks = {
        split: tuple(FrozenTask.from_record(record) for record in records_by_split[split])
        for split in LOGICAL_SPLITS
    }
    for split in ("confirm", "holdout"):
        for record in records_by_split[split]:
            if str(record.get("contamination_state") or "") not in CLEAN_CONFIRM_STATES:
                raise EvaluationPlanError(f"{split} task is not contamination-clean")
    if not allow_empty_splits and any(not tasks[split] for split in LOGICAL_SPLITS):
        raise EvaluationPlanError("all four logical splits must be non-empty")
    _validate_disjoint(tasks)
    repeats = _validate_repeat_seeds(repeat_seeds)
    evaluator_json = _canonical_json(dict(evaluator_identity))
    provisional = EvaluationPlan(
        schema=PLAN_SCHEMA,
        campaign_id=str(campaign_id),
        created_at=str(created_at or _utc_now()),
        baseline_candidate_id=str(baseline_candidate_id),
        baseline_genome_sha256=str(baseline_genome_sha256),
        repeat_seeds=repeats,
        train=tasks["train"],
        explore=tasks["explore"],
        confirm=tasks["confirm"],
        holdout=tasks["holdout"],
        evaluator_identity_json=evaluator_json,
        plan_sha256="",
    )
    _validate_plan_header(provisional, require_digest=False)
    digest = content_digest(provisional.to_dict(include_digest=False))
    return EvaluationPlan(**{**provisional.__dict__, "plan_sha256": digest})


def build_evaluation_plan_from_overlay(
    *,
    overlay_receipt: Mapping[str, Any],
    task_loader: Callable[[str], Mapping[str, Any]],
    repeat_seeds: Iterable[int],
    baseline_candidate_id: str,
    baseline_genome_sha256: str,
    evaluator_identity: Mapping[str, Any],
    created_at: str | None = None,
) -> EvaluationPlan:
    """Materialize a plan from a persisted taskbed campaign overlay receipt."""
    if overlay_receipt.get("schema") != "forge_v2.campaign_task_overlay.v1":
        raise EvaluationPlanError("unsupported campaign overlay receipt")
    unsigned_overlay = dict(overlay_receipt)
    claimed_overlay_digest = str(unsigned_overlay.pop("overlay_sha256", ""))
    if claimed_overlay_digest != content_digest(unsigned_overlay):
        raise EvaluationPlanError("campaign overlay digest mismatch")
    if overlay_receipt.get("frozen") is not True:
        raise EvaluationPlanError("campaign overlay is not frozen")
    if overlay_receipt.get("all_splits_disjoint") is not True:
        raise EvaluationPlanError("campaign overlay splits are not disjoint")
    if overlay_receipt.get("confirm_pool_contamination_clean") is not True:
        raise EvaluationPlanError("campaign overlay confirm pool is not contamination-clean")
    if overlay_receipt.get("logical_to_physical") != LOGICAL_TO_PHYSICAL:
        raise EvaluationPlanError("campaign overlay physical mapping is invalid")
    raw_splits = overlay_receipt.get("logical_splits")
    if not isinstance(raw_splits, Mapping) or set(raw_splits) != set(LOGICAL_SPLITS):
        raise EvaluationPlanError("campaign overlay must contain all four logical splits")
    split_tasks: dict[str, list[Mapping[str, Any]]] = {}
    for split in LOGICAL_SPLITS:
        ids = raw_splits[split]
        if not isinstance(ids, list) or any(not isinstance(task_id, str) for task_id in ids):
            raise EvaluationPlanError(f"campaign overlay {split} task IDs are invalid")
        split_tasks[split] = []
        for task_id in ids:
            record = task_loader(task_id)
            loaded_id, _, _ = _task_parts(record)
            if loaded_id != task_id:
                raise EvaluationPlanError(
                    f"task loader returned {loaded_id!r} for frozen overlay ID {task_id!r}"
                )
            split_tasks[split].append(record)
    return build_evaluation_plan(
        campaign_id=str(overlay_receipt.get("campaign_id") or ""),
        split_tasks=split_tasks,
        repeat_seeds=repeat_seeds,
        baseline_candidate_id=baseline_candidate_id,
        baseline_genome_sha256=baseline_genome_sha256,
        evaluator_identity=evaluator_identity,
        created_at=created_at,
    )


def write_evaluation_plan(path: Path | str, plan: EvaluationPlan) -> EvaluationPlan:
    """Create a frozen plan atomically; an existing different plan is fatal."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = load_evaluation_plan(target)
        if existing.plan_sha256 != plan.plan_sha256:
            raise EvaluationPlanError("evaluation plan already frozen with different content")
        return existing

    payload = (_canonical_json(plan.to_dict()) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_name, target)
        except FileExistsError:
            existing = load_evaluation_plan(target)
            if existing.plan_sha256 != plan.plan_sha256:
                raise EvaluationPlanError("evaluation plan concurrently frozen with different content")
            return existing
        _fsync_directory(target.parent)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return plan


def load_evaluation_plan(path: Path | str) -> EvaluationPlan:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationPlanError(f"cannot load evaluation plan: {exc}") from exc
    if not isinstance(value, Mapping):
        raise EvaluationPlanError("evaluation plan root must be an object")
    return EvaluationPlan.from_dict(value)


def frozen_task_mismatches(
    plan: EvaluationPlan,
    task_loader: Callable[[str], Mapping[str, Any]],
) -> list[str]:
    """Return task IDs whose current content/provenance differs from the plan."""
    mismatches: list[str] = []
    for split in LOGICAL_SPLITS:
        for frozen in plan.tasks(split):
            try:
                current = FrozenTask.from_record(task_loader(frozen.task_id))
            except Exception:
                mismatches.append(frozen.task_id)
                continue
            if current != frozen:
                mismatches.append(frozen.task_id)
    return sorted(set(mismatches))


def assert_frozen_tasks(
    plan: EvaluationPlan,
    task_loader: Callable[[str], Mapping[str, Any]],
) -> None:
    mismatches = frozen_task_mismatches(plan, task_loader)
    if mismatches:
        raise EvaluationPlanError(f"frozen task content changed: {mismatches}")


def _validate_repeat_seeds(values: Iterable[int]) -> tuple[int, ...]:
    try:
        repeats = tuple(values)
    except TypeError as exc:
        raise EvaluationPlanError("repeat_seeds must be iterable") from exc
    if not repeats or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in repeats):
        raise EvaluationPlanError("repeat_seeds must be non-empty integers")
    if len(set(repeats)) != len(repeats):
        raise EvaluationPlanError("repeat_seeds must be unique")
    return repeats


def _validate_disjoint(tasks: Mapping[str, tuple[FrozenTask, ...]]) -> None:
    seen: dict[str, str] = {}
    for split in LOGICAL_SPLITS:
        ids = [task.task_id for task in tasks[split]]
        if len(ids) != len(set(ids)):
            raise EvaluationPlanError(f"duplicate task ID within {split}")
        for task_id in ids:
            if task_id in seen:
                raise EvaluationPlanError(f"task {task_id!r} appears in both {seen[task_id]} and {split}")
            seen[task_id] = split


def _validate_plan_header(plan: EvaluationPlan, *, require_digest: bool = True) -> None:
    if not plan.campaign_id or not plan.created_at or not plan.baseline_candidate_id:
        raise EvaluationPlanError("campaign_id, created_at, and baseline_candidate_id are required")
    if not _is_sha256(plan.baseline_genome_sha256):
        raise EvaluationPlanError("baseline_genome_sha256 must be a full SHA-256 digest")
    if plan.baseline_candidate_id != f"cand_{plan.baseline_genome_sha256[:16]}":
        raise EvaluationPlanError("baseline_candidate_id does not match baseline genome digest")
    if require_digest and not _is_sha256(plan.plan_sha256):
        raise EvaluationPlanError("plan_sha256 must be a full SHA-256 digest")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


__all__ = [
    "EvaluationPlan",
    "EvaluationPlanError",
    "FrozenTask",
    "LOGICAL_SPLITS",
    "LOGICAL_TO_PHYSICAL",
    "PLAN_SCHEMA",
    "assert_frozen_tasks",
    "build_evaluation_plan",
    "build_evaluation_plan_from_overlay",
    "frozen_task_mismatches",
    "load_evaluation_plan",
    "write_evaluation_plan",
]
