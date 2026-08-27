"""Bounded, offline campaign orchestration for one pinned target.

This layer exercises proposal, evaluation, tripwire, and held-out semantics.  It
does not mint improvement receipts: binding a promoted candidate to an exact
replayed artifact and pre-registered benchmark belongs to the separate digest
layer.  In particular, a synthetic dry-run score is exploration evidence only,
not an isolation, artifact-lineage, or improvement claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.foundry.army import MutationBudget
from dharma_swarm.foundry.evaluator import Candidate, CallableEvaluator, Evaluator, EvalMetrics
from dharma_swarm.foundry.loop import FoundryLoop, ProposeFn
from dharma_swarm.foundry.targets import TargetSpec, assert_contributable


@dataclass
class CampaignConfig:
    generations: int = 5
    per_generation: int = 6
    strategy: str = "explore"
    survival_threshold: float = 0.5
    budget_cap_usd: float = 300.0
    timing_floor_s: float = 0.0
    baseline_metric: float = 0.0


@dataclass
class CampaignResult:
    target_id: str
    generations_run: int = 0
    proposed: int = 0
    ring1_wins: int = 0
    tripwire_trips: int = 0
    ring2_checked: int = 0
    ring2_survivors: int = 0
    ring2_promotion_blocked: int = 0
    provider_failures: int = 0
    best_fitness: float = 0.0
    mean_survival: float = 0.0
    spend_usd: float = 0.0
    # Retained for API compatibility.  This offline layer never appends to it.
    receipt_ids: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    trip_reasons: dict[str, int] = field(default_factory=dict)


def run_campaign(
    spec: TargetSpec,
    evaluator: Evaluator,
    propose_fn: ProposeFn,
    *,
    heldout_evaluators: dict[str, Evaluator],
    config: CampaignConfig | None = None,
    counterparty: str = "",
    state_root: Path | None = None,
) -> CampaignResult:
    """Run a bounded campaign without persisting promotion claims.

    ``counterparty`` is retained for call compatibility with the former receipt
    writer.  The digest layer must separately bind an exact replay artifact,
    pinned target, benchmark, and isolation proofs before persistence.
    """
    assert_contributable(spec)  # refuse do-not-touch / AI-banned targets
    config = config or CampaignConfig()
    result = CampaignResult(target_id=spec.id, started_at=datetime.now(timezone.utc).isoformat())

    loop = FoundryLoop(
        evaluator=evaluator,
        propose_fn=propose_fn,
        heldout_evaluators=heldout_evaluators,
        allowed_paths=spec.evolve_paths or None,
        strategy=config.strategy,
        per_generation=config.per_generation,
        timing_floor_s=config.timing_floor_s,
        survival_threshold=config.survival_threshold,
        win_floor=config.baseline_metric,
        budget=MutationBudget(cap_usd=config.budget_cap_usd),
        state_root=state_root,
    )

    reports = loop.run(config.generations)
    result.generations_run = len(reports)
    result.proposed = sum(r.proposed for r in reports)
    result.ring1_wins = sum(r.ring1_wins for r in reports)
    result.provider_failures = sum(r.provider_failures for r in reports)
    result.tripwire_trips = sum(r.tripwire_trips for r in reports)
    for report in reports:
        for reason, count in report.trip_reasons.items():
            result.trip_reasons[reason] = result.trip_reasons.get(reason, 0) + count
    result.ring2_checked = sum(r.ring2_checked for r in reports)
    result.ring2_survivors = sum(r.ring2_survivors for r in reports)
    result.ring2_promotion_blocked = sum(r.ring2_promotion_blocked for r in reports)
    result.spend_usd = round(sum(r.spend_usd for r in reports), 6)
    best = loop.grid.best()
    result.best_fitness = best.fitness if best else 0.0
    rates = [rate for r in reports for rate in r.survival_rates]
    result.mean_survival = round(sum(rates) / len(rates), 6) if rates else 0.0
    result.finished_at = datetime.now(timezone.utc).isoformat()
    return result


# --- hermetic dry run (no external deps / keys / network) --------------------

_SPEED = re.compile(r"SPEED=([0-9.]+)")


def _dry_evaluator(scale: float = 1.0, eid: str = "dry-eval") -> CallableEvaluator:
    def score(candidate: Candidate, seed: int) -> EvalMetrics:
        m = _SPEED.search(candidate.diff)
        val = float(m.group(1)) * scale if m else 0.0
        return EvalMetrics(primary_score=val, correctness_passed=True,
                           metrics={"speedup": val}, wall_clock_s=0.5)

    return CallableEvaluator(evaluator_id=eid, score_fn=score)


def _dry_proposer(spec: TargetSpec) -> ProposeFn:
    path = (spec.evolve_paths or ["kernels/k.py"])[0].rstrip("/") + "/candidate.py"

    def propose(model, parent_id, seed):
        speed = round((seed % 5) * 0.4 + 0.6, 2)
        diff = f"--- a/{path}\n+++ b/{path}\n+SPEED={speed}\n"
        return Candidate(candidate_id=f"{model.id}-{seed}", target_id=spec.id,
                         diff=diff, origin_model=model.id, parent_id=parent_id)

    return propose


def dry_run_campaign(
    spec: TargetSpec,
    *,
    config: CampaignConfig | None = None,
    state_root: Path | None = None,
) -> CampaignResult:
    """Exercise the offline loop; synthetic evaluators never prove promotion."""
    return run_campaign(
        spec,
        evaluator=_dry_evaluator(),
        propose_fn=_dry_proposer(spec),
        heldout_evaluators={"holdout": _dry_evaluator(scale=0.85, eid="dry-holdout")},
        config=config,
        counterparty=spec.name,
        state_root=state_root,
    )
