#!/usr/bin/env python3
"""Tiny operator console for steering opus_composer and codex_composer.

This is intentionally a filesystem-bus wrapper, not a new coordination system.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import fill


BUS_ROOT = Path(os.environ.get("DHARMA_A2A_BUS_ROOT", Path.home() / ".dharma" / "a2a_bus"))
CONVERGENCE_DIR = BUS_ROOT / "collab" / "convergence"
INBOXES = {
    "opus_composer": BUS_ROOT / "inboxes" / "opus_composer",
    "codex_composer": BUS_ROOT / "inboxes" / "codex_composer",
}
LOG_DIR = BUS_ROOT / "operator"
LOG_FILE = LOG_DIR / "composer_console_log.jsonl"
LATEST_FILE = LOG_DIR / "latest_composer_steer.md"
BACKGROUND_DIR = LOG_DIR / "composer_background_loop"
BACKGROUND_HEARTBEAT = BACKGROUND_DIR / "heartbeat.json"
BACKGROUND_RECEIPTS = BACKGROUND_DIR / "receipts.jsonl"

ARTIFACTS = {
    "opus view": CONVERGENCE_DIR / "opus_composer_view_round1.md",
    "codex view": CONVERGENCE_DIR / "codex_composer_view_round1.md",
    "codex ledger": CONVERGENCE_DIR / "codex_disagreement_ledger_round1.md",
    "shared picture": CONVERGENCE_DIR / "SHARED_PICTURE.md",
}

MISSION_PATTERNS = [
    "MISSIONS.md",
    "DAILY_HIGHEST_LEVERAGE_MISSION_*.md",
    "OPERATOR_LEASE_*.md",
    "bridge_gate_verdict_*.md",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def short_time(path: Path) -> str:
    if not path.exists():
        return "missing"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%m-%d %H:%M")


def ensure_dirs() -> None:
    CONVERGENCE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for inbox in INBOXES.values():
        inbox.mkdir(parents=True, exist_ok=True)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def process_count(pattern: str) -> int | None:
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode == 3 or "Cannot get process list" in result.stderr:
        return None
    if result.returncode != 0:
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def process_count_label(pattern: str) -> str:
    count = process_count(pattern)
    if count is None:
        return "n/a"
    return str(count)


def newest(paths: list[Path], count: int = 5) -> list[Path]:
    existing = [path for path in paths if path.exists()]
    existing.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return existing[:count]


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def short_json_line(payload: dict[str, object]) -> str:
    if not payload:
        return "missing"
    status = str(payload.get("status", "unknown"))
    updated = str(payload.get("updated_at", "unknown"))
    cycle = payload.get("cycle", "?")
    return f"{status} cycle={cycle} updated={updated}"


def mission_files() -> list[Path]:
    files: list[Path] = []
    for pattern in MISSION_PATTERNS:
        files.extend(CONVERGENCE_DIR.glob(pattern))
    return newest([path for path in files if path.is_file()], 8)


def print_status() -> None:
    print("\n== Composer Console ==")
    print(f"bus: {BUS_ROOT}")
    print(f"codex process refs: {process_count_label('codex_composer')}")
    print(f"opus process refs:  {process_count_label('opus_composer')}")
    print(f"background loop refs: {process_count_label('composer_background_loop')}")
    print()
    print("round artifacts")
    for name, path in ARTIFACTS.items():
        mark = "OK" if path.exists() else "--"
        print(f"  {mark:2} {name:15} {short_time(path)}")

    print("\nmission / gate files")
    missions = mission_files()
    if not missions:
        print("  none yet")
    for path in missions:
        print(f"  {short_time(path)}  {path.name}")

    print("\nbackground loop")
    heartbeat = read_json(BACKGROUND_HEARTBEAT)
    print(f"  heartbeat: {short_json_line(heartbeat)}")
    if BACKGROUND_RECEIPTS.exists():
        print(f"  receipts:  {short_time(BACKGROUND_RECEIPTS)}  {BACKGROUND_RECEIPTS}")

    print("\nrecent operator steering")
    steering = newest(list(CONVERGENCE_DIR.glob("OPERATOR_STEER*.md")), 4)
    if not steering:
        print("  none yet")
    for path in steering:
        print(f"  {short_time(path)}  {path.name}")

    print("\nrecent replies to opus")
    replies = newest(list(INBOXES["opus_composer"].glob("*codex*reply*.md")), 4)
    if not replies:
        print("  no codex reply packet yet")
    for path in replies:
        print(f"  {short_time(path)}  {path.name}")
    print()


def packet_text(mode: str, body: str, stamp: str) -> str:
    mode_label = mode.upper()
    if mode_label == "ASK":
        mode_label = "QUESTION"
    return f"""# OPERATOR STEER - {mode_label} - {stamp}
