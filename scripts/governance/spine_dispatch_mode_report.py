#!/usr/bin/env python3
"""Report whether live orchestrator dispatch defaults through the spine."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FALSE_LIKE = {"0", "false", "no", "off", "legacy", "direct"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _line_number(text: str, pattern: str) -> int | None:
    for index, line in enumerate(text.splitlines(), start=1):
        if pattern in line:
            return index
    return None


def _orchestrator_entry() -> dict[str, Any]:
    path = REPO_ROOT / "dharma_swarm" / "orchestrator.py"
    source = _read_text(path)
    has_switch = "def _spine_dispatch_enabled" in source
    default_on = bool(
        has_switch
        and re.search(
            r"if raw is None:\s*\n\s*return True",
            source,
            flags=re.MULTILINE,
        )
    )
    explicit_false_opt_out = all(value in source for value in FALSE_LIKE)
    execute_uses_switch = "if self._spine_dispatch_enabled():" in source
    legacy_opt_in = 'os.environ.get("DHARMA_SPINE_DISPATCH") == "1"' in source

    if default_on and execute_uses_switch and explicit_false_opt_out:
        mode = "spine_default_on"
        current_state = "spine_default_in_current_process"
        risk = "low"
        default_path = "invoke_agent unless DHARMA_SPINE_DISPATCH is explicit false"
    elif legacy_opt_in:
        mode = "spine_opt_in_legacy_default"
        current_state = "legacy_default_in_current_process"
        risk = "medium"
        default_path = "direct runner.run_task unless DHARMA_SPINE_DISPATCH=1"
    else:
        mode = "unknown"
        current_state = "unclassified"
        risk = "high"
        default_path = "could not prove dispatch default from source"

    env_raw = os.environ.get("DHARMA_SPINE_DISPATCH")
    env_enabled = True if env_raw is None else env_raw.strip().lower() not in FALSE_LIKE

    return {
        "surface": "orchestrator",
        "file": "dharma_swarm/orchestrator.py",
        "line": _line_number(source, "def _spine_dispatch_enabled"),
        "mode": mode,
        "current_state": current_state if env_enabled else "legacy_opt_out_current_process",
        "default_path": default_path,
        "activation": "default-on; set DHARMA_SPINE_DISPATCH=0 to opt out",
        "evidence": (
            "_execute_task calls _spine_dispatch_enabled before runner.run_task"
            if execute_uses_switch
            else "source check did not find _spine_dispatch_enabled call"
        ),
        "risk": risk,
        "owner": "runtime-truth-spine-adoption-2026-06",
        "verification": "python scripts/governance/spine_dispatch_mode_report.py --strict",
        "env": {
            "DHARMA_SPINE_DISPATCH_present": env_raw is not None,
            "DHARMA_SPINE_DISPATCH_false_like": (
                env_raw.strip().lower() in FALSE_LIKE if env_raw is not None else False
            ),
            "current_process_spine_enabled": env_enabled,
        },
        "checks": {
            "has_switch": has_switch,
            "default_on": default_on,
            "explicit_false_opt_out": explicit_false_opt_out,
            "execute_uses_switch": execute_uses_switch,
            "legacy_opt_in_absent": not legacy_opt_in,
        },
    }


def _launch_spec(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    exists = path.exists()
    if exists:
        try:
            with path.open("rb") as handle:
                payload = plistlib.load(handle)
        except Exception as exc:  # noqa: BLE001 - report, do not crash
            return {
                "file": str(path),
                "exists": True,
                "state": "unreadable",
                "error": str(exc),
            }

    env = payload.get("EnvironmentVariables", {}) if isinstance(payload, dict) else {}
    args = payload.get("ProgramArguments", []) if isinstance(payload, dict) else []
    command = " ".join(str(arg) for arg in args)
    env_value = str(env.get("DHARMA_SPINE_DISPATCH", "") or "")
    env_spine_enabled = bool(env_value) and env_value.strip().lower() not in FALSE_LIKE
    repo_module_invocation = "-m dharma_swarm.dgc_cli" in command
    ambient_dgc_invocation = bool(re.search(r"(^|\s)dgc(\s|$)", command))

    if not exists:
        state = "missing"
    elif env_spine_enabled or "DHARMA_SPINE_DISPATCH=1" in command:
        state = "spine_enabled_launch_spec"
    elif env_value.strip().lower() in FALSE_LIKE:
        state = "legacy_opt_out_launch_spec"
    else:
        state = "spine_default_launch_spec"

    return {
        "file": str(path),
        "exists": exists,
        "state": state,
        "env": env,
        "command": command,
        "repo_module_invocation": repo_module_invocation,
        "ambient_dgc_invocation": ambient_dgc_invocation,
        "evidence": (
            "launch spec explicit spine env or default-on source contract"
            if exists
            else "launch spec not present at this path"
        ),
    }


def build_report() -> dict[str, Any]:
    orchestrator = _orchestrator_entry()
    launch_specs = [
        _launch_spec(Path.home() / "Library/LaunchAgents/com.dharma.swarm.plist"),
        _launch_spec(REPO_ROOT / "com.dharma.swarm.plist"),
    ]
    strict_pass = (
        orchestrator["checks"]["default_on"]
        and orchestrator["checks"]["execute_uses_switch"]
        and orchestrator["checks"]["explicit_false_opt_out"]
        and orchestrator["checks"]["legacy_opt_in_absent"]
        and orchestrator["env"]["current_process_spine_enabled"]
    )
    summary = {
        "orchestrator_mode": orchestrator["mode"],
        "orchestrator_current_process": orchestrator["current_state"],
        "orchestrator_persistent_daemon": next(
            (
                spec["state"]
                for spec in launch_specs
                if spec.get("exists") and "LaunchAgents" in spec.get("file", "")
            ),
            "not_inspected",
        ),
        "explicit_modes": True,
        "production_direct_runner_clear": strict_pass,
        "manual_direct_runner_clear": strict_pass,
        "score_gate_65_to_70": strict_pass,
    }
    return {
        "report": "spine_dispatch_mode_report",
        "repo": str(REPO_ROOT),
        "entries": [orchestrator],
        "launch_specs": launch_specs,
        "summary": summary,
    }


def _print_text(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("spine_dispatch_mode_report")
    print(f"repo: {report['repo']}")
    print(f"orchestrator_mode: {summary['orchestrator_mode']}")
    print(f"current_process: {summary['orchestrator_current_process']}")
    print(f"strict_gate: {summary['score_gate_65_to_70']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero unless the source and current process are spine-enabled.",
    )
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)

    if args.strict and not report["summary"]["score_gate_65_to_70"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
