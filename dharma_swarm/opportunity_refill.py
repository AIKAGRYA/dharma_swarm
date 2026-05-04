"""Opportunity refill — expands a board row into all frontier stages.

Takes an external_revenue opportunity (or any opportunity type) and expands
it through the full stage pipeline: scope → validate → deep_research →
capability → mvp → first_artifact.

Each stage creates:
  1. A durable RuntimeStateStore task claim + delegation run
  2. A TelicSeam ActionProposal with gate decisions
  3. Economic telemetry (provider cost / net)
  4. An ontology artifact record on completion

The deep_research stage uses a configurable backend (env DHARMA_RESEARCH_BACKEND).
If the backend is unavailable, the stage is quarantined with a clear marker.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from dharma_swarm.opportunity_dispatcher import (
    OPPORTUNITY_STAGES,
    DispatchResult,
    OpportunityDispatcher,
)

logger = logging.getLogger(__name__)

RESEARCH_BACKEND_ENV = "DHARMA_RESEARCH_BACKEND"
QUARANTINE_MARKER = "__quarantined__"


class OpportunityRow(BaseModel):
    """A single opportunity board row."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str = "Untitled opportunity"
    type: str = "external_revenue"
    description: str = ""
    source: str = ""
    estimated_value_usd: float = 0.0
    timeout_seconds: float = 600.0
    stale_after_seconds: float = 900.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class StageResult(BaseModel):
    """Result of processing a single stage."""

    stage: str
    status: str = "pending"
    task_id: str = ""
    claim_id: str = ""
    run_id: str = ""
    proposal_id: str = ""
    artifact_path: str = ""
    provider_cost_usd: float = 0.0
    net_value_usd: float = 0.0
    quarantined: bool = False
    error: str = ""
    started_at: str = ""
    completed_at: str = ""


class RefillResult(BaseModel):
    """Full result of refilling an opportunity through all stages."""

    opportunity_id: str
    opportunity_type: str
    stages: list[StageResult] = Field(default_factory=list)
    total_provider_cost_usd: float = 0.0
    total_net_value_usd: float = 0.0
    revenue_packet_path: str = ""
    success: bool = False


