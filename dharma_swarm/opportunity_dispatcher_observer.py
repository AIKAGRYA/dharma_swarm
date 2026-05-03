"""Completion observer support for ``opportunity_dispatcher``."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ObserveResult:
    completed: list[dict[str, Any]] = field(default_factory=list)
    failed_retried: list[dict[str, Any]] = field(default_factory=list)
    failed_abandoned: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    in_flight: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _scan_in_flight(dispatcher: ModuleType) -> list[tuple[str, str, dict[str, Any]]]:
    out: list[tuple[str, str, dict[str, Any]]] = []
    for opp_id in dispatcher.list_campaign_ids():
        manifest = dispatcher.read_manifest(opp_id)
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
    dispatcher: ModuleType,
    opp_id: str,
    stage: str,
    manifest: dict[str, Any],
    task: Any,
    result: ObserveResult,
) -> None:
    quarantined = _is_quarantine_result(task)

    if stage == "deep_research":
        filename = "deep_research.quarantined.json" if quarantined else "deep_research.json"
        target = dispatcher.CAMPAIGN_ROOT / opp_id / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        body = str(getattr(task, "result", "") or "")
        target.write_text(body, encoding="utf-8")
        try:
            from uuid import uuid4
            from dharma_swarm.engine.artifacts import ArtifactRef
            from dharma_swarm.artifact_manifest import ArtifactManifestStore
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
                    "frontier_id": (manifest.get("stages") or {}).get(stage, {}).get("frontier_id", ""),
                },
            )
        except Exception:
            logger.debug("ArtifactManifestStore.record_manifest failed", exc_info=True)
        new_status = "quarantined" if quarantined else "completed"
        dispatcher.update_stage(
            manifest, stage,
            status=new_status,
            task_id=task.id,
            completed_at=datetime.now(timezone.utc).isoformat(),
            artifact_path=filename,
            quarantine_cleared_by=None if quarantined else None,
        )
        dispatcher.write_manifest(opp_id, manifest)
        if quarantined:
            result.quarantined.append({"opportunity_id": opp_id, "stage": stage, "task_id": task.id})
        else:
            result.completed.append({"opportunity_id": opp_id, "stage": stage, "task_id": task.id})
        return

    if quarantined:
        dispatcher.update_stage(
            manifest, stage,
            status="quarantined",
            task_id=task.id,
            completed_at=datetime.now(timezone.utc).isoformat(),
            quarantine_cleared_by=None,
        )
        dispatcher.write_manifest(opp_id, manifest)
        result.quarantined.append({"opportunity_id": opp_id, "stage": stage, "task_id": task.id})
        return

    artifact_path: str | None = None
    if stage in dispatcher.STAGE_DOC_STAGES:
        body = str(getattr(task, "result", "") or "")
        target = dispatcher.CAMPAIGN_ROOT / opp_id / dispatcher.STAGE_FILENAME[stage]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        artifact_path = dispatcher.STAGE_FILENAME[stage]

    dispatcher.update_stage(
        manifest, stage,
        status="completed",
        task_id=task.id,
        completed_at=datetime.now(timezone.utc).isoformat(),
        artifact_path=artifact_path,
    )
    dispatcher.write_manifest(opp_id, manifest)

    try:
        from dharma_swarm.stigmergy import leave_stigmergic_mark
        await leave_stigmergic_mark(
            agent="opportunity_dispatcher.observer",
            file_path=str(dispatcher.CAMPAIGN_ROOT / opp_id / (artifact_path or "manifest.json")),
            observation=f"completed {stage} for {opp_id} \u2192 task {task.id}",
            salience=0.8,
            connections=[opp_id, task.id],
            channel="strategy",
            action="write",
        )
    except Exception:
        logger.debug("observer stigmergy mark failed", exc_info=True)

    result.completed.append({"opportunity_id": opp_id, "stage": stage, "task_id": task.id})


def _process_failed_task(
    dispatcher: ModuleType,
    opp_id: str,
    stage: str,
    manifest: dict[str, Any],
    task: Any,
    result: ObserveResult,
) -> None:
    s = manifest["stages"][stage]
    retry_count = int(s.get("retry_count") or 0)
    next_backoff = (
        dispatcher.RETRY_BACKOFF_SECONDS[retry_count]
        if retry_count < len(dispatcher.RETRY_BACKOFF_SECONDS)
        else None
    )
    now = datetime.now(timezone.utc)
    if next_backoff is None:
        dispatcher.update_stage(
            manifest, stage,
            status="abandoned",
            retry_count=retry_count + 1,
            last_retry_at=now.isoformat(),
            next_retry_at=None,
            failure_reason=str(getattr(task, "result", "") or "")[:500],
        )
        dispatcher.write_manifest(opp_id, manifest)
        result.failed_abandoned.append(
            {"opportunity_id": opp_id, "stage": stage, "task_id": task.id, "retry_count": retry_count + 1}
        )
        return

    next_retry = now.timestamp() + next_backoff
    next_retry_iso = datetime.fromtimestamp(next_retry, tz=timezone.utc).isoformat()
    dispatcher.update_stage(
        manifest, stage,
        status="failed",
        task_id=task.id,
        retry_count=retry_count + 1,
        last_retry_at=now.isoformat(),
        next_retry_at=next_retry_iso,
        failure_reason=str(getattr(task, "result", "") or "")[:500],
    )
    dispatcher.write_manifest(opp_id, manifest)
    result.failed_retried.append(
        {"opportunity_id": opp_id, "stage": stage, "task_id": task.id,
         "next_retry_at": next_retry_iso, "retry_count": retry_count + 1}
    )


async def observe_completions(dispatcher: ModuleType) -> ObserveResult:
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board import TaskBoard

    result = ObserveResult()
    triples = _scan_in_flight(dispatcher)
    if not triples:
        return result

    dispatcher.TASK_BOARD_DB.parent.mkdir(parents=True, exist_ok=True)
    board = TaskBoard(dispatcher.TASK_BOARD_DB)
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
            dispatcher.update_stage(
                manifest, stage,
                status="abandoned",
                failure_reason="task missing from task_board",
            )
            dispatcher.write_manifest(opp_id, manifest)
            result.failed_abandoned.append(
                {"opportunity_id": opp_id, "stage": stage, "task_id": task_id, "reason": "missing"}
            )
            continue
        status = task.status if hasattr(task.status, "value") else str(task.status)
        status_val = status.value if hasattr(status, "value") else str(status)
        if status_val == TaskStatus.COMPLETED.value:
            try:
                await _process_completed_task(dispatcher, opp_id, stage, manifest, task, result)
            except Exception as exc:
                logger.exception("process_completed failed for %s/%s", opp_id, stage)
                result.errors.append(f"{opp_id}/{stage}: {exc}")
        elif status_val == TaskStatus.FAILED.value:
            try:
                _process_failed_task(dispatcher, opp_id, stage, manifest, task, result)
            except Exception as exc:
                logger.exception("process_failed failed for %s/%s", opp_id, stage)
                result.errors.append(f"{opp_id}/{stage}: {exc}")
        else:
            result.in_flight.append(
                {"opportunity_id": opp_id, "stage": stage, "task_id": task_id, "task_status": status_val}
            )
    return result


def retry_quarantined(dispatcher: ModuleType, spec: str) -> tuple[bool, str]:
    if ":" not in spec:
        return False, f"expected OPP_ID:STAGE, got {spec!r}"
    opp_id, stage = spec.split(":", 1)
    if stage not in dispatcher.PROMOTABLE_STAGES and stage not in dispatcher.STAGE_FILENAME:
        return False, f"unknown stage: {stage!r}"
    manifest = dispatcher.read_manifest(opp_id)
    if manifest is None:
        return False, f"no manifest for opportunity {opp_id!r}"
    s = manifest["stages"].get(stage)
    if s is None:
        return False, f"stage {stage!r} not present in manifest"
    if s.get("status") != "quarantined":
        return False, f"stage {stage!r} is {s.get('status')!r}, not quarantined"
    dispatcher.update_stage(
        manifest, stage,
        status="pending",
        task_id=None,
        retry_count=int(s.get("retry_count") or 0),
        last_retry_at=datetime.now(timezone.utc).isoformat(),
        next_retry_at=None,
        quarantine_cleared_by="cli",
        quarantine_cleared_at=datetime.now(timezone.utc).isoformat(),
    )
    dispatcher.write_manifest(opp_id, manifest)
    return True, f"cleared quarantine on {opp_id}/{stage}"
