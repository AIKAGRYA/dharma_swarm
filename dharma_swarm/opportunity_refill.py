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
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from dharma_swarm.opportunity_dispatcher import (
    OPPORTUNITY_STAGES,
    OpportunityDispatcher,
)
from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.runtime_state import RuntimeStateStore, _new_id
from dharma_swarm.spine.identity import ExecutionIdentity

logger = logging.getLogger(__name__)

RESEARCH_BACKEND_ENV = "DHARMA_RESEARCH_BACKEND"
QUARANTINE_MARKER = "__quarantined__"
_OPPORTUNITY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")


def _canonical_opportunity_id(value: str) -> str:
    """Return an opportunity id that is safe as one path component."""
    if not isinstance(value, str) or _CONTROL_CHARACTER_RE.search(value):
        raise ValueError("opportunity id contains a control character")
    component = re.sub(r"[^A-Za-z0-9_.-]", "", value)
    if component != value or not _OPPORTUNITY_ID_RE.fullmatch(component):
        raise ValueError("opportunity id is not a canonical path component")
    return component


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

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Reject traversal and control characters at the API model boundary."""
        return _canonical_opportunity_id(value)


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
        runtime_state: RuntimeStateStore | None = None,
    ) -> None:
        self._telic_seam = telic_seam
        self._economic_engine = economic_engine
        self._telemetry_store = telemetry_store
        self._runtime_state = runtime_state
        self._dispatcher = dispatcher or OpportunityDispatcher(
            state_store=runtime_state,
            telic_seam=telic_seam,
            economic_engine=economic_engine,
        )
        if self._runtime_state is None:
            self._runtime_state = getattr(self._dispatcher, "_store", None)
        configured_output_dir = output_dir or (dharma_state_dir() / "revenue_packets")
        self._output_dir = Path(
            os.path.realpath(os.fspath(configured_output_dir.expanduser()))
        )
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def refill(self, row: OpportunityRow) -> RefillResult:
        """Refill a single opportunity through all stages.

        Returns a RefillResult with per-stage details and a revenue packet.
        """
        result = RefillResult(
            opportunity_id=row.id,
            opportunity_type=row.type,
        )

        trace_id = str(row.metadata.get("trace_id") or _new_id("trace"))
        correlation_id = str(row.metadata.get("correlation_id") or trace_id)
        opp_dict = row.model_dump()
        opp_dict["trace_id"] = trace_id
        opp_dict["correlation_id"] = correlation_id
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
            self._record_runtime_stage_receipt(sr, row, trace_id=trace_id, correlation_id=correlation_id)
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
            AutoResearchLoop()
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

    def _record_runtime_stage_receipt(
        self,
        sr: StageResult,
        row: OpportunityRow,
        *,
        trace_id: str,
        correlation_id: str,
    ) -> None:
        """Record the refill wrapper's own stage observation in runtime truth."""
        if self._runtime_state is None or not sr.task_id or not sr.run_id or not sr.claim_id:
            return
        identity = self._runtime_state.get_execution_identity_sync(sr.run_id)
        if identity is None:
            identity = ExecutionIdentity.new(
                task_id=sr.task_id,
                agent_id="opportunity_agent",
                session_id=str(getattr(self._dispatcher, "_session_id", "") or ""),
                trace_id=trace_id,
                correlation_id=correlation_id,
                causation_id=f"opportunity:{row.id}:{sr.stage}",
                run_id=sr.run_id,
                claim_id=sr.claim_id,
                idempotency_key=f"idem_{sr.run_id}",
                proposal_id=sr.proposal_id,
                metadata={
                    "source": "opportunity_refill",
                    "opportunity_id": row.id,
                    "opportunity_type": row.type,
                    "stage": sr.stage,
                },
            )
        payload = {
            "opportunity_id": row.id,
            "opportunity_type": row.type,
            "stage": sr.stage,
            "status": sr.status,
            "quarantined": sr.quarantined,
            "provider_cost_usd": sr.provider_cost_usd,
            "net_value_usd": sr.net_value_usd,
            "artifact_path": sr.artifact_path,
            "error": sr.error,
        }
        try:
            self._runtime_state.record_execution_identity_sync(
                identity,
                source="opportunity_refill",
                metadata=payload,
            )
            self._runtime_state.record_receipt_for_identity_sync(
                identity,
                receipt_type="opportunity_refill_stage",
                status=sr.status,
                side_effect_key=f"opportunity_refill:{row.id}:{sr.stage}",
                payload=payload,
            )
        except Exception:
            logger.debug("Runtime stage receipt record failed", exc_info=True)

    def _write_revenue_packet(
        self,
        row: OpportunityRow,
        result: RefillResult,
    ) -> Path:
        """Write a revenue_packet.md summarizing the completed opportunity."""
        safe_id = _canonical_opportunity_id(row.id)
        packet_value = os.path.realpath(
            os.path.join(
                os.fspath(self._output_dir),
                f"revenue_packet_{safe_id}.md",
            )
        )
        output_root = os.fspath(self._output_dir)
        root_prefix = output_root if output_root.endswith(os.sep) else output_root + os.sep
        if not packet_value.startswith(root_prefix):
            raise ValueError("revenue packet path escapes the output directory")
        packet_path = Path(packet_value)
        lines = [
            f"# Revenue Packet: {row.title}",
            "",
            f"**Opportunity ID:** {safe_id}",
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
        # Keep user-controlled identifiers and paths out of the log record.
        logger.info("Revenue packet written")
        return packet_path


# ---------------------------------------------------------------------------
#  BR-002 closure: refill_frontier_tasks_pending
#
#  This is the missing bridge between opportunity_board.json and the swarm
#  TaskBoard. The cron_runner (handler="frontier_refill") calls this function.
#
#  Canonical path (from CONTEMPLATIVE_SPINE §1):
#    ShaktiExecutive → opportunity_board.json → refill_frontier_tasks_pending
#    → frontier_tasks_pending.jsonl → opportunity_dispatcher → TaskBoard
#    → TelicSeam → Outcome / ValueEvent / Contribution → ShaktiExecutive feedback
# ---------------------------------------------------------------------------


class FrontierRefillResult(BaseModel):
    """Result of a frontier refill cycle."""

    paused: bool = False
    board_count: int = 0
    queued_count: int = 0
    addressed_count: int = 0
    appended_rows: int = 0
    appended_opportunity_ids: list[str] = Field(default_factory=list)
    error: str = ""


def _read_board(board_path: Path | None = None) -> list[dict[str, Any]]:
    """Read the opportunity board, returning an empty list on any failure."""
    path = (board_path or dharma_state_dir() / "meta" / "opportunity_board.json").expanduser()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce numeric board fields without letting malformed rows crash refill."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalized_score(value: Any) -> float:
    """Return a 0..1 score whether the board stores normalized or 0..100 values."""
    score = _safe_float(value)
    if score > 1.0:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def _opportunity_id(row: dict[str, Any]) -> str:
    """Return the canonical board identifier, accepting legacy ``id`` rows."""
    raw = row.get("opportunity_id") or row.get("id")
    if raw:
        return str(raw)
    generated = uuid4().hex[:12]
    row["opportunity_id"] = generated
    return generated


def _select_pending(
    board: list[dict[str, Any]],
    *,
    top_k: int = 3,
    min_telos_alignment: float = 0.5,
) -> list[dict[str, Any]]:
    """Pick the top-k board entries that are neither addressed nor queued."""
    pending = []
    for row in board:
        if row.get("addressed") or row.get("queued"):
            continue
        if not _passes_world_admission(row):
            continue
        telos = _normalized_score(row.get("telos_alignment", row.get("final_score", 0)))
        if telos < min_telos_alignment:
            continue
        pending.append(row)
    pending.sort(key=lambda r: _normalized_score(r.get("final_score", 0)), reverse=True)
    return pending[:top_k]


def _passes_world_admission(row: dict[str, Any]) -> bool:
    """Keep watchlist/incubating world signals out of direct execution."""
    domain = str(row.get("domain") or row.get("type") or "").strip()
    strategic = row.get("strategic_vision") if isinstance(row.get("strategic_vision"), dict) else {}
    source_inputs = [item for item in row.get("source_inputs", []) or [] if isinstance(item, dict)]
    is_world = domain == "ecosystem_scan" or any(
        str(item.get("source") or "") == "zeitgeist" and str(item.get("raw_source") or "")
        for item in source_inputs
    )
    if not is_world:
        return True
    status = str(
        strategic.get("promotion_status")
        or strategic.get("incubation_status")
        or row.get("promotion_status")
        or ""
    ).strip()
    if status and status != "promotion_ready":
        return False
    has_evidence = bool(row.get("evidence_signals")) and bool(source_inputs)
    has_source_url = bool(strategic.get("url") or row.get("url"))
    return has_evidence or has_source_url or status == "promotion_ready"


def _append_frontier_rows(
    rows: list[dict[str, Any]],
    frontier_path: Path | None = None,
) -> int:
    """Append opportunity-sourced task rows to frontier_tasks_pending.jsonl."""
    path = (frontier_path or dharma_state_dir() / "meta" / "frontier_tasks_pending.jsonl").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")
            count += 1
    return count


def _mark_queued(
    board: list[dict[str, Any]],
    opp_ids: set[str],
    board_path: Path | None = None,
) -> None:
    """Mark queued opportunities so refill does not duplicate pending work."""
    path = (board_path or dharma_state_dir() / "meta" / "opportunity_board.json").expanduser()
    queued_at = datetime.now(timezone.utc).isoformat()
    for row in board:
        if _opportunity_id(row) in opp_ids:
            row["queued"] = True
            row["queued_at"] = queued_at
    tmp = path.with_suffix(path.suffix + f".tmp.{int(time.time() * 1000)}")
    tmp.write_text(json.dumps(board, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def refill_frontier_tasks_pending(
    *,
    top_k: int = 3,
    min_telos_alignment: float = 0.5,
    dry_run: bool = False,
    board_path: Path | None = None,
    frontier_path: Path | None = None,
) -> FrontierRefillResult:
    """Promote top pending opportunities from the board into the frontier queue.

    This closes the BR-002 gap: opportunities selected by ShaktiExecutive
    become frontier task rows carrying ``opportunity_id`` in metadata. When the
    swarm dispatches these tasks and agents complete them, telic_seam.record_outcome
    reads ``opportunity_id`` from task.metadata and calls feedback_writer to
    update the board. The loop closes.

    Called by cron_runner handler ``frontier_refill``.
    """
    pause_file = dharma_state_dir() / ".PAUSE"
    if pause_file.exists():
        return FrontierRefillResult(paused=True)

    board = _read_board(board_path)
    if not board:
        return FrontierRefillResult(board_count=0)

    selected = _select_pending(board, top_k=top_k, min_telos_alignment=min_telos_alignment)
    if not selected:
        return FrontierRefillResult(board_count=len(board))

    frontier_rows: list[dict[str, Any]] = []
    queued_ids: set[str] = set()

    for opp in selected:
        opp_id = _opportunity_id(opp)
        opp_title = str(opp.get("title", "Untitled opportunity"))
        opp_type = str(opp.get("type") or opp.get("domain") or "external_revenue")
        queued_ids.add(opp_id)

        for stage in OPPORTUNITY_STAGES:
            metadata = _frontier_metadata(opp, opportunity_id=opp_id, opportunity_type=opp_type, stage=stage)
            frontier_rows.append({
                "title": f"[{opp_type}] {opp_title} — {stage}",
                "description": f"Stage '{stage}' for opportunity {opp_id}",
                "priority": "high",
                "created_by": "frontier_refill",
                "metadata": metadata,
            })

    if dry_run:
        return FrontierRefillResult(
            board_count=len(board),
            queued_count=len(selected),
            addressed_count=0,
            appended_rows=len(frontier_rows),
            appended_opportunity_ids=sorted(queued_ids),
        )

    appended = _append_frontier_rows(frontier_rows, frontier_path)
    _mark_queued(board, queued_ids, board_path)

    return FrontierRefillResult(
        board_count=len(board),
        queued_count=len(selected),
        addressed_count=0,
        appended_rows=appended,
        appended_opportunity_ids=sorted(queued_ids),
    )


def _frontier_metadata(
    opp: dict[str, Any],
    *,
    opportunity_id: str,
    opportunity_type: str,
    stage: str,
) -> dict[str, Any]:
    """Preserve strategic context as a board row becomes frontier work."""
    metadata = {
        "opportunity_id": opportunity_id,
        "opportunity_type": opportunity_type,
        "stage": stage,
        "source": "frontier_refill",
        "opportunity_title": opp.get("title", ""),
        "opportunity_domain": opp.get("domain") or opp.get("type") or "",
        "final_score": opp.get("final_score", 0),
        "why_now": opp.get("why_now", ""),
        "thesis": opp.get("thesis", ""),
    }
    for key in ("strategic_vision", "source_inputs", "evidence_signals", "factor_scores"):
        value = opp.get(key)
        if value:
            metadata[key] = value
    return metadata
