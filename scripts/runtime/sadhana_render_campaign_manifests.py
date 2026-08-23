#!/usr/bin/env python3.11
"""Render the three exact SADHANA runtime manifests after bootstrap.

This command must run while dispatch is disabled.  It inspects the already
bootstrapped MissionControl state, ingests prompt-only observed evidence, and
writes only ``observed-inputs.json``, ``held-out-oracle.json``, and
``authority-manifest.json``.  It does not spawn agents or create leases.
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
    GoalContractError,
    campaign_bootstrap_lock,
    load_goal_contract,
)
from dharma_swarm.mission_control_contract import MissionControlError  # noqa: E402
from dharma_swarm.mission_control_roster import (  # noqa: E402
    CampaignRosterError,
    load_campaign_agent_roster,
)
from dharma_swarm.mission_control_runtime_manifests import (  # noqa: E402
    RuntimeManifestPins,
    render_runtime_manifests,
)
from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: E402
from dharma_swarm.task_board import TaskBoard, TaskBoardError  # noqa: E402


def _absolute(value: str) -> Path:
    path = Path(str(value or "").strip()).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("path must be absolute")
    return path


async def _render(args: argparse.Namespace) -> str:
    portfolio = load_goal_contract(args.contracts)
    runtime = RuntimeStateStore(
        args.state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )
    board = TaskBoard(args.state_dir / "db" / "tasks.db", runtime_state=runtime)
    await runtime.init_db()
    await board.init_db()
    roster = load_campaign_agent_roster(
        args.roster,
        expected_sha256=args.roster_sha256,
        campaign_id=portfolio.campaign_id,
        objective_sha256=args.objective_sha256,
    )
    pins = RuntimeManifestPins(
        evaluator_path=args.evaluator_path,
        evaluator_sha256=args.evaluator_sha256,
        policy_path=args.policy_path,
        policy_sha256=args.policy_sha256,
        operator_control_semantics_sha256=args.operator_control_semantics_sha256,
        operator_control_authority_binding_sha256=(
            args.operator_control_authority_binding_sha256
        ),
        deployment_authority_topology_sha256=(
            args.deployment_authority_topology_sha256
        ),
        deployment_authority_credential_clarification_sha256=(
            args.deployment_authority_credential_clarification_sha256
        ),
    )
    lock_path = args.state_dir / "locks" / "sadhana-bootstrap.lock"
    with campaign_bootstrap_lock(lock_path) as lock:
        result = await render_runtime_manifests(
            portfolio,
            MissionControl(board, runtime),
            board,
            runtime,
            roster,
            observed_source_path=args.observed_source,
            output_root=args.output_root,
            verifier_seat_name=args.verifier_seat,
            pins=pins,
            operator_id=args.operator_id,
            lock=lock,
        )
    return result.to_json()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bind exact bootstrap task identities into three runtime manifests."
    )
    parser.add_argument("--contracts", required=True, type=_absolute)
    parser.add_argument("--observed-source", required=True, type=_absolute)
    parser.add_argument("--roster", required=True, type=_absolute)
    parser.add_argument("--roster-sha256", required=True)
    parser.add_argument("--objective-sha256", required=True)
    parser.add_argument("--state-dir", required=True, type=_absolute)
    parser.add_argument("--output-root", required=True, type=_absolute)
    parser.add_argument("--operator-id", default="operator")
    parser.add_argument("--verifier-seat", required=True)
    parser.add_argument("--evaluator-path", required=True, type=_absolute)
    parser.add_argument("--evaluator-sha256", required=True)
    parser.add_argument("--policy-path", required=True, type=_absolute)
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--operator-control-semantics-sha256", required=True)
    parser.add_argument(
        "--operator-control-authority-binding-sha256",
        required=True,
    )
    parser.add_argument("--deployment-authority-topology-sha256", required=True)
    parser.add_argument(
        "--deployment-authority-credential-clarification-sha256",
        required=True,
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
        output = asyncio.run(_render(args))
    except (
        BootstrapLockError,
        CampaignRosterError,
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
