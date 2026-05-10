"""Opportunity dispatcher — routes governed opportunities through the runtime.

Connects the task board to the orchestrator via RuntimeStateStore, creating
durable task claims and delegation runs on every dispatch. Uses the active
swarm state root (from config/env) rather than defaulting to ~/.dharma.

Usage::

    dispatcher = OpportunityDispatcher(
        state_store=store,
        telic_seam=seam,
        economic_engine=engine,
    )
    results = await dispatcher.dispatch_opportunity(opportunity)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeStateStore,
    TaskClaim,
    _new_id,
    _utc_now,
    _utc_now_iso,
)

logger = logging.getLogger(__name__)


def _resolve_state_root() -> Path:
    """Resolve the active swarm state root from env or config, never ~/.dharma blindly."""
    env_root = os.environ.get("DHARMA_STATE_DIR")
    if env_root:
        return Path(env_root)
    try:
        from dharma_swarm.config import DEFAULT_CONFIG
        cfg_root = getattr(DEFAULT_CONFIG, "state_dir", None)
        if cfg_root:
            return Path(cfg_root)
    except Exception:
        pass
    return Path.home() / ".dharma" / "state"


OPPORTUNITY_STAGES = (
    "scope",
    "validate",
    "deep_research",
    "capability",
    "mvp",
    "first_artifact",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce score fields without crashing cron on malformed board rows."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _opportunity_id(opportunity: dict[str, Any]) -> str:
    """Return canonical opportunity ID, accepting older rows that used ``id``."""
    raw = opportunity.get("opportunity_id") or opportunity.get("id")
    if raw:
        return str(raw)
    generated = uuid4().hex[:12]
    opportunity["opportunity_id"] = generated
    return generated


class DispatchResult:
    """Result of dispatching a single opportunity stage."""

    __slots__ = ("stage", "task_id", "claim_id", "run_id", "proposal_id", "success", "error")

    def __init__(
        self,
        stage: str,
        task_id: str = "",
        claim_id: str = "",
        run_id: str = "",
        proposal_id: str = "",
        success: bool = True,
        error: str = "",
    ) -> None:
        self.stage = stage
        self.task_id = task_id
        self.claim_id = claim_id
        self.run_id = run_id
        self.proposal_id = proposal_id
        self.success = success
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "run_id": self.run_id,
            "proposal_id": self.proposal_id,
            "success": self.success,
            "error": self.error,
        }


class OpportunityDispatcher:
    """Dispatches governed opportunities through runtime with durable claims."""

    def __init__(
        self,
        state_store: RuntimeStateStore | None = None,
        telic_seam: Any | None = None,
        economic_engine: Any | None = None,
        session_id: str = "",
    ) -> None:
        state_root = _resolve_state_root()
        db_path = state_root / "runtime.db"
        self._store = state_store or RuntimeStateStore(db_path=db_path)
        self._telic_seam = telic_seam
        self._economic_engine = economic_engine
        self._session_id = session_id or f"opp-{uuid4().hex[:8]}"
        self._store.init_db_sync()

    def dispatch_opportunity_sync(
        self,
        opportunity: dict[str, Any],
        *,
        agent_id: str = "opportunity_agent",
    ) -> list[DispatchResult]:
        """Synchronously dispatch an opportunity through all stages.

        Creates durable RuntimeStateStore task claims and delegation runs
        for each stage. Records telic provenance if a seam is available.
        """
        results: list[DispatchResult] = []
        opp_id = _opportunity_id(opportunity)
        opp_title = str(opportunity.get("title", "Untitled opportunity"))
        opp_type = str(
            opportunity.get("type") or opportunity.get("domain") or "external_revenue"
        )

        for stage in OPPORTUNITY_STAGES:
            task_id = _new_id("task")
            claim_id = _new_id("claim")
            run_id = _new_id("run")

            task = Task(
                id=task_id,
                title=f"[{opp_type}] {opp_title} — {stage}",
                description=f"Stage '{stage}' for opportunity {opp_id}",
                priority=TaskPriority.HIGH,
                status=TaskStatus.PENDING,
                metadata={
                    "opportunity_id": opp_id,
                    "opportunity_type": opp_type,
                    "stage": stage,
                    "timeout_seconds": opportunity.get("timeout_seconds", 600),
                    "stale_after_seconds": opportunity.get("stale_after_seconds", 900),
                },
            )

            proposal_id: str | None = None
            if self._telic_seam is not None:
                try:
                    proposal_id = self._telic_seam.record_dispatch(
                        task, agent_id, topology="dispatch"
                    )
                except Exception as exc:
                    logger.debug("Telic dispatch record failed: %s", exc)

            try:
                self._store.create_task_claim_sync(
                    TaskClaim(
                        claim_id=claim_id,
                        task_id=task_id,
                        agent_id=agent_id,
                        status="claimed",
                        session_id=self._session_id,
                    )
                )
                self._store.create_delegation_run_sync(
                    DelegationRun(
                        run_id=run_id,
                        task_id=task_id,
                        assigned_to=agent_id,
                        status="running",
                        session_id=self._session_id,
                        claim_id=claim_id,
                    )
                )
                results.append(DispatchResult(
                    stage=stage,
                    task_id=task_id,
                    claim_id=claim_id,
                    run_id=run_id,
                    proposal_id=proposal_id or "",
                    success=True,
                ))
            except Exception as exc:
                logger.warning("Dispatch failed for stage %s: %s", stage, exc)
                results.append(DispatchResult(
                    stage=stage,
                    task_id=task_id,
                    error=str(exc),
                    success=False,
                ))
                break

        return results


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for cron_runner's ``frontier_dispatcher`` handler.

    Reads opportunity_board.json and dispatches top pending rows through
    the stage pipeline via :class:`OpportunityDispatcher`.
    """
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description="Dispatch opportunities from board")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--max", type=int, default=3, help="Max promotions per run")
    args = parser.parse_args(argv)

    board_path = Path.home() / ".dharma" / "meta" / "opportunity_board.json"
    if not board_path.exists():
        logger.info("No opportunity board found at %s", board_path)
        return 0

    try:
        board = _json.loads(board_path.read_text(encoding="utf-8"))
    except (OSError, _json.JSONDecodeError) as exc:
        logger.error("Failed to read board: %s", exc)
        return 1

    if not isinstance(board, list):
        logger.error("Board is not a list")
        return 1

    pending = [r for r in board if isinstance(r, dict) and not r.get("addressed")]
    pending.sort(key=lambda r: _safe_float(r.get("final_score", 0)), reverse=True)
    pending = pending[:args.max]

    if not pending:
        logger.info("No pending opportunities to dispatch")
        return 0

    if args.dry_run:
        for row in pending:
            logger.info("[dry-run] Would dispatch: %s (%s)", row.get("title"), _opportunity_id(row))
        return 0

    dispatcher = OpportunityDispatcher()
    for row in pending:
        results = dispatcher.dispatch_opportunity_sync(row)
        for r in results:
            logger.info("Dispatched %s/%s: success=%s", _opportunity_id(row), r.stage, r.success)

    return 0
