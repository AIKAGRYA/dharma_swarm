"""External service runner for LivingAgentKernel daemon cycles.

This module owns process-level concerns around the kernel control cycle:
bounded repeated invocation, a split-brain lock, and a compact run result. It
does not introduce a second queue or execute provider/subprocess tools.
"""

from __future__ import annotations

import fcntl
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import (
    DEFAULT_KERNEL_RUN_DIR,
    KernelDaemonCycle,
    KernelRunStore,
    LivingAgentKernel,
)

KernelDaemonServiceStatus = Literal["completed", "stopped", "lock_held", "failed"]


class KernelDaemonServiceRun(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_service_run.v1"
    status: KernelDaemonServiceStatus
    daemon_id: str = "living-agent-kernel"
    requested_cycles: int | None = 1
    completed_cycles: int = 0
    cycles: list[KernelDaemonCycle] = Field(default_factory=list)
    lock_ref: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


def run_kernel_daemon_service(
    *,
    store_dir: Path | str | None = None,
    workspace_root: Path | str | None = None,
    daemon_id: str = "living-agent-kernel",
    cycles: int | None = 1,
    max_wakes: int = 1,
    lease_seconds: int = 300,
    interval_seconds: int = 60,
    latest_limit: int = 20,
    recover_expired: bool = True,
    source_roots: dict[str, Path | str] | None = None,
    lock_path: Path | str | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    now_fn: Callable[[], str | None] | None = None,
    stop_on_stopped: bool = True,
) -> KernelDaemonServiceRun:
    """Run bounded daemon cycles under a non-blocking file lock.

    Args:
        cycles: Number of cycles to run. ``None`` means unbounded until stopped
            or interrupted by the caller. Tests and one-shot CLIs should pass a
            finite value.
        sleep_fn: Optional injectable sleeper for tests. Defaults to
            ``time.sleep`` when another cycle remains.
        now_fn: Optional timestamp provider for deterministic tests.
    """
    store = KernelRunStore(store_dir or DEFAULT_KERNEL_RUN_DIR)
    workspace = Path(workspace_root or Path.cwd()).expanduser().resolve()
    service_lock = Path(lock_path or store.base_dir / "daemon_service.lock").expanduser()
    service_lock.parent.mkdir(parents=True, exist_ok=True)
    sleeper = sleep_fn or time.sleep
    lock_ref = {"kind": "kernel_daemon_service_lock", "path": str(service_lock)}
    requested_cycles = None if cycles is None else max(0, int(cycles))
    if requested_cycles == 0:
        return KernelDaemonServiceRun(
            status="completed",
            daemon_id=daemon_id,
            requested_cycles=0,
            lock_ref=lock_ref,
            message="No daemon cycles requested.",
        )

    with service_lock.open("w", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return KernelDaemonServiceRun(
                status="lock_held",
                daemon_id=daemon_id,
                requested_cycles=requested_cycles,
                lock_ref={**lock_ref, "held": True},
                message="Daemon service lock is held by another runner.",
            )

        observed_cycles: list[KernelDaemonCycle] = []
        status: KernelDaemonServiceStatus = "completed"
        message = "Daemon service completed requested cycle(s)."
        try:
            kernel = LivingAgentKernel(store=store, workspace_root=workspace)
            cycle_index = 0
            while requested_cycles is None or cycle_index < requested_cycles:
                cycle_index += 1
                cycle = kernel.run_daemon_cycle(
                    daemon_id=daemon_id,
                    lease_seconds=lease_seconds,
                    max_wakes=max_wakes,
                    source_roots=source_roots,
                    recover_expired=recover_expired,
                    latest_limit=latest_limit,
                    interval_seconds=interval_seconds,
                    now=now_fn() if now_fn is not None else None,
                )
                observed_cycles.append(cycle)
                if cycle.status == "stopped" and stop_on_stopped:
                    status = "stopped"
                    message = "Daemon service stopped by durable control receipt."
                    break
                if cycle.status == "failed":
                    status = "failed"
                    message = cycle.message or "Daemon service cycle failed."
                    break
                if requested_cycles is None or cycle_index < requested_cycles:
                    sleeper(max(0, float(interval_seconds)))
        except Exception as exc:
            return KernelDaemonServiceRun(
                status="failed",
                daemon_id=daemon_id,
                requested_cycles=requested_cycles,
                completed_cycles=len(observed_cycles),
                cycles=observed_cycles,
                lock_ref=lock_ref,
                message=f"Daemon service failed: {type(exc).__name__}: {exc}",
            )
        finally:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)

    return KernelDaemonServiceRun(
        status=status,
        daemon_id=daemon_id,
        requested_cycles=requested_cycles,
        completed_cycles=len(observed_cycles),
        cycles=observed_cycles,
        lock_ref=lock_ref,
        message=message,
    )


__all__ = [
    "KernelDaemonServiceRun",
    "KernelDaemonServiceStatus",
    "run_kernel_daemon_service",
]
