"""Explore-tier grading adapter: one genome × N fresh tasks → per-task truth.

Wraps the verified seams (never runner.run()):
  runner._pull_task_context (context, cached per task per generation by the
  caller), arms.{self_moa,verify_chain,mixed_moa}_arm, canonical._propose_slot
  (the freeform_single arm — 1 call, carries the genome's free-form
  extra_instruction), runner._grade_task (host-pytest, anti-cheat inside).

Every seam is injectable so the unit tests never touch network, git, or
pytest-in-pytest. Production defaults are resolved lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

TIER_EXPLORE_FAST = "explore-fast-host-pytest"
TIER_CONFIRM_SWEBENCH = "confirm-swebench-docker"
_VALID_CANDIDATE_FAILURE_PREFIXES = (
    "test_returncode=",
    "patch_apply_failed",
    "patch_touches_test_file",
    "empty_patch",
)


@dataclass(frozen=True)
class GradeSeams:
    slot_for_id: Callable[[str], Any]
    propose_slot: Callable[..., dict[str, Any]]
    self_moa_arm: Callable[..., dict[str, Any]]
    verify_chain_arm: Callable[..., dict[str, Any]]
    mixed_moa_arm: Callable[..., dict[str, Any]]
    grade_task: Callable[..., tuple[bool, float, str | None]]
    budget_factory: Callable[..., Any]


def production_seams() -> GradeSeams:
    from dharma_swarm.forge_v1.canonical import _propose_slot
    from dharma_swarm.forge_v1.forge_v2 import runner_slots
    from dharma_swarm.forge_v1.forge_v2.arms import mixed_moa_arm, self_moa_arm, verify_chain_arm
    from dharma_swarm.forge_v1.forge_v2.budget import Budget
    from dharma_swarm.forge_v1.forge_v2.runner import _grade_task

    return GradeSeams(
        slot_for_id=runner_slots._slot_for_id,
        propose_slot=_propose_slot,
        self_moa_arm=self_moa_arm,
        verify_chain_arm=verify_chain_arm,
        mixed_moa_arm=mixed_moa_arm,
        grade_task=_grade_task,
        budget_factory=Budget,
    )


@dataclass(frozen=True)
class GradeOutcome:
    pass_rate: float
    per_task: list[dict[str, Any]]
    budget: dict[str, Any]
    tokens_used: int
    tier: str = TIER_EXPLORE_FAST
    error: str | None = None
    failures: list[dict[str, Any]] = field(default_factory=list)


def _observation_validity(
    error_note: str | None,
) -> tuple[bool, str, str | None]:
    """Classify the legacy grader's overloaded third tuple field.

    The PR-suite grader currently uses ``error`` both for ordinary candidate
    failures and for infrastructure failure.  Keep that distinction explicit
    here until the seam returns a typed result.
    """
    note = str(error_note or "").strip()
    if not note or note.startswith("receipt="):
        return True, "official_grader_result", None
    head = note.split("; receipt=", 1)[0]
    if head.startswith(_VALID_CANDIDATE_FAILURE_PREFIXES):
        return True, "candidate_grade_failure", None
    return False, "grader_error", "grader_error"


class _ExploreOpenBudget:
    """Explore-mode budget adapter.

    Forge v0.1 separates *research accounting* from *candidate validity*:
    tokens over the declared comparison budget are measured and reported, but
    they do not make an otherwise executable candidate invalid during open
    exploration. Hard operational fuses, especially a real/shadow dollar cap,
    still invalidate and short-circuit through ``invalid``.

    The wrapped forge_v2 ``Budget`` still records the original over-token
    reason, so legacy evidence remains auditable, while arms that check
    ``budget.invalid`` no longer stop simply because the soft token cap was
    crossed.
    """

    def __init__(self, base: Any, *, soft_cap_tokens: int):
        self._base = base
        self.soft_cap_tokens = int(soft_cap_tokens)
        self.token_soft_cap_reason: str | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    @property
    def spent(self) -> int:
        return int(getattr(self._base, "spent", 0) or 0)

    def _base_reason(self) -> str | None:
        return getattr(self._base, "invalid_reason", None)

    def _token_overage_reason(self) -> str | None:
        reason = self._base_reason()
        if isinstance(reason, str) and reason.startswith("over token cap:"):
            return reason
        if self.spent > self.soft_cap_tokens:
            return f"over token soft cap: {self.spent}/{self.soft_cap_tokens}"
        return self.token_soft_cap_reason

    def _hard_invalid_reason(self) -> str | None:
        reason = self._base_reason()
        if not getattr(self._base, "invalid", False):
            return None
        if isinstance(reason, str) and reason.startswith("over token cap:"):
            return None
        return reason or "hard_budget_invalid"

    @property
    def soft_token_cap_exceeded(self) -> bool:
        return self._token_overage_reason() is not None

    @property
    def invalid(self) -> bool:
        return self._hard_invalid_reason() is not None

    @property
    def invalid_reason(self) -> str | None:
        return self._hard_invalid_reason()

    def charge(self, component: str, tokens: int, **kw: Any) -> int:
        spent = int(self._base.charge(component, tokens, **kw))
        if spent > self.soft_cap_tokens:
            self.token_soft_cap_reason = f"over token soft cap: {spent}/{self.soft_cap_tokens}"
        return spent

    def remaining(self) -> int:
        return max(0, self.soft_cap_tokens - self.spent)

    def to_dict(self) -> dict[str, Any]:
        data = dict(self._base.to_dict() if hasattr(self._base, "to_dict") else {})
        spent = int(data.get("spent_tokens", self.spent) or 0)
        soft_reason = self._token_overage_reason()
        hard_reason = self._hard_invalid_reason()
        data.update(
            {
                "soft_cap_tokens": self.soft_cap_tokens,
                "soft_token_cap_exceeded": bool(soft_reason),
                "token_soft_cap_reason": soft_reason,
                "token_invalid_ignored_for_explore": bool(soft_reason and not hard_reason),
                "hard_invalid": bool(hard_reason),
                "hard_invalid_reason": hard_reason,
                # In explore-open, ``invalid`` means hard invalid, not token over
                # soft cap. Keep the soft overage in explicit fields above.
                "invalid": bool(hard_reason),
                "invalid_reason": hard_reason,
                "spent_tokens": spent,
            }
        )
        return data


def _final_patch(genome: dict[str, Any], inst: dict, ctx: dict, budget: Any, *, seams: GradeSeams, timeout_s: int) -> tuple[str, int]:
    kind = genome["arm_kind"]
    per_call = int(genome.get("per_call_tokens", 6000))
    window = int(genome.get("window_chars", 11000))
    gen_slot = seams.slot_for_id(str(genome["generator_model"]))
    if gen_slot is None:
        raise ValueError(f"unresolvable_generator_model:{genome['generator_model']}")
    if kind == "freeform_single":
        rec = seams.propose_slot(
            gen_slot,
            inst,
            ctx,
            max_tokens=per_call,
            timeout_s=timeout_s,
            window_chars=window,
            extra_instruction=str(genome.get("extra_instruction") or ""),
        )
        tokens = int(rec.get("tokens") or 0)
        budget.charge("generation", tokens)
        return str(rec.get("patch") or ""), tokens
    if kind == "self_moa":
        out = seams.self_moa_arm(
            gen_slot, inst, ctx, budget,
            k=int(genome.get("k", 3)), per_call_tokens=per_call, timeout_s=timeout_s, window_chars=window,
        )
        return str(out.get("final_patch") or ""), int(budget.spent)
    ver_slot = seams.slot_for_id(str(genome.get("verifier_model") or ""))
    if ver_slot is None:
        raise ValueError(f"unresolvable_verifier_model:{genome.get('verifier_model')}")
    if kind == "verify_chain":
        out = seams.verify_chain_arm(
            gen_slot, ver_slot, inst, ctx, budget,
            per_call_tokens=per_call, timeout_s=timeout_s, window_chars=window,
        )
    elif kind == "mixed_moa":
        out = seams.mixed_moa_arm(
            [gen_slot, ver_slot], ver_slot, inst, ctx, budget,
            per_call_tokens=per_call, timeout_s=timeout_s, window_chars=window,
        )
    else:
        raise ValueError(f"unknown_arm_kind:{kind}")
    return str(out.get("final_patch") or ""), int(budget.spent)


def grade_genome_explore(
    genome: dict[str, Any],
    task_contexts: dict[str, tuple[dict, dict]],
    *,
    seams: GradeSeams,
    budget_cap_tokens: int,
    budget_cap_usd: float,
    propose_timeout_s: int = 240,
    grade_timeout_s: int = 600,
    soft_token_cap: bool = True,
    tier: str = TIER_EXPLORE_FAST,
) -> GradeOutcome:
    """Grade one genome on the generation's task slice. Never raises for
    per-task trouble — a failed observation is a row, not an exception."""
    raw_budget = seams.budget_factory(cap_tokens=budget_cap_tokens, cap_usd=budget_cap_usd)
    budget = (
        _ExploreOpenBudget(raw_budget, soft_cap_tokens=budget_cap_tokens)
        if soft_token_cap else raw_budget
    )
    per_task: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    tokens_total = 0
    for task_id, (inst, ctx) in task_contexts.items():
        row: dict[str, Any] = {
            "task_id": task_id,
            "resolved": False,
            "tier": tier,
            "valid_observation": False,
        }
        try:
            if getattr(budget, "invalid", False):
                row["error"] = f"budget_invalid:{getattr(budget, 'invalid_reason', '')}"
                row["observation_invalid_reason"] = "budget_invalid"
                per_task.append(row)
                failures.append(row)
                continue
            patch, tokens = _final_patch(
                genome, inst, ctx, budget, seams=seams, timeout_s=propose_timeout_s
            )
            tokens_total = int(getattr(budget, "spent", tokens))
            row["tokens_spent"] = tokens
            row["budget_soft_token_cap_exceeded"] = bool(getattr(budget, "soft_token_cap_exceeded", False))
            if not patch.strip():
                row["error"] = "empty_patch"
                row["valid_observation"] = True
                row["observation_validity"] = "candidate_output_failure"
            elif getattr(budget, "invalid", False):
                row["error"] = f"budget_invalid:{getattr(budget, 'invalid_reason', '')}"
                row["observation_invalid_reason"] = "budget_invalid"
            else:
                resolved, seconds, err = seams.grade_task(inst, patch, timeout=grade_timeout_s)
                row.update(resolved=bool(resolved), grade_seconds=float(seconds))
                valid_grade, validity, invalid_reason = _observation_validity(err)
                row["valid_observation"] = valid_grade
                row["observation_validity"] = validity
                if err:
                    row["grade_note"] = str(err)[:500]
                if invalid_reason:
                    row["observation_invalid_reason"] = invalid_reason
        except Exception as exc:  # observation-level honesty: record, continue
            row["error"] = f"{type(exc).__name__}:{exc}"[:500]
            row["observation_invalid_reason"] = "provider_or_grader_exception"
        per_task.append(row)
        if not row.get("resolved"):
            failures.append(row)
    denominator = len(per_task)
    resolved_count = sum(1 for r in per_task if r.get("resolved"))
    pass_rate = (resolved_count / denominator) if denominator else 0.0
    budget_dict = budget.to_dict() if hasattr(budget, "to_dict") else {}
    spent_tokens = int(budget_dict.get("spent_tokens", getattr(budget, "spent", tokens_total)) or tokens_total or 0)
    budget_dict["pass_rate_per_100k_tokens"] = (
        round(pass_rate * 100_000 / spent_tokens, 6) if spent_tokens else None
    )
    budget_dict["tokens_per_resolved"] = (
        round(spent_tokens / resolved_count, 1) if resolved_count else None
    )
    return GradeOutcome(
        pass_rate=pass_rate,
        per_task=per_task,
        budget=budget_dict,
        tokens_used=spent_tokens,
        tier=tier,
        failures=failures,
    )


__all__ = [
    "GradeSeams",
    "GradeOutcome",
    "production_seams",
    "grade_genome_explore",
    "TIER_EXPLORE_FAST",
    "TIER_CONFIRM_SWEBENCH",
]
