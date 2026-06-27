"""Bounded long-run supervisor for standalone Holon."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from holon.holon_runtime import HolonRuntime, runtime_from_identity
from holon.organs import health, persistence, service
from holon.receipts import build_receipt, write_receipt


@dataclass(frozen=True)
class SupervisorConfig:
    name: str
    prompt: str = "Run one bounded autonomy cycle and report evidence."
    max_cycles: int = 1
    sleep_seconds: float = 0.0
    cap_usd: float = 0.0
    agents_root: Path = Path.home() / ".dharma" / "agents"
    lease_seconds: int = 300
    lock_path: Path | None = None
    service_id: str = "holon-supervisor"
    heartbeat_fresh_seconds: int = 300


async def run_supervisor(config: SupervisorConfig, *, runtime: HolonRuntime | None = None) -> dict[str, object]:
    results = []
    start_cycle = persistence.resume_point(config.name, agents_root=config.agents_root)["next_cycle"]
    lock = service.acquire_service_lock(
        config.name,
        agents_root=config.agents_root,
        holder=config.service_id,
        lease_seconds=config.lease_seconds,
        lock_path=config.lock_path,
    )
    if not lock.acquired:
        heartbeat = service.record_service_heartbeat(
            config.name,
            agents_root=config.agents_root,
            session_id=f"supervisor:{config.name}:{start_cycle}",
            service_id=config.service_id,
            status="paused",
            runtime_ref={"start_cycle": start_cycle, "lock": lock.to_dict()},
            claim_scope={"lock_held": True, "supervisor_started": False},
        )
        liveness = service.assess_service_liveness(
            config.name,
            agents_root=config.agents_root,
            service_id=config.service_id,
            fresh_after_seconds=config.heartbeat_fresh_seconds,
        )
        status = health.holon_status(config.name, agents_root=config.agents_root)
        receipt = build_receipt(
            kind="holon_supervisor_run",
            subject=config.name,
            status="warn",
            side_effect_key=f"supervisor-lock-held:{config.name}:{start_cycle}:{config.prompt}",
            payload={
                "status": "lock_held",
                "results": results,
                "health": status,
                "lock": lock.to_dict(),
                "service_heartbeat": heartbeat,
                "service_liveness": liveness,
            },
        )
        ref = write_receipt(receipt, agents_root=config.agents_root, holon_name=config.name)
        return {
            "status": "lock_held",
            "results": results,
            "health": status,
            "lock": lock.to_dict(),
            "service_heartbeat": heartbeat,
            "service_liveness": liveness,
            "receipt": ref,
        }

    final_heartbeat: dict[str, object] = {}
    lock_released = False
    try:
        active_runtime = runtime or runtime_from_identity(config.name, agents_root=config.agents_root)
        running_heartbeat = service.record_service_heartbeat(
            config.name,
            agents_root=config.agents_root,
            session_id=f"supervisor:{config.name}:{start_cycle}",
            service_id=config.service_id,
            status="running",
            runtime_ref={"start_cycle": start_cycle, "max_cycles": config.max_cycles},
            claim_scope={"lock_acquired": True, "supervisor_started": True},
        )
        final_heartbeat = running_heartbeat
        for offset in range(max(0, config.max_cycles)):
            cycle = start_cycle + offset
            result = await active_runtime.run_provider_cycle(
                config.prompt,
                cycle=cycle,
                cap_usd=config.cap_usd,
                side_effect_key=f"supervisor:{config.name}:{cycle}:{config.prompt}",
            )
            results.append(result.to_dict())
            if result.status != "ran":
                break
            if config.sleep_seconds > 0:
                await asyncio.sleep(config.sleep_seconds)
        final_status = _heartbeat_status(results)
        final_heartbeat = service.record_service_heartbeat(
            config.name,
            agents_root=config.agents_root,
            session_id=f"supervisor:{config.name}:{start_cycle}",
            service_id=config.service_id,
            status=final_status,
            runtime_ref={
                "start_cycle": start_cycle,
                "cycles_attempted": len(results),
                "last_status": results[-1]["status"] if results else "none",
            },
            claim_scope={
                "lock_acquired": True,
                "supervisor_started": True,
                "clean_completion": bool(results and results[-1]["status"] == "ran"),
            },
        )
    finally:
        lock_released = service.release_service_lock(lock)

    liveness = service.assess_service_liveness(
        config.name,
        agents_root=config.agents_root,
        service_id=config.service_id,
        fresh_after_seconds=config.heartbeat_fresh_seconds,
    )
    status = health.holon_status(config.name, agents_root=config.agents_root)
    receipt = build_receipt(
        kind="holon_supervisor_run",
        subject=config.name,
        status="pass" if results and results[-1]["status"] == "ran" else "warn",
        side_effect_key=f"supervisor-run:{config.name}:{start_cycle}:{config.max_cycles}:{config.prompt}",
        payload={
            "status": "completed" if results and results[-1]["status"] == "ran" else "warn",
            "results": results,
            "health": status,
            "lock": {**lock.to_dict(), "released": lock_released},
            "service_heartbeat": final_heartbeat,
            "service_liveness": liveness,
        },
    )
    ref = write_receipt(receipt, agents_root=config.agents_root, holon_name=config.name)
    return {
        "status": "completed" if results and results[-1]["status"] == "ran" else "warn",
        "results": results,
        "health": status,
        "lock": {**lock.to_dict(), "released": lock_released},
        "service_heartbeat": final_heartbeat,
        "service_liveness": liveness,
        "receipt": ref,
    }


def _heartbeat_status(results: list[dict[str, object]]) -> str:
    if not results:
        return "idle"
    status = str(results[-1].get("status") or "")
    if status == "ran":
        return "idle"
    if status.startswith("halted:") and status != "halted:error":
        return "safe_refusal"
    return "error"


def run_supervisor_sync(config: SupervisorConfig) -> dict[str, object]:
    return asyncio.run(run_supervisor(config))
