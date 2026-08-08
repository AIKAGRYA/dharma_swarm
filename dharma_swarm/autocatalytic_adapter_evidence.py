"""Shared evidence construction for project-specific autocatalytic adapters."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from dharma_swarm.autocatalytic_contracts import (
    ADAPTER_VERSION,
    PROJECT_EVIDENCE_SCHEMA,
    SIGNAL_ENVELOPE_SCHEMA,
    SemanticPromotionError,
    _canonical_json,
    _digest,
    evaluate_promotion_gate,
)


def _project_evidence(
    *,
    node: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    adapter_id: str,
    sources: Sequence[Mapping[str, Any]],
    output_state: str,
    modality: str,
    blockers: Sequence[str],
    details: Mapping[str, Any],
    consumed_cross_feeds: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build a typed, non-self-promoting project-evidence value."""

    invalid_sources = [
        str(source.get("path") or "unknown")
        for source in sources
        if source.get("valid") is not True
    ]
    if invalid_sources:
        raise SemanticPromotionError(
            "project source contract is invalid: " + ", ".join(invalid_sources)
        )

    cross_feed_inputs: dict[str, Any] = {}
    unavailable: list[str] = []
    for feed in consumed_cross_feeds:
        signal = str(feed.get("signal") or "")
        if feed.get("status") == "consumed":
            cross_feed_inputs[signal] = {
                key: feed.get(key)
                for key in (
                    "source_evidence_hash",
                    "state",
                    "modality",
                    "emitted_turn",
                )
            }
        else:
            cross_feed_inputs[signal] = {
                "status": "not_available",
                "source": feed.get("source"),
                "expected_turn": feed.get("expected_turn"),
            }
            unavailable.append(f"cross_feed_{signal}_unavailable")
    bound_details = dict(details)
    bound_details["cross_feed_inputs"] = cross_feed_inputs
    promotion_gate = evaluate_promotion_gate(str(node["id"]), bound_details)

    input_signal = predecessor.get("signal")
    input_state = (
        input_signal.get("state")
        if isinstance(input_signal, Mapping)
        else "bootstrap_fixture"
    )
    evidence: dict[str, Any] = {
        "schema_version": PROJECT_EVIDENCE_SCHEMA,
        "adapter_version": ADAPTER_VERSION,
        "adapter_id": adapter_id,
        "node_id": str(node["id"]),
        "project_bindings": list(node.get("project_bindings") or []),
        "authority": str(node["authority"]),
        "claim_ceiling": "local_rehearsal",
        "execution_mode": "read_only_project_adapter",
        "side_effects_performed": False,
        "external_effects_proven": False,
        "project_source_causally_linked_to_input": False,
        "input_ref": {
            "artifact_hash": predecessor.get("artifact_hash"),
            "message_id": predecessor.get("message_id"),
            "signal_type": predecessor.get("output_signal"),
            "signal_state": input_state,
        },
        "sources": [dict(source) for source in sources],
        "signal": {
            "schema_version": SIGNAL_ENVELOPE_SCHEMA,
            "type": str(node["output_signal"]),
            "state": output_state,
            "modality": modality,
            "promotion_authorized": False,
            "external_effects_proven": False,
            "blockers": [*blockers, *unavailable],
        },
        "promotion_gate": promotion_gate,
        "details": bound_details,
    }
    normalized = json.loads(_canonical_json(evidence))
    normalized["evidence_hash"] = _digest(normalized)
    return normalized


def _consumed_feed(
    feeds: Sequence[Mapping[str, Any]], signal: str
) -> Mapping[str, Any] | None:
    return next(
        (
            row
            for row in feeds
            if row.get("signal") == signal and row.get("status") == "consumed"
        ),
        None,
    )
