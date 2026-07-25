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
) -> GradeOutcome:
    """Grade one genome on the generation's task slice. Never raises for
    per-task trouble — a failed observation is a row, not an exception."""
    budget = seams.budget_factory(cap_tokens=budget_cap_tokens, cap_usd=budget_cap_usd)
    per_task: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    tokens_total = 0
    for task_id, (inst, ctx) in task_contexts.items():
        row: dict[str, Any] = {"task_id": task_id, "resolved": False, "tier": TIER_EXPLORE_FAST}
        try:
            if getattr(budget, "invalid", False):
                row["error"] = f"budget_invalid:{getattr(budget, 'invalid_reason', '')}"
                per_task.append(row)
                failures.append(row)
                continue
            patch, tokens = _final_patch(
                genome, inst, ctx, budget, seams=seams, timeout_s=propose_timeout_s
            )
            tokens_total = int(getattr(budget, "spent", tokens))
            row["tokens_spent"] = tokens
            if not patch.strip():
                row["error"] = "empty_patch"
            elif getattr(budget, "invalid", False):
                row["error"] = f"budget_invalid:{getattr(budget, 'invalid_reason', '')}"
            else:
                resolved, seconds, err = seams.grade_task(inst, patch, timeout=grade_timeout_s)
                row.update(resolved=bool(resolved), grade_seconds=float(seconds))
                if err:
                    row["grade_note"] = str(err)[:500]
        except Exception as exc:  # observation-level honesty: record, continue
            row["error"] = f"{type(exc).__name__}:{exc}"[:500]
        per_task.append(row)
        if not row.get("resolved"):
            failures.append(row)
    graded = [r for r in per_task if "error" not in r or r.get("resolved")]
    denominator = len(per_task)
    pass_rate = (sum(1 for r in per_task if r.get("resolved")) / denominator) if denominator else 0.0
    return GradeOutcome(
        pass_rate=pass_rate,
        per_task=per_task,
        budget=budget.to_dict() if hasattr(budget, "to_dict") else {},
        tokens_used=int(getattr(budget, "spent", tokens_total) or tokens_total),
        failures=failures,
    )


__all__ = ["GradeSeams", "GradeOutcome", "production_seams", "grade_genome_explore", "TIER_EXPLORE_FAST"]
