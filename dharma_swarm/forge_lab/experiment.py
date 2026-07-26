"""The generational EXPLORE loop — the Forge v3 chassis, wild-first.

Doctrine (freeform_explore, on main): EXPLORE freely, CONFIRM honestly,
PROMOTE rarely. This module is EXPLORE only: it can never emit a positive-lift
claim, never touches promotion, never requests live mutation. The membrane is
enforced at preflight; inside it, mutation is free.

Loop shape (packet §7): seed baseline (generation 0) → per generation:
one fixed task panel allocated from the taskbed → one parent sampled PER CHILD
SLOT from the full graded archive (novelty-pressure weighted) → mutate
(LLM-proposed by default) → reject non-executed phenotype changes → dedup by
content-addressed id → grade on the same explore-fast panel → append
(immediately durable) → generation receipt → honest closeout.
"""

from __future__ import annotations

import asyncio
import platform
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.evolution_safety import evaluate_mutation, model_spend_allowed, safety_summary
from dharma_swarm.forge_lab import grade_explore, ids, mutation, selection, worktree
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.freeform_explore import (
    MEMBRANE_REQUIREMENTS,
    FreeformExploreEnvelope,
    validate_freeform_explore_envelope,
)
from dharma_swarm.forge_lab.genome_spec import (
    check_genome,
    executed_phenotype,
    merged_with_defaults,
)
from dharma_swarm.forge_lab.run_identity import git_head_sha, git_identity
from dharma_swarm.forge_lab.run_receipts import (
    AFTER_RUN_NOTES_SCHEMA,
    EXPLORE_CLOSEOUTS,
    GENERATION_RECEIPT_SCHEMA,
    RESULT_ROW_SCHEMA,
    _append_result_row,
    _closeout,
    _now,
    _result_row,
    _result_summary,
    _write_json,
)

RUN_MANIFEST_SCHEMA = "forge_lab.run_manifest.v0"
TASK_PANEL_RECEIPT_SCHEMA = "forge_lab.task_panel_receipt.v0"


@dataclass
class ExperimentConfig:
    generations: int = 2
    children: int = 3  # TOTAL per generation
    tasks_per_generation: int = 3  # legacy name: one fixed panel per experiment
    novelty_pressure: float = 0.7
    solver_model: str = ""
    verifier_model: str = ""
    mutator_model: str = ""
    seed_genome: dict[str, Any] | None = None
    budget_cap_tokens: int = 120_000  # per candidate-grade
    budget_cap_usd: float = 2.0
    soft_token_cap: bool = True
    require_valid_seed: bool = True
    max_experiment_tokens: int = 600_000
    propose_timeout_s: int = 240
    grade_timeout_s: int = 600
    rng_seed: int = 20260706
    lane_id: str = "forge_lab_chassis_v0"
    category: str = "agent_evolution"
    benchmark: str = "taskbed-explore-fresh-pr-suite"
    dry_run: bool = False
    keep_worktree: bool = False
    source_repo: Path = field(default_factory=lambda: Path.home() / "dharma_swarm")
    state_root: Path = field(default_factory=lambda: Path.home() / ".dharma" / "evolution_archive")


@dataclass
class Seams:
    """Every external effect, injectable. Production defaults built lazily."""

    grade: grade_explore.GradeSeams | None = None
    pull_task_context: Callable[[str], tuple[dict, dict]] | None = None
    allocate_explore: Callable[..., dict[str, Any]] | None = None
    mutate_complete: Callable[[str], tuple[str, int]] | None = None
    make_worktree: Callable[..., Path] | None = None
    remove_worktree: Callable[..., None] | None = None

    def resolved(self, cfg: ExperimentConfig) -> "Seams":
        if cfg.dry_run:
            return self
        from dharma_swarm.api_keys import bootstrap_runtime_env

        bootstrap_runtime_env()
        grade = self.grade or grade_explore.production_seams()
        if self.pull_task_context is None or self.allocate_explore is None:
            from dharma_swarm.forge_v1.forge_v2.runner import _pull_task_context
            from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import allocate_explore

            pull = self.pull_task_context or _pull_task_context
            alloc = self.allocate_explore or allocate_explore
        else:
            pull, alloc = self.pull_task_context, self.allocate_explore
        mutate = self.mutate_complete
        if mutate is None:
            from dharma_swarm.forge_v1.providers import PoolCompletion

            completion = PoolCompletion(cfg.mutator_model)
            mutate = completion.complete
        return Seams(
            grade=grade,
            pull_task_context=pull,
            allocate_explore=alloc,
            mutate_complete=mutate,
            make_worktree=self.make_worktree or worktree.create_marked_scratch_worktree,
            remove_worktree=self.remove_worktree or worktree.remove_scratch_worktree,
        )


