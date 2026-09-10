"""Strict durable-transcript evidence reading for route verification.

Extracted from ``terminal_bridge_route_truth`` so the mixin owns route
semantics while this module owns tamper-evident transcript acquisition.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

from dharma_swarm.tui.engine.events import (
    CanonicalEventType,
    EVENT_TYPES,
    SCHEMA_VERSION,
)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in pairs:
        if key in decoded:
            raise ValueError(f"duplicate JSON key: {key}")
        decoded[key] = value
    return decoded


def _reject_non_finite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def read_durable_transcript(
    store_root: object,
    session_id: str,
) -> tuple[bytes | None, str | None, str | None]:
    """Read and hash one root-confined regular transcript from one file handle."""

    if (
        not session_id
        or session_id in {".", ".."}
        or "/" in session_id
        or "\\" in session_id
    ):
        return None, None, None
    try:
        store_root = Path(str(store_root)).resolve()
        session_path = store_root / session_id
        if session_path.is_symlink():
            return None, None, None
        session_dir = session_path.resolve(strict=True)
        transcript_path = session_dir / "transcript.jsonl"
        if transcript_path.is_symlink():
            return None, None, None
        resolved_transcript = transcript_path.resolve(strict=True)
    except OSError:
        return None, None, None
    if (
        session_dir.parent != store_root
        or session_dir.name != session_id
        or resolved_transcript.parent != session_dir
    ):
        return None, None, None

    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(transcript_path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            return None, None, None
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    except OSError:
        return None, None, None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    transcript_bytes = b"".join(chunks)
    if identity_before != identity_after or len(transcript_bytes) != after.st_size:
        return None, None, None
    try:
        if (
            transcript_path.is_symlink()
            or transcript_path.resolve(strict=True) != resolved_transcript
        ):
            return None, None, None
    except OSError:
        return None, None, None
    return (
        transcript_bytes,
        str(resolved_transcript),
        hashlib.sha256(transcript_bytes).hexdigest(),
    )


def strict_transcript_from_bytes(
    transcript_bytes: bytes,
    *,
    session_id: str,
) -> list[CanonicalEventType] | None:
    """Decode every persisted byte; malformed or skipped rows reject the receipt."""

    if not transcript_bytes or not transcript_bytes.endswith(b"\n"):
        return None
    try:
        decoded = transcript_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None

    transcript: list[CanonicalEventType] = []
    for raw_line in decoded.splitlines():
        if not raw_line.strip():
            return None
        try:
            payload = json.loads(
                raw_line,
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_reject_non_finite_json_constant,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        event_type = payload.get("type")
        if not isinstance(event_type, str):
            return None
        event_cls = EVENT_TYPES.get(event_type)
        if event_cls is None:
            return None
        try:
            event = event_cls(**payload)
        except (TypeError, ValueError):
            return None
        if (
            event.schema_version != SCHEMA_VERSION
            or event.session_id != session_id
            or event.raw is not None
            or asdict(event) != payload
        ):
            return None
        transcript.append(event)
    return transcript
