"""Unified-diff parsing: hunk/file-patch model and parser.

Extracted verbatim from ``dharma_swarm.diff_applier`` (module line-budget);
``diff_applier`` re-exports these names so existing importers are unaffected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Hunk:
    """A single hunk from a unified diff."""

    src_start: int
    src_count: int
    dst_start: int
    dst_count: int
    lines: list[str] = field(default_factory=list)


@dataclass
class FilePatch:
    """All hunks targeting a single file."""

    old_path: str  # "a/foo.py" or "/dev/null"
    new_path: str  # "b/foo.py" or "/dev/null"
    hunks: list[Hunk] = field(default_factory=list)
    is_new_file: bool = False

    @property
    def target_path(self) -> str:
        """Return the effective file path (strip leading a/ or b/)."""
        if self.new_path == "/dev/null":
            return _strip_prefix(self.old_path)
        return _strip_prefix(self.new_path)


_HUNK_RE = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@"
)


def _strip_prefix(path: str) -> str:
    """Remove leading ``a/`` or ``b/`` prefix from diff paths."""
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def parse_unified_diff(diff_text: str) -> list[FilePatch]:
    """Parse a unified diff into a list of per-file patches.

    Handles:
    - Single and multi-file diffs
    - Multi-hunk patches
    - New file creation (old path ``/dev/null``)
    - Context, addition, and removal lines

    Args:
        diff_text: The full unified diff string.

    Returns:
        A list of ``FilePatch`` objects.

    Raises:
        ValueError: If the diff contains malformed hunk headers.
    """
    patches: list[FilePatch] = []
    current_patch: FilePatch | None = None
    current_hunk: Hunk | None = None
    lines = diff_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # --- / +++ pair signals a new file patch
        if line.startswith("--- "):
            old_path = line[4:].strip()
            # Expect +++ on the next line
            if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                new_path = lines[i + 1][4:].strip()
                is_new = old_path == "/dev/null"
                current_patch = FilePatch(
                    old_path=old_path,
                    new_path=new_path,
                    is_new_file=is_new,
                )
                patches.append(current_patch)
                current_hunk = None
                i += 2
                continue

        # Hunk header
        m = _HUNK_RE.match(line)
        if m and current_patch is not None:
            current_hunk = Hunk(
                src_start=int(m.group(1)),
                src_count=int(m.group(2)) if m.group(2) is not None else 1,
                dst_start=int(m.group(3)),
                dst_count=int(m.group(4)) if m.group(4) is not None else 1,
            )
            current_patch.hunks.append(current_hunk)
            i += 1
            continue

        # Hunk body: context, add, or remove lines
        if current_hunk is not None and line[:1] in (" ", "+", "-"):
            current_hunk.lines.append(line)
            i += 1
            continue

        # Skip diff metadata lines (diff --git, index, etc.)
        i += 1

    return patches
