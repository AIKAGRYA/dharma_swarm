"""Shared primitives for the autocatalytic portfolio contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

PORTFOLIO_SCHEMA = "dharma.autocatalytic_portfolio.v1"
SEMANTIC_HOP_SCHEMA = "dharma.a2a.semantic_hop.v1"
SEMANTIC_SEED_SCHEMA = "dharma.a2a.semantic_seed.v1"
CYCLE_PROOF_SCHEMA = "dharma.a2a.cycle_proof.v1"
CYCLE_WITNESS_SCHEMA = "dharma.a2a.cycle_witness.v1"
RUNTIME_ATTESTATION_SCHEMA = "dharma.a2a.runtime_attestation.v1"
PROJECT_EVIDENCE_SCHEMA = "dharma.autocatalytic.project_evidence.v1"
SIGNAL_ENVELOPE_SCHEMA = "dharma.autocatalytic.signal_envelope.v1"
CROSS_FEED_SCHEMA = "dharma.autocatalytic.cross_feed.v1"
PROMOTION_GATE_SCHEMA = "dharma.autocatalytic.promotion_gate.v1"
ADAPTER_VERSION = "project-adapters/1.0"
VERIFIER_VERSION = "autocatalytic-verifier/1.1"
LOCAL_RECEIPT_CONSISTENCY_SCOPE = "local_mutable_runtime_receipt_consistency"
REQUIRED_NODE_COUNT = 10

PROMOTION_CHECKS_BY_NODE: dict[str, tuple[str, ...]] = {
    "world_signal_supply": ("fresh_signal_promoted", "bronze_bound"),
    "sarathi_runtime": (
        "dispatch_proven",
        "restart_recovery_proven",
        "operator_intent_bound",
    ),
    "dharmagraph_execution": (
        "executed",
        "execution_receipt_present",
        "causally_linked",
        "safety_contract_satisfied",
    ),
    "cybernetic_supervision": (
        "current_daemon_witness",
        "predecessor_receipt_causally_matched",
    ),
    "arena_selection": ("selected", "authorized"),
    "chamber_research": ("proposed", "oracle_evidence_authorized"),
    "assurance_merge": ("verified", "merged", "authorized"),
    "operator_experience": ("authorization.granted",),
    "external_value_delivery": (
        "publisher_present",
        "response_ingestor_present",
        "delivery_observed",
        "independent_outcome_observed",
    ),
    "learning_promotion": (
        "independent_outcome_observed",
        "promotion.applied",
    ),
}


class PortfolioContractError(ValueError):
    """Raised when declared portfolio topology or semantics are invalid."""


class SemanticPromotionError(ValueError):
    """Raised when an A2A task cannot inhabit ``StructuralHop``."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _completion_hash(hop: Any | Mapping[str, Any]) -> str:
    """Hash the semantic result together with projected receipt references."""

    def _value(name: str) -> Any:
        if isinstance(hop, Mapping):
            return hop.get(name)
        return getattr(hop, name)

    artifact = _value("artifact")
    if not isinstance(artifact, Mapping):
        artifact = {}
    return _digest(
        {
            "task_id": _value("task_id"),
            "run_id": _value("run_id"),
            "idempotency_key": _value("idempotency_key"),
            "a2a_receipt_id": _value("a2a_receipt_id"),
            "semantic_receipt_id": _value("semantic_receipt_id"),
            "status": _value("status"),
            "node_id": _value("node_id"),
            "artifact_hash": artifact.get("artifact_hash"),
            "predecessor_hash": artifact.get("predecessor_hash"),
            "causation_id": artifact.get("causation_id"),
        }
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _nested_value(value: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = value
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def evaluate_promotion_gate(node_id: str, details: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate code-owned future-proof predicates without granting authority."""

    predicates = PROMOTION_CHECKS_BY_NODE.get(node_id)
    if predicates is None:
        raise SemanticPromotionError(f"no promotion-check contract for {node_id}")
    checks = []
    for predicate in predicates:
        raw = _nested_value(details, predicate)
        actual = raw if type(raw) is bool else None
        checks.append(
            {
                "predicate": predicate,
                "actual": actual,
                "expected": True,
                "passed": actual is True,
            }
        )
    return {
        "schema": PROMOTION_GATE_SCHEMA,
        "node_id": node_id,
        "checks": checks,
        "satisfied": all(check["passed"] for check in checks),
        "state": "blocked",
        "authority_upgrade_authorized": False,
        "authority_requirement": "new_authority_bearing_evaluator_and_work_packet",
    }


def _artifact_hash_payload(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in artifact.items() if key != "artifact_hash"}


def _verify_artifact_hash(artifact: Mapping[str, Any]) -> bool:
    expected = str(artifact.get("artifact_hash") or "")
    return bool(expected) and expected == _digest(_artifact_hash_payload(artifact))


def _semantic_seed(cycle_id: str, trace_id: str) -> dict[str, Any]:
    seed: dict[str, Any] = {
        "schema_version": SEMANTIC_SEED_SCHEMA,
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "correlation_id": cycle_id,
        "turn": -1,
        "ordinal": 0,
        "node_id": "bootstrap",
        "input_signal": "bootstrap_observation",
        "output_signal": "promoted_feedback",
        "transform": "seed_local_rehearsal",
        "message_id": f"msg_{cycle_id}_seed",
        "causation_id": "",
        "predecessor_hash": "0" * 64,
        "visited_nodes": [],
        "payload": {
            "seed_kind": "local_rehearsal_fixture",
            "external_observation": False,
            "transforms": [],
        },
        "claim_ceiling": "local_rehearsal",
        "external_effects_proven": False,
    }
    seed["artifact_hash"] = _digest(seed)
    return seed
