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

Each cycle has a fresh elite grid, while verified cumulative artifacts compound
across cycles through a base/parent/delta manifest and mandatory replay.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from dharma_swarm.foundry.artifacts import (
    ArtifactReplayError,
    PriorArtifact,
    build_lineage,
    verify_lineage,
)
from dharma_swarm.foundry.campaign import CampaignConfig, CampaignResult, run_campaign
from dharma_swarm.foundry.live import estimate_cost_usd
from dharma_swarm.foundry.oracle_evaluator import (
    OracleEvaluator,
    apply_diff,
    canonicalize_diff,
    sentinel_metrics_parser,
)
from dharma_swarm.foundry.real_proposer import real_proposer
from dharma_swarm.foundry.receipts import audit_receipts
from dharma_swarm.foundry.runner_isolation import (
    IsolationPolicy,
    StrongIsolationUnavailable,
    UNATTENDED_UID_GID,
    docker_available,
)
from dharma_swarm.foundry.target_ingest import compute_tree_digest, ingest
from dharma_swarm.foundry.targets import TARGET_REGISTRY, assert_contributable

ORACLE_TIMEOUT_S = 600.0


def _under_root(root: Path, raw_path: str) -> Path:
    candidate = (
        (root / raw_path).resolve()
        if not Path(raw_path).is_absolute()
        else Path(raw_path).resolve()
    )
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ArtifactReplayError(f"artifact path escapes state root: {raw_path}") from exc
    return candidate


