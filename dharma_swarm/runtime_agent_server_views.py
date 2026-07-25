"""Agent Server-style read surfaces over existing runtime and cron state."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm import cron_scheduler
from dharma_swarm.runtime_platform_views import _serialize_value
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore, SessionEventRecord


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    normalized = str(value).strip()
    return normalized or default


def _metadata(record: Any) -> dict[str, Any]:
    raw = getattr(record, "metadata", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _profile_field(metadata: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = _text(metadata.get(key))
        if value:
            return value
    return default


def _configuration_id(
    metadata: dict[str, Any],
    *,
    assistant_id: str,
    provider: str,
    model: str,
) -> str:
    explicit = _profile_field(metadata, "configuration_id", "assistant_config_id")
    if explicit:
        return explicit
    provider_part = provider or "provider-unknown"
    model_part = model or "model-unknown"
    return f"{assistant_id}:{provider_part}:{model_part}"


def _is_background_run(run: DelegationRun) -> bool:
    metadata = _metadata(run)
    run_kind = _profile_field(metadata, "run_kind", "execution_kind", "surface").lower()
    truthy = {"1", "true", "yes", "background", "cron", "scheduled"}
    if str(metadata.get("background", "")).lower() in truthy:
        return True
    if run_kind in {"background", "cron", "scheduled"}:
        return True
    if _profile_field(metadata, "cron_job_id", "background_job_id", "schedule_id"):
        return True
    return "cron" in run.assigned_by.lower() or "background" in run.assigned_by.lower()


def _is_background_event(event: SessionEventRecord) -> bool:
    payload = event.payload if isinstance(event.payload, dict) else {}
    name = event.event_name.lower()
    ledger = event.ledger_kind.lower()
    keys = {str(key).lower() for key in payload}
    return (
        ledger in {"background", "cron", "scheduler"}
        or "background" in name
        or "cron" in name
        or bool(keys & {"cron_job_id", "background_job_id", "schedule_id"})
    )


def _cron_output_count(job_id: str) -> int:
    job_dir = cron_scheduler.OUTPUT_DIR / job_id
    if not job_dir.exists():
        return 0
    return sum(1 for path in job_dir.glob("*.md") if path.is_file())


class RuntimeAgentServerViews:
    """Project assistants/configurations and background jobs without new authority."""

    def __init__(self, runtime_state: RuntimeStateStore) -> None:
        self.runtime_state = runtime_state

    async def runtime_assistants(self, *, limit: int = 50) -> dict[str, Any]:
        max_items = max(1, limit)
        sessions = await asyncio.to_thread(
            self.runtime_state.list_sessions_sync,
            limit=max_items * 2,
        )
        runs = await self.runtime_state.list_delegation_runs(limit=max_items * 5)
        assistants: dict[str, dict[str, Any]] = {}
        configurations: dict[str, dict[str, Any]] = {}

        for session in sessions:
            metadata = _metadata(session)
            assistant_id = _profile_field(
                metadata,
                "assistant_id",
                "agent_id",
                default=session.operator_id or "operator",
            )
            self._touch_assistant(
                assistants,
                configurations,
                assistant_id=assistant_id,
                name=_profile_field(metadata, "assistant_name", "name", default=assistant_id),
                provider=_profile_field(metadata, "provider", "planned_provider"),
                model=_profile_field(metadata, "model", "planned_model"),
                metadata=metadata,
                session_id=session.session_id,
                status=session.status,
            )

        for run in runs:
            metadata = _metadata(run)
            assistant_id = _profile_field(
                metadata,
                "assistant_id",
                "agent_id",
                default=run.assigned_to or "unassigned",
            )
            self._touch_assistant(
                assistants,
                configurations,
                assistant_id=assistant_id,
                name=_profile_field(metadata, "assistant_name", "name", default=assistant_id),
                provider=_profile_field(metadata, "provider", "planned_provider", "actual_provider"),
                model=_profile_field(metadata, "model", "planned_model", "actual_model"),
                metadata=metadata,
                session_id=run.session_id,
                run_id=run.run_id,
                status=run.status,
            )

        assistant_views = sorted(
            assistants.values(),
            key=lambda row: (row["active_run_count"], row["run_count"], row["assistant_id"]),
            reverse=True,
        )[:max_items]
        configuration_views = sorted(
            configurations.values(),
            key=lambda row: (row["run_count"], row["configuration_id"]),
            reverse=True,
        )[:max_items]
        return {
            "schema_version": "runtime_assistants_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "filters": {"limit": max_items},
            "summary": {
                "assistant_count": len(assistant_views),
                "configuration_count": len(configuration_views),
                "active_assistant_count": sum(
                    1 for assistant in assistant_views if assistant["active_run_count"] > 0
                ),
            },
            "assistants": assistant_views,
            "configurations": configuration_views,
        }

    async def runtime_background_jobs(self, *, limit: int = 50) -> dict[str, Any]:
        max_items = max(1, limit)
        cron_jobs = await asyncio.to_thread(cron_scheduler.list_jobs, True)
        runs = await self.runtime_state.list_delegation_runs(limit=max_items * 5)
        events = await self.runtime_state.list_session_events(limit=max_items * 5)
        background_runs = [self._run_to_dict(run) for run in runs if _is_background_run(run)]
        background_events = [
            _serialize_value(event) for event in events if _is_background_event(event)
        ]
        cron_views = [self._cron_job_to_dict(job) for job in cron_jobs]
        return {
            "schema_version": "runtime_background_jobs_snapshot.v1",
            "generated_at": _utc_now().isoformat(),
            "runtime_db": str(self.runtime_state.db_path),
            "cron_jobs_file": str(cron_scheduler.JOBS_FILE),
            "filters": {"limit": max_items},
            "summary": {
                "cron_job_count": len(cron_views),
                "enabled_cron_job_count": sum(1 for job in cron_views if job["enabled"]),
                "background_run_count": len(background_runs),
                "active_background_run_count": sum(
                    1
                    for run in background_runs
                    if run["status"] not in {"completed", "failed", "stale_recovered"}
                ),
                "background_event_count": len(background_events),
            },
            "cron_jobs": cron_views[:max_items],
            "background_runs": background_runs[:max_items],
            "background_events": background_events[:max_items],
        }

    @staticmethod
    def _touch_assistant(
        assistants: dict[str, dict[str, Any]],
        configurations: dict[str, dict[str, Any]],
        *,
        assistant_id: str,
        name: str,
        provider: str,
        model: str,
        metadata: dict[str, Any],
        session_id: str = "",
        run_id: str = "",
        status: str = "",
    ) -> None:
        configuration_id = _configuration_id(
            metadata,
            assistant_id=assistant_id,
            provider=provider,
            model=model,
        )
        assistant = assistants.setdefault(
            assistant_id,
            {
                "assistant_id": assistant_id,
                "name": name,
                "configuration_ids": [],
                "session_ids": [],
                "latest_run_id": "",
                "latest_session_id": "",
                "run_count": 0,
                "active_run_count": 0,
                "status": status or "unknown",
                "metadata": {},
            },
        )
        if configuration_id not in assistant["configuration_ids"]:
            assistant["configuration_ids"].append(configuration_id)
        if session_id and session_id not in assistant["session_ids"]:
            assistant["session_ids"].append(session_id)
            assistant["latest_session_id"] = session_id
        if run_id:
            assistant["latest_run_id"] = run_id
            assistant["run_count"] += 1
            if status not in {"completed", "failed", "stale_recovered"}:
                assistant["active_run_count"] += 1
        assistant["status"] = status or assistant["status"]
        assistant["metadata"].update(_serialize_value(metadata))

        configuration = configurations.setdefault(
            configuration_id,
            {
                "configuration_id": configuration_id,
                "assistant_ids": [],
                "provider": provider,
                "model": model,
                "tool_count": len(metadata.get("tools") or []),
                "system_prompt_hash": _profile_field(metadata, "system_prompt_hash"),
                "run_count": 0,
                "session_count": 0,
                "metadata": {},
            },
        )
        if assistant_id not in configuration["assistant_ids"]:
            configuration["assistant_ids"].append(assistant_id)
        if run_id:
            configuration["run_count"] += 1
        if session_id:
            configuration["session_count"] += 1
        configuration["metadata"].update(_serialize_value(metadata))

    @staticmethod
    def _run_to_dict(run: DelegationRun) -> dict[str, Any]:
        run_view = _serialize_value(run)
        metadata = _metadata(run)
        run_view["cron_job_id"] = _profile_field(
            metadata,
            "cron_job_id",
            "background_job_id",
            "schedule_id",
        )
        run_view["run_kind"] = _profile_field(
            metadata,
            "run_kind",
            "execution_kind",
            "surface",
            default="background",
        )
        return run_view

    @staticmethod
    def _cron_job_to_dict(job: dict[str, Any]) -> dict[str, Any]:
        job_id = _text(job.get("id"))
        return {
            "job_id": job_id,
            "name": _text(job.get("name"), job_id),
            "enabled": bool(job.get("enabled", True)),
            "urgent": bool(job.get("urgent", False)),
            "schedule": _serialize_value(job.get("schedule") or {}),
            "schedule_display": _text(job.get("schedule_display")),
            "deliver": _text(job.get("deliver"), "local"),
            "next_run_at": _text(job.get("next_run_at")),
            "last_run_at": _text(job.get("last_run_at")),
            "last_status": _text(job.get("last_status")),
            "last_error": _text(job.get("last_error")),
            "repeat": _serialize_value(job.get("repeat") or {}),
            "output_count": _cron_output_count(job_id) if job_id else 0,
            "output_dir": str((cron_scheduler.OUTPUT_DIR / job_id) if job_id else Path("")),
            "metadata": _serialize_value(
                {
                    key: value
                    for key, value in job.items()
                    if key
                    not in {
                        "id",
                        "name",
                        "enabled",
                        "urgent",
                        "schedule",
                        "schedule_display",
                        "deliver",
                        "next_run_at",
                        "last_run_at",
                        "last_status",
                        "last_error",
                        "repeat",
                    }
                }
            ),
        }
