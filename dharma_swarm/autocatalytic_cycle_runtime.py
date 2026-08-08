"""Local cycle orchestration, persistence, and witness loading."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.a2a.a2a_server import A2AMessage, A2APart, A2AServer, A2ATask
from dharma_swarm.a2a.agent_card import AgentCapability, AgentCard, CardRegistry
from dharma_swarm.a2a.spine_adapter import submit_task_via_spine_sync
from dharma_swarm.autocatalytic_contracts import (
    CYCLE_WITNESS_SCHEMA,
    LOCAL_RECEIPT_CONSISTENCY_SCOPE,
    REQUIRED_NODE_COUNT,
    RUNTIME_ATTESTATION_SCHEMA,
    SEMANTIC_HOP_SCHEMA,
    VERIFIER_VERSION,
    PortfolioContractError,
    SemanticPromotionError,
    StructuralCycleProof,
    StructuralHop,
    TransportAck,
    _canonical_json,
    _digest,
    _ordered_nodes,
    _semantic_seed,
    _utc_now,
    load_portfolio_manifest,
    validate_portfolio,
)
from dharma_swarm.autocatalytic_proof_builders import (
    build_structural_cycle_proof,
    build_structural_hop,
)
from dharma_swarm.autocatalytic_task_runtime import _handler_for
from dharma_swarm.autocatalytic_verifier import (
    _check_structural_cycle_witness,
    _implementation_fingerprint,
    _runtime_attestation_core,
    verify_cycle_witness,
)
from dharma_swarm.correlation_context import correlation_scope_sync
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore


def _default_state_dir() -> Path:
    """Resolve the manifest-declared state root before the legacy alias."""

    return dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME").expanduser()


def _default_witness_dir() -> Path:
    return _default_state_dir() / "a2a" / "autocatalytic_portfolio"


def _default_runtime_db() -> Path:
    return _default_state_dir() / "state" / "runtime.db"


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def run_local_cycle(
    *,
    portfolio: Mapping[str, Any] | None = None,
    witness_dir: Path | None = None,
    runtime_db: Path | None = None,
    turns: int = 2,
    persist: bool = True,
) -> dict[str, Any]:
    """Run a ten-node rehearsal and check local mutable-receipt consistency."""

    declared = dict(portfolio or load_portfolio_manifest())
    errors = validate_portfolio(declared, require_files=persist)
    if errors:
        raise PortfolioContractError("; ".join(errors))
    if turns < 2:
        raise PortfolioContractError("closure witness requires at least two turns")
    if not persist:
        raise PortfolioContractError(
            "semantic cycle proof requires persisted A2A and runtime receipts"
        )

    cycle_id = f"autocat_{uuid.uuid4().hex[:16]}"
    trace_id = f"trc_{uuid.uuid4().hex[:16]}"
    output_dir = witness_dir or _default_witness_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    cards = CardRegistry(cards_dir=output_dir / "cards")

    runtime_state = RuntimeStateStore(
        runtime_db or _default_runtime_db(), include_memory_plane=False
    )
    runtime_state.init_db_sync()
    server = A2AServer(
        task_log_path=output_dir / f"{cycle_id}.tasks.jsonl",
        persist=persist,
        runtime_state=runtime_state,
        require_execution_identity=True,
    )

    nodes = _ordered_nodes(declared)
    for node in nodes:
        capability = f"autocatalytic.{node['id']}"
        cards.register(
            AgentCard(
                name=str(node["id"]),
                agent_uid=str(node["id"]),
                description=str(node["role"]),
                capabilities=[
                    AgentCapability(
                        name=capability,
                        description=f"{node['input_signal']} -> {node['output_signal']}",
                        input_modes=["data"],
                        output_modes=["data"],
                        tags=["autocatalytic", "semantic-hop", str(node["authority"])],
                    )
                ],
                role="metabolic-node",
                status="idle",
                metadata={
                    "ordinal": int(node["ordinal"]),
                    "authority": str(node["authority"]),
                    "claim_ceiling": "local_rehearsal",
                },
            )
        )
        server.register_handler(capability, _handler_for(node))

    seed_artifact = _semantic_seed(cycle_id, trace_id)
    predecessor = seed_artifact
    proofs: list[StructuralCycleProof] = []
    transport_acks: list[TransportAck] = []
    parent_run_id = ""
    with correlation_scope_sync(trace_id=trace_id, session_id=cycle_id):
        for turn in range(turns):
            turn_start = predecessor
            completed: list[StructuralHop] = []
            for node in nodes:
                ordinal = int(node["ordinal"])
                node_id = str(node["id"])
                task_id = f"task_{cycle_id}_t{turn:02d}_h{ordinal:02d}"
                run_id = f"run_{cycle_id}_t{turn:02d}_h{ordinal:02d}"
                request_message_id = f"req_{cycle_id}_t{turn:02d}_h{ordinal:02d}"
                output_message_id = f"msg_{cycle_id}_t{turn:02d}_h{ordinal:02d}"
                causation_id = str(predecessor["message_id"])
                identity = {
                    "trace_id": trace_id,
                    "correlation_id": cycle_id,
                    "task_id": task_id,
                    "run_id": run_id,
                    "claim_id": f"claim_{cycle_id}_t{turn:02d}_h{ordinal:02d}",
                    "idempotency_key": f"idem_{cycle_id}_t{turn:02d}_h{ordinal:02d}",
                    "causation_id": causation_id,
                    "parent_run_id": parent_run_id,
                    "agent_id": node_id,
                    "session_id": cycle_id,
                    "external_a2a_task_id": task_id,
                    "message_id": request_message_id,
                    "artifact_id": f"artifact_{task_id}",
                }
                task = A2ATask(
                    id=task_id,
                    context_id=cycle_id,
                    from_agent=completed[-1].node_id if completed else "organism-root",
                    to_agent=node_id,
                    capability=f"autocatalytic.{node_id}",
                    history=[
                        A2AMessage(
                            role="user",
                            parts=[A2APart.data(_canonical_json(predecessor))],
                            metadata={"message_id": request_message_id},
                        )
                    ],
                    trace_id=trace_id,
                    metadata={
                        "execution_identity": identity,
                        "cycle_id": cycle_id,
                        "correlation_id": cycle_id,
                        "turn": turn,
                        "ordinal": ordinal,
                        "causation_id": causation_id,
                        "output_message_id": output_message_id,
                    },
                )
                transport_acks.append(
                    TransportAck(
                        task_id=task_id,
                        transport="in_process_local",
                        accepted=True,
                    )
                )
                observed, spine_receipt = submit_task_via_spine_sync(
                    server,
                    task,
                    router_name="autocatalytic_portfolio",
                )
                if spine_receipt.status != "ok":
                    raise SemanticPromotionError(
                        "runtime truth spine rejected "
                        f"{task_id}: {spine_receipt.error_detail or spine_receipt.status}"
                    )
                hop = build_structural_hop(
                    observed,
                    node=node,
                    predecessor=predecessor,
                    cycle_id=cycle_id,
                    trace_id=trace_id,
                    turn=turn,
                )
                runtime_state.record_runtime_receipt_sync(
                    RuntimeReceipt(
                        receipt_id=hop.semantic_receipt_id,
                        receipt_type="autocatalytic_hop_proof",
                        status="verified",
                        run_id=hop.run_id,
                        task_id=hop.task_id,
                        trace_id=trace_id,
                        correlation_id=cycle_id,
                        causation_id=str(hop.artifact["causation_id"]),
                        parent_run_id=parent_run_id,
                        agent_id="autocatalytic-verifier",
                        idempotency_key=f"{hop.idempotency_key}:semantic",
                        side_effect_key=f"autocatalytic_hop:{cycle_id}:{turn}:{ordinal}",
                        payload={
                            "schema_version": SEMANTIC_HOP_SCHEMA,
                            "turn": turn,
                            "ordinal": ordinal,
                            "node_id": node_id,
                            "artifact_hash": hop.artifact_hash,
                            "predecessor_hash": hop.predecessor_hash,
                            "completion_hash": hop.completion_hash,
                            "a2a_receipt_id": hop.a2a_receipt_id,
                            "authority": str(node["authority"]),
                            "claim_ceiling": "local_rehearsal",
                            "external_effects_proven": False,
                        },
                    )
                )
                completed.append(hop)
                predecessor = hop.artifact
                parent_run_id = run_id
            proofs.append(
                build_structural_cycle_proof(
                    completed,
                    portfolio=declared,
                    predecessor=turn_start,
                    cycle_id=cycle_id,
                    trace_id=trace_id,
                    turn=turn,
                )
            )

    proof_dicts = [proof.to_dict() for proof in proofs]
    cycle_path = output_dir / f"{cycle_id}.json"
    latest_path = output_dir / "latest.json"
    witness: dict[str, Any] = {
        "schema_version": CYCLE_WITNESS_SCHEMA,
        "verifier_version": VERIFIER_VERSION,
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "correlation_id": cycle_id,
        "mode": "local_rehearsal",
        "claim_ceiling": "local_rehearsal",
        "generated_at": _utc_now(),
        "structural_proof_valid": False,
        "local_receipt_consistency_valid": False,
        "cycle_closed": True,
        "completed_hops": REQUIRED_NODE_COUNT,
        "required_hops": REQUIRED_NODE_COUNT,
        "turns_proven": turns,
        "transport_evidence": "in_process_local",
        "transport_acks": [asdict(ack) for ack in transport_acks],
        "external_effects_proven": False,
        "runtime_receipts_recorded": True,
        "execution_evidence_scope": LOCAL_RECEIPT_CONSISTENCY_SCOPE,
        "execution_provenance_authenticated": False,
        "implementation": _implementation_fingerprint(declared),
        "seed_artifact": seed_artifact,
        "proofs": proof_dicts,
        "witness_path": str(cycle_path),
    }
    attestation_core = _runtime_attestation_core(witness)
    witness["runtime_attestation"] = {
        **attestation_core,
        "attestation_hash": _digest(attestation_core),
    }
    structural = _check_structural_cycle_witness(witness, declared)
    if not structural.valid:
        raise SemanticPromotionError(
            f"structural self-verification failed: {structural.error}"
        )
    runtime_state.record_runtime_receipt_sync(
        RuntimeReceipt(
            receipt_id=f"rr_{cycle_id}_semantic_cycle",
            receipt_type="autocatalytic_cycle_proof",
            status="completed",
            run_id=parent_run_id,
            task_id=f"task_{cycle_id}_cycle_proof",
            trace_id=trace_id,
            correlation_id=cycle_id,
            causation_id=str(predecessor["message_id"]),
            parent_run_id="",
            agent_id="autocatalytic-verifier",
            idempotency_key=f"idem_{cycle_id}_semantic_cycle",
            side_effect_key=f"autocatalytic_cycle:{cycle_id}",
            payload={
                "schema_version": RUNTIME_ATTESTATION_SCHEMA,
                "attestation_hash": witness["runtime_attestation"]["attestation_hash"],
                "proof_hashes": witness["runtime_attestation"]["proof_hashes"],
                "completed_hops": REQUIRED_NODE_COUNT,
                "total_completed_hops": turns * REQUIRED_NODE_COUNT,
                "turns_proven": turns,
                "evidence_scope": LOCAL_RECEIPT_CONSISTENCY_SCOPE,
                "independently_authenticated": False,
                "claim_ceiling": "local_rehearsal",
                "external_effects_proven": False,
                "witness_path": str(cycle_path),
            },
        )
    )
    consistency = verify_cycle_witness(
        witness,
        declared,
        runtime_db=Path(runtime_state.db_path),
    )
    if not consistency.valid:
        raise SemanticPromotionError(
            f"local receipt-consistency verification failed: {consistency.error}"
        )
    witness["structural_proof_valid"] = True
    witness["local_receipt_consistency_valid"] = True
    _write_json_atomic(cycle_path, witness)
    _write_json_atomic(latest_path, witness)
    return witness


def load_latest_cycle(
    portfolio: Mapping[str, Any],
    *,
    witness_dir: Path | None = None,
    runtime_db: Path | None = None,
) -> dict[str, Any] | None:
    """Load and reverify the latest local witness; never trust stored booleans."""

    path = (witness_dir or _default_witness_dir()) / "latest.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "structural_proof_valid": False,
            "local_receipt_consistency_valid": False,
            "verification_error": f"cannot load witness: {exc}",
            "source_alias_path": str(path),
        }
    if not isinstance(value, dict):
        return {
            "structural_proof_valid": False,
            "local_receipt_consistency_valid": False,
            "verification_error": "latest witness is not an object",
            "source_alias_path": str(path),
        }
    structural = _check_structural_cycle_witness(value, portfolio)
    consistency = verify_cycle_witness(
        value,
        portfolio,
        runtime_db=runtime_db or _default_runtime_db(),
    )
    value["structural_proof_valid"] = structural.valid
    value["local_receipt_consistency_valid"] = consistency.valid
    value["cycle_closed"] = structural.valid
    value["completed_hops"] = REQUIRED_NODE_COUNT if structural.valid else 0
    value["required_hops"] = REQUIRED_NODE_COUNT
    value["external_effects_proven"] = False
    value["source_alias_path"] = str(path)
    if consistency.error:
        value["verification_error"] = consistency.error
    return value
