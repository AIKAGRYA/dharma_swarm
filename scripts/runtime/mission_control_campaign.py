#!/usr/bin/env python3
"""Run and inspect the durable Mission Control campaign supervisor."""

from __future__ import annotations

# ruff: noqa: E402

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_activation import activation_barrier_from_config
from dharma_swarm.mission_control_authority import (
    FileExecutionLeaseAuthorityVerifier,
    GovernedCampaignTaskDispatcher,
)
from dharma_swarm.mission_control_auto_verifier import AutomaticCandidateVerifier
from dharma_swarm.mission_control_campaign import (
    CAMPAIGN_SESSION_PREFIX,
    CAMPAIGN_SCHEMA_VERSION,
    CampaignConfig,
    CampaignSupervisor,
    observer_only_adapter,
)
from dharma_swarm.mission_control_binding import bind_campaign_authority
from dharma_swarm.mission_control_observed_input import (
    ingest_observed_input_manifest,
)
from dharma_swarm.mission_control_contract import (
    MissionControlError,
    clean_identifier,
    stable_id,
)
from dharma_swarm.mission_control_dispatch import GovernedMissionDispatcher
from dharma_swarm.mission_control_evidence import IndependentAcceptance
from dharma_swarm.mission_control_execution import OrchestratorMissionAdapter
from dharma_swarm.mission_control_held_out_oracle import (
    HeldOutOracleManifest,
    load_held_out_oracle_manifest,
)
from dharma_swarm.mission_control_oracle_launcher import (
    FilesystemOracleSandboxLauncher,
)
from dharma_swarm.mission_control_operator_runtime import (
    operator_control_reconciler_from_config,
)
from dharma_swarm.mission_control_runtime_manifests import (
    add_campaign_runtime_arguments,
)
from dharma_swarm.mission_control_roster import (
    CampaignAgentSeat,
    CampaignAgentRoster,
    CampaignRosterError,
    ensure_campaign_agent_roster,
    load_campaign_agent_roster,
)
from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.mission_control_service import (
    CampaignControlGate,
    CampaignPaths,
    CampaignProjectionError,
    CampaignService,
    CampaignWriterBusy,
    CampaignWriterLock,
    materialize_projection_liveness,
    projection_confirms_start,
    read_campaign_projection,
    read_writer_lock_identity,
    writer_lock_is_held,
)
from dharma_swarm.operator_core.execution_lease import default_lease_root
from dharma_swarm.providers import OllamaProvider
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


