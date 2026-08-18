"""Strict credential-file loading for the sealed Grok OAuth adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
from typing import Any

MAX_AUTH_FILE_BYTES = 64 * 1024

AuthRejection = tuple[str, str]


def load_current_oauth_key(
    path: Path,
) -> tuple[str | None, AuthRejection | None]:
    """Read one unexpired access key from an owner-only regular file.

    The loader deliberately ignores refresh credentials and rejects ambiguous
    records, duplicate JSON keys, links, non-owner files, and oversized input.
    """

    missing = (
        "missing_oauth_auth",
        "Grok OAuth credentials are unavailable",
    )
    insecure = (
        "insecure_oauth_auth",
        "Grok OAuth credential file permissions are not secure",
    )
    malformed = (
        "malformed_oauth_auth",
        "Grok OAuth credential file is invalid",
    )

    try:
        metadata = path.lstat()
    except (FileNotFoundError, OSError):
        return None, missing
    if stat.S_ISLNK(metadata.st_mode):
        return None, insecure

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None, missing
    except OSError:
        return None, insecure

    try:
        opened_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_metadata.st_mode)
            or stat.S_IMODE(opened_metadata.st_mode) != 0o600
            or opened_metadata.st_uid != os.getuid()
            or opened_metadata.st_size > MAX_AUTH_FILE_BYTES
        ):
            return None, insecure
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            raw = stream.read(MAX_AUTH_FILE_BYTES + 1)
    except (OSError, UnicodeError):
        return None, malformed
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    if not raw or len(raw.encode("utf-8")) > MAX_AUTH_FILE_BYTES:
        return None, malformed
    try:
        data = json.loads(raw, object_pairs_hook=_unique_json_object)
    except (TypeError, ValueError):
        return None, malformed
    if not isinstance(data, dict):
        return None, malformed

    records: list[dict[str, Any]] = []
    if "key" in data or "expires_at" in data:
        records.append(data)
    records.extend(
        value
        for value in data.values()
        if isinstance(value, dict) and ("key" in value or "expires_at" in value)
    )
    if not records:
        return None, malformed
    if len(records) != 1:
        return None, (
            "ambiguous_oauth_auth",
            "Grok OAuth credential selection is ambiguous",
        )

    # Read only the access key and its expiry.  Refresh credentials never
    # cross this adapter boundary.
    record = records[0]
    key = record.get("key")
    expires_at = record.get("expires_at")
    if (
        not isinstance(key, str)
        or not key.strip()
        or len(key) > 16_384
        or "\r" in key
        or "\n" in key
        or not isinstance(expires_at, str)
        or not expires_at.strip()
        or len(expires_at) > 128
    ):
        return None, malformed
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None, malformed
    if expiry.tzinfo is None:
        return None, malformed
    if expiry.astimezone(timezone.utc) <= datetime.now(timezone.utc):
        return None, (
            "expired_oauth_auth",
            "Grok OAuth access credential is expired",
        )
    return key, None


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate Grok OAuth credential key")
        value[key] = item
    return value


__all__ = ["AuthRejection", "MAX_AUTH_FILE_BYTES", "load_current_oauth_key"]
