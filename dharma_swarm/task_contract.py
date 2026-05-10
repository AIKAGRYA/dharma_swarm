"""Canonical metadata-first task execution contract.

This module is tranche-one compatibility infrastructure:

- keep the existing task board schema alive
- make the task metadata carry a stable execution contract
- normalize aliases so old and new callers converge on one shape
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dharma_swarm.build_authority import BuildLane, SettlementState
from dharma_swarm.models import TaskStatus

TASK_CONTRACT_VERSION = "task_contract_v1"

CANONICAL_ARTIFACT_KEY = "target_artifact"
CANONICAL_ARTIFACTS_KEY = "target_artifacts"

_TEXT_KEYS = (
    "task_class",
    "owner_lane",
    "campaign_id",
    "artifact_id",
    "artifact_kind",
    "outcome_id",
    "done_condition",
    "no_artifact_justification",
    "settlement_state",
    "source_task_id",
)
_BOOL_KEYS = ("requires_verifier",)
_ARTIFACT_SINGLE_KEYS = (
    "target_file",
    "target_path",
    "artifact_path",
    "required_artifact",
    "target_artifact",
)
_ARTIFACT_MULTI_KEYS = (
    "required_artifacts",
    "artifact_paths",
    "target_files",
    "target_artifacts",
)

_TASK_STATUS_TO_SETTLEMENT: dict[str, str] = {
    TaskStatus.PENDING.value: SettlementState.QUEUED.value,
    TaskStatus.ASSIGNED.value: SettlementState.CLAIMED.value,
    TaskStatus.RUNNING.value: SettlementState.IN_PROGRESS.value,
    TaskStatus.COMPLETED.value: SettlementState.SUBMITTED.value,
    TaskStatus.FAILED.value: SettlementState.BLOCKED.value,
    TaskStatus.CANCELLED.value: SettlementState.ABANDONED.value,
}

_STRICT_BUILD_TASK_CLASSES = frozenset({"build", "integrate", "operate"})
_TEXT_ONLY_TASK_CLASSES = frozenset({"research", "verify"})
_TEXT_ONLY_ARTIFACT_KINDS = frozenset(
    {"memo", "report", "spec", "ledger", "brief", "document"}
)
_WORKER_BUILD_LANES = frozenset(
    {
        BuildLane.CONDUCTOR,
        BuildLane.BUILDER,
        BuildLane.RESEARCHER,
        BuildLane.VERIFIER,
        BuildLane.GATEWAY,
    }
)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_str_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        raw = values
    else:
        raw = [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def settlement_state_for_status(status: TaskStatus | str | None) -> str | None:
    if isinstance(status, TaskStatus):
        text = status.value
    else:
        text = _clean_text(status)
    if not text:
        return None
    return _TASK_STATUS_TO_SETTLEMENT.get(text)


def required_artifact_targets(metadata: dict[str, Any] | None) -> list[str]:
    meta = dict(metadata or {})
    values: list[str] = []
    for key in _ARTIFACT_SINGLE_KEYS:
        values.extend(_clean_str_list(meta.get(key)))
    for key in _ARTIFACT_MULTI_KEYS:
        values.extend(_clean_str_list(meta.get(key)))

    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        path = str(Path(raw).expanduser())
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _normalized_build_lane(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return BuildLane(text).value
    except ValueError:
        return None


def _normalized_settlement_state(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return SettlementState(text).value
    except ValueError:
        return None


def owner_lane(metadata: dict[str, Any] | None) -> str | None:
    return _normalized_build_lane((metadata or {}).get("owner_lane"))


def task_class(metadata: dict[str, Any] | None) -> str | None:
    return _clean_text((metadata or {}).get("task_class"))


def artifact_kind(metadata: dict[str, Any] | None) -> str | None:
    return _clean_text((metadata or {}).get("artifact_kind"))


def no_artifact_justification(metadata: dict[str, Any] | None) -> str | None:
    return _clean_text((metadata or {}).get("no_artifact_justification"))


def allowed_claim_lanes(metadata: dict[str, Any] | None) -> tuple[BuildLane, ...]:
    meta = dict(metadata or {})
    lane = owner_lane(meta)
    if lane is not None and lane in {item.value for item in _WORKER_BUILD_LANES}:
        return (BuildLane(lane),)

    klass = task_class(meta)
    if bool(meta.get("requires_verifier")) or klass == "verify":
        return (BuildLane.VERIFIER,)
    if klass == "research":
        return (BuildLane.RESEARCHER,)
    if required_artifact_targets(meta) or klass in _STRICT_BUILD_TASK_CLASSES:
        return (BuildLane.BUILDER, BuildLane.GATEWAY)
    return ()


def requires_tooling_lane(metadata: dict[str, Any] | None) -> bool:
    meta = dict(metadata or {})
    if required_artifact_targets(meta):
        return True
    return bool(allowed_claim_lanes(meta)) and any(
        lane in {BuildLane.BUILDER, BuildLane.GATEWAY}
        for lane in allowed_claim_lanes(meta)
    )


def allows_text_result_completion(metadata: dict[str, Any] | None) -> bool:
    meta = dict(metadata or {})
    if no_artifact_justification(meta):
        return True
    if required_artifact_targets(meta):
        return False
    klass = task_class(meta)
    if klass in _TEXT_ONLY_TASK_CLASSES:
        return True
    kind = artifact_kind(meta)
    if kind in _TEXT_ONLY_ARTIFACT_KINDS:
        return True
    return not requires_tooling_lane(meta)


def carries_execution_contract(metadata: dict[str, Any] | None) -> bool:
    meta = dict(metadata or {})
    if not meta:
        return False
    return any(
        key in meta
        for key in (
            "contract_version",
            "owner_lane",
            "task_class",
            "settlement_state",
            "done_condition",
            "artifact_id",
            "artifact_kind",
            "outcome_id",
            "source_task_id",
            CANONICAL_ARTIFACT_KEY,
            CANONICAL_ARTIFACTS_KEY,
        )
    )


def normalize_task_contract_metadata(
    metadata: dict[str, Any] | None,
    *,
    status: TaskStatus | str | None = None,
) -> dict[str, Any]:
    meta = dict(metadata or {})

    for key in _TEXT_KEYS:
        text = _clean_text(meta.get(key))
        if text is None:
            meta.pop(key, None)
        else:
            meta[key] = text

    for key in _BOOL_KEYS:
        if key in meta:
            meta[key] = bool(meta[key])

    normalized_lane = _normalized_build_lane(meta.get("owner_lane"))
    if normalized_lane is None:
        meta.pop("owner_lane", None)
    else:
        meta["owner_lane"] = normalized_lane

    normalized_settlement = _normalized_settlement_state(meta.get("settlement_state"))
    if normalized_settlement is None:
        meta.pop("settlement_state", None)
    else:
        meta["settlement_state"] = normalized_settlement

    artifact_targets = required_artifact_targets(meta)
    if artifact_targets:
        meta[CANONICAL_ARTIFACT_KEY] = artifact_targets[0]
        meta["artifact_path"] = artifact_targets[0]
        meta[CANONICAL_ARTIFACTS_KEY] = artifact_targets
        meta["artifact_paths"] = artifact_targets
    else:
        meta.pop(CANONICAL_ARTIFACT_KEY, None)
        meta.pop("artifact_path", None)
        meta.pop(CANONICAL_ARTIFACTS_KEY, None)
        meta.pop("artifact_paths", None)

    if _clean_text(meta.get("task_class")) is None:
        if meta.get("owner_lane") == BuildLane.RESEARCHER.value:
            meta["task_class"] = "research"
        elif meta.get("owner_lane") == BuildLane.VERIFIER.value:
            meta["task_class"] = "verify"
        elif artifact_targets or meta.get("owner_lane") in {
            BuildLane.BUILDER.value,
            BuildLane.GATEWAY.value,
        }:
            meta["task_class"] = "build"

    if _clean_text(meta.get("owner_lane")) is None:
        if _clean_text(meta.get("task_class")) == "research":
            meta["owner_lane"] = BuildLane.RESEARCHER.value
        elif _clean_text(meta.get("task_class")) == "verify":
            meta["owner_lane"] = BuildLane.VERIFIER.value
        elif artifact_targets or _clean_text(meta.get("task_class")) in _STRICT_BUILD_TASK_CLASSES:
            meta["owner_lane"] = BuildLane.BUILDER.value

    settlement_state = settlement_state_for_status(status)
    if settlement_state is not None:
        meta["settlement_state"] = settlement_state
    elif _clean_text(meta.get("settlement_state")) is None:
        meta["settlement_state"] = SettlementState.QUEUED.value

    if artifact_targets and "requires_verifier" not in meta:
        meta["requires_verifier"] = True

    if _clean_text(meta.get("done_condition")) is None:
        if artifact_targets:
            meta["done_condition"] = "artifact_written_or_explicit_no_artifact_reason"
        else:
            meta["done_condition"] = "explicit_result_or_no_artifact_reason"

    meta["contract_version"] = TASK_CONTRACT_VERSION
    return meta


def merge_task_contract_metadata(
    base: dict[str, Any] | None,
    overlay: dict[str, Any] | None,
    *,
    status: TaskStatus | str | None = None,
) -> dict[str, Any]:
    merged = dict(base or {})
    if isinstance(overlay, dict):
        merged.update(overlay)
    return normalize_task_contract_metadata(merged, status=status)


__all__ = [
    "CANONICAL_ARTIFACT_KEY",
    "CANONICAL_ARTIFACTS_KEY",
    "TASK_CONTRACT_VERSION",
    "allowed_claim_lanes",
    "allows_text_result_completion",
    "artifact_kind",
    "carries_execution_contract",
    "merge_task_contract_metadata",
    "no_artifact_justification",
    "normalize_task_contract_metadata",
    "owner_lane",
    "required_artifact_targets",
    "requires_tooling_lane",
    "settlement_state_for_status",
    "task_class",
]