def _positive_finite(value: float, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{label} must be a positive finite number")
    return float(value)


def default_campaign_paths(
    state_dir: Path | str,
    mission_id: str,
) -> CampaignPaths:
    mission_id = clean_identifier(mission_id, "mission_id")
    root = Path(state_dir).expanduser().resolve(strict=False) / "mission_control"
    campaign_key = stable_id("campaign", mission_id)
    return CampaignPaths(
        lock_path=root / "campaign-supervisor.lock",
        control_gate_path=root / "campaign-supervisor.lock.control",
        projection_path=root / "campaigns" / campaign_key / "status.json",
        log_path=root / "campaigns" / campaign_key / "supervisor.log",
    )


def _paths(args: argparse.Namespace) -> CampaignPaths:
    defaults = default_campaign_paths(args.state_dir, args.mission_id)
    return CampaignPaths(
        lock_path=Path(args.lock_path).expanduser().resolve(strict=False)
        if args.lock_path
        else defaults.lock_path,
        control_gate_path=(
            Path(f"{args.lock_path}.control").expanduser().resolve(strict=False)
            if args.lock_path
            else defaults.control_gate_path
        ),
        projection_path=Path(args.projection_path).expanduser().resolve(strict=False)
        if args.projection_path
        else defaults.projection_path,
        log_path=Path(getattr(args, "log_path", "") or defaults.log_path)
        .expanduser()
        .resolve(strict=False),
    )


def _runtime_store(state_dir: Path | str) -> RuntimeStateStore:
    return RuntimeStateStore(
        Path(state_dir).expanduser().resolve(strict=False) / "state" / "runtime.db",
        include_memory_plane=False,
    )


async def _board(state_dir: Path | str) -> TaskBoard:
    db_path = Path(state_dir).expanduser().resolve(strict=False) / "db" / "tasks.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    board = TaskBoard(db_path)
    await board.init_db()
    return board


def _requested_config(args: argparse.Namespace) -> CampaignConfig:
    return CampaignConfig(
        mission_id=args.mission_id,
        operator_id=args.operator_id,
        canary_task_id=args.canary_task_id,
        max_dispatch_per_cycle=args.max_dispatch_per_cycle,
        cycle_interval_seconds=args.cycle_interval_seconds,
        freshness_seconds=args.freshness_seconds,
        held_out_oracle_digest=args.held_out_oracle_digest,
    )


def _requested_roster(args: argparse.Namespace) -> CampaignAgentRoster:
    values = {
        "path": str(getattr(args, "agent_roster", "") or ""),
        "sha256": str(getattr(args, "agent_roster_sha256", "") or ""),
        "objective_sha256": str(getattr(args, "objective_sha256", "") or ""),
    }
    configured = {key for key, value in values.items() if value}
    if not configured:
        raise CampaignRosterError("campaign roster configuration is required")
    if configured != set(values):
        missing = sorted(set(values) - configured)
        raise CampaignRosterError(
            "campaign roster configuration is partial: " + ",".join(missing)
        )
    return load_campaign_agent_roster(
        Path(values["path"]),
        expected_sha256=values["sha256"],
        campaign_id=args.mission_id,
        objective_sha256=values["objective_sha256"],
    )


def _requested_verifier_seat(
    roster: CampaignAgentRoster,
    name: str,
) -> CampaignAgentSeat:
    matches = [seat for seat in roster.seats if seat.name == name]
    if len(matches) != 1:
        raise CampaignRosterError("campaign verifier seat is absent or ambiguous")
    seat = matches[0]
    if seat.role is not AgentRole.VALIDATOR or seat.provider is not ProviderType.OLLAMA:
        raise CampaignRosterError("campaign verifier seat is not an Ollama validator")
    return seat


def _requested_held_out_manifest(
    args: argparse.Namespace,
    config: CampaignConfig,
) -> HeldOutOracleManifest:
    if not config.held_out_oracle_digest:
        raise MissionControlError("campaign held-out oracle digest is required")
    manifest = load_held_out_oracle_manifest(
        Path(args.held_out_oracle_manifest).expanduser().absolute(),
        expected_digest=config.held_out_oracle_digest,
    )
    if (
        manifest.campaign_id != config.mission_id
        or manifest.mission_id != config.mission_id
    ):
        raise MissionControlError("held-out oracle manifest names a foreign campaign")
    return manifest


async def _recorded_config(
    runtime: RuntimeStateStore,
    mission_id: str,
) -> CampaignConfig | None:
    session = await runtime.get_session(CAMPAIGN_SESSION_PREFIX + mission_id)
    if session is None:
        return None
    raw = session.metadata.get("config")
    if not isinstance(raw, Mapping):
        raise MissionControlError("campaign session has no valid recorded config")
    try:
        return CampaignConfig(**dict(raw))
    except (TypeError, ValueError) as exc:
        raise MissionControlError("campaign recorded config is invalid") from exc


async def _existing_supervisor(
    state_dir: Path | str,
    mission_id: str,
) -> tuple[CampaignSupervisor, RuntimeStateStore]:
    runtime = _runtime_store(state_dir)
    await runtime.init_db()
    config = await _recorded_config(runtime, mission_id)
    if config is None:
        raise MissionControlError("campaign has not been started")
    board = await _board(state_dir)
    control = MissionControl(board, runtime)
    return (
        CampaignSupervisor(
            config,
            control,
            board,
            runtime,
            observer_only_adapter(control, board, runtime),
        ),
        runtime,
    )


async def _initialize_campaign(
    state_dir: Path | str,
    config: CampaignConfig,
    control_gate_path: Path,
):
    runtime = _runtime_store(state_dir)
    await runtime.init_db()
    board = await _board(state_dir)
    control = MissionControl(board, runtime)
    supervisor = CampaignSupervisor(
        config,
        control,
        board,
        runtime,
        observer_only_adapter(control, board, runtime),
    )
    async with CampaignControlGate(control_gate_path):
        return await supervisor.start()


async def prepare_campaign(args: argparse.Namespace) -> dict[str, Any]:
    """Create one campaign session without booting an executor or doing work."""
    config = _requested_config(args)
    state_dir = Path(args.state_dir).expanduser().resolve(strict=False)
    paths = _paths(args)
    writer_lock = CampaignWriterLock(paths.lock_path)
    writer_lock.acquire()
    try:
        runtime = _runtime_store(state_dir)
        await runtime.init_db()
        board = await _board(state_dir)
        control = MissionControl(board, runtime)
        supervisor = CampaignSupervisor(
            config,
            control,
            board,
            runtime,
            observer_only_adapter(control, board, runtime),
        )
        async with CampaignControlGate(paths.control_gate_path):
            existing = await runtime.get_session(config.session_id)
            initialized = existing is None
            if initialized:
                session = await supervisor.start()
            else:
                recorded = await _recorded_config(runtime, config.mission_id)
                if recorded is None or recorded.digest != config.digest:
                    raise MissionControlError(
                        "requested prepare config conflicts with recorded campaign"
                    )
                if (
                    existing.metadata.get("schema_version") != CAMPAIGN_SCHEMA_VERSION
                    or existing.metadata.get("mission_id") != config.mission_id
                    or existing.metadata.get("config_digest") != config.digest
                ):
                    raise MissionControlError(
                        "prepared campaign session has a foreign identity"
                    )
                generation = existing.metadata.get("generation")
                if (
                    isinstance(generation, bool)
                    or not isinstance(generation, int)
                    or generation < 1
                ):
                    raise MissionControlError("prepared campaign generation is invalid")
                session = existing
        prepared = (
            session.status in {"active", "paused"}
            and session.metadata.get("stop_requested") is not True
        )
        return {
            "status": "prepared" if prepared else "stopped",
            "initialized": initialized,
            "campaign_status": session.status,
            "mission_id": config.mission_id,
            "session_id": session.session_id,
            "config_digest": config.digest,
            "generation": session.metadata["generation"],
            "provider_effect_performed": False,
            "tool_effect_performed": False,
            "work_performed": False,
            "lock_path": str(paths.lock_path),
            "control_gate_path": str(paths.control_gate_path),
        }
    finally:
        writer_lock.release()


def _acquire_writer_handoff(
    writer_lock: CampaignWriterLock,
    timeout: float,
) -> None:
    timeout = _positive_finite(timeout, "writer_handoff_timeout")
    deadline = time.monotonic() + timeout
    while True:
        try:
            writer_lock.acquire()
            return
        except CampaignWriterBusy:
            if time.monotonic() >= deadline:
                raise
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


async def run_campaign(args: argparse.Namespace) -> dict[str, Any]:
    """Boot the real swarm executor and reconcile until stopped or bounded."""
    from dharma_swarm.swarm import SwarmManager

    _positive_finite(args.shutdown_timeout, "shutdown_timeout")
    _positive_finite(args.writer_handoff_timeout, "writer_handoff_timeout")
    if args.fast_boot:
        os.environ["DHARMA_FAST_BOOT"] = "1"
    state_dir = Path(args.state_dir).expanduser().resolve(strict=False)
    paths = _paths(args)
    requested_roster = _requested_roster(args)
    requested = _requested_config(args)
    activation_barrier = activation_barrier_from_config(
        args.mission_id,
        args.observer_health_receipt,
        args.observer_health_receipt_sha256,
    )
    operator_control_reconciler = operator_control_reconciler_from_config(
        args.mission_id,
        normal_inbox=args.operator_control_normal_inbox,
        inflight_inbox=args.operator_control_inflight_inbox,
        applied_inbox=args.operator_control_applied_inbox,
        rejected_inbox=args.operator_control_rejected_inbox,
        max_candidates_per_cycle=args.operator_control_max_candidates_per_cycle,
    )
    verifier_seat = _requested_verifier_seat(requested_roster, args.verifier_seat)
    held_out_manifest = _requested_held_out_manifest(args, requested)
    oracle_launcher = FilesystemOracleSandboxLauncher(
        sandbox_evidence_sha256=args.oracle_sandbox_evidence_sha256,
        request_root=Path(args.oracle_request_root).expanduser(),
        terminal_root=Path(args.oracle_terminal_root).expanduser(),
        timeout_seconds=args.oracle_timeout_seconds,
        poll_interval_seconds=args.oracle_poll_interval_seconds,
    )
    oracle_launcher.preflight()
    verifier_lock_root = (
        Path(args.verifier_lock_root or state_dir / "leases" / "verifiers")
        .expanduser()
        .absolute()
    )
    oracle_work_root = (
        Path(args.oracle_work_root or state_dir / "mission_control" / "oracle-work")
        .expanduser()
        .absolute()
    )
    writer_lock = CampaignWriterLock(paths.lock_path)
    _acquire_writer_handoff(writer_lock, args.writer_handoff_timeout)
    swarm = SwarmManager(state_dir=state_dir)
    roster_receipt = None
    verifier_provider: OllamaProvider | None = None
    try:
        await swarm.init()
        roster_receipt = await ensure_campaign_agent_roster(
            swarm,
            requested_roster,
        )
        board = swarm._task_board
        orchestrator = swarm._orchestrator
        agent_pool = swarm._agent_pool
        if board is None or orchestrator is None or agent_pool is None:
            raise RuntimeError("SwarmManager did not initialize its canonical executor")
        runtime = _runtime_store(state_dir)
        await runtime.init_db()
        observed_inputs = await ingest_observed_input_manifest(
            Path(args.observed_input_manifest).expanduser().absolute(),
            board,
            runtime,
        )
        config = await _recorded_config(runtime, requested.mission_id)
        if config is None:
            raise MissionControlError(
                "campaign has not been prepared; use prepare first"
            )
        if config.digest != requested.digest:
            raise MissionControlError(
                "requested run config conflicts with recorded campaign"
            )
        control = MissionControl(board, runtime)
        authority_binding = await bind_campaign_authority(
            manifest_path=Path(args.authority_manifest).expanduser().absolute(),
            mission_control=control,
            board=board,
            agent_pool=agent_pool,
            campaign_roster=requested_roster,
            observed_inputs=observed_inputs,
            runtime_state=runtime,
            lease_root=(
                Path(args.lease_root).expanduser().resolve(strict=False)
                if args.lease_root
                else default_lease_root(state_dir)
            ),
            reserved_agent_names=(verifier_seat.name,),
        )
        held_task = await board.get(held_out_manifest.task_id)
        if (
            held_task is None
            or held_task.metadata.get("mission_id") != config.mission_id
            or held_task.metadata.get("goal_id") != held_out_manifest.goal_id
            or held_task.metadata.get("mission_task_creation_hash")
            != held_out_manifest.task_creation_hash
            or held_out_manifest.task_id
            not in {bound.task_id for bound in authority_binding.tasks}
        ):
            raise MissionControlError(
                "held-out oracle task is not exactly authority-bound"
            )
        owner = OrchestratorMissionAdapter(
            orchestrator,
            control,
            board,
            runtime,
        )
        lease_root = (
            Path(args.lease_root).expanduser().resolve(strict=False)
            if args.lease_root
            else default_lease_root(state_dir)
        )
        dispatcher = GovernedCampaignTaskDispatcher(
            GovernedMissionDispatcher(
                control,
                board,
                owner,
                authority_verifier=FileExecutionLeaseAuthorityVerifier(
                    lease_root, board
                ),
            ),
            board,
        )
        supervisor = CampaignSupervisor(
            config,
            control,
            board,
            runtime,
            owner,
            dispatcher=dispatcher,
        )
        verifier_provider = OllamaProvider(model=verifier_seat.model)
        candidate_verifier = AutomaticCandidateVerifier(
            runtime=runtime,
            board=board,
            roster=requested_roster,
            model_provider=verifier_provider,
            verifier_seat_name=verifier_seat.name,
            model_lock_root=verifier_lock_root,
            held_out_manifest_path=held_out_manifest.manifest_path,
            held_out_manifest_digest=held_out_manifest.manifest_digest,
            oracle_work_root=oracle_work_root,
            oracle_launcher=oracle_launcher,
        )
        result = await CampaignService(
            supervisor,
            lock_path=paths.lock_path,
            control_gate_path=paths.control_gate_path,
            projection_path=paths.projection_path,
            writer_lock=writer_lock,
            candidate_verifier=candidate_verifier,
            activation_barrier=activation_barrier,
            operator_control_reconciler=operator_control_reconciler,
        ).run(max_cycles=args.cycles, start_campaign=False)
        return {
            "status": result.status,
            "completed_cycles": result.completed_cycles,
            "lock_path": str(result.lock_path),
            "control_gate_path": str(result.control_gate_path),
            "projection_path": str(result.projection_path),
            "roster_receipt": (roster_receipt.to_dict()),
            "authority_binding": authority_binding.to_dict(),
            "snapshot": result.snapshot.to_dict(),
        }
    finally:
        try:
            try:
                if verifier_provider is not None:
                    await verifier_provider.close()
            finally:
                if swarm._running:
                    await swarm.shutdown(drain_timeout=args.shutdown_timeout)
        finally:
            writer_lock.release()


def _cycle_is_fresh(
    projection: Mapping[str, Any] | None,
    requested_at: datetime,
) -> bool:
    if projection is None:
        return False
    raw = projection.get("latest_cycle_at")
    if not isinstance(raw, str):
        return False
    try:
        latest = datetime.fromisoformat(raw)
    except ValueError:
        return False
    return bool(
        latest.tzinfo is not None
        and latest.astimezone(timezone.utc) >= requested_at.astimezone(timezone.utc)
    )


def _run_child_command(args: argparse.Namespace, paths: CampaignPaths) -> list[str]:
    state_dir = Path(args.state_dir).expanduser().resolve(strict=False)
    _requested_roster(args)
    activation_barrier_from_config(
        args.mission_id,
        args.observer_health_receipt,
        args.observer_health_receipt_sha256,
    )
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run",
        "--state-dir",
        str(state_dir),
        "--mission-id",
        args.mission_id,
        "--operator-id",
        args.operator_id,
        "--max-dispatch-per-cycle",
        str(args.max_dispatch_per_cycle),
        "--cycle-interval-seconds",
        str(args.cycle_interval_seconds),
        "--freshness-seconds",
        str(args.freshness_seconds),
        "--shutdown-timeout",
        str(args.shutdown_timeout),
        "--writer-handoff-timeout",
        str(args.writer_handoff_timeout),
        "--lock-path",
        str(paths.lock_path),
        "--projection-path",
        str(paths.projection_path),
    ]
    if args.canary_task_id:
        command.extend(["--canary-task-id", args.canary_task_id])
    command.extend(
        [
            "--authority-manifest",
            str(Path(args.authority_manifest).expanduser().absolute()),
            "--observed-input-manifest",
            str(Path(args.observed_input_manifest).expanduser().absolute()),
            "--held-out-oracle-manifest",
            str(Path(args.held_out_oracle_manifest).expanduser().absolute()),
            "--verifier-seat",
            args.verifier_seat,
            "--oracle-request-root",
            str(Path(args.oracle_request_root).expanduser().absolute()),
            "--oracle-terminal-root",
            str(Path(args.oracle_terminal_root).expanduser().absolute()),
            "--oracle-sandbox-evidence-sha256",
            args.oracle_sandbox_evidence_sha256,
            "--oracle-timeout-seconds",
            str(args.oracle_timeout_seconds),
            "--oracle-poll-interval-seconds",
            str(args.oracle_poll_interval_seconds),
        ]
    )
    if args.observer_health_receipt:
        command.extend(
            [
                "--observer-health-receipt",
                str(Path(args.observer_health_receipt).expanduser().absolute()),
                "--observer-health-receipt-sha256",
                args.observer_health_receipt_sha256,
            ]
        )
    command.extend(
        [
            "--operator-control-normal-inbox",
            str(Path(args.operator_control_normal_inbox).expanduser().absolute()),
            "--operator-control-inflight-inbox",
            str(Path(args.operator_control_inflight_inbox).expanduser().absolute()),
            "--operator-control-applied-inbox",
            str(Path(args.operator_control_applied_inbox).expanduser().absolute()),
            "--operator-control-rejected-inbox",
            str(Path(args.operator_control_rejected_inbox).expanduser().absolute()),
            "--operator-control-max-candidates-per-cycle",
            str(args.operator_control_max_candidates_per_cycle),
        ]
    )
    if args.lease_root:
        command.extend(
            [
                "--lease-root",
                str(Path(args.lease_root).expanduser().resolve(strict=False)),
            ]
        )
    if args.held_out_oracle_digest:
        command.extend(["--held-out-oracle-digest", args.held_out_oracle_digest])
    if args.verifier_lock_root:
        command.extend(
            [
                "--verifier-lock-root",
                str(Path(args.verifier_lock_root).expanduser().absolute()),
            ]
        )
    if args.oracle_work_root:
        command.extend(
            [
                "--oracle-work-root",
                str(Path(args.oracle_work_root).expanduser().absolute()),
            ]
        )
    roster_values = (
        str(getattr(args, "agent_roster", "") or ""),
        str(getattr(args, "agent_roster_sha256", "") or ""),
        str(getattr(args, "objective_sha256", "") or ""),
    )
    if any(roster_values):
        if not all(roster_values):
            raise CampaignRosterError("campaign roster configuration is partial")
        command.extend(
            [
                "--agent-roster",
                str(Path(roster_values[0]).expanduser().resolve(strict=False)),
                "--agent-roster-sha256",
                roster_values[1],
                "--objective-sha256",
                roster_values[2],
            ]
        )
    if args.fast_boot:
        command.append("--fast-boot")
    return command


