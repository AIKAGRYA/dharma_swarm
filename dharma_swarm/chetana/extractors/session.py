"""Claude Code JSONL session extractor.

Sessions live at:
    ~/.claude/projects/<sanitized-cwd>/<session-uuid>.jsonl

Each line is a JSON object representing one turn. Extracts substantive
assistant turns (≥80 chars, non-tool) into (user_prompt, assistant_text) pairs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionTurn:
    line_idx: int
    user_text: str
    assistant_text: str


def extract_session_turns(path: Path, *, min_length: int = 80) -> list[SessionTurn]:
    if not path.exists():
        return []
    turns: list[SessionTurn] = []
    last_user = ""
    for line_idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = row.get("type") or row.get("role")
        text = _extract_text(row)
        if not text:
            continue
        if kind in ("user", "human"):
            last_user = text
            continue
        if kind not in ("assistant", "ai"):
            continue
        if len(text) < min_length:
            continue
        turns.append(SessionTurn(line_idx=line_idx, user_text=last_user, assistant_text=text))
    return turns


def _extract_text(row) -> str:
    content = row.get("content") or row.get("message")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict) and "text" in content:
        return str(content["text"]).strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in ("text", "output_text") and item.get("text"):
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(p.strip() for p in parts if p.strip()).strip()
    return ""
