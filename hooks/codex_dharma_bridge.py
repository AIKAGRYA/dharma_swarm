#!/usr/bin/env python3
"""Codex lifecycle bridge for dharma_swarm.

The repo-level `.codex/hooks.json` routes Codex hook events here. This hook must
be fail-open: a local receipt/logging problem should never prevent an agent from
finishing its own receipt. It records only sanitized metadata and short previews.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]\s*[^\s\"']+"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize(value: Any, *, max_len: int = 240) -> str:
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    text = text.replace("\n", "\\n")
    if len(text) > max_len:
        return text[:max_len] + "...[truncated]"
    return text


def stable_hash(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, default=str).encode("utf-8", errors="replace")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def build_receipt(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"parse_error": True, "raw_preview": sanitize(raw)}

    tool_input = payload.get("tool_input")
    command_preview = None
    if isinstance(tool_input, dict):
        command_preview = tool_input.get("command") or tool_input.get("cmd")

    return {
        "schema_version": "dharma.codex_hook_event.v1",
        "recorded_at": utc_now(),
        "hook_event_name": payload.get("hook_event_name") or payload.get("event") or "unknown",
        "tool_name": payload.get("tool_name"),
        "cwd": payload.get("cwd") or os.getcwd(),
        "session_id": payload.get("session_id"),
        "payload_hash": stable_hash(payload),
        "payload_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
        "command_preview": sanitize(command_preview) if command_preview else None,
        "secret_value_recorded": False,
        "decision": "allow",
        "failure_policy": "fail_open",
    }


def write_receipt(receipt: dict[str, Any]) -> None:
    root = Path.home() / ".dharma" / "codex_hooks"
    root.mkdir(parents=True, exist_ok=True)
    path = root / (datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")


def main() -> int:
    raw = sys.stdin.read()
    receipt = build_receipt(raw)
    write_receipt(receipt)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)
