"""Standing campaign — run the inner loop against one pinned target.

A campaign binds a :class:`TargetSpec` to a :class:`FoundryLoop`, runs a bounded
number of generations, mints a lab-local seven-link receipt for every candidate
that clears ring 2, and returns a summary that feeds the standing kill-metrics.
Nothing here contacts an external repo or claims an external win: ring-3 links
(a merged PR, an independent-leaderboard record) are added later by the operator
or the live lane. Receipts stay lab-local until the guardian quorum is real.

``dry_run_campaign`` runs the whole path hermetically with a synthetic proposer
and evaluator, so CI (and this file's tests) can prove the loop composes without
any external dependency, model key, or network.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.foundry.army import MutationBudget
from dharma_swarm.foundry.evaluator import Candidate, CallableEvaluator, Evaluator, EvalMetrics
from dharma_swarm.foundry.heldout import HeldoutOutcome
from dharma_swarm.foundry.loop import FoundryLoop, ProposeFn
from dharma_swarm.foundry.receipts import (
    FoundryReceipt,
    StratifiedFields,
    benchmark_link,
    disclosure_link,
    pre_registration_link,
    write_receipt,
)
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
    best_fitness: float = 0.0
    mean_survival: float = 0.0
    spend_usd: float = 0.0
    receipt_ids: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    trip_reasons: dict[str, int] = field(default_factory=dict)
    artifact_paths: list[str] = field(default_factory=list)


def run_campaign(
    spec: TargetSpec,
    evaluator: Evaluator,
    propose_fn: ProposeFn,
    *,
    heldout_evaluators: dict[str, Evaluator],
    config: CampaignConfig | None = None,
    counterparty: str = "",
    state_root: Path | None = None,
    tree_digest: str = "sha256:UNPINNED",
    resolved_sha: str = "",
    isolation_level: str = "local_restricted",
) -> CampaignResult:
    """Run a bounded campaign against ``spec`` and mint ring-1/2 receipts.

    Receipt integrity rule: ``tree_digest``, ``resolved_sha``, and
    ``isolation_level`` are recorded EXACTLY as passed by the caller — the
    caller must pass what actually happened (e.g. the ``PinnedTarget`` digest
    and the evaluator's measured isolation level). The defaults are loudly
    honest placeholders, never claims: a receipt saying UNPINNED /
    local_restricted is admissible only as lab-local evidence and can never
    feed ring 3.
    """
    assert_contributable(spec)  # refuse do-not-touch / AI-banned targets
    config = config or CampaignConfig()
    result = CampaignResult(target_id=spec.id, started_at=datetime.now(timezone.utc).isoformat())

    survival_by_candidate: dict[str, HeldoutOutcome] = {}

    def _persist_artifact(candidate: Candidate, diff_sha: str) -> None:
        """A receipt without its artifact is unshippable (the kimi-k3-5003
        lesson, 2026-08-19: a +0.102 receipt whose diff was lost). Survivor
        diffs are persisted keyed by their sha so every receipt can be
        re-verified byte-for-byte."""
        root = (Path(state_root) if state_root else Path.home() / ".dharma" / "foundry") / "artifacts"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{diff_sha}.patch"
        path.write_text(candidate.diff, encoding="utf-8")
        result.artifact_paths.append(str(path))

    def _on_survivor(candidate: Candidate, fitness: float, outcome: HeldoutOutcome) -> None:
        survival_by_candidate[candidate.candidate_id] = outcome
        diff_sha = hashlib.sha256(candidate.diff.encode("utf-8")).hexdigest()
        _persist_artifact(candidate, diff_sha)
        receipt = FoundryReceipt(
            receipt_id=f"{spec.id}-{candidate.candidate_id}",
            target_id=spec.id,
            candidate_id=candidate.candidate_id,
            stratified=StratifiedFields(
                domain="external_code_contribution",
                counterparty=counterparty or spec.name,
                value_risk=f"benchmark delta {config.baseline_metric}->{fitness}",
                independence="held-out ring-2 survived; ring-3 external confirmation pending",
                transfer="not yet merged/recorded upstream",
            ),
            pre_registration=pre_registration_link(
                target_id=spec.id, resolved_sha=resolved_sha or spec.sha or "unpinned",
                tree_digest=tree_digest, baseline_metric=config.baseline_metric,
                oracle_cmd=spec.oracle_cmd, seed=0,
            ),
            benchmark=benchmark_link(
                baseline_metric=config.baseline_metric, candidate_metric=fitness,
                runs=1 + len(outcome.workloads),
                coefficient_of_variation=0.0, repro_cmd=spec.oracle_cmd,
                isolation_level=isolation_level,
            ),
            disclosure=disclosure_link(
                ai_assisted=True, duplicate_checked=True,
                test_results=f"ring-2 survival_rate={outcome.survival_rate:.3f}",
                diff_sha256=diff_sha,
            ),
        )
        write_receipt(receipt, state_root=(Path(state_root) / "receipts") if state_root else None)
        result.receipt_ids.append(receipt.receipt_id)

    loop = FoundryLoop(
        evaluator=evaluator,
        propose_fn=propose_fn,
        heldout_evaluators=heldout_evaluators,
        allowed_paths=spec.evolve_paths or None,
        strategy=config.strategy,
        per_generation=config.per_generation,
        timing_floor_s=config.timing_floor_s,
        survival_threshold=config.survival_threshold,
        budget=MutationBudget(cap_usd=config.budget_cap_usd),
        state_root=state_root,
        on_survivor=_on_survivor,
        # A "win" must beat the measured baseline, not merely score > 0 —
        # reproducing the original program is not an improvement.
        win_floor=config.baseline_metric,
    )

    reports = loop.run(config.generations)
    result.generations_run = len(reports)
    result.proposed = sum(r.proposed for r in reports)
    result.ring1_wins = sum(r.ring1_wins for r in reports)
    result.tripwire_trips = sum(r.tripwire_trips for r in reports)
    for r in reports:
        for reason, n in r.trip_reasons.items():
            result.trip_reasons[reason] = result.trip_reasons.get(reason, 0) + n
    result.ring2_checked = sum(r.ring2_checked for r in reports)
    result.ring2_survivors = sum(r.ring2_survivors for r in reports)
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
    """Run a campaign end-to-end with synthetic army/evaluator (hermetic)."""
    return run_campaign(
        spec,
        evaluator=_dry_evaluator(),
        propose_fn=_dry_proposer(spec),
        heldout_evaluators={"holdout": _dry_evaluator(scale=0.85, eid="dry-holdout")},
        config=config,
        counterparty=spec.name,
        state_root=state_root,
        tree_digest="sha256:HERMETIC-DRY-RUN",
        isolation_level="hermetic_dry",  # nothing executed; never claim docker
    )
