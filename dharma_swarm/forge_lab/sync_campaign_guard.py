"""Foreground-campaign deploy guard for code-sync activation.

Split out of ``sync_control`` to keep both modules under the repo's 500-line
budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). STDLIB-ONLY: this module
is bundled into the remote node program by
``sync_orchestrator._node_source`` — do not add first-party imports.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


_FOREGROUND_CAMPAIGN_PATTERNS = (
    re.compile(r"dharma_swarm\.forge_lab\.experiment(?:\s|$)", re.I),
    re.compile(r"dharma_swarm\.forge_lab\.cli\s+run(?:\s|$)", re.I),
    re.compile(
        r"dharma_swarm\.forge_lab(?:\.rsi_cli)?\s+newrun\b.*(?:^|\s)--execute(?:\s|$)",
        re.I,
    ),
    re.compile(
        r"dharma_swarm\.forge_lab(?:\.rsi_cli)?\s+campaign\s+"
        r"(?:run|pause|resume|stop|fork|fuse-ack)\b",
        re.I,
    ),
    re.compile(
        r"(?:^|\s)(?:\S*/)?(?:rsi|rsilab)(?:\s+-)?\s+newrun\b"
        r".*(?:^|\s)--execute(?:\s|$)",
        re.I,
    ),
    re.compile(
        r"(?:^|\s)(?:\S*/)?(?:rsi|rsilab)\s+campaign\s+"
        r"(?:run|pause|resume|stop|fork|fuse-ack)\b",
        re.I,
    ),
    re.compile(r"(?:^|\s)(?:\S*/)?experiment\.py(?:\s|$)", re.I),
    re.compile(r"rsi-manager-|rsi-overnight|forge_lab_v1_run", re.I),
)


def _foreground_campaign_argv(argv: str) -> bool:
    return any(pattern.search(argv) for pattern in _FOREGROUND_CAMPAIGN_PATTERNS)


def _campaign_guard(root: Path) -> dict[str, Any]:
    reasons: list[str] = []
    evidence: dict[str, Any] = {}
    block = root / "DEPLOYMENT_BLOCK"
    if block.exists():
        reasons.append(f"operator deployment block exists: {block}")

    active_manifest = root / "state" / ".dharma" / "forge_lab" / "active_campaign.json"
    if active_manifest.is_file():
        try:
            payload = json.loads(active_manifest.read_text(encoding="utf-8"))
            state = str(payload.get("state", "unknown")).lower()
            evidence["active_campaign_manifest_state"] = state
            terminal_states = {
                "completed",
                "failed",
                "paused",
                "stopped",
                "aborted",
                "cancelled",
            }
            if state not in terminal_states:
                reasons.append(f"campaign manifest reports active state: {state}")
        except (OSError, json.JSONDecodeError) as exc:
            reasons.append(f"active campaign manifest is unreadable: {exc}")

    try:
        tmux = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        sessions = [line.strip() for line in tmux.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        sessions = []
    active_sessions = [
        name
        for name in sessions
        if re.search(r"(^|[-_])(rsi|forge[-_]lab)([-_]|$)", name, re.I)
    ]
    evidence["tmux_sessions"] = sessions
    if active_sessions:
        reasons.append(f"active RSI tmux sessions: {', '.join(active_sessions)}")

    try:
        processes = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        processes = []
    active_processes = [
        line.strip()
        for line in processes
        if _foreground_campaign_argv(line)
        and "sync_control" not in line
    ]
    evidence["active_process_count"] = len(active_processes)
    if active_processes:
        reasons.append(f"active RSI process count: {len(active_processes)}")
    return {"ok": not reasons, "reasons": reasons, "evidence": evidence}
