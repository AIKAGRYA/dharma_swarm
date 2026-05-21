"""Deterministic in-memory projection for Trace Attractor Ledger packets."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from dharma_swarm.trace_attractor.models import (
    AttractorEvent,
    AttractorPacket,
    FindingSeverity,
    FourfoldWarrantSummary,
    LifecycleFinding,
    ProvenanceEdge,
    ProvenanceGraph,
    ProvenanceNode,
    ValueSummary,
    utc_now_iso,
)


_ACTION_PROPOSAL_TYPES = {"actionproposal", "action_proposals"}
_GATE_DECISION_TYPES = {"gatedecisionrecord", "gate_decision_records"}
_TASK_TYPES = {"task", "tasks"}
_CLAIM_TYPES = {"taskclaim", "task_claims"}
_DELEGATION_TYPES = {"delegationrun", "delegation_runs"}
_ARTIFACT_TYPES = {"artifactrecord", "artifact_records", "knowledgeartifact"}
_OUTCOME_TYPES = {"outcome", "outcomes"}
_VALUE_EVENT_TYPES = {"valueevent", "value_events"}
_CONTRIBUTION_TYPES = {"contribution", "contributions"}
_ECONOMIC_TYPES = {"economic_event", "economic_events", "economiceventrecord"}
_SIGNAL_STORES = {"signal_bus", "signalbus"}
_WITNESS_TYPES = {"witnesslog", "witness_logs"}
_LINEAGE_TYPES = {"lineageedge", "lineage_edges"}


def _norm(value: str) -> str:
    return value.replace("-", "_").replace(".", "_").replace(" ", "_").lower()


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _attr(event: AttractorEvent, key: str) -> str:
    return _text(event.attributes.get(key)).strip()


def _first_text(event: AttractorEvent, *keys: str) -> str:
    for key in keys:
        value = _attr(event, key)
        if value:
            return value
    return ""


def _add(target: set[str], value: Any) -> None:
    text = _text(value).strip()
    if text:
        target.add(text)


def _float_attr(event: AttractorEvent, key: str) -> float:
    raw = event.attributes.get(key)
    if raw is None or raw == "":
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _sorted(values: set[str]) -> list[str]:
    return sorted(values)


def _node_kind(source_type: str) -> str:
    normalized = _norm(source_type)
    if normalized in _ACTION_PROPOSAL_TYPES | _GATE_DECISION_TYPES:
        return "prov:Activity"
    if normalized in _TASK_TYPES | _DELEGATION_TYPES:
        return "prov:Activity"
    if normalized in _CONTRIBUTION_TYPES:
        return "prov:Entity"
    if normalized in _SIGNAL_STORES:
        return "prov:Activity"
    return "prov:Entity"


class TraceAttractorProjector:
    """Build deterministic trace packets from normalized events.

    This projector is intentionally pure: callers provide already-normalized
    events, and no database, SignalBus, filesystem, or ontology registry is
    touched here.
    """

    def build_packet(
        self,
        trace_id: str,
        events: Iterable[AttractorEvent | dict[str, Any]],
        *,
        generated_at: str | None = None,
    ) -> AttractorPacket:
        normalized = [
            event
            if isinstance(event, AttractorEvent)
            else AttractorEvent.model_validate(event)
            for event in events
        ]
        trace_events = sorted(
            (event for event in normalized if event.trace_id == trace_id),
            key=lambda event: (event.occurred_at, event.event_id),
        )

        session_ids: set[str] = set()
        proposal_ids: set[str] = set()
        gate_decision_ids: set[str] = set()
        task_ids: set[str] = set()
        claim_ids: set[str] = set()
        delegation_run_ids: set[str] = set()
        artifact_ids: set[str] = set()
        outcome_ids: set[str] = set()
        value_event_ids: set[str] = set()
        contribution_ids: set[str] = set()
        economic_event_ids: set[str] = set()
        signal_event_ids: set[str] = set()
        witness_log_ids: set[str] = set()
        lineage_edge_ids: set[str] = set()
        agent_ids: set[str] = set()
        currencies: set[str] = set()
        findings: list[LifecycleFinding] = []
        nodes: dict[str, ProvenanceNode] = {}
        edges: dict[tuple[str, str, str, str], ProvenanceEdge] = {}
        warrant = FourfoldWarrantSummary()

        composite_value = 0.0
        economic_amount = 0.0
        counted_value_events: set[str] = set()
        counted_economic_events: set[str] = set()

        for event in trace_events:
            source_type = _norm(event.source_table_or_type)
            event_type = _norm(event.event_type)
            primary_id = event.primary_object_id

            _add(session_ids, event.session_id)
            _add(session_ids, _attr(event, "session_id"))
            _add(proposal_ids, event.proposal_id)
            _add(proposal_ids, _attr(event, "proposal_id"))
            _add(
                agent_ids,
                _first_text(event, "agent_id", "created_by", "attributed_to"),
            )

            if event.source_store and _norm(event.source_store) in _SIGNAL_STORES:
                _add(signal_event_ids, event.event_id)

            if source_type in _ACTION_PROPOSAL_TYPES:
                _add(proposal_ids, primary_id)
            if source_type in _GATE_DECISION_TYPES:
                _add(
                    gate_decision_ids,
                    _first_text(event, "gate_decision_id", "decision_id")
                    or primary_id,
                )
            if source_type in _TASK_TYPES:
                _add(task_ids, _first_text(event, "task_id") or primary_id)
            if source_type in _CLAIM_TYPES:
                _add(claim_ids, _first_text(event, "claim_id") or primary_id)
            if source_type in _DELEGATION_TYPES:
                _add(
                    delegation_run_ids,
                    _first_text(event, "run_id", "delegation_run_id")
                    or primary_id,
                )
            if source_type in _ARTIFACT_TYPES:
                _add(
                    artifact_ids,
                    _first_text(event, "artifact_id", "knowledge_artifact_id")
                    or primary_id,
                )
            if source_type in _OUTCOME_TYPES or "outcome_recorded" in event_type:
                _add(outcome_ids, _first_text(event, "outcome_id") or primary_id)
            if source_type in _VALUE_EVENT_TYPES or "value_event_recorded" in event_type:
                _add(value_event_ids, _first_text(event, "value_event_id") or primary_id)
            if source_type in _CONTRIBUTION_TYPES:
                _add(contribution_ids, _first_text(event, "contribution_id") or primary_id)
            if source_type in _ECONOMIC_TYPES:
                _add(
                    economic_event_ids,
                    _first_text(event, "economic_event_id", "event_id")
                    or primary_id,
                )
            if source_type in _WITNESS_TYPES:
                _add(witness_log_ids, _first_text(event, "witness_log_id") or primary_id)
            if source_type in _LINEAGE_TYPES:
                _add(
                    lineage_edge_ids,
                    _first_text(event, "lineage_edge_id", "edge_id")
                    or primary_id,
                )

            self._collect_attribute_ids(
                event,
                task_ids=task_ids,
                claim_ids=claim_ids,
                delegation_run_ids=delegation_run_ids,
                artifact_ids=artifact_ids,
                outcome_ids=outcome_ids,
                value_event_ids=value_event_ids,
                contribution_ids=contribution_ids,
                economic_event_ids=economic_event_ids,
                witness_log_ids=witness_log_ids,
                lineage_edge_ids=lineage_edge_ids,
            )

            is_value_event_source = (
                source_type in _VALUE_EVENT_TYPES
                or "value_event_recorded" in event_type
            )
            value_event_id = (
                _first_text(event, "value_event_id")
                or (primary_id if is_value_event_source else "")
            )
            if is_value_event_source and value_event_id not in counted_value_events:
                composite_value += _float_attr(event, "composite_value")
                if value_event_id:
                    counted_value_events.add(value_event_id)

            if source_type in _ECONOMIC_TYPES and primary_id not in counted_economic_events:
                economic_amount += _float_attr(event, "amount")
                counted_economic_events.add(primary_id)
                currency = _first_text(event, "currency")
                if currency:
                    currencies.add(currency)

            warrant = self._merge_warrant(warrant, event)
            self._add_graph_nodes_and_edges(event, nodes, edges)
            findings.extend(self._find_event_issues(event))

        if not warrant.has_evidence:
            findings.append(LifecycleFinding(
                code="warrant_unknown",
                severity=FindingSeverity.INFO,
                message="No Fourfold Action Warrant evidence was present in projected events.",
            ))

        packet = AttractorPacket(
            trace_id=trace_id,
            generated_at=generated_at or utc_now_iso(),
            session_ids=_sorted(session_ids),
            proposal_ids=_sorted(proposal_ids),
            gate_decision_ids=_sorted(gate_decision_ids),
            task_ids=_sorted(task_ids),
            claim_ids=_sorted(claim_ids),
            delegation_run_ids=_sorted(delegation_run_ids),
            artifact_ids=_sorted(artifact_ids),
            outcome_ids=_sorted(outcome_ids),
            value_event_ids=_sorted(value_event_ids),
            contribution_ids=_sorted(contribution_ids),
            economic_event_ids=_sorted(economic_event_ids),
            signal_event_ids=_sorted(signal_event_ids),
            witness_log_ids=_sorted(witness_log_ids),
            lineage_edge_ids=_sorted(lineage_edge_ids),
            fourfold_warrant=warrant,
            value_summary=ValueSummary(
                composite_value=round(composite_value, 6),
                economic_amount=round(economic_amount, 6),
                currency=self._currency(currencies),
                agent_count=len(agent_ids),
                artifact_count=len(artifact_ids),
                task_count=len(task_ids),
            ),
            lifecycle_findings=sorted(
                findings,
                key=lambda finding: (
                    finding.severity,
                    finding.code,
                    finding.source_event_id,
                    finding.source_object_id,
                ),
            ),
            provenance_graph=ProvenanceGraph(
                nodes=sorted(nodes.values(), key=lambda node: node.id),
                edges=sorted(
                    edges.values(),
                    key=lambda edge: (
                        edge.source,
                        edge.target,
                        edge.relation,
                        edge.source_event_id,
                    ),
                ),
            ),
        )
        return packet

    def _collect_attribute_ids(
        self,
        event: AttractorEvent,
        *,
        task_ids: set[str],
        claim_ids: set[str],
        delegation_run_ids: set[str],
        artifact_ids: set[str],
        outcome_ids: set[str],
        value_event_ids: set[str],
        contribution_ids: set[str],
        economic_event_ids: set[str],
        witness_log_ids: set[str],
        lineage_edge_ids: set[str],
    ) -> None:
        _add(task_ids, _attr(event, "task_id"))
        _add(claim_ids, _attr(event, "claim_id"))
        _add(delegation_run_ids, _first_text(event, "run_id", "delegation_run_id"))
        _add(artifact_ids, _first_text(event, "artifact_id", "knowledge_artifact_id"))
        _add(outcome_ids, _attr(event, "outcome_id"))
        _add(value_event_ids, _attr(event, "value_event_id"))
        _add(contribution_ids, _attr(event, "contribution_id"))
        _add(economic_event_ids, _first_text(event, "economic_event_id"))
        _add(witness_log_ids, _first_text(event, "witness_log_id"))
        _add(lineage_edge_ids, _first_text(event, "lineage_edge_id", "edge_id"))

    def _merge_warrant(
        self,
        current: FourfoldWarrantSummary,
        event: AttractorEvent,
    ) -> FourfoldWarrantSummary:
        raw = event.attributes.get("fourfold_warrant")
        data: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
        for key in (
            "status",
            "maheshwari",
            "mahakali",
            "mahalakshmi",
            "mahasaraswati",
        ):
            if key in event.attributes:
                data[key] = event.attributes[key]
        if not data:
            return current

        payload = current.model_dump(mode="json")
        evidence_refs = set(payload.get("evidence_refs", []))
        evidence_refs.add(event.event_id)
        for key, value in data.items():
            if key == "evidence_refs" and isinstance(value, list):
                evidence_refs.update(
                    _text(item) for item in value if _text(item).strip()
                )
            elif key in payload and _text(value).strip():
                payload[key] = _text(value).strip()
        payload["evidence_refs"] = sorted(evidence_refs)
        try:
            return FourfoldWarrantSummary.model_validate(payload)
        except Exception:
            return current

    def _add_graph_nodes_and_edges(
        self,
        event: AttractorEvent,
        nodes: dict[str, ProvenanceNode],
        edges: dict[tuple[str, str, str, str], ProvenanceEdge],
    ) -> None:
        primary_id = event.primary_object_id
        if primary_id:
            nodes.setdefault(
                primary_id,
                ProvenanceNode(
                    id=primary_id,
                    label=event.source_table_or_type,
                    kind=_node_kind(event.source_table_or_type),
                    source_event_id=event.event_id,
                    attributes={
                        "source_store": event.source_store,
                        "source_table_or_type": event.source_table_or_type,
                    },
                ),
            )

        self._edge_from_attr(event, nodes, edges, primary_id, "proposal_id", "prov:used")
        self._edge_from_attr(
            event, nodes, edges, primary_id, "task_id", "prov:wasGeneratedBy"
        )
        self._edge_from_attr(
            event, nodes, edges, primary_id, "outcome_id", "prov:wasDerivedFrom"
        )
        self._edge_from_attr(
            event, nodes, edges, primary_id, "value_event_id", "prov:wasDerivedFrom"
        )
        self._edge_from_attr(
            event,
            nodes,
            edges,
            primary_id,
            "parent_artifact_id",
            "prov:wasDerivedFrom",
        )
        self._edge_from_attr(
            event, nodes, edges, primary_id, "agent_id", "prov:wasAttributedTo"
        )

    def _edge_from_attr(
        self,
        event: AttractorEvent,
        nodes: dict[str, ProvenanceNode],
        edges: dict[tuple[str, str, str, str], ProvenanceEdge],
        source: str,
        attr_name: str,
        relation: str,
    ) -> None:
        target = _attr(event, attr_name)
        if not source or not target or source == target:
            return
        nodes.setdefault(
            target,
            ProvenanceNode(id=target, label=attr_name, kind="prov:Entity"),
        )
        key = (source, target, relation, event.event_id)
        edges.setdefault(
            key,
            ProvenanceEdge(
                source=source,
                target=target,
                relation=relation,
                source_event_id=event.event_id,
            ),
        )

    def _find_event_issues(self, event: AttractorEvent) -> list[LifecycleFinding]:
        findings: list[LifecycleFinding] = []
        source_type = _norm(event.source_table_or_type)
        event_type = _norm(event.event_type)
        primary_id = event.primary_object_id

        if not event.trace_id:
            findings.append(LifecycleFinding(
                code="missing_trace_id",
                severity=FindingSeverity.DEGRADED,
                message="Projected event does not carry trace_id.",
                source_event_id=event.event_id,
                source_object_id=primary_id,
            ))

        if source_type in _OUTCOME_TYPES or "outcome_recorded" in event_type:
            if not (event.proposal_id or _attr(event, "proposal_id")):
                findings.append(LifecycleFinding(
                    code="orphan_outcome",
                    severity=FindingSeverity.DEGRADED,
                    message="Outcome event lacks a proposal link.",
                    source_event_id=event.event_id,
                    source_object_id=primary_id,
                ))

        if source_type in _VALUE_EVENT_TYPES or "value_event_recorded" in event_type:
            if not _attr(event, "outcome_id"):
                findings.append(LifecycleFinding(
                    code="orphan_value_event",
                    severity=FindingSeverity.DEGRADED,
                    message="ValueEvent event lacks an outcome link.",
                    source_event_id=event.event_id,
                    source_object_id=primary_id,
                ))

        if source_type in {"artifactrecord", "artifact_records"}:
            has_manifest = any(
                _attr(event, key)
                for key in ("manifest_path", "payload_path", "checksum")
            )
            if not has_manifest:
                findings.append(LifecycleFinding(
                    code="artifact_without_manifest",
                    severity=FindingSeverity.DEGRADED,
                    message=(
                        "Artifact record lacks manifest, payload path, "
                        "and checksum evidence."
                    ),
                    source_event_id=event.event_id,
                    source_object_id=primary_id,
                ))

        if source_type in _ECONOMIC_TYPES:
            if not (_attr(event, "value_event_id") or _attr(event, "outcome_id")):
                findings.append(LifecycleFinding(
                    code="economic_without_value_event",
                    severity=FindingSeverity.BLOCKER,
                    message="Economic event cannot be tied to a value event or outcome.",
                    source_event_id=event.event_id,
                    source_object_id=primary_id,
                ))

        return findings

    def _currency(self, currencies: set[str]) -> str:
        if not currencies:
            return "USD"
        if len(currencies) == 1:
            return next(iter(currencies))
        return "MIXED"
