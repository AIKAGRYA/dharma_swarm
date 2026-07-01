"""Fail-closed preregistration and scaffold-parity receipt anchors.

These helpers only build deterministic receipt payloads for the Forge promotion
battery.  They do not sign receipts, verify signer authority, run grading, or
grant promotion.  ``verify_promotion`` remains the sole live-apply arbiter.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .receipts import scaffold_parity_hash
from .signals import canonical_sha256

PREREGISTRATION_SCHEMA = "forge_v2.preregistration_receipt.v1"
SCAFFOLD_PARITY_SCHEMA = "forge_v2.scaffold_parity_receipt.v1"
PREREGISTRATION_NAME = "preregistration"
SCAFFOLD_PARITY_NAME = "scaffold_parity_proof"
MIN_CONFIRM_N = 500
MIN_EFFECT = 0.05
DEFAULT_PREREGISTERED_MDE = 0.056
CANONICAL_CONTROL_ARMS = (
    "frontier_single_full_budget",
    "best_of_n_same_model",
    "same_budget_self_moa",
    "planner_builder_verifier_no_a2a",
    "full_a2a_swarm",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _base_receipt(*, schema: str, name: str, payload: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
    clean_blockers = sorted(set(blockers))
    passed = not clean_blockers
    receipt = {
        "schema": schema,
        "name": name,
        "decision": "pass" if passed else "refused",
        "promotion_gate_satisfied": passed,
        "payload": payload,
        "blockers": clean_blockers,
    }
    receipt["payload_sha256"] = canonical_sha256(receipt)
    return receipt


def evaluate_preregistration_anchor(
    plan: Mapping[str, Any],
    *,
    min_confirm_n: int = MIN_CONFIRM_N,
    min_effect: float = MIN_EFFECT,
    default_mde: float = DEFAULT_PREREGISTERED_MDE,
    required_controls: Iterable[str] = CANONICAL_CONTROL_ARMS,
) -> dict[str, Any]:
    """Build a preregistration receipt for a frozen full-CONFIRM plan.

    The predicate is intentionally simple and conservative: the plan must name
    its candidate, epoch, taskbed, metric, CONFIRM split, full task count,
    effect target, MDE, and canonical control arms before a run can later claim
    this preregistration receipt.
    """
    mde_value = plan.get("pre_registered_mde")
    if mde_value is None:
        mde_value = plan.get("preregistered_mde")
    payload = {
        "run_id": str(plan.get("run_id") or ""),
        "candidate_id": str(plan.get("candidate_id") or plan.get("arm") or ""),
        "epoch_id": str(plan.get("epoch_id") or ""),
        "taskbed": str(plan.get("taskbed") or ""),
        "planned_split": str(plan.get("planned_split") or plan.get("split") or ""),
        "planned_task_count": _safe_int(
            plan.get("planned_task_count") or plan.get("task_count")
        ),
        "primary_metric": str(plan.get("primary_metric") or ""),
        "class_null": str(plan.get("class_null") or ""),
        "min_effect": _safe_float(plan.get("min_effect"), min_effect),
        "pre_registered_mde": _safe_float(mde_value, default_mde),
        "controls": sorted(set(_as_list(plan.get("controls") or plan.get("control_arms")))),
        "frozen_at": str(plan.get("frozen_at") or plan.get("created_at") or ""),
        "analysis_plan_sha256": str(plan.get("analysis_plan_sha256") or ""),
    }
    blockers: list[str] = []
    for field in ("run_id", "candidate_id", "epoch_id", "taskbed", "primary_metric", "class_null"):
        if not payload[field]:
            blockers.append(f"missing_{field}")
    if payload["planned_split"] != "confirm":
        blockers.append("planned_split_not_confirm")
    if payload["planned_task_count"] < min_confirm_n:
        blockers.append(f"planned_task_count<{min_confirm_n}")
    if payload["min_effect"] < min_effect:
        blockers.append("min_effect_below_gate")
    if mde_value is None:
        blockers.append("pre_registered_mde_missing")
    elif payload["pre_registered_mde"] <= 0:
        blockers.append("pre_registered_mde_missing")
    if not payload["frozen_at"]:
        blockers.append("missing_frozen_at")
    required = set(required_controls)
    missing_controls = sorted(required - set(payload["controls"]))
    if missing_controls:
        blockers.extend(f"missing_control:{control}" for control in missing_controls)
    if not payload["analysis_plan_sha256"]:
        payload["analysis_plan_sha256"] = canonical_sha256(
            {
                "run_id": payload["run_id"],
                "candidate_id": payload["candidate_id"],
                "epoch_id": payload["epoch_id"],
                "taskbed": payload["taskbed"],
                "metric": payload["primary_metric"],
                "controls": payload["controls"],
                "planned_task_count": payload["planned_task_count"],
            }
        )
    return _base_receipt(
        schema=PREREGISTRATION_SCHEMA,
        name=PREREGISTRATION_NAME,
        payload=payload,
        blockers=blockers,
    )


def evaluate_scaffold_parity(
    scaffold_templates: Mapping[str, str | Iterable[str]],
    *,
    required_arms: Iterable[str] = CANONICAL_CONTROL_ARMS,
) -> dict[str, Any]:
    """Build a receipt proving each arm used the same non-arm-specific scaffold.

    Callers pass only the shared template pieces for each arm.  Arm-specific
    model names, labels, and candidates should be excluded before calling this
    helper; otherwise the receipt correctly refuses parity.
    """
    per_arm_hash: dict[str, str] = {}
    for arm, templates in scaffold_templates.items():
        parts = [templates] if isinstance(templates, str) else list(templates)
        per_arm_hash[str(arm)] = scaffold_parity_hash(*[str(part) for part in parts])

    blockers: list[str] = []
    required = set(required_arms)
    missing = sorted(required - set(per_arm_hash))
    if missing:
        blockers.extend(f"missing_arm:{arm}" for arm in missing)
    if len(per_arm_hash) < 2:
        blockers.append("insufficient_arms_for_parity")

    unique_hashes = sorted(set(per_arm_hash.values()))
    if len(unique_hashes) > 1:
        blockers.append("scaffold_hash_mismatch")

    payload = {
        "arms": sorted(per_arm_hash),
        "per_arm_hash": per_arm_hash,
        "shared_scaffold_hash": unique_hashes[0] if len(unique_hashes) == 1 else "",
        "required_arms": sorted(required),
    }
    return _base_receipt(
        schema=SCAFFOLD_PARITY_SCHEMA,
        name=SCAFFOLD_PARITY_NAME,
        payload=payload,
        blockers=blockers,
    )


__all__ = [
    "CANONICAL_CONTROL_ARMS",
    "DEFAULT_PREREGISTERED_MDE",
    "MIN_CONFIRM_N",
    "MIN_EFFECT",
    "PREREGISTRATION_NAME",
    "PREREGISTRATION_SCHEMA",
    "SCAFFOLD_PARITY_NAME",
    "SCAFFOLD_PARITY_SCHEMA",
    "evaluate_preregistration_anchor",
    "evaluate_scaffold_parity",
]
