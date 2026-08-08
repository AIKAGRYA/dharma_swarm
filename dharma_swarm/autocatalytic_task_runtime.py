"""Typed A2A task handling for the local autocatalytic rehearsal."""

from __future__ import annotations

import json
from typing import Any, Mapping

from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2APart,
    A2APartType,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.autocatalytic_adapters import (
    _consume_project_cross_feeds,
    _project_cross_feeds,
    _project_evidence_for,
)
from dharma_swarm.autocatalytic_contracts import (
    SEMANTIC_HOP_SCHEMA,
    SemanticPromotionError,
    _canonical_json,
    _digest,
    _verify_artifact_hash,
)


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
