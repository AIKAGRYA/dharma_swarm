#!/usr/bin/env python3
"""One-shot, authority-neutral initialization of the pinned SADHANA campaign.

Example systemd ``ExecStartPre`` command::

    python3 scripts/runtime/sadhana_campaign_bootstrap.py initialize \
      --contracts /path/to/goal-contracts.v1.json \
      --state-dir /path/to/campaign-state --operator-id operator

The command validates the external contract before creating a lock, directory,
or database.  It seeds MissionControl owner state only; it never starts the
campaign supervisor and never binds dispatch authority.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import sqlite3
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.mission_control import MissionControl  # noqa: E402
from dharma_swarm.mission_control_bootstrap import (  # noqa: E402
    GoalContractError,
    GoalPortfolio,
    initialize_sadhana_campaign,
    load_goal_contract,
)
from dharma_swarm.mission_control_contract import MissionControlError  # noqa: E402
from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: E402
from dharma_swarm.task_board import TaskBoard, TaskBoardError  # noqa: E402


class BootstrapLockError(RuntimeError):
    """Raised when the one-shot cross-process bootstrap lock is unavailable."""


def _canonical_state_dir(value: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise argparse.ArgumentTypeError("state directory is required")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("state directory must be absolute")
    return path


def _require_safe_lock_file(descriptor: int) -> None:
    details = os.fstat(descriptor)
    if not stat.S_ISREG(details.st_mode):
        raise BootstrapLockError("bootstrap lock must be a regular file")
    if details.st_nlink != 1:
        raise BootstrapLockError("bootstrap lock must have exactly one hard link")
    if hasattr(os, "getuid") and details.st_uid != os.getuid():
        raise BootstrapLockError("bootstrap lock must be owned by the current account")
    if stat.S_IMODE(details.st_mode) & 0o022:
        raise BootstrapLockError("bootstrap lock must not be group/world writable")


@contextmanager
def _bootstrap_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise BootstrapLockError("bootstrap lock requires O_NOFOLLOW support")
    flags = os.O_CREAT | os.O_RDWR | nofollow | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(os.fspath(path), flags, 0o600)
    except OSError as exc:
        raise BootstrapLockError(f"cannot securely open bootstrap lock: {exc}") from exc
    acquired = False
    try:
        _require_safe_lock_file(descriptor)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BootstrapLockError("another SADHANA bootstrap is active") from exc
        acquired = True
        yield
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


async def _initialize(
    portfolio: GoalPortfolio,
    *,
    state_dir: Path,
    operator_id: str,
) -> str:
    runtime = RuntimeStateStore(
        state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )
    task_db = state_dir / "db" / "tasks.db"
    task_db.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    board = TaskBoard(task_db, runtime_state=runtime)
    await runtime.init_db()
    await board.init_db()
    result = await initialize_sadhana_campaign(
        portfolio,
        MissionControl(board, runtime),
        board,
        operator_id=operator_id,
    )
    return result.to_json()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize the exact authority-unbound SADHANA mission once."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    initialize = subcommands.add_parser(
        "initialize",
        help="validate the pinned contract and idempotently seed MissionControl",
    )
    initialize.add_argument(
        "--contracts",
        required=True,
        type=Path,
        help="exact external goal-contracts.v1.json path",
    )
    initialize.add_argument(
        "--state-dir",
        required=True,
        type=_canonical_state_dir,
        help="campaign state root shared with the supervisor",
    )
    initialize.add_argument(
        "--operator-id",
        default="operator",
        help="stable MissionControl operator identifier (default: operator)",
    )
    return parser


def _error_json(exc: BaseException) -> str:
    return (
        json.dumps(
            {"error": str(exc), "error_type": type(exc).__name__, "status": "error"},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        # Contract validation intentionally precedes every filesystem effect.
        portfolio = load_goal_contract(args.contracts)
        lock_path = args.state_dir / "locks" / "sadhana-bootstrap.lock"
        with _bootstrap_lock(lock_path):
            output = asyncio.run(
                _initialize(
                    portfolio,
                    state_dir=args.state_dir,
                    operator_id=args.operator_id,
                )
            )
    except (
        BootstrapLockError,
        GoalContractError,
        MissionControlError,
        OSError,
        sqlite3.Error,
        TaskBoardError,
    ) as exc:
        sys.stderr.write(_error_json(exc))
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
