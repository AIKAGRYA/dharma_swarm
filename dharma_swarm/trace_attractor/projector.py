"""Trace Attractor Projector — assembles an AttractorPacket from stores.

Pure read/projection code. Reads from:
  - OntologyRegistry (proposals, gates, outcomes, value events, contributions)
  - RuntimeStateStore (task claims, delegation runs, artifacts)
  - TelemetryPlaneStore (economic events)
  - LineageGraph (lineage edges)

Never writes to any store. The packet can always be deleted and rebuilt.
"""

from __future__ import annotations

import logging
from typing import Any

from dharma_swarm.trace_attractor.models import (
    AttractorEvent,
    AttractorPacket,
    FourfoldWarrantSummary,
    LifecycleFinding,
    ProvenanceEdge,
    ProvenanceNode,
    ValueSummary,
)

logger = logging.getLogger(__name__)


class TraceAttractorProjector:
    """Assembles an AttractorPacket for a given trace_id."""

    def __init__(
        self,
        *,
        ontology: Any | None = None,
        runtime_state: Any | None = None,
        telemetry_plane: Any | None = None,
        lineage_graph: Any | None = None,
    ) -> None:
        self._ontology = ontology
        self._runtime = runtime_state
        self._telemetry = telemetry_plane
        self._lineage = lineage_graph

    async def project(self, trace_id: str) -> AttractorPacket:
        """Build a complete AttractorPacket for the given trace_id."""
        packet = AttractorPacket(trace_id=trace_id)

        # Read from each store independently
        await self._read_ontology(packet)
        await self._read_runtime(packet)
        await self._read_telemetry(packet)
        self._read_lineage(packet)

        # Compute summaries
        self._compute_value_summary(packet)
        self._compute_fourfold_warrant(packet)
        self._detect_lifecycle_findings(packet)
        self._build_provenance_graph(packet)

        return packet

    # ── Ontology reader ──────────────────────────────────────────

    async def _read_ontology(self, packet: AttractorPacket) -> None:
        if self._ontology is None:
            return
        reg = self._ontology

        for type_name, id_list, event_type in [
            ("ActionProposal", packet.proposal_ids, "proposal"),
            ("GateDecision", packet.gate_decision_ids, "gate_decision"),
            ("Outcome", packet.outcome_ids, "outcome"),
            ("ValueEvent", packet.value_event_ids, "value_event"),
            ("Contribution", packet.contribution_ids, "contribution"),
            ("WitnessLog", packet.witness_log_ids, "witness_log"),
        ]:
            try:
                objects = reg.get_objects_by_type(type_name)
            except Exception:
                logger.debug("Failed to read %s from ontology", type_name)
                continue
            for obj in objects:
                obj_trace = obj.properties.get("trace_id", "")
                meta = obj.properties.get("metadata", {})
                if isinstance(meta, dict):
                    obj_trace = obj_trace or meta.get("trace_id", "")
                if obj_trace != packet.trace_id:
                    continue
                id_list.append(obj.id)
                packet.events.append(
                    AttractorEvent(
                        event_id=obj.id,
                        trace_id=packet.trace_id,
                        proposal_id=obj.properties.get("proposal_id", ""),
                        session_id=obj.properties.get("session_id", ""),
                        source_store="ontology",
                        source_table_or_type=type_name,
                        source_object_id=obj.id,
                        event_type=event_type,
                        subject=obj.properties.get("task_id", obj.id),
                        occurred_at=obj.created_at.isoformat()
                        if hasattr(obj.created_at, "isoformat")
                        else str(obj.created_at),
                        attributes=dict(obj.properties),
                    )
                )

    # ── Runtime state reader ─────────────────────────────────────

    async def _read_runtime(self, packet: AttractorPacket) -> None:
        if self._runtime is None:
            return
        rs = self._runtime

        # Task claims by trace_id
        try:
            await rs.init_db()
            import aiosqlite

            async with aiosqlite.connect(rs.db_path) as db:
                db.row_factory = aiosqlite.Row
                rows = await (
                    await db.execute(
                        "SELECT claim_id, task_id, session_id FROM task_claims"
                        " WHERE trace_id = ? ORDER BY claimed_at DESC LIMIT 500",
                        (packet.trace_id,),
                    )
                ).fetchall()
            for row in rows:
                claim_id = row["claim_id"]
                packet.claim_ids.append(claim_id)
                task_id = row["task_id"]
                if task_id and task_id not in packet.task_ids:
                    packet.task_ids.append(task_id)
                packet.events.append(
                    AttractorEvent(
                        event_id=claim_id,
                        trace_id=packet.trace_id,
                        session_id=row["session_id"],
                        source_store="runtime_state",
                        source_table_or_type="task_claims",
                        source_object_id=claim_id,
                        event_type="task_claim",
                        subject=task_id,
                    )
                )
        except Exception:
            logger.debug("Failed to read task_claims by trace_id")

        # Delegation runs by trace_id
        try:
            import aiosqlite

            async with aiosqlite.connect(rs.db_path) as db:
                db.row_factory = aiosqlite.Row
                rows = await (
                    await db.execute(
                        "SELECT run_id, session_id, task_id FROM delegation_runs"
                        " WHERE trace_id = ? ORDER BY started_at DESC LIMIT 500",
                        (packet.trace_id,),
                    )
                ).fetchall()
            for row in rows:
                run_id = row["run_id"]
                packet.delegation_run_ids.append(run_id)
                packet.events.append(
                    AttractorEvent(
                        event_id=run_id,
                        trace_id=packet.trace_id,
                        session_id=row["session_id"],
                        source_store="runtime_state",
                        source_table_or_type="delegation_runs",
                        source_object_id=run_id,
                        event_type="delegation_run",
                        subject=row["task_id"],
                    )
                )
        except Exception:
            logger.debug("Failed to read delegation_runs by trace_id")

        # Artifacts — check metadata_json for trace_id
        try:
            artifacts = await rs.list_artifacts(limit=500)
            for art in artifacts:
                meta = {}
                if hasattr(art, "metadata_json") and art.metadata_json:
                    import json as _json

                    try:
                        meta = _json.loads(art.metadata_json)
                    except (ValueError, TypeError):
                        meta = {}
                art_trace = meta.get("trace_id", "")
                if art_trace == packet.trace_id:
                    packet.artifact_ids.append(art.artifact_id)
        except Exception:
            logger.debug("Failed to read artifacts by trace_id")

    # ── Telemetry reader ─────────────────────────────────────────

    async def _read_telemetry(self, packet: AttractorPacket) -> None:
        if self._telemetry is None:
            return
        tp = self._telemetry

        try:
            await tp.init_db()
            import aiosqlite

            async with tp._open() as db:
                db.row_factory = aiosqlite.Row
                rows = await (
                    await db.execute(
                        "SELECT event_id, session_id, task_id, amount, currency"
                        " FROM economic_events WHERE trace_id = ?"
                        " ORDER BY created_at DESC LIMIT 500",
                        (packet.trace_id,),
                    )
                ).fetchall()
            for row in rows:
                packet.economic_event_ids.append(row["event_id"])
                packet.events.append(
                    AttractorEvent(
                        event_id=row["event_id"],
                        trace_id=packet.trace_id,
                        session_id=row["session_id"],
                        source_store="telemetry_plane",
                        source_table_or_type="economic_events",
                        source_object_id=row["event_id"],
                        event_type="economic_event",
                        subject=row["task_id"],
                        attributes={
                            "amount": row["amount"],
                            "currency": row["currency"],
                        },
                    )
                )
        except Exception:
            logger.debug("Failed to read economic_events by trace_id")

    # ── Lineage reader ───────────────────────────────────────────

    def _read_lineage(self, packet: AttractorPacket) -> None:
        if self._lineage is None:
            return
        lg = self._lineage

        try:
            all_edges = lg._edges if hasattr(lg, "_edges") else []
            for edge in all_edges:
                if getattr(edge, "trace_id", "") == packet.trace_id:
                    packet.lineage_edge_ids.append(edge.edge_id)
                    packet.events.append(
                        AttractorEvent(
                            event_id=edge.edge_id,
                            trace_id=packet.trace_id,
                            source_store="lineage",
                            source_table_or_type="lineage_edges",
                            source_object_id=edge.edge_id,
                            event_type="lineage_edge",
                            subject=edge.task_id,
                            occurred_at=edge.timestamp,
                            attributes={
                                "agent": edge.agent,
                                "delegated_by": edge.delegated_by,
                                "operation": edge.operation,
                                "input_artifacts": edge.input_artifacts,
                                "output_artifacts": edge.output_artifacts,
                            },
                        )
                    )
        except Exception:
            logger.debug("Failed to read lineage edges by trace_id")

    # ── Value summary ────────────────────────────────────────────

    def _compute_value_summary(self, packet: AttractorPacket) -> None:
        total_amount = 0.0
        currency = "USD"
        agents: set[str] = set()

        for ev in packet.events:
            if ev.event_type == "economic_event":
                total_amount += ev.attributes.get("amount", 0.0)
                currency = ev.attributes.get("currency", currency)
            if ev.event_type == "lineage_edge":
                agent = ev.attributes.get("agent", "")
                if agent:
                    agents.add(agent)
            if ev.event_type == "contribution":
                agent = ev.attributes.get("agent_id", "")
                if agent:
                    agents.add(agent)

        packet.value_summary = ValueSummary(
            composite_value=total_amount,
            economic_amount=total_amount,
            currency=currency,
            agent_count=len(agents),
            artifact_count=len(packet.artifact_ids),
            task_count=len(packet.task_ids),
        )

    # ── Fourfold warrant ─────────────────────────────────────────

    def _compute_fourfold_warrant(self, packet: AttractorPacket) -> None:
        gate_events = [
            e for e in packet.events if e.event_type == "gate_decision"
        ]
        if not gate_events:
            packet.fourfold_warrant = FourfoldWarrantSummary(status="unknown")
            return

        dims: dict[str, str] = {}
        refs: list[str] = []
        for ge in gate_events:
            gate_name = ge.attributes.get("gate_name", "")
            decision = ge.attributes.get("decision", "unknown")
            refs.append(ge.event_id)
            name_lower = gate_name.lower()
            for dim in ("maheshwari", "mahakali", "mahalakshmi", "mahasaraswati"):
                if dim in name_lower:
                    dims[dim] = decision

        statuses = list(dims.values()) if dims else ["unknown"]
        overall = "pass"
        if "block" in statuses:
            overall = "block"
        elif "hold" in statuses:
            overall = "hold"
        elif all(s == "unknown" for s in statuses):
            overall = "unknown"

        packet.fourfold_warrant = FourfoldWarrantSummary(
            status=overall,
            maheshwari=dims.get("maheshwari", "unknown"),
            mahakali=dims.get("mahakali", "unknown"),
            mahalakshmi=dims.get("mahalakshmi", "unknown"),
            mahasaraswati=dims.get("mahasaraswati", "unknown"),
            evidence_refs=refs,
        )

    # ── Lifecycle findings ───────────────────────────────────────

    def _detect_lifecycle_findings(self, packet: AttractorPacket) -> None:
        findings: list[LifecycleFinding] = []

        # orphan_outcome: outcome without a proposal
        for ev in packet.events:
            if ev.event_type == "outcome" and not ev.proposal_id:
                findings.append(
                    LifecycleFinding(
                        finding_type="orphan_outcome",
                        severity="DEGRADED",
                        detail="Outcome lacks proposal_id link",
                        source_object_id=ev.event_id,
                    )
                )

        # orphan_value_event: value_event without an outcome link
        outcome_set = {e.event_id for e in packet.events if e.event_type == "outcome"}
        for ev in packet.events:
            if ev.event_type == "value_event":
                linked_outcome = ev.attributes.get("outcome_id", "")
                if linked_outcome and linked_outcome not in outcome_set:
                    findings.append(
                        LifecycleFinding(
                            finding_type="orphan_value_event",
                            severity="DEGRADED",
                            detail=f"ValueEvent references outcome {linked_outcome} not in this trace",
                            source_object_id=ev.event_id,
                        )
                    )

        # economic_without_value_event
        if packet.economic_event_ids and not packet.value_event_ids:
            findings.append(
                LifecycleFinding(
                    finding_type="economic_without_value_event",
                    severity="DEGRADED",
                    detail="Economic events exist but no value events in trace",
                )
            )

        # missing_trace_id on primary-path events with empty trace_id
        for ev in packet.events:
            if not ev.trace_id:
                findings.append(
                    LifecycleFinding(
                        finding_type="missing_trace_id",
                        severity="DEGRADED",
                        detail=f"{ev.source_store}/{ev.source_table_or_type} row lacks trace_id",
                        source_object_id=ev.event_id,
                    )
                )

        # warrant_unknown
        if packet.fourfold_warrant.status == "unknown":
            findings.append(
                LifecycleFinding(
                    finding_type="warrant_unknown",
                    severity="INFO",
                    detail="No fourfold warrant evidence derivable from gate decisions",
                )
            )

        packet.lifecycle_findings = findings

    # ── Provenance graph ─────────────────────────────────────────

    def _build_provenance_graph(self, packet: AttractorPacket) -> None:
        nodes: list[dict[str, str]] = []
        edges: list[dict[str, str]] = []
        seen_nodes: set[str] = set()

        def _add_node(nid: str, ntype: str, label: str, store: str) -> None:
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({
                    "node_id": nid,
                    "node_type": ntype,
                    "label": label,
                    "source_store": store,
                })

        for ev in packet.events:
            if ev.event_type == "proposal":
                _add_node(ev.event_id, "activity", "proposal", "ontology")
            elif ev.event_type == "outcome":
                _add_node(ev.event_id, "entity", "outcome", "ontology")
                if ev.proposal_id:
                    edges.append({
                        "source_id": ev.event_id,
                        "target_id": ev.proposal_id,
                        "relation": "wasGeneratedBy",
                    })
            elif ev.event_type == "value_event":
                _add_node(ev.event_id, "entity", "value_event", "ontology")
                outcome_id = ev.attributes.get("outcome_id", "")
                if outcome_id:
                    edges.append({
                        "source_id": ev.event_id,
                        "target_id": outcome_id,
                        "relation": "wasDerivedFrom",
                    })
            elif ev.event_type == "contribution":
                _add_node(ev.event_id, "entity", "contribution", "ontology")
                agent_id = ev.attributes.get("agent_id", "")
                if agent_id:
                    _add_node(agent_id, "agent", agent_id, "ontology")
                    edges.append({
                        "source_id": ev.event_id,
                        "target_id": agent_id,
                        "relation": "wasAttributedTo",
                    })
            elif ev.event_type == "lineage_edge":
                for out_art in ev.attributes.get("output_artifacts", []):
                    _add_node(out_art, "entity", out_art, "lineage")
                    edges.append({
                        "source_id": out_art,
                        "target_id": ev.event_id,
                        "relation": "wasGeneratedBy",
                    })
                for in_art in ev.attributes.get("input_artifacts", []):
                    _add_node(in_art, "entity", in_art, "lineage")
                    edges.append({
                        "source_id": ev.event_id,
                        "target_id": in_art,
                        "relation": "used",
                    })

        packet.provenance_graph = {"nodes": nodes, "edges": edges}