def start_campaign_process(
    args: argparse.Namespace,
    *,
    popen: Callable[..., Any] = subprocess.Popen,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Launch a daemon and confirm it without treating its PID as evidence."""
    _positive_finite(args.start_timeout, "start_timeout")
    _positive_finite(args.poll_interval, "poll_interval")
    _positive_finite(args.shutdown_timeout, "shutdown_timeout")
    _positive_finite(args.writer_handoff_timeout, "writer_handoff_timeout")
    paths = _paths(args)
    paths.log_path.parent.mkdir(parents=True, exist_ok=True)
    requested_at = now()
    if requested_at.tzinfo is None:
        raise ValueError("start clock must return a timezone-aware datetime")
    command = _run_child_command(args, paths)
    already_running = writer_lock_is_held(paths.lock_path)
    process = None
    requested_config = _requested_config(args)
    expected_generation: int | None = None
    if not already_running:
        handoff_lock = CampaignWriterLock(paths.lock_path)
        handoff_lock.acquire()
        try:
            initialized = asyncio.run(
                _initialize_campaign(
                    Path(args.state_dir).expanduser().resolve(strict=False),
                    requested_config,
                    paths.control_gate_path,
                )
            )
            raw_generation = initialized.metadata.get("generation")
            if isinstance(raw_generation, bool) or not isinstance(raw_generation, int):
                raise MissionControlError("initialized campaign generation is invalid")
            expected_generation = raw_generation
            with paths.log_path.open("ab") as log:
                process = popen(
                    command,
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        finally:
            handoff_lock.release()
    else:
        current = read_campaign_projection(paths.projection_path)
        if current is not None:
            if (
                current.get("mission_id") != requested_config.mission_id
                or current.get("config_digest") != requested_config.digest
            ):
                raise MissionControlError(
                    "existing campaign writer has a conflicting projection identity"
                )
    deadline = monotonic() + args.start_timeout
    projection: dict[str, Any] | None = None
    projection_error = ""
    lock_held = False
    confirmed = False
    while monotonic() <= deadline:
        lock_held = writer_lock_is_held(paths.lock_path)
        writer_identity = (
            read_writer_lock_identity(paths.lock_path) if lock_held else None
        )
        try:
            projection = read_campaign_projection(paths.projection_path)
            projection_error = ""
        except CampaignProjectionError as exc:
            projection = None
            projection_error = str(exc)
        confirmed = projection_confirms_start(
            projection,
            requested_at=requested_at,
            writer_lock_held=lock_held,
            writer_lock_identity=writer_identity,
            expected_mission_id=requested_config.mission_id,
            expected_config_digest=requested_config.digest,
            expected_generation=expected_generation,
        )
        if confirmed:
            break
        if process is not None and process.poll() is not None and not lock_held:
            break
        sleep(min(args.poll_interval, max(0.0, deadline - monotonic())))
    return {
        "status": "started" if confirmed else "unconfirmed",
        "start_confirmed": confirmed,
        "supervisor_cycle_fresh": _cycle_is_fresh(projection, requested_at),
        "writer_lock_held": lock_held,
        "canary_acceptance": (
            projection.get("canary_acceptance", "unobserved")
            if projection is not None
            else "unobserved"
        ),
        "transport_state": (
            projection.get("transport_state", "unobserved")
            if projection is not None
            else "unobserved"
        ),
        "model_execution_state": (
            projection.get("model_execution_state", "unobserved")
            if projection is not None
            else "unobserved"
        ),
        "acceptance_state": (
            projection.get("acceptance_state", "unobserved")
            if projection is not None
            else "unobserved"
        ),
        "pid": getattr(process, "pid", None),
        "pid_is_success_evidence": False,
        "child_process_started": process is not None,
        "existing_writer_observed": already_running,
        "requested_at": requested_at.isoformat(),
        "projection_path": str(paths.projection_path),
        "lock_path": str(paths.lock_path),
        "control_gate_path": str(paths.control_gate_path),
        "log_path": str(paths.log_path),
        "projection_error": projection_error,
    }


def campaign_status(args: argparse.Namespace) -> dict[str, Any]:
    """Inspect only the replaceable read model and its live advisory lock."""
    paths = _paths(args)
    lock_held = writer_lock_is_held(paths.lock_path)
    writer_identity = read_writer_lock_identity(paths.lock_path) if lock_held else None
    projection = read_campaign_projection(paths.projection_path)
    if projection is None:
        return {
            "status": "unobserved",
            "writer_lock_held": lock_held,
            "projection_path": str(paths.projection_path),
            "canonical_database_opened": False,
        }
    live = materialize_projection_liveness(
        projection,
        now=datetime.now(timezone.utc),
        writer_lock_held=lock_held,
        writer_lock_identity=writer_identity,
        expected_mission_id=clean_identifier(args.mission_id, "mission_id"),
    )
    return {
        **live,
        "reported_writer_lock_held": projection.get("writer_lock_held") is True,
        "canonical_database_opened": False,
        "projection_path": str(paths.projection_path),
        "lock_path": str(paths.lock_path),
        "control_gate_path": str(paths.control_gate_path),
    }


async def stop_campaign(args: argparse.Namespace) -> dict[str, Any]:
    paths = _paths(args)
    async with CampaignControlGate(paths.control_gate_path):
        supervisor, _runtime = await _existing_supervisor(
            args.state_dir,
            args.mission_id,
        )
        session = await supervisor.stop()
    return {
        "status": "stop_requested",
        "campaign_status": session.status,
        "stop_requested": session.metadata.get("stop_requested") is True,
        "queued_work_preserved": True,
        "session_id": session.session_id,
    }


async def verify_campaign(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(Path(args.acceptance_json).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise MissionControlError("acceptance JSON must be an object")
    acceptance = IndependentAcceptance.from_payload(raw)
    paths = _paths(args)
    async with CampaignControlGate(paths.control_gate_path):
        supervisor, _runtime = await _existing_supervisor(
            args.state_dir,
            args.mission_id,
        )
        receipt = await supervisor.accept(acceptance)
    return {
        "status": receipt.status,
        "receipt_id": receipt.receipt_id,
        "task_id": receipt.task_id,
        "acceptance_is_independent": True,
    }


def _add_paths(parser: argparse.ArgumentParser, *, log: bool = False) -> None:
    parser.add_argument("--state-dir", default=".dharma")
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--lock-path", default=None)
    parser.add_argument("--projection-path", default=None)
    if log:
        parser.add_argument("--log-path", default=None)


def _add_campaign_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--operator-id", default="operator")
    parser.add_argument("--canary-task-id", default="")
    parser.add_argument("--max-dispatch-per-cycle", type=int, default=4)
    parser.add_argument("--cycle-interval-seconds", type=float, default=5.0)
    parser.add_argument("--freshness-seconds", type=float, default=30.0)
    parser.add_argument("--held-out-oracle-digest", default="")


def _add_run_config(parser: argparse.ArgumentParser) -> None:
    _add_campaign_config(parser)
    add_campaign_runtime_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="Launch and verify a background supervisor.")
    _add_paths(start, log=True)
    _add_run_config(start)
    start.add_argument("--start-timeout", type=float, default=120.0)
    start.add_argument("--poll-interval", type=float, default=0.25)

    prepare = sub.add_parser(
        "prepare", help="Idempotently create the durable campaign session."
    )
    _add_paths(prepare)
    _add_campaign_config(prepare)

    run = sub.add_parser("run", help="Run the foreground supervisor service.")
    _add_paths(run)
    _add_run_config(run)
    run.add_argument("--cycles", type=int, default=None)

    status = sub.add_parser("status", help="Read the JSON projection only.")
    _add_paths(status)

    verify = sub.add_parser("verify", help="Record an independent acceptance.")
    _add_paths(verify)
    verify.add_argument("--acceptance-json", required=True)

    stop = sub.add_parser("stop", help="Persist a durable campaign stop request.")
    _add_paths(stop)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            payload = start_campaign_process(args)
            code = 0 if payload["start_confirmed"] else 2
        elif args.command == "prepare":
            payload = asyncio.run(prepare_campaign(args))
            code = 0 if payload["status"] == "prepared" else 2
        elif args.command == "run":
            payload = asyncio.run(run_campaign(args))
            code = 0
        elif args.command == "status":
            payload = campaign_status(args)
            code = 0 if payload["status"] != "unobserved" else 2
        elif args.command == "verify":
            payload = asyncio.run(verify_campaign(args))
            code = 0 if payload["status"] == "accepted" else 2
        else:
            payload = asyncio.run(stop_campaign(args))
            code = 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        code = 2
    print(json.dumps(payload, allow_nan=False, sort_keys=True, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
