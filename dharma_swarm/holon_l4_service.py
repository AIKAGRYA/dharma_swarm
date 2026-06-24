"""Launchd-ready L4 HOLON service runner.

This module owns only process-level service concerns for the existing L4 smoke
proof: a non-blocking split-brain lock, bounded repeated cycles, and heartbeat
projection through ``holon_service_liveness``. It does not create a new queue,
daemon supervisor, receipt store, or model route.
"""
from __future__ import annotations

import asyncio
import fcntl
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from dharma_swarm.holon_bridge import AGENTS_ROOT
from dharma_swarm.holon_l4_smoke import L4SmokeConfig, run_l4_supervised_smoke, utc_compact
from dharma_swarm.holon_service_liveness import record_service_heartbeat

SERVICE_RUN_SCHEMA_VERSION = "dharma.holon_l4_service_run.v1"
SERVICE_ID = "holon-l4-service"

HolonL4ServiceStatus = Literal["completed", "stopped", "lock_held", "failed", "paused"]
HolonL4CycleRunner = Callable[[L4SmokeConfig], Awaitable[dict[str, Any]]]
SleepFn = Callable[[float], None]


def default_service_lock_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "holon_l4_service.lock"


def _requested_cycles(cycles: int | None) -> int | None:
    return None if cycles is None else max(0, int(cycles))


def _cycle_session_id(base_session_id: str, cycle_index: int) -> str:
    base = str(base_session_id or "").strip()
    if not base:
        return f"l4-service-{utc_compact()}-cycle-{cycle_index}"
    if cycle_index == 1:
        return base
    return f"{base}-cycle-{cycle_index}"


def _cycle_status(proof: dict[str, Any]) -> str:
    if proof.get("overall_pass"):
        return "passed"
    if proof.get("claim_scope", {}).get("safe_refusal"):
        return "safe_refusal"
    if proof.get("runtime_result", {}).get("status") == "halted:kill":
        return "stopped"
    return "failed"


def _cycle_config(
    config: L4SmokeConfig,
    *,
    session_id: str,
    cycle_index: int,
    model_probe_first_cycle_only: bool,
) -> L4SmokeConfig:
    cycle_config = replace(config, session_id=session_id)
    if model_probe_first_cycle_only and cycle_index > 1:
        cycle_config = replace(
            cycle_config,
            enable_model_probe=False,
            allow_subprocess_model_probe=False,
            model_probe_lease_id="",
            model_probe_lease_path=None,
        )
    return cycle_config


def _heartbeat_status(cycle_status: str) -> str:
    if cycle_status == "passed":
        return "idle"
    if cycle_status == "safe_refusal":
        return "safe_refusal"
    if cycle_status == "stopped":
        return "stopped"
    return "error"


def _global_pause_path(config: L4SmokeConfig) -> Path:
    return config.agents_root.parent / ".PAUSE"


def _summarize_cycle(cycle_index: int, proof: dict[str, Any]) -> dict[str, Any]:
    artifact = dict(proof.get("artifact") or {})
    return {
        "cycle_index": cycle_index,
        "session_id": str(proof.get("session_id") or ""),
        "status": _cycle_status(proof),
        "overall_pass": bool(proof.get("overall_pass")),
        "proof_digest": str(proof.get("proof_digest") or ""),
        "artifact": {
            "artifact_id": str(artifact.get("artifact_id") or ""),
            "digest": str(artifact.get("digest") or ""),
            "path": str(artifact.get("path") or ""),
        },
        "proof_levels": dict(proof.get("proof_levels") or {}),
        "claim_scope": dict(proof.get("claim_scope") or {}),
        "service_heartbeat": dict(proof.get("service_heartbeat") or {}),
        "transport_liveness": dict(proof.get("transport_liveness") or {}),
        "model_probe": dict(proof.get("model_probe") or {}),
        "orchestration_probe": dict(proof.get("orchestration_probe") or {}),
    }


def _new_result(
    *,
    status: HolonL4ServiceStatus,
    name: str,
    requested_cycles: int | None,
    lock_ref: dict[str, Any],
    completed_cycles: int = 0,
    cycles: list[dict[str, Any]] | None = None,
    message: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": SERVICE_RUN_SCHEMA_VERSION,
        "status": status,
        "holon": name,
        "service_id": SERVICE_ID,
        "requested_cycles": requested_cycles,
        "completed_cycles": completed_cycles,
        "cycles": list(cycles or []),
        "lock_ref": dict(lock_ref),
        "message": message,
    }


