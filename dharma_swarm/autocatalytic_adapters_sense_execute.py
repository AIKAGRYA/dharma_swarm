"""Project adapters for sensing, prioritization, execution, and selection."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from dharma_swarm.a2a.a2a_server import A2ATask
from dharma_swarm import autocatalytic_source_contracts as _sources
from dharma_swarm.autocatalytic_adapter_evidence import (
    _consumed_feed,
    _project_evidence,
)
from dharma_swarm.autocatalytic_contracts import (
    SemanticPromotionError,
    _digest,
)

_json_object = _sources._json_object
_source_snapshot = _sources._source_snapshot


def _adapt_world_signal_supply(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source = _source_snapshot(
        "reports/loop_closure/cybernetics_codex/2026-07-02_loop5b_world_radar_closure.json",
        required_types={
            "observed_at": str,
            "real_data": bool,
            "cycles": int,
            "host_status": str,
            "adapt_proof.fed_forward": bool,
            "adapt_proof.accepted_receipts_total": int,
        },
        fact_paths=(
            "observed_at",
            "real_data",
            "cycles",
            "host_status",
            "adapt_proof.fed_forward",
            "adapt_proof.accepted_receipts_total",
        ),
    )
    historical_fixture = bool(
        source["facts"].get("real_data")
        and source["facts"].get("adapt_proof.fed_forward")
    )
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="world_radar.historical_receipt_projection",
        sources=[source],
        output_state=(
            "historical_grounded_fixture"
            if historical_fixture
            else "grounding_unproven"
        ),
        modality="historical_local_evidence",
        blockers=("no_fresh_bronze_bound_observation", "not_causally_linked_to_input"),
        details={
            "historical_fixture_valid": historical_fixture,
            "fresh_signal_promoted": False,
            "bronze_bound": False,
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_sarathi_runtime(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from dharma_swarm.holon_system.sarathi.plan import BootPack, build_plan
    from dharma_swarm.holon_system.sarathi.pulse import sarathi_pulse

    input_hash = str(predecessor.get("artifact_hash") or "")
    operator_feed = _consumed_feed(feeds, "operator_intent")
    operator_ref = operator_feed.get("source_evidence_hash") if operator_feed else None
    plan = build_plan(
        BootPack(
            roster=("codex_composer",),
            open_items=(
                {
                    "kind": "review",
                    "summary": f"Inspect metabolic input {input_hash[:12]}",
                    "body": "Review the receipt-bound predecessor; do not dispatch or mutate.",
                    "metadata": {
                        "predecessor_hash": input_hash,
                        "operator_intent_ref": operator_ref,
                    },
                },
            ),
        )
    )
    pulse = sarathi_pulse(
        roster=("codex_composer",),
        agents_root=_sources._REPO_ROOT / "docs" / "agents",
    )
    plan_rows = [asdict(row) for row in plan]
    source = _source_snapshot(
        "docs/sarathi_apex_build/08_CURRENT_STATE_SARATHI_AUTONOMY_2026-07-30.md",
        kind="raw_utf8_markdown",
    )
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="sarathi.pure_bootpack_plan",
        sources=[source],
        output_state="planned_not_accepted",
        modality="local_rehearsal",
        blockers=("wake_loop_not_proven", "dispatch_not_performed", "plan_not_ranked"),
        details={
            "plan_count": len(plan_rows),
            "plan_hash": _digest(plan_rows),
            "planned_delegations": plan_rows,
            "pulse": {
                "schema_version": pulse.get("schema_version"),
                "wake_loop_active": pulse.get("wake_loop_active"),
                "alive_claim": pulse.get("alive_claim"),
                "roster_count": len(pulse.get("roster") or []),
            },
            "dispatch_proven": False,
            "restart_recovery_proven": False,
            "operator_intent_bound": operator_feed is not None,
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_dharmagraph_execution(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    task: A2ATask,
    turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from dharma_swarm.graph.durable_invoker import (
        claim_idempotency_key,
        derive_graph_side_effect_key,
    )

    identity = task.metadata.get("execution_identity") or {}
    run_id = str(identity.get("run_id") or task.id)
    side_effect_key = derive_graph_side_effect_key(run_id, turn, str(node["id"]), 0)
    source = _source_snapshot(
        "reports/governance/dharmagraph_parity/judge_receipt.json",
        expected_schema="dharma_swarm.dharmagraph_parity_receipt.v1",
        require_digest=True,
        required_types={
            "observed_at": str,
            "verdict": str,
            "score.display": str,
            "closeout_blocked": bool,
            "claim_boundary": str,
        },
        fact_paths=(
            "observed_at",
            "verdict",
            "score.display",
            "closeout_blocked",
            "claim_boundary",
        ),
    )
    safety_feed = _consumed_feed(feeds, "safety_contract")
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="dharmagraph.pure_execution_identity",
        sources=[source],
        output_state="rehearsal_intent_no_domain_execution",
        modality="local_rehearsal",
        blockers=(
            "domain_dispatch_not_performed",
            "parity_not_finished",
            "no_causal_receipt",
        ),
        details={
            "side_effect_key": side_effect_key,
            "claim_idempotency_key": claim_idempotency_key(side_effect_key),
            "execution_mode": "rehearsal_no_dispatch",
            "executed": False,
            "execution_receipt_present": False,
            "causally_linked": False,
            "parity": source["facts"],
            "safety_contract_bound": safety_feed is not None,
            "safety_contract_satisfied": bool(
                safety_feed and safety_feed.get("state") == "verified"
            ),
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_cybernetic_supervision(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    relative = "reports/loop_closure/cybernetics_codex/latest_audit.json"
    audit = _json_object(relative) or {}
    statuses = (
        audit.get("loop_statuses")
        if isinstance(audit.get("loop_statuses"), list)
        else []
    )
    verdict_counts: dict[str, int] = {}
    for row in statuses:
        if isinstance(row, Mapping):
            verdict = str(row.get("verdict") or "UNKNOWN")
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
    source = _source_snapshot(
        relative,
        expected_schema="cybernetics_codex.audit.v3",
        schema_field="schema_version",
        required_types={
            "observed_at": str,
            "runtime.read_ok": bool,
            "one_wire.eligible": bool,
            "loop_statuses": list,
        },
        fact_paths=(
            "observed_at",
            "runtime.read_ok",
            "runtime.error",
            "one_wire.eligible",
        ),
    )
    if any(
        not isinstance(row, Mapping)
        or type(row.get("id")) is not str
        or type(row.get("verdict")) is not str
        or type(row.get("blocker")) is not str
        for row in statuses
    ):
        raise SemanticPromotionError(f"invalid project source {relative}: loop status")
    gaps = [
        {
            "id": row.get("id"),
            "verdict": row.get("verdict"),
            "blocker": row.get("blocker"),
        }
        for row in statuses
        if isinstance(row, Mapping) and row.get("verdict") != "CLOSED_LIVE"
    ]
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="cybernetics_codex.committed_audit_projection",
        sources=[source],
        output_state="closure_gaps_observed",
        modality="historical_local_evidence",
        blockers=(
            "audit_not_current_live_owner_proof",
            "predecessor_receipt_not_joined",
        ),
        details={
            "verdict_counts": verdict_counts,
            "closure_gap_count": len(gaps),
            "closure_gaps": gaps,
            "current_daemon_witness": False,
            "predecessor_receipt_causally_matched": False,
            "dispatch_authority": False,
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_arena_selection(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source = _source_snapshot(
        "reports/governance/arena/arena_truth_receipt.json",
        expected_schema="arena_truth_report.v1",
        require_digest=True,
        required_types={
            "generated_at": str,
            "hermetic": bool,
            "best.genome_id": str,
            "best.closeout_state": str,
            "best.significance.significant": bool,
            "best.dpi.learning_active": bool,
            "corpus.sha256": str,
            "corpus.rows": int,
            "capability_claim": str,
        },
        fact_paths=(
            "generated_at",
            "hermetic",
            "best.genome_id",
            "best.closeout_state",
            "best.significance.significant",
            "best.dpi.learning_active",
            "capability_claim",
        ),
    )
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="arena.hermetic_truth_receipt",
        sources=[source],
        output_state="candidate_only_not_selected",
        modality="historical_local_evidence",
        blockers=(
            "hermetic_fixture_only",
            "promotion_not_authorized",
            "no_live_measurement",
        ),
        details={
            "candidate_genome_id": source["facts"].get("best.genome_id"),
            "significant_on_fixture": source["facts"].get(
                "best.significance.significant"
            ),
            "learning_active": source["facts"].get("best.dpi.learning_active"),
            "experiment_id": None,
            "selected": False,
            "authorized": False,
        },
        consumed_cross_feeds=feeds,
    )
