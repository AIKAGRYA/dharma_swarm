"""Typed contracts and topology validation for the autocatalytic portfolio."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from dharma_swarm.a2a.a2a_server import A2ATaskStatus
from dharma_swarm.catalytic_graph import CatalyticGraph

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

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _REPO_ROOT / "ACTIVE_SURFACE_MANIFEST.yaml"

class PortfolioContractError(ValueError):
    """Raised when declared portfolio topology or semantics are invalid."""


class SemanticPromotionError(ValueError):
    """Raised when an A2A task cannot inhabit ``StructuralHop``."""


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


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _completion_hash(hop: StructuralHop | Mapping[str, Any]) -> str:
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


def evaluate_promotion_gate(
    node_id: str, details: Mapping[str, Any]
) -> dict[str, Any]:
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


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise SemanticPromotionError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _json_object(relative_path: str) -> dict[str, Any] | None:
    """Load an object without JSON's unsafe last-key-wins behaviour."""
    path = _REPO_ROOT / relative_path
    if not path.is_file():
        return None
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SemanticPromotionError(
            f"invalid project source JSON {relative_path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SemanticPromotionError(
            f"invalid project source JSON {relative_path}: expected object"
        )
    return value


def _declared_source_digest(payload: Mapping[str, Any]) -> str:
    """Reproduce governance receipt hashing (escaped Unicode by design)."""
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_snapshot(
    relative_path: str,
    *,
    kind: str = "structured_json",
    expected_schema: str | None = None,
    schema_field: str = "schema",
    required_types: Mapping[str, type | tuple[type, ...]] | None = None,
    require_digest: bool = False,
    optional: bool = False,
    row_schema: str | None = None,
    row_required_types: Mapping[str, type | tuple[type, ...]] | None = None,
    fact_paths: Sequence[str] = (),
) -> dict[str, Any]:
    """Validate and content-address one explicitly typed project source."""
    path = _REPO_ROOT / relative_path
    if not path.is_file():
        if not optional:
            raise SemanticPromotionError(f"required project source missing: {relative_path}")
        return {
            "path": relative_path, "source_kind": kind, "present": False,
            "valid": True, "status": "optional_absent", "sha256": None,
            "size_bytes": 0, "schema": None, "generated_at": None,
            "declared_digest_valid": None, "facts": {},
        }
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise SemanticPromotionError(
            f"invalid project source {relative_path}: not readable UTF-8"
        ) from exc
    if not text.strip():
        raise SemanticPromotionError(f"invalid project source {relative_path}: empty")
    base: dict[str, Any] = {
        "path": relative_path, "source_kind": kind, "present": True,
        "valid": True, "status": "validated",
        "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw),
        "schema": None, "generated_at": None,
        "declared_digest_valid": None, "facts": {},
    }
    if kind in {"raw_utf8_text", "raw_utf8_markdown"}:
        return base

    def _require_fields(
        value: Mapping[str, Any],
        fields: Mapping[str, type | tuple[type, ...]],
        label: str,
    ) -> None:
        for dotted, expected in fields.items():
            observed = _nested_value(value, dotted)
            accepted = expected if isinstance(expected, tuple) else (expected,)
            if type(observed) not in accepted or (
                type(observed) is str and not observed.strip()
            ):
                names = "/".join(item.__name__ for item in accepted)
                raise SemanticPromotionError(
                    f"invalid project source {relative_path}: {label} field "
                    f"{dotted!r} must be {names}"
                )

    if kind == "jsonl":
        rows: list[dict[str, Any]] = []
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
            except json.JSONDecodeError as exc:
                raise SemanticPromotionError(
                    f"invalid project source JSONL {relative_path} row {index}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise SemanticPromotionError(
                    f"invalid project source JSONL {relative_path} row {index}: object required"
                )
            if row_schema is not None and row.get("schema") != row_schema:
                raise SemanticPromotionError(
                    f"invalid project source JSONL {relative_path} row {index}: wrong schema"
                )
            _require_fields(row, row_required_types or {}, f"row {index}")
            rows.append(row)
        if not rows:
            raise SemanticPromotionError(
                f"invalid project source JSONL {relative_path}: no rows"
            )
        return {**base, "schema": row_schema, "row_count": len(rows)}
    if kind != "structured_json":
        raise SemanticPromotionError(f"unknown project source kind: {kind}")
    value = _json_object(relative_path)
    if value is None:
        raise SemanticPromotionError(f"required project source missing: {relative_path}")
    if expected_schema is not None and value.get(schema_field) != expected_schema:
        raise SemanticPromotionError(
            f"invalid project source {relative_path}: expected {schema_field} "
            f"{expected_schema!r}"
        )
    _require_fields(value, required_types or {}, "object")
    digest_valid: bool | None = None
    if require_digest:
        if not isinstance(value.get("digest"), str):
            raise SemanticPromotionError(
                f"invalid project source {relative_path}: required digest missing"
            )
        unsigned = {key: item for key, item in value.items() if key != "digest"}
        digest_valid = value["digest"] == _declared_source_digest(unsigned)
        if not digest_valid:
            raise SemanticPromotionError(
                f"invalid project source {relative_path}: digest mismatch"
            )
    return {
        **base, "schema": value.get(schema_field),
        "generated_at": value.get("generated_at") or value.get("observed_at"),
        "declared_digest_valid": digest_valid,
        "facts": {fact: _nested_value(value, fact) for fact in fact_paths},
    }

