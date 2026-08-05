"""Independent structural proof builders for autocatalytic A2A artifacts."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from dharma_swarm.a2a.a2a_server import A2APartType, A2ATask, A2ATaskStatus
from dharma_swarm.autocatalytic_adapters import _validate_project_semantics
from dharma_swarm.autocatalytic_contracts import (
    CYCLE_PROOF_SCHEMA,
    REQUIRED_NODE_COUNT,
    SEMANTIC_HOP_SCHEMA,
    SemanticPromotionError,
    StructuralCycleProof,
    StructuralHop,
    _completion_hash,
    _digest,
    _ordered_nodes,
    _verify_artifact_hash,
)


def build_structural_hop(
    task: A2ATask,
    *,
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    cycle_id: str,
    trace_id: str,
    turn: int,
) -> StructuralHop:
    """Recompute one terminal task into a non-authoritative structural value."""

    if not isinstance(task, A2ATask):
        raise SemanticPromotionError(
            "StructuralHop requires a terminal A2ATask, not transport evidence"
        )
    if task.status is not A2ATaskStatus.COMPLETED:
        raise SemanticPromotionError(
            f"task {task.id} is {task.status.value}, not exact completed"
        )
    if len(task.artifacts) != 1:
        raise SemanticPromotionError("completed hop requires exactly one artifact")
    parts = task.artifacts[0].parts
    if len(parts) != 1 or parts[0].type is not A2APartType.DATA:
        raise SemanticPromotionError("completed hop requires one typed data artifact")
    try:
        artifact = json.loads(parts[0].content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SemanticPromotionError("semantic artifact is not valid JSON") from exc
    if not isinstance(artifact, dict):
        raise SemanticPromotionError("semantic artifact must be an object")
    expected = {
        "schema_version": SEMANTIC_HOP_SCHEMA,
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "correlation_id": cycle_id,
        "turn": turn,
        "ordinal": int(node["ordinal"]),
        "node_id": str(node["id"]),
        "input_signal": str(node["input_signal"]),
        "output_signal": str(node["output_signal"]),
        "transform": str(node["transform"]),
        "authority": str(node["authority"]),
        "predecessor_hash": str(predecessor["artifact_hash"]),
        "causation_id": str(predecessor["message_id"]),
        "claim_ceiling": "local_rehearsal",
        "external_effects_proven": False,
    }
    mismatches = {
        key: {"expected": value, "observed": artifact.get(key)}
        for key, value in expected.items()
        if artifact.get(key) != value
    }
    if mismatches:
        raise SemanticPromotionError(f"semantic artifact mismatch: {mismatches}")
    if task.to_agent != node["id"] or task.trace_id != trace_id:
        raise SemanticPromotionError(
            "task target/trace does not match semantic artifact"
        )
    if task.context_id != cycle_id or task.capability != f"autocatalytic.{node['id']}":
        raise SemanticPromotionError(
            "task context/capability does not match semantic artifact"
        )
    if task.result != node["output_signal"]:
        raise SemanticPromotionError(
            "task result does not project the typed output signal"
        )
    if task.metadata.get("causation_id") != predecessor.get("message_id"):
        raise SemanticPromotionError("task causation is not contiguous")
    output_message_id = str(task.metadata.get("output_message_id") or "")
    if not output_message_id or artifact.get("message_id") != output_message_id:
        raise SemanticPromotionError(
            "semantic artifact message identity is missing or invalid"
        )
    if not _verify_artifact_hash(artifact):
        raise SemanticPromotionError("semantic artifact hash is invalid")
    expected_visited = (
        []
        if int(predecessor.get("turn", -1)) != turn
        else list(predecessor.get("visited_nodes") or [])
    ) + [str(node["id"])]
    if artifact.get("visited_nodes") != expected_visited:
        raise SemanticPromotionError(
            "semantic artifact node visitation is not contiguous"
        )
    predecessor_payload = predecessor.get("payload")
    artifact_payload = artifact.get("payload")
    if not isinstance(predecessor_payload, dict) or not isinstance(
        artifact_payload, dict
    ):
        raise SemanticPromotionError("semantic hop payloads must be objects")
    expected_transforms = list(predecessor_payload.get("transforms") or [])
    expected_transforms.append(
        {
            "turn": turn,
            "ordinal": int(node["ordinal"]),
            "node_id": str(node["id"]),
            "transform": str(node["transform"]),
        }
    )
    if artifact_payload.get("transforms") != expected_transforms:
        raise SemanticPromotionError("semantic transform ledger is not contiguous")
    _validate_project_semantics(
        artifact=artifact,
        node=node,
        predecessor=predecessor,
        task=task,
        turn=turn,
    )

    identity = task.metadata.get("execution_identity")
    if not isinstance(identity, dict):
        raise SemanticPromotionError("completed hop lacks execution identity")
    expected_run_id = f"run_{cycle_id}_t{turn:02d}_h{int(node['ordinal']):02d}"
    expected_idempotency_key = (
        f"idem_{cycle_id}_t{turn:02d}_h{int(node['ordinal']):02d}"
    )
    expected_identity = {
        "task_id": task.id,
        "run_id": expected_run_id,
        "trace_id": trace_id,
        "correlation_id": cycle_id,
        "causation_id": predecessor.get("message_id"),
        "agent_id": str(node["id"]),
        "idempotency_key": expected_idempotency_key,
        "external_a2a_task_id": task.id,
        "artifact_id": task.artifacts[0].id,
    }
    if any(identity.get(key) != value for key, value in expected_identity.items()):
        raise SemanticPromotionError("completed hop execution identity is invalid")
    a2a_receipt_id = f"rr_{expected_run_id}_a2a_completed"
    semantic_receipt_id = f"rr_{expected_run_id}_autocatalytic_hop"
    completion_payload = {
        "turn": turn,
        "ordinal": int(node["ordinal"]),
        "node_id": str(node["id"]),
        "task_id": task.id,
        "run_id": expected_run_id,
        "idempotency_key": expected_idempotency_key,
        "a2a_receipt_id": a2a_receipt_id,
        "semantic_receipt_id": semantic_receipt_id,
        "status": task.status.value,
        "artifact": artifact,
        "artifact_hash": artifact["artifact_hash"],
        "predecessor_hash": artifact["predecessor_hash"],
    }
    completion_hash = _completion_hash(completion_payload)
    return StructuralHop(
        turn=turn,
        ordinal=int(node["ordinal"]),
        node_id=str(node["id"]),
        task_id=task.id,
        run_id=expected_run_id,
        idempotency_key=expected_idempotency_key,
        a2a_receipt_id=a2a_receipt_id,
        semantic_receipt_id=semantic_receipt_id,
        status=task.status.value,
        artifact=artifact,
        artifact_hash=str(artifact["artifact_hash"]),
        predecessor_hash=str(artifact["predecessor_hash"]),
        completion_hash=completion_hash,
    )


def build_structural_cycle_proof(
    hops: Sequence[StructuralHop],
    *,
    portfolio: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    cycle_id: str,
    trace_id: str,
    turn: int,
) -> StructuralCycleProof:
    """Construct a structural proof from exactly ten valid ordered hops."""

    nodes = _ordered_nodes(portfolio)
    expected_ids = [str(node["id"]) for node in nodes]
    if len(hops) != REQUIRED_NODE_COUNT:
        raise SemanticPromotionError(
            "StructuralCycleProof requires exactly "
            f"{REQUIRED_NODE_COUNT} StructuralHop values"
        )
    if [hop.node_id for hop in hops] != expected_ids:
        raise SemanticPromotionError(
            "StructuralCycleProof hop order does not match portfolio order"
        )
    if [hop.ordinal for hop in hops] != list(range(1, REQUIRED_NODE_COUNT + 1)):
        raise SemanticPromotionError(
            "StructuralCycleProof hop ordinals do not match portfolio order"
        )
    if len({hop.task_id for hop in hops}) != REQUIRED_NODE_COUNT:
        raise SemanticPromotionError(
            "StructuralCycleProof task identities must be unique"
        )
    message_ids = [str(hop.artifact.get("message_id") or "") for hop in hops]
    if not all(message_ids) or len(set(message_ids)) != REQUIRED_NODE_COUNT:
        raise SemanticPromotionError(
            "StructuralCycleProof message identities must be non-empty and unique"
        )
    if str(predecessor.get("message_id") or "") in message_ids:
        raise SemanticPromotionError(
            "StructuralCycleProof message identity must differ from its predecessor"
        )
    prior_hash = str(predecessor["artifact_hash"])
    previous_artifact: Mapping[str, Any] = predecessor
    for index, hop in enumerate(hops):
        node = nodes[index]
        if hop.turn != turn or hop.status != A2ATaskStatus.COMPLETED.value:
            raise SemanticPromotionError(
                "StructuralCycleProof contains a wrong-turn/nonterminal hop"
            )
        if hop.predecessor_hash != prior_hash:
            raise SemanticPromotionError(
                "StructuralCycleProof hash chain is discontinuous"
            )
        artifact = hop.artifact
        expected_semantics = {
            "schema_version": SEMANTIC_HOP_SCHEMA,
            "cycle_id": cycle_id,
            "trace_id": trace_id,
            "correlation_id": cycle_id,
            "turn": turn,
            "ordinal": index + 1,
            "node_id": node["id"],
            "input_signal": node["input_signal"],
            "output_signal": node["output_signal"],
            "transform": node["transform"],
            "authority": node["authority"],
            "causation_id": previous_artifact.get("message_id"),
            "predecessor_hash": prior_hash,
            "visited_nodes": expected_ids[: index + 1],
            "claim_ceiling": "local_rehearsal",
            "external_effects_proven": False,
        }
        if any(artifact.get(key) != value for key, value in expected_semantics.items()):
            raise SemanticPromotionError(
                "StructuralCycleProof contains an invalid semantic hop"
            )
        if not _verify_artifact_hash(
            artifact
        ) or hop.completion_hash != _completion_hash(hop):
            raise SemanticPromotionError(
                "StructuralCycleProof contains an invalid hop hash"
            )
        verification_task = A2ATask(
            id=hop.task_id,
            context_id=cycle_id,
            to_agent=str(node["id"]),
            status=A2ATaskStatus.COMPLETED,
            capability=f"autocatalytic.{node['id']}",
            trace_id=trace_id,
            metadata={
                "execution_identity": {
                    "run_id": hop.run_id,
                    "task_id": hop.task_id,
                    "idempotency_key": hop.idempotency_key,
                }
            },
        )
        _validate_project_semantics(
            artifact=artifact,
            node=node,
            predecessor=previous_artifact,
            task=verification_task,
            turn=turn,
        )
        prior_hash = hop.artifact_hash
        previous_artifact = artifact
    cycle_closed = (
        hops[-1].artifact["output_signal"] == nodes[0]["input_signal"]
        and nodes[-1]["next_node"] == nodes[0]["id"]
        and hops[-1].artifact["visited_nodes"] == expected_ids
    )
    if not cycle_closed:
        raise SemanticPromotionError(
            "StructuralCycleProof does not close the declared ring"
        )
    proof_core = {
        "schema_version": CYCLE_PROOF_SCHEMA,
        "cycle_id": cycle_id,
        "trace_id": trace_id,
        "turn": turn,
        "start_hash": str(predecessor["artifact_hash"]),
        "end_hash": hops[-1].artifact_hash,
        "hop_receipt_hashes": [hop.completion_hash for hop in hops],
        "cycle_closed": True,
    }
    return StructuralCycleProof(
        cycle_id=cycle_id,
        trace_id=trace_id,
        turn=turn,
        start_hash=str(predecessor["artifact_hash"]),
        end_hash=hops[-1].artifact_hash,
        proof_hash=_digest(proof_core),
        hops=tuple(hops),
    )
