#!/usr/bin/env python3
"""Plan B L2 — persist IdentityMonitor.measure() snapshots to a time-series JSONL.

The TCS metric the system claims to optimize against has no historical record:
``IdentityMonitor._history`` is an in-memory ``deque(maxlen=1000)`` that resets on
every process restart. This script samples the public API and appends one JSON row
per invocation to ``~/.dharma/identity_history.jsonl``, unblocking every metric
analysis that depends on a TCS time-series (Plan B L3 estimator, ACS, etc).

Non-invasive: no edits to ``dharma_swarm/identity.py``. Intended to be invoked from
the unified cron scheduler after Plan v2.1 Phase 2; safe to run manually before then.

Usage: ``python -m scripts.tcs_history_writer`` (or direct invocation).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.identity import IdentityMonitor  # noqa: E402

OUT_PATH = Path(os.path.expanduser("~/.dharma/identity_history.jsonl"))
LOCK_PATH = Path(os.path.expanduser("~/.dharma/identity_history.lock"))


async def _measure_once() -> dict:
    monitor = IdentityMonitor()
    state = await monitor.measure()
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "id": state.id,
        "tcs": state.tcs,
        "gpr": state.gpr,
        "bsi": state.bsi,
        "rm": state.rm,
        "regime": state.regime,
        "correction_issued": state.correction_issued,
        "snapshot_ts": state.timestamp.isoformat() if state.timestamp else None,
    }


def _append_atomic(row: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, separators=(",", ":")) + "\n"
    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def _try_lock() -> bool:
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def main() -> int:
    if not _try_lock():
        print("tcs_history_writer: another instance is running; skipping", file=sys.stderr)
        return 0
    try:
        row = asyncio.run(_measure_once())
        _append_atomic(row)
        print(f"tcs_history_writer: wrote tcs={row['tcs']:.4f} regime={row['regime']} -> {OUT_PATH}")
        return 0
    finally:
        _release_lock()


if __name__ == "__main__":
    sys.exit(main())
