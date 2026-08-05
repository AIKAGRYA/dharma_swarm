"""Structural and local mutable-receipt verification for cycle witnesses."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.a2a.a2a_server import A2ATask, A2ATaskStatus
from dharma_swarm.autocatalytic_adapters import _validate_project_semantics
from dharma_swarm.autocatalytic_contracts import (
    CYCLE_PROOF_SCHEMA,
    CYCLE_WITNESS_SCHEMA,
    LOCAL_RECEIPT_CONSISTENCY_SCOPE,
    REQUIRED_NODE_COUNT,
    RUNTIME_ATTESTATION_SCHEMA,
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
from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB

_IMPLEMENTATION_MODULE_NAMES = (
    "autocatalytic_adapters.py",
    "autocatalytic_contracts.py",
    "autocatalytic_portfolio.py",
    "autocatalytic_verifier.py",
)


def _load_implementation_source_sha256() -> str:
    """Hash the exact four-module source bundle once during import."""

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
    """Bind a witness to the loaded four-module implementation bundle."""

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


def _runtime_attestation_core(witness: Mapping[str, Any]) -> dict[str, Any]:
    proofs = witness.get("proofs")
    proof_rows = proofs if isinstance(proofs, list) else []
    hops = [
        hop
        for proof in proof_rows
        if isinstance(proof, dict)
        for hop in (proof.get("hops") or [])
        if isinstance(hop, dict)
    ]
    seed = witness.get("seed_artifact")
    return {
        "schema_version": RUNTIME_ATTESTATION_SCHEMA,
        "verifier_version": VERIFIER_VERSION,
        "cycle_id": witness.get("cycle_id"),
        "trace_id": witness.get("trace_id"),
        "correlation_id": witness.get("correlation_id"),
        "implementation": witness.get("implementation"),
        "seed_hash": seed.get("artifact_hash") if isinstance(seed, dict) else None,
        "proof_hashes": [
            proof.get("proof_hash") for proof in proof_rows if isinstance(proof, dict)
        ],
        "completion_hashes": [hop.get("completion_hash") for hop in hops],
        "a2a_receipt_ids": [hop.get("a2a_receipt_id") for hop in hops],
        "semantic_receipt_ids": [hop.get("semantic_receipt_id") for hop in hops],
        "turns_proven": witness.get("turns_proven"),
        "total_completed_hops": len(hops),
        "evidence_scope": LOCAL_RECEIPT_CONSISTENCY_SCOPE,
        "independently_authenticated": False,
        "claim_ceiling": witness.get("claim_ceiling"),
        "external_effects_proven": witness.get("external_effects_proven"),
    }


def _runtime_receipt_rows(
    runtime_db: Path, *, correlation_id: str
) -> dict[str, dict[str, Any]]:
    if not runtime_db.is_file():
        raise SemanticPromotionError(
            f"runtime receipt database is missing: {runtime_db}"
        )
    try:
        with sqlite3.connect(
            f"{runtime_db.resolve().as_uri()}?mode=ro", uri=True
        ) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT receipt_id, receipt_type, run_id, task_id, trace_id, "
                "correlation_id, causation_id, parent_run_id, agent_id, "
                "idempotency_key, side_effect_key, status, payload_json, created_at "
                "FROM runtime_receipts WHERE correlation_id = ? AND receipt_type IN "
                "('a2a_task', 'autocatalytic_hop_proof', 'autocatalytic_cycle_proof')",
                (correlation_id,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise SemanticPromotionError(
            f"cannot read local runtime receipts: {exc}"
        ) from exc
    values: dict[str, dict[str, Any]] = {}
    for row in rows:
        receipt_id = str(row["receipt_id"] or "")
        if not receipt_id or receipt_id in values:
            raise SemanticPromotionError("local runtime receipt identities are invalid")
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise SemanticPromotionError(
                "local runtime receipt payload is invalid"
            ) from exc
        values[receipt_id] = {**dict(row), "payload": payload}
    return values


def _verify_local_runtime_receipt_consistency(
    witness: Mapping[str, Any], *, runtime_db: Path
) -> None:
    if witness.get("runtime_receipts_recorded") is not True:
        raise SemanticPromotionError(
            "witness does not claim persisted runtime receipts"
        )
    if witness.get("execution_evidence_scope") != LOCAL_RECEIPT_CONSISTENCY_SCOPE:
        raise SemanticPromotionError(
            "witness local receipt-consistency scope is missing or invalid"
        )
    if witness.get("execution_provenance_authenticated") is not False:
        raise SemanticPromotionError(
            "local mutable receipts cannot claim authenticated execution provenance"
        )
    attestation = witness.get("runtime_attestation")
    if not isinstance(attestation, dict):
        raise SemanticPromotionError("witness runtime attestation is missing")
    expected_core = _runtime_attestation_core(witness)
    expected_attestation = {
        **expected_core,
        "attestation_hash": _digest(expected_core),
    }
    if attestation != expected_attestation:
        raise SemanticPromotionError("witness runtime attestation is invalid")

    cycle_id = str(witness["cycle_id"])
    trace_id = str(witness["trace_id"])
    proofs = witness["proofs"]
    hops = [hop for proof in proofs for hop in proof["hops"]]
    rows = _runtime_receipt_rows(runtime_db, correlation_id=cycle_id)
    expected_receipt_ids = (
        {str(hop["a2a_receipt_id"]) for hop in hops}
        | {str(hop["semantic_receipt_id"]) for hop in hops}
        | {f"rr_{cycle_id}_semantic_cycle"}
    )
    if set(rows) != expected_receipt_ids:
        raise SemanticPromotionError(
            "runtime receipt set does not exactly back the witness: "
            f"missing={sorted(expected_receipt_ids - set(rows))}, "
            f"extra={sorted(set(rows) - expected_receipt_ids)}"
        )

    previous_run_id = ""
    for hop in hops:
        artifact = hop["artifact"]
        node_id = str(hop["node_id"])
        task_id = str(hop["task_id"])
        run_id = str(hop["run_id"])
        turn = int(hop["turn"])
        ordinal = int(hop["ordinal"])
        a2a_row = rows[str(hop["a2a_receipt_id"])]
        a2a_expected = {
            "receipt_type": "a2a_task",
            "run_id": run_id,
            "task_id": task_id,
            "trace_id": trace_id,
            "correlation_id": cycle_id,
            "causation_id": artifact["causation_id"],
            "parent_run_id": previous_run_id,
            "agent_id": node_id,
            "idempotency_key": hop["idempotency_key"],
            "side_effect_key": f"a2a_handler:{task_id}:autocatalytic.{node_id}",
            "status": "completed",
        }
        if any(a2a_row.get(key) != value for key, value in a2a_expected.items()):
            raise SemanticPromotionError(f"A2A runtime receipt mismatch for {task_id}")
        expected_a2a_payload = {
            "external_a2a_task_id": task_id,
            "context_id": cycle_id,
            "capability": f"autocatalytic.{node_id}",
        }
        if a2a_row.get("payload") != expected_a2a_payload:
            raise SemanticPromotionError(
                f"A2A runtime receipt payload mismatch for {task_id}"
            )

        semantic_row = rows[str(hop["semantic_receipt_id"])]
        semantic_expected = {
            "receipt_type": "autocatalytic_hop_proof",
            "run_id": run_id,
            "task_id": task_id,
            "trace_id": trace_id,
            "correlation_id": cycle_id,
            "causation_id": artifact["causation_id"],
            "parent_run_id": previous_run_id,
            "agent_id": "autocatalytic-verifier",
            "idempotency_key": f"{hop['idempotency_key']}:semantic",
            "side_effect_key": f"autocatalytic_hop:{cycle_id}:{turn}:{ordinal}",
            "status": "verified",
        }
        if any(
            semantic_row.get(key) != value for key, value in semantic_expected.items()
        ):
            raise SemanticPromotionError(
                f"semantic runtime receipt mismatch for {task_id}"
            )
        expected_semantic_payload = {
            "schema_version": SEMANTIC_HOP_SCHEMA,
            "turn": turn,
            "ordinal": ordinal,
            "node_id": node_id,
            "artifact_hash": hop["artifact_hash"],
            "predecessor_hash": hop["predecessor_hash"],
            "completion_hash": hop["completion_hash"],
            "a2a_receipt_id": hop["a2a_receipt_id"],
            "authority": artifact["authority"],
            "claim_ceiling": "local_rehearsal",
            "external_effects_proven": False,
        }
        if semantic_row.get("payload") != expected_semantic_payload:
            raise SemanticPromotionError(
                f"semantic receipt payload mismatch for {task_id}"
            )
        previous_run_id = run_id

    cycle_row = rows[f"rr_{cycle_id}_semantic_cycle"]
    last_hop = hops[-1]
    cycle_expected = {
        "receipt_type": "autocatalytic_cycle_proof",
        "run_id": last_hop["run_id"],
        "task_id": f"task_{cycle_id}_cycle_proof",
        "trace_id": trace_id,
        "correlation_id": cycle_id,
        "causation_id": last_hop["artifact"]["message_id"],
        "parent_run_id": "",
        "agent_id": "autocatalytic-verifier",
        "idempotency_key": f"idem_{cycle_id}_semantic_cycle",
        "side_effect_key": f"autocatalytic_cycle:{cycle_id}",
        "status": "completed",
    }
    if any(cycle_row.get(key) != value for key, value in cycle_expected.items()):
        raise SemanticPromotionError("cycle runtime receipt identity is invalid")
    expected_cycle_payload = {
        "schema_version": RUNTIME_ATTESTATION_SCHEMA,
        "attestation_hash": expected_attestation["attestation_hash"],
        "proof_hashes": expected_attestation["proof_hashes"],
        "completed_hops": REQUIRED_NODE_COUNT,
        "total_completed_hops": len(hops),
        "turns_proven": len(proofs),
        "evidence_scope": LOCAL_RECEIPT_CONSISTENCY_SCOPE,
        "independently_authenticated": False,
        "claim_ceiling": "local_rehearsal",
        "external_effects_proven": False,
        "witness_path": witness.get("witness_path"),
    }
    if cycle_row.get("payload") != expected_cycle_payload:
        raise SemanticPromotionError("cycle runtime receipt payload is invalid")


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