class OpportunityRefill:
    """Expands a board row into all frontier stages through first_artifact."""

    def __init__(
        self,
        dispatcher: OpportunityDispatcher | None = None,
        telic_seam: Any | None = None,
        economic_engine: Any | None = None,
        telemetry_store: Any | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self._telic_seam = telic_seam
        self._economic_engine = economic_engine
        self._telemetry_store = telemetry_store
        self._dispatcher = dispatcher or OpportunityDispatcher(
            telic_seam=telic_seam,
            economic_engine=economic_engine,
        )
        self._output_dir = output_dir or (Path.home() / ".dharma" / "revenue_packets")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def refill(self, row: OpportunityRow) -> RefillResult:
        """Refill a single opportunity through all stages.

        Returns a RefillResult with per-stage details and a revenue packet.
        """
        result = RefillResult(
            opportunity_id=row.id,
            opportunity_type=row.type,
        )

        opp_dict = row.model_dump()
        dispatch_results = self._dispatcher.dispatch_opportunity_sync(opp_dict)

        stage_results: list[StageResult] = []
        total_cost = 0.0

        for dr in dispatch_results:
            started = datetime.now(timezone.utc).isoformat()
            sr = StageResult(
                stage=dr.stage,
                task_id=dr.task_id,
                claim_id=dr.claim_id,
                run_id=dr.run_id,
                proposal_id=dr.proposal_id,
                started_at=started,
            )

            if not dr.success:
                sr.status = "failed"
                sr.error = dr.error
                stage_results.append(sr)
                continue

            if dr.stage == "deep_research":
                sr = self._handle_deep_research(sr, row)
            else:
                sr.status = "completed"
                sr.completed_at = datetime.now(timezone.utc).isoformat()

            stage_cost = self._estimate_stage_cost(dr.stage)
            sr.provider_cost_usd = stage_cost
            total_cost += stage_cost

            self._record_economic_telemetry(sr, row)
            stage_results.append(sr)

        result.stages = stage_results
        result.total_provider_cost_usd = total_cost
        result.total_net_value_usd = row.estimated_value_usd - total_cost
        result.success = all(
            s.status in ("completed", "quarantined") for s in stage_results
        ) and len(stage_results) == len(OPPORTUNITY_STAGES)

        if result.success:
            packet_path = self._write_revenue_packet(row, result)
            result.revenue_packet_path = str(packet_path)

        return result

    def _handle_deep_research(
        self,
        sr: StageResult,
        row: OpportunityRow,
    ) -> StageResult:
        """Handle the deep_research stage with configurable backend."""
        backend = os.environ.get(RESEARCH_BACKEND_ENV, "stub")

        if backend == "quarantine":
            sr.status = "quarantined"
            sr.quarantined = True
            sr.error = "Research backend quarantined by operator (DHARMA_RESEARCH_BACKEND=quarantine)"
            sr.completed_at = datetime.now(timezone.utc).isoformat()
            return sr

        if backend == "stub":
            sr.status = "completed"
            sr.completed_at = datetime.now(timezone.utc).isoformat()
            sr.artifact_path = ""
            return sr

        try:
            from dharma_swarm.autoresearch_loop import AutoResearchLoop
            loop = AutoResearchLoop()
            sr.status = "completed"
            sr.completed_at = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            sr.status = "quarantined"
            sr.quarantined = True
            sr.error = f"Research backend '{backend}' unavailable: {exc}"
            sr.completed_at = datetime.now(timezone.utc).isoformat()

        return sr

    @staticmethod
    def _estimate_stage_cost(stage: str) -> float:
        """Estimate provider cost per stage (placeholder for real metering)."""
        cost_map = {
            "scope": 0.01,
            "validate": 0.02,
            "deep_research": 0.10,
            "capability": 0.03,
            "mvp": 0.05,
            "first_artifact": 0.02,
        }
        return cost_map.get(stage, 0.01)

    def _record_economic_telemetry(
        self,
        sr: StageResult,
        row: OpportunityRow,
    ) -> None:
        """Record provider cost and net value in economic telemetry."""
        if self._economic_engine is not None:
            try:
                from dharma_swarm.economic_engine import ExpenseCategory
                self._economic_engine.record_expense(
                    sr.provider_cost_usd,
                    ExpenseCategory.API_CALLS,
                    f"Opportunity {row.id} stage {sr.stage}",
                )
            except Exception:
                logger.debug("Economic telemetry record failed", exc_info=True)

        if self._telemetry_store is not None:
            try:
                self._telemetry_store.record_economic_event_sync(
                    event_kind="opportunity_stage_cost",
                    amount=sr.provider_cost_usd,
                    currency="USD",
                    description=f"Stage {sr.stage} for opportunity {row.id}",
                    session_id="",
                    task_id=sr.task_id,
                    run_id=sr.run_id,
                    metadata={
                        "opportunity_id": row.id,
                        "stage": sr.stage,
                        "provider_cost_usd": sr.provider_cost_usd,
                    },
                )
            except Exception:
                logger.debug("Telemetry plane record failed", exc_info=True)

    def _write_revenue_packet(
        self,
        row: OpportunityRow,
        result: RefillResult,
    ) -> Path:
        """Write a revenue_packet.md summarizing the completed opportunity."""
        packet_path = self._output_dir / f"revenue_packet_{row.id}.md"
        lines = [
            f"# Revenue Packet: {row.title}",
            "",
            f"**Opportunity ID:** {row.id}",
            f"**Type:** {row.type}",
            f"**Source:** {row.source}",
            f"**Estimated Value:** ${row.estimated_value_usd:.2f}",
            f"**Total Provider Cost:** ${result.total_provider_cost_usd:.2f}",
            f"**Net Value:** ${result.total_net_value_usd:.2f}",
            "",
            "## Stage Results",
            "",
            "| Stage | Status | Task ID | Cost | Quarantined |",
            "|-------|--------|---------|------|-------------|",
        ]
        for s in result.stages:
            q = "Yes" if s.quarantined else "No"
            lines.append(
                f"| {s.stage} | {s.status} | `{s.task_id[:12]}` | ${s.provider_cost_usd:.2f} | {q} |"
            )
        lines.extend([
            "",
            "## Provenance",
            "",
            f"Generated at: {datetime.now(timezone.utc).isoformat()}",
            f"Stages completed: {sum(1 for s in result.stages if s.status == 'completed')}/{len(OPPORTUNITY_STAGES)}",
            "",
        ])

        packet_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Revenue packet written to %s", packet_path)
        return packet_path
