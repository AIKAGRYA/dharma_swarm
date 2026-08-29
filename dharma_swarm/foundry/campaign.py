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
import json
import math
import os
import re
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from dharma_swarm.foundry.army import MutationBudget
from dharma_swarm.foundry.evaluator import (
    Candidate,
    CallableEvaluator,
    Evaluator,
    EvalMetrics,
    canonical_digest,
)
from dharma_swarm.foundry.heldout import HeldoutOutcome
from dharma_swarm.foundry.loop import FoundryLoop, ProposeFn
from dharma_swarm.foundry.live import (
    ProviderUsageUnverifiable,
    estimate_cost_usd,
)
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
    ring2_promotion_blocked: int = 0
    provider_failures: int = 0
    best_fitness: float = 0.0
    mean_survival: float = 0.0
    spend_usd: float = 0.0
    receipt_ids: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    trip_reasons: dict[str, int] = field(default_factory=dict)
    artifact_paths: list[str] = field(default_factory=list)
    duplicate_candidates: int = 0
    campaign_id: str = ""
    provider_attempts: list[dict] = field(default_factory=list)
    provider_tokens_by_provider: dict[str, int] = field(default_factory=dict)
    provider_route_provenance: dict[str, dict] = field(default_factory=dict)
    provider_usage_verified: bool = True
    provider_cost_usd: float = 0.0
    provider_accounting_digest: str = ""
    provider_accounting_path: str = ""


def _validated_provider_cost(
    tokens_by_provider: dict[str, int],
    route_provenance: dict[str, dict],
) -> float:
    """Price usage only from a complete, explicit route/tariff binding."""
    total = 0.0
    for provider, tokens in tokens_by_provider.items():
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise ProviderUsageUnverifiable("provider token accounting is invalid")
        route = route_provenance.get(provider)
        if not isinstance(route, dict):
            raise ProviderUsageUnverifiable("provider route provenance is missing")
        base_url = route.get("base_url")
        model = route.get("model")
        provenance = route.get("tariff_provenance")
        rate = route.get("tariff_usd_per_mtok_upper_bound")
        checked_raw = route.get("tariff_checked_at")
        valid_raw = route.get("tariff_valid_until")
        try:
            checked_at = datetime.fromisoformat(
                str(checked_raw).replace("Z", "+00:00")
            )
            valid_until = datetime.fromisoformat(
                str(valid_raw).replace("Z", "+00:00")
            )
            if checked_at.tzinfo is None or valid_until.tzinfo is None:
                raise ValueError("tariff timestamps must be timezone-aware")
            checked_at = checked_at.astimezone(timezone.utc)
            valid_until = valid_until.astimezone(timezone.utc)
        except (TypeError, ValueError):
            checked_at = valid_until = None
        if (
            not isinstance(base_url, str)
            or not base_url.startswith("https://")
            or not isinstance(model, str)
            or not model
            or not isinstance(provenance, str)
            or not provenance
            or isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not math.isfinite(float(rate))
            or float(rate) < 0
            or checked_at is None
            or valid_until is None
            or not checked_at < valid_until
            or datetime.now(timezone.utc) >= valid_until
        ):
            raise ProviderUsageUnverifiable("provider tariff provenance is invalid")
        total += estimate_cost_usd(
            provider, tokens, rate_upper_bound=float(rate)
        )
    return round(total, 6)


