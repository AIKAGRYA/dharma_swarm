"""Descriptor-anchored, no-follow text replacement transactions.

Path validation followed by a pathname-based rename leaves a TOCTOU window: a
directory can be swapped for a symlink after validation.  This module opens the
resolved anchor one component at a time with ``O_NOFOLLOW`` and performs every
read, stage, replace, cleanup, and rollback relative to held directory
descriptors.  A later pathname swap can make the transaction fail, but cannot
redirect a write outside the originally opened tree.
"""

from __future__ import annotations

import errno
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence


AnchorIdentity = tuple[int, int]


class AnchoredWriteError(OSError):
    """An anchored transaction failed or observed concurrent drift."""


@dataclass(frozen=True)
class AnchoredTextChange:
    """One exact create, replace, or delete below an anchored directory."""

    relative_path: str
    original_text: str | None
    updated_text: str | None


@dataclass
class _StagedChange:
    change: AnchoredTextChange
    parent_fd: int
    parent_parts: tuple[str, ...]
    filename: str
    temporary_name: str
    original_mode: int | None


def read_anchored_text(anchor_root: Path | str, relative_path: str) -> str | None:
    """Read one regular UTF-8 file without following any path symlink."""

    anchor = _lexical_absolute_path(anchor_root)
    relative = _validate_relative_path(relative_path)
    root_fd = _open_absolute_directory(anchor)
    try:
        parent_fd = _open_relative_directory(root_fd, relative.parts[:-1])
        try:
            return _read_regular_text(parent_fd, relative.name)
        finally:
            os.close(parent_fd)
    finally:
        os.close(root_fd)


