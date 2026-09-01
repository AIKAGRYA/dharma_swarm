"""Explore-tier grading adapter: one genome × N fresh tasks → per-task truth.

Wraps the verified seams (never runner.run()):
  runner._pull_task_context (context, cached per task per generation by the
  caller), arms.{self_moa,verify_chain,mixed_moa}_arm, canonical._propose_slot
  (the freeform_single arm — 1 call, carries the genome's free-form
  extra_instruction), runner._grade_task (SWE-bench only; host PR-suite
  grading is refused).

Every seam is injectable so the unit tests never touch network, git, or
pytest-in-pytest. Production defaults are resolved lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

TIER_EXPLORE_FAST = "explore-fast-isolated"
TIER_CONFIRM_SWEBENCH = "confirm-swebench-docker"
INCONCLUSIVE_INFRASTRUCTURE = "InconclusiveInfrastructure"
INCONCLUSIVE_GENERATION = "InconclusiveGeneration"
INCONCLUSIVE_BUDGET = "InconclusiveBudget"
MEASURED_NEGATIVE = "MeasuredNegative"
MEASURED_TASK_OUTCOME = "MeasuredTaskOutcome"


class GraderOutcome(str, Enum):
    EXECUTED_PASS = "executed_pass"
    EXECUTED_FAIL = "executed_fail"
    INFRASTRUCTURE_ERROR = "infrastructure_error"


@dataclass(frozen=True)
class GraderResult:
    """Typed evaluator result; only executed/comparable false is a negative."""

    resolved: bool
    seconds: float
    outcome: GraderOutcome
    executed: bool
    comparable: bool
    note: str | None = None
    error_class: str | None = None
    isolation_proofs: tuple[dict[str, Any], ...] = ()

    def __iter__(self):
        """Preserve the historical ``resolved, seconds, note`` seam."""

        yield self.resolved
        yield self.seconds
        yield self.note

    @classmethod
    def executed_verdict(
        cls,
        resolved: bool,
        seconds: float,
        *,
        note: str | None = None,
        isolation_proofs: tuple[dict[str, Any], ...] = (),
    ) -> GraderResult:
        return cls(
            resolved=bool(resolved),
            seconds=float(seconds),
            outcome=(
                GraderOutcome.EXECUTED_PASS
                if resolved
                else GraderOutcome.EXECUTED_FAIL
            ),
            executed=True,
            comparable=True,
            note=note,
            isolation_proofs=isolation_proofs,
        )

    @classmethod
    def infrastructure(
        cls,
        error_class: str,
        *,
        seconds: float = 0.0,
        note: str | None = None,
        isolation_proofs: tuple[dict[str, Any], ...] = (),
    ) -> GraderResult:
        return cls(
            resolved=False,
            seconds=float(seconds),
            outcome=GraderOutcome.INFRASTRUCTURE_ERROR,
            executed=False,
            comparable=False,
            note=note,
            error_class=error_class,
            isolation_proofs=isolation_proofs,
        )


def normalize_grader_result(value: Any) -> GraderResult:
    """Normalize legacy tuple seams without guessing from prose notes."""

    if isinstance(value, GraderResult):
        return value
    try:
        resolved, seconds, legacy_error = value
    except (TypeError, ValueError) as exc:
        raise TypeError("grader must return GraderResult or a three-item tuple") from exc
    if legacy_error is None:
        return GraderResult.executed_verdict(bool(resolved), float(seconds))
    # A populated third field in the historical tuple was an error channel, not
    # a typed test verdict. It is non-comparable regardless of its prose.
    return GraderResult.infrastructure(
        "untyped_legacy_grader_error",
        seconds=float(seconds),
        note=str(legacy_error)[:500],
    )


class ExploreInfrastructureError(RuntimeError):
    pass


class ExploreGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GradeSeams:
    slot_for_id: Callable[[str], Any]
    propose_slot: Callable[..., dict[str, Any]]
    self_moa_arm: Callable[..., dict[str, Any]]
    verify_chain_arm: Callable[..., dict[str, Any]]
    mixed_moa_arm: Callable[..., dict[str, Any]]
    grade_task: Callable[..., GraderResult | tuple[bool, float, str | None]]
    budget_factory: Callable[..., Any]


def production_seams() -> GradeSeams:
    from dharma_swarm.forge_v1.canonical import _propose_slot
    from dharma_swarm.forge_v1.forge_v2 import runner_slots
    from dharma_swarm.forge_v1.forge_v2.arms import mixed_moa_arm, self_moa_arm, verify_chain_arm
    from dharma_swarm.forge_v1.forge_v2.budget import Budget
    from dharma_swarm.forge_v1.forge_v2.runner import _grade_task
    from dharma_swarm.forge_v1.forge_v2.pr_suite_grader import is_pr_suite_task
    from dharma_swarm.forge_lab.grader_isolation import isolated_swebench_containers

    def isolated_grade_task(
        inst: dict[str, Any], patch: str, *, timeout: int
    ) -> GraderResult:
        # SWE-bench goes through the official Docker evaluator.  The PR-suite
        # adapter still executes pytest on the host, so it is not admitted to
        # RSI production until a brokerless container worker replaces it.
        if is_pr_suite_task(inst):
            return GraderResult.infrastructure(
                "isolated_pr_suite_grader_unavailable",
            )
        try:
            with isolated_swebench_containers() as isolation_proofs:
                resolved, seconds, error = _grade_task(inst, patch, timeout=timeout)
            proofs = tuple(isolation_proofs)
            if error:
                return GraderResult.infrastructure(
                    "swebench_grader_error",
                    seconds=float(seconds),
                    note=str(error)[:500],
                    isolation_proofs=proofs,
                )
            if not proofs or not all(proof.get("promotion_eligible") for proof in proofs):
                return GraderResult.infrastructure(
                    "isolation_proof_missing_or_incomplete",
                    seconds=float(seconds),
                    isolation_proofs=proofs,
                )
            return GraderResult.executed_verdict(
                bool(resolved),
                float(seconds),
                isolation_proofs=proofs,
            )
        except Exception as exc:
            return GraderResult.infrastructure(
                "isolated_swebench_grader_failed",
                note=f"{type(exc).__name__}:{exc}"[:500],
            )

    return GradeSeams(
        slot_for_id=runner_slots._slot_for_id,
        propose_slot=_propose_slot,
        self_moa_arm=self_moa_arm,
        verify_chain_arm=verify_chain_arm,
        mixed_moa_arm=mixed_moa_arm,
        grade_task=isolated_grade_task,
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
    evidence_class: str = INCONCLUSIVE_INFRASTRUCTURE
    comparable_observations: int = 0


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


def _final_patch(
    genome: dict[str, Any],
    inst: dict,
    ctx: dict,
    budget: Any,
    *,
    seams: GradeSeams,
    timeout_s: int,
) -> tuple[str, int, dict[str, Any]]:
    kind = genome["arm_kind"]
    per_call = int(genome.get("per_call_tokens", 6000))
    window = int(genome.get("window_chars", 11000))
    gen_slot = seams.slot_for_id(str(genome["generator_model"]))
    if gen_slot is None:
        raise ExploreInfrastructureError(
            f"unresolvable_generator_model:{genome['generator_model']}"
        )
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
        evidence = rec.get("execution_input_receipt")
        return (
            str(rec.get("patch") or ""),
            tokens,
            {
                "schema": "rsi_lab.execution_evidence.v1",
                "arm": kind,
                "generator_input": evidence if isinstance(evidence, dict) else None,
            },
        )
    if kind == "self_moa":
        out = seams.self_moa_arm(
            gen_slot, inst, ctx, budget,
            k=int(genome.get("k", 3)), per_call_tokens=per_call, timeout_s=timeout_s, window_chars=window,
        )
        return (
            str(out.get("final_patch") or ""),
            int(budget.spent),
            {
                "schema": "rsi_lab.execution_evidence.v1",
                "arm": kind,
                "generator_input": None,
            },
        )
    ver_slot = seams.slot_for_id(str(genome.get("verifier_model") or ""))
    if ver_slot is None:
        raise ExploreInfrastructureError(
            f"unresolvable_verifier_model:{genome.get('verifier_model')}"
        )
    if kind == "verify_chain":
        out = seams.verify_chain_arm(
            gen_slot, ver_slot, inst, ctx, budget,
            per_call_tokens=per_call, timeout_s=timeout_s, window_chars=window,
            extra_instruction=str(genome.get("extra_instruction") or ""),
        )
    elif kind == "mixed_moa":
        out = seams.mixed_moa_arm(
            [gen_slot, ver_slot], ver_slot, inst, ctx, budget,
            per_call_tokens=per_call, timeout_s=timeout_s, window_chars=window,
        )
    else:
        raise ExploreGenerationError(f"unknown_arm_kind:{kind}")
    raw_evidence = out.get("execution_evidence")
    evidence = {
        "schema": "rsi_lab.execution_evidence.v1",
        "arm": kind,
        "generator_input": None,
    }
    if isinstance(raw_evidence, dict):
        evidence.update(
            {
                key: value
                for key, value in raw_evidence.items()
                if key != "schema"
            }
        )
    return (
        str(out.get("final_patch") or ""),
        int(budget.spent),
        evidence,
    )


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
        row: dict[str, Any] = {"task_id": task_id, "resolved": False, "tier": tier}
        grader_result: GraderResult | None = None
        noncomparable_kind: str | None = None
        try:
            if getattr(budget, "invalid", False):
                row["error"] = f"budget_invalid:{getattr(budget, 'invalid_reason', '')}"
                noncomparable_kind = "budget"
            else:
                patch, tokens, execution_evidence = _final_patch(
                    genome, inst, ctx, budget, seams=seams, timeout_s=propose_timeout_s
                )
                tokens_total = int(getattr(budget, "spent", tokens))
                row["tokens_spent"] = tokens
                row["budget_soft_token_cap_exceeded"] = bool(getattr(budget, "soft_token_cap_exceeded", False))
                if execution_evidence:
                    row["execution_evidence"] = execution_evidence
                if not patch.strip():
                    row["error"] = "empty_patch"
                    noncomparable_kind = "generation"
                elif getattr(budget, "invalid", False):
                    row["error"] = f"budget_invalid:{getattr(budget, 'invalid_reason', '')}"
                    noncomparable_kind = "budget"
                else:
                    grader_result = normalize_grader_result(
                        seams.grade_task(inst, patch, timeout=grade_timeout_s)
                    )
                    row.update(
                        resolved=bool(grader_result.resolved),
                        grade_seconds=float(grader_result.seconds),
                        grader_outcome=grader_result.outcome.value,
                        grader_executed=grader_result.executed,
                        grader_comparable=grader_result.comparable,
                    )
                    if grader_result.note:
                        row["grade_note"] = grader_result.note
                    if grader_result.error_class:
                        row["grader_error_class"] = grader_result.error_class
                    if grader_result.isolation_proofs:
                        row["isolation_proofs"] = list(grader_result.isolation_proofs)
        except ExploreInfrastructureError as exc:
            row["error"] = f"{type(exc).__name__}:{exc}"[:500]
            noncomparable_kind = "infrastructure"
        except ExploreGenerationError as exc:
            row["error"] = f"{type(exc).__name__}:{exc}"[:500]
            noncomparable_kind = "generation"
        except Exception as exc:  # provider/runtime failure: record, continue
            row["error"] = f"{type(exc).__name__}:{exc}"[:500]
            noncomparable_kind = "infrastructure"

        if noncomparable_kind == "budget":
            row["evidence_class"] = INCONCLUSIVE_BUDGET
        elif noncomparable_kind == "generation":
            row["evidence_class"] = INCONCLUSIVE_GENERATION
        elif noncomparable_kind == "infrastructure":
            row["evidence_class"] = INCONCLUSIVE_INFRASTRUCTURE
        elif grader_result is None:
            row["evidence_class"] = INCONCLUSIVE_INFRASTRUCTURE
            row["grader_error_class"] = "grader_result_missing"
        elif not grader_result.executed or not grader_result.comparable:
            row["evidence_class"] = INCONCLUSIVE_INFRASTRUCTURE
        elif grader_result.outcome is GraderOutcome.EXECUTED_PASS and row.get("resolved"):
            row["evidence_class"] = MEASURED_TASK_OUTCOME
        elif grader_result.outcome is GraderOutcome.EXECUTED_FAIL and not row.get("resolved"):
            # This is the only path that can mint a measured negative: an
            # executed comparable evaluator explicitly returned false.
            row["evidence_class"] = MEASURED_NEGATIVE
        else:
            row["evidence_class"] = INCONCLUSIVE_INFRASTRUCTURE
            row["grader_error_class"] = "inconsistent_typed_grader_result"
        per_task.append(row)
        if not row.get("resolved"):
            failures.append(row)
    graded = [
        row
        for row in per_task
        if row.get("evidence_class") in {MEASURED_NEGATIVE, MEASURED_TASK_OUTCOME}
    ]
    denominator = len(graded)
    resolved_count = sum(1 for r in graded if r.get("resolved"))
    pass_rate = (resolved_count / denominator) if denominator else 0.0
    budget_dict = budget.to_dict() if hasattr(budget, "to_dict") else {}
    spent_tokens = int(budget_dict.get("spent_tokens", getattr(budget, "spent", tokens_total)) or tokens_total or 0)
    budget_dict["pass_rate_per_100k_tokens"] = (
        round(pass_rate * 100_000 / spent_tokens, 6) if spent_tokens else None
    )
    budget_dict["tokens_per_resolved"] = (
        round(spent_tokens / resolved_count, 1) if resolved_count else None
    )
    budget_dict["comparable_observations"] = denominator
    budget_dict["inconclusive_infrastructure_observations"] = sum(
        row.get("evidence_class") == INCONCLUSIVE_INFRASTRUCTURE for row in per_task
    )
    budget_dict["inconclusive_generation_observations"] = sum(
        row.get("evidence_class") == INCONCLUSIVE_GENERATION for row in per_task
    )
    budget_dict["inconclusive_budget_observations"] = sum(
        row.get("evidence_class") == INCONCLUSIVE_BUDGET for row in per_task
    )
    if not denominator:
        classes = {row.get("evidence_class") for row in per_task}
        if INCONCLUSIVE_INFRASTRUCTURE in classes:
            evidence_class = INCONCLUSIVE_INFRASTRUCTURE
        elif INCONCLUSIVE_BUDGET in classes:
            evidence_class = INCONCLUSIVE_BUDGET
        else:
            evidence_class = INCONCLUSIVE_GENERATION
    elif resolved_count:
        evidence_class = MEASURED_TASK_OUTCOME
    else:
        evidence_class = MEASURED_NEGATIVE
    return GradeOutcome(
        pass_rate=pass_rate,
        per_task=per_task,
        budget=budget_dict,
        tokens_used=spent_tokens,
        tier=tier,
        failures=failures,
        evidence_class=evidence_class,
        comparable_observations=denominator,
    )


__all__ = [
    "GradeSeams",
    "GradeOutcome",
    "GraderOutcome",
    "GraderResult",
    "normalize_grader_result",
    "production_seams",
    "grade_genome_explore",
    "TIER_EXPLORE_FAST",
    "TIER_CONFIRM_SWEBENCH",
    "INCONCLUSIVE_INFRASTRUCTURE",
    "INCONCLUSIVE_GENERATION",
    "INCONCLUSIVE_BUDGET",
    "MEASURED_NEGATIVE",
    "MEASURED_TASK_OUTCOME",
]
