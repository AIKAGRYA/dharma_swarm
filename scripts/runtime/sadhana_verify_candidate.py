#!/usr/bin/env python3
"""Run one roster-bound model verifier and record its campaign verdict."""

from __future__ import annotations

# ruff: noqa: E402

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_campaign import (
    CAMPAIGN_SESSION_PREFIX,
    CampaignConfig,
    CampaignSupervisor,
    observer_only_adapter,
)
from dharma_swarm.mission_control_contract import MissionControlError, stable_id
from dharma_swarm.mission_control_execution import EXECUTION_METADATA_KEY
from dharma_swarm.mission_control_roster import (
    CampaignRosterError,
    load_campaign_agent_roster,
)
from dharma_swarm.mission_control_service import CampaignControlGate
from dharma_swarm.mission_control_verifier import (
    ModelVerifierError,
    run_verifier,
)
from dharma_swarm.providers import OllamaProvider
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


def _absolute_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise argparse.ArgumentTypeError("path must be absolute")
    return Path(os.path.abspath(candidate))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True, type=_absolute_path)
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--policy-digest", required=True)
    parser.add_argument("--agent-roster", required=True, type=_absolute_path)
    parser.add_argument("--agent-roster-sha256", required=True)
    parser.add_argument("--objective-sha256", required=True)
    parser.add_argument("--verifier-seat", default="sadhana-nemotron")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--verifier-lock-path", type=_absolute_path, default=None)
    parser.add_argument("--control-gate-path", type=_absolute_path, default=None)
    return parser


def _runtime(state_dir: Path) -> RuntimeStateStore:
    return RuntimeStateStore(
        state_dir / "state" / "runtime.db",
        include_memory_plane=False,
    )


async def _board(state_dir: Path) -> TaskBoard:
    board = TaskBoard(state_dir / "db" / "tasks.db")
    await board.init_db()
    return board


async def _campaign_config(
    runtime: RuntimeStateStore,
    mission_id: str,
) -> CampaignConfig:
    session = await runtime.get_session(CAMPAIGN_SESSION_PREFIX + mission_id)
    if session is None:
        raise MissionControlError("campaign has not been prepared")
    raw = session.metadata.get("config")
    if not isinstance(raw, Mapping):
        raise MissionControlError("campaign session has no valid config")
    try:
        config = CampaignConfig(**dict(raw))
    except (TypeError, ValueError) as exc:
        raise MissionControlError("campaign recorded config is invalid") from exc
    if config.mission_id != mission_id:
        raise MissionControlError("campaign config names a foreign mission")
    return config


async def verify_candidate(args: argparse.Namespace) -> dict[str, Any]:
    roster = load_campaign_agent_roster(
        args.agent_roster,
        expected_sha256=args.agent_roster_sha256,
        campaign_id=args.mission_id,
        objective_sha256=args.objective_sha256,
    )
    runtime = _runtime(args.state_dir)
    await runtime.init_db()
    config = await _campaign_config(runtime, args.mission_id)
    board = await _board(args.state_dir)
    control = MissionControl(board, runtime)
    task = await board.get(args.task_id)
    if task is None or task.metadata.get("mission_id") != args.mission_id:
        raise MissionControlError("candidate task is absent or foreign")
    marker = task.metadata.get(EXECUTION_METADATA_KEY)
    if not isinstance(marker, Mapping):
        raise MissionControlError("candidate task has no owner execution marker")
    dispatch_key = marker.get("dispatch_key", "default")
    if not isinstance(dispatch_key, str):
        raise MissionControlError("candidate dispatch key is invalid")
    owner_reader = observer_only_adapter(control, board, runtime)
    ref = await owner_reader.recover(
        args.mission_id,
        args.task_id,
        dispatch_key=dispatch_key,
    )
    if ref is None:
        raise MissionControlError("candidate owner execution was not found")
    candidate = await owner_reader.observe(ref)
    lock_path = args.verifier_lock_path or (
        args.state_dir
        / "leases"
        / "verifiers"
        / f"{stable_id('campaign_verifier_lock', args.mission_id, args.task_id, str(args.attempt))}.lock"
    )
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if lock_path.parent.stat().st_mode & 0o077:
        raise ModelVerifierError("verifier lock directory is not private")
    seat_matches = [seat for seat in roster.seats if seat.name == args.verifier_seat]
    if len(seat_matches) != 1:
        raise ModelVerifierError("verifier seat is absent or ambiguous")
    provider = OllamaProvider(model=seat_matches[0].model)
    try:
        acceptance = await run_verifier(
            runtime=runtime,
            provider=provider,
            roster=roster,
            verifier_seat_name=args.verifier_seat,
            task=task,
            candidate=candidate,
            policy_digest=args.policy_digest,
            lock_path=lock_path,
            attempt_number=args.attempt,
        )
    finally:
        await provider.close()
    supervisor = CampaignSupervisor(
        config,
        control,
        board,
        runtime,
        owner_reader,
    )
    control_gate = args.control_gate_path or (
        args.state_dir / "mission_control" / "campaign-supervisor.lock.control"
    )
    async with CampaignControlGate(control_gate):
        receipt = await supervisor.accept(acceptance)
    return {
        "schema_version": "dharma.sadhana.verifier_cli.v1",
        "mission_id": args.mission_id,
        "task_id": args.task_id,
        "status": receipt.status,
        "acceptance_receipt_id": receipt.receipt_id,
        "producer_run_id": acceptance.producer_run_id,
        "producer_model": acceptance.producer_model_family,
        "verifier_run_id": acceptance.verifier_run_id,
        "verifier_model": acceptance.verifier_model_family,
        "verifier_agent_id": acceptance.verifier_agent_id,
        "provider_effect": "inference_only",
        "tools_used": False,
        "acceptance_is_independent": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = asyncio.run(verify_candidate(args))
        code = 0 if payload["status"] == "accepted" else 3
    except (
        CampaignRosterError,
        MissionControlError,
        ModelVerifierError,
        OSError,
        ValueError,
    ) as exc:
        payload = {
            "schema_version": "dharma.sadhana.verifier_cli.v1",
            "status": "blocked",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "acceptance_is_independent": False,
        }
        code = 2
    print(json.dumps(payload, allow_nan=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
