"""Bounded filesystem operations for latency-sensitive async callers.

The functions here are synchronous by design. Async callers must invoke them
through ``asyncio.to_thread`` so a slow filesystem call cannot pin the event
loop while the explicit entry, time, and byte budgets take effect.
"""

from __future__ import annotations

import fnmatch
import os
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Pattern


DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".venv",
        "__pycache__",
        "node_modules",
        "venv",
    }
)


@dataclass(frozen=True)
class BoundedGlobResult:
    paths: tuple[Path, ...]
    entries_seen: int
    complete: bool
    stop_reason: str | None = None
    skipped_directories: int = 0
    errors: int = 0
    skipped_symlinks: int = 0


@dataclass(frozen=True)
class BoundedGrepMatch:
    path: Path
    line_number: int
    line: str


@dataclass(frozen=True)
class BoundedGrepResult:
    matches: tuple[BoundedGrepMatch, ...]
    discovery: BoundedGlobResult
    bytes_considered: int
    stop_reason: str | None = None
    oversized_skipped: int = 0
    errors: int = 0
    clipped_lines: int = 0


@dataclass(frozen=True)
class BoundedEditResult:
    source_bytes: int
    occurrences: int
    output_bytes: int | None = None
    wrote: bool = False


def _pattern_parts(pattern: str) -> tuple[str, ...]:
    if not pattern or pattern.startswith("/"):
        raise ValueError("glob pattern must be a non-empty relative path")
    parts = tuple(part for part in pattern.split("/") if part not in {"", "."})
    if not parts or ".." in parts:
        raise ValueError("glob pattern may not traverse outside the search root")
    return parts


def _matches_pattern(path_parts: tuple[str, ...], pattern_parts: tuple[str, ...]) -> bool:
    @lru_cache(maxsize=None)
    def matches(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        token = pattern_parts[pattern_index]
        if token == "**":
            return matches(path_index, pattern_index + 1) or (
                path_index < len(path_parts)
                and matches(path_index + 1, pattern_index)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], token)
            and matches(path_index + 1, pattern_index + 1)
        )

    return matches(0, 0)


def bounded_glob(
    root: Path,
    pattern: str,
    *,
    max_entries: int,
    max_matches: int,
    max_seconds: float,
    files_only: bool = False,
    excluded_dirs: frozenset[str] = DEFAULT_EXCLUDED_DIRS,
    _deadline: float | None = None,
) -> BoundedGlobResult:
    """Discover matching paths without an unbounded recursive traversal."""
    if max_entries <= 0 or max_matches <= 0 or max_seconds <= 0:
        raise ValueError("filesystem scan budgets must be positive")
    pattern_parts = _pattern_parts(pattern)
    deadline = _deadline or time.monotonic() + max_seconds
    max_depth = None if "**" in pattern_parts else len(pattern_parts)
    pending: deque[tuple[Path, tuple[str, ...]]] = deque([(Path(root), ())])
    matches: list[Path] = []
    entries_seen = skipped_directories = skipped_symlinks = errors = 0

    while pending:
        if time.monotonic() >= deadline:
            return BoundedGlobResult(
                tuple(matches), entries_seen, False, "deadline",
                skipped_directories, errors, skipped_symlinks,
            )
        directory, parent_parts = pending.popleft()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entries_seen >= max_entries:
                        return BoundedGlobResult(
                            tuple(matches), entries_seen, False, "entry_limit",
                            skipped_directories, errors, skipped_symlinks,
                        )
                    if time.monotonic() >= deadline:
                        return BoundedGlobResult(
                            tuple(matches), entries_seen, False, "deadline",
                            skipped_directories, errors, skipped_symlinks,
                        )
                    entries_seen += 1
                    path_parts = (*parent_parts, entry.name)
                    try:
                        if entry.is_symlink():
                            skipped_symlinks += 1
                            continue
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError:
                        errors += 1
                        continue
                    if _matches_pattern(path_parts, pattern_parts) and (
                        not files_only or is_file
                    ):
                        matches.append(Path(entry.path))
                        if len(matches) >= max_matches:
                            return BoundedGlobResult(
                                tuple(matches), entries_seen, False, "match_limit",
                                skipped_directories, errors, skipped_symlinks,
                            )
                    if not is_dir or (max_depth is not None and len(path_parts) >= max_depth):
                        continue
                    if entry.name in excluded_dirs:
                        skipped_directories += 1
                    else:
                        pending.append((Path(entry.path), path_parts))
        except OSError:
            errors += 1

    complete = skipped_directories == 0 and skipped_symlinks == 0 and errors == 0
    reason = None if complete else "skipped_paths"
    return BoundedGlobResult(
        tuple(matches), entries_seen, complete, reason,
        skipped_directories, errors, skipped_symlinks,
    )


