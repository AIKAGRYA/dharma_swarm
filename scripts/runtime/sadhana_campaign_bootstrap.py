#!/usr/bin/env python3.11
"""One-shot, authority-neutral initialization of the pinned SADHANA campaign.

Example systemd ``ExecStartPre`` command (use absolute paths and the project's
Python 3.11+ environment; do not rely on the host ``python3`` alias)::

    ExecStartPre=/absolute/repo/.venv/bin/python \
      /absolute/repo/scripts/runtime/sadhana_campaign_bootstrap.py initialize \
      --contracts /path/to/goal-contracts.v1.json \
      --state-dir /path/to/campaign-state --operator-id operator

The command validates the external contract before creating a lock, directory,
or database.  It seeds MissionControl owner state only; it never starts the
campaign supervisor and never binds dispatch authority.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from typing import Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.mission_control import MissionControl  # noqa: E402
from dharma_swarm.mission_control_bootstrap import (  # noqa: E402
    BootstrapLockError,
    CampaignBootstrapLock,
    GoalContractError,
    GoalPortfolio,
    campaign_bootstrap_lock,
    initialize_sadhana_campaign,
    load_goal_contract,
)
from dharma_swarm.mission_control_contract import MissionControlError  # noqa: E402
from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: E402
from dharma_swarm.task_board import TaskBoard, TaskBoardError  # noqa: E402


def _canonical_state_dir(value: str) -> Path:
    text = str(value or "").strip()
    if not text:
        raise argparse.ArgumentTypeError("state directory is required")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("state directory must be absolute")
    return path


async def _initialize(
    portfolio: GoalPortfolio,
    *,
    state_dir: Path,
    operator_id: str,
    lock: CampaignBootstrapLock,
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
        operator_id=operator_id,
        lock=lock,
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
        with campaign_bootstrap_lock(lock_path) as lock:
            output = asyncio.run(
                _initialize(
                    portfolio,
                    state_dir=args.state_dir,
                    operator_id=args.operator_id,
                    lock=lock,
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