def apply_anchored_text_changes(
    anchor_root: Path | str,
    changes: Sequence[AnchoredTextChange],
    *,
    expected_text: Mapping[str, str | None] | None = None,
    expected_anchor_identity: AnchorIdentity | None = None,
    final_validator: Callable[[], None] | None = None,
) -> None:
    """Stage and apply an exact multi-file transaction below ``anchor_root``.

    Every output is staged before the first replacement.  The caller may also
    provide a full-corpus ``expected_text`` snapshot; it is revalidated after
    staging.  Rollback restores only a file that still equals this transaction's
    output, preserving a later non-cooperative edit as an explicit conflict.
    """

    anchor = _lexical_absolute_path(anchor_root)
    if not changes:
        return
    relative_changes = tuple(
        (change, _validate_relative_path(change.relative_path)) for change in changes
    )
    if any(
        change.original_text == change.updated_text for change, _ in relative_changes
    ):
        raise AnchoredWriteError("anchored changes must alter their target")
    relative_names = [relative.as_posix() for _change, relative in relative_changes]
    if len(relative_names) != len(set(relative_names)):
        raise AnchoredWriteError("each anchored target may appear only once")

    root_fd = _open_absolute_directory(anchor)
    staged: list[_StagedChange] = []
    replaced: list[_StagedChange] = []
    try:
        if (
            expected_anchor_identity is not None
            and _descriptor_identity(root_fd) != expected_anchor_identity
        ):
            raise AnchoredWriteError(
                f"transaction anchor changed before staging: {anchor}"
            )
        for change, relative in relative_changes:
            parent_parts = tuple(relative.parts[:-1])
            parent_fd = _open_relative_directory(root_fd, parent_parts)
            try:
                current, mode = _read_regular_text_with_mode(parent_fd, relative.name)
                if current != change.original_text:
                    raise AnchoredWriteError(
                        f"anchored target changed before staging: {relative}"
                    )
                temporary_name = (
                    _stage_text(
                        parent_fd,
                        relative.name,
                        change.updated_text,
                        mode=mode or 0o644,
                    )
                    if change.updated_text is not None
                    else ""
                )
            except Exception:
                os.close(parent_fd)
                raise
            staged.append(
                _StagedChange(
                    change=change,
                    parent_fd=parent_fd,
                    parent_parts=parent_parts,
                    filename=relative.name,
                    temporary_name=temporary_name,
                    original_mode=mode,
                )
            )

        for raw_relative, expected in (expected_text or {}).items():
            _assert_anchor_still_mapped(anchor, root_fd)
            relative = _validate_relative_path(raw_relative)
            current = _read_from_root(root_fd, relative)
            if current != expected:
                raise AnchoredWriteError(
                    f"anchored corpus changed during staging: {relative}"
                )

        for item in staged:
            _assert_anchor_still_mapped(anchor, root_fd)
            _assert_parent_still_mapped(root_fd, item)
            current = _read_regular_text(item.parent_fd, item.filename)
            if current != item.change.original_text:
                raise AnchoredWriteError(
                    "anchored target changed before replacement: "
                    f"{item.change.relative_path}"
                )
            # Track before the syscall: a fault-injection wrapper (or unusual
            # filesystem) can perform the rename and then raise.  Rollback must
            # still inspect and restore that target.
            replaced.append(item)
            if item.change.updated_text is None:
                os.unlink(item.filename, dir_fd=item.parent_fd)
            else:
                os.replace(
                    item.temporary_name,
                    item.filename,
                    src_dir_fd=item.parent_fd,
                    dst_dir_fd=item.parent_fd,
                )
                item.temporary_name = ""
            # A non-cooperative writer can swap the named directory after the
            # pre-replace check (including from inside a wrapped replace call).
            # The write is still confined to our held descriptor, but it must
            # not be reported as a canonical-path success if that descriptor
            # has been detached from the tree.
            _assert_anchor_still_mapped(anchor, root_fd)
            _assert_parent_still_mapped(root_fd, item)
            if _read_regular_text(item.parent_fd, item.filename) != (
                item.change.updated_text
            ):
                raise AnchoredWriteError(
                    "anchored target does not contain staged output after replacement: "
                    f"{item.change.relative_path}"
                )

        for parent_fd in {item.parent_fd for item in staged}:
            os.fsync(parent_fd)
        # Revalidate the complete corpus after durability calls. Changed paths
        # now expect the transaction output; untouched paths retain the caller's
        # snapshot. This catches a concurrent semantic-source edit after the
        # first replacement and turns it into a rollback rather than a stale
        # successful projection.
        final_expected = dict(expected_text or {})
        final_expected.update(
            {change.relative_path: change.updated_text for change in changes}
        )
        _validate_final_state(
            anchor,
            root_fd,
            staged,
            final_expected,
        )
        if final_validator is not None:
            final_validator()
            # A pathname-based validator may itself race with a root/parent
            # swap, so bind its result back to the held descriptors.
            _validate_final_state(
                anchor,
                root_fd,
                staged,
                final_expected,
            )
    except Exception as exc:
        rollback_errors: list[str] = []
        for item in reversed(replaced):
            rollback_name = ""
            try:
                current = _read_regular_text(item.parent_fd, item.filename)
                if current == item.change.original_text:
                    # The replacement syscall failed before changing the entry.
                    continue
                if current != item.change.updated_text:
                    rollback_errors.append(
                        f"{item.change.relative_path}: changed again after write"
                    )
                    continue
                if item.change.original_text is None:
                    os.unlink(item.filename, dir_fd=item.parent_fd)
                else:
                    rollback_name = _stage_text(
                        item.parent_fd,
                        item.filename,
                        item.change.original_text,
                        mode=item.original_mode or 0o644,
                    )
                    os.replace(
                        rollback_name,
                        item.filename,
                        src_dir_fd=item.parent_fd,
                        dst_dir_fd=item.parent_fd,
                    )
                    rollback_name = ""
            except Exception as rollback_exc:  # preserve the primary failure
                rollback_errors.append(f"{item.change.relative_path}: {rollback_exc}")
            finally:
                if rollback_name:
                    _unlink_if_present(item.parent_fd, rollback_name)
        for parent_fd in {item.parent_fd for item in replaced}:
            try:
                os.fsync(parent_fd)
            except OSError as sync_exc:
                rollback_errors.append(f"directory fsync: {sync_exc}")
        detail = (
            "; rollback conflicts: " + ", ".join(rollback_errors)
            if rollback_errors
            else "; prior writes rolled back"
        )
        raise AnchoredWriteError(f"anchored apply failed: {exc}{detail}") from exc
    finally:
        for item in staged:
            if item.temporary_name:
                _unlink_if_present(item.parent_fd, item.temporary_name)
            os.close(item.parent_fd)
        os.close(root_fd)


def capture_anchor_identity(anchor_root: Path | str) -> AnchorIdentity:
    """Capture the no-follow directory identity a later apply must retain."""

    anchor = _lexical_absolute_path(anchor_root)
    descriptor = _open_absolute_directory(anchor)
    try:
        return _descriptor_identity(descriptor)
    finally:
        os.close(descriptor)


def _lexical_absolute_path(path: Path | str) -> Path:
    """Normalize dot segments without resolving symlinks."""

    return Path(os.path.abspath(os.fspath(Path(path).expanduser())))


