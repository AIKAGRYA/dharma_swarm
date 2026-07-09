"""Atomic file writes -- crash-safe replacement for truncate-in-place.

A plain ``path.write_text(...)`` / ``open(path, "w")`` truncates the target
before the new bytes are durable. A crash (or a full disk) mid-write leaves
a half-written or empty file where valid state used to live. These helpers
write to a temp file in the SAME directory, fsync it, then ``os.replace`` it
over the target -- an atomic rename on POSIX -- so a reader ever sees either
the old complete file or the new complete file, never a torn one.

Modeled on the correct pattern in ``dharma_swarm/cron_scheduler.py`` save_jobs.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


def write_text_atomic(path: str | Path, text: str) -> None:
    """Atomically write *text* to *path*.

    Writes to a temp file in the target's directory, flushes and fsyncs it,
    then ``os.replace``s it over the target. The temp file is unlinked and
    the exception re-raised if any step fails, so the pre-existing target is
    left intact. Best-effort ``chmod 0600`` on the final file.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent), suffix=".tmp", prefix=f".{target.name}_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
        try:
            os.chmod(target, 0o600)
        except (OSError, NotImplementedError):
            pass
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_json_atomic(
    path: str | Path,
    obj: Any,
    *,
    indent: int = 2,
    default: Callable[[Any], Any] | None = None,
) -> None:
    """Atomically write *obj* as JSON to *path*.

    Serializes *obj* fully in memory before touching the filesystem, so a
    serialization error never truncates the target. *default* is passed
    through to :func:`json.dumps` for non-native types (e.g. ``str``).
    """
    text = json.dumps(obj, indent=indent, default=default)
    write_text_atomic(path, text)
