"""Paired arm execution and archival support for the frozen experiment path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from dharma_swarm.forge_lab import grade_explore
from dharma_swarm.forge_lab.campaign_budget import (
    CampaignBudgetExceeded,
    CampaignBudgetLedger,
    CampaignBudgetSettlementError,
)
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.evaluation_plan import EvaluationPlan
from dharma_swarm.forge_lab.freeform_explore import (
    FreeformExploreEnvelope,
    validate_freeform_explore_envelope,
)
from dharma_swarm.forge_lab.genome_spec import check_genome
from dharma_swarm.forge_lab.paired_evaluation import (
    PairObservation,
    aggregate_paired_observations,
    build_paired_cells,
    evaluation_id,
)
from dharma_swarm.forge_lab.run_receipts import (
    _append_jsonl,
    _append_result_row,
    _now,
    _result_row,
)

PAIRED_OBSERVATION_SCHEMA = "forge_lab.paired_arm_observation.v1"


class PairedEvaluationBlocked(RuntimeError):
    """A dispatch was refused before it could violate frozen protocol."""


class PairedEvaluator:
    def __init__(
        self, *, cfg: Any, seams: Any, run_guard: Any, plan: EvaluationPlan,
        ledger: CampaignBudgetLedger, budget_path: Path, observations_path: Path,
        baseline_genome: dict[str, Any], baseline_id: str,
        contexts: dict[str, tuple[dict, dict]], store: CandidateStore,
        experiment_id: str, category: str, membrane: dict[str, bool],
        results_path: Path, counters: dict[str, int],
        offload: Callable[..., Awaitable[Any]],
    ) -> None:
        self.cfg, self.seams, self.run_guard, self.plan = cfg, seams, run_guard, plan
        self.ledger, self.budget_path = ledger, budget_path
        self.observations_path = observations_path
        self.baseline_genome, self.baseline_id = baseline_genome, baseline_id
        self.contexts, self.store = contexts, store
        self.experiment_id, self.category, self.membrane = experiment_id, category, membrane
        self.results_path, self.counters, self.offload = results_path, counters, offload
        self.baseline_cache: dict[str, dict[str, Any]] = {}

    async def grade_arm(
        self, *, genome: dict[str, Any], evaluated_candidate_id: str, role: str,
        split: str, task_id: str, repeat_seed: int, eval_id: str, component: str,
    ) -> dict[str, Any]:
        if role == "baseline" and eval_id in self.baseline_cache:
            return self.baseline_cache[eval_id]
        if self.run_guard is not None:
            self.run_guard.checkpoint()
        try:
            reservation = self.ledger.reserve(
                component, max_tokens=self.cfg.budget_cap_tokens,
                max_usd=self.cfg.budget_cap_usd, operation_id=eval_id,
            )
        except CampaignBudgetExceeded as exc:
            raise PairedEvaluationBlocked(f"budget_refused_before_dispatch:{eval_id}:{exc}") from exc
        self.ledger.save(self.budget_path)
        try:
            outcome = await self.offload(
                grade_explore.grade_genome_explore, genome,
                {task_id: self.contexts[task_id]}, seams=self.seams.grade,
                budget_cap_tokens=reservation.max_tokens,
                budget_cap_usd=float(reservation.max_usd),
                propose_timeout_s=self.cfg.propose_timeout_s,
                grade_timeout_s=self.cfg.grade_timeout_s, soft_token_cap=False,
            )
        except Exception as exc:
            self.ledger.settle(
                eval_id, actual_tokens=reservation.max_tokens, actual_usd=reservation.max_usd,
            )
            self.ledger.save(self.budget_path)
            row = self._arm_row(
                eval_id=eval_id, candidate_id=evaluated_candidate_id, role=role,
                split=split, task_id=task_id, repeat_seed=repeat_seed, score=0.0,
                valid=False, tokens_used=reservation.max_tokens,
                error=f"{type(exc).__name__}:{exc}"[:500],
            )
            self._record_arm(role, eval_id, row)
            return row

        settlement_error = ""
        actual_usd = outcome.budget.get("spent_usd", 0) or 0
        try:
            self.ledger.settle(
                eval_id, actual_tokens=max(0, int(outcome.tokens_used)), actual_usd=actual_usd,
            )
        except CampaignBudgetSettlementError as exc:
            settlement_error = str(exc)
        self.ledger.save(self.budget_path)
        valid = not bool(outcome.budget.get("invalid") or outcome.budget.get("hard_invalid")
                         or settlement_error)
        row = self._arm_row(
            eval_id=eval_id, candidate_id=evaluated_candidate_id, role=role,
            split=split, task_id=task_id, repeat_seed=repeat_seed,
            score=float(outcome.pass_rate), valid=valid, tokens_used=int(outcome.tokens_used),
            error=settlement_error or None, budget=outcome.budget,
        )
        self._record_arm(role, eval_id, row)
        return row

    def _arm_row(self, *, eval_id: str, candidate_id: str, role: str, split: str,
                 task_id: str, repeat_seed: int, score: float, valid: bool,
                 tokens_used: int, error: str | None, budget: dict[str, Any] | None = None,
                 ) -> dict[str, Any]:
        return {
            "schema": PAIRED_OBSERVATION_SCHEMA, "eval_id": eval_id,
            "candidate_id": candidate_id, "role": role, "split": split,
            "task_id": task_id, "repeat_seed": repeat_seed, "seed_support": "unsupported",
            "score": score, "resolved": score > 0.5, "valid": valid,
            "tokens_used": tokens_used, "budget": budget or {}, "error": error, "at": _now(),
        }

    def _record_arm(self, role: str, eval_id: str, row: dict[str, Any]) -> None:
        _append_jsonl(self.observations_path, row)
        if role == "baseline":
            self.baseline_cache[eval_id] = row

    async def ensure_baseline(self, split: str, component: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for task_id in self.plan.task_ids(split):
            for repeat_seed in self.plan.repeat_seeds:
                eval_id = evaluation_id(
                    role="baseline", candidate_id=self.baseline_id,
                    protocol_sha256=self.plan.plan_sha256, split=split,
                    task_id=task_id, repeat_seed=repeat_seed,
                )
                rows.append(await self.grade_arm(
                    genome=self.baseline_genome, evaluated_candidate_id=self.baseline_id,
                    role="baseline", split=split, task_id=task_id,
                    repeat_seed=repeat_seed, eval_id=eval_id, component=component,
                ))
        return rows

    async def contrast(
        self, genome: dict[str, Any], candidate_id: str, split: str, component: str,
    ) -> tuple[dict[str, Any], list[PairObservation], list[dict[str, Any]]]:
        cells = build_paired_cells(
            protocol_sha256=self.plan.plan_sha256, baseline_candidate_id=self.baseline_id,
            candidate_id=candidate_id, split=split, task_ids=self.plan.task_ids(split),
            repeat_seeds=self.plan.repeat_seeds, seed_support="unsupported",
        )
        baseline_component = component if split in {"confirm", "holdout"} else "baseline_eval"
        await self.ensure_baseline(split, baseline_component)
        observations: list[PairObservation] = []
        candidate_rows: list[dict[str, Any]] = []
        for cell in cells:
            baseline_row = self.baseline_cache[cell.baseline_eval_id]
            candidate_row = await self.grade_arm(
                genome=genome, evaluated_candidate_id=candidate_id, role="candidate",
                split=split, task_id=cell.task_id, repeat_seed=cell.repeat_seed,
                eval_id=cell.candidate_eval_id, component=component,
            )
            candidate_rows.append(candidate_row)
            observations.append(PairObservation.from_cell(
                cell, baseline_score=baseline_row["score"],
                candidate_score=candidate_row["score"],
                baseline_valid=baseline_row["valid"], candidate_valid=candidate_row["valid"],
                budget_valid=baseline_row["valid"] and candidate_row["valid"],
                errors=tuple(str(row["error"]) for row in (baseline_row, candidate_row)
                             if row.get("error")),
            ))
        aggregate = aggregate_paired_observations(
            cells, observations, bootstrap_samples=self.cfg.paired_bootstrap_samples,
            bootstrap_seed=self.cfg.rng_seed, evaluation_plan=self.plan,
            min_decision_tasks=self.cfg.paired_min_decision_tasks,
        )
        return aggregate, observations, candidate_rows

    async def archive_graded(
        self, *, genome: dict[str, Any], candidate_id: str, parent_id: str | None,
        generation: int, role: str, per_task: list[dict[str, Any]],
        paired_stats: dict[str, Any], notes: str, operator: str,
    ) -> dict[str, Any]:
        checked = check_genome(genome)
        absolute_rate = sum(float(row["score"]) for row in per_task) / len(per_task) if per_task else 0.0
        envelope = FreeformExploreEnvelope(
            candidate_id=candidate_id, parent_id=parent_id, experiment_id=self.experiment_id,
            category=self.category, notes=notes,
            artifacts={"operator": operator, "evaluation_plan_sha256": self.plan.plan_sha256},
            benchmark_receipt={"protocol": "paired_frozen_v1", "paired_stats": paired_stats},
            membrane=self.membrane,
        )
        issues = validate_freeform_explore_envelope(envelope)
        if issues:
            raise PairedEvaluationBlocked(f"envelope_failed:{issues}")
        archive_rows = [{
            "task_id": row["task_id"], "repeat_seed": row["repeat_seed"],
            "resolved": row.get("resolved", False), "score": row["score"],
            "eval_id": row["eval_id"], "tokens_spent": row["tokens_used"],
        } for row in per_task]
        await self.store.append_graded(
            candidate_id=candidate_id, genome=genome, parent_id=parent_id,
            generation=generation, loop_iteration=generation, role=role,
            pass_rate=absolute_rate, per_task=archive_rows,
            budget={"campaign_ledger_sha256": self.ledger.to_dict()["ledger_sha256"],
                    "paired_stats": paired_stats},
            tier="paired-frozen-v1", executed_fields=checked.executed_fields,
            ignored_fields=checked.ignored_fields, envelope=envelope, mutation_notes=notes,
            model=str(genome.get("generator_model") or ""),
            tokens_used=sum(int(row["tokens_used"]) for row in per_task),
        )
        self.counters["graded"] += 1
        return _append_result_row(self.results_path, _result_row(
            exp_id=self.experiment_id, candidate_id=candidate_id, parent_id=parent_id,
            state="graded", role=role, op=operator, generation=generation,
            pass_rate=absolute_rate, per_task=archive_rows,
            budget={"paired_stats": paired_stats},
        ))


__all__ = ["PAIRED_OBSERVATION_SCHEMA", "PairedEvaluationBlocked", "PairedEvaluator"]