def _descriptor_identity(descriptor: int) -> AnchorIdentity:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _validate_final_state(
    anchor: Path,
    root_fd: int,
    staged: Sequence[_StagedChange],
    expected_text: Mapping[str, str | None],
) -> None:
    """Rebind final bytes and corpus snapshots to held descriptors."""

    _assert_anchor_still_mapped(anchor, root_fd)
    for item in staged:
        _assert_parent_still_mapped(root_fd, item)
        if _read_regular_text(item.parent_fd, item.filename) != (
            item.change.updated_text
        ):
            raise AnchoredWriteError(
                "anchored target drifted before transaction completion: "
                f"{item.change.relative_path}"
            )
    for raw_relative, expected in expected_text.items():
        relative = _validate_relative_path(raw_relative)
        current = _read_from_root(root_fd, relative)
        if current != expected:
            raise AnchoredWriteError(
                f"anchored corpus drifted before transaction completion: {relative}"
            )


def _validate_relative_path(raw: str) -> PurePosixPath:
    relative = PurePosixPath(raw)
    if (
        not raw
        or "\\" in raw
        or relative.is_absolute()
        or ".." in relative.parts
        or not relative.name
    ):
        raise AnchoredWriteError(f"unsafe anchored relative path: {raw!r}")
    return relative


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute():
        raise AnchoredWriteError(f"anchor must be absolute: {path}")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _open_relative_directory(root_fd: int, parts: Sequence[str]) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.dup(root_fd)
    try:
        for part in parts:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _read_from_root(root_fd: int, relative: PurePosixPath) -> str | None:
    parent_fd = _open_relative_directory(root_fd, relative.parts[:-1])
    try:
        return _read_regular_text(parent_fd, relative.name)
    finally:
        os.close(parent_fd)


def _read_regular_text(parent_fd: int, filename: str) -> str | None:
    text, _mode = _read_regular_text_with_mode(parent_fd, filename)
    return text


def _read_regular_text_with_mode(
    parent_fd: int, filename: str
) -> tuple[str | None, int | None]:
    flags = os.O_RDONLY | os.O_NOFOLLOW
    try:
        descriptor = os.open(filename, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        return None, None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AnchoredWriteError(f"target is not a regular file: {filename}")
        data = bytearray()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            data.extend(chunk)
        try:
            return data.decode("utf-8"), stat.S_IMODE(metadata.st_mode)
        except UnicodeDecodeError as exc:
            raise AnchoredWriteError(f"target is not UTF-8: {filename}") from exc
    finally:
        os.close(descriptor)


def _stage_text(parent_fd: int, filename: str, text: str, *, mode: int) -> str:
    temporary_name = f".{filename}.{secrets.token_hex(12)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    descriptor = os.open(temporary_name, flags, mode, dir_fd=parent_fd)
    try:
        os.fchmod(descriptor, mode)
        payload = text.encode("utf-8")
        cursor = 0
        while cursor < len(payload):
            cursor += os.write(descriptor, payload[cursor:])
        os.fsync(descriptor)
    except Exception:
        os.close(descriptor)
        _unlink_if_present(parent_fd, temporary_name)
        raise
    os.close(descriptor)
    return temporary_name


def _assert_parent_still_mapped(root_fd: int, item: _StagedChange) -> None:
    current_parent = _open_relative_directory(root_fd, item.parent_parts)
    try:
        staged_stat = os.fstat(item.parent_fd)
        current_stat = os.fstat(current_parent)
        if (staged_stat.st_dev, staged_stat.st_ino) != (
            current_stat.st_dev,
            current_stat.st_ino,
        ):
            raise AnchoredWriteError(
                f"target directory changed during apply: {item.change.relative_path}"
            )
    finally:
        os.close(current_parent)


def _assert_anchor_still_mapped(anchor: Path, root_fd: int) -> None:
    current_root = _open_absolute_directory(anchor)
    try:
        anchored_stat = os.fstat(root_fd)
        current_stat = os.fstat(current_root)
        if (anchored_stat.st_dev, anchored_stat.st_ino) != (
            current_stat.st_dev,
            current_stat.st_ino,
        ):
            raise AnchoredWriteError(
                f"transaction anchor changed during apply: {anchor}"
            )
    finally:
        os.close(current_root)


def _unlink_if_present(parent_fd: int, filename: str) -> None:
    try:
        os.unlink(filename, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise
