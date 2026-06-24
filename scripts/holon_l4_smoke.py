#!/usr/bin/env python3
"""Run the deterministic L4 HOLON smoke proof."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dharma_swarm.holon_bridge import AGENTS_ROOT
from dharma_swarm.holon_l4_orchestration_runtime import (
    deterministic_l4_decompose,
    run_l4_smoke_with_readonly_swarm_manager,
)
from dharma_swarm.holon_l4_smoke import (
    L4SmokeConfig,
    run_l4_supervised_smoke_sync,
)


def _base_config(args: argparse.Namespace) -> L4SmokeConfig:
    return L4SmokeConfig(
        name=args.name,
        agents_root=args.agents_root,
        memory_receipt_path=args.memory_receipt_path,
        session_id=args.session_id,
        lease_seconds=args.lease_seconds,
        enable_model_probe=args.live_model_probe,
        model_probe_timeout_seconds=args.model_probe_timeout_seconds,
        model_probe_message=args.model_probe_message,
        allow_subprocess_model_probe=args.allow_subprocess_model_probe,
        safe_subprocess_model_probe=args.safe_subprocess_model_probe,
        safe_subprocess_probe_cwd=args.safe_subprocess_probe_cwd,
        model_probe_lease_id=args.model_probe_lease_id,
        model_probe_lease_path=args.model_probe_lease_path,
        transport_agent_uid=args.transport_agent_uid,
        transport_heartbeat_path=args.transport_heartbeat_path,
        transport_fresh_after_seconds=args.transport_fresh_after_seconds,
        require_transport_reachable=args.require_transport_reachable,
        enable_orchestration_probe=args.enable_orchestration_probe,
        require_orchestration=args.require_orchestration,
        orchestration_decomposer=(
            deterministic_l4_decompose
            if args.deterministic_orchestration_plan
            else None
        ),
        orchestration_execution_mode=args.orchestration_execution_mode,
        orchestration_execution_timeout_seconds=args.orchestration_timeout_seconds,
        orchestration_min_subtasks=args.orchestration_min_subtasks,
        orchestration_min_model_tiers=args.orchestration_min_model_tiers,
    )


async def _run_with_readonly_swarm_manager(args: argparse.Namespace) -> dict:
    return await run_l4_smoke_with_readonly_swarm_manager(
        _base_config(args),
        state_dir=args.orchestration_state_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", default="codex_composer")
    parser.add_argument("--agents-root", type=Path, default=AGENTS_ROOT)
    parser.add_argument(
        "--memory-receipt-path",
        type=Path,
        default=Path("reports/sovereign_holons/l4_memory_write_receipts.jsonl"),
    )
    parser.add_argument("--session-id", default="")
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument(
        "--live-model-probe",
        action="store_true",
        help="call the holon's declared provider and require a non-empty response",
    )
    parser.add_argument("--model-probe-timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--model-probe-message",
        default="Reply with one short sentence confirming you are responsive as this holon.",
    )
    parser.add_argument(
        "--allow-subprocess-model-probe",
        action="store_true",
        help="allow live probes through subprocess CLI providers such as codex/claude_code",
    )
    parser.add_argument(
        "--safe-subprocess-model-probe",
        action="store_true",
        help="for codex identities, use codex exec in read-only/no-approval/ephemeral mode",
    )
    parser.add_argument("--safe-subprocess-probe-cwd", type=Path, default=None)
    parser.add_argument(
        "--model-probe-lease-id",
        default="",
        help="lease id required for declared live model probes",
    )
    parser.add_argument(
        "--model-probe-lease-path",
        type=Path,
        default=None,
        help="JSON lease receipt required for declared live model probes",
    )
    parser.add_argument("--transport-agent-uid", default="")
    parser.add_argument("--transport-heartbeat-path", type=Path, default=None)
    parser.add_argument("--transport-fresh-after-seconds", type=int, default=3600)
    parser.add_argument(
        "--require-transport-reachable",
        action="store_true",
        help="require a fresh A2A inbox bridge heartbeat in the proof",
    )
    parser.add_argument(
        "--enable-orchestration-probe",
        action="store_true",
        help="run the orchestration probe; requires an orchestrator unless using the read-only SwarmManager option",
    )
    parser.add_argument(
        "--require-orchestration",
        action="store_true",
        help="require orchestration proof for overall_pass",
    )
    parser.add_argument(
        "--orchestration-execution-mode",
        choices=["dispatch_aggregation_probe", "bounded_subtask_execution"],
        default="dispatch_aggregation_probe",
    )
    parser.add_argument("--orchestration-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--orchestration-min-subtasks", type=int, default=2)
    parser.add_argument("--orchestration-min-model-tiers", type=int, default=2)
    parser.add_argument(
        "--deterministic-orchestration-plan",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use the fixed two-subtask L4 smoke plan for reproducible receipts",
    )
    parser.add_argument(
        "--use-readonly-swarm-manager-orchestrator",
        action="store_true",
        help="boot SwarmManager in read-only mode and attach deterministic no-provider runners for bounded orchestration",
    )
    parser.add_argument(
        "--orchestration-state-dir",
        type=Path,
        default=AGENTS_ROOT.parent,
        help="state directory for the read-only SwarmManager orchestration proof",
    )
    args = parser.parse_args()

    if args.use_readonly_swarm_manager_orchestrator:
        proof = asyncio.run(_run_with_readonly_swarm_manager(args))
    else:
        proof = run_l4_supervised_smoke_sync(
            _base_config(args)
        )
    print(json.dumps(proof, indent=2, sort_keys=True))
    return 0 if proof.get("overall_pass") else 3


if __name__ == "__main__":
    raise SystemExit(main())
