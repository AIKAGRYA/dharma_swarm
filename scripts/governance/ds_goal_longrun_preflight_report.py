#!/usr/bin/env python3
"""Report unsafe unpinned ds-goal workflow commands in repo-owned surfaces."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SCAN_PATHS = (
    Path("docs/agent_tasks"),
    Path("scripts"),
    Path("Makefile"),
)

COMMAND_RE = re.compile(
    r"^\s*(?:[-*]\s*)?`?"
    r"(?P<command>"
    r"(?:(?:env\s+)?DHARMA_SWARM_REPO=(?P<pin>[^\s`]+)\s+)?"
    r"(?P<wrapper>"
    r"ds-goal|"
    r"/Users/dhyana/\.dharma/bin/ds-goal|"
    r"\$HOME/\.dharma/bin/ds-goal|"
    r"~/\.dharma/bin/ds-goal"
    r")\s+"
    r"(?P<verb>init|run|status)\b"
    r"[^`]*"
    r")"
)

SCAN_SUFFIXES = {".md", ".py", ".sh", ".bash", ".zsh"}


@dataclass(frozen=True)
class DsGoalCommandEntry:
    file: str
    line: int
    classification: str
    verb: str
    command: str
    reason: str


@dataclass(frozen=True)
class DsGoalPreventionReceiptEntry:
    file: str
    line: int
    mission_id: str
    task_id: str
    created_at: str
    record_hash: str
    preflight_status: str
    longrun_start_allowed: bool
    default_target_repo: str
    repo_pin_source: str
    runtime_db_evidence: str
    kernel_store_evidence: str
    classification: str
    reason: str


def _iter_scan_files(repo_root: Path, scan_paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for scan_path in scan_paths:
        path = scan_path if scan_path.is_absolute() else repo_root / scan_path
        if not path.exists():
            continue
        if path.is_file():
            files.append(path)
            continue
        for root, dirnames, filenames in os.walk(path):
            dirnames[:] = [
                name
                for name in dirnames
                if name not in {"__pycache__", ".git", "node_modules", ".venv"}
            ]
            for filename in filenames:
                candidate = Path(root) / filename
                if candidate.name == "Makefile" or candidate.suffix in SCAN_SUFFIXES:
                    files.append(candidate)
    return sorted(files)


def _iter_receipt_files(receipt_roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for receipt_root in receipt_roots:
        root = receipt_root.expanduser()
        if not root.exists():
            continue
        if root.is_file():
            if root.name == "receipts.jsonl":
                files.append(root)
            continue
        files.extend(sorted(root.rglob("receipts.jsonl")))
    return sorted(files)


def _relative_path(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _safe_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _classify_command(command: str, pin: str | None) -> tuple[str, str]:
    if pin:
        return (
            "pinned",
            "explicit DHARMA_SWARM_REPO pin present before ds-goal command",
        )
    return (
        "unsafe_unpinned",
        "ds-goal command can resolve through installed-wrapper default target",
    )


def _path_has_files(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file():
        return True
    try:
        return any(candidate.is_file() for candidate in path.rglob("*"))
    except OSError:
        return True


def _default_state_root() -> Path:
    return Path.home() / ".dharma" / "ds_goals"


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return str(left.expanduser()) == str(right.expanduser())


def _side_effect_evidence(receipt_file: Path) -> tuple[str, str]:
    mission_path = receipt_file.parent / "mission.json"
    mission: dict[str, Any] = {}
    if mission_path.exists():
        try:
            mission = _safe_json(mission_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            mission = {}
    state_root = Path(str(mission.get("state_root") or receipt_file.parent.parent)).expanduser()
    kernel_store_raw = str(mission.get("kernel_store") or "").strip()
    kernel_store = Path(kernel_store_raw).expanduser() if kernel_store_raw else None
    if _same_path(state_root, _default_state_root()):
        runtime_db_evidence = "default_state_global_runtime_db_not_inspected"
    elif (state_root / ".runtime" / "runtime.db").exists():
        runtime_db_evidence = "runtime_db_exists_under_state_root"
    else:
        runtime_db_evidence = "runtime_db_absent_under_state_root"
    if kernel_store is None:
        kernel_store_evidence = "kernel_store_unknown"
    elif not kernel_store.exists():
        kernel_store_evidence = "kernel_store_absent"
    elif _path_has_files(kernel_store):
        kernel_store_evidence = "kernel_store_has_files"
    else:
        kernel_store_evidence = "kernel_store_empty"
    return runtime_db_evidence, kernel_store_evidence


def scan_ds_goal_commands(
    *,
    repo_root: Path = REPO_ROOT,
    scan_paths: list[Path] | None = None,
) -> list[DsGoalCommandEntry]:
    paths = scan_paths if scan_paths is not None else list(DEFAULT_SCAN_PATHS)
    entries: list[DsGoalCommandEntry] = []
    for path in _iter_scan_files(repo_root, paths):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = _relative_path(repo_root, path)
        for line_number, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            match = COMMAND_RE.search(line)
            if not match:
                continue
            command = match.group("command").strip()
            verb = match.group("verb").strip()
            classification, reason = _classify_command(command, match.group("pin"))
            entries.append(
                DsGoalCommandEntry(
                    file=rel,
                    line=line_number,
                    classification=classification,
                    verb=verb,
                    command=command,
                    reason=reason,
                )
            )
    return entries


def scan_preflight_prevention_receipts(
    *,
    repo_root: Path = REPO_ROOT,
    receipt_roots: list[Path] | None = None,
) -> list[DsGoalPreventionReceiptEntry]:
    roots = receipt_roots or []
    entries: list[DsGoalPreventionReceiptEntry] = []
    for receipt_file in _iter_receipt_files(roots):
        try:
            lines = receipt_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = _relative_path(repo_root, receipt_file)
        runtime_db_evidence, kernel_store_evidence = _side_effect_evidence(receipt_file)
        for line_number, line in enumerate(lines, start=1):
            row = _safe_json(line)
            if row.get("event") != "ds_goal_run" or row.get("status") != "preflight_blocked":
                continue
            preflight = row.get("ds_goal_longrun_preflight")
            if not isinstance(preflight, dict):
                preflight = {}
            longrun_start_allowed = preflight.get("longrun_start_allowed") is True
            preflight_status = str(preflight.get("status") or "")
            if longrun_start_allowed:
                classification = "conflicting_prevention_receipt"
                reason = "receipt says preflight_blocked but longrun_start_allowed=true"
            elif preflight_status.startswith("blocked_"):
                classification = "valid_preflight_block"
                reason = "unsafe longrun start blocked before runtime dispatch"
            else:
                classification = "weak_prevention_receipt"
                reason = "preflight_blocked receipt lacks blocked_* preflight status"
            entries.append(
                DsGoalPreventionReceiptEntry(
                    file=rel,
                    line=line_number,
                    mission_id=str(row.get("mission_id") or ""),
                    task_id=str(row.get("task_id") or ""),
                    created_at=str(row.get("created_at") or ""),
                    record_hash=str(row.get("record_hash") or ""),
                    preflight_status=preflight_status,
                    longrun_start_allowed=longrun_start_allowed,
                    default_target_repo=str(preflight.get("default_target_repo") or ""),
                    repo_pin_source=str(preflight.get("repo_pin_source") or ""),
                    runtime_db_evidence=runtime_db_evidence,
                    kernel_store_evidence=kernel_store_evidence,
                    classification=classification,
                    reason=reason,
                )
            )
    return entries


def build_report(
    entries: list[DsGoalCommandEntry],
    prevention_receipts: list[DsGoalPreventionReceiptEntry] | None = None,
) -> dict[str, Any]:
    unsafe = [
        entry for entry in entries if entry.classification == "unsafe_unpinned"
    ]
    pinned = [entry for entry in entries if entry.classification == "pinned"]
    prevention_receipts = prevention_receipts or []
    valid_prevention_receipts = [
        entry
        for entry in prevention_receipts
        if entry.classification == "valid_preflight_block"
    ]
    conflicting_prevention_receipts = [
        entry
        for entry in prevention_receipts
        if entry.classification == "conflicting_prevention_receipt"
    ]
    return {
        "schema_version": "dharma.ds_goal_longrun_preflight_report.v1",
        "scan_paths": [str(path) for path in DEFAULT_SCAN_PATHS],
        "total_command_shaped_ds_goal_entries": len(entries),
        "pinned": len(pinned),
        "unsafe_unpinned": len(unsafe),
        "preflight_prevention_receipts": len(prevention_receipts),
        "valid_preflight_blocks": len(valid_prevention_receipts),
        "conflicting_prevention_receipts": len(conflicting_prevention_receipts),
        "strict_passed": not unsafe and not conflicting_prevention_receipts,
        "entries": [asdict(entry) for entry in entries],
        "unsafe_entries": [asdict(entry) for entry in unsafe],
        "prevention_receipts": [asdict(entry) for entry in prevention_receipts],
        "valid_prevention_receipts": [
            asdict(entry) for entry in valid_prevention_receipts
        ],
        "conflicting_prevention_entries": [
            asdict(entry) for entry in conflicting_prevention_receipts
        ],
        "required_mitigation": (
            "prefix repo-owned ds-goal init/run/status commands with "
            "DHARMA_SWARM_REPO=<audited_checkout> or run "
            "scripts/runtime/ds_goal_longrun_preflight.py before launch"
        ),
    }


def _print_text(report: dict[str, Any]) -> None:
    print("=" * 72)
    print("DS-GOAL LONGRUN PREFLIGHT REPORT")
    print("=" * 72)
    print()
    print(
        "  "
        f"Command-shaped ds-goal entries: {report['total_command_shaped_ds_goal_entries']}"
    )
    print(f"  Pinned commands:                {report['pinned']}")
    print(f"  Unsafe unpinned commands:       {report['unsafe_unpinned']}")
    print(
        "  "
        f"Preflight prevention receipts: {report['preflight_prevention_receipts']}"
    )
    print(f"  Valid preflight blocks:         {report['valid_preflight_blocks']}")
    print()
    entries = report.get("entries") if isinstance(report.get("entries"), list) else []
    if entries:
        print(f"{'Class':<18} {'File':<58} {'Line':>5}  Command")
        print("-" * 120)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            print(
                f"{entry.get('classification', ''):<18} "
                f"{entry.get('file', ''):<58} "
                f"{entry.get('line', ''):>5}  "
                f"{entry.get('command', '')}"
            )
        print()
    prevention_entries = (
        report.get("prevention_receipts")
        if isinstance(report.get("prevention_receipts"), list)
        else []
    )
    if prevention_entries:
        print("Preflight prevention receipts")
        print(f"{'Class':<28} {'File':<58} {'Line':>5}  Mission / task")
        print("-" * 132)
        for entry in prevention_entries:
            if not isinstance(entry, dict):
                continue
            mission = entry.get("mission_id", "")
            task = entry.get("task_id", "")
            print(
                f"{entry.get('classification', ''):<28} "
                f"{entry.get('file', ''):<58} "
                f"{entry.get('line', ''):>5}  "
                f"{mission} / {task}"
            )
            print(
                " " * 96
                + f"preflight={entry.get('preflight_status', '')}; "
                + f"runtime_db={entry.get('runtime_db_evidence', '')}; "
                + f"kernel={entry.get('kernel_store_evidence', '')}"
            )
        print()
    if report.get("strict_passed"):
        print("PASS: all command-shaped ds-goal longrun workflow commands are pinned.")
    else:
        print("FAIL: unsafe unpinned ds-goal workflow commands remain.")
        print(f"Mitigation: {report['required_mitigation']}")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Detect repo-owned ds-goal init/run/status commands without an audited-checkout pin.",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Additional or replacement scan path. May be repeated.",
    )
    parser.add_argument(
        "--prevention-receipt-root",
        action="append",
        default=[],
        help=(
            "Optional ds-goal state root or receipts.jsonl path to scan for "
            "preflight_blocked prevention receipts. May be repeated."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scan_paths = [Path(item) for item in args.path] if args.path else None
    prevention_roots = [Path(item) for item in args.prevention_receipt_root]
    report = build_report(
        scan_ds_goal_commands(scan_paths=scan_paths),
        prevention_receipts=scan_preflight_prevention_receipts(
            receipt_roots=prevention_roots
        ),
    )
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        _print_text(report)
    if args.strict and not report["strict_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
