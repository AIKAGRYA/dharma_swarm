"""The generational EXPLORE loop — the Forge v3 chassis, wild-first.

Doctrine (freeform_explore, on main): EXPLORE freely, CONFIRM honestly,
PROMOTE rarely. This module is EXPLORE only: it can never emit a positive-lift
claim, never touches promotion, never requests live mutation. The membrane is
enforced at preflight; inside it, mutation is free.

Loop shape (packet §7): seed baseline (generation 0) → per generation:
fresh task slice from the taskbed → one parent sampled PER CHILD SLOT from the
full graded archive (novelty-pressure weighted) → mutate (LLM-proposed by
default) → dedup by content-addressed id → grade on the explore-fast tier →
append (immediately durable) → generation receipt → honest closeout.

Decomposition (leaf modules, one-directional):
  experiment_config    — ExperimentConfig, Seams, cost estimate
  experiment_git       — source-git identity probes for receipts
  experiment_preflight — membrane facts, scratch admission, run manifest
  experiment_closeout  — terminal state decision and closeout receipt
This module keeps the public API stable by re-exporting those leaves.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from dharma_swarm.forge_lab import grade_explore, ids, mutation, selection
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.experiment_closeout import finalize_closeout
from dharma_swarm.forge_lab.experiment_config import (
    ExperimentConfig,
    Seams,
    _cost_estimate,
)
from dharma_swarm.forge_lab.experiment_git import (
    _git as _git,
    _git_identity,
    _git_sha as _git_sha,
)
from dharma_swarm.forge_lab.experiment_preflight import (
    RUN_MANIFEST_SCHEMA as RUN_MANIFEST_SCHEMA,
    admit_scratch_worktree,
    initial_membrane,
    write_run_manifest,
)
from dharma_swarm.forge_lab.freeform_explore import (
    FreeformExploreEnvelope,
    validate_freeform_explore_envelope,
)
from dharma_swarm.forge_lab.genome_spec import check_genome, merged_with_defaults
from dharma_swarm.forge_lab.run_receipts import (
    AFTER_RUN_NOTES_SCHEMA,
    EXPLORE_CLOSEOUTS,
    GENERATION_RECEIPT_SCHEMA,
    RESULT_ROW_SCHEMA,
    _append_result_row,
    _closeout as _closeout,
    _now,
    _result_row,
    _result_summary,
    _write_json,
)

__all__ = [
    "ExperimentConfig",
    "Seams",
    "run_experiment",
    "EXPLORE_CLOSEOUTS",
    "RESULT_ROW_SCHEMA",
    "GENERATION_RECEIPT_SCHEMA",
    "AFTER_RUN_NOTES_SCHEMA",
]


async def run_experiment(cfg: ExperimentConfig, seams: Seams | None = None) -> dict[str, Any]:
    started_at = _now()
    started_mono = time.monotonic()
    rng = random.Random(cfg.rng_seed)
    seams = (seams or Seams()).resolved(cfg)
    git_identity = _git_identity(cfg.source_repo, dry_run=cfg.dry_run)
    base_sha = git_identity["head_sha"]
    exp_id = ids.experiment_id(
        category=cfg.category, benchmark=cfg.benchmark, started_at=started_at, base_sha=base_sha
    )
    exp_dir = cfg.state_root / cfg.category / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    archive_path = exp_dir / "archive.jsonl"
    results_path = exp_dir / "results.jsonl"

    # ---- preflight (§7a): fail-closed, each fact recorded -------------------
    membrane = initial_membrane()
    scratch, early_closeout = admit_scratch_worktree(
        cfg,
        exp_id=exp_id,
        exp_dir=exp_dir,
        archive_path=archive_path,
        seams=seams,
        started_at=started_at,
        membrane=membrane,
    )
    if early_closeout is not None:
        return early_closeout

    estimate = _cost_estimate(cfg)
    write_run_manifest(
        cfg,
        exp_id=exp_id,
        exp_dir=exp_dir,
        git_identity=git_identity,
        started_at=started_at,
        membrane=membrane,
        scratch=scratch,
        estimate=estimate,
    )
    print(f"[forge_lab] {exp_id}: estimate={estimate}")

    store = CandidateStore(archive_path, experiment_id=exp_id, category=cfg.category)
    await store.load()

    counters = {
        "graded": 0,
        "blocked": 0,
        "errored": 0,
        "duplicate": 0,
        "paired_controls": 0,
        "inconclusive_infrastructure": 0,
        "inconclusive_generation": 0,
        "inconclusive_budget": 0,
    }
    tokens_spent_total = 0
    comparable_observations_total = 0
    infrastructure_observations_total = 0
    generation_observations_total = 0
    budget_observations_total = 0
    stopped_early = ""

    async def _tasks_for_generation(gen: int) -> dict[str, tuple[dict, dict]]:
        receipt = await asyncio.to_thread(
            seams.allocate_explore,
            count=cfg.tasks_per_generation,
            epoch_id=f"{exp_id}_gen{gen}",
            lane_id=cfg.lane_id,
        )
        contexts: dict[str, tuple[dict, dict]] = {}
        for task_id in receipt.get("task_ids", []):
            contexts[task_id] = await asyncio.to_thread(seams.pull_task_context, task_id)
        return contexts

    async def _grade_and_archive(
        genome: dict[str, Any], *, cid: str, parent_id: str | None, generation: int,
        loop_iteration: int, role: str, contexts: dict, notes: str, raw: str, op: str,
        comparison_block_id: str | None = None,
        control_pass_rate: float | None = None,
    ) -> dict[str, Any]:
        nonlocal tokens_spent_total
        nonlocal comparable_observations_total
        nonlocal infrastructure_observations_total
        nonlocal generation_observations_total
        nonlocal budget_observations_total
        checked = check_genome(genome)
        if not checked.executable:
            await store.append_blocked(
                candidate_id=cid, genome=genome, parent_id=parent_id,
                generation=generation, loop_iteration=loop_iteration,
                reasons=list(checked.reasons), raw_output=raw,
            )
            counters["blocked"] += 1
            return _append_result_row(
                results_path,
                _result_row(
                    exp_id=exp_id,
                    candidate_id=cid,
                    parent_id=parent_id,
                    state="blocked",
                    role=role,
                    op=op,
                    generation=generation,
                    reasons=checked.reasons,
                ),
            )
        outcome = await asyncio.to_thread(
            grade_explore.grade_genome_explore,
            genome, contexts,
            seams=seams.grade,
            budget_cap_tokens=cfg.budget_cap_tokens,
            budget_cap_usd=cfg.budget_cap_usd,
            propose_timeout_s=cfg.propose_timeout_s,
            grade_timeout_s=cfg.grade_timeout_s,
            soft_token_cap=cfg.soft_token_cap,
        )
        tokens_spent_total += outcome.tokens_used
        comparable_observations_total += outcome.comparable_observations
        infrastructure_count = sum(
            row.get("evidence_class") == grade_explore.INCONCLUSIVE_INFRASTRUCTURE
            for row in outcome.per_task
        )
        infrastructure_observations_total += infrastructure_count
        generation_count = sum(
            row.get("evidence_class") == grade_explore.INCONCLUSIVE_GENERATION
            for row in outcome.per_task
        )
        budget_count = sum(
            row.get("evidence_class") == grade_explore.INCONCLUSIVE_BUDGET
            for row in outcome.per_task
        )
        generation_observations_total += generation_count
        budget_observations_total += budget_count
        if infrastructure_count:
            counters["inconclusive_infrastructure"] += 1
        if generation_count:
            counters["inconclusive_generation"] += 1
        if budget_count:
            counters["inconclusive_budget"] += 1
        if outcome.error:
            # Custody fail-closed: budget-invalid or zero-attempt grades are
            # errored evidence rows, never GRADED / fitness-bearing.
            await store.append_errored(
                candidate_id=cid, genome=genome, parent_id=parent_id,
                generation=generation, loop_iteration=loop_iteration,
                reasons=[outcome.error], raw_output=raw,
            )
            counters["errored"] += 1
            return _append_result_row(
                results_path,
                _result_row(
                    exp_id=exp_id,
                    candidate_id=cid,
                    parent_id=parent_id,
                    state="errored",
                    role=role,
                    op=op,
                    generation=generation,
                    pass_rate=outcome.pass_rate,
                    per_task=outcome.per_task,
                    budget=outcome.budget,
                    reasons=[outcome.error],
                ),
            )
        envelope = FreeformExploreEnvelope(
            candidate_id=cid, parent_id=parent_id, experiment_id=exp_id,
            category=cfg.category, raw_output=raw, notes=notes,
            artifacts={"operator": op},
            benchmark_receipt={
                "tier": outcome.tier,
                "pass_rate": outcome.pass_rate,
                "evidence_class": outcome.evidence_class,
                "comparable_observations": outcome.comparable_observations,
            },
            membrane=membrane,
        )
        issues = validate_freeform_explore_envelope(envelope)
        if issues:
            raise RuntimeError(f"envelope failed membrane validation: {issues}")
        await store.append_graded(
            candidate_id=cid, genome=genome, parent_id=parent_id,
            generation=generation, loop_iteration=loop_iteration, role=role,
            pass_rate=outcome.pass_rate, per_task=outcome.per_task,
            budget=outcome.budget, tier=outcome.tier,
            executed_fields=checked.executed_fields, ignored_fields=checked.ignored_fields,
            envelope=envelope, mutation_notes=notes,
            model=str(genome.get("generator_model", "")), tokens_used=outcome.tokens_used,
        )
        counters["graded"] += 1
        return _append_result_row(
            results_path,
            _result_row(
                exp_id=exp_id,
                candidate_id=cid,
                parent_id=parent_id,
                state="graded",
                role=role,
                op=op,
                generation=generation,
                pass_rate=outcome.pass_rate,
                per_task=outcome.per_task,
                budget=outcome.budget,
                evidence_class=outcome.evidence_class,
                comparable_observations=outcome.comparable_observations,
                comparison_block_id=comparison_block_id,
                control_candidate_id=seed_cid if comparison_block_id else None,
                control_pass_rate=control_pass_rate,
            ),
        )

    async def _grade_paired_control(
        generation: int, contexts: dict[str, tuple[dict, dict]]
    ) -> dict[str, Any]:
        nonlocal tokens_spent_total
        nonlocal comparable_observations_total
        nonlocal infrastructure_observations_total
        nonlocal generation_observations_total
        nonlocal budget_observations_total
        outcome = await asyncio.to_thread(
            grade_explore.grade_genome_explore,
            seed,
            contexts,
            seams=seams.grade,
            budget_cap_tokens=cfg.budget_cap_tokens,
            budget_cap_usd=cfg.budget_cap_usd,
            propose_timeout_s=cfg.propose_timeout_s,
            grade_timeout_s=cfg.grade_timeout_s,
            soft_token_cap=cfg.soft_token_cap,
        )
        tokens_spent_total += outcome.tokens_used
        comparable_observations_total += outcome.comparable_observations
        infrastructure_count = sum(
            row.get("evidence_class") == grade_explore.INCONCLUSIVE_INFRASTRUCTURE
            for row in outcome.per_task
        )
        infrastructure_observations_total += infrastructure_count
        generation_count = sum(
            row.get("evidence_class") == grade_explore.INCONCLUSIVE_GENERATION
            for row in outcome.per_task
        )
        budget_count = sum(
            row.get("evidence_class") == grade_explore.INCONCLUSIVE_BUDGET
            for row in outcome.per_task
        )
        generation_observations_total += generation_count
        budget_observations_total += budget_count
        counters["paired_controls"] += 1
        if infrastructure_count:
            counters["inconclusive_infrastructure"] += 1
        if generation_count:
            counters["inconclusive_generation"] += 1
        if budget_count:
            counters["inconclusive_budget"] += 1
        return _append_result_row(
            results_path,
            _result_row(
                exp_id=exp_id,
                candidate_id=seed_cid,
                parent_id=None,
                state="graded",
                role="paired_control",
                op="seed_control",
                generation=generation,
                pass_rate=outcome.pass_rate,
                per_task=outcome.per_task,
                budget=outcome.budget,
                evidence_class=outcome.evidence_class,
                comparable_observations=outcome.comparable_observations,
                comparison_block_id=f"{exp_id}:generation:{generation}",
                control_candidate_id=seed_cid,
                control_pass_rate=outcome.pass_rate,
            ),
        )

    # ---- generation 0: seed baseline ----------------------------------------
    seed = merged_with_defaults(dict(cfg.seed_genome or {}))
    if not seed.get("generator_model"):
        seed["generator_model"] = cfg.solver_model
    if not seed.get("verifier_model"):
        seed["verifier_model"] = cfg.verifier_model or None
    seed_cid = ids.candidate_id(seed)
    contexts = await _tasks_for_generation(0)
    await _grade_and_archive(
        seed, cid=seed_cid, parent_id=None, generation=0, loop_iteration=0,
        role="seed_baseline", contexts=contexts, notes="seed", raw="", op="seed",
    )
    graded_after_seed = await store.graded_entries()
    seed_row = next(
        (CandidateStore._row(e) for e in graded_after_seed if CandidateStore._row(e).get("role") == "seed_baseline"),
        {},
    )
    seed_budget = seed_row.get("budget") if isinstance(seed_row.get("budget"), dict) else {}
    if cfg.require_valid_seed and seed_budget.get("hard_invalid"):
        stopped_early = f"seed_baseline_hard_invalid:{seed_budget.get('hard_invalid_reason')}"
    seed_soft_cap_exceeded = bool(seed_budget.get("soft_token_cap_exceeded"))

    # ---- generations ---------------------------------------------------------
    for gen in range(1, cfg.generations + 1):
        if stopped_early:
            break
        if tokens_spent_total >= cfg.max_experiment_tokens:
            stopped_early = f"token_ceiling_reached:{tokens_spent_total}"
            break
        contexts = await _tasks_for_generation(gen)
        comparison_block_id = f"{exp_id}:generation:{gen}"
        control_row = await _grade_paired_control(gen, contexts)
        graded = await store.graded_entries()
        counts = store.n_children_map()
        gen_children: list[dict[str, Any]] = []
        for slot in range(cfg.children):
            parent = selection.sample_parent(
                graded, counts, novelty_pressure=cfg.novelty_pressure, rng=rng
            )
            parent_row = CandidateStore._row(parent)
            parent_genome = dict(parent_row.get("genome") or {})
            failures = [
                {k: r.get(k) for k in ("task_id", "error", "grade_note") if r.get(k)}
                for r in parent_row.get("per_task", []) if not r.get("resolved")
            ]
            archive_context = [
                {"genome": CandidateStore._row(e).get("genome"), "pass_rate": CandidateStore._row(e).get("pass_rate")}
                for e in graded[:6]
            ]
            # operator draw: wild by default
            roll = rng.random()
            if cfg.dry_run or (not cfg.force_single_llm_mutation and roll < 0.2):
                result = mutation.parametric_mutation(parent_genome, rng=rng)
            elif (
                not cfg.force_single_llm_mutation
                and roll < 0.4
                and len(graded) >= 2
            ):
                other = rng.choice([e for e in graded if e.id != parent.id] or graded)
                result = await asyncio.to_thread(
                    mutation.llm_propose_genome, parent_genome,
                    complete_fn=seams.mutate_complete, failures=failures,
                    archive_context=archive_context,
                    second_parent=dict(CandidateStore._row(other).get("genome") or {}),
                )
            else:
                result = await asyncio.to_thread(
                    mutation.llm_propose_genome, parent_genome,
                    complete_fn=seams.mutate_complete, failures=failures,
                    archive_context=archive_context,
                )
            if result.genome is None:
                blocked_id = ids.candidate_id(
                    {"blocked_raw": result.raw_output[:2000], "op": result.operator, "gen": gen, "slot": slot}
                )
                await store.append_blocked(
                    candidate_id=blocked_id, genome=None, parent_id=parent.id,
                    generation=gen, loop_iteration=gen,
                    reasons=list(result.parse_issues) or ["no_genome"], raw_output=result.raw_output,
                )
                counters["blocked"] += 1
                row = _append_result_row(
                    results_path,
                    _result_row(
                        exp_id=exp_id,
                        candidate_id=blocked_id,
                        parent_id=parent.id,
                        state="blocked",
                        role="candidate",
                        op=result.operator,
                        generation=gen,
                        reasons=list(result.parse_issues) or ["no_genome"],
                    ),
                )
                gen_children.append(_result_summary(row))
                continue
            child = merged_with_defaults(result.genome)
            if not str(child.get("generator_model") or "").strip():
                child["generator_model"] = parent_genome.get("generator_model") or cfg.solver_model
            cid = ids.candidate_id(child)
            if await store.has(cid):
                duplicate_id = f"dup_{cid[5:]}_{gen}_{slot}"
                await store.append_duplicate(
                    candidate_id=duplicate_id, genome=child, parent_id=parent.id,
                    generation=gen, loop_iteration=gen, reasons=[f"duplicate_of:{cid}"],
                )
                counters["duplicate"] += 1
                row = _append_result_row(
                    results_path,
                    _result_row(
                        exp_id=exp_id,
                        candidate_id=duplicate_id,
                        parent_id=parent.id,
                        state="duplicate",
                        role="candidate",
                        op=result.operator,
                        generation=gen,
                        reasons=[f"duplicate_of:{cid}"],
                        duplicate_of=cid,
                    ),
                )
                gen_children.append(_result_summary(row))
                continue
            row = await _grade_and_archive(
                child, cid=cid, parent_id=parent.id, generation=gen, loop_iteration=gen,
                role="candidate", contexts=contexts,
                notes=result.notes or f"op:{result.operator}", raw=result.raw_output, op=result.operator,
                comparison_block_id=comparison_block_id,
                control_pass_rate=control_row.get("pass_rate"),
            )
            summary = _result_summary(row)
            if (
                int(summary.get("comparable_observations") or 0) > 0
                and int(summary.get("comparable_observations") or 0)
                == int(control_row.get("comparable_observations") or 0)
                and summary.get("pass_rate") is not None
                and control_row.get("pass_rate") is not None
            ):
                summary["paired_delta"] = round(
                    float(summary["pass_rate"]) - float(control_row["pass_rate"]), 6
                )
            else:
                summary["paired_delta"] = None
            gen_children.append(summary)
        _write_json(exp_dir / "receipts" / f"generation_{gen:03}.json", {
            "schema": GENERATION_RECEIPT_SCHEMA,
            "generation": gen, "rng_seed": cfg.rng_seed, "task_ids": list(contexts),
            "comparison_block_id": comparison_block_id,
            "paired_control": _result_summary(control_row),
            "children": gen_children, "observations": gen_children, "counters": dict(counters),
            "tokens_spent_total": tokens_spent_total, "at": _now(),
        })

    # ---- honest closeout ------------------------------------------------------
    return await finalize_closeout(
        cfg,
        exp_id=exp_id,
        exp_dir=exp_dir,
        store=store,
        seams=seams,
        counters=counters,
        stopped_early=stopped_early,
        started_at=started_at,
        started_mono=started_mono,
        scratch=scratch,
        tokens_spent_total=tokens_spent_total,
        comparable_observations_total=comparable_observations_total,
        infrastructure_observations_total=infrastructure_observations_total,
        generation_observations_total=generation_observations_total,
        budget_observations_total=budget_observations_total,
        seed_soft_cap_exceeded=seed_soft_cap_exceeded,
    )
