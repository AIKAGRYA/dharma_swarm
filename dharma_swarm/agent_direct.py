"""Directive layer — human-in-the-loop injection into persistent conductors.

``PersistentAgent.accept_task`` has existed for a while but nothing exposed
it. This module gives the operator a first-class socket:

* ``write_directive(agent, task, campaign_id, priority)`` writes a structured
  JSON file to ``~/.dharma/directives/<uuid>.json``. The CLI (``dgc
  agent:direct`` / ``dgc campaign:new``) calls this.
* ``watcher_loop(shutdown_event)`` runs inside ``orchestrate_live`` alongside
  the executive loop. Every 5 seconds it scans the directives dir, resolves
  each file's target conductor via ``dharma_swarm.conductors.get``, hands the
  task to ``accept_task``, appends a witness log entry, and deletes the file.
* Unmatched targets (conductor not registered, missing payload) move to
  ``~/.dharma/directives/_unmatched/`` with a ``reason`` field so the operator
  can inspect why.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.campaigns import find_campaign

logger = logging.getLogger(__name__)

_DEFAULT_DIRECTIVES_DIR = Path.home() / ".dharma" / "directives"
_DEFAULT_POLL_INTERVAL = 5.0
_MAX_DIRECTIVE_AGE_SECONDS = 7 * 24 * 3600.0  # 7 days


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _directives_dir(directives_dir: Path | None = None) -> Path:
    return directives_dir or _DEFAULT_DIRECTIVES_DIR


def _unmatched_dir(directives_dir: Path | None = None) -> Path:
    return _directives_dir(directives_dir) / "_unmatched"


def _ensure_dirs(directives_dir: Path | None = None) -> None:
    base = _directives_dir(directives_dir)
    base.mkdir(parents=True, exist_ok=True)
    _unmatched_dir(base).mkdir(parents=True, exist_ok=True)


def write_directive(
    agent: str,
    task: str,
    *,
    campaign_id: str | None = None,
    priority: str = "normal",
    directives_dir: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Persist a directive and return the path. Does not dispatch it."""
    if not agent or not isinstance(agent, str):
        raise ValueError("agent must be a non-empty string")
    if not task or not isinstance(task, str):
        raise ValueError("task must be a non-empty string")
    if priority not in ("normal", "override"):
        priority = "normal"

    _ensure_dirs(directives_dir)
    directive_id = uuid.uuid4().hex
    record = {
        "directive_id": directive_id,
        "agent": agent,
        "task": task,
        "campaign_id": campaign_id,
        "priority": priority,
        "created": _utc_now_iso(),
        "metadata": dict(metadata or {}),
    }
    path = _directives_dir(directives_dir) / f"{directive_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2))
    tmp.replace(path)
    return path


def _move_to_unmatched(
    src: Path,
    reason: str,
    record: dict[str, Any] | None,
    directives_dir: Path | None,
) -> None:
    unmatched = _unmatched_dir(directives_dir)
    try:
        unmatched.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error("agent_direct: cannot create _unmatched dir: %s", e)
        return
    dst = unmatched / src.name
    try:
        if record is not None:
            record = {**record, "unmatched_reason": reason, "unmatched_at": _utc_now_iso()}
            dst.write_text(json.dumps(record, indent=2))
            src.unlink(missing_ok=True)
        else:
            payload = {
                "raw": src.read_text(errors="replace") if src.exists() else "",
                "unmatched_reason": reason,
                "unmatched_at": _utc_now_iso(),
                "original_name": src.name,
            }
            dst.write_text(json.dumps(payload, indent=2))
            src.unlink(missing_ok=True)
    except Exception as e:
        logger.error("agent_direct: failed to move unmatched directive: %s", e)


