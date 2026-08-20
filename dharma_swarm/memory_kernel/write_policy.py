"""Dry-run write governance policy for MemoryKernel writer discovery."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from dharma_swarm.memory_kernel.atoms import RiskLevel, WriteMode
from dharma_swarm.memory_kernel.surfaces import SurfaceSpec, default_surface_specs
from dharma_swarm.memory_kernel.writer_models import MemoryWriterSpec, WriterClassification


class WriteDecisionOutcome(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    DENY = "deny"


@dataclass(frozen=True)
class WriterIdentity:
    identity_type: str
    source_path: str
    symbol: str
    writer_ids: tuple[str, ...] = ()
    classifications: tuple[str, ...] = ()
    declared_write_modes: tuple[str, ...] = ()
    declared_surface_ids: tuple[str, ...] = ()
    risk: RiskLevel = RiskLevel.UNKNOWN

    def to_json(self) -> dict[str, object]:
        return {
            "identity_type": self.identity_type,
            "source_path": self.source_path,
            "symbol": self.symbol,
            "writer_ids": self.writer_ids,
            "classifications": self.classifications,
            "declared_write_modes": self.declared_write_modes,
            "declared_surface_ids": self.declared_surface_ids,
            "risk": self.risk.value,
        }


@dataclass(frozen=True)
class WriteRequest:
    source_path: str
    symbol: str
    operation: str
    target: str
    mode: str
    writer_identity: WriterIdentity
    occurrence_index: int = 1

    def baseline_key(self) -> tuple[str, str, str, str]:
        return reviewed_write_key(
            self.source_path,
            self.symbol,
            self.operation,
            self.target,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "source_path": self.source_path,
            "symbol": self.symbol,
            "operation": self.operation,
            "target": self.target,
            "mode": self.mode,
            "occurrence_index": self.occurrence_index,
            "writer_identity": self.writer_identity.to_json(),
        }


@dataclass(frozen=True)
class SurfaceResolution:
    surface_id: str
    path_template: str
    write_mode: WriteMode
    risk: RiskLevel
    resolution: str
    matched_tokens: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "surface_id": self.surface_id,
            "path_template": self.path_template,
            "write_mode": self.write_mode.value,
            "risk": self.risk.value,
            "resolution": self.resolution,
            "matched_tokens": self.matched_tokens,
        }


@dataclass(frozen=True)
class WriteDecision:
    request: WriteRequest
    decision: WriteDecisionOutcome
    requested_write_mode: WriteMode
    risk: RiskLevel
    resolved_surface: SurfaceResolution | None
    reviewed_baseline_id: str | None = None
    reasons: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "decision": self.decision.value,
            "source_path": self.request.source_path,
            "symbol": self.request.symbol,
            "operation": self.request.operation,
            "mode": self.request.mode,
            "requested_write_mode": self.requested_write_mode.value,
            "resolved_surface_id": (
                self.resolved_surface.surface_id if self.resolved_surface else None
            ),
            "resolved_surface": (
                self.resolved_surface.to_json() if self.resolved_surface else None
            ),
            "risk": self.risk.value,
            "writer_identity": self.request.writer_identity.to_json(),
            "reviewed_baseline": self.reviewed_baseline_id is not None,
            "reviewed_baseline_id": self.reviewed_baseline_id,
            "baseline_key": self.request.baseline_key(),
            "occurrence_index": self.request.occurrence_index,
            "reasons": self.reasons,
        }


@dataclass(frozen=True)
class ReviewedWriteBaselineEntry:
    source_path: str
    symbol: str
    operation: str
    target_sha256: str
    triage_category: str
    occurrences: int = 1
    review_note: str = "reviewed static discovery baseline"

    @property
    def review_id(self) -> str:
        return (
            f"{self.source_path}:{self.symbol}:{self.operation}:"
            f"{self.target_sha256}"
        )

    def key(self) -> tuple[str, str, str, str]:
        return (
            self.source_path,
            self.symbol,
            self.operation,
            self.target_sha256,
        )

    def to_json(self) -> dict[str, object]:
        return {
            "review_id": self.review_id,
            "source_path": self.source_path,
            "symbol": self.symbol,
            "operation": self.operation,
            "target_sha256": self.target_sha256,
            "triage_category": self.triage_category,
            "occurrences": self.occurrences,
            "review_note": self.review_note,
        }


class MemoryWriteSurfaceResolver:
    """Resolve static write targets against registered surface templates."""

    def __init__(self, surface_specs: Iterable[SurfaceSpec] | None = None) -> None:
        self.surface_specs = (
            tuple(default_surface_specs())
            if surface_specs is None
            else tuple(surface_specs)
        )
        self._by_id = {surface.surface_id: surface for surface in self.surface_specs}
        self._template_index = tuple(
            (
                surface,
                _template_tokens(surface.path_template),
                _surface_risk(surface),
            )
            for surface in self.surface_specs
        )

    def resolve(
        self,
        target: str,
        *,
        fallback_surface_ids: Iterable[str] = (),
    ) -> SurfaceResolution | None:
        for surface_id in fallback_surface_ids:
            surface = self._by_id.get(surface_id)
            if surface is not None:
                return SurfaceResolution(
                    surface_id=surface.surface_id,
                    path_template=surface.path_template,
                    write_mode=surface.write_mode,
                    risk=_surface_risk(surface),
                    resolution="writer_spec",
                )

        normalized_target = _normalize_target(target)
        matches: list[tuple[int, SurfaceResolution]] = []
        for surface, tokens, risk in self._template_index:
            matched_tokens, resolution = _match_template_tokens(normalized_target, tokens)
            if not matched_tokens:
                continue
            score = _surface_match_score(surface, matched_tokens, resolution)
            matches.append(
                (
                    score,
                    SurfaceResolution(
                        surface_id=surface.surface_id,
                        path_template=surface.path_template,
                        write_mode=surface.write_mode,
                        risk=risk,
                        resolution=resolution,
                        matched_tokens=matched_tokens,
                    ),
                )
            )
        if not matches:
            return None
        return sorted(matches, key=lambda item: (-item[0], item[1].surface_id))[0][1]


class MemoryWritePolicy:
    """Dry-run policy classifier for discovered write paths."""

    def __init__(
        self,
        *,
        surface_specs: Iterable[SurfaceSpec] | None = None,
        reviewed_baseline: Iterable[ReviewedWriteBaselineEntry] | None = None,
    ) -> None:
        self.resolver = MemoryWriteSurfaceResolver(surface_specs)
        baseline = (
            tuple(default_reviewed_write_baseline())
            if reviewed_baseline is None
            else tuple(reviewed_baseline)
        )
        self.reviewed_baseline = baseline
        self._baseline_by_key = {entry.key(): entry for entry in baseline}

    def identity_for_writer_specs(
        self,
        specs: Iterable[MemoryWriterSpec],
        *,
        source_path: str,
        symbol: str,
    ) -> WriterIdentity:
        rows = tuple(specs)
        if not rows:
            return WriterIdentity(
                identity_type="heuristic_discovery",
                source_path=source_path,
                symbol=symbol,
            )
        return WriterIdentity(
            identity_type="registered_writer",
            source_path=source_path,
            symbol=symbol,
            writer_ids=tuple(sorted(spec.writer_id for spec in rows)),
            classifications=tuple(
                sorted({spec.classification.value for spec in rows})
            ),
            declared_write_modes=tuple(sorted({spec.write_mode.value for spec in rows})),
            declared_surface_ids=tuple(
                sorted({surface_id for spec in rows for surface_id in spec.writes_to})
            ),
            risk=_max_risk(*(spec.risk for spec in rows)),
        )

    def decide(self, request: WriteRequest) -> WriteDecision:
        requested_mode = infer_requested_write_mode(request.operation, request.mode)
        resolved_surface = self.resolver.resolve(
            request.target,
            fallback_surface_ids=request.writer_identity.declared_surface_ids,
        )
        baseline_entry = self._reviewed_baseline_entry(request)
        reasons: list[str] = []
        if resolved_surface is None:
            reasons.append("no registered surface template resolved the write target")
        else:
            reasons.append(
                f"resolved write target to {resolved_surface.surface_id} "
                f"via {resolved_surface.resolution}"
            )

        risk = _max_risk(
            request.writer_identity.risk,
            resolved_surface.risk if resolved_surface else RiskLevel.UNKNOWN,
        )
        mode_issue = _mode_issue(requested_mode, resolved_surface)
        if request.writer_identity.identity_type == "registered_writer":
            decision = self._registered_writer_decision(request.writer_identity, risk)
            reasons.append(
                "matched explicit MemoryWriterSpec "
                f"{', '.join(request.writer_identity.writer_ids)}"
            )
        elif baseline_entry is not None:
            decision = WriteDecisionOutcome.WARN
            reasons.append(
                "matched reviewed discovery baseline "
                f"{baseline_entry.review_id}"
            )
        else:
            decision = WriteDecisionOutcome.DENY
            reasons.append(
                "unregistered memory-like write is not in the reviewed baseline"
            )

        if mode_issue:
            reasons.append(mode_issue)
            if request.writer_identity.identity_type == "registered_writer":
                if decision == WriteDecisionOutcome.ALLOW:
                    decision = WriteDecisionOutcome.WARN
            else:
                decision = WriteDecisionOutcome.DENY
        if decision == WriteDecisionOutcome.ALLOW and risk in {
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
            RiskLevel.UNKNOWN,
        }:
            decision = WriteDecisionOutcome.WARN
            reasons.append(f"write risk is {risk.value}; require governance visibility")

        return WriteDecision(
            request=request,
            decision=decision,
            requested_write_mode=requested_mode,
            risk=risk,
            resolved_surface=resolved_surface,
            reviewed_baseline_id=(
                baseline_entry.review_id if baseline_entry is not None else None
            ),
            reasons=tuple(reasons),
        )

    def _registered_writer_decision(
        self,
        identity: WriterIdentity,
        risk: RiskLevel,
    ) -> WriteDecisionOutcome:
        classifications = set(identity.classifications)
        if WriterClassification.UNSAFE.value in classifications:
            return WriteDecisionOutcome.DENY
        if classifications & {
            WriterClassification.DORMANT.value,
            WriterClassification.LEGACY_TOLERATED.value,
            WriterClassification.REVIEW_REQUIRED.value,
        }:
            return WriteDecisionOutcome.WARN
        if risk in {RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.UNKNOWN}:
            return WriteDecisionOutcome.WARN
        return WriteDecisionOutcome.ALLOW

    def _reviewed_baseline_entry(
        self,
        request: WriteRequest,
    ) -> ReviewedWriteBaselineEntry | None:
        entry = self._baseline_by_key.get(request.baseline_key())
        if entry is None:
            return None
        if request.occurrence_index > entry.occurrences:
            return None
        return entry


def default_reviewed_write_baseline() -> tuple[ReviewedWriteBaselineEntry, ...]:
    return (
        ReviewedWriteBaselineEntry('scripts/forge/sample_swebench_instances.py', 'main', 'path_write', 'f4b52e12cb6d', 'generated_artifact', occurrences=2),
        ReviewedWriteBaselineEntry('dharma_swarm/active_inference.py', 'ActiveInferenceEngine._log_prediction_error', 'path_open_write', '55d048f783d0', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/agent_install.py', 'execute_install_plan', 'path_write', '9c658af64661', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/artifact_manifest.py', 'ArtifactManifestStore.write_manifest', 'path_write', 'b276c0a735d8', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/capital_lab/broker_paper_membrane.py', 'run_goal_b_proof_loop', 'path_write', '4d4d8d8376ae', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/chetana/palace.py', 'render_palace', 'path_write', 'd9a1b85d4e72', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/chetana/tests/test_graph_unifier.py', 'test_query_finds_node_in_catalytic_graph', 'path_write', 'efe23a5663cc', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/chetana/tests/test_ingest_promote.py', 'test_ingest_session_jsonl_creates_atom_per_substantive_turn', 'path_write', 'ada18f938a44', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/codex_overnight.py', 'main', 'path_write', '9c7d7ac4d5fa', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/codex_overnight.py', 'write_morning_handoff', 'path_write', 'f6ad48708b8c', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/conversation_distiller.py', '_save_distill_time', 'path_write', '0dba4ef3bf6f', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/conversation_distiller.py', '_write_latest_synthesis', 'path_write', 'd33fd3fc3fea', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/capital_lab/broker_paper_membrane.py', 'run_goal_b_proof_loop', 'path_write', 'c25eb06c9a64', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/chetana/palace.py', 'render_palace', 'path_write', 'd9a1b85d4e72', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/chetana/tests/test_graph_unifier.py', 'test_query_finds_node_in_catalytic_graph', 'path_write', 'efe23a5663cc', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/chetana/tests/test_ingest_promote.py', 'test_ingest_session_jsonl_creates_atom_per_substantive_turn', 'path_write', 'ada18f938a44', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/custodians.py', 'install_launchd_service', 'path_write', '9c7f9f689336', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/dual_audit.py', 'DualAudit._persist', 'path_write', 'a8cfe9ea3a9d', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/economic_spine.py', 'EconomicSpine.__init__', 'sqlite_connect', '7f61bf97a3a8', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/foundry/daemon.py', '_write_month_spend', 'path_write', '3946458004be', 'operational_state', occurrences=1, review_note='Foundry daemon monthly spend ledger (spend_ledger.json) under ~/.dharma/foundry — budget-cap persistence across service restarts so Restart=always cannot reset the cap; not canonical memory (PR #1424 follow-up, 2026-08-19).'),
        ReviewedWriteBaselineEntry('dharma_swarm/foundry/target_ingest.py', 'ingest', 'path_write', '76808f750d07', 'generated_artifact', occurrences=1, review_note='Foundry target pin manifest (<id>.pin.json) under ~/.dharma/foundry/targets — a reproducibility pin (repo/sha/tree-digest), not canonical memory (PR #1389).'),
        ReviewedWriteBaselineEntry('dharma_swarm/ginko_orchestrator.py', 'save_state', 'path_write', '535ccc087541', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/guardian_crew.py', '_create_issue_if_needed', 'path_write', 'e08815565330', 'operational_state', occurrences=3),
        ReviewedWriteBaselineEntry('dharma_swarm/identity.py', 'IdentityMonitor._issue_correction', 'path_write', '53e7798f503c', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/loop_supervisor.py', 'LoopSupervisor.save_state', 'path_write', 'c006db8e7f1d', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/memory_common.py', 'run_memory_metabolism', 'path_write', '65b2a23ed30c', 'generated_artifact', occurrences=1, review_note='Metabolism receipt JSON under the state-dir report sink (~/.dharma/reports/memory_kernel), never canonical memory rows (PR #1132).'),
        ReviewedWriteBaselineEntry('dharma_swarm/ontology.py', 'OntologyRegistry.save', 'path_write', 'bab070f87b44', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/orchestrate.py', 'save_state', 'path_write', 'c6056417f922', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/orchestrate_live.py', 'orchestrate', 'path_write', '03f223acc3e6', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/overnight_director.py', 'OvernightDirector.run', 'path_write', '89ea04695522', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/overnight_director.py', 'write_morning_brief', 'path_write', 'c2b5dae8e153', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/pulse.py', '_check_and_run_cron_jobs', 'path_write', '1805e1edcad4', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/pulse.py', '_save_living_state', 'path_write', '68aae60df8b0', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/runtime_artifacts.py', 'write_dgc_health_snapshot', 'path_write', 'c4360a3a4355', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/samvara.py', 'SamvaraEngine._persist', 'path_write', '8f13b37d8a6a', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/scout_audit.py', 'write_pipeline_audit', 'path_open_write', 'a93f40801868', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/seed_harvester.py', 'harvest', 'path_write', '0b70dc59cb3f', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/skill_bridge.py', 'SkillBridge._ingest_diversity_grid', 'path_write', '23692a743ed7', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/thread_manager.py', 'ThreadManager._save_state', 'path_write', '1aa772630e7c', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/tui/commands/system_commands.py', 'SystemCommandHandler._handle_thread', 'path_write', '483b322dd4eb', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/tui_legacy.py', 'DGCApp._handle_command', 'path_write', '483b322dd4eb', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('dharma_swarm/world_model.py', 'WorldModelStore.save_snapshot', 'path_write', 'c70c4629322d', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/algedonic_triage.py', 'save_state', 'path_write', '09c8535fac12', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/allout_autopilot.py', 'execute_single_step', 'path_write', '9d58935c034b', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/allout_autopilot.py', 'execute_single_step', 'path_write', 'c77238abb207', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/experiments/test_full_loop.py', 'main', 'path_write', '0ade2c85a8ba', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/experiments/test_full_loop.py', 'main', 'path_write', '99c83aa2bd78', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/governance/run_nats_live_production_matrix.py', 'MatrixRunner.run', 'path_write', 'c5b7b9f59aa9', 'generated_artifact', occurrences=1, review_note='NATS live matrix success path updates repo evidence latest.json pointer only.'),
        ReviewedWriteBaselineEntry('scripts/governance/run_nats_live_production_matrix.py', 'async_main', 'path_write', '92e4ec17921e', 'generated_artifact', occurrences=1, review_note='NATS live matrix failure path updates repo evidence latest.json pointer only.'),
        ReviewedWriteBaselineEntry('scripts/governance/hygiene/scan.py', 'main', 'path_write', 'ca40bd1a2c8e', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/lattice_test.py', 'build_lattice_db', 'sqlite_connect', '7b7dd5543675', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/lattice_test.py', 'main', 'path_write', 'e7f43d056757', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop2_heartbeat_closure_run.py', 'main', 'path_write', 'eebcfa85ce76', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop4_10_memory_context_closure_run.py', '_prepare_state_dir', 'path_write', 'fff3e82d4cdf', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop4_10_memory_context_closure_run.py', 'run_loop10', 'path_write', '51891e41d1c9', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop4_10_memory_context_closure_run.py', 'run_replay', 'path_write', '84f88386c2bb', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop5_zeitgeist_closure_run.py', 'main', 'path_write', 'eebcfa85ce76', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop5b_world_radar_closure_run.py', 'main', 'path_write', 'eebcfa85ce76', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop6_witness_closure_run.py', 'main', 'path_write', 'eebcfa85ce76', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/loop8_recognition_closure_run.py', '_write_interpreted_history', 'path_write', '3efe0bf9f8c6', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/merge_snapshot.py', 'write_canonical_outputs', 'path_write', 'b75b71c07cd1', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/mirror_test.py', 'build_sqlite_graph', 'sqlite_connect', '7b7dd5543675', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/onboard_cybernetics_stewards.py', 'main', 'path_write', '46fbb16ffdbd', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/organism_council.py', 'main', 'path_write', 'efc4fba934f2', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/overnight_autopilot.py', 'main', 'path_write', 'bb376ba4fa8b', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/rebind_cybernetics_directive.py', '_amain', 'path_write', '9cf7924d9d6d', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/regression_guard.py', 'main', 'path_write', '332dd97b1a0f', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/runtime/codex_composer_semantic_inbox_drain.py', 'drain_semantic_inbox', 'path_write', 'cee8def16f72', 'generated_artifact', occurrences=1, review_note='Semantic drain writes one task-scoped prompt file under its operator-provided temporary work directory; it does not write canonical memory or claim publication.'),
        ReviewedWriteBaselineEntry('scripts/seed_cybernetics_directive.py', '_amain', 'path_write', '405197978dba', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/seed_cybernetics_population_cycle.py', '_amain', 'path_write', '1596e5fe1cc1', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/seed_cybernetics_population_cycle.py', '_amain', 'path_write', '3dce95c52e97', 'operational_state', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/strange_loop.py', 'execute_single_step', 'path_write', '9d58935c034b', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/strange_loop.py', 'execute_single_step', 'path_write', 'c77238abb207', 'generated_artifact', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/system_integration_probe.py', 'run_all', 'path_write', '430b9a968242', 'test_or_experiment', occurrences=1),
        ReviewedWriteBaselineEntry('scripts/test_sentinel.py', 'main', 'path_write', 'c6056417f922', 'test_or_experiment', occurrences=1),
    )


def reviewed_write_key(
    source_path: str,
    symbol: str,
    operation: str,
    target: str,
) -> tuple[str, str, str, str]:
    return (
        source_path,
        symbol,
        operation,
        target_fingerprint(target),
    )


def target_fingerprint(target: str) -> str:
    return hashlib.sha256(target.encode("utf-8")).hexdigest()[:12]


def infer_requested_write_mode(operation: str, mode: str) -> WriteMode:
    normalized = mode.lower()
    if operation == "sqlite_connect":
        return WriteMode.READ_WRITE
    if operation == "path_write":
        return WriteMode.READ_WRITE
    if "read_write" in normalized or "write" in normalized:
        return WriteMode.READ_WRITE
    if "a" in normalized and "+" not in normalized and "w" not in normalized:
        return WriteMode.APPEND_ONLY
    if any(flag in normalized for flag in ("w", "x", "+")):
        return WriteMode.READ_WRITE
    return WriteMode.UNKNOWN


def _mode_issue(
    requested_mode: WriteMode,
    resolved_surface: SurfaceResolution | None,
) -> str | None:
    if resolved_surface is None:
        return None
    surface_mode = resolved_surface.write_mode
    if requested_mode == WriteMode.UNKNOWN or surface_mode == WriteMode.UNKNOWN:
        return None
    if surface_mode in {WriteMode.EXTERNAL, WriteMode.PROJECTION_WRITE, WriteMode.READ_WRITE}:
        return None
    if surface_mode == WriteMode.READ_ONLY and requested_mode != WriteMode.READ_ONLY:
        return "write operation targets a read-only registered surface"
    if surface_mode == WriteMode.APPEND_ONLY and requested_mode != WriteMode.APPEND_ONLY:
        return "write operation exceeds append-only registered surface mode"
    return None


def _template_tokens(path_template: str) -> tuple[str, ...]:
    template = path_template.lower()
    template = template.replace("{home}", "").replace("{repo_root}", "")
    return tuple(
        part
        for part in re.split(r"[/\\]+", template)
        if part and not part.startswith("{")
    )


def _normalize_target(target: str) -> str:
    return target.lower().replace("\\", "/")


def _match_template_tokens(
    target: str,
    tokens: tuple[str, ...],
) -> tuple[tuple[str, ...], str]:
    if not tokens:
        return (), ""
    if _tokens_in_order(target, tokens):
        return tokens, "template"
    if tokens[0] in {".dharma", ".claude"}:
        suffix = tokens[1:]
        if suffix and _tokens_in_order(target, suffix):
            return suffix, "template_suffix"
    return (), ""


def _tokens_in_order(target: str, tokens: tuple[str, ...]) -> bool:
    cursor = -1
    for token in tokens:
        next_index = target.find(token, cursor + 1)
        if next_index < 0:
            return False
        cursor = next_index
    return True


def _surface_match_score(
    surface: SurfaceSpec,
    matched_tokens: tuple[str, ...],
    resolution: str,
) -> int:
    score = len(matched_tokens) * 100 + sum(len(token) for token in matched_tokens)
    if resolution == "template_suffix":
        score -= 30
    if surface.surface_id.endswith("dharma_root"):
        score -= 50
    return score


def _surface_risk(surface: SurfaceSpec) -> RiskLevel:
    return _max_risk(
        surface.canon_risk,
        surface.pii_secrets_risk,
        surface.latency_risk,
    )


def _max_risk(*risks: RiskLevel) -> RiskLevel:
    known = tuple(risk for risk in risks if risk is not None)
    if not known:
        return RiskLevel.UNKNOWN
    return max(known, key=lambda risk: _RISK_RANK[risk])


_RISK_RANK = {
    RiskLevel.UNKNOWN: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


__all__ = [
    "MemoryWritePolicy",
    "MemoryWriteSurfaceResolver",
    "ReviewedWriteBaselineEntry",
    "SurfaceResolution",
    "WriteDecision",
    "WriteDecisionOutcome",
    "WriteRequest",
    "WriterIdentity",
    "default_reviewed_write_baseline",
    "infer_requested_write_mode",
    "reviewed_write_key",
    "target_fingerprint",
]
