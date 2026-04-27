"""Runtime lifecycle producer helpers for structured runtime records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.models import Task, TaskDispatch, _new_id
from dharma_swarm.runtime_state import ArtifactRecord, DelegationRun, TaskClaim
from dharma_swarm.session_ledger import SessionLedger

logger = logging.getLogger(__name__)


class RuntimeLifecycle:
    """Centralizes structured runtime producer writes for the orchestrator."""

    def __init__(self, ledger: SessionLedger) -> None:
        self._ledger = ledger

    @staticmethod
    def _task_meta(task: Task | None) -> dict[str, Any]:
        if task is None or not isinstance(task.metadata, dict):
            return {}
        return dict(task.metadata)

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _utc_datetime_from(value: Any, fallback: datetime | None = None) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), timezone.utc)
            except Exception:
                pass
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                pass
        return fallback or datetime.now(timezone.utc)

    @staticmethod
    def _runtime_status_time(status: str) -> datetime | None:
        if status in {"running", "completed", "failed"}:
            return datetime.now(timezone.utc)
        return None

    def _runtime_state_store(self) -> Any | None:
        return getattr(self._ledger, "_runtime_state", None)

    def ensure_runtime_run_id(self, td: TaskDispatch) -> str:
        existing = str(td.metadata.get("runtime_run_id", "") or "").strip()
        if existing:
            return existing
        run_id = f"run_{_new_id()}"
        td.metadata["runtime_run_id"] = run_id
        return run_id

    def runtime_metadata(
        self,
        td: TaskDispatch,
        *,
        status: str,
        failure_code: str = "",
        error: str = "",
        result: str | None = None,
    ) -> dict[str, Any]:
        metadata = {
            "source": "orchestrator",
            "status": status,
            "topology": td.topology.value if td.topology else "dispatch",
            "timeout_seconds": td.timeout_seconds,
            "retry_count": td.metadata.get("retry_count", 0),
            "max_retries": td.metadata.get("max_retries", 0),
            "claim_timeout_seconds": td.metadata.get("claim_timeout_seconds", 0),
        }
        if failure_code:
            metadata["failure_code"] = failure_code
        if error:
            metadata["error"] = error[:500]
        if result is not None:
            metadata["result_chars"] = len(result or "")
        return metadata

    async def record_task_claim(
        self,
        td: TaskDispatch,
        *,
        task: Task | None,
        status: str,
        failure_code: str = "",
        error: str = "",
    ) -> None:
        store = self._runtime_state_store()
        claim_id = str(td.metadata.get("claim_id", "") or "").strip()
        if store is None or not claim_id:
            return
        task_meta = self._task_meta(task)
        active_claim = task_meta.get("active_claim")
        if not isinstance(active_claim, dict):
            active_claim = {}
        now = datetime.now(timezone.utc)
        acked_at = self._runtime_status_time(status)
        heartbeat_at = now if status in {"running", "completed", "failed"} else None
        stale_after = None
        if active_claim.get("claim_expires_at_epoch") is not None:
            stale_after = self._utc_datetime_from(active_claim.get("claim_expires_at_epoch"))
        claim = TaskClaim(
            claim_id=claim_id,
            task_id=td.task_id,
            agent_id=td.agent_id,
            status=status,
            session_id=self._ledger.session_id,
            claimed_at=self._utc_datetime_from(active_claim.get("claimed_at"), now),
            acked_at=acked_at,
            heartbeat_at=heartbeat_at,
            stale_after=stale_after,
            retry_count=max(0, self._coerce_int(td.metadata.get("retry_count"), 0)),
            metadata=self.runtime_metadata(
                td,
                status=status,
                failure_code=failure_code,
                error=error,
            ),
        )
        try:
            await store.record_task_claim(claim)
        except Exception:
            logger.debug("Runtime task claim recording failed", exc_info=True)

    async def record_delegation_run(
        self,
        td: TaskDispatch,
        *,
        task: Task | None,
        status: str,
        failure_code: str = "",
        error: str = "",
        result: str | None = None,
    ) -> None:
        store = self._runtime_state_store()
        if store is None:
            return
        run_id = self.ensure_runtime_run_id(td)
        started_raw = td.metadata.get("runtime_run_started_at")
        started_at = self._utc_datetime_from(started_raw)
        if not started_raw:
            td.metadata["runtime_run_started_at"] = started_at.isoformat()
        task_meta = self._task_meta(task)
        requested_output = task_meta.get("requested_output", [])
        if not isinstance(requested_output, list):
            requested_output = []
        completed_at = datetime.now(timezone.utc) if status in {"completed", "failed"} else None
        run = DelegationRun(
            run_id=run_id,
            task_id=td.task_id,
            assigned_to=td.agent_id,
            status=status,
            session_id=self._ledger.session_id,
            claim_id=str(td.metadata.get("claim_id", "") or ""),
            parent_run_id=str(task_meta.get("parent_run_id", "") or ""),
            assigned_by="orchestrator",
            requested_output=[str(item) for item in requested_output],
            current_artifact_id=str(task_meta.get("current_artifact_id", "") or ""),
            started_at=started_at,
            completed_at=completed_at,
            failure_code=failure_code,
            metadata=self.runtime_metadata(
                td,
                status=status,
                failure_code=failure_code,
                error=error,
                result=result,
            ),
        )
        try:
            await store.record_delegation_run(run)
        except Exception:
            logger.debug("Runtime delegation run recording failed", exc_info=True)

    async def record_artifact(
        self,
        *,
        task: Task,
        artifact_id: str,
        artifact_kind: str,
        payload_path: Path,
        checksum: str,
        manifest_path: Path | None = None,
        run_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        store = self._runtime_state_store()
        if store is None:
            return
        artifact = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            session_id=self._ledger.session_id,
            task_id=task.id,
            run_id=run_id,
            manifest_path=str(manifest_path or ""),
            payload_path=str(payload_path),
            checksum=checksum,
            promotion_state="ephemeral",
            metadata={
                "source": "orchestrator._persist_result",
                "task_title": task.title,
                **(metadata or {}),
            },
        )
        try:
            await store.record_artifact(artifact)
        except Exception:
            logger.debug("Runtime artifact recording failed", exc_info=True)
