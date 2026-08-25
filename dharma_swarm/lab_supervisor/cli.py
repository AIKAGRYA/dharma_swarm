"""JSON command-line surface for the lab supervisor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapters import BoundedCommandRunner, command_hash
from .config import ConfigError, load_config
from .engine import Supervisor
from .prompts import anomaly_output_schema


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _features(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    runner = BoundedCommandRunner(config.policy.max_subprocess_calls_per_tick)
    rows: dict[str, Any] = {}
    failures: list[str] = []
    for lab in config.labs:
        commands: dict[str, Any] = {}
        for name in (
            "status_probe",
            "keep_halted",
            "quarantine_provider",
            "rotate_provider",
            "bounded_trial",
        ):
            spec = getattr(lab, name)
            if spec is None:
                commands[name] = {
                    "declared": False,
                    "executable_available": False,
                    "feature_verified": False,
                }
                continue
            outcome = runner.feature_detect(spec)
            commands[name] = {
                "declared": True,
                "executable_available": outcome.available,
                "feature_verified": outcome.succeeded,
                "reason": outcome.error or ("" if outcome.succeeded else "feature_probe_failed"),
                "command_sha256": command_hash(spec.argv, cwd=spec.cwd),
                "feature_command_sha256": (
                    command_hash(spec.feature_argv, cwd=spec.cwd)
                    if spec.feature_argv
                    else ""
                ),
            }
            if not outcome.succeeded:
                failures.append(f"{lab.name}:{name}:{commands[name]['reason']}")
        rows[lab.name] = {
            "kind": lab.kind,
            "state_root_exists": lab.state_root.exists(),
            "commands": commands,
        }
    return {
        "schema": "dharma.lab_supervisor.features.v1",
        "config_sha256": config.config_sha256,
        "ready": not failures,
        "failures": failures,
        "labs": rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("anomaly-schema", help="emit the optional read-only analysis schema")
    validate = sub.add_parser("validate-config", help="validate config and feature availability")
    validate.add_argument("--config", type=Path, required=True)
    tick = sub.add_parser("tick", help="run one bounded lock-protected tick")
    tick.add_argument("--config", type=Path, required=True)
    tick.add_argument("--state-root", type=Path, required=True)
    tick.add_argument(
        "--allow-actions",
        action="store_true",
        help="second key for declared actions; config dry_run must also be false",
    )
    status = sub.add_parser("status", help="emit runtime and receipt-chain status")
    status.add_argument("--config", type=Path, required=True)
    status.add_argument("--state-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "anomaly-schema":
            _print(anomaly_output_schema())
            return 0
        if args.command == "validate-config":
            features = _features(args.config)
            _print(features)
            return 0 if features["ready"] else 4
        config = load_config(args.config)
        supervisor = Supervisor(config, state_root=args.state_root)
        if args.command == "tick":
            report = supervisor.run_tick(allow_actions=args.allow_actions)
            _print(report.to_dict())
            return 4 if report.internal_failure else 0
        _print(supervisor.status())
        return 0
    except ConfigError as exc:
        _print({"schema": "dharma.lab_supervisor.error.v1", "error": str(exc)})
        return 2
    except RuntimeError as exc:
        _print({"schema": "dharma.lab_supervisor.error.v1", "error": str(exc)})
        return 3
    except OSError as exc:
        _print(
            {
                "schema": "dharma.lab_supervisor.error.v1",
                "error": f"supervisor_io_failure:{type(exc).__name__}",
            }
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())