def best_prior_artifact(state_root: "Path | None", target_id: str) -> PriorArtifact | None:
    """The best surviving artifact for a target: (patch path, its verified metric).

    This is what makes cycles COMPOUND instead of restart: each new campaign
    seeds the pinned tree with the best ring-2-surviving diff so far, then
    must beat THAT baseline. Receipts stay honest — the artifact is selected
    by its receipt's ``candidate_metric`` and must exist byte-for-byte
    (``diff_sha256`` is the filename).
    """
    root = Path(state_root) if state_root else Path.home() / ".dharma" / "foundry"
    best: PriorArtifact | None = None
    for receipt_path in (root / "receipts").glob("*.json"):
        try:
            data = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("target_id") != target_id:
            continue
        metric = (data.get("benchmark") or {}).get("candidate_metric")
        if metric is None:
            continue
        lineage = data.get("artifact_lineage") or {}
        sha = str(lineage.get("cumulative_sha256") or (data.get("disclosure") or {}).get("diff_sha256", ""))
        raw_artifact = str(lineage.get("cumulative_artifact") or f"artifacts/{sha}.patch")
        if not sha or len(sha) != 64:
            raise ArtifactReplayError(f"receipt {receipt_path.name} has invalid artifact sha")
        artifact = _under_root(root, raw_artifact)
        if not artifact.is_file():
            raise ArtifactReplayError(
                f"receipt {receipt_path.name} references missing artifact {artifact}"
            )
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != sha:
            raise ArtifactReplayError(
                f"receipt {receipt_path.name} artifact bytes do not match sha256"
            )

        manifest_path: Path | None = None
        manifest: dict | None = None
        if lineage.get("schema_version") == "foundry_artifact_lineage.v1":
            raw_manifest = str(lineage.get("manifest_path", ""))
            if not raw_manifest:
                raise ArtifactReplayError(f"receipt {receipt_path.name} lacks lineage manifest")
            manifest_path = _under_root(root, raw_manifest)
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError) as exc:
                raise ArtifactReplayError(
                    f"receipt {receipt_path.name} lineage manifest unreadable"
                ) from exc
            if manifest != lineage:
                raise ArtifactReplayError(
                    f"receipt {receipt_path.name} embedded lineage differs from manifest"
                )

        selection = PriorArtifact(artifact, float(metric), manifest_path, manifest)
        if best is None or selection.metric > best.metric:
            best = selection
    return best


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
    if not docker_ok:
        raise StrongIsolationUnavailable(
            "unattended campaign requires Docker; degraded host execution is forbidden"
        )
    foundry_root = Path(state_root) if state_root else Path.home() / ".dharma" / "foundry"
    existing_audit = audit_receipts(foundry_root)
    if not existing_audit.ok:
        raise ArtifactReplayError(
            "receipt/artifact state failed pre-cycle audit: "
            + json.dumps(existing_audit.to_dict(), sort_keys=True)
        )
    pinned = ingest(spec, dest_root=foundry_root / "targets")

    evolve_file = (spec.evolve_paths or [""])[0]
    if not evolve_file or evolve_file.endswith("/"):
        raise RuntimeError(f"target {spec.id} evolve scope is not a single file")

    with tempfile.TemporaryDirectory(prefix="foundry_base_") as temp_root:
        base_root = Path(temp_root) / "base"
        shutil.copytree(
            Path(pinned.root),
            base_root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"),
        )
        base_tree_digest = compute_tree_digest(base_root, [evolve_file])

        # Compound across cycles only from evidence that replays byte-for-byte.
        # A mismatch is terminal; silently falling back to clean would sever
        # lineage while still advertising a compound campaign.
        seeded_from = ""
        parent_artifact_sha = ""
        parent_candidate_tree_digest = ""
        prior = best_prior_artifact(state_root, spec.id)
        if prior is not None:
            if prior.manifest is not None:
                verify_lineage(base_root, prior.manifest, artifact_path=prior.path)
                parent_artifact_sha = str(prior.manifest["cumulative_sha256"])
                parent_candidate_tree_digest = str(
                    prior.manifest["candidate_tree_digest"]
                )
            else:
                raise ArtifactReplayError(
                    "legacy delta artifact is compatibility evidence only; "
                    "quarantine/migrate it before authoritative compounding"
                )
            seed_text = prior.path.read_text(encoding="utf-8")
            failure = apply_diff(Path(pinned.root), seed_text)
            if failure is not None:
                raise ArtifactReplayError(f"seed artifact failed to apply: {failure}")
            tree_digest = compute_tree_digest(Path(pinned.root), [evolve_file])
            if (
                prior.manifest is not None
                and tree_digest != prior.manifest["candidate_tree_digest"]
            ):
                raise ArtifactReplayError(
                    "seeded artifact tree differs from verified candidate tree"
                )
            seeded_from = f"{prior.path.stem[:16]} (metric {prior.metric})"
        else:
            tree_digest = base_tree_digest

        policy = IsolationPolicy(
            timeout_s=ORACLE_TIMEOUT_S,
            docker_image=spec.docker_image or "python:3.11-slim",
            allow_degraded=False,
            readonly_workdir=True,
            run_as_user=UNATTENDED_UID_GID,
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
            heldout["heldout"] = _make_eval(
                f"heldout:{spec.id}", ["bash", "-c", spec.heldout_cmd]
            )

        raw_propose = real_proposer(
            target_id=spec.id, pinned_root=Path(pinned.root),
            evolve_file=evolve_file, objective=spec.objective,
        )

        def propose(model, parent_id, seed):
            """Canonicalize each delta relative to this cycle's seeded tree."""
            cand = raw_propose(model, parent_id, seed)
            if not cand.diff:
                return cand
            canonical = canonicalize_diff(Path(pinned.root), evolve_file, cand.diff)
            return dataclasses.replace(cand, diff=canonical or "")

        propose.usage = getattr(raw_propose, "usage", {"tokens": 0, "calls": 0})  # type: ignore[attr-defined]
        propose.resolved = getattr(raw_propose, "resolved", {})  # type: ignore[attr-defined]

        def artifact_builder(candidate):
            return build_lineage(
                state_root=foundry_root,
                target_id=spec.id,
                resolved_sha=pinned.resolved_sha,
                base_root=base_root,
                seeded_root=Path(pinned.root),
                base_tree_digest=base_tree_digest,
                evolve_file=evolve_file,
                delta=candidate.diff,
                parent_artifact_sha256=parent_artifact_sha,
                parent_candidate_tree_digest=parent_candidate_tree_digest,
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
            tree_digest=tree_digest, resolved_sha=pinned.resolved_sha,
            isolation_level=oracle.last_isolation_level or "local_restricted",
            artifact_builder=artifact_builder,
            lineage_base_root=base_root,
        )
        if seeded_from:
            result.target_id = f"{spec.id} (seeded from {seeded_from})"

        usage = getattr(propose, "usage", {"tokens": 0, "calls": 0})
        tokens_by_provider = usage.get("tokens_by_provider", {})
        result.spend_usd = round(
            result.spend_usd + sum(
                estimate_cost_usd(provider, tokens)
                for provider, tokens in tokens_by_provider.items()
            ), 6
        )
        # One journald line per cycle — the daemon runs cycles silently otherwise.
        print(json.dumps({
            "cycle_target": spec.id,
            "seeded_from": seeded_from or "clean tree",
            "baseline": baseline,
            "best_fitness": result.best_fitness,
            "proposed": result.proposed,
            "provider_failures": result.provider_failures,
            "ring1_wins": result.ring1_wins,
            "ring2_survivors": result.ring2_survivors,
            "trip_reasons": result.trip_reasons,
            "spend_usd": result.spend_usd,
        }), flush=True)
        return result