from: Dhyana
to: opus_composer + codex_composer
mode: {mode_label}
created: {iso_now()}
canonical_home: {CONVERGENCE_DIR}

## Operator Message

{body.strip()}

## Required Response

- Each composer answers independently first.
- Then each composer reads the other's answer.
- Then update the disagreement ledger or shared picture.
- Do not execute code or change repo files unless this packet is explicitly an EXECUTION_LEASE.

## Routing Receipt Contract

This same packet is copied to both composer inboxes and the convergence home.
"""


def send_packet(mode: str, body: str) -> None:
    ensure_dirs()
    if not body.strip():
        print("Nothing sent: empty message.")
        return
    stamp = utc_stamp()
    safe_mode = mode.lower().replace(" ", "_")
    filename = f"OPERATOR_STEER_{stamp}_{safe_mode}.md"
    content = packet_text(mode, body, stamp)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    canonical = CONVERGENCE_DIR / filename
    atomic_write(canonical, content)
    atomic_write(LATEST_FILE, content)

    inbox_paths: list[str] = []
    for agent, inbox in INBOXES.items():
        target = inbox / filename
        shutil.copy2(canonical, target)
        inbox_paths.append(str(target))

    append_jsonl(
        LOG_FILE,
        {
            "timestamp": iso_now(),
            "mode": mode.upper(),
            "sha256_16": digest,
            "canonical": str(canonical),
            "inboxes": inbox_paths,
        },
    )

    print("\nSENT")
    print(f"  mode: {mode.upper()}")
    print(f"  sha:  {digest}")
    print(f"  home: {canonical}")
    for agent, inbox_path in zip(INBOXES, inbox_paths):
        print(f"  {agent}: {inbox_path}")
    print()


def read_artifact(name: str) -> None:
    aliases = {
        "opus": ARTIFACTS["opus view"],
        "codex": ARTIFACTS["codex view"],
        "ledger": ARTIFACTS["codex ledger"],
        "shared": ARTIFACTS["shared picture"],
        "latest": LATEST_FILE,
    }
    path = aliases.get(name)
    if path is None:
        print("Use: show opus|codex|ledger|shared|latest")
        return
    if not path.exists():
        print(f"Missing: {path}")
        return
    print(f"\n--- {path} ---")
    text = path.read_text(encoding="utf-8", errors="replace")
    print(text[-6000:])
    print("--- end ---\n")


def collect_multiline(command: str) -> str:
    print(f"Enter {command} text. End with a single '.' on its own line.")
    lines: list[str] = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def help_text() -> str:
    return """Commands:
  status                  show processes, round files, latest replies
  ask <text>              ask both composers a question
  verdict <text>          record an operator decision for both composers
  note <text>             send context without granting execution
  lease <text>            send an execution-lease packet; include scope yourself
  show opus|codex|ledger|shared|latest
  help
  quit

Tip: use bare ask/verdict/note/lease for multiline input, then '.' to send.
"""


def dispatch(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    command, _, rest = stripped.partition(" ")
    command = command.lower()

    if command in {"quit", "exit", "q"}:
        return False
    if command == "help":
        print(help_text())
        return True
    if command == "status":
        print_status()
        return True
    if command == "show":
        read_artifact(rest.strip().lower())
        return True
    if command in {"ask", "verdict", "note", "lease"}:
        body = rest.strip() or collect_multiline(command)
        mode = "EXECUTION_LEASE" if command == "lease" else command.upper()
        send_packet(mode, body)
        return True

    print("Unknown command. Type help.")
    return True


def main() -> int:
    ensure_dirs()
    print("Composer console: one surface for steering opus_composer + codex_composer.")
    print("Type 'help' for commands. Type 'status' first.")
    print_status()
    while True:
        try:
            line = input("composer> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 130
        if not dispatch(line):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
