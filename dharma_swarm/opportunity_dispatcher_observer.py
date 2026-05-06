"""Observer, retry, and health helpers for opportunity_dispatcher.

This module is an implementation capsule behind ``opportunity_dispatcher``.
The public import surface stays on ``dharma_swarm.opportunity_dispatcher`` so
existing callers and tests can continue to patch that module's paths.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm._campaign_manifest import (
    CAMPAIGN_ROOT as DEFAULT_CAMPAIGN_ROOT,
    list_campaign_ids,
    read_manifest,
    update_stage,
    write_manifest,
)

logger = logging.getLogger(__name__)

DEFAULT_DHARMA_HOME = Path.home() / ".dharma"
DEFAULT_HEALTH_PATH = (
    DEFAULT_DHARMA_HOME / "meta" / "opportunity_dispatcher.health.json"
)
DEFAULT_TASK_BOARD_DB = DEFAULT_DHARMA_HOME / "db" / "tasks.db"
DEFAULT_STAGE_FILENAME: dict[str, str] = {
    "scope": "scope.md",
    "validate": "validate.md",
    "deep_research": "deep_research.json",
    "capability": "capability.md",
    "mvp": "mvp.md",
}
DEFAULT_STAGE_DOC_STAGES: frozenset[str] = frozenset(
    {"scope", "validate", "capability", "mvp"}
)
DEFAULT_PROMOTABLE_STAGES: tuple[str, ...] = (
    "scope",
    "validate",
    "deep_research",
    "capability",
    "mvp",
)
DEFAULT_RETRY_BACKOFF_SECONDS: tuple[int | None, ...] = (3600, 21600, None)
DEFAULT_INTERVAL_SECONDS = 1800
CRITICAL_FAILURE_THRESHOLD = 3


@dataclass
class HealthState:
    last_run_at: str = ""
    last_success_at: str | None = None
    consecutive_failures: int = 0
    run_count: int = 0
    success_count: int = 0
    last_run_dispatched: int = 0
    last_run_dry_run: bool = False
    last_run_paused: bool = False
    last_run_pending_count: int = 0
    last_run_errors: list[str] = field(default_factory=list)
    last_run_observed_completed: int = 0
    last_run_observed_failed_retried: int = 0
    last_run_observed_failed_abandoned: int = 0
    last_run_observed_quarantined: int = 0
    last_run_observed_in_flight: int = 0


def _read_health(health_path: Path = DEFAULT_HEALTH_PATH) -> HealthState:
    if not health_path.exists():
        return HealthState()
    try:
        raw = json.loads(health_path.read_text(encoding="utf-8"))
    except Exception:
        return HealthState()
    return HealthState(
        last_run_at=str(raw.get("last_run_at") or ""),
        last_success_at=raw.get("last_success_at"),
        consecutive_failures=int(raw.get("consecutive_failures") or 0),
        run_count=int(raw.get("run_count") or 0),
        success_count=int(raw.get("success_count") or 0),
        last_run_dispatched=int(raw.get("last_run_dispatched") or 0),
        last_run_dry_run=bool(raw.get("last_run_dry_run") or False),
        last_run_paused=bool(raw.get("last_run_paused") or False),
        last_run_pending_count=int(raw.get("last_run_pending_count") or 0),
        last_run_errors=list(raw.get("last_run_errors") or []),
        last_run_observed_completed=int(raw.get("last_run_observed_completed") or 0),
        last_run_observed_failed_retried=int(raw.get("last_run_observed_failed_retried") or 0),
        last_run_observed_failed_abandoned=int(raw.get("last_run_observed_failed_abandoned") or 0),
        last_run_observed_quarantined=int(raw.get("last_run_observed_quarantined") or 0),
        last_run_observed_in_flight=int(raw.get("last_run_observed_in_flight") or 0),
    )


def _write_health(
    state: HealthState, health_path: Path = DEFAULT_HEALTH_PATH,
) -> None:
    health_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_run_at": state.last_run_at,
        "last_success_at": state.last_success_at,
        "consecutive_failures": state.consecutive_failures,
        "run_count": state.run_count,
        "success_count": state.success_count,
        "last_run_dispatched": state.last_run_dispatched,
        "last_run_dry_run": state.last_run_dry_run,
        "last_run_paused": state.last_run_paused,
        "last_run_pending_count": state.last_run_pending_count,
        "last_run_errors": state.last_run_errors[-5:],
        "last_run_observed_completed": state.last_run_observed_completed,
        "last_run_observed_failed_retried": state.last_run_observed_failed_retried,
        "last_run_observed_failed_abandoned": state.last_run_observed_failed_abandoned,
        "last_run_observed_quarantined": state.last_run_observed_quarantined,
        "last_run_observed_in_flight": state.last_run_observed_in_flight,
        "schema_version": 2,
    }
    tmp = health_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, health_path)


def _update_health_from_result(
    state: HealthState, result: Any, ok: bool,
) -> HealthState:
    state.run_count += 1
    state.last_run_at = datetime.now(timezone.utc).isoformat()
    state.last_run_dry_run = result.dry_run
    state.last_run_paused = result.paused
    state.last_run_pending_count = result.pending_count
    state.last_run_dispatched = len(result.promoted)
    state.last_run_errors = list(result.errors)
    if ok:
        state.success_count += 1
        state.last_success_at = state.last_run_at
        state.consecutive_failures = 0
    else:
        state.consecutive_failures += 1
    return state


@dataclass
class ObserveResult:
    completed: list[dict[str, Any]] = field(default_factory=list)
    failed_retried: list[dict[str, Any]] = field(default_factory=list)
    failed_abandoned: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    in_flight: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _scan_in_flight() -> list[tuple[str, str, dict[str, Any]]]:
    """Return opportunity/stage/manifest triples for in-flight stages."""
    out: list[tuple[str, str, dict[str, Any]]] = []
    for opp_id in list_campaign_ids():
        manifest = read_manifest(opp_id)
        if manifest is None:
            continue
        for stage, s in (manifest.get("stages") or {}).items():
            status = str(s.get("status") or "")
            if status in {"promoted", "dispatched"}:
                out.append((opp_id, stage, manifest))
    return out


def _is_quarantine_result(task: Any) -> bool:
    raw = getattr(task, "result", None)
    if not raw:
        return False
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return False
    return bool(isinstance(parsed, dict) and parsed.get("quarantined") is True)


async def _process_completed_task(
    opp_id: str,
    stage: str,
    manifest: dict[str, Any],
    task: Any,
    result: ObserveResult,
    *,
    campaign_root: Path = DEFAULT_CAMPAIGN_ROOT,
    stage_filename: dict[str, str] | None = None,
    stage_doc_stages: Iterable[str] | None = None,
) -> None:
    """Handle a completed task without recording economic/telic events."""
    filenames = stage_filename or DEFAULT_STAGE_FILENAME
    doc_stages = frozenset(stage_doc_stages or DEFAULT_STAGE_DOC_STAGES)
    quarantined = _is_quarantine_result(task)

    if stage == "deep_research":
        filename = "deep_research.quarantined.json" if quarantined else "deep_research.json"
        target = campaign_root / opp_id / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        body = str(getattr(task, "result", "") or "")
        target.write_text(body, encoding="utf-8")
        try:
            from uuid import uuid4

            from dharma_swarm.artifact_manifest import ArtifactManifestStore
            from dharma_swarm.engine.artifacts import ArtifactRef

            ref = ArtifactRef(
                artifact_id=uuid4().hex[:16],
                artifact_type="deep_research_report",
                path=str(target),
                created_by="opportunity_dispatcher.observer",
                session_id=opp_id,
                version=1,
                confidence=0.0,
                citations=[],
                depends_on=[],
                metadata={
                    "opportunity_id": opp_id,
                    "stage": stage,
                    "quarantined": quarantined,
                },
            )
            ArtifactManifestStore().record_manifest(
                ref,
                artifact_kind="research_report",
                task_id=task.id,
                promotion_state="rollback_or_revise" if quarantined else "candidate",
                provenance={
                    "opportunity_id": opp_id,
                    "frontier_id": (
                        (manifest.get("stages") or {})
                        .get(stage, {})
                        .get("frontier_id", "")
                    ),
                },
            )
        except Exception:
            logger.debug("ArtifactManifestStore.record_manifest failed", exc_info=True)
        new_status = "quarantined" if quarantined else "completed"
        update_stage(
            manifest,
            stage,
            status=new_status,
            task_id=task.id,
            completed_at=datetime.now(timezone.utc).isoformat(),
            artifact_path=filename,
            quarantine_cleared_by=None if quarantined else None,
        )
        write_manifest(opp_id, manifest)
        if quarantined:
            result.quarantined.append(
                {"opportunity_id": opp_id, "stage": stage, "task_id": task.id}
            )
        else:
            result.completed.append(
                {"opportunity_id": opp_id, "stage": stage, "task_id": task.id}
            )
        return

    if quarantined:
        update_stage(
            manifest,
            stage,
            status="quarantined",
            task_id=task.id,
            completed_at=datetime.now(timezone.utc).isoformat(),
            quarantine_cleared_by=None,
        )
        write_manifest(opp_id, manifest)
        result.quarantined.append(
            {"opportunity_id": opp_id, "stage": stage, "task_id": task.id}
        )
        return

    artifact_path: str | None = None
    if stage in doc_stages:
        body = str(getattr(task, "result", "") or "")
        target = campaign_root / opp_id / filenames[stage]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        artifact_path = filenames[stage]

    update_stage(
        manifest,
        stage,
        status="completed",
        task_id=task.id,
        completed_at=datetime.now(timezone.utc).isoformat(),
        artifact_path=artifact_path,
    )
    write_manifest(opp_id, manifest)

    try:
        from dharma_swarm.stigmergy import leave_stigmergic_mark

        await leave_stigmergic_mark(
            agent="opportunity_dispatcher.observer",
            file_path=str(campaign_root / opp_id / (artifact_path or "manifest.json")),
            observation=f"completed {stage} for {opp_id} -> task {task.id}",
            salience=0.8,
            connections=[opp_id, task.id],
            channel="strategy",
            action="write",
        )
    except Exception:
        logger.debug("observer stigmergy mark failed", exc_info=True)

    result.completed.append(
        {"opportunity_id": opp_id, "stage": stage, "task_id": task.id}
    )


def _process_failed_task(
    opp_id: str,
    stage: str,
    manifest: dict[str, Any],
    task: Any,
    result: ObserveResult,
    *,
    retry_backoff_seconds: tuple[int | None, ...] = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> None:
    """Handle a failed task by applying retry backoff or abandoning."""
    s = manifest["stages"][stage]
    retry_count = int(s.get("retry_count") or 0)
    next_backoff = (
        retry_backoff_seconds[retry_count]
        if retry_count < len(retry_backoff_seconds)
        else None
    )
    now = datetime.now(timezone.utc)
    if next_backoff is None:
        update_stage(
            manifest,
            stage,
            status="abandoned",
            retry_count=retry_count + 1,
            last_retry_at=now.isoformat(),
            next_retry_at=None,
            failure_reason=str(getattr(task, "result", "") or "")[:500],
        )
        write_manifest(opp_id, manifest)
        result.failed_abandoned.append(
            {
                "opportunity_id": opp_id,
                "stage": stage,
                "task_id": task.id,
                "retry_count": retry_count + 1,
            }
        )
        return

    next_retry = now.timestamp() + next_backoff
    next_retry_iso = datetime.fromtimestamp(next_retry, tz=timezone.utc).isoformat()
    update_stage(
        manifest,
        stage,
        status="failed",
        task_id=task.id,
        retry_count=retry_count + 1,
        last_retry_at=now.isoformat(),
        next_retry_at=next_retry_iso,
        failure_reason=str(getattr(task, "result", "") or "")[:500],
    )
    write_manifest(opp_id, manifest)
    result.failed_retried.append(
        {
            "opportunity_id": opp_id,
            "stage": stage,
            "task_id": task.id,
            "next_retry_at": next_retry_iso,
            "retry_count": retry_count + 1,
        }
    )


async def observe_completions(
    *,
    task_board_db: Path = DEFAULT_TASK_BOARD_DB,
    campaign_root: Path = DEFAULT_CAMPAIGN_ROOT,
    stage_filename: dict[str, str] | None = None,
    stage_doc_stages: Iterable[str] | None = None,
    retry_backoff_seconds: tuple[int | None, ...] = DEFAULT_RETRY_BACKOFF_SECONDS,
) -> ObserveResult:
    """Poll task_board for in-flight dispatcher tasks and reconcile them."""
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board import TaskBoard

    result = ObserveResult()
    triples = _scan_in_flight()
    if not triples:
        return result

    task_board_db.parent.mkdir(parents=True, exist_ok=True)
    board = TaskBoard(task_board_db)
    await board.init_db()

    for opp_id, stage, manifest in triples:
        task_id = manifest["stages"][stage].get("task_id")
        if not task_id:
            continue
        try:
            task = await board.get(task_id)
        except Exception as exc:
            logger.exception("board.get failed for %s", task_id)
            result.errors.append(f"{opp_id}/{stage}: {exc}")
            continue
        if task is None:
            update_stage(
                manifest,
                stage,
                status="abandoned",
                failure_reason="task missing from task_board",
            )
            write_manifest(opp_id, manifest)
            result.failed_abandoned.append(
                {
                    "opportunity_id": opp_id,
                    "stage": stage,
                    "task_id": task_id,
                    "reason": "missing",
                }
            )
            continue
        status = task.status if hasattr(task.status, "value") else str(task.status)
        status_val = status.value if hasattr(status, "value") else str(status)
        if status_val == TaskStatus.COMPLETED.value:
            try:
                await _process_completed_task(
                    opp_id,
                    stage,
                    manifest,
                    task,
                    result,
                    campaign_root=campaign_root,
                    stage_filename=stage_filename,
                    stage_doc_stages=stage_doc_stages,
                )
            except Exception as exc:
                logger.exception("process_completed failed for %s/%s", opp_id, stage)
                result.errors.append(f"{opp_id}/{stage}: {exc}")
        elif status_val == TaskStatus.FAILED.value:
            try:
                _process_failed_task(
                    opp_id,
                    stage,
                    manifest,
                    task,
                    result,
                    retry_backoff_seconds=retry_backoff_seconds,
                )
            except Exception as exc:
                logger.exception("process_failed failed for %s/%s", opp_id, stage)
                result.errors.append(f"{opp_id}/{stage}: {exc}")
        else:
            result.in_flight.append(
                {
                    "opportunity_id": opp_id,
                    "stage": stage,
                    "task_id": task_id,
                    "task_status": status_val,
                }
            )
    return result


def retry_quarantined(
    spec: str,
    *,
    promotable_stages: Iterable[str] = DEFAULT_PROMOTABLE_STAGES,
    stage_filename: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Clear a quarantined stage so the dispatcher will re-attempt it."""
    if ":" not in spec:
        return False, f"expected OPP_ID:STAGE, got {spec!r}"
    opp_id, stage = spec.split(":", 1)
    known_stages = set(promotable_stages) | set(
        (stage_filename or DEFAULT_STAGE_FILENAME).keys()
    )
    if stage not in known_stages:
        return False, f"unknown stage: {stage!r}"
    manifest = read_manifest(opp_id)
    if manifest is None:
        return False, f"no manifest for opportunity {opp_id!r}"
    s = manifest["stages"].get(stage)
    if s is None:
        return False, f"stage {stage!r} not present in manifest"
    if s.get("status") != "quarantined":
        return False, f"stage {stage!r} is {s.get('status')!r}, not quarantined"
    update_stage(
        manifest,
        stage,
        status="pending",
        task_id=None,
        retry_count=int(s.get("retry_count") or 0),
        last_retry_at=datetime.now(timezone.utc).isoformat(),
        next_retry_at=None,
        quarantine_cleared_by="cli",
        quarantine_cleared_at=datetime.now(timezone.utc).isoformat(),
    )
    write_manifest(opp_id, manifest)
    return True, f"cleared quarantine on {opp_id}/{stage}"


