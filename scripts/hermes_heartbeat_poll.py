#!/usr/bin/env python3
"""hermes_heartbeat_poll.py — Hermes M5 heartbeat state writer + queue poller.

Fixes two protocol gaps identified in the 2026-05-23 morning briefing:
1. Hermes cron sessions execute but never write back to state file
2. A2A bus task queue → Hermes heartbeat pickup is not wired

This script is meant to be called from Hermes' cron heartbeat (every 30m).
It:
  1. Writes the current timestamp to the Hermes state file
  2. Polls queue.jsonl for unclaimed tasks matching Hermes' capabilities
  3. Claims any matching tasks (sets claimed_by, claimed_at)
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
import fcntl
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.a2a_task_lifecycle import queue_path

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

# A2A bus queue — file-based task queue for inter-agent coordination.
# Sourced from the canonical writer (a2a_task_lifecycle.queue_path) so Hermes
# reads the same ``a2a_bus/tasks/queue.jsonl`` surface every other consumer
# writes/reads — not the legacy root ``a2a_bus/queue.jsonl``.
QUEUE_FILE = queue_path(DHARMA_HOME)

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


def queue_lock_file() -> Path:
    """Return the advisory lock file used for queue read-modify-write cycles."""

    return QUEUE_FILE.with_suffix(QUEUE_FILE.suffix + ".lock")


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


def poll_queue(dry_run: bool = False) -> list[dict[str, Any]]:
    """Poll queue.jsonl for unclaimed tasks matching Hermes capabilities.

    Returns list of claimed tasks.
    """
    if not QUEUE_FILE.exists():
        logger.info("No queue file at %s — nothing to poll", QUEUE_FILE)
        return []

    lock_path = queue_lock_file()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            return _poll_queue_locked(dry_run=dry_run)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _poll_queue_locked(dry_run: bool = False) -> list[dict[str, Any]]:
    """Poll and optionally rewrite the queue while the caller holds the lock."""

    try:
        lines = QUEUE_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed to read queue: %s", exc)
        return []

    records: list[tuple[str, dict[str, Any] | None]] = []
    claimed: list[dict[str, Any]] = []
    modified = False
    now_iso = datetime.now(timezone.utc).isoformat()

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            records.append((raw_line, None))
            continue
        try:
            task = json.loads(line)
        except json.JSONDecodeError:
            records.append((raw_line, None))
            continue

        records.append(("", task))

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

        # Claim it
        if not dry_run:
            task["claimed_by"] = HERMES_AGENT_ID
            task["claimed_at"] = now_iso
            task["status"] = "claimed"
            modified = True

        claimed.append(task)
        logger.info(
            "%sClaimed task %s (capability=%s): %s",
            "[DRY-RUN] " if dry_run else "",
            task.get("id", f"line-{i}"),
            required_cap,
            task.get("description", task.get("title", "untitled"))[:80],
        )

    # Write back modified queue. A failed write must not be reported as a
    # successful claim: callers depend on claimed IDs as dispatch evidence.
    if modified and not dry_run:
        new_lines = []
        for raw_line, task in records:
            if task is None:
                new_lines.append(raw_line)
            else:
                new_lines.append(json.dumps(task, separators=(",", ":")))
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(QUEUE_FILE.parent),
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            os.replace(tmp_path, str(QUEUE_FILE))
        except Exception as exc:
            logger.warning("Failed to write back queue: %s", exc)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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
