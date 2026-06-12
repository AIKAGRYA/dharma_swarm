#!/usr/bin/env python3
"""Detect legacy A2A filesystem broadcast amplification.

The filesystem inbox is a compatibility dock. A single broadcast copied into
every inbox is not 76 independent work items, and it must not be mistaken for
live NATS contact or production collaboration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_INBOXES_ROOT = Path.home() / ".dharma" / "a2a_bus" / "inboxes"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECEIPT = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "nats_reset"
    / "2026-06-13"
    / "FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json"
)


@dataclass(frozen=True)
class InboxEntry:
    path: Path
    agent: str
    entry_type: str
    bytes: int
    fingerprint: str
    parsed: bool
    message_id: str | None
    sender: str | None
    recipient: str | None
    message_type: str | None
    read: bool | None


def _entry_bytes(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    if path.is_dir():
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
        return total
    return 0


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        digest.update(path.read_bytes())
    except OSError:
        digest.update(str(path).encode())
    return digest.hexdigest()


def _directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(child.relative_to(path)).encode())
        try:
            digest.update(child.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()


def _fingerprint(path: Path, payload: dict[str, Any] | None) -> str:
    message_id = payload.get("id") if payload else None
    if isinstance(message_id, str) and message_id:
        return f"id:{message_id}"
    if path.is_dir():
        return f"sha256:{_directory_digest(path)}"
    return f"sha256:{_file_digest(path)}"


def _read_entry(path: Path, agent: str) -> InboxEntry:
    payload: dict[str, Any] | None = None
    parsed = False
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload = raw
                parsed = True
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            payload = None
    fingerprint = _fingerprint(path, payload)
    return InboxEntry(
        path=path,
        agent=agent,
        entry_type="directory" if path.is_dir() else "file",
        bytes=_entry_bytes(path),
        fingerprint=fingerprint,
        parsed=parsed,
        message_id=str(payload.get("id")) if payload and payload.get("id") else None,
        sender=str(payload.get("from")) if payload and payload.get("from") else None,
        recipient=str(payload.get("to")) if payload and payload.get("to") else None,
        message_type=str(payload.get("type")) if payload and payload.get("type") else None,
        read=bool(payload.get("read")) if payload and "read" in payload else None,
    )


def discover_entries(inboxes_root: Path) -> list[InboxEntry]:
    if not inboxes_root.exists():
        return []
    entries: list[InboxEntry] = []
    for inbox_dir in sorted(path for path in inboxes_root.iterdir() if path.is_dir()):
        for path in sorted(inbox_dir.iterdir()):
            if path.name == "README.md":
                continue
            entries.append(_read_entry(path, inbox_dir.name))
    return entries


def analyze_file_bus(
    inboxes_root: Path,
    *,
    broadcast_mirror_threshold: int = 5,
) -> dict[str, Any]:
    entries = discover_entries(inboxes_root)
    groups: dict[str, list[InboxEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.fingerprint, []).append(entry)

    broadcast_groups: list[dict[str, Any]] = []
    for fingerprint, grouped in sorted(groups.items()):
        agents = sorted({entry.agent for entry in grouped})
        recipients = sorted({entry.recipient for entry in grouped if entry.recipient})
        is_broadcast = "all" in recipients
        is_mirrored = len(agents) >= broadcast_mirror_threshold
        if not (is_broadcast and is_mirrored):
            continue
        sample = grouped[0]
        broadcast_groups.append(
            {
                "fingerprint": fingerprint,
                "message_id": sample.message_id,
                "from": sample.sender,
                "to": sample.recipient,
                "type": sample.message_type,
                "agents_count": len(agents),
                "agents_preview": agents[:20],
                "entry_count": len(grouped),
                "unread_count": sum(1 for entry in grouped if entry.read is False),
                "bytes_total": sum(entry.bytes for entry in grouped),
                "sample_paths": [str(entry.path) for entry in grouped[:5]],
            }
        )

    return {
        "schema_version": "dharma.a2a.file_bus_guard.v1",
        "inboxes_root": str(inboxes_root),
        "status": "FAIL" if broadcast_groups else "PASS",
        "production_claim": False,
        "entry_count": len(entries),
        "group_count": len(groups),
        "broadcast_mirror_threshold": broadcast_mirror_threshold,
        "broadcast_group_count": len(broadcast_groups),
        "broadcast_candidate_count": sum(group["entry_count"] for group in broadcast_groups),
        "broadcast_groups": broadcast_groups,
        "production_interpretation": (
            "filesystem broadcast amplification detected; do not count mirrored "
            "inbox files as independent live-contact tasks"
            if broadcast_groups
            else "no amplified legacy filesystem broadcast detected"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inboxes-root", default=str(DEFAULT_INBOXES_ROOT))
    parser.add_argument("--broadcast-mirror-threshold", type=int, default=5)
    parser.add_argument("--receipt-path", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--write", action="store_true", help="write the JSON receipt")
    parser.add_argument("--check", action="store_true", help="exit non-zero if guard status is FAIL")
    parser.add_argument("--json", action="store_true")
    return parser


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = analyze_file_bus(
        Path(args.inboxes_root).expanduser(),
        broadcast_mirror_threshold=max(args.broadcast_mirror_threshold, 2),
    )
    if args.write:
        write_receipt(Path(args.receipt_path).expanduser(), result)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"{result['status']} entries={result['entry_count']} "
            f"broadcast_groups={result['broadcast_group_count']}"
        )
    if args.check and result["status"] == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
