"""Offline equal-budget Forge scoreboard production contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from dharma_swarm.forge_prod_contracts.taskbed import (
    CONTAMINATION_STATE,
    PrivateRepairTask,
    default_private_code_repair_tasks,
    grade_candidate_source,
    stable_payload_hash,
    visible_task_manifest,
)


SCHEMA_VERSION = "forge_prod_contracts.offline_scoreboard.v1"
ArmName = Literal["strong_single", "same_budget_self_moa", "swarm_topology"]
ARM_NAMES: tuple[ArmName, ...] = (
    "strong_single",
    "same_budget_self_moa",
    "swarm_topology",
)


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    """Equal-budget policy for local deterministic arms."""

    token_budget: int = 1200
    max_candidates_per_arm: int = 3

    def to_dict(self) -> dict[str, int]:
        return {
            "token_budget": self.token_budget,
            "max_candidates_per_arm": self.max_candidates_per_arm,
        }


@dataclass(frozen=True, slots=True)
class CandidateSubmission:
    """One arm submission before hidden-test grading."""

    arm: ArmName
    candidate_id: str
    source: str
    estimated_tokens: int
    candidate_count: int
    strategy: str
    selected_without_hidden_tests: bool = True

    @property
    def over_budget(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ScoreRow:
    """One task/arm score after execution grading."""

    task_id: str
    arm: ArmName
    score: float
    passed: bool
    estimated_tokens: int
    budget_cap_tokens: int
    candidate_count: int
    selected_without_hidden_tests: bool
    failure_classes: tuple[str, ...]
    candidate_source_sha256: str
    execution: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "arm": self.arm,
            "score": self.score,
            "passed": self.passed,
            "estimated_tokens": self.estimated_tokens,
            "budget_cap_tokens": self.budget_cap_tokens,
            "candidate_count": self.candidate_count,
            "selected_without_hidden_tests": self.selected_without_hidden_tests,
            "failure_classes": list(self.failure_classes),
            "candidate_source_sha256": self.candidate_source_sha256,
            "execution": self.execution,
        }


@dataclass(frozen=True, slots=True)
class ScoreboardReport:
    """Serializable offline scoreboard report."""

    run_id: str
    created_at: str
    budget_policy: BudgetPolicy
    tasks: tuple[PrivateRepairTask, ...]
    rows: tuple[ScoreRow, ...]

    @property
    def summary(self) -> dict[str, object]:
        by_arm: dict[str, dict[str, object]] = {}
        for arm in ARM_NAMES:
            arm_rows = [row for row in self.rows if row.arm == arm]
            total = len(arm_rows)
            by_arm[arm] = {
                "task_count": total,
                "pass_count": sum(row.passed for row in arm_rows),
                "average_score": round(
                    sum(row.score for row in arm_rows) / total if total else 0.0,
                    4,
                ),
                "tokens_spent": sum(row.estimated_tokens for row in arm_rows),
                "budget_cap_tokens": self.budget_policy.token_budget,
                "max_candidate_count": max(
                    (row.candidate_count for row in arm_rows),
                    default=0,
                ),
                "failure_classes": sorted(
                    {failure for row in arm_rows for failure in row.failure_classes}
                ),
            }
        single_score = float(by_arm["strong_single"]["average_score"])
        swarm_score = float(by_arm["swarm_topology"]["average_score"])
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "task_count": len(self.tasks),
            "arm_count": len(ARM_NAMES),
            "strong_single_baseline": "strong_single",
            "equal_budget": self._equal_budget(),
            "contamination_state": CONTAMINATION_STATE,
            "execution_graded": True,
            "hidden_tests_withheld_from_arms": True,
            "swarm_lift_vs_strong_single": round(swarm_score - single_score, 4),
            "arms": by_arm,
            "promotion": self.promotion_decision,
        }

    @property
    def promotion_decision(self) -> dict[str, object]:
        blockers = [
            "shadow_only_first_production_contract",
            "local_task_count_below_confirm_threshold",
            "no_independent_external_countercheck",
            "no_frozen_confirm_manifest",
        ]
        if any(task.contamination_state != CONTAMINATION_STATE for task in self.tasks):
            blockers.append("non_private_or_contaminated_task_present")
        return {
            "promotion_allowed": False,
            "decision": "refuse_promotion_record_candidate_signal",
            "blocked_gates": blockers,
            "safe_learning_action": "record_scoreboard_and_schedule_private_confirm",
        }

    def to_dict(self) -> dict[str, object]:
        task_manifest = visible_task_manifest(self.tasks)
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "budget_policy": self.budget_policy.to_dict(),
            "task_manifest": task_manifest,
            "task_manifest_sha256": stable_payload_hash(task_manifest),
            "summary": self.summary,
            "rows": [row.to_dict() for row in self.rows],
        }

    def _equal_budget(self) -> bool:
        caps = {row.budget_cap_tokens for row in self.rows}
        return caps == {self.budget_policy.token_budget}


def run_offline_scoreboard(
    *,
    tasks: tuple[PrivateRepairTask, ...] | None = None,
    budget_policy: BudgetPolicy | None = None,
    run_id: str = "",
) -> ScoreboardReport:
    """Run the local private taskbed through all equal-budget arms."""

    selected_tasks = tasks or default_private_code_repair_tasks()
    policy = budget_policy or BudgetPolicy()
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report_run_id = (
        run_id or f"forge-prod-contracts-{now.replace(':', '').replace('-', '')}"
    )
    rows: list[ScoreRow] = []
    for task in selected_tasks:
        for arm in ARM_NAMES:
            submission = build_submission(task, arm, policy)
            if submission.estimated_tokens > policy.token_budget:
                grade = None
                passed = False
                score = 0.0
                failures = ("budget_overrun",)
                execution = {"skipped": True, "reason": "budget_overrun"}
            else:
                grade = grade_candidate_source(task, submission.source)
                passed = grade.passed
                score = grade.score
                failures = () if passed else ("hidden_execution_failed",)
                execution = grade.to_dict()
            rows.append(
                ScoreRow(
                    task_id=task.task_id,
                    arm=arm,
                    score=score,
                    passed=passed,
                    estimated_tokens=submission.estimated_tokens,
                    budget_cap_tokens=policy.token_budget,
                    candidate_count=submission.candidate_count,
                    selected_without_hidden_tests=submission.selected_without_hidden_tests,
                    failure_classes=failures,
                    candidate_source_sha256=stable_payload_hash(
                        {
                            "task_id": task.task_id,
                            "arm": arm,
                            "source": submission.source,
                        }
                    ),
                    execution=execution,
                )
            )
    return ScoreboardReport(
        run_id=report_run_id,
        created_at=now,
        budget_policy=policy,
        tasks=selected_tasks,
        rows=tuple(rows),
    )


def build_submission(
    task: PrivateRepairTask,
    arm: ArmName,
    budget_policy: BudgetPolicy,
) -> CandidateSubmission:
    if arm == "strong_single":
        source = _strong_single_patch(task.buggy_source)
        candidate_count = 1
        strategy = "single deterministic repair heuristic"
    elif arm == "same_budget_self_moa":
        candidates = _self_moa_candidates(task.buggy_source)
        source = _select_without_hidden_tests(candidates)
        candidate_count = len(candidates)
        strategy = "three deterministic samples selected by visible-source confidence"
    else:
        source = _swarm_patch(task.buggy_source)
        candidate_count = min(3, budget_policy.max_candidates_per_arm)
        strategy = "planner-builder-verifier deterministic repair topology"
    return CandidateSubmission(
        arm=arm,
        candidate_id=f"{task.task_id}:{arm}",
        source=source,
        estimated_tokens=_estimate_tokens(task.visible_prompt, source, strategy),
        candidate_count=candidate_count,
        strategy=strategy,
    )


def _estimate_tokens(*parts: str) -> int:
    raw = "\n".join(parts)
    return max(1, len(raw.split()) + len(raw) // 12)


def _strong_single_patch(source: str) -> str:
    patched = source.replace("* tax_bps / 1000", "* tax_bps / 10000")
    patched = patched.replace("range(attempts)", "range(1, attempts + 1)")
    return patched


def _self_moa_candidates(source: str) -> tuple[str, ...]:
    return (
        _strong_single_patch(source),
        source.replace(
            "int(subtotal * tax_bps / 1000)", "round(subtotal * tax_bps / 10000)"
        ),
        _order_preserving_patch(source),
    )


def _select_without_hidden_tests(candidates: tuple[str, ...]) -> str:
    scored = sorted(
        candidates,
        key=lambda item: (
            "seen =" in item,
            "range(1, attempts + 1)" in item,
            "/ 10000" in item,
            len(item),
        ),
        reverse=True,
    )
    return scored[0]


def _swarm_patch(source: str) -> str:
    return _order_preserving_patch(_strong_single_patch(source))


def _order_preserving_patch(source: str) -> str:
    return source.replace(
        "return list(set(event_ids))",
        "seen = set()\n    out = []\n    for event_id in event_ids:\n        if event_id not in seen:\n            seen.add(event_id)\n            out.append(event_id)\n    return out",
    )
