"""Command line interface for standalone Holon."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from holon.a2a import ping_agents
from holon.burn_in import BurnInConfig, run_burn_in
from holon.holon_runtime import runtime_from_identity
from holon.organs.health import holon_status
from holon.supervisor import SupervisorConfig, run_supervisor
from holon.verifier import verify_standalone


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="holon")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="Run standalone isolation checks")
    verify.add_argument("--json", action="store_true", dest="as_json")

    wake = sub.add_parser("wake", help="Run one provider-backed cycle")
    wake.add_argument("name")
    wake.add_argument("prompt")
    wake.add_argument("--agents-root", type=Path, default=Path.home() / ".dharma" / "agents")

    supervise = sub.add_parser("supervise", help="Run bounded supervisor cycles")
    supervise.add_argument("name")
    supervise.add_argument("--prompt", default="Run one bounded autonomy cycle and report evidence.")
    supervise.add_argument("--cycles", type=int, default=1)
    supervise.add_argument("--agents-root", type=Path, default=Path.home() / ".dharma" / "agents")

    burn_in = sub.add_parser("burn-in", help="Run bounded supervisor burn-in samples")
    burn_in.add_argument("name")
    burn_in.add_argument("--prompt", default="Run one bounded autonomy cycle and report evidence.")
    burn_in.add_argument("--duration-seconds", type=float, default=0.0)
    burn_in.add_argument("--interval-seconds", type=float, default=0.0)
    burn_in.add_argument("--min-cycles", type=int, default=1)
    burn_in.add_argument("--cap-usd", type=float, default=0.0)
    burn_in.add_argument("--agents-root", type=Path, default=Path.home() / ".dharma" / "agents")
    burn_in.add_argument("--multi-hour-threshold-seconds", type=float, default=7200.0)
    burn_in.add_argument("--no-stop-on-failure", action="store_true")

    status = sub.add_parser("status", help="Project local Holon health")
    status.add_argument("name")
    status.add_argument("--agents-root", type=Path, default=Path.home() / ".dharma" / "agents")

    a2a = sub.add_parser("a2a-ping", help="Probe local A2A agent identities")
    a2a.add_argument("name")
    a2a.add_argument("--agents-root", type=Path, default=Path.home() / ".dharma" / "agents")
    a2a.add_argument("--min-agents", type=int, default=3)
    return parser


async def async_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        report = verify_standalone()
        if args.as_json:
            print(json.dumps(report.to_dict(), sort_keys=True, indent=2))
        else:
            print(f"standalone={report.status}")
            for finding in report.findings:
                if finding.status == "fail":
                    print(f"FAIL {finding.code}: {finding.path} {finding.message}")
        return 0 if report.status == "pass" else 1
    if args.command == "wake":
        runtime = runtime_from_identity(args.name, agents_root=args.agents_root)
        result = await runtime.run_provider_cycle(args.prompt)
        print(json.dumps(result.to_dict(), sort_keys=True, indent=2))
        return 0 if result.status == "ran" else 1
    if args.command == "supervise":
        output = await run_supervisor(
            SupervisorConfig(
                name=args.name,
                prompt=args.prompt,
                max_cycles=args.cycles,
                agents_root=args.agents_root,
            )
        )
        print(json.dumps(output, sort_keys=True, indent=2))
        return 0
    if args.command == "burn-in":
        output = await run_burn_in(
            BurnInConfig(
                name=args.name,
                prompt=args.prompt,
                duration_seconds=args.duration_seconds,
                interval_seconds=args.interval_seconds,
                min_cycles=args.min_cycles,
                cap_usd=args.cap_usd,
                agents_root=args.agents_root,
                multi_hour_threshold_seconds=args.multi_hour_threshold_seconds,
                stop_on_failure=not args.no_stop_on_failure,
            )
        )
        print(json.dumps(output, sort_keys=True, indent=2))
        return 0 if output.get("passed") else 1
    if args.command == "status":
        print(json.dumps(holon_status(args.name, agents_root=args.agents_root), sort_keys=True, indent=2))
        return 0
    if args.command == "a2a-ping":
        results = ping_agents(
            holon_name=args.name,
            agents_root=args.agents_root,
            min_agents=args.min_agents,
        )
        print(json.dumps([result.__dict__ for result in results], sort_keys=True, indent=2))
        return 0 if len([item for item in results if item.status == "pass"]) >= args.min_agents else 1
    return 2


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
