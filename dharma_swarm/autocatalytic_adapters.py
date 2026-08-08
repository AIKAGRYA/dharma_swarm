"""Project-adapter registry, cross-feeds, and compatibility facade."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from dharma_swarm import autocatalytic_source_contracts as _sources
from dharma_swarm.a2a.a2a_server import A2ATask
from dharma_swarm.autocatalytic_adapter_evidence import (
    _consumed_feed as _consumed_feed,
    _project_evidence as _project_evidence,
)
from dharma_swarm.autocatalytic_adapters_research_promote import (
    _adapt_assurance_merge,
    _adapt_chamber_research,
    _adapt_external_value_delivery,
    _adapt_learning_promotion,
    _adapt_operator_experience,
)
from dharma_swarm.autocatalytic_adapters_sense_execute import (
    _adapt_arena_selection,
    _adapt_cybernetic_supervision,
    _adapt_dharmagraph_execution,
    _adapt_sarathi_runtime,
    _adapt_world_signal_supply,
)
from dharma_swarm.autocatalytic_contracts import (
    ADAPTER_VERSION as ADAPTER_VERSION,
    CROSS_FEED_SCHEMA,
    PROJECT_EVIDENCE_SCHEMA as PROJECT_EVIDENCE_SCHEMA,
    SIGNAL_ENVELOPE_SCHEMA as SIGNAL_ENVELOPE_SCHEMA,
    SemanticPromotionError,
    _canonical_json as _canonical_json,
    _digest,
    evaluate_promotion_gate as evaluate_promotion_gate,
)

_REPO_ROOT = _sources._REPO_ROOT
_json_object = _sources._json_object
_source_snapshot = _sources._source_snapshot

_PROJECT_ADAPTERS = {
    "world_signal_supply": _adapt_world_signal_supply,
    "sarathi_runtime": _adapt_sarathi_runtime,
    "dharmagraph_execution": _adapt_dharmagraph_execution,
    "cybernetic_supervision": _adapt_cybernetic_supervision,
    "arena_selection": _adapt_arena_selection,
    "chamber_research": _adapt_chamber_research,
    "assurance_merge": _adapt_assurance_merge,
    "operator_experience": _adapt_operator_experience,
    "external_value_delivery": _adapt_external_value_delivery,
    "learning_promotion": _adapt_learning_promotion,
}
_NODE_ORDINALS = {node_id: index for index, node_id in enumerate(_PROJECT_ADAPTERS, 1)}


def _consume_project_cross_feeds(
    *, node: Mapping[str, Any], predecessor_payload: Mapping[str, Any], turn: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Consume only ledger-bound, topology-fresh feed envelopes, once."""

    prior_bus = predecessor_payload.get("cross_feed_bus")
    if prior_bus is not None and not isinstance(prior_bus, Mapping):
        raise SemanticPromotionError("cross-feed bus must be an object")
    bus = dict(prior_bus or {})
    ledger = predecessor_payload.get("project_evidence_ledger") or []
    if not isinstance(ledger, list):
        raise SemanticPromotionError("cross-feed source evidence ledger must be a list")
    consumed: list[dict[str, Any]] = []
    envelope_keys = {
        "schema_version",
        "signal",
        "source",
        "target",
        "emitted_turn",
        "source_evidence_hash",
        "state",
        "modality",
        "promotion_authorized",
    }
    for contract in node.get("cross_inputs") or []:
        signal, source = str(contract["signal"]), str(contract["source"])
        expected_turn = (
            turn if _NODE_ORDINALS[source] < int(node["ordinal"]) else turn - 1
        )
        available = bus.get(signal)
        if available is None:
            consumed.append(
                {
                    "schema_version": CROSS_FEED_SCHEMA,
                    "signal": signal,
                    "source": source,
                    "target": str(node["id"]),
                    "status": "not_available",
                    "expected_turn": expected_turn,
                    "consumed_by": str(node["id"]),
                    "consumed_turn": turn,
                }
            )
            continue
        if not isinstance(available, Mapping) or set(available) != envelope_keys:
            raise SemanticPromotionError(f"cross-feed {signal} envelope is invalid")
        expected = {
            "schema_version": CROSS_FEED_SCHEMA,
            "signal": signal,
            "source": source,
            "target": str(node["id"]),
            "emitted_turn": expected_turn,
            "promotion_authorized": False,
        }
        if any(available.get(key) != value for key, value in expected.items()):
            raise SemanticPromotionError(
                f"cross-feed {signal} topology or turn is stale"
            )
        source_hash = available.get("source_evidence_hash")
        matches = [
            row
            for row in ledger
            if isinstance(row, Mapping)
            and row.get("evidence_hash") == source_hash
            and row.get("node_id") == source
            and _digest(
                {key: value for key, value in row.items() if key != "evidence_hash"}
            )
            == source_hash
        ]
        if len(matches) != 1:
            raise SemanticPromotionError(
                f"cross-feed {signal} source evidence is not uniquely ledger-bound"
            )
        source_signal = matches[0].get("signal")
        if (
            not isinstance(source_signal, Mapping)
            or available.get("state") != source_signal.get("state")
            or available.get("modality") != source_signal.get("modality")
            or source_signal.get("promotion_authorized") is not False
            or available.get("promotion_authorized") is not False
        ):
            raise SemanticPromotionError(
                f"cross-feed {signal} state/modality is invalid"
            )
        consumed.append(
            {
                **dict(available),
                "status": "consumed",
                "consumed_by": str(node["id"]),
                "consumed_turn": turn,
            }
        )
        bus.pop(signal)
    return bus, consumed


