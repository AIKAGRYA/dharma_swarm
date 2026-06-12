#!/usr/bin/env python3
"""Audit local A2A/NATS daemon wiring without mutating runtime state.

The production A2A path can only be trusted when long-running daemons point at
real modules/scripts and the intended broker scope. This audit checks the local
LaunchAgent declarations and their recent logs; it does not load, unload, start,
stop, pull, ack, or publish anything.
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dharma.a2a.daemon_wiring_audit.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "nats_reset"
    / "2026-06-13"
    / "A2A_DAEMON_WIRING_AUDIT.json"
)
A2A_TOKENS = ("a2a", "nats")
LOCAL_BROKER_MARKERS = ("127.0.0.1", "localhost")
AGNI_BROKER_MARKERS = ("agni", "157.245.193.15", "wss://")
LOG_PROBLEM_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"No module named (?P<detail>[\w.]+)", "missing_python_module"),
    (r"can't open file '(?P<detail>[^']+)'", "missing_script_file"),
    (r"ImportError: (?P<detail>[^\n]+)", "import_error"),
    (r"TimeoutError(?P<detail>[^\n]*)", "timeout_error"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_plist(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = plistlib.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected plist dictionary")
    return payload


def as_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def is_a2a_candidate(path: Path, payload: dict[str, Any]) -> bool:
    label = str(payload.get("Label") or "")
    args = " ".join(as_list(payload.get("ProgramArguments")))
    env = payload.get("EnvironmentVariables")
    env_text = json.dumps(env, sort_keys=True) if isinstance(env, dict) else ""
    text = f"{path.name} {label} {args} {env_text}".lower()
    return any(token in text for token in A2A_TOKENS)


def resolve_working_dir(payload: dict[str, Any]) -> Path | None:
    working_dir = payload.get("WorkingDirectory")
    if not isinstance(working_dir, str) or not working_dir:
        return None
    return Path(working_dir).expanduser()


def module_path_candidates(module: str, working_dir: Path | None) -> list[Path]:
    if working_dir is None:
        return []
    parts = module.split(".")
    return [
        working_dir.joinpath(*parts).with_suffix(".py"),
        working_dir.joinpath(*parts, "__init__.py"),
    ]


def module_exists(module: str, working_dir: Path | None) -> bool:
    return any(path.exists() for path in module_path_candidates(module, working_dir))


def script_path(arg: str, working_dir: Path | None) -> Path:
    path = Path(arg).expanduser()
    if path.is_absolute() or working_dir is None:
        return path
    return working_dir / path


def module_arg(args: list[str]) -> str | None:
    for idx, arg in enumerate(args[:-1]):
        if arg == "-m":
            return args[idx + 1]
    return None


def script_args(args: list[str]) -> list[str]:
    return [arg for arg in args[1:] if arg.endswith(".py")]


def broker_scope(url: str | None) -> str:
    if not url:
        return "missing"
    lowered = url.lower()
    if any(marker in lowered for marker in AGNI_BROKER_MARKERS):
        return "agni"
    if any(marker in lowered for marker in LOCAL_BROKER_MARKERS):
        return "local"
    return "unknown"


def add_issue(
    issues: list[dict[str, Any]],
    *,
    severity: str,
    issue_type: str,
    message: str,
    evidence: str | None = None,
) -> None:
    issues.append(
        {
            "severity": severity,
            "type": issue_type,
            "message": message,
            "evidence": evidence,
        }
    )


def scan_log(path: Path, *, tail_bytes: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > tail_bytes:
                handle.seek(size - tail_bytes)
            text = handle.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return [
            {
                "severity": "WARN",
                "type": "log_unreadable",
                "message": f"Could not read log: {exc}",
                "evidence": str(path),
            }
        ]
    problems: list[dict[str, Any]] = []
    for pattern, issue_type in LOG_PROBLEM_PATTERNS:
        for match in re.finditer(pattern, text):
            detail = (match.groupdict().get("detail") or "").strip()
            problems.append(
                {
                    "severity": "ERROR" if issue_type != "timeout_error" else "WARN",
                    "type": issue_type,
                    "message": detail or issue_type,
                    "evidence": str(path),
                }
            )
    return problems[-8:]


def dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str]] = set()
    for issue in issues:
        key = (
            str(issue.get("type") or ""),
            issue.get("evidence") if isinstance(issue.get("evidence"), str) else None,
            str(issue.get("message") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def evaluate_launch_agent(
    path: Path,
    payload: dict[str, Any],
    *,
    expected_broker_scope: str,
    log_tail_bytes: int,
) -> dict[str, Any]:
    args = as_list(payload.get("ProgramArguments"))
    env = payload.get("EnvironmentVariables")
    env = env if isinstance(env, dict) else {}
    working_dir = resolve_working_dir(payload)
    issues: list[dict[str, Any]] = []

    if not args:
        add_issue(
            issues,
            severity="ERROR",
            issue_type="missing_program_arguments",
            message="LaunchAgent has no ProgramArguments",
        )
    elif Path(args[0]).is_absolute() and not Path(args[0]).exists():
        add_issue(
            issues,
            severity="ERROR",
            issue_type="missing_program",
            message=f"Program does not exist: {args[0]}",
            evidence=args[0],
        )

    if working_dir is not None and not working_dir.exists():
        add_issue(
            issues,
            severity="ERROR",
            issue_type="missing_working_directory",
            message=f"WorkingDirectory does not exist: {working_dir}",
            evidence=str(working_dir),
        )

    module = module_arg(args)
    if module and not module_exists(module, working_dir):
        add_issue(
            issues,
            severity="ERROR",
            issue_type="missing_module_target",
            message=f"Module target is not present under WorkingDirectory: {module}",
            evidence=str(working_dir) if working_dir else None,
        )

    for script in script_args(args):
        resolved = script_path(script, working_dir)
        if not resolved.exists():
            add_issue(
                issues,
                severity="ERROR",
                issue_type="missing_script_target",
                message=f"Script target does not exist: {resolved}",
                evidence=str(resolved),
            )

    nats_url = str(env.get("DHARMA_NATS_URL") or "")
    observed_scope = broker_scope(nats_url)
    if expected_broker_scope != "any" and observed_scope not in {
        expected_broker_scope,
        "missing",
    }:
        add_issue(
            issues,
            severity="ERROR",
            issue_type="broker_scope_mismatch",
            message=(
                f"Expected {expected_broker_scope} broker scope, "
                f"observed {observed_scope}: {nats_url}"
            ),
            evidence=nats_url,
        )

    log_paths = [
        payload.get("StandardErrorPath"),
        payload.get("StandardOutPath"),
    ]
    for log_path in log_paths:
        if isinstance(log_path, str) and log_path:
            issues.extend(scan_log(Path(log_path).expanduser(), tail_bytes=log_tail_bytes))

    issues = dedupe_issues(issues)
    severity_counts = Counter(issue["severity"] for issue in issues)
    status = "FAIL" if severity_counts["ERROR"] else "WARN" if severity_counts["WARN"] else "PASS"
    return {
        "label": str(payload.get("Label") or path.stem),
        "path": str(path),
        "status": status,
        "working_directory": str(working_dir) if working_dir else None,
        "program_arguments": args,
        "module_target": module,
        "script_targets": [str(script_path(arg, working_dir)) for arg in script_args(args)],
        "nats_url": nats_url or None,
        "broker_scope": observed_scope,
        "issue_count": len(issues),
        "issues": issues,
    }


def discover_launch_agents(launch_agents_dir: Path) -> list[Path]:
    if not launch_agents_dir.exists():
        return []
    return sorted(launch_agents_dir.glob("*.plist"))


def build_audit(
    *,
    launch_agents_dir: Path,
    expected_broker_scope: str = "agni",
    log_tail_bytes: int = 65536,
    created_at: str | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []
    for path in discover_launch_agents(launch_agents_dir):
        try:
            payload = read_plist(path)
        except Exception as exc:
            parse_errors.append(
                {
                    "path": str(path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        if not is_a2a_candidate(path, payload):
            continue
        candidates.append(
            evaluate_launch_agent(
                path,
                payload,
                expected_broker_scope=expected_broker_scope,
                log_tail_bytes=log_tail_bytes,
            )
        )

    status_counts = Counter(candidate["status"] for candidate in candidates)
    issue_counts = Counter(
        issue["type"]
        for candidate in candidates
        for issue in candidate.get("issues", [])
        if isinstance(issue, dict)
    )
    status = "FAIL" if status_counts["FAIL"] else "WARN" if status_counts["WARN"] else "PASS"
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "status": status,
        "production_claim": False,
        "expected_broker_scope": expected_broker_scope,
        "launch_agents_dir": str(launch_agents_dir),
        "candidate_count": len(candidates),
        "status_counts": dict(sorted(status_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "parse_errors": parse_errors,
        "candidates": candidates,
        "interpretation": (
            "PASS means declared local A2A/NATS daemons point at existing targets "
            "and do not contradict the expected broker scope. It does not prove "
            "peer-agent semantic work, production readiness, or NATS delivery."
        ),
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--launch-agents-dir",
        default=str(Path.home() / "Library" / "LaunchAgents"),
        help="Directory containing LaunchAgent plist files.",
    )
    parser.add_argument(
        "--expected-broker-scope",
        choices=("agni", "local", "any"),
        default="agni",
        help="Expected production broker scope for A2A/NATS daemons.",
    )
    parser.add_argument("--log-tail-bytes", type=int, default=65536)
    parser.add_argument("--receipt-path", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--write", action="store_true", help="Write the JSON receipt.")
    parser.add_argument("--check", action="store_true", help="Exit non-zero when status is FAIL.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = build_audit(
        launch_agents_dir=Path(args.launch_agents_dir).expanduser(),
        expected_broker_scope=args.expected_broker_scope,
        log_tail_bytes=args.log_tail_bytes,
    )
    if args.write:
        write_receipt(Path(args.receipt_path).expanduser(), payload)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['status']} candidates={payload['candidate_count']} "
            f"issues={sum(payload['issue_counts'].values())}"
        )
    if args.check and payload["status"] == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