async def _dispatch_one(
    path: Path,
    directives_dir: Path | None,
    witness_dir: Path,
) -> bool:
    """Process one directive file. Returns True iff handed to an agent."""
    from dharma_swarm.conductors import get as get_conductor  # lazy

    try:
        raw = path.read_text()
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.error("agent_direct: unreadable %s (%s)", path.name, e)
        _move_to_unmatched(path, f"unreadable: {e}", None, directives_dir)
        return False

    try:
        record = json.loads(raw)
    except Exception as e:
        logger.error("agent_direct: malformed JSON in %s (%s)", path.name, e)
        _move_to_unmatched(path, f"malformed_json: {e}", None, directives_dir)
        return False

    agent = str(record.get("agent") or "").strip()
    task = str(record.get("task") or "").strip()
    if not agent or not task:
        _move_to_unmatched(path, "missing_agent_or_task", record, directives_dir)
        return False

    # Expiration sweep
    try:
        created = datetime.fromisoformat(str(record.get("created", "")).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - created).total_seconds()
        if age > _MAX_DIRECTIVE_AGE_SECONDS:
            _move_to_unmatched(path, "expired", record, directives_dir)
            return False
    except Exception:
        pass  # missing/invalid timestamp — proceed anyway

    conductor = await get_conductor(agent)
    if conductor is None:
        _move_to_unmatched(path, f"conductor_not_registered:{agent}", record, directives_dir)
        return False

    campaign_id = record.get("campaign_id")
    if campaign_id:
        camp = find_campaign(str(campaign_id))
        if camp is None:
            # Campaign referenced but not in registry — flag loud, dispatch plain.
            logger.warning(
                "agent_direct: directive references unknown campaign '%s'; "
                "dispatching as plain task", campaign_id,
            )
            task_text = task
            campaign_id = None
        else:
            task_text = f"CAMPAIGN: {camp['campaign_id']} — {task}"
    else:
        task_text = task

    try:
        await conductor.accept_task(task_text)
    except Exception as e:
        logger.error("agent_direct: accept_task failed for %s (%s)", agent, e)
        _move_to_unmatched(path, f"accept_task_failed:{e}", record, directives_dir)
        return False

    # Witness log — append-only
    try:
        witness_dir.mkdir(parents=True, exist_ok=True)
        witness_path = witness_dir / f"directives_{agent}.jsonl"
        witness_record = {
            "timestamp": _utc_now_iso(),
            "directive_id": record.get("directive_id"),
            "agent": agent,
            "task_prefix": task_text[:200],
            "campaign_id": campaign_id,
            "priority": record.get("priority", "normal"),
        }
        with witness_path.open("a") as fh:
            fh.write(json.dumps(witness_record) + "\n")
    except Exception as e:
        logger.error("agent_direct: witness log failed: %s", e)

    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        logger.error("agent_direct: cleanup failed for %s (%s)", path.name, e)
    return True


async def scan_once(
    directives_dir: Path | None = None,
    witness_dir: Path | None = None,
) -> int:
    """Process all directives in the queue once. Returns count dispatched."""
    base = _directives_dir(directives_dir)
    if not base.exists():
        return 0
    wdir = witness_dir or (Path.home() / ".dharma" / "witness")
    files = sorted(p for p in base.glob("*.json") if p.is_file())
    dispatched = 0
    for path in files:
        if await _dispatch_one(path, directives_dir, wdir):
            dispatched += 1
    return dispatched


async def watcher_loop(
    shutdown_event: asyncio.Event,
    directives_dir: Path | None = None,
    poll_interval: float = _DEFAULT_POLL_INTERVAL,
    witness_dir: Path | None = None,
) -> None:
    """Run the watcher until shutdown. Registered by orchestrate_live."""
    from dharma_swarm.conductors import snapshot_names

    _ensure_dirs(directives_dir)
    logger.info(
        "agent_direct: watcher running (dir=%s interval=%.1fs)",
        _directives_dir(directives_dir), poll_interval,
    )
    logger.info(
        "agent_direct: initial active conductors=%s",
        ", ".join(snapshot_names()) or "(none)",
    )
    while not shutdown_event.is_set():
        try:
            dispatched = await scan_once(directives_dir, witness_dir)
            if dispatched:
                logger.info("agent_direct: dispatched %d directive(s)", dispatched)
        except Exception as e:
            logger.error("agent_direct: watcher error: %s", e)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=poll_interval)
            break
        except asyncio.TimeoutError:
            pass
    logger.info("agent_direct: watcher stopped")


__all__ = [
    "write_directive",
    "scan_once",
    "watcher_loop",
]
