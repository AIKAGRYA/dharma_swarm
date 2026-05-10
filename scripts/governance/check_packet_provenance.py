#!/usr/bin/env python3
"""Check commit provenance against governed prompt-lane packets.

This is the first enforcement layer for prompt governance. It is designed for a
`commit-msg` hook, but can also run in CI or tests with explicit file lists.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKET_DIR = REPO_ROOT / "reports/governance/prompt_lane_runs"
DEFAULT_WITNESS_PATH = Path.home() / ".dharma/witness/packet_provenance.jsonl"

JsonDict = dict[str, Any]

HOT_PATH_PATTERNS = (
    "CLAUDE.md",
    ".pre-commit-config.yaml",
    ".github/workflows/**",
    ".semgrep/**",
    "scripts/governance/**",
    "docs/governance/**",
    "dharma_swarm/guardian_crew.py",
    "dharma_swarm/swarm.py",
    "dharma_swarm/agent_runner.py",
    "dharma_swarm/telos_gates.py",
    "dharma_swarm/dharma_kernel.py",
)

EXEMPT_PATH_PATTERNS = (
    "reports/**",
    "quality-reports/**",
    "tests/**",
    "docs/**",
    "*.md",
)

SOURCE_PATH_PATTERNS = (
    "dharma_swarm/*.py",
    "dharma_swarm/**/*.py",
    "dashboard/src/**",
    "api/**",
)

RISKY_COMMIT_TERMS = (
    "cleanup",
    "consolidate",
    "dead code",
    "delete",
    "fallback",
    "refactor",
    "remove",
    "rewrite",
    "slop",
    "type",
    "untangle",
)

RISKY_DIFF_PATTERNS = (
    re.compile(r"^-+\s*(async\s+)?def\s+\w+"),
    re.compile(r"^-+\s*class\s+\w+"),
    re.compile(r"^-+\s*(export\s+)?(async\s+)?function\s+\w+"),
    re.compile(r"^-+\s*(export\s+)?(interface|type)\s+\w+"),
    re.compile(r"^-+\s*except\s+.*:\s*$"),
    re.compile(r"^-+\s*pass\s*$"),
)

PACKET_ID_RE = re.compile(r"(?im)^Packet-Id:\s*([0-9a-f]{12,64})\s*$")
BYPASS_RE = re.compile(r"(?im)^Packet-Bypass-Reason:\s*(.{15,})\s*$")


@dataclass(frozen=True)
class FileRequirement:
    path: str
    required: bool
    reason: str
    bypass_allowed: bool = False


@dataclass(frozen=True)
class PacketRecord:
    packet_id: str
    path: Path
    target: str
    lane_id: str


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def staged_files() -> list[str]:
    text = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMRD"])
    return sorted(path for path in text.splitlines() if path.strip())


def staged_name_status() -> dict[str, str]:
    text = run_git(["diff", "--cached", "--name-status", "--diff-filter=ACMRD"])
    statuses: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            statuses[parts[-1]] = parts[0]
    return statuses


def staged_diff() -> str:
    return run_git(["diff", "--cached", "--unified=0"])


def matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/**") and path.startswith(pattern[:-3] + "/"):
            return True
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def is_hot_path(path: str) -> bool:
    return matches_any(path, HOT_PATH_PATTERNS)


def is_source_path(path: str) -> bool:
    return matches_any(path, SOURCE_PATH_PATTERNS)


def is_exempt_path(path: str) -> bool:
    return matches_any(path, EXEMPT_PATH_PATTERNS) and not is_hot_path(path)


def commit_text(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def commit_mentions_risky_work(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in RISKY_COMMIT_TERMS)


def diff_touches_risky_source(path: str, name_status: str, diff_text: str) -> bool:
    if not is_source_path(path):
        return False
    if name_status.startswith("D"):
        return True
    file_header = f"+++ b/{path}"
    if file_header not in diff_text and f"--- a/{path}" not in diff_text:
        return False
    removal_count = 0
    in_file = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            in_file = f" b/{path}" in line or f" a/{path}" in line
            continue
        if not in_file:
            continue
        if line.startswith("-") and not line.startswith("---"):
            removal_count += 1
            if any(pattern.search(line) for pattern in RISKY_DIFF_PATTERNS):
                return True
    return removal_count >= 20


def classify_files(
    files: list[str],
    *,
    message_text: str = "",
    name_status: dict[str, str] | None = None,
    diff_text: str = "",
) -> list[FileRequirement]:
    name_status = name_status or {}
    risky_message = commit_mentions_risky_work(message_text)
    requirements: list[FileRequirement] = []
    for path in sorted(files):
        if is_hot_path(path):
            requirements.append(
                FileRequirement(path=path, required=True, reason="hot_or_governance_path")
            )
            continue
        if is_exempt_path(path):
            requirements.append(FileRequirement(path=path, required=False, reason="exempt_path"))
            continue
        if is_source_path(path) and (
            risky_message or diff_touches_risky_source(path, name_status.get(path, ""), diff_text)
        ):
            requirements.append(
                FileRequirement(
                    path=path,
                    required=True,
                    reason="risky_source_cleanup_or_refactor",
                    bypass_allowed=True,
                )
            )
            continue
        requirements.append(FileRequirement(path=path, required=False, reason="not_packet_required"))
    return requirements


def packet_ids_from_message(text: str) -> list[str]:
    return PACKET_ID_RE.findall(text)


def has_bypass_reason(text: str) -> bool:
    return bool(BYPASS_RE.search(text))


def load_packets(packet_dir: Path) -> dict[str, PacketRecord]:
    packets: dict[str, PacketRecord] = {}
    if not packet_dir.exists():
        return packets
    for path in sorted(packet_dir.glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        packet_id = str(row.get("prompt_hash") or "")
        target = str(dict(row.get("target") or {}).get("path") or "")
        lane_id = str(dict(row.get("lane") or {}).get("lane_id") or "")
        if packet_id and target:
            packets[packet_id] = PacketRecord(
                packet_id=packet_id,
                path=path,
                target=target,
                lane_id=lane_id,
            )
    return packets


def target_covers_path(target: str, path: str) -> bool:
    normalized_target = target.rstrip("/")
    if normalized_target in {"", "."}:
        return True
    if path == normalized_target:
        return True
    return path.startswith(f"{normalized_target}/")


def uncovered_required_files(
    requirements: list[FileRequirement],
    packet_records: list[PacketRecord],
    *,
    bypass_reason: bool,
) -> list[FileRequirement]:
    uncovered: list[FileRequirement] = []
    for requirement in requirements:
        if not requirement.required:
            continue
        if requirement.bypass_allowed and bypass_reason:
            continue
        if any(target_covers_path(record.target, requirement.path) for record in packet_records):
            continue
        uncovered.append(requirement)
    return uncovered


def check_packet_provenance(
    *,
    files: list[str],
    message_text: str,
    packet_dir: Path = DEFAULT_PACKET_DIR,
    name_status: dict[str, str] | None = None,
    diff_text: str = "",
) -> JsonDict:
    requirements = classify_files(
        files,
        message_text=message_text,
        name_status=name_status,
        diff_text=diff_text,
    )
    required = [requirement for requirement in requirements if requirement.required]
    packet_ids = packet_ids_from_message(message_text)
    packets_by_id = load_packets(packet_dir)
    found_packets = [packets_by_id[packet_id] for packet_id in packet_ids if packet_id in packets_by_id]
    missing_packet_ids = [packet_id for packet_id in packet_ids if packet_id not in packets_by_id]
    bypass_reason = has_bypass_reason(message_text)
    uncovered = uncovered_required_files(
        requirements,
        found_packets,
        bypass_reason=bypass_reason,
    )
    valid = not uncovered and not missing_packet_ids
    message = result_message(
        valid=valid,
        required_count=len(required),
        uncovered=uncovered,
        missing_packet_ids=missing_packet_ids,
    )
    return {
        "valid": valid,
        "message": message,
        "files": files,
        "requirements": [requirement.__dict__ for requirement in requirements],
        "required_count": len(required),
        "packet_ids": packet_ids,
        "found_packets": [record.__dict__ | {"path": str(record.path)} for record in found_packets],
        "missing_packet_ids": missing_packet_ids,
        "bypass_reason": bypass_reason,
        "uncovered_required_files": [requirement.__dict__ for requirement in uncovered],
    }


def result_message(
    *,
    valid: bool,
    required_count: int,
    uncovered: list[FileRequirement],
    missing_packet_ids: list[str],
) -> str:
    if valid:
        if required_count:
            return "packet provenance ok"
        return "packet provenance not required for this change"
    parts: list[str] = []
    if uncovered:
        parts.append(f"{len(uncovered)} required file(s) lack packet coverage")
    if missing_packet_ids:
        parts.append(f"{len(missing_packet_ids)} Packet-Id artifact(s) missing")
    return "; ".join(parts) or "packet provenance missing or incomplete"


def render_text(result: JsonDict, *, warn_only: bool) -> str:
    if result["valid"]:
        return str(result["message"])

    prefix = "WARNING" if warn_only else "ERROR"
    lines = [f"{prefix}: packet provenance missing or incomplete"]
    for item in result["uncovered_required_files"]:
        lines.append(f"- {item['path']}: {item['reason']}")
    for packet_id in result["missing_packet_ids"]:
        lines.append(f"- missing Packet-Id artifact: {packet_id}")
    lines.extend(
        [
            "",
            "Add a commit-message line:",
            "Packet-Id: <prompt_hash>",
            "",
            "Create one with:",
            "python scripts/governance/prompt_lane_run.py --lane <lane_id> --target <path>",
            "",
            "For non-hot risky source work only, an explicit override is accepted:",
            "Packet-Bypass-Reason: <specific reason, 15+ chars>",
        ]
    )
    return "\n".join(lines)


def append_witness(
    result: JsonDict,
    *,
    witness_path: Path = DEFAULT_WITNESS_PATH,
    source: str = "local",
) -> None:
    """Append one provenance check row for hourly calibration dashboards."""

    row = {
        **result,
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "repo_root": str(REPO_ROOT),
    }
    witness_path = witness_path.expanduser()
    witness_path.parent.mkdir(parents=True, exist_ok=True)
    with witness_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_file", nargs="?", type=Path)
    parser.add_argument("--commit-msg-file", type=Path, default=None)
    parser.add_argument("--packet-dir", type=Path, default=DEFAULT_PACKET_DIR)
    parser.add_argument("--files", nargs="*", default=None, help="Explicit file list for tests/CI")
    parser.add_argument("--warn-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--witness-jsonl",
        type=Path,
        default=DEFAULT_WITNESS_PATH,
        help="Append structured local evidence for calibration dashboards",
    )
    parser.add_argument("--no-witness", action="store_true")
    parser.add_argument("--source", default="local", help="Evidence source label")
    args = parser.parse_args()

    message_path = args.commit_msg_file or args.message_file
    message = commit_text(message_path)
    explicit_files = [str(path) for path in args.files] if args.files is not None else None
    files = explicit_files if explicit_files is not None else staged_files()
    name_status = {} if explicit_files is not None else staged_name_status()
    diff = "" if explicit_files is not None else staged_diff()

    packet_dir = args.packet_dir if args.packet_dir.is_absolute() else REPO_ROOT / args.packet_dir
    result = check_packet_provenance(
        files=files,
        message_text=message,
        packet_dir=packet_dir,
        name_status=name_status,
        diff_text=diff,
    )
    if not args.no_witness:
        try:
            append_witness(result, witness_path=args.witness_jsonl, source=args.source)
        except OSError:
            # Provenance evidence is diagnostic; packet validity must not depend
            # on the local filesystem accepting witness writes.
            pass
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_text(result, warn_only=args.warn_only))
    return 0 if result["valid"] or args.warn_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
