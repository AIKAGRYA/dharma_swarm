#!/usr/bin/env python3
"""hermes_heartbeat_poll.py — Hermes M5 heartbeat state writer + queue poller.

Fixes two protocol gaps identified in the 2026-05-23 morning briefing:
1. Hermes cron sessions execute but never write back to state file
2. A2A bus task queue → Hermes heartbeat pickup is not wired

This script is meant to be called from Hermes' cron heartbeat (every 30m).
It:
  1. Writes the current timestamp to the Hermes state file
  2. Scans the canonical task queue for unclaimed tasks matching Hermes'
     capabilities
  3. Claims matching tasks through the canonical lifecycle mutation
     (``a2a_task_lifecycle.claim_task``) — this script never rewrites the
     queue file itself, so there is exactly one mutation protocol and no
     unsynchronized whole-file rewrite racing ``claim_task``/``close_task``
  4. Returns claimed task IDs for Hermes to execute

Usage (from Hermes cron):
  python3 scripts/hermes_heartbeat_poll.py

  # With custom state dir
  DHARMA_HOME=~/.dharma python3 scripts/hermes_heartbeat_poll.py

  # Dry run (no state writes, no claims)
  python3 scripts/hermes_heartbeat_poll.py --dry-run

Exit codes:
  0 — success (heartbeat written, tasks polled)
  1 — error
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dharma_swarm.operator_core.a2a_task_lifecycle import (
        A2ATaskLifecycleError,
        claim_task,
        queue_path,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by cron layout only
    # Direct-checkout cron invocation: ``python3 scripts/hermes_heartbeat_poll.py``
    # from the repository root puts ``scripts/`` (not its parent) on sys.path,
    # so the package import needs the repo root bootstrapped explicitly.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dharma_swarm.operator_core.a2a_task_lifecycle import (
        A2ATaskLifecycleError,
        claim_task,
        queue_path,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DHARMA_HOME = Path(os.environ.get("DHARMA_HOME", Path.home() / ".dharma"))

# Hermes state file — documents Hermes' liveness
HERMES_STATE_FILE = DHARMA_HOME / "agents" / "hermes-m5" / "state.json"

# Hermes agent ID
HERMES_AGENT_ID = "hermes-m5"

# Capabilities Hermes can claim tasks for
HERMES_CAPABILITIES = frozenset({
    "filesystem_sync",
    "git_pull",
    "git_push",
    "cron_management",
    "state_persistence",
    "inter_agent_relay",
    "inbox_delivery",
    "heartbeat",
})


def _queue_root(queue_file: Path) -> Path:
    """Return the state root that owns a canonical queue file path.

    ``<root>/a2a_bus/tasks/queue.jsonl`` → ``<root>``. Used so the scan and
    the canonical ``claim_task`` mutation always target the same state root,
    even when the queue path was supplied explicitly (tests, tooling).
    """

    return queue_file.parent.parent.parent


# ---------------------------------------------------------------------------
# State file writer
# ---------------------------------------------------------------------------


def write_heartbeat_state(dry_run: bool = False) -> dict[str, Any]:
    """Write current heartbeat timestamp to Hermes state file.

    Atomic write (temp file + rename) to avoid corruption.
    """
    now = datetime.now(timezone.utc)
    state = {
        "agent_id": HERMES_AGENT_ID,
        "last_heartbeat": now.isoformat(),
        "status": "alive",
        "capabilities": sorted(HERMES_CAPABILITIES),
        "uptime_check": True,
    }

    # Read existing state to preserve cumulative fields
    existing: dict[str, Any] = {}
    if HERMES_STATE_FILE.exists():
        try:
            existing = json.loads(HERMES_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Preserve heartbeat_count
    heartbeat_count = existing.get("heartbeat_count", 0) + 1
    state["heartbeat_count"] = heartbeat_count
    state["first_seen"] = existing.get("first_seen", now.isoformat())

    if dry_run:
        logger.info("[DRY-RUN] Would write state: %s", json.dumps(state, indent=2))
        return state

    # Atomic write
    HERMES_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(HERMES_STATE_FILE.parent),
        suffix=".tmp",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, str(HERMES_STATE_FILE))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    logger.info("Heartbeat #%d written to %s", heartbeat_count, HERMES_STATE_FILE)
    return state


# ---------------------------------------------------------------------------
# Queue poller
# ---------------------------------------------------------------------------


def poll_queue(
    dry_run: bool = False,
    *,
    queue_file: Path | None = None,
) -> list[dict[str, Any]]:
    """Scan the canonical queue for claimable tasks; claim them canonically.

    The scan is read-only. Matching tasks are claimed through
    ``a2a_task_lifecycle.claim_task`` (which re-reads the queue, mutates the
    task, rewrites the file atomically, and mirrors the task into the agent
    inbox). This module performs no queue writes of its own.

    When another agent claims or closes a matching task between the scan and
    the claim, ``claim_task`` raises and the task is skipped — the canonical
    writer's view wins, never a stale local snapshot.
    """

    resolved = Path(queue_file) if queue_file is not None else queue_path()
    if not resolved.exists():
        logger.info("No queue file at %s — nothing to poll", resolved)
        return []

    state_root = _queue_root(resolved)
    claimed: list[dict[str, Any]] = []

    try:
        lines = resolved.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to read queue: %s", exc)
        return []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            task = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(task, dict):
            continue

        # Check if claimable
        if task.get("status") != "pending":
            continue
        if task.get("claimed_by") is not None:
            continue

        # Check capability match. Missing/empty task type is not claimable:
        # Hermes must only consume tasks with an explicit supported capability.
        required_cap = task.get("capability") or task.get("type")
        if not isinstance(required_cap, str) or not required_cap.strip():
            continue
        required_cap = required_cap.strip()
        if required_cap not in HERMES_CAPABILITIES:
            continue

        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            continue
        task_id = task_id.strip()

        if dry_run:
            claimed.append(dict(task))
            logger.info(
                "[DRY-RUN] Would claim task %s (capability=%s): %s",
                task_id,
                required_cap,
                str(task.get("description", task.get("title", "untitled")))[:80],
            )
            continue

        try:
            result = claim_task(
                task_id,
                agent_uid=HERMES_AGENT_ID,
                state_root=state_root,
            )
        except A2ATaskLifecycleError as exc:
            # Lost the race (already claimed/closed by a canonical writer) or
            # the task cannot be claimed — skip without touching the queue.
            logger.info("Skipping task %s: %s", task_id, exc)
            continue

        claimed.append(result)
        logger.info(
            "Claimed task %s (capability=%s): %s",
            task_id,
            required_cap,
            str(result.get("description", result.get("title", "untitled")))[:80],
        )

    return claimed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hermes M5 heartbeat state writer + queue poller."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )
    args = parser.parse_args()

    try:
        state = write_heartbeat_state(dry_run=args.dry_run)
        claimed = poll_queue(dry_run=args.dry_run)

        # Summary output for cron log
        summary = {
            "heartbeat": state.get("last_heartbeat"),
            "heartbeat_count": state.get("heartbeat_count"),
            "tasks_claimed": len(claimed),
            "claimed_ids": [t.get("id") for t in claimed],
        }
        print(json.dumps(summary, indent=2))
        return 0

    except Exception as exc:
        logger.error("Heartbeat poll failed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
