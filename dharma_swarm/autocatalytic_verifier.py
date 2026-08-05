"""Structural and local mutable-receipt verification for cycle witnesses."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.a2a.a2a_server import A2ATask, A2ATaskStatus
from dharma_swarm.autocatalytic_adapters import _validate_project_semantics
from dharma_swarm.autocatalytic_contracts import (
    CYCLE_PROOF_SCHEMA,
    CYCLE_WITNESS_SCHEMA,
    REQUIRED_NODE_COUNT,
    SEMANTIC_HOP_SCHEMA,
    VERIFIER_VERSION,
    LocalReceiptConsistencyCheck,
    SemanticPromotionError,
    StructuralCycleCheck,
    _completion_hash,
    _digest,
    _ordered_nodes,
    _semantic_seed,
    _verify_artifact_hash,
)
from dharma_swarm.autocatalytic_receipt_verifier import (
    _runtime_attestation_core as _runtime_attestation_core,
    _runtime_receipt_rows as _runtime_receipt_rows,
    _verify_local_runtime_receipt_consistency,
)
from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

_IMPLEMENTATION_MODULE_NAMES = (
    "autocatalytic_adapter_evidence.py",
    "autocatalytic_adapters.py",
    "autocatalytic_adapters_research_promote.py",
    "autocatalytic_adapters_sense_execute.py",
    "autocatalytic_contract_primitives.py",
    "autocatalytic_contracts.py",
    "autocatalytic_cycle_runtime.py",
    "autocatalytic_manifest_contracts.py",
    "autocatalytic_portfolio.py",
    "autocatalytic_proof_builders.py",
    "autocatalytic_receipt_verifier.py",
    "autocatalytic_source_contracts.py",
    "autocatalytic_task_runtime.py",
    "autocatalytic_verifier.py",
)


def _load_implementation_source_sha256() -> str:
    """Hash the explicit semantic implementation source bundle once."""

    digest = hashlib.sha256()
    module_dir = Path(__file__).resolve().parent
    for name in _IMPLEMENTATION_MODULE_NAMES:
        name_bytes = name.encode("utf-8")
        source_bytes = (module_dir / name).read_bytes()
        digest.update(len(name_bytes).to_bytes(4, "big"))
        digest.update(name_bytes)
        digest.update(len(source_bytes).to_bytes(8, "big"))
        digest.update(source_bytes)
    return digest.hexdigest()


_VERIFIER_SOURCE_SHA256 = _load_implementation_source_sha256()
del _load_implementation_source_sha256


def _implementation_fingerprint(portfolio: Mapping[str, Any]) -> dict[str, str]:
    """Bind a witness to the loaded semantic implementation bundle."""

    return {
        "verifier_version": VERIFIER_VERSION,
        "portfolio_sha256": _digest(portfolio),
        "verifier_sha256": _VERIFIER_SOURCE_SHA256,
    }


def _proof_core_from_dict(proof: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CYCLE_PROOF_SCHEMA,
        "cycle_id": proof.get("cycle_id"),
        "trace_id": proof.get("trace_id"),
        "turn": proof.get("turn"),
        "start_hash": proof.get("start_hash"),
        "end_hash": proof.get("end_hash"),
        "hop_receipt_hashes": proof.get("hop_receipt_hashes"),
        "cycle_closed": True,
    }


def _check_structural_cycle_witness(
    witness: Mapping[str, Any],
    portfolio: Mapping[str, Any],
) -> StructuralCycleCheck:
    """Recompute semantic structure without conferring receipt authority."""

    try:
        if witness.get("schema_version") != CYCLE_WITNESS_SCHEMA:
            raise SemanticPromotionError("wrong cycle witness schema")
        if witness.get("verifier_version") != VERIFIER_VERSION:
            raise SemanticPromotionError("witness verifier version is stale or invalid")
        if witness.get("mode") != "local_rehearsal":
            raise SemanticPromotionError("witness mode is not local_rehearsal")
        if witness.get("claim_ceiling") != "local_rehearsal":
            raise SemanticPromotionError("witness exceeds local_rehearsal ceiling")
        if witness.get("external_effects_proven") is not False:
            raise SemanticPromotionError("local witness cannot prove external effects")
        try:
            generated_at = datetime.fromisoformat(
                str(witness.get("generated_at") or "")
            )
        except ValueError as exc:
            raise SemanticPromotionError("witness timestamp is invalid") from exc
        if generated_at.tzinfo is None:
            raise SemanticPromotionError("witness timestamp must be timezone-aware")
        if witness.get("cycle_closed") is not True:
            raise SemanticPromotionError("witness root does not claim cycle closure")
        if witness.get("implementation") != _implementation_fingerprint(portfolio):
            raise SemanticPromotionError(
                "witness implementation fingerprint is stale or invalid"
            )
        cycle_id = str(witness.get("cycle_id") or "")
        trace_id = str(witness.get("trace_id") or "")
        if not cycle_id or not trace_id or witness.get("correlation_id") != cycle_id:
            raise SemanticPromotionError(
                "witness cycle/trace/correlation identity is incomplete"
            )
        seed = witness.get("seed_artifact")
        if not isinstance(seed, dict) or not _verify_artifact_hash(seed):
            raise SemanticPromotionError("witness seed artifact is missing or invalid")
        expected_seed = _semantic_seed(cycle_id, trace_id)
        if seed != expected_seed:
            raise SemanticPromotionError("witness seed is not the canonical fixture")
        proofs = witness.get("proofs")
        if not isinstance(proofs, list) or len(proofs) < 2:
            raise SemanticPromotionError("witness requires at least two proven turns")
        if witness.get("turns_proven") != len(proofs):
            raise SemanticPromotionError("turn count does not match serialized proofs")
        if (
            witness.get("completed_hops") != REQUIRED_NODE_COUNT
            or witness.get("required_hops") != REQUIRED_NODE_COUNT
        ):
            raise SemanticPromotionError(
                "witness root does not declare exact ten-hop closure"
            )
        nodes = _ordered_nodes(portfolio)
        expected_nodes = [str(node["id"]) for node in nodes]
        previous_artifact: Mapping[str, Any] = seed
        task_ids: list[str] = []
        message_ids: list[str] = [str(seed["message_id"])]
        for expected_turn, proof in enumerate(proofs):
            if not isinstance(proof, dict) or proof.get("turn") != expected_turn:
                raise SemanticPromotionError("proof turns are not contiguous")
            if proof.get("cycle_id") != cycle_id or proof.get("trace_id") != trace_id:
                raise SemanticPromotionError(
                    "proof identity does not match witness identity"
                )
            hops = proof.get("hops")
            if not isinstance(hops, list) or len(hops) != REQUIRED_NODE_COUNT:
                raise SemanticPromotionError(
                    "serialized proof does not contain ten hops"
                )
            if [
                hop.get("node_id") for hop in hops if isinstance(hop, dict)
            ] != expected_nodes:
                raise SemanticPromotionError("serialized proof node order is invalid")
            prior_hash = str(proof.get("start_hash") or "")
            if prior_hash != previous_artifact.get("artifact_hash"):
                raise SemanticPromotionError("turn-to-turn hash chain is discontinuous")
            receipt_hashes: list[str] = []
            for index, hop in enumerate(hops):
                if not isinstance(hop, dict) or hop.get("status") != "completed":
                    raise SemanticPromotionError("serialized hop is nonterminal")
                node = nodes[index]
                artifact = hop.get("artifact")
                if not isinstance(artifact, dict) or not _verify_artifact_hash(
                    artifact
                ):
                    raise SemanticPromotionError(
                        "serialized hop artifact hash is invalid"
                    )
                semantic_expectations = {
                    "schema_version": SEMANTIC_HOP_SCHEMA,
                    "cycle_id": cycle_id,
                    "trace_id": trace_id,
                    "correlation_id": cycle_id,
                    "turn": expected_turn,
                    "ordinal": index + 1,
                    "node_id": node["id"],
                    "input_signal": node["input_signal"],
                    "output_signal": node["output_signal"],
                    "transform": node["transform"],
                    "authority": node["authority"],
                    "causation_id": previous_artifact.get("message_id"),
                    "claim_ceiling": "local_rehearsal",
                    "external_effects_proven": False,
                    "visited_nodes": expected_nodes[: index + 1],
                }
                if any(
                    artifact.get(key) != value
                    for key, value in semantic_expectations.items()
                ):
                    raise SemanticPromotionError("serialized hop semantics are invalid")
                previous_payload = previous_artifact.get("payload")
                artifact_payload = artifact.get("payload")
                if not isinstance(previous_payload, dict) or not isinstance(
                    artifact_payload, dict
                ):
                    raise SemanticPromotionError(
                        "serialized semantic payload is invalid"
                    )
                expected_transforms = list(previous_payload.get("transforms") or [])
                expected_transforms.append(
                    {
                        "turn": expected_turn,
                        "ordinal": index + 1,
                        "node_id": node["id"],
                        "transform": node["transform"],
                    }
                )
                if artifact_payload.get("transforms") != expected_transforms:
                    raise SemanticPromotionError(
                        "serialized transform ledger is invalid"
                    )
                if artifact.get("predecessor_hash") != prior_hash:
                    raise SemanticPromotionError(
                        "serialized hop chain is discontinuous"
                    )
                if hop.get("artifact_hash") != artifact.get("artifact_hash"):
                    raise SemanticPromotionError(
                        "hop/artifact hash projection is inconsistent"
                    )
                if hop.get("predecessor_hash") != prior_hash:
                    raise SemanticPromotionError(
                        "hop predecessor projection is inconsistent"
                    )
                if hop.get("ordinal") != index + 1 or hop.get("turn") != expected_turn:
                    raise SemanticPromotionError(
                        "hop ordinal/turn projection is inconsistent"
                    )
                expected_task_id = (
                    f"task_{cycle_id}_t{expected_turn:02d}_h{index + 1:02d}"
                )
                expected_run_id = (
                    f"run_{cycle_id}_t{expected_turn:02d}_h{index + 1:02d}"
                )
                expected_idempotency_key = (
                    f"idem_{cycle_id}_t{expected_turn:02d}_h{index + 1:02d}"
                )
                execution_expectations = {
                    "task_id": expected_task_id,
                    "run_id": expected_run_id,
                    "idempotency_key": expected_idempotency_key,
                    "a2a_receipt_id": f"rr_{expected_run_id}_a2a_completed",
                    "semantic_receipt_id": f"rr_{expected_run_id}_autocatalytic_hop",
                }
                if any(
                    hop.get(key) != value
                    for key, value in execution_expectations.items()
                ):
                    raise SemanticPromotionError(
                        "serialized hop execution identity is invalid"
                    )
                verification_task = A2ATask(
                    id=expected_task_id,
                    context_id=cycle_id,
                    to_agent=str(node["id"]),
                    status=A2ATaskStatus.COMPLETED,
                    capability=f"autocatalytic.{node['id']}",
                    trace_id=trace_id,
                    metadata={
                        "execution_identity": {
                            "run_id": expected_run_id,
                            "task_id": expected_task_id,
                            "idempotency_key": expected_idempotency_key,
                        }
                    },
                )
                _validate_project_semantics(
                    artifact=artifact,
                    node=node,
                    predecessor=previous_artifact,
                    task=verification_task,
                    turn=expected_turn,
                )
                message_id = str(artifact.get("message_id") or "")
                if not message_id:
                    raise SemanticPromotionError(
                        "serialized artifact message identity is empty"
                    )
                task_ids.append(expected_task_id)
                message_ids.append(message_id)
                expected_completion = _completion_hash(hop)
                if hop.get("completion_hash") != expected_completion:
                    raise SemanticPromotionError(
                        "serialized completion hash is invalid"
                    )
                receipt_hashes.append(expected_completion)
                prior_hash = str(artifact["artifact_hash"])
                previous_artifact = artifact
            if proof.get("hop_receipt_hashes") != receipt_hashes:
                raise SemanticPromotionError("proof receipt hash list is invalid")
            if proof.get("end_hash") != prior_hash:
                raise SemanticPromotionError("proof end hash is invalid")
            if proof.get("proof_hash") != _digest(_proof_core_from_dict(proof)):
                raise SemanticPromotionError("cycle proof hash is invalid")
            if proof.get("cycle_closed") is not True:
                raise SemanticPromotionError("cycle proof is not closed")
            if previous_artifact.get("output_signal") != nodes[0]["input_signal"]:
                raise SemanticPromotionError(
                    "serialized proof does not close the signal ring"
                )
        expected_total_hops = len(proofs) * REQUIRED_NODE_COUNT
        if (
            len(set(task_ids)) != expected_total_hops
            or len(set(message_ids)) != expected_total_hops + 1
        ):
            raise SemanticPromotionError(
                "witness task/message identities are not globally unique"
            )
        transport_acks = witness.get("transport_acks")
        if (
            witness.get("transport_evidence") != "in_process_local"
            or not isinstance(transport_acks, list)
            or len(transport_acks) != expected_total_hops
        ):
            raise SemanticPromotionError("transport evidence is incomplete")
        expected_ack_rows = [
            {"task_id": task_id, "transport": "in_process_local", "accepted": True}
            for task_id in task_ids
        ]
        if transport_acks != expected_ack_rows:
            raise SemanticPromotionError("transport acknowledgement ledger is invalid")
        return StructuralCycleCheck(valid=True)
    except (
        ImportError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        SemanticPromotionError,
    ) as exc:
        return StructuralCycleCheck(valid=False, error=str(exc))


def verify_cycle_witness(
    witness: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    *,
    runtime_db: Path | None = None,
) -> LocalReceiptConsistencyCheck:
    """Check structure plus exact rows in a local mutable runtime store.

    A valid result establishes local receipt consistency only. Because the
    SQLite store is writable by the local operator, it never authenticates
    execution provenance and cannot promote the portfolio above
    ``local_rehearsal``.
    """

    structural = _check_structural_cycle_witness(witness, portfolio)
    if not structural.valid:
        return LocalReceiptConsistencyCheck(valid=False, error=structural.error)
    try:
        _verify_local_runtime_receipt_consistency(
            witness,
            runtime_db=Path(runtime_db or DEFAULT_RUNTIME_DB),
        )
        return LocalReceiptConsistencyCheck(valid=True)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return LocalReceiptConsistencyCheck(valid=False, error=str(exc))
