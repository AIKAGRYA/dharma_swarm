"""Karpathy-style append-only wiki operation log."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Mapping

from . import staging as staging_mod
from .safe_write import (
    AnchoredTextChange,
    apply_anchored_text_changes,
    capture_anchor_identity,
    read_anchored_text,
)


def append_wiki_log(
    *,
    operation: str,
    title: str,
    atom_path: Path | None = None,
    atom_id: str | None = None,
    details: Mapping[str, str] | None = None,
    root: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Append a parseable operation entry to ``wiki/log.md``."""
    wiki_root = Path(root or staging_mod.WIKI_ROOT).expanduser()
    wiki_root.mkdir(parents=True, exist_ok=True)
    wiki_root = wiki_root.resolve()
    anchor_identity = capture_anchor_identity(wiki_root)
    log_path = wiki_root / "log.md"
    original = read_anchored_text(wiki_root, "log.md")
    entry = render_wiki_log_entry(
        operation=operation,
        title=title,
        atom_path=atom_path,
        atom_id=atom_id,
        details=details,
        now=now,
    )
    separator = "" if not original or original.endswith("\n") else "\n"
    updated = (original or "") + separator + entry
    apply_anchored_text_changes(
        wiki_root,
        [
            AnchoredTextChange(
                relative_path="log.md",
                original_text=original,
                updated_text=updated,
            )
        ],
        expected_text={"log.md": original},
        expected_anchor_identity=anchor_identity,
    )
    return log_path


def render_wiki_log_entry(
    *,
    operation: str,
    title: str,
    atom_path: Path | None = None,
    atom_id: str | None = None,
    details: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> str:
    """Render one injection-safe, prefix-parseable operation receipt."""

    stamp = (now or datetime.now().astimezone()).strftime("%Y-%m-%d %H:%M")
    lines = [f"## [{stamp}] {_header_field(operation)} | {_header_field(title)}", ""]
    if atom_id:
        lines.append(f"- atom_id: {_single_line(atom_id)}")
    if atom_path:
        lines.append(f"- path: {_single_line(atom_path)}")
    for key, value in (details or {}).items():
        safe_key = _detail_key(key)
        safe_value = _single_line(value)
        lines.append(f"- {safe_key}: {safe_value}")
    lines.append("")
    return "\n".join(lines)


def _single_line(value: object) -> str:
    # str.splitlines recognizes CR/LF plus Unicode separators such as U+2028,
    # U+2029, U+0085, and vertical tab. Joining closes forged-record injection
    # through any Python-recognized logical line boundary.
    rendered = " ".join(part.strip() for part in str(value).splitlines())
    # Neutralize terminal controls (Cc) and invisible formatting controls (Cf),
    # including NUL, ESC, bidi overrides, and zero-width direction marks.
    rendered = "".join(
        " " if unicodedata.category(character) in {"Cc", "Cf"} else character
        for character in rendered
    )
    return rendered.strip()


def _header_field(value: object) -> str:
    return _single_line(value).replace("|", "¦")


def _detail_key(value: object) -> str:
    rendered = _single_line(value)
    safe = "".join(
        character if character.isalnum() or character in "_.-" else "_"
        for character in rendered
    ).strip("_")
    return safe or "detail"
