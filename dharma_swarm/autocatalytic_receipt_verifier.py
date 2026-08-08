"""Read-only local receipt-consistency checks for autocatalytic witnesses."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.autocatalytic_contracts import (
    LOCAL_RECEIPT_CONSISTENCY_SCOPE,
    REQUIRED_NODE_COUNT,
    RUNTIME_ATTESTATION_SCHEMA,
    SEMANTIC_HOP_SCHEMA,
    VERIFIER_VERSION,
    SemanticPromotionError,
    _digest,
)


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
