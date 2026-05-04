#!/usr/bin/env python3
"""Run a governed local AgentOps work packet.

AgentOps v0 is deliberately small: it validates a machine-readable work
packet, prepares an isolated git worktree, runs declared gates, enforces a
file-scope contract, writes structured reports, and optionally creates a
local commit candidate. It never merges or pushes.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


REPORT_ROOT = Path("reports") / "agentops"
DEFAULT_GATE_TIMEOUT_SECONDS = 900
DEFAULT_MAX_OUTPUT_CHARS = 30_000

BANNED_GATE_GIT_SUBCOMMANDS = {
    "am",
    "cherry-pick",
    "clean",
    "commit",
    "merge",
    "pull",
    "push",
    "rebase",
    "reset",
    "restore",
    "revert",
    "stash",
}
BANNED_SHELL_TOKENS = {"&&", "||", ";", "|", ">", ">>", "<", "<<"}
BANNED_LIVE_COMMAND_TOKENS = {
    "orchestrate-live",
    "live_swarm",
    "autonomy-daemon",
    "autonomous-daemon",
}


class AgentOpsError(Exception):
    """Raised when a packet or repo state fails closed."""


@dataclass(frozen=True)
class GateSpec:
    name: str
    command: str
    argv: list[str]
    env: dict[str, str]
    timeout_seconds: int = DEFAULT_GATE_TIMEOUT_SECONDS
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS


@dataclass(frozen=True)
class CommitPolicy:
    allowed: bool
    message: str


@dataclass(frozen=True)
class ApprovalPolicy:
    before_commit: bool
    before_merge: bool


@dataclass(frozen=True)
class WorkPacket:
    id: str
    base_ref: str
    branch: str
    worktree: Path
    intent: str
    allowed_files: list[str]
    forbidden_files: list[str]
    gates: list[GateSpec]
    commit: CommitPolicy
    approval: ApprovalPolicy


@dataclass(frozen=True)
class ScopeState:
    tracked_changed_files: list[str]
    staged_files: list[str]
    untracked_files: list[str]
    changed_files: list[str]
    violations: list[dict[str, Any]]

    @property
    def passed(self) -> bool:
        return not self.violations


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_seconds: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def run_git(args: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = run_command(["git", *args], cwd=cwd)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"git {' '.join(args)} failed: {detail}")
    return result


def repo_root_from(path: Path) -> Path:
    result = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    return Path(result.stdout.strip()).resolve()


def require_repo_root(path: Path) -> Path:
    root = repo_root_from(path)
    if root != path.resolve():
        raise AgentOpsError(f"run from repo root; got {path.resolve()}, repo root is {root}")
    return root


def safe_packet_id(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise AgentOpsError("id must be a non-empty string")
    packet_id = raw.strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")
    if any(char not in allowed for char in packet_id):
        raise AgentOpsError("id may contain only letters, numbers, '_', '.', ':', and '-'")
    return packet_id


def require_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AgentOpsError(f"{field} is required and must be a non-empty string")
    return value.strip()


def require_bool(data: dict[str, Any], field: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise AgentOpsError(f"{field} is required and must be a boolean")
    return value


def normalize_repo_pattern(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentOpsError(f"{field} entries must be non-empty strings")
    candidate = value.strip().replace("\\", "/")
    if candidate.startswith("/"):
        raise AgentOpsError(f"{field} entries must be repo-relative: {value}")
    posix = PurePosixPath(candidate)
    if any(part == ".." for part in posix.parts):
        raise AgentOpsError(f"{field} entries must not traverse upward: {value}")
    if posix.as_posix() in {"", "."}:
        raise AgentOpsError(f"{field} entries must name a file, directory, or glob")
    return posix.as_posix()


def require_pattern_list(data: dict[str, Any], field: str, *, non_empty: bool) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list):
        raise AgentOpsError(f"{field} is required and must be a list")
    patterns = [normalize_repo_pattern(item, field=field) for item in value]
    if non_empty and not patterns:
        raise AgentOpsError(f"{field} must contain at least one entry")
    return patterns


def path_matches_pattern(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    normalized_pattern = pattern.replace("\\", "/")
    if fnmatch.fnmatchcase(normalized, normalized_pattern):
        return True
    if normalized_pattern.endswith("/"):
        return normalized.startswith(normalized_pattern)
    return fnmatch.fnmatchcase(normalized, f"{normalized_pattern}/**")


def matching_patterns(path: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if path_matches_pattern(path, pattern)]


def parse_gate_command(command: str) -> list[str]:
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise AgentOpsError(f"invalid gate command {command!r}: {exc}") from exc
    if not argv:
        raise AgentOpsError("gate command must not be empty")
    if any(token in BANNED_SHELL_TOKENS for token in argv):
        raise AgentOpsError(f"gate command uses unsupported shell control token: {command}")
    lowered = [Path(part).name.lower() if index == 0 else part.lower() for index, part in enumerate(argv)]
    if lowered[0] == "git" and len(lowered) > 1 and lowered[1] in BANNED_GATE_GIT_SUBCOMMANDS:
        raise AgentOpsError(f"gate command is not allowed to run git {lowered[1]}")
    if any(token in BANNED_LIVE_COMMAND_TOKENS for token in lowered):
        raise AgentOpsError(f"gate command appears to invoke live swarm/autonomy: {command}")
    return argv


def parse_gate(raw: Any, index: int) -> GateSpec:
    if isinstance(raw, str):
        command = raw.strip()
        name = f"gate-{index + 1}"
        env: dict[str, str] = {}
        timeout = DEFAULT_GATE_TIMEOUT_SECONDS
        max_output = DEFAULT_MAX_OUTPUT_CHARS
    elif isinstance(raw, dict):
        command_value = raw.get("command")
        if not isinstance(command_value, str) or not command_value.strip():
            raise AgentOpsError(f"gates[{index}].command is required and must be a string")
        command = command_value.strip()
        name_value = raw.get("name", f"gate-{index + 1}")
        if not isinstance(name_value, str) or not name_value.strip():
            raise AgentOpsError(f"gates[{index}].name must be a non-empty string")
        name = name_value.strip()
        env_value = raw.get("env", {})
        if not isinstance(env_value, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in env_value.items()
        ):
            raise AgentOpsError(f"gates[{index}].env must be an object of string values")
        env = dict(env_value)
        timeout = raw.get("timeout_seconds", DEFAULT_GATE_TIMEOUT_SECONDS)
        if not isinstance(timeout, int) or timeout <= 0:
            raise AgentOpsError(f"gates[{index}].timeout_seconds must be a positive integer")
        max_output = raw.get("max_output_chars", DEFAULT_MAX_OUTPUT_CHARS)
        if not isinstance(max_output, int) or max_output <= 0:
            raise AgentOpsError(f"gates[{index}].max_output_chars must be a positive integer")
    else:
        raise AgentOpsError(f"gates[{index}] must be a command string or object")

    argv = parse_gate_command(command)
    return GateSpec(
        name=name,
        command=command,
        argv=argv,
        env=env,
        timeout_seconds=timeout,
        max_output_chars=max_output,
    )


def load_raw_packet(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AgentOpsError("YAML packets require PyYAML; use JSON instead") from exc
        data = yaml.safe_load(text)
    else:
        raise AgentOpsError("work packet must end in .json, .yaml, or .yml")
    if not isinstance(data, dict):
        raise AgentOpsError("work packet root must be an object")
    return data


def parse_work_packet(data: dict[str, Any]) -> WorkPacket:
    packet_id = safe_packet_id(data.get("id"))
    base_ref = require_string(data, "base_ref")
    branch = require_string(data, "branch")
    worktree_raw = require_string(data, "worktree")
    intent = require_string(data, "intent")
    allowed_files = require_pattern_list(data, "allowed_files", non_empty=True)
    forbidden_files = require_pattern_list(data, "forbidden_files", non_empty=False)

    gates_raw = data.get("gates")
    if not isinstance(gates_raw, list):
        raise AgentOpsError("gates is required and must be a list")
    gates = [parse_gate(raw_gate, index) for index, raw_gate in enumerate(gates_raw)]

    commit_raw = data.get("commit")
    if not isinstance(commit_raw, dict):
        raise AgentOpsError("commit is required and must be an object")
    commit = CommitPolicy(
        allowed=require_bool(commit_raw, "allowed"),
        message=require_string(commit_raw, "message"),
    )

    approval_raw = data.get("approval")
    if not isinstance(approval_raw, dict):
        raise AgentOpsError("approval is required and must be an object")
    approval = ApprovalPolicy(
        before_commit=require_bool(approval_raw, "before_commit"),
        before_merge=require_bool(approval_raw, "before_merge"),
    )

    return WorkPacket(
        id=packet_id,
        base_ref=base_ref,
        branch=branch,
        worktree=Path(worktree_raw).expanduser().resolve(),
        intent=intent,
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        gates=gates,
        commit=commit,
        approval=approval,
    )


def load_work_packet(path: Path) -> WorkPacket:
    return parse_work_packet(load_raw_packet(path))


def git_lines(repo_root: Path, args: list[str]) -> list[str]:
    output = run_git(args, cwd=repo_root).stdout
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def git_status(repo_root: Path) -> str:
    return run_git(["status", "--short"], cwd=repo_root).stdout


def inspect_scope(repo_root: Path, packet: WorkPacket) -> ScopeState:
    tracked = sorted(set(git_lines(repo_root, ["diff", "--name-only"])))
    staged = sorted(set(git_lines(repo_root, ["diff", "--name-only", "--cached"])))
    untracked = sorted(set(git_lines(repo_root, ["ls-files", "--others", "--exclude-standard"])))
    changed = sorted(set(tracked + staged + untracked))
    violations: list[dict[str, Any]] = []
    for path in changed:
        forbidden = matching_patterns(path, packet.forbidden_files)
        allowed = matching_patterns(path, packet.allowed_files)
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
    return ScopeState(
        tracked_changed_files=tracked,
        staged_files=staged,
        untracked_files=untracked,
        changed_files=changed,
        violations=violations,
    )


def resolve_base_ref(source_root: Path, base_ref: str) -> str:
    return run_git(["rev-parse", base_ref], cwd=source_root).stdout.strip()


def branch_for(repo_root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=repo_root).stdout.strip()


def head_for(repo_root: Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=repo_root).stdout.strip()


def verify_base_is_ancestor(repo_root: Path, base_hash: str) -> None:
    result = run_git(["merge-base", "--is-ancestor", base_hash, "HEAD"], cwd=repo_root, check=False)
    if result.returncode != 0:
        raise AgentOpsError(f"target worktree HEAD does not contain base_ref {base_hash}")


def prepare_worktree(source_root: Path, packet: WorkPacket) -> Path:
    base_hash = resolve_base_ref(source_root, packet.base_ref)
    if packet.worktree.exists():
        target_root = repo_root_from(packet.worktree)
        if target_root != packet.worktree:
            raise AgentOpsError(f"worktree path is not a repo root: {packet.worktree}")
        actual_branch = branch_for(target_root)
        if actual_branch != packet.branch:
            raise AgentOpsError(f"worktree branch expected {packet.branch}, got {actual_branch}")
        verify_base_is_ancestor(target_root, base_hash)
        return target_root

    packet.worktree.parent.mkdir(parents=True, exist_ok=True)
    result = run_git(
        ["worktree", "add", "-b", packet.branch, str(packet.worktree), packet.base_ref],
        cwd=source_root,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"could not create worktree {packet.worktree}: {detail}")
    target_root = repo_root_from(packet.worktree)
    if branch_for(target_root) != packet.branch:
        raise AgentOpsError(f"created worktree is not on expected branch {packet.branch}")
    return target_root


def trim_output(output: str, max_chars: int) -> str:
    if len(output) <= max_chars:
        return output
    omitted = len(output) - max_chars
    return f"{output[:max_chars]}\n...[truncated {omitted} chars]"


def run_gate(repo_root: Path, gate: GateSpec) -> dict[str, Any]:
    started = time.monotonic()
    env = os.environ.copy()
    env.update(gate.env)
    try:
        result = run_command(
            gate.argv,
            cwd=repo_root,
            env=env,
            timeout_seconds=gate.timeout_seconds,
        )
        exit_code = result.returncode
        combined_output = result.stdout
        if result.stderr:
            combined_output += result.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        timed_out = True
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        combined_output = f"{stdout}{stderr}\ncommand timed out after {gate.timeout_seconds}s"

    return {
        "name": gate.name,
        "command": gate.command,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output": trim_output(combined_output, gate.max_output_chars),
    }


def timestamp_slug(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.strftime("%Y%m%dT%H%M%S%fZ")


def report_paths(repo_root: Path, job_id: str, timestamp: str) -> tuple[Path, Path]:
    report_dir = repo_root / REPORT_ROOT / job_id / timestamp
    return report_dir / "report.json", report_dir / "report.md"


def scope_to_dict(scope: ScopeState) -> dict[str, Any]:
    return {
        "tracked_changed_files": scope.tracked_changed_files,
        "staged_files": scope.staged_files,
        "untracked_files": scope.untracked_files,
        "changed_files": scope.changed_files,
        "violations": scope.violations,
        "passed": scope.passed,
    }


def write_report(repo_root: Path, report: dict[str, Any], timestamp: str) -> tuple[Path, Path]:
    json_path, md_path = report_paths(repo_root, report["job_id"], timestamp)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, md_path


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        f"# AgentOps Report: {report['job_id']}",
        "",
        f"- Status: {report['status']}",
        f"- Base ref: `{report['base_ref']}`",
        f"- Branch: `{report['branch']}`",
        f"- Worktree: `{report['worktree']}`",
        f"- Commit hash: `{report.get('commit_hash') or ''}`",
        f"- Approval before commit: `{report['approval']['before_commit']}`",
        f"- Approval before merge: `{report['approval']['before_merge']}`",
        "",
        "## Intent",
        "",
        report["intent"],
        "",
        "## Scope",
        "",
        f"- Scope passed: `{report['scope']['passed']}`",
        f"- Changed files: `{len(report['scope']['changed_files'])}`",
        f"- Violations: `{len(report['scope']['violations'])}`",
        "",
        "## Gates",
        "",
        "| Gate | Exit | Result |",
        "|---|---:|---|",
    ]
    for gate in report["gates"]:
        result = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"| {gate['name']} | {gate['exit_code']} | {result} |")
    lines.extend(
        [
            "",
            "## Final Git Status",
            "",
            "```",
            report.get("final_git_status", "").rstrip(),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def should_commit(report: dict[str, Any], packet: WorkPacket, final_scope: ScopeState) -> tuple[bool, str]:
    if not packet.commit.allowed:
        return False, "commit.allowed is false"
    if packet.approval.before_commit:
        return False, "human approval required before commit"
    if not all(gate["passed"] for gate in report["gates"]):
        return False, "one or more gates failed"
    if not final_scope.passed:
        return False, "scope gate failed"
    if not final_scope.changed_files:
        return False, "no changes to commit"
    return True, "commit permitted"


def create_commit(repo_root: Path, files: list[str], message: str) -> str:
    run_git(["add", "--", *files], cwd=repo_root)
    result = run_git(["commit", "-m", message], cwd=repo_root, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AgentOpsError(f"git commit failed: {detail}")
    return head_for(repo_root)


def base_report(packet: WorkPacket, target_root: Path, *, dry_run: bool) -> dict[str, Any]:
    return {
        "job_id": packet.id,
        "base_ref": packet.base_ref,
        "branch": packet.branch,
        "worktree": str(packet.worktree),
        "intent": packet.intent,
        "allowed_files": packet.allowed_files,
        "forbidden_files": packet.forbidden_files,
        "approval": {
            "before_commit": packet.approval.before_commit,
            "before_merge": packet.approval.before_merge,
        },
        "dry_run": dry_run,
        "target_head": head_for(target_root) if target_root.exists() else None,
        "scope": {
            "tracked_changed_files": [],
            "staged_files": [],
            "untracked_files": [],
            "changed_files": [],
            "violations": [],
            "passed": True,
        },
        "gates": [],
        "commit_hash": None,
        "commit_decision": "not evaluated",
        "final_git_status": "",
        "status": "pending",
    }


def execute_packet(
    packet_path: Path,
    *,
    source_root: Path | None = None,
    dry_run: bool = False,
    allow_existing_changes: bool = False,
) -> tuple[int, dict[str, Any] | None]:
    source = source_root.resolve() if source_root else require_repo_root(Path.cwd())
    packet = load_work_packet(packet_path)

    if dry_run:
        summary = {
            "job_id": packet.id,
            "base_ref": packet.base_ref,
            "branch": packet.branch,
            "worktree": str(packet.worktree),
            "intent": packet.intent,
            "allowed_files": packet.allowed_files,
            "forbidden_files": packet.forbidden_files,
            "gates": [gate.command for gate in packet.gates],
            "commit_allowed": packet.commit.allowed,
            "approval": {
                "before_commit": packet.approval.before_commit,
                "before_merge": packet.approval.before_merge,
            },
            "dry_run": True,
            "would_create_worktree": not packet.worktree.exists(),
            "would_run_gates": False,
            "would_commit": False,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0, None

    target_root = prepare_worktree(source, packet)
    timestamp = timestamp_slug()
    report = base_report(packet, target_root, dry_run=False)
    initial_scope = inspect_scope(target_root, packet)
    if initial_scope.changed_files and not allow_existing_changes:
        report["scope"] = scope_to_dict(initial_scope)
        report["final_git_status"] = git_status(target_root)
        report["status"] = "failed"
        report["commit_decision"] = "target worktree dirty before gates; rerun with --allow-existing-changes after human review"
        write_report(target_root, report, timestamp)
        return 1, report

    for gate in packet.gates:
        gate_result = run_gate(target_root, gate)
        report["gates"].append(gate_result)

    final_scope = inspect_scope(target_root, packet)
    report["scope"] = scope_to_dict(final_scope)
    commit_allowed, commit_reason = should_commit(report, packet, final_scope)
    report["commit_decision"] = commit_reason
    if commit_allowed:
        report["commit_hash"] = create_commit(target_root, final_scope.changed_files, packet.commit.message)
        final_scope = inspect_scope(target_root, packet)
        report["scope"] = scope_to_dict(final_scope)

    report["final_git_status"] = git_status(target_root)
    gates_passed = all(gate["passed"] for gate in report["gates"])
    report["status"] = "passed" if gates_passed and final_scope.passed else "failed"
    write_report(target_root, report, timestamp)
    return (0 if report["status"] == "passed" else 1), report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a governed AgentOps work packet")
    parser.add_argument("--packet", required=True, type=Path, help="Path to JSON/YAML work packet")
    parser.add_argument(
        "--dry-run",
        "--inspect",
        action="store_true",
        help="Validate and print intended actions without creating a worktree, running gates, or committing",
    )
    parser.add_argument(
        "--allow-existing-changes",
        action="store_true",
        help="Allow an already-dirty target worktree after explicit human review; scope still fails closed",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code, report = execute_packet(
            args.packet,
            dry_run=args.dry_run,
            allow_existing_changes=args.allow_existing_changes,
        )
    except AgentOpsError as exc:
        print(f"AgentOps error: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"AgentOps error: invalid JSON packet: {exc}", file=sys.stderr)
        return 2

    if report is not None:
        print(f"Status: {report['status']}")
        print(f"Commit: {report.get('commit_hash') or ''}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
