"""Project adapters for research, assurance, authorization, and learning."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from dharma_swarm.a2a.a2a_server import A2ATask
from dharma_swarm import autocatalytic_source_contracts as _sources
from dharma_swarm.autocatalytic_adapter_evidence import (
    _consumed_feed,
    _project_evidence,
)
from dharma_swarm.autocatalytic_contracts import SemanticPromotionError

_json_object = _sources._json_object
_source_snapshot = _sources._source_snapshot


def _adapt_chamber_research(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from dharma_swarm.chamber.traces import read_corpus

    corpus_path = (
        _sources._REPO_ROOT
        / "reports"
        / "governance"
        / "chamber"
        / "trace_corpus.jsonl"
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
        len(corpus_rows)
        == corpus["row_count"]
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
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from scripts.runtime.ci_truth import (
        contract_summary,
        evaluate_rollup,
        load_contract,
    )

    contract_path = (
        _sources._REPO_ROOT / "docs" / "governance" / "CI_TRUTH_CONTRACT.json"
    )
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
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from dharma_swarm.operator_core.onboarding.contract import (
        AgentOpsError,
        parse_work_packet,
    )
    from dharma_swarm.terminal_control import load_terminal_control_state

    terminal_state = load_terminal_control_state(_sources._REPO_ROOT)
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
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
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
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    _task: A2ATask,
    _turn: int,
    feeds: Sequence[Mapping[str, Any]],
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
    corpus_bound = receipt["facts"].get("corpus.sha256") == corpus.get(
        "sha256"
    ) and receipt["facts"].get("corpus.rows") == corpus.get("row_count")
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
