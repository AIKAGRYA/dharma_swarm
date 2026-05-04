#!/usr/bin/env python3
"""Run a governed repo Agent Work Packet.

This is intentionally a small, local runner. It does not launch agents,
stage files, commit, push, reset, clean, or manage branches. It turns a
human-approved job packet into deterministic mechanics:

* verify worktree identity
* verify dirty-file scope before and after commands
* reject mutating git commands
* run explicit argv-based gates
* write a JSON witness report

Packet formats: JSON, TOML, or YAML when PyYAML is installed.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_REPORT_TEMPLATE = ".dharma/agentops/runs/{packet_id}.json"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_MAX_OUTPUT_CHARS = 20_000

MUTATING_GIT_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("git", "add"),
    ("git", "am"),
    ("git", "apply"),
    ("git", "bisect"),
    ("git", "branch"),
    ("git", "cherry-pick"),
    ("git", "checkout"),
    ("git", "clean"),
    ("git", "commit"),
    ("git", "merge"),
    ("git", "mv"),
    ("git", "pull"),
    ("git", "push"),
    ("git", "rebase"),
    ("git", "reset"),
    ("git", "restore"),
    ("git", "revert"),
    ("git", "rm"),
    ("git", "stash"),
    ("git", "switch"),
    ("git", "tag"),
    ("git", "worktree"),
)


class PacketError(Exception):
    """Packet validation or governance failure."""


@dataclass(frozen=True)
class CommandSpec:
    name: str
    argv: list[str]
    cwd: str | None
    env: dict[str, str]
    timeout_seconds: int
    max_output_chars: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_git(args: list[str], repo_root: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PacketError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def repo_root_from_cwd() -> Path:
    return Path(run_git(["rev-parse", "--show-toplevel"])).resolve()


def current_branch(repo_root: Path) -> str:
    return run_git(["branch", "--show-current"], repo_root)


def current_head(repo_root: Path) -> str:
    return run_git(["rev-parse", "HEAD"], repo_root)


def load_packet(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PacketError(f"could not read packet {path}: {exc}") from exc

    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(text)
        elif suffix == ".toml":
            import tomllib

            data = tomllib.loads(text)
        elif suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore[import-not-found]
            except ImportError as exc:
                raise PacketError("YAML packets require PyYAML; use JSON or TOML instead") from exc
            data = yaml.safe_load(text)
        else:
            raise PacketError("packet must end in .json, .toml, .yaml, or .yml")
    except PacketError:
        raise
    except Exception as exc:  # pragma: no cover - parser-specific message
        raise PacketError(f"could not parse packet {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise PacketError("packet root must be an object")
    return data


def safe_packet_id(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise PacketError("packet.id must be a non-empty string")
    packet_id = raw.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", packet_id):
        raise PacketError("packet.id may contain only letters, numbers, '_', '.', ':', and '-'")
    return packet_id


def normalize_repo_path(path: str, *, field: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise PacketError(f"{field} entries must be non-empty strings")
    candidate = path.strip().replace("\\", "/")
    if candidate.startswith("/"):
        raise PacketError(f"{field} entries must be repo-relative: {path}")
    posix = PurePosixPath(candidate)
    if any(part == ".." for part in posix.parts):
        raise PacketError(f"{field} entries must not traverse upward: {path}")
    if str(posix) in {"", "."}:
        raise PacketError(f"{field} entries must name a file, dir, or glob")
    return posix.as_posix()


def normalize_patterns(values: Any, *, field: str, required: bool = False) -> list[str]:
    if values is None:
        if required:
            raise PacketError(f"{field} is required")
        return []
    if not isinstance(values, list):
        raise PacketError(f"{field} must be a list")
    patterns = [normalize_repo_path(value, field=field) for value in values]
    if required and not patterns:
        raise PacketError(f"{field} must contain at least one entry")
    return patterns


def pattern_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if fnmatch.fnmatchcase(path, pattern):
        return True
    if fnmatch.fnmatchcase(path, f"{pattern}/**"):
        return True
    return False


def files_matching(path: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if pattern_matches(path, pattern)]


def parse_status_line(line: str) -> list[str]:
    if not line:
        return []
    raw = line[3:] if len(line) > 3 else ""
    if " -> " in raw:
        old_path, new_path = raw.split(" -> ", 1)
        return [old_path.strip().strip('"'), new_path.strip().strip('"')]
    return [raw.strip().strip('"')] if raw.strip() else []


def dirty_files(repo_root: Path) -> list[str]:
    out = run_git(["status", "--porcelain=v1", "-uall"], repo_root)
    files: set[str] = set()
    for line in out.splitlines():
        for path in parse_status_line(line):
            if path:
                files.add(path.replace("\\", "/"))
    return sorted(files)


def scope_violations(
    paths: list[str],
    *,
    allowed_patterns: list[str],
    forbidden_patterns: list[str],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for path in paths:
        forbidden = files_matching(path, forbidden_patterns)
        allowed = files_matching(path, allowed_patterns)
        if forbidden:
            violations.append(
                {
                    "path": path,
                    "reason": "forbidden",
                    "patterns": forbidden,
                }
            )
        elif not allowed:
            violations.append(
                {
                    "path": path,
                    "reason": "outside_allowed_scope",
                    "patterns": [],
                }
            )
    return violations


def validate_worktree(packet: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    worktree = packet.get("worktree") or {}
    if not isinstance(worktree, dict):
        raise PacketError("worktree must be an object when provided")

    expected_path = worktree.get("path")
    if expected_path is not None:
        expected = Path(str(expected_path)).expanduser().resolve()
        if expected != repo_root:
            errors.append(f"worktree.path expected {expected}, got {repo_root}")

    expected_branch = worktree.get("branch")
    if expected_branch is not None:
        actual_branch = current_branch(repo_root)
        if actual_branch != str(expected_branch):
            errors.append(f"worktree.branch expected {expected_branch}, got {actual_branch}")

    expected_head = worktree.get("head")
    if expected_head is not None:
        actual_head = current_head(repo_root)
        if not actual_head.startswith(str(expected_head)):
            errors.append(f"worktree.head expected {expected_head}, got {actual_head}")

    return errors


def command_prefix(argv: list[str], length: int) -> tuple[str, ...]:
    tokens = [Path(argv[0]).name.lower(), *(part.lower() for part in argv[1:length])]
    return tuple(tokens)


def validate_command_spec(raw: Any, index: int, packet: dict[str, Any]) -> CommandSpec:
    if not isinstance(raw, dict):
        raise PacketError(f"commands[{index}] must be an object")
    if "run" in raw or raw.get("shell"):
        raise PacketError(
            f"commands[{index}] must use argv, not shell/run strings; "
            "this runner intentionally avoids shell expansion"
        )
    argv = raw.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(p, str) and p for p in argv):
        raise PacketError(f"commands[{index}].argv must be a non-empty list of strings")

    policy = packet.get("command_policy") or {}
    if not isinstance(policy, dict):
        raise PacketError("command_policy must be an object when provided")
    allow_git_mutation = bool(policy.get("allow_git_mutation", False))
    if not allow_git_mutation:
        for prefix in MUTATING_GIT_PREFIXES:
            if command_prefix(argv, len(prefix)) == prefix:
                rendered = " ".join(argv[: len(prefix)])
                raise PacketError(
                    f"commands[{index}] uses forbidden mutating git command: {rendered}"
                )

    env = raw.get("env") or {}
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        raise PacketError(f"commands[{index}].env must be an object of string values")

    cwd = raw.get("cwd")
    if cwd is not None:
        cwd = str(cwd).strip()
        if cwd == ".":
            cwd = None
        else:
            cwd = normalize_repo_path(cwd, field=f"commands[{index}].cwd")

    name = raw.get("name") or f"command-{index + 1}"
    if not isinstance(name, str) or not name.strip():
        raise PacketError(f"commands[{index}].name must be a non-empty string")

    timeout = raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(timeout, int) or timeout <= 0:
        raise PacketError(f"commands[{index}].timeout_seconds must be a positive integer")

    max_output = raw.get("max_output_chars", DEFAULT_MAX_OUTPUT_CHARS)
    if not isinstance(max_output, int) or max_output <= 0:
        raise PacketError(f"commands[{index}].max_output_chars must be a positive integer")

    return CommandSpec(
        name=name.strip(),
        argv=argv,
        cwd=cwd,
        env=env,
        timeout_seconds=timeout,
        max_output_chars=max_output,
    )


def validate_commands(packet: dict[str, Any]) -> list[CommandSpec]:
    commands = packet.get("commands") or []
    if not isinstance(commands, list):
        raise PacketError("commands must be a list")
    return [validate_command_spec(command, index, packet) for index, command in enumerate(commands)]


def require_approval(packet: dict[str, Any], supplied: str | None) -> None:
    approval = packet.get("approval") or {}
    if not isinstance(approval, dict):
        raise PacketError("approval must be an object when provided")
    if not bool(approval.get("required", False)):
        return
    token = approval.get("token") or "approved"
    if not isinstance(token, str) or not token:
        raise PacketError("approval.token must be a non-empty string when approval is required")
    if supplied != token:
        raise PacketError("packet requires human approval token; pass --approval with the exact token")


def resolve_command_cwd(repo_root: Path, cwd: str | None) -> Path:
    if cwd is None:
        return repo_root
    resolved = (repo_root / cwd).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise PacketError(f"command cwd escapes repo: {cwd}") from exc
    return resolved


def trim_output(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n...[truncated {omitted} chars]"


def run_command(repo_root: Path, command: CommandSpec) -> dict[str, Any]:
    started = time.monotonic()
    env = os.environ.copy()
    env.update(command.env)
    cwd = resolve_command_cwd(repo_root, command.cwd)
    try:
        result = subprocess.run(
            command.argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=command.timeout_seconds,
            check=False,
        )
        exit_code = result.returncode
        timed_out = False
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        timed_out = True
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr += f"\ncommand timed out after {command.timeout_seconds}s"

    duration = time.monotonic() - started
    return {
        "name": command.name,
        "argv": command.argv,
        "cwd": str(cwd.relative_to(repo_root)) if cwd != repo_root else ".",
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 3),
        "stdout": trim_output(stdout, command.max_output_chars),
        "stderr": trim_output(stderr, command.max_output_chars),
    }


def report_path_for(packet: dict[str, Any], repo_root: Path, packet_id: str) -> Path:
    report = packet.get("report") or {}
    if not isinstance(report, dict):
        raise PacketError("report must be an object when provided")
    raw = report.get("path") or DEFAULT_REPORT_TEMPLATE.format(packet_id=packet_id)
    if not isinstance(raw, str) or not raw:
        raise PacketError("report.path must be a non-empty string")
    rendered = raw.format(packet_id=packet_id)
    path = Path(rendered)
    if not path.is_absolute():
        path = repo_root / path
    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise PacketError("report.path must stay inside the repo") from exc
    return resolved


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_scope(packet: dict[str, Any]) -> tuple[list[str], list[str], bool]:
    scope = packet.get("scope")
    if not isinstance(scope, dict):
        raise PacketError("scope is required and must be an object")
    allowed = normalize_patterns(scope.get("allowed_files"), field="scope.allowed_files", required=True)
    forbidden = normalize_patterns(scope.get("forbidden_files"), field="scope.forbidden_files")

    preflight = packet.get("preflight") or {}
    if not isinstance(preflight, dict):
        raise PacketError("preflight must be an object when provided")
    require_clean = bool(preflight.get("require_clean", False))
    return allowed, forbidden, require_clean


def execute_packet(
    packet_path: Path,
    *,
    approval: str | None,
    dry_run: bool,
    check_only: bool,
    no_report: bool,
) -> tuple[int, dict[str, Any]]:
    repo_root = repo_root_from_cwd()
    packet = load_packet(packet_path)
    packet_id = safe_packet_id(packet.get("id"))
    allowed, forbidden, require_clean = build_scope(packet)
    commands = validate_commands(packet)
    require_approval(packet, approval)

    started_at = utc_now()
    branch = current_branch(repo_root)
    head = current_head(repo_root)
    report: dict[str, Any] = {
        "packet_id": packet_id,
        "title": packet.get("title"),
        "agent_profile": packet.get("agent_profile"),
        "started_at": started_at,
        "finished_at": None,
        "repo_root": str(repo_root),
        "branch": branch,
        "head": head,
        "dry_run": dry_run,
        "check_only": check_only,
        "scope": {
            "allowed_files": allowed,
            "forbidden_files": forbidden,
        },
        "dirty_before": [],
        "dirty_after": [],
        "violations": [],
        "commands": [],
        "status": "running",
    }

    worktree_errors = validate_worktree(packet, repo_root)
    dirty_before = dirty_files(repo_root)
    before_violations = scope_violations(
        dirty_before,
        allowed_patterns=allowed,
        forbidden_patterns=forbidden,
    )
    if require_clean and dirty_before:
        before_violations.extend(
            {"path": path, "reason": "preflight_requires_clean", "patterns": []}
            for path in dirty_before
        )
    report["dirty_before"] = dirty_before
    report["violations"].extend({"phase": "preflight", "message": error} for error in worktree_errors)
    report["violations"].extend({"phase": "preflight", **item} for item in before_violations)

    if worktree_errors or before_violations:
        report["status"] = "failed"
        report["finished_at"] = utc_now()
        if not no_report:
            write_report(report_path_for(packet, repo_root, packet_id), report)
        return 1, report

    if dry_run or check_only:
        report["status"] = "passed"
        report["finished_at"] = utc_now()
        if not no_report:
            write_report(report_path_for(packet, repo_root, packet_id), report)
        return 0, report

    exit_code = 0
    for command in commands:
        result = run_command(repo_root, command)
        report["commands"].append(result)
        if result["exit_code"] != 0:
            exit_code = int(result["exit_code"])
            break

        dirty_now = dirty_files(repo_root)
        command_violations = scope_violations(
            dirty_now,
            allowed_patterns=allowed,
            forbidden_patterns=forbidden,
        )
        if command_violations:
            report["violations"].extend({"phase": command.name, **item} for item in command_violations)
            exit_code = 1
            break

    dirty_after = dirty_files(repo_root)
    after_violations = scope_violations(
        dirty_after,
        allowed_patterns=allowed,
        forbidden_patterns=forbidden,
    )
    report["dirty_after"] = dirty_after
    report["violations"].extend({"phase": "postflight", **item} for item in after_violations)

    if exit_code == 0 and after_violations:
        exit_code = 1

    report["status"] = "passed" if exit_code == 0 else "failed"
    report["finished_at"] = utc_now()
    if not no_report:
        write_report(report_path_for(packet, repo_root, packet_id), report)
    return exit_code, report


def print_summary(report: dict[str, Any]) -> None:
    print(f"Agent Work Packet: {report['packet_id']}")
    if report.get("title"):
        print(f"Title: {report['title']}")
    print(f"Repo: {report['repo_root']}")
    print(f"Branch: {report['branch']}")
    print(f"Head: {report['head']}")
    print(f"Status: {report['status']}")
    print(f"Dirty before: {len(report['dirty_before'])}")
    print(f"Dirty after: {len(report['dirty_after'])}")

    if report["commands"]:
        print("Commands:")
        for command in report["commands"]:
            print(
                f"  - {command['name']}: exit={command['exit_code']} "
                f"duration={command['duration_seconds']}s"
            )
            if command["exit_code"] != 0:
                if command["stdout"]:
                    print("    stdout:")
                    print(indent(command["stdout"], "      "))
                if command["stderr"]:
                    print("    stderr:")
                    print(indent(command["stderr"], "      "))

    if report["violations"]:
        print("Violations:")
        for violation in report["violations"]:
            details = violation.get("path") or violation.get("message")
            reason = violation.get("reason") or "worktree"
            phase = violation.get("phase")
            print(f"  - {phase}: {reason}: {details}")


def indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True, help="Path to the Agent Work Packet")
    parser.add_argument("--approval", help="Human approval token, when packet requires one")
    parser.add_argument("--dry-run", action="store_true", help="Validate packet and scope without commands")
    parser.add_argument("--check-only", action="store_true", help="Validate packet, worktree, and scope only")
    parser.add_argument("--no-report", action="store_true", help="Do not write the JSON witness report")
    args = parser.parse_args(argv)

    try:
        exit_code, report = execute_packet(
            Path(args.packet),
            approval=args.approval,
            dry_run=args.dry_run,
            check_only=args.check_only,
            no_report=args.no_report,
        )
    except PacketError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print_summary(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