async def run_holon_l4_service_async(
    config: L4SmokeConfig,
    *,
    cycles: int | None = 1,
    interval_seconds: float = 60.0,
    lock_path: Path | str | None = None,
    sleep_fn: SleepFn | None = None,
    cycle_runner: HolonL4CycleRunner | None = None,
    model_probe_first_cycle_only: bool = False,
) -> dict[str, Any]:
    """Run L4 smoke proof cycles under a non-blocking per-holon service lock."""
    requested = _requested_cycles(cycles)
    service_lock = Path(lock_path or default_service_lock_path(config.name, config.agents_root))
    service_lock.parent.mkdir(parents=True, exist_ok=True)
    lock_ref = {"kind": "holon_l4_service_lock", "path": str(service_lock)}
    if requested == 0:
        return _new_result(
            status="completed",
            name=config.name,
            requested_cycles=0,
            lock_ref=lock_ref,
            message="No L4 service cycles requested.",
        )

    runner = cycle_runner or run_l4_supervised_smoke
    observed_cycles: list[dict[str, Any]] = []
    status: HolonL4ServiceStatus = "completed"
    message = "L4 HOLON service completed requested cycle(s)."

    with service_lock.open("w", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _new_result(
                status="lock_held",
                name=config.name,
                requested_cycles=requested,
                lock_ref={**lock_ref, "held": True},
                message="L4 HOLON service lock is held by another runner.",
            )

        cycle_index = 0
        try:
            while requested is None or cycle_index < requested:
                next_cycle_index = cycle_index + 1
                session_id = _cycle_session_id(config.session_id, next_cycle_index)
                pause_path = _global_pause_path(config)
                if pause_path.exists():
                    record_service_heartbeat(
                        config.name,
                        agents_root=config.agents_root,
                        session_id=session_id,
                        service_id=SERVICE_ID,
                        status="paused",
                        runtime_ref={
                            "cycle_index": next_cycle_index,
                            "requested_cycles": requested,
                            "pause_path": str(pause_path),
                        },
                        proof_ref={"kind": "l4_service_cycle_paused"},
                        claim_scope={"runtime_paused": True},
                    )
                    if requested is None:
                        delay = max(1.0, float(interval_seconds))
                        if sleep_fn is not None:
                            sleep_fn(delay)
                        else:
                            await asyncio.sleep(delay)
                        continue
                    status = "paused"
                    message = f"L4 HOLON service paused by {pause_path}."
                    break

                cycle_index = next_cycle_index
                record_service_heartbeat(
                    config.name,
                    agents_root=config.agents_root,
                    session_id=session_id,
                    service_id=SERVICE_ID,
                    status="running",
                    runtime_ref={
                        "cycle_index": cycle_index,
                        "requested_cycles": requested,
                        "lock_ref": lock_ref,
                    },
                    proof_ref={"kind": "l4_service_cycle_start"},
                    claim_scope={},
                )
                proof = await runner(
                    _cycle_config(
                        config,
                        session_id=session_id,
                        cycle_index=cycle_index,
                        model_probe_first_cycle_only=model_probe_first_cycle_only,
                    )
                )
                cycle = _summarize_cycle(cycle_index, proof)
                observed_cycles.append(cycle)
                record_service_heartbeat(
                    config.name,
                    agents_root=config.agents_root,
                    session_id=session_id,
                    service_id=SERVICE_ID,
                    status=_heartbeat_status(cycle["status"]),
                    runtime_ref={
                        "cycle_index": cycle_index,
                        "requested_cycles": requested,
                        "service_cycle_status": cycle["status"],
                    },
                    proof_ref={
                        "kind": "l4_service_cycle",
                        "proof_digest": cycle["proof_digest"],
                        "artifact": cycle["artifact"],
                    },
                    claim_scope=cycle["claim_scope"],
                )
                if cycle["status"] == "stopped":
                    status = "stopped"
                    message = "L4 HOLON service stopped by holon kill switch."
                    break
                if cycle["status"] not in {"passed", "safe_refusal"}:
                    status = "failed"
                    message = f"L4 HOLON service cycle {cycle_index} failed."
                    break
                if requested is None or cycle_index < requested:
                    delay = max(0.0, float(interval_seconds))
                    if sleep_fn is not None:
                        sleep_fn(delay)
                    else:
                        await asyncio.sleep(delay)
        except Exception as exc:  # noqa: BLE001 - service receipts failures.
            status = "failed"
            message = f"L4 HOLON service failed: {type(exc).__name__}: {exc}"
            record_service_heartbeat(
                config.name,
                agents_root=config.agents_root,
                session_id=_cycle_session_id(config.session_id, cycle_index or 1),
                service_id=SERVICE_ID,
                status="error",
                runtime_ref={
                    "cycle_index": cycle_index,
                    "requested_cycles": requested,
                    "error_type": type(exc).__name__,
                },
                proof_ref={"kind": "l4_service_error"},
                claim_scope={},
            )
        finally:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)

    return _new_result(
        status=status,
        name=config.name,
        requested_cycles=requested,
        completed_cycles=len(observed_cycles),
        cycles=observed_cycles,
        lock_ref=lock_ref,
        message=message,
    )


def run_holon_l4_service(
    config: L4SmokeConfig,
    *,
    cycles: int | None = 1,
    interval_seconds: float = 60.0,
    lock_path: Path | str | None = None,
    sleep_fn: SleepFn | None = None,
    cycle_runner: HolonL4CycleRunner | None = None,
    model_probe_first_cycle_only: bool = False,
) -> dict[str, Any]:
    return asyncio.run(
        run_holon_l4_service_async(
            config,
            cycles=cycles,
            interval_seconds=interval_seconds,
            lock_path=lock_path,
            sleep_fn=sleep_fn,
            cycle_runner=cycle_runner,
            model_probe_first_cycle_only=model_probe_first_cycle_only,
        )
    )


__all__ = [
    "SERVICE_ID",
    "SERVICE_RUN_SCHEMA_VERSION",
    "default_service_lock_path",
    "run_holon_l4_service",
    "run_holon_l4_service_async",
]