def _is_frontier_active(pending_count: int, observed_in_flight: int) -> bool:
    return pending_count > 0 or observed_in_flight > 0


def _stall_window_seconds(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> int:
    return 2 * int(interval_seconds)


def detect_stalled_frontier(
    *,
    state: HealthState,
    pending_count: int,
    observed_in_flight: int,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> dict[str, Any] | None:
    """Return the stalled-frontier signal to fire, or None."""
    if not _is_frontier_active(pending_count, observed_in_flight):
        return None

    if state.consecutive_failures >= CRITICAL_FAILURE_THRESHOLD:
        return {
            "severity": "critical",
            "kind": "dispatcher_consecutive_failures",
            "action": f"opportunity_dispatcher failed {state.consecutive_failures}x in a row",
            "value": state.consecutive_failures,
            "description": (
                f"opportunity_dispatcher has failed {state.consecutive_failures} "
                f"consecutive times while pending={pending_count} and "
                f"in_flight={observed_in_flight}. The frontier is stalled - "
                f"investigate logs and last_run_errors before clearing."
            ),
            "context": {
                "consecutive_failures": state.consecutive_failures,
                "pending_count": pending_count,
                "in_flight": observed_in_flight,
                "last_run_errors": state.last_run_errors,
                "last_success_at": state.last_success_at,
            },
        }

    if state.last_success_at:
        try:
            last_success = datetime.fromisoformat(state.last_success_at)
        except ValueError:
            last_success = None
    else:
        last_success = None
    if last_success is not None:
        elapsed = (datetime.now(timezone.utc) - last_success).total_seconds()
        if elapsed > _stall_window_seconds(interval_seconds):
            return {
                "severity": "warning",
                "kind": "dispatcher_stale_success",
                "action": f"opportunity_dispatcher stale by {int(elapsed)}s",
                "value": int(elapsed),
                "description": (
                    f"opportunity_dispatcher last reported success "
                    f"{int(elapsed)}s ago (window={_stall_window_seconds(interval_seconds)}s) "
                    f"while pending={pending_count} and in_flight={observed_in_flight}."
                ),
                "context": {
                    "elapsed_seconds": int(elapsed),
                    "stall_window_seconds": _stall_window_seconds(interval_seconds),
                    "pending_count": pending_count,
                    "in_flight": observed_in_flight,
                    "last_success_at": state.last_success_at,
                },
            }

    return None


def _maybe_fire_invariant(
    state: HealthState,
    pending_count: int,
    observed_in_flight: int,
    *,
    interval_seconds: int | None = None,
) -> None:
    """Detect and fire the stalled-frontier invariant best-effort."""
    if interval_seconds is None:
        interval_seconds = int(
            os.environ.get("DISPATCHER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
        )
    sig = detect_stalled_frontier(
        state=state,
        pending_count=pending_count,
        observed_in_flight=observed_in_flight,
        interval_seconds=interval_seconds,
    )
    if sig is None:
        return
    try:
        from dharma_swarm.algedonic_bridge import fire_signal

        fire_signal(
            kind=sig["kind"],
            severity=sig["severity"],
            action=sig["action"],
            value=sig["value"],
            description=sig["description"],
            source="opportunity_dispatcher",
            context=sig["context"],
        )
    except Exception:
        logger.exception("algedonic_bridge.fire_signal raised")
