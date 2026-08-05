"""Ten-node autocatalytic portfolio and local semantic A2A rehearsal harness.

This compatibility facade preserves the established public imports and CLI.
Structural validation and local mutable-receipt consistency remain distinct;
no result from this module authenticates external execution provenance.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2AMessage,
    A2APart,
    A2APartType,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.agent_card import AgentCapability, AgentCard, CardRegistry
from dharma_swarm.a2a.spine_adapter import submit_task_via_spine_sync
from dharma_swarm.autocatalytic_adapters import (
    _consume_project_cross_feeds,
    _project_cross_feeds,
    _project_evidence_for,
    _source_snapshot,
    _validate_project_semantics,
)
from dharma_swarm.autocatalytic_contracts import (
    CYCLE_PROOF_SCHEMA,
    CYCLE_WITNESS_SCHEMA,
    LOCAL_RECEIPT_CONSISTENCY_SCOPE,
    PORTFOLIO_SCHEMA,
    REQUIRED_NODE_COUNT,
    RUNTIME_ATTESTATION_SCHEMA,
    SEMANTIC_HOP_SCHEMA,
    VERIFIER_VERSION,
    LocalReceiptConsistencyCheck,
    PortfolioContractError,
    SemanticPromotionError,
    StructuralCycleCheck,
    StructuralCycleProof,
    StructuralHop,
    TransportAck,
    _build_catalytic_graph,
    _canonical_json,
    _completion_hash,
    _declared_source_digest,
    _digest,
    _ordered_nodes,
    _semantic_seed,
    _utc_now,
    _verify_artifact_hash,
    load_portfolio_manifest,
    validate_portfolio,
)
from dharma_swarm.autocatalytic_verifier import (
    _check_structural_cycle_witness,
    _implementation_fingerprint,
    _runtime_attestation_core,
    verify_cycle_witness,
)
from dharma_swarm.correlation_context import correlation_scope_sync
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore

__all__ = [
    "LOCAL_RECEIPT_CONSISTENCY_SCOPE",
    "LocalReceiptConsistencyCheck",
    "PortfolioContractError",
    "REQUIRED_NODE_COUNT",
    "SemanticPromotionError",
    "StructuralCycleCheck",
    "StructuralCycleProof",
    "StructuralHop",
    "TransportAck",
    "build_autocatalytic_snapshot",
    "build_structural_cycle_proof",
    "build_structural_hop",
    "load_latest_cycle",
    "load_portfolio_manifest",
    "run_local_cycle",
    "validate_portfolio",
    "verify_cycle_witness",
    "_build_catalytic_graph",
    "_check_structural_cycle_witness",
    "_declared_source_digest",
    "_digest",
    "_implementation_fingerprint",
    "_project_evidence_for",
    "_semantic_seed",
    "_source_snapshot",
]

def _default_state_dir() -> Path:
    """Resolve the manifest-declared state root before the legacy alias."""

    return dharma_state_dir("DHARMA_STATE_DIR", "DHARMA_HOME").expanduser()


def _default_witness_dir() -> Path:
    return _default_state_dir() / "a2a" / "autocatalytic_portfolio"


def _default_runtime_db() -> Path:
    return _default_state_dir() / "state" / "runtime.db"

def _input_artifact(task: A2ATask) -> dict[str, Any]:
    parts = [part for message in task.history for part in message.parts]
    data_parts = [part for part in parts if part.type == A2APartType.DATA]
    if len(data_parts) != 1:
        raise SemanticPromotionError(
            "A2A hop requires exactly one structured input part"
        )
    try:
        value = json.loads(data_parts[0].content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SemanticPromotionError("A2A hop input is not valid JSON") from exc
    if not isinstance(value, dict):
        raise SemanticPromotionError("A2A hop input artifact must be an object")
    if not _verify_artifact_hash(value):
        raise SemanticPromotionError("A2A hop input artifact hash is invalid")
    return value


def _handler_for(node: Mapping[str, Any]):
    node_id = str(node["id"])
    ordinal = int(node["ordinal"])

    def _handler(task: A2ATask) -> A2ATask:
        predecessor = _input_artifact(task)
        turn = int(task.metadata.get("turn", -1))
        if task.to_agent != node_id:
            raise SemanticPromotionError(
                f"handler {node_id} received task for {task.to_agent}"
            )
        if predecessor.get("output_signal") != node.get("input_signal"):
            raise SemanticPromotionError(
                f"{node_id} requires {node.get('input_signal')}, got "
                f"{predecessor.get('output_signal')}"
            )
        predecessor_turn = int(predecessor.get("turn", -1))
        prior_visited = list(predecessor.get("visited_nodes") or [])
        visited = [] if predecessor_turn != turn else prior_visited
        if len(visited) != ordinal - 1:
            raise SemanticPromotionError(
                f"{node_id} expected {ordinal - 1} prior nodes, got {len(visited)}"
            )
        if node_id in visited:
            raise SemanticPromotionError(f"duplicate node visit: {node_id}")
        causation_id = str(task.metadata.get("causation_id") or "")
        if causation_id != predecessor.get("message_id"):
            raise SemanticPromotionError(
                f"{node_id} causation does not name predecessor message"
            )

        payload = dict(predecessor.get("payload") or {})
        transforms = list(payload.get("transforms") or [])
        transforms.append(
            {
                "turn": turn,
                "ordinal": ordinal,
                "node_id": node_id,
                "transform": str(node["transform"]),
            }
        )
        payload["transforms"] = transforms
        _, consumed_cross_feeds = _consume_project_cross_feeds(
            node=node, predecessor_payload=payload, turn=turn
        )
        project_evidence = _project_evidence_for(
            node, predecessor, task, turn, consumed_cross_feeds
        )
        evidence_ledger = list(payload.get("project_evidence_ledger") or [])
        evidence_ledger.append(project_evidence)
        payload["project_evidence_ledger"] = evidence_ledger
        cross_feed_bus, recomputed_consumed, emitted_cross_feeds = (
            _project_cross_feeds(
                node=node,
                predecessor_payload=payload,
                project_evidence=project_evidence,
                turn=turn,
            )
        )
        if recomputed_consumed != consumed_cross_feeds:
            raise SemanticPromotionError(f"{node_id} cross-feed consumption drifted")
        payload["cross_feed_bus"] = cross_feed_bus
        payload["last_signal_state"] = project_evidence["signal"]["state"]
        artifact: dict[str, Any] = {
            "schema_version": SEMANTIC_HOP_SCHEMA,
            "cycle_id": str(task.metadata["cycle_id"]),
            "trace_id": task.trace_id,
            "correlation_id": str(task.metadata["correlation_id"]),
            "turn": turn,
            "ordinal": ordinal,
            "node_id": node_id,
            "input_signal": str(node["input_signal"]),
            "output_signal": str(node["output_signal"]),
            "transform": str(node["transform"]),
            "message_id": str(task.metadata["output_message_id"]),
            "causation_id": causation_id,
            "predecessor_hash": str(predecessor["artifact_hash"]),
            "visited_nodes": [*visited, node_id],
            "payload": payload,
            "signal": project_evidence["signal"],
            "project_evidence": project_evidence,
            "consumed_cross_feeds": consumed_cross_feeds,
            "emitted_cross_feeds": emitted_cross_feeds,
            "authority": str(node["authority"]),
            "claim_ceiling": "local_rehearsal",
            "external_effects_proven": False,
        }
        artifact["artifact_hash"] = _digest(artifact)
        task.artifacts = [
            A2AArtifact(
                id=f"artifact_{task.id}",
                name=f"{node_id} semantic output",
                description="Typed local-rehearsal semantic handoff",
                parts=[A2APart.data(_canonical_json(artifact))],
                metadata={
                    "schema_version": SEMANTIC_HOP_SCHEMA,
                    "claim_ceiling": "local_rehearsal",
                },
            )
        ]
        task.result = str(node["output_signal"])
        task.status = A2ATaskStatus.COMPLETED
        return task

    return _handler


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


def build_autocatalytic_snapshot(
    *, witness_dir: Path | None = None, runtime_db: Path | None = None
) -> dict[str, Any]:
    """Return the API/dashboard read model with topology and latest proof."""

    portfolio = load_portfolio_manifest()
    errors = validate_portfolio(portfolio)
    graph = _build_catalytic_graph(portfolio)
    summary = graph.summary()
    topology = {
        **summary,
        "required_nodes": REQUIRED_NODE_COUNT,
        "strongly_connected": summary["largest_scc"] == REQUIRED_NODE_COUNT,
        "one_autocatalytic_set": summary["autocatalytic_sets"] == 1,
        "contract_valid": not errors,
        "validation_errors": errors,
    }
    return {
        "schema_version": PORTFOLIO_SCHEMA,
        "portfolio": portfolio,
        "topology": topology,
        "latest_cycle": load_latest_cycle(
            portfolio,
            witness_dir=witness_dir,
            runtime_db=runtime_db,
        ),
    }


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate declared topology and print snapshot")
    run_parser = subparsers.add_parser("run", help="run a local two-turn A2A rehearsal")
    run_parser.add_argument("--turns", type=int, default=2)
    run_parser.add_argument("--witness-dir", type=Path)
    run_parser.add_argument("--runtime-db", type=Path)
    args = parser.parse_args(argv)

    if args.command == "check":
        snapshot = build_autocatalytic_snapshot()
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 0 if snapshot["topology"]["contract_valid"] else 1
    witness = run_local_cycle(
        witness_dir=args.witness_dir,
        runtime_db=args.runtime_db,
        turns=args.turns,
        persist=True,
    )
    print(json.dumps(witness, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
