"""Strict, local-only unified-diff replay for Foundry artifacts.

The artifact lane needs one deliberately smaller primitive than the live
proposal lane: replay an already-canonical, single-file unified diff against a
pinned tree.  It does not guess at drift, invoke a shell, allow new/deleted
files, or accept paths outside the declared evolve scope.  A mismatch is a
typed failure and leaves the target bytes untouched.
"""

from __future__ import annotations

import os
import re
import shlex
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?(?:\n)?$"
)


class PatchReplayError(RuntimeError):
    """A patch is unsafe, malformed, stale, or outside the declared scope."""


def read_regular_nofollow(
    path: Path,
    *,
    field: str,
    error_type: type[RuntimeError] = PatchReplayError,
) -> bytes:
    """Read the regular file addressed by a no-follow descriptor."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise error_type(f"{field} missing or unreadable: {path}") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise error_type(f"{field} is not a regular file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def scoped_regular_file(
    root: Path,
    relative: object,
    *,
    field: str,
    error_type: type[RuntimeError] = PatchReplayError,
) -> Path:
    """Resolve a bounded regular file while rejecting every symlink component."""
    try:
        root = Path(root).resolve(strict=True)
    except OSError as exc:
        raise error_type(f"{field} root is unavailable: {root}") from exc
    text = str(relative)
    path = PurePosixPath(text)
    if (
        not text
        or text.startswith("/")
        or "\\" in text
        or "\x00" in text
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise error_type(f"unsafe {field}: {text!r}")
    lexical = root / path
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise error_type(f"{field} is unavailable: {text}") from exc
    if not resolved.is_relative_to(root):
        raise error_type(f"{field} escapes declared root: {text}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise error_type(f"{field} traverses a symlink: {text}")
    if not resolved.is_file():
        raise error_type(f"{field} is not a regular file: {text}")
    return resolved


def write_immutable_beneath(root: Path, relative: str, data: bytes) -> Path:
    """Create or verify one immutable file through no-follow directory handles."""
    path = PurePosixPath(relative)
    if (
        not relative
        or relative.startswith("/")
        or "\\" in relative
        or "\x00" in relative
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PatchReplayError(f"unsafe immutable artifact path: {relative!r}")
    root = Path(root)
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        root.mkdir(parents=True, exist_ok=True)
        directory_fd = os.open(root, directory_flags)
    except OSError as exc:
        raise PatchReplayError(f"immutable artifact root is unsafe: {root}") from exc
    try:
        for part in path.parts[:-1]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=directory_fd)
            except FileExistsError:
                pass
            except OSError as exc:
                raise PatchReplayError(
                    f"immutable artifact parent is unsafe: {relative}"
                ) from exc
            try:
                next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            except OSError as exc:
                raise PatchReplayError(
                    f"immutable artifact parent is unsafe: {relative}"
                ) from exc
            os.close(directory_fd)
            directory_fd = next_fd

        name = path.parts[-1]
        create_flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open(name, create_flags, 0o600, dir_fd=directory_fd)
        except FileExistsError:
            read_flags = (
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
            )
            try:
                descriptor = os.open(name, read_flags, dir_fd=directory_fd)
                with os.fdopen(descriptor, "rb") as handle:
                    if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                        raise PatchReplayError(
                            f"immutable artifact is not regular: {relative}"
                        )
                    existing = handle.read()
            except OSError as exc:
                raise PatchReplayError(
                    f"immutable artifact is unsafe: {relative}"
                ) from exc
            if existing != data:
                raise PatchReplayError(f"content-address collision at {relative}")
        except OSError as exc:
            raise PatchReplayError(f"immutable artifact is unsafe: {relative}") from exc
        else:
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.fsync(directory_fd)
            except OSError as exc:
                try:
                    os.unlink(name, dir_fd=directory_fd)
                except OSError:
                    pass
                raise PatchReplayError(
                    f"immutable artifact write failed: {relative}"
                ) from exc
    finally:
        os.close(directory_fd)
    return root / Path(*path.parts)


@dataclass(frozen=True)
class PatchHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class ParsedPatch:
    path: str
    hunks: tuple[PatchHunk, ...]


def _header_path(line: str, prefix: str) -> str:
    if not line.startswith(prefix):
        raise PatchReplayError(f"expected {prefix.strip()} patch header")
    raw = line[len(prefix) :].rstrip("\n").split("\t", 1)[0]
    if raw.startswith(("a/", "b/")):
        raw = raw[2:]
    if raw == "/dev/null":
        raise PatchReplayError("new and deleted files are outside artifact replay scope")
    if not raw or raw.startswith("/") or "\\" in raw or "\x00" in raw:
        raise PatchReplayError(f"unsafe patch path: {raw!r}")
    posix = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise PatchReplayError(f"unsafe patch path: {raw!r}")
    return posix.as_posix()


def _git_diff_paths(line: str) -> tuple[str, str]:
    try:
        tokens = shlex.split(line.rstrip("\n"))
    except ValueError as exc:
        raise PatchReplayError("malformed diff --git header") from exc
    if len(tokens) != 4 or tokens[:2] != ["diff", "--git"]:
        raise PatchReplayError("malformed diff --git header")
    return (
        _header_path(f"--- {tokens[2]}\n", "--- "),
        _header_path(f"+++ {tokens[3]}\n", "+++ "),
    )


def parse_unified_diff(diff: str) -> ParsedPatch:
    """Parse one existing-file unified diff and validate all hunk counts."""
    lines = diff.splitlines(keepends=True)
    if len(lines) < 3:
        raise PatchReplayError("patch is empty or missing unified-diff headers")
    header_index = next(
        (index for index, line in enumerate(lines) if line.startswith("--- ")),
        None,
    )
    if header_index is None or header_index + 1 >= len(lines):
        raise PatchReplayError("patch is missing an old/new file header pair")
    old_path = _header_path(lines[header_index], "--- ")
    new_path = _header_path(lines[header_index + 1], "+++ ")
    if old_path != new_path:
        raise PatchReplayError("artifact replay cannot rename files")
    preamble = [line for line in lines[:header_index] if line.strip()]
    if preamble:
        if not preamble[0].startswith("diff --git ") or any(
            not line.startswith("index ") for line in preamble[1:]
        ):
            raise PatchReplayError("unsupported structural patch preamble")
        git_old, git_new = _git_diff_paths(preamble[0])
        if git_old != old_path or git_new != new_path:
            raise PatchReplayError("diff --git header does not bind the replay target")

    hunks: list[PatchHunk] = []
    changed = False
    index = header_index + 2
    while index < len(lines):
        if lines[index].startswith(("--- ", "+++ ", "diff --git ")):
            raise PatchReplayError("artifact replay accepts exactly one file")
        match = _HUNK_HEADER.match(lines[index])
        if match is None:
            if not lines[index].strip():
                index += 1
                continue
            raise PatchReplayError(f"malformed hunk header: {lines[index].rstrip()!r}")
        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        new_start = int(match.group(3))
        new_count = int(match.group(4) or "1")
        index += 1
        body: list[str] = []
        observed_old = 0
        observed_new = 0
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if line.startswith(("--- ", "+++ ", "diff --git ")):
                raise PatchReplayError("artifact replay accepts exactly one file")
            if line.startswith("\\ No newline at end of file"):
                raise PatchReplayError("no-newline patches are not supported")
            if not line or line[0] not in {" ", "+", "-"}:
                raise PatchReplayError(f"malformed hunk body line: {line.rstrip()!r}")
            body.append(line)
            if line[0] in {"+", "-"}:
                changed = True
            if line[0] in {" ", "-"}:
                observed_old += 1
            if line[0] in {" ", "+"}:
                observed_new += 1
            index += 1
        if observed_old != old_count or observed_new != new_count:
            raise PatchReplayError(
                "hunk count mismatch: "
                f"declared -{old_count}/+{new_count}, "
                f"observed -{observed_old}/+{observed_new}"
            )
        hunks.append(PatchHunk(old_start, old_count, new_start, new_count, tuple(body)))
    if not hunks:
        raise PatchReplayError("patch contains no hunks")
    if not changed:
        raise PatchReplayError("patch contains no changed lines")
    return ParsedPatch(path=old_path, hunks=tuple(hunks))


def _scoped_target(root: Path, relative: str, allowed_paths: Iterable[str]) -> Path:
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise PatchReplayError(f"pinned tree is unavailable: {root}") from exc
    allowed = {PurePosixPath(path).as_posix() for path in allowed_paths}
    if not allowed:
        raise PatchReplayError("declared evolve scope is empty")
    if relative not in allowed:
        raise PatchReplayError(f"patch path is outside declared evolve scope: {relative}")
    lexical = root / relative
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise PatchReplayError(f"patch target is unavailable: {relative}") from exc
    if not resolved.is_relative_to(root):
        raise PatchReplayError(f"patch path escapes pinned tree: {relative}")
    cursor = root
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise PatchReplayError(f"symlinked patch path is forbidden: {relative}")
    if not resolved.is_file():
        raise PatchReplayError(f"patch target is not a regular file: {relative}")
    return resolved


def _replay(source: list[str], patch: ParsedPatch) -> list[str]:
    output: list[str] = []
    source_index = 0
    expected_new_line = 1
    for hunk in patch.hunks:
        hunk_index = hunk.old_start - 1 if hunk.old_count else hunk.old_start
        if hunk_index < source_index or hunk_index > len(source):
            raise PatchReplayError("hunks overlap or start outside the target")
        output.extend(source[source_index:hunk_index])
        expected_new_line += hunk_index - source_index
        # Unified-diff coordinates anchor an empty new-file range immediately
        # before the next output line.  A deletion at the start of a file is
        # therefore ``+0,0`` (and a later deletion is ``+(line - 1),0``).
        declared_new_start = (
            expected_new_line if hunk.new_count else expected_new_line - 1
        )
        if hunk.new_start != declared_new_start:
            raise PatchReplayError("new-file hunk coordinates are inconsistent")
        source_index = hunk_index
        for line in hunk.lines:
            marker, content = line[0], line[1:]
            if marker in {" ", "-"}:
                if source_index >= len(source) or source[source_index] != content:
                    raise PatchReplayError("patch context does not match pinned target bytes")
                source_index += 1
            if marker in {" ", "+"}:
                output.append(content)
                expected_new_line += 1
    output.extend(source[source_index:])
    return output


def apply_unified_diff(
    root: Path,
    diff: str,
    *,
    allowed_paths: Iterable[str],
    check_only: bool = False,
) -> Path:
    """Replay ``diff`` exactly, atomically replacing one scoped UTF-8 file."""
    parsed = parse_unified_diff(diff)
    target = _scoped_target(Path(root), parsed.path, allowed_paths)
    try:
        # ``Path.read_text`` enables universal-newline translation and would
        # silently rewrite untouched CRLF/mixed-newline lines. Exact replay
        # keeps the source terminators byte-for-byte unless the diff names them.
        with target.open("r", encoding="utf-8", newline="") as handle:
            source = handle.readlines()
    except UnicodeDecodeError as exc:
        raise PatchReplayError("binary artifact targets are unsupported") from exc
    candidate = "".join(_replay(source, parsed))
    if check_only:
        return target

    descriptor, temporary = tempfile.mkstemp(prefix=".foundry-replay-", dir=target.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(candidate)
            handle.flush()
            os.fsync(handle.fileno())
        original_mode = stat.S_IMODE(target.stat().st_mode)
        os.chmod(temporary_path, original_mode)
        os.replace(temporary_path, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)
    return target