def _project_evidence_for(
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    task: A2ATask,
    turn: int,
    consumed_cross_feeds: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    adapter = _PROJECT_ADAPTERS.get(str(node.get("id") or ""))
    if adapter is None:
        raise SemanticPromotionError(
            f"no project adapter registered for {node.get('id')}"
        )
    payload = predecessor.get("payload")
    if not isinstance(payload, Mapping):
        raise SemanticPromotionError("predecessor project payload is invalid")
    _, expected_feeds = _consume_project_cross_feeds(
        node=node, predecessor_payload=payload, turn=turn
    )
    if consumed_cross_feeds is None:
        consumed_cross_feeds = expected_feeds
    elif list(consumed_cross_feeds) != expected_feeds:
        raise SemanticPromotionError("provided cross-feed consumption is not causal")
    evidence = adapter(node, predecessor, task, turn, consumed_cross_feeds)
    expected_hash = str(evidence.get("evidence_hash") or "")
    if not expected_hash or expected_hash != _digest(
        {key: value for key, value in evidence.items() if key != "evidence_hash"}
    ):
        raise SemanticPromotionError(
            f"project adapter evidence hash invalid for {node['id']}"
        )
    return evidence


def _project_cross_feeds(
    *,
    node: Mapping[str, Any],
    predecessor_payload: Mapping[str, Any],
    project_evidence: Mapping[str, Any],
    turn: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compose causal one-shot consumption with later feed emission."""
    bus, consumed = _consume_project_cross_feeds(
        node=node, predecessor_payload=predecessor_payload, turn=turn
    )
    signal = project_evidence.get("signal")
    if not isinstance(signal, Mapping):
        raise SemanticPromotionError("project evidence signal is invalid")
    emitted: list[dict[str, Any]] = []
    for contract in node.get("cross_outputs") or []:
        envelope = {
            "schema_version": CROSS_FEED_SCHEMA,
            "signal": str(contract["signal"]),
            "source": str(node["id"]),
            "target": str(contract["target"]),
            "emitted_turn": turn,
            "source_evidence_hash": project_evidence.get("evidence_hash"),
            "state": signal.get("state"),
            "modality": signal.get("modality"),
            "promotion_authorized": False,
        }
        bus[str(contract["signal"])] = envelope
        emitted.append(envelope)
    return bus, consumed, emitted


def _validate_project_semantics(
    *,
    artifact: Mapping[str, Any],
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    task: A2ATask,
    turn: int,
) -> None:
    """Independently recompute consume -> adapter -> emit semantics."""
    prior_payload, payload = predecessor.get("payload"), artifact.get("payload")
    if not isinstance(prior_payload, Mapping) or not isinstance(payload, Mapping):
        raise SemanticPromotionError(f"{node['id']} project payload is invalid")
    _, consumed = _consume_project_cross_feeds(
        node=node, predecessor_payload=prior_payload, turn=turn
    )
    evidence = _project_evidence_for(node, predecessor, task, turn, consumed)
    if artifact.get("project_evidence") != evidence:
        raise SemanticPromotionError(
            f"{node['id']} project evidence is not adapter-derived"
        )
    if artifact.get("signal") != evidence.get("signal"):
        raise SemanticPromotionError(f"{node['id']} signal envelope is invalid")
    bus, expected_consumed, emitted = _project_cross_feeds(
        node=node,
        predecessor_payload=prior_payload,
        project_evidence=evidence,
        turn=turn,
    )
    checks = (
        (artifact.get("consumed_cross_feeds"), expected_consumed, "consumption"),
        (artifact.get("emitted_cross_feeds"), emitted, "emission"),
        (payload.get("cross_feed_bus"), bus, "bus"),
    )
    for observed, expected, label in checks:
        if observed != expected:
            raise SemanticPromotionError(f"{node['id']} cross-feed {label} is invalid")
    ledger = [*(prior_payload.get("project_evidence_ledger") or []), evidence]
    if payload.get("project_evidence_ledger") != ledger:
        raise SemanticPromotionError(f"{node['id']} project-evidence ledger is invalid")
    if payload.get("last_signal_state") != evidence["signal"]["state"]:
        raise SemanticPromotionError(f"{node['id']} signal-state projection is invalid")
