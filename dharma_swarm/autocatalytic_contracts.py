"""Typed contracts and compatibility facade for the autocatalytic portfolio."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from dharma_swarm.a2a.a2a_server import A2ATaskStatus
from dharma_swarm import autocatalytic_contract_primitives as _primitives
from dharma_swarm import autocatalytic_manifest_contracts as _manifest_contracts
from dharma_swarm import autocatalytic_source_contracts as _source_contracts

PORTFOLIO_SCHEMA = _primitives.PORTFOLIO_SCHEMA
SEMANTIC_HOP_SCHEMA = _primitives.SEMANTIC_HOP_SCHEMA
SEMANTIC_SEED_SCHEMA = _primitives.SEMANTIC_SEED_SCHEMA
CYCLE_PROOF_SCHEMA = _primitives.CYCLE_PROOF_SCHEMA
CYCLE_WITNESS_SCHEMA = _primitives.CYCLE_WITNESS_SCHEMA
RUNTIME_ATTESTATION_SCHEMA = _primitives.RUNTIME_ATTESTATION_SCHEMA
PROJECT_EVIDENCE_SCHEMA = _primitives.PROJECT_EVIDENCE_SCHEMA
SIGNAL_ENVELOPE_SCHEMA = _primitives.SIGNAL_ENVELOPE_SCHEMA
CROSS_FEED_SCHEMA = _primitives.CROSS_FEED_SCHEMA
PROMOTION_GATE_SCHEMA = _primitives.PROMOTION_GATE_SCHEMA
ADAPTER_VERSION = _primitives.ADAPTER_VERSION
VERIFIER_VERSION = _primitives.VERIFIER_VERSION
LOCAL_RECEIPT_CONSISTENCY_SCOPE = _primitives.LOCAL_RECEIPT_CONSISTENCY_SCOPE
REQUIRED_NODE_COUNT = _primitives.REQUIRED_NODE_COUNT
PROMOTION_CHECKS_BY_NODE = _primitives.PROMOTION_CHECKS_BY_NODE

PortfolioContractError = _primitives.PortfolioContractError
SemanticPromotionError = _primitives.SemanticPromotionError

_canonical_json = _primitives._canonical_json
_digest = _primitives._digest
_completion_hash = _primitives._completion_hash
_utc_now = _primitives._utc_now
_nested_value = _primitives._nested_value
evaluate_promotion_gate = _primitives.evaluate_promotion_gate
_artifact_hash_payload = _primitives._artifact_hash_payload
_verify_artifact_hash = _primitives._verify_artifact_hash
_semantic_seed = _primitives._semantic_seed

_REPO_ROOT = _source_contracts._REPO_ROOT
_reject_duplicate_keys = _source_contracts._reject_duplicate_keys
_json_object = _source_contracts._json_object
_declared_source_digest = _source_contracts._declared_source_digest
_source_snapshot = _source_contracts._source_snapshot

_MANIFEST_PATH = _manifest_contracts._MANIFEST_PATH
load_portfolio_manifest = _manifest_contracts.load_portfolio_manifest
_ordered_nodes = _manifest_contracts._ordered_nodes
_active_track_ids = _manifest_contracts._active_track_ids
_build_catalytic_graph = _manifest_contracts._build_catalytic_graph
validate_portfolio = _manifest_contracts.validate_portfolio


@dataclass(frozen=True, slots=True)
class TransportAck:
    """Transport-only evidence.

    This type intentionally has no conversion method to :class:`StructuralHop`.
    A broker or in-process acceptance acknowledgement cannot satisfy semantic
    completion.
    """

    task_id: str
    transport: str
    accepted: bool


@dataclass(frozen=True, slots=True)
class StructuralHop:
    """A structurally verified terminal A2A result, without receipt authority."""

    turn: int
    ordinal: int
    node_id: str
    task_id: str
    run_id: str
    idempotency_key: str
    a2a_receipt_id: str
    semantic_receipt_id: str
    status: str
    artifact: dict[str, Any]
    artifact_hash: str
    predecessor_hash: str
    completion_hash: str

    def __post_init__(self) -> None:
        if self.status != A2ATaskStatus.COMPLETED.value:
            raise SemanticPromotionError("StructuralHop status must be exact completed")
        if self.turn < 0 or self.ordinal not in range(1, REQUIRED_NODE_COUNT + 1):
            raise SemanticPromotionError(
                "StructuralHop turn/ordinal is outside the proof domain"
            )
        required_ids = {
            "node_id": self.node_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "idempotency_key": self.idempotency_key,
            "a2a_receipt_id": self.a2a_receipt_id,
            "semantic_receipt_id": self.semantic_receipt_id,
        }
        if any(not str(value).strip() for value in required_ids.values()):
            raise SemanticPromotionError(
                "StructuralHop projected execution identities must be non-empty"
            )
        if not isinstance(self.artifact, dict) or not _verify_artifact_hash(
            self.artifact
        ):
            raise SemanticPromotionError("StructuralHop artifact hash is invalid")
        if self.artifact_hash != self.artifact.get("artifact_hash"):
            raise SemanticPromotionError(
                "StructuralHop artifact hash projection is invalid"
            )
        if self.predecessor_hash != self.artifact.get("predecessor_hash"):
            raise SemanticPromotionError(
                "StructuralHop predecessor projection is invalid"
            )
        if self.completion_hash != _completion_hash(self):
            raise SemanticPromotionError("StructuralHop completion hash is invalid")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StructuralCycleProof:
    """Exactly ten ordered :class:`StructuralHop` values for one turn."""

    cycle_id: str
    trace_id: str
    turn: int
    start_hash: str
    end_hash: str
    proof_hash: str
    hops: tuple[StructuralHop, ...]
    cycle_closed: bool = True

    def __post_init__(self) -> None:
        if len(self.hops) != REQUIRED_NODE_COUNT:
            raise SemanticPromotionError(
                "StructuralCycleProof requires exactly ten StructuralHop values"
            )
        if not self.cycle_id or not self.trace_id or self.turn < 0:
            raise SemanticPromotionError(
                "StructuralCycleProof execution identity is incomplete"
            )
        if [hop.ordinal for hop in self.hops] != list(
            range(1, REQUIRED_NODE_COUNT + 1)
        ):
            raise SemanticPromotionError(
                "StructuralCycleProof hop ordinals must be exactly 1..10"
            )
        prior_hash = self.start_hash
        for hop in self.hops:
            if hop.turn != self.turn or hop.predecessor_hash != prior_hash:
                raise SemanticPromotionError(
                    "StructuralCycleProof hop chain is discontinuous"
                )
            prior_hash = hop.artifact_hash
        if self.end_hash != prior_hash or self.cycle_closed is not True:
            raise SemanticPromotionError(
                "StructuralCycleProof does not close its hash chain"
            )
        proof_core = {
            "schema_version": CYCLE_PROOF_SCHEMA,
            "cycle_id": self.cycle_id,
            "trace_id": self.trace_id,
            "turn": self.turn,
            "start_hash": self.start_hash,
            "end_hash": self.end_hash,
            "hop_receipt_hashes": [hop.completion_hash for hop in self.hops],
            "cycle_closed": True,
        }
        if self.proof_hash != _digest(proof_core):
            raise SemanticPromotionError("StructuralCycleProof proof hash is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CYCLE_PROOF_SCHEMA,
            "cycle_id": self.cycle_id,
            "trace_id": self.trace_id,
            "turn": self.turn,
            "start_hash": self.start_hash,
            "end_hash": self.end_hash,
            "proof_hash": self.proof_hash,
            "completed_hops": len(self.hops),
            "cycle_closed": self.cycle_closed,
            "hop_receipt_hashes": [hop.completion_hash for hop in self.hops],
            "hops": [hop.to_dict() for hop in self.hops],
        }


@dataclass(frozen=True, slots=True)
class StructuralCycleCheck:
    """Non-authoritative result of recomputing semantic structure only."""

    valid: bool
    error: str = ""
    modality: str = field(default="structure_only", init=False)

    def __bool__(self) -> bool:
        raise TypeError("use StructuralCycleCheck.valid explicitly")


@dataclass(frozen=True, slots=True)
class LocalReceiptConsistencyCheck:
    """Consistency with a local mutable store, never authenticated provenance."""

    valid: bool
    error: str = ""
    modality: str = field(default=LOCAL_RECEIPT_CONSISTENCY_SCOPE, init=False)
    independently_authenticated: bool = field(default=False, init=False)

    def __bool__(self) -> bool:
        raise TypeError("use LocalReceiptConsistencyCheck.valid explicitly")
