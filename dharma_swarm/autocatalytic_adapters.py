"""Project evidence adapters and typed auxiliary cross-feeds."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Mapping, Sequence

from dharma_swarm.a2a.a2a_server import A2ATask
from dharma_swarm.autocatalytic_contracts import (
    ADAPTER_VERSION,
    CROSS_FEED_SCHEMA,
    PROJECT_EVIDENCE_SCHEMA,
    SIGNAL_ENVELOPE_SCHEMA,
    SemanticPromotionError,
    _REPO_ROOT,
    _canonical_json,
    _digest,
    _json_object,
    _source_snapshot,
    evaluate_promotion_gate,
)


def _project_evidence(
    *,
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    adapter_id: str,
    sources: Sequence[Mapping[str, Any]],
    output_state: str,
    modality: str,
    blockers: Sequence[str],
    details: Mapping[str, Any],
    consumed_cross_feeds: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a typed, non-self-promoting project-evidence value."""

    invalid_sources = [
        str(source.get("path") or "unknown")
        for source in sources
        if source.get("valid") is not True
    ]
    if invalid_sources:
        raise SemanticPromotionError(
            "project source contract is invalid: " + ", ".join(invalid_sources)
        )

    cross_feed_inputs: dict[str, Any] = {}
    unavailable: list[str] = []
    for feed in consumed_cross_feeds:
        signal = str(feed.get("signal") or "")
        if feed.get("status") == "consumed":
            cross_feed_inputs[signal] = {
                key: feed.get(key)
                for key in ("source_evidence_hash", "state", "modality", "emitted_turn")
            }
        else:
            cross_feed_inputs[signal] = {
                "status": "not_available",
                "source": feed.get("source"),
                "expected_turn": feed.get("expected_turn"),
            }
            unavailable.append(f"cross_feed_{signal}_unavailable")
    bound_details = dict(details)
    bound_details["cross_feed_inputs"] = cross_feed_inputs
    promotion_gate = evaluate_promotion_gate(str(node["id"]), bound_details)

    input_signal = predecessor.get("signal")
    input_state = (
        input_signal.get("state")
        if isinstance(input_signal, Mapping)
        else "bootstrap_fixture"
    )
    evidence: dict[str, Any] = {
        "schema_version": PROJECT_EVIDENCE_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "adapter_id": adapter_id,
        "node_id": str(node["id"]),
        "project_bindings": list(node.get("project_bindings") or []),
        "authority": str(node["authority"]),
        "claim_ceiling": "local_rehearsal",
        "execution_mode": "read_only_project_adapter",
        "side_effects_performed": False,
        "external_effects_proven": False,
        "project_source_causally_linked_to_input": False,
        "input_ref": {
            "artifact_hash": predecessor.get("artifact_hash"),
            "message_id": predecessor.get("message_id"),
            "signal_type": predecessor.get("output_signal"),
            "signal_state": input_state,
        },
        "sources": [dict(source) for source in sources],
        "signal": {
            "schema_version": SIGNAL_ENVELOPE_SCHEMA,
            "type": str(node["output_signal"]),
            "state": output_state,
            "modality": modality,
            "promotion_authorized": False,
            "external_effects_proven": False,
            "blockers": [*blockers, *unavailable],
        },
        "promotion_gate": promotion_gate,
        "details": bound_details,
    }
    normalized = json.loads(_canonical_json(evidence))
    normalized["evidence_hash"] = _digest(normalized)
    return normalized


