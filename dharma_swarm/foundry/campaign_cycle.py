"""The real campaign as a daemon cycle — how the Foundry runs around the clock.

:func:`real_campaign_cycle` matches the daemon's ``CycleFn`` signature, so the
standing engine (``daemon.run_daemon``) can run bounded REAL campaigns —
pinned target, real oracle in Docker, live army — cycle after cycle, with the
daemon supplying what one-shot runs lack: kill-switch checks between cycles,
kill-metric verdicts, a persistent monthly spend ledger, and systemd
supervision (restart on crash, survive reboots).

Honest accounting: the returned ``CampaignResult.spend_usd`` includes BOTH the
loop's in-loop budget charges and the proposer's metered token cost at the
provider's upper-bound rate, so the daemon's budget guard sees the true burn.

Each cycle is an independent bounded campaign (fresh elite grid). Receipts and
survivor artifacts accumulate under the shared state root across cycles.
Cross-cycle elite-grid lineage is a known next rung, not a claim.
"""

from __future__ import annotations

from pathlib import Path

from dharma_swarm.foundry.campaign import CampaignConfig, CampaignResult, run_campaign
from dharma_swarm.foundry.live import estimate_cost_usd
from dharma_swarm.foundry.oracle_evaluator import OracleEvaluator, sentinel_metrics_parser
from dharma_swarm.foundry.real_proposer import real_proposer
from dharma_swarm.foundry.runner_isolation import IsolationPolicy, docker_available
from dharma_swarm.foundry.target_ingest import ingest
from dharma_swarm.foundry.targets import TARGET_REGISTRY, assert_contributable

ORACLE_TIMEOUT_S = 600.0


def real_campaign_cycle(
    target_id: str,
    generations: int,
    budget_cap: float,
    state_root: "Path | None",
) -> CampaignResult:
    """One daemon cycle = one bounded REAL campaign against ``target_id``."""
    spec = TARGET_REGISTRY[target_id]
    assert_contributable(spec)
    if not spec.objective:
        raise RuntimeError(
            f"target {spec.id} has no objective — cannot run unattended; "
            "set TargetSpec.objective"
        )

    docker_ok = docker_available()
    pinned = ingest(spec)
    policy = IsolationPolicy(
        timeout_s=ORACLE_TIMEOUT_S,
        docker_image=spec.docker_image or "python:3.11-slim",
    )

    def _make_eval(eid: str, cmd) -> OracleEvaluator:
        ev = OracleEvaluator(
            evaluator_id=eid, pinned_root=Path(pinned.root), oracle_cmd=cmd,
            evolve_paths=spec.evolve_paths, metric_parser=sentinel_metrics_parser(),
            policy=policy, docker_ok=docker_ok,
        )
        ev.prepare()
        return ev

    oracle = _make_eval(f"oracle:{spec.id}", spec.oracle_cmd)
    baseline = oracle.baseline.primary_score if oracle.baseline else 0.0

    heldout = {}
    if spec.heldout_cmd:
        heldout["heldout"] = _make_eval(f"heldout:{spec.id}", ["bash", "-c", spec.heldout_cmd])

    evolve_file = (spec.evolve_paths or [""])[0]
    if not evolve_file or evolve_file.endswith("/"):
        raise RuntimeError(f"target {spec.id} evolve scope is not a single file")

    propose = real_proposer(
        target_id=spec.id, pinned_root=Path(pinned.root),
        evolve_file=evolve_file, objective=spec.objective,
    )

    config = CampaignConfig(
        generations=generations,
        budget_cap_usd=budget_cap,
        baseline_metric=baseline,
    )
    result = run_campaign(
        spec, oracle, propose,
        heldout_evaluators=heldout, config=config,
        state_root=state_root,
        tree_digest=pinned.tree_digest, resolved_sha=pinned.resolved_sha,
        isolation_level=oracle.last_isolation_level or "local_restricted",
    )

    usage = getattr(propose, "usage", {"tokens": 0, "calls": 0})
    provider = getattr(propose, "resolved", {}).get("provider", "")
    result.spend_usd = round(
        result.spend_usd + estimate_cost_usd(provider, usage.get("tokens", 0)), 6
    )
    return result