def _validate_attempt_bindings(
    attempts: list[dict], route_provenance: dict[str, dict]
) -> None:
    for attempt in attempts:
        provider = attempt.get("provider")
        route = route_provenance.get(provider)
        if not isinstance(provider, str) or not isinstance(route, dict):
            raise ProviderUsageUnverifiable("provider attempt route is unbound")
        category = attempt.get("category")
        rate = route.get("tariff_usd_per_mtok_upper_bound")
        if rate is None:
            if (
                category not in {"tariff_unverified", "route_retired"}
                or attempt.get("tokens") != 0
                or attempt.get("attempt") != 0
            ):
                raise ProviderUsageUnverifiable("unpriced provider attempt is invalid")
            continue
        if (
            attempt.get("route_base_url") != route.get("base_url")
            or attempt.get("tariff_usd_per_mtok_upper_bound") != rate
            or attempt.get("tariff_provenance") != route.get("tariff_provenance")
            or attempt.get("tariff_checked_at") != route.get("tariff_checked_at")
            or attempt.get("tariff_valid_until") != route.get("tariff_valid_until")
        ):
            raise ProviderUsageUnverifiable("provider attempt tariff tuple mismatch")
        if (
            category != "model_tariff_mismatch"
            and attempt.get("model") != route.get("model")
        ):
            raise ProviderUsageUnverifiable("provider attempt model is unpriced")


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
    artifact_builder: Callable[[Candidate, dict], dict] | None = None,
    lineage_base_root: Path | None = None,
    evaluator_image_digest: str = "",
    evaluator_config_digest: str = "",
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

    registered_at = datetime.now(timezone.utc).isoformat()
    preregistration_body = {
        "schema_version": "foundry_preregistration.v1",
        "target_id": spec.id,
        "resolved_sha": resolved_sha or spec.sha or "unpinned",
        "tree_digest": tree_digest,
        "baseline_metric": config.baseline_metric,
        "oracle_cmd": spec.oracle_cmd,
        "evaluator_id": evaluator.evaluator_id,
        "evaluator_config_digest": evaluator_config_digest,
        "evaluator_image_digest": evaluator_image_digest,
        "seed_schedule": list(range(config.generations)),
        "required_repetitions": 2,
        "registered_at": registered_at,
    }
    preregistration_digest = canonical_digest(preregistration_body)
    result.campaign_id = "campaign-" + hashlib.sha256(
        f"{preregistration_digest}:{result.started_at}:{uuid.uuid4().hex}".encode("utf-8")
    ).hexdigest()
    preregistration_path = ""
    if state_root is not None:
        prereg_root = Path(state_root) / "preregistrations"
        prereg_root.mkdir(parents=True, exist_ok=True)
        prereg = prereg_root / (
            preregistration_digest.removeprefix("sha256:") + ".json"
        )
        payload = (json.dumps(
            {**preregistration_body, "digest": preregistration_digest},
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n").encode("utf-8")
        try:
            with prereg.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            directory = os.open(prereg_root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except FileExistsError:
            if prereg.read_bytes() != payload:
                raise RuntimeError("preregistration content-address collision")
        directory = os.open(prereg_root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        preregistration_path = str(prereg.relative_to(Path(state_root)))

    survival_by_candidate: dict[str, HeldoutOutcome] = {}

    def _on_survivor(
        candidate: Candidate,
        fitness: float,
        outcome: HeldoutOutcome,
        evaluation_evidence: dict,
    ) -> None:
        survival_by_candidate[candidate.candidate_id] = outcome
        if artifact_builder is None:
            raise RuntimeError(
                "ring-2 promotion requires a cumulative replay artifact builder"
            )
        observations = [
            float(value)
            for value in evaluation_evidence.get("primary_scores", [])
        ]
        if len(observations) < 2 or any(
            not math.isfinite(value) for value in observations
        ):
            raise RuntimeError("promotion lacks finite repeated ring-1 observations")
        mean = statistics.fmean(observations)
        if not math.isfinite(mean):
            raise RuntimeError("promotion repeated score mean is non-finite")
        if mean:
            coefficient = statistics.pstdev(observations) / abs(mean)
        elif all(value == 0 for value in observations):
            coefficient = 0.0
        else:
            raise RuntimeError("promotion variance is undefined around zero mean")
        if not math.isfinite(coefficient):
            raise RuntimeError("promotion score variance is non-finite")
        delta_sha = hashlib.sha256(candidate.diff.encode("utf-8")).hexdigest()
        from dharma_swarm.foundry.artifacts import DuplicateArtifact

        try:
            artifact_lineage = artifact_builder(candidate, evaluation_evidence)
        except DuplicateArtifact:
            result.duplicate_candidates += 1
            return
        diff_sha = str(artifact_lineage.get("cumulative_sha256", delta_sha))
        cumulative_path = artifact_lineage.get("cumulative_artifact")
        if cumulative_path:
            root = Path(state_root) if state_root else Path.home() / ".dharma" / "foundry"
            path = Path(str(cumulative_path))
            result.artifact_paths.append(str(path if path.is_absolute() else root / path))
        proof_levels = sorted({
            str(proof.get("isolation_level", "unknown"))
            for proof in outcome.isolation_proofs.values()
        })
        measured_isolation = "+".join(proof_levels) if proof_levels else "unproven"
        existing_digests: set[str] = set()
        receipt_root = (
            Path(state_root) / "receipts"
            if state_root is not None else Path.home() / ".dharma" / "foundry" / "receipts"
        )
        compared = 0
        for existing in receipt_root.glob("*.json"):
            try:
                existing_payload = json.loads(existing.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            compared += 1
            prior_sha = str(
                (existing_payload.get("artifact_lineage") or {}).get(
                    "cumulative_sha256", ""
                )
            )
            if prior_sha:
                existing_digests.add(prior_sha)
        duplicate_evidence = {
            "method": "cumulative_sha256_exact",
            "receipts_compared": compared,
            "candidate_cumulative_sha256": diff_sha,
            "matches": int(diff_sha in existing_digests),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        if duplicate_evidence["matches"]:
            raise RuntimeError("duplicate cumulative artifact passed pre-persist guard")
        attempts = list(candidate.metadata.get("provider_attempts", ()))
        provider_tokens: dict[str, int] = {}
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            provider = str(attempt.get("provider", "unknown"))
            provider_tokens[provider] = provider_tokens.get(provider, 0) + int(
                attempt.get("tokens", 0) or 0
            )
        provider_accounting = {
            "provider": candidate.metadata.get("provider", ""),
            "model": candidate.metadata.get("routed_model", ""),
            "calls": sum(
                1 for attempt in attempts
                if isinstance(attempt, dict) and int(attempt.get("attempt", 1) or 0) > 0
            ),
            "tokens_by_provider": provider_tokens,
            "attempts": attempts,
            "route_provenance": dict(
                candidate.metadata.get("provider_route_provenance", {})
            ),
            "usage_verified": candidate.metadata.get("usage_verified") is True,
        }
        if not provider_accounting["usage_verified"]:
            raise RuntimeError("provider usage is not verifiable; promotion refused")
        _validate_attempt_bindings(
            attempts, provider_accounting["route_provenance"]
        )
        provider_accounting["cost_usd_upper_bound"] = _validated_provider_cost(
            provider_tokens, provider_accounting["route_provenance"]
        )
        receipt = FoundryReceipt(
            receipt_id=(
                f"{spec.id}-{candidate.candidate_id}-{diff_sha[:16]}-"
                f"{uuid.uuid4().hex[:12]}"
            ),
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
                registered_at=registered_at,
                manifest_path=preregistration_path,
                manifest_digest=preregistration_digest,
                evaluator_id=evaluator.evaluator_id,
                evaluator_image_digest=evaluator_image_digest,
            ),
            benchmark=benchmark_link(
                baseline_metric=config.baseline_metric, candidate_metric=fitness,
                runs=len(observations),
                coefficient_of_variation=coefficient, repro_cmd=spec.oracle_cmd,
                isolation_level=measured_isolation,
                isolation_proofs=outcome.isolation_proofs,
                observations=observations,
            ),
            disclosure=disclosure_link(
                ai_assisted=True, duplicate_checked=True,
                test_results=f"ring-2 survival_rate={outcome.survival_rate:.3f}",
                diff_sha256=diff_sha,
                duplicate_evidence=duplicate_evidence,
            ),
            artifact_lineage=artifact_lineage,
            provider_accounting=provider_accounting,
            evaluation_evidence={
                **evaluation_evidence,
                "heldout_scores": outcome.per_workload,
                "heldout_survival_rate": outcome.survival_rate,
            },
        )
        write_receipt(
            receipt,
            state_root=(Path(state_root) / "receipts") if state_root else None,
            lineage_base_root=lineage_base_root,
        )
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
    result.provider_failures = sum(r.provider_failures for r in reports)
    result.tripwire_trips = sum(r.tripwire_trips for r in reports)
    for r in reports:
        for reason, n in r.trip_reasons.items():
            result.trip_reasons[reason] = result.trip_reasons.get(reason, 0) + n
    result.ring2_checked = sum(r.ring2_checked for r in reports)
    result.ring2_survivors = sum(r.ring2_survivors for r in reports)
    result.ring2_promotion_blocked = sum(r.ring2_promotion_blocked for r in reports)
    result.spend_usd = round(sum(r.spend_usd for r in reports), 6)
    best = loop.grid.best()
    result.best_fitness = best.fitness if best else 0.0
    rates = [rate for r in reports for rate in r.survival_rates]
    result.mean_survival = round(sum(rates) / len(rates), 6) if rates else 0.0
    result.finished_at = datetime.now(timezone.utc).isoformat()
    usage = getattr(propose_fn, "usage", None)
    if isinstance(usage, dict):
        attempts = [
            dict(item) for item in usage.get("provider_attempts", [])
            if isinstance(item, dict)
        ]
        tokens_by_provider = {
            str(provider): int(tokens)
            for provider, tokens in dict(
                usage.get("tokens_by_provider", {})
            ).items()
        }
        result.provider_attempts = attempts
        result.provider_tokens_by_provider = tokens_by_provider
        result.provider_route_provenance = {
            str(provider): dict(route)
            for provider, route in dict(
                usage.get("provider_route_provenance", {})
            ).items()
            if isinstance(route, dict)
        }
        result.provider_usage_verified = usage.get("usage_verified") is True
        try:
            _validate_attempt_bindings(
                attempts, result.provider_route_provenance
            )
            result.provider_cost_usd = _validated_provider_cost(
                tokens_by_provider, result.provider_route_provenance
            )
        except ProviderUsageUnverifiable:
            result.provider_usage_verified = False
            # Retain a conservative monetary projection while refusing to
            # continue without the route/tariff evidence needed to settle it.
            result.provider_cost_usd = round(sum(
                estimate_cost_usd(provider, tokens)
                for provider, tokens in tokens_by_provider.items()
            ), 6)
        result.spend_usd = round(result.spend_usd + result.provider_cost_usd, 6)
    if state_root is not None:
        try:
            from dharma_swarm.foundry.daemon import current_cycle_accounting_context
            ledger_binding = current_cycle_accounting_context()
        except (ImportError, AttributeError):
            ledger_binding = {}
        body = {
            "schema_version": "foundry_provider_cycle.v1",
            "campaign_id": result.campaign_id,
            "target_id": spec.id,
            "preregistration_digest": preregistration_digest,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "budget_cap_usd": config.budget_cap_usd,
            "ledger_binding": ledger_binding,
            "provider_attempts": result.provider_attempts,
            "tokens_by_provider": result.provider_tokens_by_provider,
            "provider_route_provenance": result.provider_route_provenance,
            "usage_verified": result.provider_usage_verified,
            "provider_cost_usd_upper_bound": result.provider_cost_usd,
            "campaign_spend_usd_upper_bound": result.spend_usd,
            "proposed": result.proposed,
            "provider_failures": result.provider_failures,
            "ring2_survivors": result.ring2_survivors,
        }
        body["digest"] = canonical_digest(body)
        accounting_root = Path(state_root) / "provider_cycles"
        accounting_root.mkdir(parents=True, exist_ok=True)
        accounting_path = accounting_root / f"{result.campaign_id}.json"
        encoded = (
            json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        with accounting_path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        directory = os.open(accounting_root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        result.provider_accounting_digest = body["digest"]
        result.provider_accounting_path = str(
            accounting_path.relative_to(Path(state_root))
        )
        projection = Path(state_root) / "provider_status.json"
        projection_body = {
            "schema_version": "foundry_provider_status.v1",
            "campaign_id": result.campaign_id,
            "accounting_digest": result.provider_accounting_digest,
            "accounting_path": result.provider_accounting_path,
            "provider_route_provenance": result.provider_route_provenance,
            "usage_verified": result.provider_usage_verified,
            "finished_at": result.finished_at,
        }
        projection_body["digest"] = canonical_digest(projection_body)
        projection_bytes = (
            json.dumps(
                projection_body, indent=2, sort_keys=True, allow_nan=False
            ) + "\n"
        ).encode("utf-8")
        projection_temp = projection.parent / (
            f".{projection.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with projection_temp.open("xb") as handle:
                handle.write(projection_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(projection_temp, projection)
            directory = os.open(projection.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            projection_temp.unlink(missing_ok=True)
    if not result.provider_usage_verified:
        raise ProviderUsageUnverifiable(
            "campaign provider usage lacks actual or full-liability evidence"
        )
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
    declared = (spec.evolve_paths or ["kernels/k.py"])[0]
    path = declared.rstrip("/") + "/candidate.py" if declared.endswith("/") else declared

    def propose(model, parent_id, seed):
        speed = round((seed % 5) * 0.4 + 0.6, 2)
        diff = (
            f"--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n"
            f"-BASELINE = 0\n+SPEED={speed}\n"
        )
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
