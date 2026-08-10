"""Scientific ``paired_frozen_v1`` orchestration for :mod:`experiment`.

This path is deliberately separate from the legacy generational loop.  It
freezes task and baseline identity before model dispatch, meters every mutation
and arm evaluation, selects only on EXPLORE, then evaluates one frozen winner
on CONFIRM and HOLDOUT before a revision-checked shadow-champion update.
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from dharma_swarm.forge_lab import ids, mutation, selection
from dharma_swarm.forge_lab.campaign_budget import (
    CampaignBudgetError,
    CampaignBudgetLedger,
)
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.champion_store import (
    ChampionConflict,
    ChampionStore,
    build_shadow_champion,
)
from dharma_swarm.forge_lab.evaluation_plan import (
    build_evaluation_plan_from_overlay,
    write_evaluation_plan,
)
from dharma_swarm.forge_lab.genome_spec import check_genome, merged_with_defaults
from dharma_swarm.forge_lab.paired_experiment_evaluator import (
    PAIRED_OBSERVATION_SCHEMA,
    PairedEvaluationBlocked,
    PairedEvaluator,
)
from dharma_swarm.forge_lab.paired_experiment_lifecycle import cleanup_scratch, run_with_cleanup
from dharma_swarm.forge_lab.run_receipts import (
    GENERATION_RECEIPT_SCHEMA,
    _closeout,
    _now,
    _result_summary,
    _write_json,
)

WINNER_FREEZE_SCHEMA = "forge_lab.winner_freeze.v1"

class PairedRunBlocked(RuntimeError):
    """Fail-closed stop after evidence has been persisted."""

async def run_paired_frozen_v1(**kwargs: Any) -> dict[str, Any]:
    """Run the paired protocol and persist cleanup evidence on setup failure."""
    return await run_with_cleanup(_run_paired_frozen_v1_impl, kwargs)


async def _run_paired_frozen_v1_impl(
    *,
    cfg: Any, seams: Any, run_guard: Any, started_at: str, started_mono: float,
    rng: Any, base_sha: str, exp_id: str, exp_dir: Path, archive_path: Path,
    results_path: Path, scratch: Path | None, membrane: dict[str, bool],
    manifest: dict[str, Any],
    offload: Callable[..., Awaitable[Any]],
) -> dict[str, Any]:
    required = {"grade": seams.grade, "pull_task_context": seams.pull_task_context,
                "allocate_campaign_pools": seams.allocate_campaign_pools,
                "load_task_record": seams.load_task_record, "mutate_complete": seams.mutate_complete}
    missing = sorted(name for name, value in required.items() if value is None)
    if missing:
        raise ValueError(f"paired_frozen_v1 seams are missing: {missing}")

    store = CandidateStore(archive_path, experiment_id=exp_id, category=cfg.category)
    await store.load()
    champion_store = ChampionStore(cfg.state_root, category=cfg.category)
    incumbent_state = champion_store.load()
    incumbent = incumbent_state.get("champion")
    seed = merged_with_defaults(dict(cfg.seed_genome or {}))
    if not seed.get("generator_model"):
        seed["generator_model"] = cfg.solver_model
    if not seed.get("verifier_model"):
        seed["verifier_model"] = cfg.verifier_model or None
    if incumbent:
        baseline_genome = merged_with_defaults(dict(incumbent["genome"]))
        baseline_id = str(incumbent["candidate_id"])
    else:
        baseline_genome = seed
        baseline_id = ids.candidate_id(seed)
    baseline_check = check_genome(baseline_genome)
    if not baseline_check.executable:
        raise PairedRunBlocked(f"baseline_not_executable:{baseline_check.reasons}")
    if ids.candidate_id(baseline_genome) != baseline_id:
        raise PairedRunBlocked("persisted_baseline_identity_mismatch")

    counters = {"graded": 0, "blocked": 0, "errored": 0, "duplicate": 0}
    stopped_reasons: list[str] = []
    winner: dict[str, Any] | None = None
    champion_state: dict[str, Any] | None = None
    holdout_touched = False
    plan = None
    overlay = None
    ledger = CampaignBudgetLedger(
        cap_tokens=cfg.max_experiment_tokens,
        cap_usd=cfg.max_experiment_usd,
    )
    budget_path = exp_dir / "campaign_budget.json"
    paired_rows_path = exp_dir / "paired_observations.jsonl"
    candidate_records: list[dict[str, Any]] = []
    contexts: dict[str, tuple[dict, dict]] = {}

    evaluator: PairedEvaluator | None = None

    try:
        overlay = await offload(
            seams.allocate_campaign_pools,
            campaign_id=cfg.campaign_id or exp_id,
            train_count=cfg.paired_train_tasks,
            explore_count=cfg.paired_explore_tasks,
            confirm_count=cfg.paired_confirm_tasks,
            holdout_count=cfg.paired_holdout_tasks,
            campaign_seed=cfg.rng_seed,
            epoch_id=cfg.campaign_id or exp_id,
            lane_id=cfg.lane_id,
            candidate_id=baseline_id,
            min_decision_count=cfg.paired_min_decision_tasks,
        )
        records = {
            task_id: await offload(seams.load_task_record, task_id)
            for task_id in overlay["task_ids"]
        }
        plan = build_evaluation_plan_from_overlay(
            overlay_receipt=overlay,
            task_loader=records.__getitem__,
            repeat_seeds=cfg.paired_repeat_seeds,
            baseline_candidate_id=baseline_id,
            baseline_genome_sha256=ids.genome_digest(baseline_genome),
            evaluator_identity={
                "base_sha": base_sha,
                "benchmark": cfg.benchmark,
                "tier": "paired-frozen-v1",
                "seed_support": "unsupported",
                "execution_mode": manifest["execution_boundary"]["mode"],
                "execution_profile_sha256": manifest["execution_boundary"].get("execution_profile_sha256"),
            },
            created_at=started_at,
        )
        write_evaluation_plan(exp_dir / "evaluation_plan.json", plan)
        manifest.update(
            evaluation_protocol="paired_frozen_v1",
            evaluation_plan_sha256=plan.plan_sha256,
            campaign_overlay=overlay,
            champion_revision_before=incumbent_state["revision"],
            baseline_candidate_id=baseline_id,
            mutation_budget_policy={
                "token_reservation_ceiling": cfg.mutation_reservation_tokens,
                "usd_reservation_ceiling": cfg.mutation_reservation_usd,
                "usd_settlement": "reserved_ceiling_for_provider_mutation"},
        )
        _write_json(exp_dir / "run_manifest.json", manifest)
        ledger.save(budget_path)

        # Context loading happens only after the immutable plan is durable.
        for task_id in overlay["task_ids"]:
            contexts[task_id] = await offload(seams.pull_task_context, task_id)

        evaluator = PairedEvaluator(
            cfg=cfg, seams=seams, run_guard=run_guard, plan=plan, ledger=ledger,
            budget_path=budget_path, observations_path=paired_rows_path,
            baseline_genome=baseline_genome, baseline_id=baseline_id,
            contexts=contexts, store=store, experiment_id=exp_id, category=cfg.category,
            membrane=membrane, results_path=results_path, counters=counters,
            offload=offload,
        )
        baseline_train = await evaluator.ensure_baseline("train", "baseline_eval")
        baseline_explore = await evaluator.ensure_baseline("explore", "baseline_eval")
        await evaluator.archive_graded(
            genome=baseline_genome,
            candidate_id=baseline_id,
            parent_id=None,
            generation=0,
            role="persistent_baseline" if incumbent else "seed_baseline",
            per_task=baseline_explore,
            paired_stats={"train_baseline_cells": len(baseline_train)},
            notes="frozen paired baseline",
            operator="baseline",
        )

        seen_phenotypes = {ids.phenotype_id(baseline_genome)}
        for generation in range(1, cfg.generations + 1):
            generation_rows: list[dict[str, Any]] = []
            for slot in range(cfg.children):
                if run_guard is not None:
                    run_guard.checkpoint()
                graded = await store.graded_entries()
                parent = selection.sample_parent(
                    graded,
                    store.n_children_map(),
                    novelty_pressure=cfg.novelty_pressure,
                    rng=rng,
                )
                parent_row = CandidateStore._row(parent)
                parent_genome = dict(parent_row.get("genome") or {})
                failures = [
                    {
                        key: row.get(key)
                        for key in ("task_id", "error", "grade_note")
                        if row.get(key)
                    }
                    for row in parent_row.get("per_task", [])
                    if not row.get("resolved")
                ]
                archive_context = [
                    {
                        "genome": CandidateStore._row(entry).get("genome"),
                        "pass_rate": CandidateStore._row(entry).get("pass_rate"),
                    }
                    for entry in graded[:6]
                ]
                operation_id = f"mutation_{exp_id}_{generation}_{slot}"
                roll = rng.random()
                parametric = cfg.dry_run or roll < 0.2
                reservation = ledger.reserve(
                    "mutation",
                    max_tokens=0 if parametric else cfg.mutation_reservation_tokens,
                    max_usd=0 if parametric else cfg.mutation_reservation_usd,
                    operation_id=operation_id,
                )
                ledger.save(budget_path)
                try:
                    if parametric:
                        result = mutation.parametric_mutation(parent_genome, rng=rng)
                    else:
                        result = await offload(
                            mutation.llm_propose_genome,
                            parent_genome,
                            complete_fn=seams.mutate_complete,
                            failures=failures,
                            archive_context=archive_context,
                        )
                except Exception:
                    # Provider usage cannot be proven after an escaped
                    # mutation failure, so charge the full reservation before
                    # the campaign is allowed to close out.
                    ledger.settle(
                        reservation.reservation_id,
                        actual_tokens=reservation.max_tokens,
                        actual_usd=reservation.max_usd,
                    )
                    ledger.save(budget_path)
                    raise
                try:
                    ledger.settle(
                        reservation.reservation_id,
                        actual_tokens=max(0, int(result.tokens_used or 0)),
                        # Completion exposes tokens only; conservatively charge the USD ceiling.
                        actual_usd=reservation.max_usd,
                    )
                finally:
                    ledger.save(budget_path)
                if result.genome is None:
                    blocked_id = ids.candidate_id(
                        {"blocked": result.raw_output, "generation": generation, "slot": slot}
                    )
                    await store.append_blocked(
                        candidate_id=blocked_id,
                        genome=None,
                        parent_id=parent.id,
                        generation=generation,
                        loop_iteration=generation,
                        reasons=list(result.parse_issues) or ["no_genome"],
                        raw_output=result.raw_output,
                    )
                    counters["blocked"] += 1
                    continue
                child = merged_with_defaults(dict(result.genome))
                if not child.get("generator_model"):
                    child["generator_model"] = parent_genome.get("generator_model") or cfg.solver_model
                candidate_id = ids.candidate_id(child)
                checked = check_genome(child)
                if not checked.executable:
                    await store.append_blocked(
                        candidate_id=candidate_id,
                        genome=child,
                        parent_id=parent.id,
                        generation=generation,
                        loop_iteration=generation,
                        reasons=list(checked.reasons),
                        raw_output=result.raw_output,
                    )
                    counters["blocked"] += 1
                    continue
                phenotype = ids.phenotype_id(child)
                if phenotype in seen_phenotypes or await store.has(candidate_id):
                    duplicate_id = f"dup_{candidate_id[5:]}_{generation}_{slot}"
                    await store.append_duplicate(
                        candidate_id=duplicate_id,
                        genome=child,
                        parent_id=parent.id,
                        generation=generation,
                        loop_iteration=generation,
                        reasons=[f"duplicate_phenotype:{phenotype}"],
                    )
                    counters["duplicate"] += 1
                    continue
                seen_phenotypes.add(phenotype)
                train_stats, _, train_rows = await evaluator.contrast(
                    child, candidate_id, "train", "candidate_eval"
                )
                explore_stats, _, explore_rows = await evaluator.contrast(
                    child, candidate_id, "explore", "candidate_eval"
                )
                paired_stats = {"train": train_stats, "explore": explore_stats}
                _write_json(
                    exp_dir / "receipts" / f"candidate_{candidate_id}.json",
                    {"schema": "forge_lab.candidate_paired_receipt.v1", **paired_stats},
                )
                if not explore_stats["selection_eligible"]:
                    await store.append_errored(
                        candidate_id=candidate_id,
                        genome=child,
                        parent_id=parent.id,
                        generation=generation,
                        loop_iteration=generation,
                        reasons=list(explore_stats["blockers"]) or ["paired_grid_incomplete"],
                    )
                    counters["errored"] += 1
                    continue
                row = await evaluator.archive_graded(
                    genome=child,
                    candidate_id=candidate_id,
                    parent_id=parent.id,
                    generation=generation,
                    role="candidate",
                    per_task=explore_rows,
                    paired_stats=paired_stats,
                    notes=result.notes or result.operator,
                    operator=result.operator,
                )
                record = {
                    "candidate_id": candidate_id,
                    "phenotype_id": phenotype,
                    "genome": child,
                    "parent_id": parent.id,
                    "generation": generation,
                    "train": train_stats,
                    "explore": explore_stats,
                    "tokens": sum(int(item["tokens_used"]) for item in train_rows + explore_rows),
                }
                candidate_records.append(record)
                generation_rows.append(_result_summary(row))
            _write_json(
                exp_dir / "receipts" / f"generation_{generation:03}.json",
                {
                    "schema": GENERATION_RECEIPT_SCHEMA,
                    "generation": generation,
                    "rng_seed": cfg.rng_seed,
                    "task_ids": list(plan.task_ids("train") + plan.task_ids("explore")),
                    "children": generation_rows,
                    "observations": generation_rows,
                    "counters": dict(counters),
                    "tokens_spent_total": ledger.spent_tokens,
                    "at": _now(),
                },
            )

        eligible = [record for record in candidate_records if record["explore"]["selection_eligible"]]
        if eligible:
            winner = min(
                eligible,
                key=lambda record: (
                    -float(record["explore"]["clustered_ci"]["mean"]),
                    int(record["tokens"]),
                    str(record["candidate_id"]),
                ),
            )
        if winner is None or float(winner["explore"]["clustered_ci"]["mean"]) <= 0.0:
            stopped_reasons.append("no_positive_observed_explore_challenger")
        else:
            _write_json(
                exp_dir / "winner_freeze.json",
                {
                    "schema": WINNER_FREEZE_SCHEMA,
                    "candidate_id": winner["candidate_id"],
                    "phenotype_id": winner["phenotype_id"],
                    "genome_sha256": ids.genome_digest(winner["genome"]),
                    "evaluation_plan_sha256": plan.plan_sha256,
                    "selection_split": "explore",
                    "selection_rule": "paired_mean_then_tokens_then_candidate_id",
                    "paired_stats": {"train": winner["train"], "explore": winner["explore"]},
                    "frozen_at": _now(),
                    "positive_lift_claimed": False,
                },
            )
            confirm_stats, _, _ = await evaluator.contrast(
                winner["genome"], winner["candidate_id"], "confirm", "confirm_eval"
            )
            winner["confirm"] = confirm_stats
            if not confirm_stats["decision_eligible"] or float(
                confirm_stats["clustered_ci"]["mean"]
            ) < 0.0:
                stopped_reasons.append("frozen_winner_failed_confirm")
            else:
                holdout_touched = True
                holdout_stats, _, _ = await evaluator.contrast(
                    winner["genome"], winner["candidate_id"], "holdout", "holdout_eval"
                )
                winner["holdout"] = holdout_stats
                if holdout_stats["decision_eligible"]:
                    ledger.assert_closeout_ready()
                    evidence_ok, evidence_info = store.verify_evidence_merkle()
                    if not evidence_ok:
                        stopped_reasons.append(
                            f"archive_evidence_invalid_before_champion:{evidence_info}"
                        )
                        continue_promotion = False
                    else:
                        continue_promotion = True
                    metadata = build_shadow_champion(
                        category=cfg.category,
                        candidate_id=winner["candidate_id"],
                        phenotype_id=winner["phenotype_id"],
                        genome=winner["genome"],
                        genome_sha256=ids.genome_digest(winner["genome"]),
                        experiment_id=exp_id,
                        source_base_sha=base_sha,
                        evaluation_plan_sha256=plan.plan_sha256,
                        baseline_candidate_id=baseline_id,
                        paired_stats={
                            split: winner[split]
                            for split in ("train", "explore", "confirm", "holdout")
                        },
                        repeat_seeds=list(plan.repeat_seeds),
                        seed_support="unsupported",
                        campaign_budget=ledger.to_dict(),
                        selection_score=float(winner["explore"]["clustered_ci"]["mean"]),
                        selection_rule="paired_mean_then_tokens_then_candidate_id",
                        tie_break={
                            "tokens": winner["tokens"],
                            "candidate_id": winner["candidate_id"],
                        },
                    )
                    if continue_promotion:
                        try:
                            champion_state = champion_store.compare_and_swap(
                                expected_revision=int(incumbent_state["revision"]),
                                champion=metadata,
                            )
                        except ChampionConflict as exc:
                            stopped_reasons.append(f"champion_cas_conflict:{exc}")
                else:
                    stopped_reasons.append("holdout_grid_incomplete")
    except (PairedRunBlocked, PairedEvaluationBlocked, CampaignBudgetError) as exc:
        stopped_reasons.append(str(exc))
    except Exception as exc:
        stopped_reasons.append(f"paired_protocol_error:{type(exc).__name__}:{exc}"[:1000])

    chain_ok, chain_info = store.verify_evidence_merkle()
    scratch_worktree = cleanup_scratch(cfg, seams, scratch, exp_id)
    if counters["graded"] == 0 or not ledger.valid or not chain_ok:
        state = "blocked_with_evidence"
    elif winner is None or "no_positive_observed_explore_challenger" in stopped_reasons:
        state = "measured_negative"
    else:
        state = "inconclusive_low_power"
    return _closeout(
        exp_dir,
        exp_id,
        state,
        reasons=stopped_reasons,
        started_at=started_at,
        stats={
            "evaluation_protocol": "paired_frozen_v1",
            "counters": counters,
            "seed_pass_rate": next(
                (
                    CandidateStore._row(entry).get("pass_rate", 0.0)
                    for entry in await store.graded_entries()
                    if CandidateStore._row(entry).get("role") in {"seed_baseline", "persistent_baseline"}
                ),
                0.0,
            ),
            "best_pass_rate": max(
                (CandidateStore._row(entry).get("pass_rate", 0.0) for entry in await store.graded_entries()),
                default=0.0,
            ),
            "tokens_spent_total": ledger.spent_tokens,
            "campaign_budget": ledger.to_dict(),
            "evaluation_plan_sha256": None if plan is None else plan.plan_sha256,
            "winner_candidate_id": None if winner is None else winner["candidate_id"],
            "winner_frozen_before_confirm": (exp_dir / "winner_freeze.json").exists(),
            "holdout_touched": holdout_touched,
            "champion_revision_before": incumbent_state["revision"],
            "champion_revision_after": (
                incumbent_state["revision"] if champion_state is None else champion_state["revision"]
            ),
            "n_tasks_per_generation": cfg.paired_explore_tasks,
            "positive_lift_claimed": False,
            "note": "paired frozen shadow evidence; no production or positive-lift claim",
        },
        merkle_root={"verified": bool(chain_ok), "info": str(chain_info)},
        wall_seconds=round(time.monotonic() - started_mono, 1),
        scratch_worktree=scratch_worktree,
    )
__all__ = ["PAIRED_OBSERVATION_SCHEMA", "WINNER_FREEZE_SCHEMA", "run_paired_frozen_v1"]