def _cost_estimate(cfg: ExperimentConfig) -> dict[str, Any]:
    observations = (1 + cfg.children * cfg.generations) * cfg.tasks_per_generation
    return {
        "planned_candidate_grades": 1 + cfg.children * cfg.generations,
        "planned_observations": observations,
        "est_llm_calls_min": observations + cfg.children * cfg.generations,
        "est_wall_minutes_rough": round(observations * 1.5, 1),
        "token_ceiling": cfg.max_experiment_tokens,
        "token_ceiling_semantics": (
            "reported_usage_stop_threshold_not_provider_or_billing_ceiling"
        ),
    }


async def run_experiment(cfg: ExperimentConfig, seams: Seams | None = None) -> dict[str, Any]:
    started_at = _now()
    started_mono = time.monotonic()
    rng = random.Random(cfg.rng_seed)
    seams = (seams or Seams()).resolved(cfg)
    git_identity_info = git_identity(cfg.source_repo, dry_run=cfg.dry_run)
    base_sha = git_identity_info["head_sha"]
    exp_id = ids.experiment_id(
        category=cfg.category, benchmark=cfg.benchmark, started_at=started_at, base_sha=base_sha
    )
    exp_dir = cfg.state_root / cfg.category / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    archive_path = exp_dir / "archive.jsonl"
    results_path = exp_dir / "results.jsonl"

    # ---- preflight (§7a): fail-closed, each fact recorded -------------------
    membrane = {name: False for name in MEMBRANE_REQUIREMENTS}
    membrane["no_live_daemon_mutation"] = True  # chassis has no daemon surface
    membrane["no_secret_wallet_or_prod_access"] = True  # keys only via provider layer
    membrane["no_evaluator_grader_safety_or_archive_tamper"] = True  # read-only imports
    membrane["budget_cap_recorded"] = True
    membrane["lineage_recorded"] = True

    scratch: Path | None = None
    if cfg.dry_run:
        membrane["marked_scratch_worktree"] = True  # recorded as dry_run below
        membrane["container_or_equivalent_sandbox"] = True
    else:
        spend_ok, spend_reason = model_spend_allowed()
        if not spend_ok:
            closeout = _closeout(
                exp_dir, exp_id, "blocked_with_evidence",
                reasons=[f"spend_gate:{spend_reason}"], started_at=started_at,
                stats={}, merkle_root=None, wall_seconds=0.0,
                scratch_worktree={"path": None, "state": "not_created", "removed": None},
            )
            return closeout
        scratch = seams.make_worktree(
            source_repo=cfg.source_repo,
            experiment_id=exp_id,
            archive_path=archive_path,
            category=cfg.category,
        )
        decision = evaluate_mutation(
            target_workspace=scratch, requested_live=False, runtime_state_available=False
        )
        if not (decision.allowed and decision.effective_shadow):
            raise RuntimeError(f"membrane refused scratch worktree: {decision.denial_reason}")
        membrane["marked_scratch_worktree"] = True
        # host-pytest grading runs in isolated temp checkouts of PINNED repos;
        # recorded honestly as the sandbox-equivalence claim (U2's posture).
        membrane["container_or_equivalent_sandbox"] = True

    estimate = _cost_estimate(cfg)
    manifest = {
        "schema": RUN_MANIFEST_SCHEMA,
        "experiment_id": exp_id,
        "category": cfg.category,
        "benchmark": cfg.benchmark,
        # Historical field retained for readers; it is now the actual source
        # HEAD used to run the experiment, not origin/main.
        "git_base_sha": base_sha,
        "git_identity": git_identity_info,
        "mode": "shadow",
        "dry_run": cfg.dry_run,
        "started_at": started_at,
        "execution_host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "node": platform.node(),
            "python": platform.python_version(),
            "mac_worker_observed": platform.system() == "Darwin",
        },
        "config": {
            k: str(v) if isinstance(v, Path) else v for k, v in vars(cfg).items() if k != "seed_genome"
        },
        "seed_genome": cfg.seed_genome,
        "membrane": membrane,
        "safety": {} if cfg.dry_run else safety_summary(repo_path=scratch),
        "archive_fitness_authority": "one_wire_disabled_explicit_lab_shadow",
        "cost_estimate": estimate,
        "evaluation_design": {
            "task_panel_scope": "fixed_for_experiment",
            "comparison": "same_panel_descriptive",
            "panel_role": "adaptive_search",
            "sealed": False,
            "held_out": False,
            "mutator_exposed_to_parent_failures": True,
            "receipt": "receipts/task_panel.json",
        },
        "caveats": [
            "explore-fast tier: host-pytest on pinned repos (no Docker)",
            "the task-panel receipt pins the exact registered EXPLORE tasks",
            "legacy configuration search only; not authentic AgentBundle evolution",
            "same-panel scores are adaptive and descriptive, never a paired-lift claim",
            "reported token usage is not a provider billing ceiling",
        ],
    }
    _write_json(exp_dir / "run_manifest.json", manifest)
    print(f"[forge_lab] {exp_id}: estimate={estimate}")

    store = CandidateStore(archive_path, experiment_id=exp_id, category=cfg.category)
    await store.load()

    counters = {
        "graded": 0,
        "blocked": 0,
        "errored": 0,
        "duplicate": 0,
        "non_executed_mutation": 0,
        "executed_phenotype_changes": 0,
    }
    tokens_spent_total = 0
    mutator_tokens_spent_total = 0
    stopped_early = ""

    async def _task_panel() -> dict[str, tuple[dict, dict]]:
        receipt = await asyncio.to_thread(
            seams.allocate_explore,
            count=cfg.tasks_per_generation,
            epoch_id=f"{exp_id}_panel",
            lane_id=cfg.lane_id,
        )
        contexts: dict[str, tuple[dict, dict]] = {}
        for task_id in receipt.get("task_ids", []):
            contexts[task_id] = await asyncio.to_thread(seams.pull_task_context, task_id)
        _write_json(
            exp_dir / "receipts" / "task_panel.json",
            {
                "schema": TASK_PANEL_RECEIPT_SCHEMA,
                "experiment_id": exp_id,
                "task_ids": list(contexts),
                "requested_task_count": cfg.tasks_per_generation,
                "allocated_task_count": len(contexts),
                "allocation_complete": len(contexts) == cfg.tasks_per_generation,
                "allocation_receipt": receipt,
                "comparison_design": "same_panel_descriptive",
                "panel_role": "adaptive_search",
                "sealed": False,
                "held_out": False,
                "at": _now(),
            },
        )
        return contexts

    async def _grade_and_archive(
        genome: dict[str, Any], *, cid: str, parent_id: str | None, generation: int,
        loop_iteration: int, role: str, contexts: dict, notes: str, raw: str, op: str,
    ) -> dict[str, Any]:
        nonlocal tokens_spent_total
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
        envelope = FreeformExploreEnvelope(
            candidate_id=cid, parent_id=parent_id, experiment_id=exp_id,
            category=cfg.category, raw_output=raw, notes=notes,
            artifacts={"operator": op},
            benchmark_receipt={"tier": outcome.tier, "pass_rate": outcome.pass_rate},
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
            ),
        )

    # ---- generation 0: seed baseline ----------------------------------------
    seed = merged_with_defaults(dict(cfg.seed_genome or {}))
    if not seed.get("generator_model"):
        seed["generator_model"] = cfg.solver_model
    if not seed.get("verifier_model"):
        seed["verifier_model"] = cfg.verifier_model or None
    seed_cid = ids.candidate_id(seed)
    contexts = await _task_panel()
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
        graded = await store.graded_entries()
        counts = store.n_children_map()
        gen_children: list[dict[str, Any]] = []
        for slot in range(cfg.children):
            if tokens_spent_total >= cfg.max_experiment_tokens:
                stopped_early = f"token_ceiling_reached:{tokens_spent_total}"
                break
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
            if cfg.dry_run or roll < 0.2:
                result = mutation.parametric_mutation(parent_genome, rng=rng)
            elif roll < 0.4 and len(graded) >= 2:
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
            mutation_tokens = max(0, int(result.tokens_used or 0))
            tokens_spent_total += mutation_tokens
            mutator_tokens_spent_total += mutation_tokens
            mutation_fuse_reached = tokens_spent_total >= cfg.max_experiment_tokens
            if mutation_fuse_reached:
                stopped_early = f"token_ceiling_reached_after_mutation:{tokens_spent_total}"
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
                if mutation_fuse_reached:
                    break
                continue
            child = merged_with_defaults(result.genome)
            if not str(child.get("generator_model") or "").strip():
                child["generator_model"] = parent_genome.get("generator_model") or cfg.solver_model
            cid = ids.candidate_id(child)
            child_phenotype = executed_phenotype(child)
            parent_phenotype = executed_phenotype(parent_genome)
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
                if mutation_fuse_reached:
                    break
                continue
            if mutation_fuse_reached:
                reason = "experiment_token_fuse_reached_after_mutation"
                await store.append_blocked(
                    candidate_id=cid,
                    genome=child,
                    parent_id=parent.id,
                    generation=gen,
                    loop_iteration=gen,
                    reasons=[reason],
                    raw_output=result.raw_output,
                )
                counters["blocked"] += 1
                row = _append_result_row(
                    results_path,
                    _result_row(
                        exp_id=exp_id,
                        candidate_id=cid,
                        parent_id=parent.id,
                        state="blocked",
                        role="candidate",
                        op=result.operator,
                        generation=gen,
                        reasons=[reason],
                    ),
                )
                gen_children.append(_result_summary(row))
                break
            if child_phenotype is not None and child_phenotype == parent_phenotype:
                reason = "no_executed_phenotype_change"
                await store.append_blocked(
                    candidate_id=cid,
                    genome=child,
                    parent_id=parent.id,
                    generation=gen,
                    loop_iteration=gen,
                    reasons=[reason],
                    raw_output=result.raw_output,
                )
                counters["blocked"] += 1
                counters["non_executed_mutation"] += 1
                row = _append_result_row(
                    results_path,
                    _result_row(
                        exp_id=exp_id,
                        candidate_id=cid,
                        parent_id=parent.id,
                        state="blocked",
                        role="candidate",
                        op=result.operator,
                        generation=gen,
                        reasons=[reason],
                    ),
                )
                gen_children.append(_result_summary(row))
                continue
            if child_phenotype is not None:
                counters["executed_phenotype_changes"] += 1
            row = await _grade_and_archive(
                child, cid=cid, parent_id=parent.id, generation=gen, loop_iteration=gen,
                role="candidate", contexts=contexts,
                notes=result.notes or f"op:{result.operator}", raw=result.raw_output, op=result.operator,
            )
            gen_children.append(_result_summary(row))
            if tokens_spent_total >= cfg.max_experiment_tokens:
                stopped_early = f"token_ceiling_reached:{tokens_spent_total}"
                break
        _write_json(exp_dir / "receipts" / f"generation_{gen:03}.json", {
            "schema": GENERATION_RECEIPT_SCHEMA,
            "generation": gen, "rng_seed": cfg.rng_seed, "task_ids": list(contexts),
            "children": gen_children, "observations": gen_children, "counters": dict(counters),
            "tokens_spent_total": tokens_spent_total,
            "reported_tokens_lower_bound": tokens_spent_total,
            "token_accounting_complete": False,
            "usage_completeness": "partial_legacy",
            "tokens_spent_total_semantics": "reported_lower_bound",
            "at": _now(),
        })

    # ---- honest closeout ------------------------------------------------------
    graded = await store.graded_entries()
    graded_pairs = [(entry, CandidateStore._row(entry)) for entry in graded]
    rows = [row for _, row in graded_pairs]
    seed_pair = next(
        ((entry, row) for entry, row in graded_pairs if row.get("role") == "seed_baseline"),
        None,
    )
    seed_rate = float(seed_pair[1].get("pass_rate", 0.0) or 0.0) if seed_pair else 0.0
    candidate_pairs = [
        (entry, row)
        for entry, row in graded_pairs
        if row.get("role") == "candidate"
    ]
    winning_pair = max(
        candidate_pairs,
        key=lambda pair: float(pair[1].get("pass_rate", 0.0) or 0.0),
        default=None,
    )
    winning_entry = winning_pair[0] if winning_pair else None
    winning_row = winning_pair[1] if winning_pair else {}
    best_candidate_rate = (
        float(winning_row.get("pass_rate", 0.0) or 0.0)
        if winning_pair
        else None
    )
    best_rate = max(
        [seed_rate, *[
            float(row.get("pass_rate", 0.0) or 0.0)
            for _, row in candidate_pairs
        ]]
    )
    observed_best_delta = (
        best_candidate_rate - seed_rate
        if best_candidate_rate is not None
        else 0.0
    )
    seed_panel_saturated = seed_rate >= 1.0
    panel_ids = list(contexts)
    allocation_complete = (
        len(panel_ids) == cfg.tasks_per_generation
        and len(set(panel_ids)) == len(panel_ids)
    )

    def _observed_task_ids(row: dict[str, Any]) -> list[str]:
        return [
            str(item.get("task_id"))
            for item in row.get("per_task", [])
            if isinstance(item, dict) and item.get("task_id")
        ]

    graded_panels_complete = bool(rows) and all(
        _observed_task_ids(row) == panel_ids for row in rows
    )
    graded_observations_valid = bool(rows) and all(
        all(
            isinstance(item, dict) and item.get("valid_observation") is True
            for item in row.get("per_task", [])
        )
        for row in rows
    )
    same_panel_comparable = allocation_complete and graded_panels_complete
    entry_by_id = {entry.id: entry for entry, _ in graded_pairs}
    winning_parent = (
        entry_by_id.get(winning_entry.parent_id)
        if winning_entry is not None and winning_entry.parent_id
        else None
    )
    winning_parent_row = CandidateStore._row(winning_parent) if winning_parent else {}
    winning_child_phenotype = executed_phenotype(winning_row.get("genome"))
    winning_parent_phenotype = executed_phenotype(winning_parent_row.get("genome"))
    winning_candidate_exact_executed_change = bool(
        winning_entry is not None
        and winning_parent is not None
        and winning_child_phenotype is not None
        and winning_parent_phenotype is not None
        and winning_child_phenotype != winning_parent_phenotype
    )
    all_graded_budgets_valid = bool(rows) and all(
        not bool((row.get("budget") or {}).get("hard_invalid"))
        for row in rows
    )
    chain_ok, chain_info = store.archive.merkle_log.verify_chain()
    descriptive_movement_blockers: list[str] = []
    if not allocation_complete:
        descriptive_movement_blockers.append("task_panel_allocation_incomplete")
    if not graded_panels_complete:
        descriptive_movement_blockers.append("graded_task_panel_incomplete")
    if not graded_observations_valid:
        descriptive_movement_blockers.append("invalid_task_observation")
    if len(contexts) < 3:
        descriptive_movement_blockers.append("unique_task_ids<3")
    if seed_panel_saturated:
        descriptive_movement_blockers.append("seed_panel_saturated")
    if not winning_candidate_exact_executed_change:
        descriptive_movement_blockers.append(
            "winning_candidate_not_exact_executed_change"
        )
    if observed_best_delta <= 0:
        descriptive_movement_blockers.append("no_positive_descriptive_delta")
    if not all_graded_budgets_valid:
        descriptive_movement_blockers.append("hard_invalid_graded_budget")
    if stopped_early:
        descriptive_movement_blockers.append("experiment_stopped_early")
    if git_identity_info.get("dirty"):
        descriptive_movement_blockers.append("dirty_source_identity")
    if not chain_ok:
        descriptive_movement_blockers.append("archive_merkle_invalid")
    if seed_panel_saturated:
        configuration_signal_status = "saturated_seed_panel"
    elif not winning_candidate_exact_executed_change:
        configuration_signal_status = "no_executed_child"
    elif not same_panel_comparable:
        configuration_signal_status = "incomplete_same_panel_comparison"
    elif len(contexts) < 3:
        configuration_signal_status = "insufficient_unique_task_panel"
    elif observed_best_delta > 0:
        configuration_signal_status = "positive_descriptive_delta"
    elif observed_best_delta < 0:
        configuration_signal_status = "negative_descriptive_delta"
    else:
        configuration_signal_status = "no_descriptive_delta"
    signal_status = configuration_signal_status  # legacy key, non-causal values
    if counters["graded"] == 0:
        state = "blocked_with_evidence"
    elif best_rate <= seed_rate and best_rate == 0.0:
        state = "measured_negative"
    else:
        state = "inconclusive_low_power"  # explore can never claim positive lift
    scratch_worktree = {
        "path": str(scratch) if scratch is not None else None,
        "keep_worktree": cfg.keep_worktree,
        "state": "not_created" if scratch is None else "kept" if cfg.keep_worktree else "pending_cleanup",
        "removed": None if scratch is None or cfg.keep_worktree else False,
    }
    if scratch is not None and not cfg.keep_worktree:
        try:
            seams.remove_worktree(source_repo=cfg.source_repo, repo=scratch, experiment_id=exp_id)
        except Exception as exc:
            scratch_worktree.update(
                {"state": "cleanup_error", "removed": False, "error": f"{type(exc).__name__}:{exc}"}
            )
        else:
            removed = not scratch.exists()
            scratch_worktree.update(
                {"state": "removed" if removed else "remove_unconfirmed", "removed": removed}
            )
    closeout = _closeout(
        exp_dir, exp_id, state,
        reasons=[stopped_early] if stopped_early else [],
        started_at=started_at,
        stats={
            "counters": counters,
            "seed_pass_rate": seed_rate,
            "best_pass_rate": best_rate,
            "best_candidate_pass_rate": best_candidate_rate,
            "observed_best_delta": observed_best_delta,
            "winning_candidate_id": winning_entry.id if winning_entry else None,
            "winning_parent_id": winning_entry.parent_id if winning_entry else None,
            "winning_candidate_exact_executed_change": (
                winning_candidate_exact_executed_change
            ),
            "tokens_spent_total": tokens_spent_total,
            "mutator_tokens_spent_total": mutator_tokens_spent_total,
            "reported_tokens_lower_bound": tokens_spent_total,
            "reported_mutator_tokens_lower_bound": mutator_tokens_spent_total,
            "token_accounting_complete": False,
            "unknown_usage_possible": True,
            "usage_completeness": "partial_legacy",
            "tokens_spent_total_semantics": "reported_lower_bound",
            "n_tasks_per_generation": cfg.tasks_per_generation,
            "requested_task_count": cfg.tasks_per_generation,
            "allocated_task_count": len(panel_ids),
            "task_panel_ids": panel_ids,
            "unique_task_ids": len(contexts),
            "same_panel_comparable": same_panel_comparable,
            "same_panel_descriptive_comparable": same_panel_comparable,
            "graded_panels_complete": graded_panels_complete,
            "graded_observations_valid": graded_observations_valid,
            "seed_panel_saturated": seed_panel_saturated,
            "executed_phenotype_changes": counters["executed_phenotype_changes"],
            "non_executed_mutations": counters["non_executed_mutation"],
            "signal_status": signal_status,
            "configuration_signal_status": configuration_signal_status,
            "descriptive_movement_eligible": not descriptive_movement_blockers,
            "descriptive_movement_blockers": descriptive_movement_blockers,
            "evidence_level": "L0_LegacyConfigurationSignal",
            "research_interpretation": "configuration_search_signal",
            "authentic_mutation": False,
            "panel_role": "adaptive_search",
            "sealed": False,
            "held_out": False,
            "mutator_exposed_to_parent_failures": True,
            "paired_lift_claim_eligible": False,
            "authority_granted": False,
            "seed_soft_token_cap_exceeded": seed_soft_cap_exceeded,
            "soft_token_cap": cfg.soft_token_cap,
            "experiment_token_fuse": (
                "reported-usage stop threshold checked before each child and "
                "after mutation/grade; not a request-level or billing ceiling"
            ),
            "require_valid_seed": cfg.require_valid_seed,
            "note": (
                "adaptive legacy configuration-search evidence only; "
                "best-of-run deltas are selection-biased and non-causal"
            ),
        },
        merkle_root={"verified": bool(chain_ok), "info": str(chain_info)},
        wall_seconds=round(time.monotonic() - started_mono, 1),
        scratch_worktree=scratch_worktree,
    )
    return closeout


def _git_sha(repo: Path) -> str:
    return git_head_sha(repo)


__all__ = [
    "ExperimentConfig",
    "Seams",
    "run_experiment",
    "EXPLORE_CLOSEOUTS",
    "RESULT_ROW_SCHEMA",
    "GENERATION_RECEIPT_SCHEMA",
    "TASK_PANEL_RECEIPT_SCHEMA",
    "AFTER_RUN_NOTES_SCHEMA",
]