def load_portfolio_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical autocatalytic portfolio declaration."""

    manifest_path = path or _MANIFEST_PATH
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    portfolio = data.get("autocatalytic_portfolio")
    if not isinstance(portfolio, dict):
        raise PortfolioContractError("autocatalytic_portfolio is not declared")
    return portfolio


def _ordered_nodes(portfolio: Mapping[str, Any]) -> list[dict[str, Any]]:
    nodes = portfolio.get("nodes")
    if not isinstance(nodes, list) or not all(isinstance(row, dict) for row in nodes):
        raise PortfolioContractError("portfolio nodes must be a list of objects")
    return sorted(
        (dict(row) for row in nodes), key=lambda row: int(row.get("ordinal", 0))
    )


def _active_track_ids(repo_root: Path) -> set[str]:
    path = repo_root / "docs" / "governance" / "ACTIVE_TRACK.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = data.get("active_tracks") or []
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict) and row.get("id") and row.get("status") == "ACTIVE"
    }


def _build_catalytic_graph(portfolio: Mapping[str, Any]) -> CatalyticGraph:
    graph = CatalyticGraph(persist_path=Path(os.devnull))
    for node in _ordered_nodes(portfolio):
        graph.add_node(
            str(node.get("id", "")),
            label=str(node.get("label", "")),
            authority=str(node.get("authority", "")),
        )
    for edge in portfolio.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        graph.add_edge(
            str(edge.get("source", "")),
            str(edge.get("target", "")),
            edge_type=str(edge.get("kind") or "enables"),
            strength=1.0,
            evidence=str(edge.get("signal") or ""),
        )
    return graph


def validate_portfolio(
    portfolio: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    require_files: bool = True,
) -> list[str]:
    """Return every topology, authority, and filesystem contract error."""

    root = repo_root or _REPO_ROOT
    errors: list[str] = []
    if portfolio.get("schema_version") != PORTFOLIO_SCHEMA:
        errors.append(f"schema_version must be {PORTFOLIO_SCHEMA}")
    if portfolio.get("claim_ceiling") != "local_rehearsal":
        errors.append("portfolio claim_ceiling must remain local_rehearsal")
    promotion_rule = portfolio.get("promotion_rule")
    if not isinstance(promotion_rule, dict):
        errors.append("promotion_rule must be a typed object")
    else:
        if promotion_rule.get("schema") != SEMANTIC_HOP_SCHEMA:
            errors.append(f"promotion_rule schema must be {SEMANTIC_HOP_SCHEMA}")
        if promotion_rule.get("transport_ack_promotes") is not False:
            errors.append("promotion_rule must set transport_ack_promotes to false")
        required_hop_evidence = {
            "terminal_completed",
            "typed_semantic_artifact",
            "causal_continuity",
            "hash_continuity",
            "project_adapter_recomputation",
        }
        if not required_hop_evidence.issubset(
            set(map(str, promotion_rule.get("structural_hop_requires") or []))
        ):
            errors.append("promotion_rule omits required StructuralHop evidence")
        required_cycle_evidence = {
            "exactly_ten_ordered_structural_hops",
            "closed_signal_ring",
            "persisted_local_mutable_receipt_consistency",
        }
        if not required_cycle_evidence.issubset(
            set(
                map(
                    str,
                    promotion_rule.get("receipt_consistent_cycle_requires") or [],
                )
            )
        ):
            errors.append(
                "promotion_rule omits required receipt-consistent cycle evidence"
            )
        forbidden = set(map(str, promotion_rule.get("forbidden_promotions") or []))
        if "transport_ack_to_structural_hop" not in forbidden:
            errors.append("promotion_rule must forbid transport ACK promotion")

    try:
        nodes = _ordered_nodes(portfolio)
    except (PortfolioContractError, TypeError, ValueError) as exc:
        return [str(exc)]
    if len(nodes) != REQUIRED_NODE_COUNT:
        errors.append(
            f"expected exactly {REQUIRED_NODE_COUNT} nodes, found {len(nodes)}"
        )

    ids = [str(node.get("id") or "") for node in nodes]
    if not all(ids) or len(set(ids)) != len(ids):
        errors.append("node ids must be non-empty and unique")
    if [int(node.get("ordinal", 0)) for node in nodes] != list(
        range(1, REQUIRED_NODE_COUNT + 1)
    ):
        errors.append("node ordinals must be exactly 1..10")
    if portfolio.get("entry_node") != (ids[0] if ids else None):
        errors.append("entry_node must be the ordinal-1 node")

    track_ids = _active_track_ids(root)
    bound_track_ids: set[str] = set()
    declared_pages: list[str] = []
    cross_outputs: set[tuple[str, str, str]] = set()
    cross_inputs: set[tuple[str, str, str]] = set()
    required_fields = (
        "label",
        "role",
        "authority",
        "input_signal",
        "output_signal",
        "transform",
        "next_node",
        "page",
        "doc",
    )
    allowed_authority = {"local_evidence", "projection_only", "external_gated"}
    for index, node in enumerate(nodes):
        node_id = ids[index]
        missing = [
            name for name in required_fields if not str(node.get(name) or "").strip()
        ]
        if missing:
            errors.append(f"{node_id}: missing fields {missing}")
        if node.get("authority") not in allowed_authority:
            errors.append(f"{node_id}: invalid authority {node.get('authority')!r}")
        expected_checks = PROMOTION_CHECKS_BY_NODE.get(node_id)
        if expected_checks is None:
            errors.append(f"{node_id}: no code-owned promotion-check mapping")
        elif node.get("promotion_checks") != list(expected_checks):
            errors.append(
                f"{node_id}: promotion_checks must exactly match {list(expected_checks)}"
            )
        expected_page = f"/dashboard/organism/{node_id}"
        declared_pages.append(str(node.get("page") or ""))
        if node.get("page") != expected_page:
            errors.append(f"{node_id}: page must be {expected_page}")
        expected_next = ids[(index + 1) % len(ids)] if ids else ""
        if node.get("next_node") != expected_next:
            errors.append(f"{node_id}: next_node must be {expected_next}")
        if ids and node.get("output_signal") != nodes[(index + 1) % len(nodes)].get(
            "input_signal"
        ):
            errors.append(f"{node_id}: output signal does not feed {expected_next}")
        obligations = node.get("proof_obligations")
        if not isinstance(obligations, list) or not obligations:
            errors.append(f"{node_id}: proof_obligations must be non-empty")
        bindings = node.get("project_bindings")
        if not isinstance(bindings, list) or not bindings:
            errors.append(f"{node_id}: project_bindings must be non-empty")
        else:
            normalized_bindings = set(map(str, bindings))
            bound_track_ids.update(normalized_bindings)
            unknown = sorted(normalized_bindings - track_ids)
            if unknown:
                errors.append(f"{node_id}: non-active project bindings {unknown}")
        refs = node.get("proof_refs")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{node_id}: proof_refs must be non-empty")
        elif require_files:
            for ref in refs:
                if not (root / str(ref)).is_file():
                    errors.append(f"{node_id}: missing proof ref {ref}")
        if (
            require_files
            and node.get("doc")
            and not (root / str(node["doc"])).is_file()
        ):
            errors.append(f"{node_id}: missing canonical node page {node['doc']}")
        for row in node.get("cross_outputs") or []:
            if (
                not isinstance(row, dict)
                or not row.get("signal")
                or not row.get("target")
            ):
                errors.append(
                    f"{node_id}: cross_outputs entries require signal and target"
                )
                continue
            cross_outputs.add((node_id, str(row["target"]), str(row["signal"])))
        for row in node.get("cross_inputs") or []:
            if (
                not isinstance(row, dict)
                or not row.get("signal")
                or not row.get("source")
            ):
                errors.append(
                    f"{node_id}: cross_inputs entries require signal and source"
                )
                continue
            cross_inputs.add((str(row["source"]), node_id, str(row["signal"])))

    if len(set(declared_pages)) != len(declared_pages):
        errors.append("node dashboard pages must be unique")
    if bound_track_ids != track_ids:
        missing = sorted(track_ids - bound_track_ids)
        extra = sorted(bound_track_ids - track_ids)
        errors.append(
            f"active project binding closure mismatch: missing={missing}, extra={extra}"
        )
    if cross_outputs != cross_inputs:
        errors.append(
            "cross-feed producer/consumer contracts disagree: "
            f"outputs_only={sorted(cross_outputs - cross_inputs)}, "
            f"inputs_only={sorted(cross_inputs - cross_outputs)}"
        )
    cross_signals = [signal for _source, _target, signal in cross_outputs]
    if len(cross_signals) != len(set(cross_signals)):
        errors.append(
            "cross-feed signal names must be globally unique because the runtime "
            "bus is keyed by signal"
        )

    ring_pairs = (
        {(ids[index], ids[(index + 1) % len(ids)]) for index in range(len(ids))}
        if ids
        else set()
    )
    declared_edges = [
        (str(edge.get("source")), str(edge.get("target")), str(edge.get("signal")))
        for edge in portfolio.get("edges") or []
        if isinstance(edge, dict)
    ]
    declared_pairs = {(source, target) for source, target, _signal in declared_edges}
    missing_ring = sorted(ring_pairs - declared_pairs)
    if missing_ring:
        errors.append(f"missing ring edges: {missing_ring}")
    expected_ring_edges = (
        {
            (
                ids[index],
                ids[(index + 1) % len(ids)],
                str(nodes[index].get("output_signal")),
            )
            for index in range(len(ids))
        }
        if ids
        else set()
    )
    expected_edges = expected_ring_edges | cross_outputs
    if len(declared_edges) != len(set(declared_edges)):
        errors.append("portfolio edges must be unique")
    if set(declared_edges) != expected_edges:
        errors.append(
            "declared edges do not match typed ring/cross-feed contracts: "
            f"missing={sorted(expected_edges - set(declared_edges))}, "
            f"extra={sorted(set(declared_edges) - expected_edges)}"
        )

    try:
        graph = _build_catalytic_graph(portfolio)
        sets = graph.detect_autocatalytic_sets()
        if graph.node_count != REQUIRED_NODE_COUNT:
            errors.append(f"catalytic graph has {graph.node_count} nodes")
        if len(sets) != 1 or set(sets[0]) != set(ids):
            errors.append("all ten nodes must form one autocatalytic set")
    except (TypeError, ValueError) as exc:
        errors.append(f"catalytic graph invalid: {exc}")
    return errors


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