def _adapt_world_signal_supply(
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
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
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
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
        agents_root=_REPO_ROOT / "docs" / "agents",
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
    node: Mapping[str, Any], predecessor: Mapping[str, Any], task: A2ATask,
    turn: int, feeds: Sequence[Mapping[str, Any]],
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
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
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
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
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


def _adapt_chamber_research(
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from dharma_swarm.chamber.traces import read_corpus

    corpus_path = (
        _REPO_ROOT / "reports" / "governance" / "chamber" / "trace_corpus.jsonl"
    )
    try:
        corpus_rows = read_corpus(corpus_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SemanticPromotionError(f"invalid Chamber trace corpus: {exc}") from exc
    corpus = _source_snapshot(
        "reports/governance/chamber/trace_corpus.jsonl",
        kind="jsonl",
        row_schema="chamber_gym_trace.v1",
        row_required_types={
            "env_id": str,
            "task_id": str,
            "taskpack_sha": str,
            "scorer_hash": str,
            "seed": int,
            "answers": list,
            "aggregated_answer": str,
            "correct": bool,
            "digest": str,
        },
    )
    transcendence = _source_snapshot(
        "reports/governance/chamber/transcendence_receipt.json",
        expected_schema="dharma_swarm.transcendence_decomposition.v1",
        require_digest=True,
        required_types={
            "generated_at": str,
            "authority": str,
            "summary.any_positive_lift_vs_best_seat": bool,
            "corpus_rows": int,
            "corpus_sha256": str,
        },
        fact_paths=(
            "generated_at",
            "authority",
            "summary.any_positive_lift_vs_best_seat",
            "corpus_rows",
            "corpus_sha256",
        ),
    )
    gym = _source_snapshot(
        "reports/governance/chamber/g1_run_receipt.json",
        expected_schema="chamber_gym_run.v1",
        require_digest=True,
        required_types={
            "live_solver.available": bool,
            "live_solver.reason": str,
            "tasks_run": int,
            "tasks_correct": int,
            "trace_corpus.rows": int,
            "trace_corpus.sha256": str,
        },
        fact_paths=(
            "live_solver.available",
            "live_solver.reason",
            "tasks_run",
            "tasks_correct",
            "trace_corpus.rows",
            "trace_corpus.sha256",
        ),
    )
    frontier = _source_snapshot(
        "reports/governance/chamber/frontier_ledger_receipt.json",
        expected_schema="dharma_swarm.frontier_ledger.v1",
        require_digest=True,
        required_types={
            "generated_at": str,
            "door.gate_open": bool,
            "chamber_drift.status": str,
        },
        fact_paths=("generated_at", "door.gate_open", "chamber_drift.status"),
    )
    if not (
        len(corpus_rows) == corpus["row_count"]
        == transcendence["facts"]["corpus_rows"]
        == gym["facts"]["trace_corpus.rows"]
        and corpus["sha256"]
        == transcendence["facts"]["corpus_sha256"]
        == gym["facts"]["trace_corpus.sha256"]
    ):
        raise SemanticPromotionError("Chamber receipts do not bind the trace corpus")
    oracle_feed = _consumed_feed(feeds, "oracle_evidence")
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="chamber.receipt_corpus_projection",
        sources=[transcendence, gym, frontier, corpus],
        output_state="blocked_no_proposal",
        modality="historical_local_evidence",
        blockers=(
            "no_authorized_experiment",
            "live_solver_unavailable",
            "frontier_gate_closed",
            "sandbox_jail_unproven",
        ),
        details={
            "trace_corpus_rows": len(corpus_rows),
            "positive_lift": transcendence["facts"].get(
                "summary.any_positive_lift_vs_best_seat"
            ),
            "live_solver_available": gym["facts"].get("live_solver.available"),
            "frontier_gate_open": frontier["facts"].get("door.gate_open"),
            "change": None,
            "proposed": False,
            "oracle_evidence_bound": oracle_feed is not None,
            "oracle_evidence_authorized": False,
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_assurance_merge(
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from scripts.runtime.ci_truth import (
        contract_summary,
        evaluate_rollup,
        load_contract,
    )

    contract_path = _REPO_ROOT / "docs" / "governance" / "CI_TRUTH_CONTRACT.json"
    contract = load_contract(contract_path)
    summary = contract_summary(contract)
    summary.pop("generated_at", None)
    empty_result = evaluate_rollup([], contract)
    empty_result.pop("generated_at", None)
    source = _source_snapshot(
        "docs/governance/CI_TRUTH_CONTRACT.json",
        expected_schema="dharma.ci_truth_contract.v1",
        required_types={
            "version": int,
            "required": list,
            "advisory": list,
            "required_contexts_manifest": str,
        },
        fact_paths=("schema", "version"),
    )
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="assurance.ci_contract_fail_closed",
        sources=[source],
        output_state="not_verified",
        modality="local_evidence",
        blockers=(
            "no_exact_candidate_sha",
            "no_authentic_ci_rollup",
            "clean_room_receipt_absent",
            "merge_not_performed",
        ),
        details={
            "contract_summary": summary,
            "empty_rollup_verdict": empty_result.get("verdict"),
            "empty_rollup_blocker_count": len(empty_result.get("merge_blockers") or []),
            "input_authenticity": "local_unverified",
            "release_ref": None,
            "verified": False,
            "merged": False,
            "authorized": False,
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_operator_experience(
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from dharma_swarm.operator_core.onboarding.contract import (
        AgentOpsError,
        parse_work_packet,
    )
    from dharma_swarm.terminal_control import load_terminal_control_state

    terminal_state = load_terminal_control_state(_REPO_ROOT)
    terminal_projection = None
    if terminal_state is not None:
        terminal_projection = {
            key: terminal_state.get(key)
            for key in (
                "run_status",
                "tasks_total",
                "tasks_pending",
                "active_task_id",
                "verification_status",
                "continue_required",
                "next_task",
                "updated_at",
            )
        }
    packet_path = (
        "reports/agentops/work_packets/"
        "helm-worldclass-terminal-WP-HELMLIVE-main-integration-2026-07-21.json"
    )
    source = _source_snapshot(
        packet_path,
        required_types={
            "id": str,
            "base_ref": str,
            "branch": str,
            "approval.before_merge": bool,
        },
        fact_paths=("id", "base_ref", "branch", "approval.before_merge"),
    )
    try:
        parse_work_packet(_json_object(packet_path) or {})
    except AgentOpsError as exc:
        raise SemanticPromotionError(f"invalid Helm work packet source: {exc}") from exc
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="helm.read_only_authorization_projection",
        sources=[source],
        output_state="authorization_not_observed",
        modality="projection_only",
        blockers=(
            "no_correlated_operator_approval",
            "no_current_terminal_control_record",
        ),
        details={
            "terminal_control": terminal_projection,
            "authorization": {
                "status": "not_observed",
                "granted": False,
                "action_id": None,
                "actor": None,
                "scope": None,
                "source_ref": None,
            },
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_external_value_delivery(
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    charter = _source_snapshot(
        "docs/plans/DARSHAN_CHARTER_2026-07-12.md", kind="raw_utf8_markdown"
    )
    expected_effect = _source_snapshot(
        "reports/darshan/issue_one_receipt.json",
        optional=True,
        require_digest=True,
        required_types={
            "schema": str,
            "observed_at": str,
            "articles": list,
            "site_build_sha256": str,
            "editorial_law_passes": (bool, list),
            "content_digest": str,
        },
    )
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="darshan.effect_receipt_gate",
        sources=[charter, expected_effect],
        output_state="external_gate_closed",
        modality="external_gated",
        blockers=(
            "missing_correlated_operator_approval",
            "missing_effect_receipt",
            "missing_response_ingestor",
        ),
        details={
            "required_effect_receipt_keys": [
                "schema",
                "observed_at",
                "articles",
                "site_build_sha256",
                "editorial_law_passes",
                "content_digest",
            ],
            "publisher_present": False,
            "response_ingestor_present": False,
            "delivery_observed": False,
            "independent_outcome_observed": False,
        },
        consumed_cross_feeds=feeds,
    )


def _adapt_learning_promotion(
    node: Mapping[str, Any], predecessor: Mapping[str, Any], _task: A2ATask,
    _turn: int, feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    receipt = _source_snapshot(
        "reports/governance/arena/arena_truth_receipt.json",
        expected_schema="arena_truth_report.v1",
        require_digest=True,
        required_types={
            "hermetic": bool,
            "corpus.sha256": str,
            "corpus.rows": int,
            "best.dpi.learning_active": bool,
            "capability_claim": str,
        },
        fact_paths=(
            "hermetic",
            "corpus.sha256",
            "corpus.rows",
            "best.dpi.learning_active",
            "capability_claim",
        ),
    )
    corpus = _source_snapshot(
        "reports/governance/arena/cold_start_corpus.jsonl",
        kind="jsonl",
        row_schema="orchestration_arena_v1_cold_start_trace.v1",
        row_required_types={
            "task_id": str,
            "genome_id": str,
            "answers": dict,
            "correct": bool,
            "scorer_hash": str,
            "task_manifest_hash": str,
        },
    )
    corpus_bound = (
        receipt["facts"].get("corpus.sha256") == corpus.get("sha256")
        and receipt["facts"].get("corpus.rows") == corpus.get("row_count")
    )
    if not corpus_bound:
        raise SemanticPromotionError("Arena receipt does not bind cold-start corpus")
    predecessor_signal = predecessor.get("signal")
    independent_outcome = bool(
        isinstance(predecessor_signal, Mapping)
        and predecessor_signal.get("state") == "independent_outcome_observed"
        and predecessor_signal.get("promotion_authorized") is True
    )
    return _project_evidence(
        node=node,
        predecessor=predecessor,
        adapter_id="arena.zero_weight_learning_gate",
        sources=[receipt, corpus],
        output_state="promotion_blocked",
        modality="projection_only",
        blockers=(
            "no_independent_external_outcome",
            "arena_labels_only",
            "routing_authority_absent",
        ),
        details={
            "corpus_digest_bound": corpus_bound,
            "independent_outcome_observed": independent_outcome,
            "promotion": {
                "state": "blocked",
                "applied": False,
                "routing_weight_delta": 0.0,
                "authority": "advisory_projection",
                "rollback_ref": None,
            },
        },
        consumed_cross_feeds=feeds,
    )


_PROJECT_ADAPTERS = {
    "world_signal_supply": _adapt_world_signal_supply,
    "sarathi_runtime": _adapt_sarathi_runtime,
    "dharmagraph_execution": _adapt_dharmagraph_execution,
    "cybernetic_supervision": _adapt_cybernetic_supervision,
    "arena_selection": _adapt_arena_selection,
    "chamber_research": _adapt_chamber_research,
    "assurance_merge": _adapt_assurance_merge,
    "operator_experience": _adapt_operator_experience,
    "external_value_delivery": _adapt_external_value_delivery,
    "learning_promotion": _adapt_learning_promotion,
}
_NODE_ORDINALS = {node_id: index for index, node_id in enumerate(_PROJECT_ADAPTERS, 1)}


def _consumed_feed(
    feeds: Sequence[Mapping[str, Any]], signal: str
) -> Mapping[str, Any] | None:
    return next(
        (row for row in feeds if row.get("signal") == signal and row.get("status") == "consumed"),
        None,
    )


def _consume_project_cross_feeds(
    *, node: Mapping[str, Any], predecessor_payload: Mapping[str, Any], turn: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Consume only ledger-bound, topology-fresh feed envelopes, once."""

    prior_bus = predecessor_payload.get("cross_feed_bus")
    if prior_bus is not None and not isinstance(prior_bus, Mapping):
        raise SemanticPromotionError("cross-feed bus must be an object")
    bus = dict(prior_bus or {})
    ledger = predecessor_payload.get("project_evidence_ledger") or []
    if not isinstance(ledger, list):
        raise SemanticPromotionError("cross-feed source evidence ledger must be a list")
    consumed: list[dict[str, Any]] = []
    envelope_keys = {
        "schema_version", "signal", "source", "target", "emitted_turn",
        "source_evidence_hash", "state", "modality", "promotion_authorized",
    }
    for contract in node.get("cross_inputs") or []:
        signal, source = str(contract["signal"]), str(contract["source"])
        expected_turn = turn if _NODE_ORDINALS[source] < int(node["ordinal"]) else turn - 1
        available = bus.get(signal)
        if available is None:
            consumed.append({
                "schema_version": CROSS_FEED_SCHEMA, "signal": signal,
                "source": source, "target": str(node["id"]),
                "status": "not_available", "expected_turn": expected_turn,
                "consumed_by": str(node["id"]), "consumed_turn": turn,
            })
            continue
        if not isinstance(available, Mapping) or set(available) != envelope_keys:
            raise SemanticPromotionError(f"cross-feed {signal} envelope is invalid")
        expected = {
            "schema_version": CROSS_FEED_SCHEMA, "signal": signal,
            "source": source, "target": str(node["id"]),
            "emitted_turn": expected_turn, "promotion_authorized": False,
        }
        if any(available.get(key) != value for key, value in expected.items()):
            raise SemanticPromotionError(f"cross-feed {signal} topology or turn is stale")
        source_hash = available.get("source_evidence_hash")
        matches = [
            row for row in ledger
            if isinstance(row, Mapping)
            and row.get("evidence_hash") == source_hash
            and row.get("node_id") == source
            and _digest({key: value for key, value in row.items() if key != "evidence_hash"})
            == source_hash
        ]
        if len(matches) != 1:
            raise SemanticPromotionError(
                f"cross-feed {signal} source evidence is not uniquely ledger-bound"
            )
        source_signal = matches[0].get("signal")
        if (
            not isinstance(source_signal, Mapping)
            or available.get("state") != source_signal.get("state")
            or available.get("modality") != source_signal.get("modality")
            or source_signal.get("promotion_authorized") is not False
            or available.get("promotion_authorized") is not False
        ):
            raise SemanticPromotionError(f"cross-feed {signal} state/modality is invalid")
        consumed.append({
            **dict(available), "status": "consumed",
            "consumed_by": str(node["id"]), "consumed_turn": turn,
        })
        bus.pop(signal)
    return bus, consumed


def _project_evidence_for(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    task: A2ATask,
    turn: int,
    consumed_cross_feeds: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    adapter = _PROJECT_ADAPTERS.get(str(node.get("id") or ""))
    if adapter is None:
        raise SemanticPromotionError(
            f"no project adapter registered for {node.get('id')}"
        )
    payload = predecessor.get("payload")
    if not isinstance(payload, Mapping):
        raise SemanticPromotionError("predecessor project payload is invalid")
    _, expected_feeds = _consume_project_cross_feeds(
        node=node, predecessor_payload=payload, turn=turn
    )
    if consumed_cross_feeds is None:
        consumed_cross_feeds = expected_feeds
    elif list(consumed_cross_feeds) != expected_feeds:
        raise SemanticPromotionError("provided cross-feed consumption is not causal")
    evidence = adapter(node, predecessor, task, turn, consumed_cross_feeds)
    expected_hash = str(evidence.get("evidence_hash") or "")
    if not expected_hash or expected_hash != _digest(
        {key: value for key, value in evidence.items() if key != "evidence_hash"}
    ):
        raise SemanticPromotionError(
            f"project adapter evidence hash invalid for {node['id']}"
        )
    return evidence


def _project_cross_feeds(
    *, node: Mapping[str, Any], predecessor_payload: Mapping[str, Any],
    project_evidence: Mapping[str, Any], turn: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compose causal one-shot consumption with later feed emission."""
    bus, consumed = _consume_project_cross_feeds(
        node=node, predecessor_payload=predecessor_payload, turn=turn
    )
    signal = project_evidence.get("signal")
    if not isinstance(signal, Mapping):
        raise SemanticPromotionError("project evidence signal is invalid")
    emitted: list[dict[str, Any]] = []
    for contract in node.get("cross_outputs") or []:
        envelope = {
            "schema_version": CROSS_FEED_SCHEMA,
            "signal": str(contract["signal"]), "source": str(node["id"]),
            "target": str(contract["target"]), "emitted_turn": turn,
            "source_evidence_hash": project_evidence.get("evidence_hash"),
            "state": signal.get("state"), "modality": signal.get("modality"),
            "promotion_authorized": False,
        }
        bus[str(contract["signal"])] = envelope
        emitted.append(envelope)
    return bus, consumed, emitted


def _validate_project_semantics(
    *, artifact: Mapping[str, Any], node: Mapping[str, Any],
    predecessor: Mapping[str, Any], task: A2ATask, turn: int,
) -> None:
    """Independently recompute consume -> adapter -> emit semantics."""
    prior_payload, payload = predecessor.get("payload"), artifact.get("payload")
    if not isinstance(prior_payload, Mapping) or not isinstance(payload, Mapping):
        raise SemanticPromotionError(f"{node['id']} project payload is invalid")
    _, consumed = _consume_project_cross_feeds(
        node=node, predecessor_payload=prior_payload, turn=turn
    )
    evidence = _project_evidence_for(node, predecessor, task, turn, consumed)
    if artifact.get("project_evidence") != evidence:
        raise SemanticPromotionError(f"{node['id']} project evidence is not adapter-derived")
    if artifact.get("signal") != evidence.get("signal"):
        raise SemanticPromotionError(f"{node['id']} signal envelope is invalid")
    bus, expected_consumed, emitted = _project_cross_feeds(
        node=node, predecessor_payload=prior_payload,
        project_evidence=evidence, turn=turn,
    )
    checks = (
        (artifact.get("consumed_cross_feeds"), expected_consumed, "consumption"),
        (artifact.get("emitted_cross_feeds"), emitted, "emission"),
        (payload.get("cross_feed_bus"), bus, "bus"),
    )
    for observed, expected, label in checks:
        if observed != expected:
            raise SemanticPromotionError(f"{node['id']} cross-feed {label} is invalid")
    ledger = [*(prior_payload.get("project_evidence_ledger") or []), evidence]
    if payload.get("project_evidence_ledger") != ledger:
        raise SemanticPromotionError(f"{node['id']} project-evidence ledger is invalid")
    if payload.get("last_signal_state") != evidence["signal"]["state"]:
        raise SemanticPromotionError(f"{node['id']} signal-state projection is invalid")