def bounded_read_lines(
    path: Path,
    *,
    offset: int,
    limit: int,
    max_file_bytes: int,
) -> tuple[int, list[str]]:
    """Return a bounded line window after rejecting large files pre-open."""
    file_size = path.stat().st_size
    if file_size > max_file_bytes:
        return file_size, []
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, start=1):
            if line_number < offset:
                continue
            if len(lines) >= limit:
                break
            lines.append(line.rstrip("\r\n"))
    return file_size, lines


def bounded_replace_text(
    path: Path,
    old: str,
    new: str,
    *,
    max_file_bytes: int,
) -> BoundedEditResult:
    """Replace one occurrence without reading or writing an oversized file."""
    file_size = path.stat().st_size
    if file_size > max_file_bytes:
        return BoundedEditResult(file_size, 0)
    with path.open("rb") as stream:
        raw = stream.read(max_file_bytes + 1)
    if len(raw) > max_file_bytes:
        return BoundedEditResult(len(raw), 0)
    content = raw.decode("utf-8", errors="replace")
    occurrences = content.count(old)
    if occurrences != 1:
        return BoundedEditResult(len(raw), occurrences)
    updated = content.replace(old, new, 1).encode("utf-8")
    if len(updated) > max_file_bytes:
        return BoundedEditResult(len(raw), occurrences, len(updated))
    path.write_bytes(updated)
    return BoundedEditResult(len(raw), occurrences, len(updated), True)


def bounded_grep(
    root: Path,
    file_glob: str,
    compiled: Pattern[str],
    *,
    max_entries: int,
    max_candidates: int,
    max_file_bytes: int,
    max_total_bytes: int,
    max_matches: int,
    max_line_chars: int,
    max_seconds: float,
) -> BoundedGrepResult:
    """Search text with shared traversal, elapsed-time, and byte budgets."""
    deadline = time.monotonic() + max_seconds
    discovery = bounded_glob(
        root,
        file_glob,
        max_entries=max_entries,
        max_matches=max_candidates + 1,
        max_seconds=max_seconds,
        files_only=True,
        _deadline=deadline,
    )
    candidates = discovery.paths[:max_candidates]
    matches: list[BoundedGrepMatch] = []
    bytes_considered = oversized_skipped = errors = clipped_lines = 0
    stop_reason: str | None = None

    for candidate in candidates:
        if time.monotonic() >= deadline:
            stop_reason = "deadline"
            break
        try:
            file_size = candidate.stat().st_size
            if file_size > max_file_bytes:
                oversized_skipped += 1
                continue
            if bytes_considered + file_size > max_total_bytes:
                stop_reason = "byte_limit"
                break
            bytes_considered += file_size
            with candidate.open("r", encoding="utf-8", errors="replace") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if time.monotonic() >= deadline:
                        stop_reason = "deadline"
                        break
                    if not compiled.search(line):
                        continue
                    if len(matches) >= max_matches:
                        stop_reason = "match_limit"
                        break
                    clean_line = line.rstrip("\r\n")
                    if len(clean_line) > max_line_chars:
                        clean_line = clean_line[:max_line_chars]
                        clipped_lines += 1
                    matches.append(BoundedGrepMatch(candidate, line_number, clean_line))
        except OSError:
            errors += 1
        if stop_reason is not None:
            break

    if len(discovery.paths) > max_candidates and stop_reason is None:
        stop_reason = "candidate_limit"
    return BoundedGrepResult(
        tuple(matches), discovery, bytes_considered, stop_reason,
        oversized_skipped, errors, clipped_lines,
    )
