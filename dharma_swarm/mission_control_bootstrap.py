"""Pinned, idempotent bootstrap for the ten-goal SADHANA mission.

This module projects one exact external goal contract into the existing
MissionControl and TaskBoard owners.  It does not create a campaign runtime
session, dispatch authority, an executor, or an acceptance claim.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import math
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION,
    TASK_SCAN_LIMIT,
    MissionControlError,
    MissionView,
    stable_id,
)
from dharma_swarm.models import Task, TaskPriority
from dharma_swarm.task_board import TaskBoard

GOAL_CONTRACT_SCHEMA = "dharma.sadhana.goal_contracts.v1"
BOOTSTRAP_SCHEMA = "dharma.sadhana.mission_bootstrap.v1"
EXPECTED_CAMPAIGN_ID = "sadhana-10-20260823"
EXPECTED_CONTRACT_SHA256 = (
    "e2891fcb2171563adc87a339d5fca42b155ee8aa5dc96b153ab3515f01051101"
)
EXPECTED_CONTRACT_DIGEST = f"sha256:{EXPECTED_CONTRACT_SHA256}"
EXPECTED_CONTRACT_STATUS = "PROVISIONAL_RECONCILIATION_REQUIRED"
EXPECTED_GOAL_IDS = (
    "G01_DARSHAN_PUBLICATION",
    "G02_DHARMAGRAPH_ENGINE",
    "G03_CONSTELLATION_OPERATOR_SURFACE",
    "G04_HYPERBOLIC_TIME_CHAMBER",
    "G05_LOOP_CLOSURE",
    "G06_MERGE_MASTER_PR_CONVERGENCE",
    "G07_ORCHESTRATION_ARENA",
    "G08_ORGANISM_REWIRE",
    "G09_TITANIUM_HARDENING",
    "G10_SAFETY_TCB",
)
CANARY_GOAL_ID = "G05_LOOP_CLOSURE"
MISSION_TITLE = "SADHANA 10"
MISSION_GOAL = (
    "Advance the ten pinned SADHANA goals through independently accepted "
    "beneficial deltas."
)
BOOTSTRAP_CREATED_BY = "sadhana-bootstrap"
DISPATCH_BLOCKER = "authority_unbound"
MAX_CONTRACT_BYTES = 1_000_000
BOOTSTRAP_LOCK_NAME = "sadhana-bootstrap.lock"

_GOAL_ID_RE = re.compile(r"G[0-9]{2}_[A-Z0-9_]+")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_TOP_LEVEL_KEYS = frozenset(
    {"campaign_id", "generated_at", "goals", "portfolio_policy", "schema", "status"}
)
_GOAL_KEYS = frozenset(
    {
        "allowed_actions",
        "approval_boundaries",
        "beneficiary",
        "ceilings",
        "deadline",
        "definition_of_done",
        "dependencies",
        "desired_beneficial_outcome",
        "evidence_locations",
        "forbidden_actions",
        "goal_id",
        "independent_verifier",
        "priority",
        "recorded_baseline",
        "rollback",
        "scope",
        "telos",
        "terminal_conditions",
    }
)
_GOAL_LIST_FIELDS = (
    "allowed_actions",
    "approval_boundaries",
    "dependencies",
    "evidence_locations",
    "forbidden_actions",
    "terminal_conditions",
)
_GOAL_TEXT_FIELDS = (
    "beneficiary",
    "deadline",
    "definition_of_done",
    "desired_beneficial_outcome",
    "goal_id",
    "independent_verifier",
    "priority",
    "rollback",
    "telos",
)
_PRIORITY = {
    "P0": TaskPriority.URGENT,
    "P1": TaskPriority.HIGH,
    "P2": TaskPriority.NORMAL,
    "P3": TaskPriority.LOW,
}
_LOCK_CONSTRUCTION_SENTINEL = object()


class GoalContractError(ValueError):
    """Raised before owner state is opened when the pinned contract is invalid."""


class BootstrapLockError(RuntimeError):
    """Raised when the mandatory campaign bootstrap lock is invalid or busy."""


@dataclass(frozen=True, slots=True)
class GoalContract:
    goal_id: str
    priority: str
    deadline: str
    definition_of_done: str
    dependencies: tuple[str, ...]
    attempts: int
    cash_usd: int | float
    concurrency: int
    default_attempt_policy: str
    content_digest: str


@dataclass(frozen=True, slots=True)
class GoalPortfolio:
    campaign_id: str
    schema: str
    status: str
    generated_at: str
    digest: str
    goals: tuple[GoalContract, ...]
    dependency_order: tuple[str, ...]
    campaign_deadline: str
    _contract_bytes: bytes = dataclass_field(repr=False)

    @property
    def by_id(self) -> dict[str, GoalContract]:
        return {goal.goal_id: goal for goal in self.goals}


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    mission_id: str
    contract_digest: str
    campaign_deadline: str
    dependency_order: tuple[str, ...]
    goal_task_map: tuple[tuple[str, str], ...]
    goal_contract_digests: tuple[tuple[str, str], ...]
    canary_goal_id: str
    canary_task_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "authority_binding": {
                "correlation_formula": (
                    "stable_id('mission_dispatch', mission_id, task_id, 'default')"
                ),
                "lease_cash_ceiling_usd": 0,
                "manifest_must_repeat": [
                    "campaign_id",
                    "campaign_deadline",
                    "contract_digest",
                    "goal_contract_digests",
                    "goal_task_map",
                ],
                "required": True,
                "readiness_source": "typed_mission_campaign_authority_and_lease",
                "required_actions": [
                    "mission_control_dispatch",
                    "mission_control_workspace",
                ],
                "seed_dispatch_fields": "immutable_provenance_not_runtime_readiness",
                "status": "separate_governed_follow_up_required",
                "requires": [
                    "explicit_pinned_principal_per_goal",
                    "exact_relative_workspace_and_allowed_files",
                    "mission_control_dispatch_and_workspace_actions",
                    "task_bound_zero_dollar_execution_lease",
                    "stable_mission_dispatch_correlation",
                    "idempotent_crash_reconciliation",
                ],
            },
            "campaign_deadline": self.campaign_deadline,
            "canary_goal_id": self.canary_goal_id,
            "canary_task_id": self.canary_task_id,
            "contract_digest": self.contract_digest,
            "dependency_order": list(self.dependency_order),
            "dispatch_blocker": DISPATCH_BLOCKER,
            "dispatch_ready": False,
            "goal_contract_digests": dict(self.goal_contract_digests),
            "goal_task_map": dict(self.goal_task_map),
            "mission_id": self.mission_id,
            "proves_independent_acceptance": False,
            "proves_model_execution": False,
            "status": "initialized",
            "task_count": len(self.goal_task_map),
        }

    def to_json(self) -> str:
        return (
            json.dumps(
                self.to_dict(),
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        )


@dataclass(frozen=True, slots=True)
class _ObservedBootstrap:
    mission: MissionView | None
    tasks_by_goal: dict[str, Task]


class CampaignBootstrapLock:
    """Opaque proof that the canonical cross-process bootstrap lock is held."""

    __slots__ = ("_active", "_async_lock", "_descriptor", "path")

    def __init__(self, path: Path, descriptor: int, sentinel: object) -> None:
        if sentinel is not _LOCK_CONSTRUCTION_SENTINEL:
            raise BootstrapLockError(
                "CampaignBootstrapLock can only be created by campaign_bootstrap_lock"
            )
        self.path = path
        self._descriptor = descriptor
        self._active = True
        self._async_lock = asyncio.Lock()

    def _require_active(self, expected_path: Path) -> None:
        if not self._active or self.path != expected_path:
            raise BootstrapLockError(
                "initializer requires the active canonical campaign bootstrap lock"
            )
        details = os.fstat(self._descriptor)
        observed = os.lstat(self.path)
        if (details.st_dev, details.st_ino) != (observed.st_dev, observed.st_ino):
            raise BootstrapLockError("campaign bootstrap lock identity changed")


def _absolute_lexical_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(Path(path).expanduser())))


def _require_safe_lock_file(descriptor: int) -> None:
    details = os.fstat(descriptor)
    if not stat.S_ISREG(details.st_mode):
        raise BootstrapLockError("bootstrap lock must be a regular file")
    if details.st_nlink != 1:
        raise BootstrapLockError("bootstrap lock must have exactly one hard link")
    if hasattr(os, "getuid") and details.st_uid != os.getuid():
        raise BootstrapLockError("bootstrap lock must be owned by the current account")
    if stat.S_IMODE(details.st_mode) & 0o022:
        raise BootstrapLockError("bootstrap lock must not be group/world writable")


@contextmanager
def campaign_bootstrap_lock(path: Path | str) -> Iterator[CampaignBootstrapLock]:
    """Acquire the mandatory canonical lock used by every bootstrap API call."""
    candidate = _absolute_lexical_path(path)
    candidate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise BootstrapLockError("bootstrap lock requires O_NOFOLLOW support")
    flags = os.O_CREAT | os.O_RDWR | nofollow | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(os.fspath(candidate), flags, 0o600)
    except OSError as exc:
        raise BootstrapLockError(f"cannot securely open bootstrap lock: {exc}") from exc
    acquired = False
    token: CampaignBootstrapLock | None = None
    try:
        _require_safe_lock_file(descriptor)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BootstrapLockError("another SADHANA bootstrap is active") from exc
        acquired = True
        token = CampaignBootstrapLock(
            candidate,
            descriptor,
            _LOCK_CONSTRUCTION_SENTINEL,
        )
        yield token
    finally:
        if token is not None:
            token._active = False
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GoalContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise GoalContractError(f"non-finite JSON number is forbidden: {value}")


def _exact_keys(value: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GoalContractError(f"{label} must be an object")
    observed = frozenset(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise GoalContractError(
            f"{label} keys differ; missing={missing}, extra={extra}"
        )
    return value


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise GoalContractError(f"{label} must be a canonical non-empty string")
    return value


def _string_list(
    value: Any, label: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise GoalContractError(f"{label} must be a string list")
    result = tuple(_required_text(item, f"{label} item") for item in value)
    if len(set(result)) != len(result):
        raise GoalContractError(f"{label} contains a duplicate")
    return result


def _bounded_int(value: Any, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise GoalContractError(f"{label} must be an integer >= {minimum}")
    return value


def _zero_cash(value: Any, label: str) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value != 0
    ):
        raise GoalContractError(f"{label} must be exactly zero")
    return value


def _aware_datetime(value: Any, label: str) -> str:
    text = _required_text(value, label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise GoalContractError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise GoalContractError(f"{label} must include a timezone")
    return text


def _canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GoalContractError("contract value is not canonical JSON") from exc
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_portfolio_policy(value: Any) -> None:
    policy = _exact_keys(
        value,
        frozenset(
            {
                "allocation",
                "default_attempt_ceiling",
                "external_cash_ceiling_usd_without_new_warrant",
                "fitness_rule",
                "global_concurrency_ceiling",
            }
        ),
        "portfolio_policy",
    )
    allocation = _exact_keys(
        policy["allocation"],
        frozenset(
            {
                "fair_goal_coverage_percent",
                "verification_exploration_recovery_percent",
                "verified_value_priority_percent",
            }
        ),
        "portfolio_policy.allocation",
    )
    percentages = [
        _bounded_int(value, f"portfolio_policy.allocation.{key}", minimum=0)
        for key, value in allocation.items()
    ]
    if any(value > 100 for value in percentages) or sum(percentages) != 100:
        raise GoalContractError("portfolio allocation percentages must total 100")
    default = _exact_keys(
        policy["default_attempt_ceiling"],
        frozenset(
            {"concurrency", "input_tokens", "output_tokens", "retries", "wall_seconds"}
        ),
        "portfolio_policy.default_attempt_ceiling",
    )
    for key, value in default.items():
        _bounded_int(
            value,
            f"portfolio_policy.default_attempt_ceiling.{key}",
            minimum=0 if key == "retries" else 1,
        )
    _zero_cash(
        policy["external_cash_ceiling_usd_without_new_warrant"],
        "portfolio_policy.external_cash_ceiling_usd_without_new_warrant",
    )
    _bounded_int(
        policy["global_concurrency_ceiling"],
        "portfolio_policy.global_concurrency_ceiling",
    )
    _required_text(policy["fitness_rule"], "portfolio_policy.fitness_rule")


def _parse_goal(value: Any, index: int) -> GoalContract:
    raw = _exact_keys(value, _GOAL_KEYS, f"goals[{index}]")
    for field in _GOAL_TEXT_FIELDS:
        _required_text(raw[field], f"goals[{index}].{field}")
    for field in _GOAL_LIST_FIELDS:
        _string_list(raw[field], f"goals[{index}].{field}")
    goal_id = str(raw["goal_id"])
    if not _GOAL_ID_RE.fullmatch(goal_id):
        raise GoalContractError(f"goals[{index}].goal_id is not canonical")
    priority = str(raw["priority"])
    if priority not in _PRIORITY:
        raise GoalContractError(f"goals[{index}].priority is unsupported")
    deadline = _aware_datetime(raw["deadline"], f"goals[{index}].deadline")
    ceilings = _exact_keys(
        raw["ceilings"],
        frozenset({"attempts", "cash_usd", "concurrency", "default_attempt_policy"}),
        f"goals[{index}].ceilings",
    )
    attempts = _bounded_int(ceilings["attempts"], f"goals[{index}].ceilings.attempts")
    cash_usd = _zero_cash(ceilings["cash_usd"], f"goals[{index}].ceilings.cash_usd")
    concurrency = _bounded_int(
        ceilings["concurrency"], f"goals[{index}].ceilings.concurrency"
    )
    default_attempt_policy = _required_text(
        ceilings["default_attempt_policy"],
        f"goals[{index}].ceilings.default_attempt_policy",
    )
    scope = _exact_keys(
        raw["scope"],
        frozenset({"code", "data", "external", "runtime"}),
        f"goals[{index}].scope",
    )
    for field, entries in scope.items():
        _string_list(entries, f"goals[{index}].scope.{field}")
    baseline = _exact_keys(
        raw["recorded_baseline"],
        frozenset({"authority", "claim", "state"}),
        f"goals[{index}].recorded_baseline",
    )
    for field, text in baseline.items():
        _required_text(text, f"goals[{index}].recorded_baseline.{field}")
    return GoalContract(
        goal_id=goal_id,
        priority=priority,
        deadline=deadline,
        definition_of_done=str(raw["definition_of_done"]),
        dependencies=tuple(str(item) for item in raw["dependencies"]),
        attempts=attempts,
        cash_usd=cash_usd,
        concurrency=concurrency,
        default_attempt_policy=default_attempt_policy,
        content_digest=_canonical_digest(raw),
    )


def _dependency_order(goals: tuple[GoalContract, ...]) -> tuple[str, ...]:
    by_id = {goal.goal_id: goal for goal in goals}
    for goal in goals:
        unknown = sorted(set(goal.dependencies) - set(by_id))
        if unknown:
            raise GoalContractError(
                f"goal {goal.goal_id} has unknown dependencies: {unknown}"
            )
        if goal.goal_id in goal.dependencies:
            raise GoalContractError(f"goal {goal.goal_id} depends on itself")
    remaining = {goal_id: set(goal.dependencies) for goal_id, goal in by_id.items()}
    ordered: list[str] = []
    while remaining:
        ready = sorted(goal_id for goal_id, deps in remaining.items() if not deps)
        if not ready:
            raise GoalContractError("goal dependency graph contains a cycle")
        for goal_id in ready:
            ordered.append(goal_id)
            remaining.pop(goal_id)
        for dependencies in remaining.values():
            dependencies.difference_update(ready)
    return tuple(ordered)


def _decode_goal_contract(raw_bytes: bytes, *, expected_sha256: str) -> GoalPortfolio:
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise GoalContractError("expected contract digest must be lowercase sha256")
    observed_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if observed_sha256 != expected_sha256:
        raise GoalContractError(
            f"goal contract digest mismatch: expected {expected_sha256}, "
            f"observed {observed_sha256}"
        )
    try:
        text = raw_bytes.decode("utf-8")
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GoalContractError("goal contract must be unique-key UTF-8 JSON") from exc
    root = _exact_keys(document, _TOP_LEVEL_KEYS, "goal contract")
    if root["schema"] != GOAL_CONTRACT_SCHEMA:
        raise GoalContractError("goal contract schema is not the pinned v1 schema")
    if root["campaign_id"] != EXPECTED_CAMPAIGN_ID:
        raise GoalContractError("goal contract campaign_id is not SADHANA 10")
    if root["status"] != EXPECTED_CONTRACT_STATUS:
        raise GoalContractError(
            "goal contract status is not the pinned provisional state"
        )
    generated_at = _aware_datetime(root["generated_at"], "generated_at")
    _validate_portfolio_policy(root["portfolio_policy"])
    raw_goals = root["goals"]
    if not isinstance(raw_goals, list) or len(raw_goals) != len(EXPECTED_GOAL_IDS):
        raise GoalContractError("goal contract must contain exactly ten goals")
    goals = tuple(_parse_goal(value, index) for index, value in enumerate(raw_goals))
    goal_ids = tuple(goal.goal_id for goal in goals)
    if goal_ids != EXPECTED_GOAL_IDS:
        raise GoalContractError(
            "goal contract goal identities/order differ from the pin"
        )
    dependency_order = _dependency_order(goals)
    campaign_deadline = max(
        goals,
        key=lambda goal: datetime.fromisoformat(goal.deadline),
    ).deadline
    return GoalPortfolio(
        campaign_id=EXPECTED_CAMPAIGN_ID,
        schema=GOAL_CONTRACT_SCHEMA,
        status=EXPECTED_CONTRACT_STATUS,
        generated_at=generated_at,
        digest=f"sha256:{observed_sha256}",
        goals=goals,
        dependency_order=dependency_order,
        campaign_deadline=campaign_deadline,
        _contract_bytes=raw_bytes,
    )


def _secure_read_contract(path: Path | str) -> bytes:
    candidate = Path(path).expanduser()
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise GoalContractError("contract custody requires O_NOFOLLOW support")
    flags = os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(os.fspath(candidate), flags)
    except OSError as exc:
        raise GoalContractError(f"cannot securely open goal contract: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise GoalContractError("goal contract must be a regular file")
        if before.st_nlink != 1:
            raise GoalContractError("goal contract must have exactly one hard link")
        if hasattr(os, "getuid") and before.st_uid != os.getuid():
            raise GoalContractError(
                "goal contract must be owned by the current account"
            )
        if stat.S_IMODE(before.st_mode) & 0o022:
            raise GoalContractError("goal contract must not be group/world writable")
        if before.st_size <= 0 or before.st_size > MAX_CONTRACT_BYTES:
            raise GoalContractError("goal contract size is outside the bounded range")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                raise GoalContractError("goal contract ended before its stated size")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise GoalContractError("goal contract grew during the bounded read")
        after = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
        )
        if any(
            getattr(before, field) != getattr(after, field) for field in stable_fields
        ):
            raise GoalContractError("goal contract changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def load_goal_contract(path: Path | str) -> GoalPortfolio:
    """Load only the exact contract bytes authorized for this campaign."""
    return _decode_goal_contract(
        _secure_read_contract(path),
        expected_sha256=EXPECTED_CONTRACT_SHA256,
    )


def _mission_metadata(portfolio: GoalPortfolio) -> dict[str, Any]:
    return {
        "sadhana_bootstrap_schema": BOOTSTRAP_SCHEMA,
        "goal_contract_schema": portfolio.schema,
        "goal_contract_sha256": portfolio.digest,
        "campaign_id": portfolio.campaign_id,
        "campaign_deadline": portfolio.campaign_deadline,
        "goal_count": len(portfolio.goals),
        "dispatch_ready": False,
        "dispatch_blocker": DISPATCH_BLOCKER,
    }


def _task_metadata(portfolio: GoalPortfolio, goal: GoalContract) -> dict[str, Any]:
    return {
        "sadhana_bootstrap_schema": BOOTSTRAP_SCHEMA,
        "goal_contract_schema": portfolio.schema,
        "goal_contract_sha256": goal.content_digest,
        "portfolio_contract_sha256": portfolio.digest,
        "campaign_id": portfolio.campaign_id,
        "goal_id": goal.goal_id,
        "goal_dependencies": list(goal.dependencies),
        "goal_priority": goal.priority,
        "goal_deadline": goal.deadline,
        "attempt_ceiling": goal.attempts,
        "cash_ceiling_usd": goal.cash_usd,
        "concurrency_ceiling": goal.concurrency,
        "default_attempt_policy": goal.default_attempt_policy,
        "dispatch_ready": False,
        "dispatch_blocker": DISPATCH_BLOCKER,
    }


def task_idempotency_key(portfolio: GoalPortfolio, goal_id: str) -> str:
    return stable_id("sadhana_goal", portfolio.campaign_id, portfolio.digest, goal_id)


def _expected_mission_fields(
    portfolio: GoalPortfolio, operator_id: str
) -> dict[str, Any]:
    return {
        "mission_id": portfolio.campaign_id,
        "session_id": f"mission:{portfolio.campaign_id}",
        "title": MISSION_TITLE,
        "goal": MISSION_GOAL,
        "operator_id": operator_id,
        "status": "active",
    }


def _require_metadata_subset(
    observed: dict[str, Any],
    expected: dict[str, Any],
    label: str,
) -> None:
    conflicts = {
        key: {"expected": value, "observed": observed.get(key)}
        for key, value in expected.items()
        if observed.get(key) != value
    }
    if conflicts:
        raise MissionControlError(f"{label} metadata conflicts: {conflicts}")


def _validate_mission(
    mission: MissionView,
    portfolio: GoalPortfolio,
    operator_id: str,
) -> None:
    expected = _expected_mission_fields(portfolio, operator_id)
    conflicts = {
        key: {"expected": value, "observed": getattr(mission, key)}
        for key, value in expected.items()
        if getattr(mission, key) != value
    }
    if conflicts:
        raise MissionControlError(f"SADHANA mission conflicts: {conflicts}")
    _require_metadata_subset(
        mission.metadata,
        {
            **_mission_metadata(portfolio),
            "schema_version": SCHEMA_VERSION,
            "mission_id": portfolio.campaign_id,
            "title": MISSION_TITLE,
            "goal": MISSION_GOAL,
        },
        "SADHANA mission",
    )
    creation_hash = mission.metadata.get("mission_creation_hash")
    if not isinstance(creation_hash, str) or not _SHA256_RE.fullmatch(creation_hash):
        raise MissionControlError("SADHANA mission creation hash is invalid")


def _task_is_in_bootstrap_namespace(
    task: Task,
    portfolio: GoalPortfolio,
    expected_keys: set[str],
) -> bool:
    metadata = task.metadata
    return bool(
        metadata.get("mission_id") == portfolio.campaign_id
        or metadata.get("campaign_id") == portfolio.campaign_id
        or metadata.get("sadhana_bootstrap_schema") == BOOTSTRAP_SCHEMA
        or metadata.get("mission_task_idempotency_key") in expected_keys
    )


def _validate_existing_task(
    task: Task,
    portfolio: GoalPortfolio,
    goal: GoalContract,
    tasks_by_goal: dict[str, Task],
) -> None:
    dependency_ids: list[str] = []
    for dependency in goal.dependencies:
        dependency_task = tasks_by_goal.get(dependency)
        if dependency_task is None:
            raise MissionControlError(
                f"partial bootstrap is not dependency-closed: {goal.goal_id} "
                f"exists before {dependency}"
            )
        dependency_ids.append(dependency_task.id)
    expected_fields = {
        "title": goal.goal_id,
        "description": goal.definition_of_done,
        "priority": _PRIORITY[goal.priority],
        "created_by": BOOTSTRAP_CREATED_BY,
    }
    conflicts = {
        key: {"expected": value, "observed": getattr(task, key)}
        for key, value in expected_fields.items()
        if getattr(task, key) != value
    }
    if conflicts:
        raise MissionControlError(f"task {goal.goal_id} conflicts: {conflicts}")
    if sorted(task.depends_on) != sorted(dependency_ids):
        raise MissionControlError(
            f"task {goal.goal_id} dependencies conflict: "
            f"expected={sorted(dependency_ids)}, observed={sorted(task.depends_on)}"
        )
    _require_metadata_subset(
        task.metadata,
        {
            **_task_metadata(portfolio, goal),
            "schema_version": SCHEMA_VERSION,
            "mission_id": portfolio.campaign_id,
            "mission_task_idempotency_key": task_idempotency_key(
                portfolio, goal.goal_id
            ),
        },
        f"task {goal.goal_id}",
    )
    creation_hash = task.metadata.get("mission_task_creation_hash")
    if not isinstance(creation_hash, str) or not _SHA256_RE.fullmatch(creation_hash):
        raise MissionControlError(f"task {goal.goal_id} creation hash is invalid")


async def _inspect_bootstrap(
    portfolio: GoalPortfolio,
    control: MissionControl,
    board: TaskBoard,
    operator_id: str,
) -> _ObservedBootstrap:
    mission = await control.get_mission(portfolio.campaign_id)
    scanned = await board.list_tasks(limit=TASK_SCAN_LIMIT + 1)
    if len(scanned) > TASK_SCAN_LIMIT:
        raise MissionControlError("bootstrap task scan saturated")
    expected_keys = {
        task_idempotency_key(portfolio, goal.goal_id) for goal in portfolio.goals
    }
    tasks_by_goal: dict[str, Task] = {}
    for task in scanned:
        if not _task_is_in_bootstrap_namespace(task, portfolio, expected_keys):
            continue
        goal_id = task.metadata.get("goal_id")
        key = task.metadata.get("mission_task_idempotency_key")
        if not isinstance(goal_id, str) or goal_id not in portfolio.by_id:
            raise MissionControlError(
                f"foreign task {task.id!r} occupies the SADHANA mission namespace"
            )
        expected_key = task_idempotency_key(portfolio, goal_id)
        if key != expected_key:
            raise MissionControlError(
                f"task {task.id!r} has conflicting SADHANA idempotency identity"
            )
        if goal_id in tasks_by_goal:
            raise MissionControlError(f"goal {goal_id} maps to multiple tasks")
        tasks_by_goal[goal_id] = task
    if mission is None:
        if tasks_by_goal:
            raise MissionControlError("SADHANA tasks exist without their mission")
        return _ObservedBootstrap(mission=None, tasks_by_goal={})
    _validate_mission(mission, portfolio, operator_id)
    for goal_id in portfolio.dependency_order:
        task = tasks_by_goal.get(goal_id)
        if task is not None:
            _validate_existing_task(
                task,
                portfolio,
                portfolio.by_id[goal_id],
                tasks_by_goal,
            )
    return _ObservedBootstrap(mission=mission, tasks_by_goal=tasks_by_goal)


async def _create_or_verify_task(
    portfolio: GoalPortfolio,
    goal: GoalContract,
    control: MissionControl,
    board: TaskBoard,
    task_ids: dict[str, str],
) -> Task:
    dependency_ids = [task_ids[dependency] for dependency in goal.dependencies]
    view = await control.create_task(
        portfolio.campaign_id,
        title=goal.goal_id,
        description=goal.definition_of_done,
        priority=_PRIORITY[goal.priority],
        created_by=BOOTSTRAP_CREATED_BY,
        depends_on=dependency_ids,
        idempotency_key=task_idempotency_key(portfolio, goal.goal_id),
        metadata=_task_metadata(portfolio, goal),
    )
    task = await board.get(view.task_id)
    if task is None:
        raise MissionControlError(f"task {goal.goal_id} disappeared after creation")
    return task


def _revalidate_portfolio(portfolio: GoalPortfolio) -> GoalPortfolio:
    if not isinstance(portfolio, GoalPortfolio):
        raise GoalContractError("initializer requires a validated GoalPortfolio")
    validated = _decode_goal_contract(
        portfolio._contract_bytes,
        expected_sha256=EXPECTED_CONTRACT_SHA256,
    )
    if validated != portfolio:
        raise GoalContractError(
            "GoalPortfolio differs from its exact pinned contract bytes"
        )
    return validated


def _canonical_owner_board(control: MissionControl) -> tuple[TaskBoard, Path]:
    # MissionControl has no public owner accessor.  Deriving its sole board here
    # is safer than accepting a second caller-supplied board that can diverge.
    board = getattr(control, "_board", None)
    if not isinstance(board, TaskBoard):
        raise MissionControlError("MissionControl has no canonical TaskBoard owner")
    task_db = _absolute_lexical_path(board._db_path)
    if task_db.name != "tasks.db" or task_db.parent.name != "db":
        raise MissionControlError(
            "TaskBoard must use the canonical <state-dir>/db/tasks.db path"
        )
    lock_path = task_db.parent.parent / "locks" / BOOTSTRAP_LOCK_NAME
    return board, lock_path


async def initialize_sadhana_campaign(
    portfolio: GoalPortfolio,
    control: MissionControl,
    *,
    operator_id: str = "operator",
    lock: CampaignBootstrapLock,
) -> BootstrapResult:
    """Create or verify the exact mission and ten tasks without dispatch authority."""
    portfolio = _revalidate_portfolio(portfolio)
    board, expected_lock_path = _canonical_owner_board(control)
    lock._require_active(expected_lock_path)
    operator_id = str(operator_id or "").strip()
    if not operator_id or any(character.isspace() for character in operator_id):
        raise MissionControlError("operator_id must be a canonical identifier")
    async with lock._async_lock:
        lock._require_active(expected_lock_path)
        observed = await _inspect_bootstrap(portfolio, control, board, operator_id)

        await control.create_mission(
            portfolio.campaign_id,
            title=MISSION_TITLE,
            goal=MISSION_GOAL,
            operator_id=operator_id,
            metadata=_mission_metadata(portfolio),
        )
        task_ids = {
            goal_id: task.id for goal_id, task in observed.tasks_by_goal.items()
        }

        # Verify every existing creation hash before creating one missing task.
        for goal_id in portfolio.dependency_order:
            if goal_id not in observed.tasks_by_goal:
                continue
            task = await _create_or_verify_task(
                portfolio,
                portfolio.by_id[goal_id],
                control,
                board,
                task_ids,
            )
            if task.id != task_ids[goal_id]:
                raise MissionControlError(f"goal {goal_id} changed task identity")

        for goal_id in portfolio.dependency_order:
            if goal_id in task_ids:
                continue
            task = await _create_or_verify_task(
                portfolio,
                portfolio.by_id[goal_id],
                control,
                board,
                task_ids,
            )
            task_ids[goal_id] = task.id

        final = await _inspect_bootstrap(portfolio, control, board, operator_id)
        if len(final.tasks_by_goal) != len(EXPECTED_GOAL_IDS):
            raise MissionControlError("bootstrap did not converge to exactly ten tasks")
        final_ids = {
            goal_id: final.tasks_by_goal[goal_id].id for goal_id in EXPECTED_GOAL_IDS
        }
        if final_ids != task_ids:
            raise MissionControlError("goal-to-task mapping changed during bootstrap")
        return BootstrapResult(
            mission_id=portfolio.campaign_id,
            contract_digest=portfolio.digest,
            campaign_deadline=portfolio.campaign_deadline,
            dependency_order=portfolio.dependency_order,
            goal_task_map=tuple(
                (goal_id, final_ids[goal_id]) for goal_id in EXPECTED_GOAL_IDS
            ),
            goal_contract_digests=tuple(
                (goal.goal_id, goal.content_digest) for goal in portfolio.goals
            ),
            canary_goal_id=CANARY_GOAL_ID,
            canary_task_id=final_ids[CANARY_GOAL_ID],
        )


__all__ = [
    "BOOTSTRAP_SCHEMA",
    "BOOTSTRAP_LOCK_NAME",
    "BootstrapLockError",
    "BootstrapResult",
    "CANARY_GOAL_ID",
    "CampaignBootstrapLock",
    "DISPATCH_BLOCKER",
    "EXPECTED_CAMPAIGN_ID",
    "EXPECTED_CONTRACT_DIGEST",
    "EXPECTED_CONTRACT_SHA256",
    "EXPECTED_GOAL_IDS",
    "GOAL_CONTRACT_SCHEMA",
    "GoalContract",
    "GoalContractError",
    "GoalPortfolio",
    "campaign_bootstrap_lock",
    "initialize_sadhana_campaign",
    "load_goal_contract",
    "task_idempotency_key",
]
