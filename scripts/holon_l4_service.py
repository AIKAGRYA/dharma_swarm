#!/usr/bin/env python3
"""Run L4 HOLON service cycles under a split-brain lock."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.holon_bridge import AGENTS_ROOT  # noqa: E402
from dharma_swarm.holon_l4_orchestration_runtime import (  # noqa: E402
    deterministic_l4_decompose,
    run_l4_smoke_with_readonly_swarm_manager,
)
from dharma_swarm.holon_l4_service import run_holon_l4_service  # noqa: E402
from dharma_swarm.holon_l4_smoke import L4SmokeConfig  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
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
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--forever", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--lock-path", type=Path, default=None)
    parser.add_argument(
        "--live-model-probe",
        action="store_true",
        help="call the holon's declared provider and require a non-empty response",
    )
    parser.add_argument(
        "--model-probe-first-cycle-only",
        action="store_true",
        help="run a configured live model probe only on the first service cycle",
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
    parser.add_argument("--model-probe-lease-id", default="")
    parser.add_argument("--model-probe-lease-path", type=Path, default=None)
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
        help="run the orchestration proof during each service cycle",
    )
    parser.add_argument(
        "--require-orchestration",
        action="store_true",
        help="require orchestration proof for each service cycle to pass",
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
        help="boot SwarmManager in read-only mode and attach deterministic no-provider runners",
    )
    parser.add_argument(
        "--orchestration-state-dir",
        type=Path,
        default=AGENTS_ROOT.parent,
        help="state directory for the read-only SwarmManager orchestration proof",
    )
    parser.add_argument("--json", action="store_true", help="print full JSON result")
    return parser


def _config(args: argparse.Namespace) -> L4SmokeConfig:
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cycle_runner = None
    if args.use_readonly_swarm_manager_orchestrator:
        async def cycle_runner(config: L4SmokeConfig) -> dict:
            return await run_l4_smoke_with_readonly_swarm_manager(
                config,
                state_dir=args.orchestration_state_dir,
            )

    result = run_holon_l4_service(
        _config(args),
        cycles=None if args.forever else args.cycles,
        interval_seconds=args.interval_seconds,
        lock_path=args.lock_path,
        cycle_runner=cycle_runner,
        model_probe_first_cycle_only=args.model_probe_first_cycle_only,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"{result['status']}: {result['completed_cycles']} cycle(s), "
            f"holon={result['holon']}, {result['message']}"
        )
    return 0 if result["status"] in {"completed", "stopped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
