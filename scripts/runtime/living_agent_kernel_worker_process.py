#!/usr/bin/env python3
"""Run a bounded LivingAgentKernel external-worker heartbeat process."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel import LivingAgentKernel  # noqa: E402
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore  # noqa: E402


class KernelWorkerProcessRun(BaseModel):
    schema_version: str = "dharma_living_agent_kernel_worker_process_run.v1"
    status: str = "completed"
    worker_id: str
    completed_cycles: int = 0
    registered_ref: dict[str, Any] = Field(default_factory=dict)
    heartbeat_refs: list[dict[str, Any]] = Field(default_factory=list)
    lease_refs: list[dict[str, Any]] = Field(default_factory=list)
    execution_refs: list[dict[str, Any]] = Field(default_factory=list)
    result_refs: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-dir", default=None, help="Kernel store directory. Defaults to ~/.dharma/living_agent_kernel.")
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--role", default="worker")
    parser.add_argument("--allowed-source", action="append", default=[])
    parser.add_argument("--max-lease-seconds", type=int, default=300)
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=60)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--forever", action="store_true", help="Run heartbeats until interrupted.")
    parser.add_argument("--lease", action="store_true", help="Lease eligible wakes after each heartbeat without completing them.")
    parser.add_argument("--execute", action="store_true", help="Lease, run, and complete one eligible wake per cycle through LivingAgentKernel.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root for worker-executed kernel tool permissions.")
    parser.add_argument("--now", default=None, help="Deterministic timestamp for tests.")
    parser.add_argument("--json", action="store_true")
    return parser


def run_worker_process(
    *,
    store_dir: Path | str | None = None,
    worker_id: str,
    role: str = "worker",
    allowed_sources: list[str] | None = None,
    max_lease_seconds: int = 300,
    heartbeat_interval_seconds: int = 60,
    cycles: int | None = 1,
    lease: bool = False,
    execute: bool = False,
    workspace_root: Path | str | None = None,
    now: str | None = None,
    sleep_fn: Any = time.sleep,
) -> KernelWorkerProcessRun:
    store = KernelExternalWorkerStore(store_dir)
    kernel = LivingAgentKernel(store=store.kernel_store, workspace_root=workspace_root or Path.cwd())
    registered = store.register_worker(
        worker_id,
        role=role,
        allowed_sources=allowed_sources or [],
        max_lease_seconds=max_lease_seconds,
        now=now,
    )
    heartbeat_refs: list[dict[str, Any]] = []
    lease_refs: list[dict[str, Any]] = []
    execution_refs: list[dict[str, Any]] = []
    result_refs: list[dict[str, Any]] = []
    completed_cycles = 0
    requested_cycles = None if cycles is None else max(0, int(cycles))
    while requested_cycles is None or completed_cycles < requested_cycles:
        heartbeat = store.heartbeat_worker(worker_id, now=now)
        heartbeat_refs.append(
            {
                "kind": "kernel_external_worker_heartbeat",
                "path": str(store.heartbeat_path),
                "record_hash": heartbeat.record_hash,
            }
        )
        if lease or execute:
            leased = store.lease_worker_wake(worker_id, now=now)
            lease_refs.append(
                {
                    "kind": "kernel_external_worker_lease",
                    "path": str(store.lease_path),
                    "record_hash": leased.record_hash,
                    "status": leased.status,
                    "wake_id": leased.wake_id,
                }
            )
            if execute and leased.status == "leased" and leased.wake_record is not None:
                result = kernel.run(leased.wake_record.envelope)
                worker_result = store.complete_worker_wake(
                    worker_id,
                    leased.wake_id,
                    status=result.status,
                    summary=f"Worker process executed kernel run {result.run_id}.",
                    result_ref={
                        "kind": "kernel_run_result",
                        "run_id": result.run_id,
                        "replay_ref": result.replay_ref,
                        "proof_entry_hash": result.proof_ledger_entry.entry_hash,
                        "provider_execution": False,
                        "unsupported_claims": list(result.proof_ledger_entry.unsupported_claims),
                    },
                    now=now,
                )
                execution_refs.append(
                    {
                        "kind": "kernel_run_result",
                        "run_id": result.run_id,
                        "status": result.status,
                        "replay_ref": result.replay_ref,
                        "proof_entry_hash": result.proof_ledger_entry.entry_hash,
                    }
                )
                result_refs.append(
                    {
                        "kind": "kernel_external_worker_result",
                        "path": str(store.result_path),
                        "record_hash": worker_result.record_hash,
                        "wake_id": worker_result.wake_id,
                        "status": worker_result.status,
                    }
                )
        completed_cycles += 1
        if requested_cycles is None or completed_cycles < requested_cycles:
            sleep_fn(max(0, float(heartbeat_interval_seconds)))
    return KernelWorkerProcessRun(
        worker_id=worker_id,
        completed_cycles=completed_cycles,
        registered_ref={
            "kind": "kernel_external_worker_registration",
            "path": str(store.registry_path),
            "record_hash": registered.record_hash,
        },
        heartbeat_refs=heartbeat_refs,
        lease_refs=lease_refs,
        execution_refs=execution_refs,
        result_refs=result_refs,
        message="Worker process emitted bounded heartbeat cycle(s).",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_worker_process(
            store_dir=args.store_dir,
            worker_id=args.worker_id,
            role=args.role,
            allowed_sources=args.allowed_source,
            max_lease_seconds=args.max_lease_seconds,
            heartbeat_interval_seconds=args.heartbeat_interval_seconds,
            cycles=None if args.forever else args.cycles,
            lease=args.lease,
            execute=args.execute,
            workspace_root=args.workspace_root,
            now=args.now,
        )
    except Exception as exc:
        payload = {
            "schema_version": "dharma_living_agent_kernel_worker_process_run.v1",
            "status": "failed",
            "worker_id": args.worker_id,
            "message": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(payload, sort_keys=True))
        return 2
    if args.json:
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    else:
        print(f"{result.status}: {result.worker_id} heartbeat cycle(s)={result.completed_cycles}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
