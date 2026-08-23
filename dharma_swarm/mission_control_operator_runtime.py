"""Secure runtime composition for the signed operator-control inbox."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import stat
from pathlib import Path

from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_operator_control import (
    DEFAULT_APPLIED_INBOX,
    DEFAULT_INFLIGHT_INBOX,
    DEFAULT_NORMAL_INBOX,
    DEFAULT_REJECTED_INBOX,
    OperatorControlInboxReconciler,
)

SADHANA_OPERATOR_CAMPAIGN_ID = "sadhana-10-20260823"
MAX_OPERATOR_HMAC_BYTES = 4096
_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _absolute_path(value: Path | str, label: str) -> Path:
    path = Path(value).expanduser()
    _need(
        path.is_absolute()
        and path.name not in {"", ".", ".."}
        and ".." not in path.parts,
        f"{label} must be an absolute non-traversing path",
    )
    return path


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    _need(
        isinstance(nofollow, int)
        and nofollow != 0
        and isinstance(directory, int)
        and directory != 0,
        "operator credential custody requires O_NOFOLLOW and O_DIRECTORY",
    )
    return os.O_RDONLY | nofollow | directory | getattr(os, "O_CLOEXEC", 0)


def _open_parent(path: Path) -> tuple[int, str]:
    flags = _directory_flags()
    descriptor = os.open(os.path.sep, flags)
    try:
        for component in path.parent.parts[1:]:
            _need(
                component not in {"", ".", ".."},
                "operator credential path component is invalid",
            )
            child = os.open(component, flags, dir_fd=descriptor)
            details = os.fstat(child)
            _need(
                stat.S_ISDIR(details.st_mode),
                "operator credential ancestor is not a directory",
            )
            os.close(descriptor)
            descriptor = child
        return descriptor, path.name
    except OSError as exc:
        os.close(descriptor)
        raise MissionControlError(
            "operator HMAC credential parent could not be opened exactly"
        ) from exc
    except BaseException:
        os.close(descriptor)
        raise


def _file_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        value.st_gid,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def load_operator_hmac_credential(
    path: Path | str,
    *,
    expected_file_sha256: str,
) -> bytes:
    """Read one hash-pinned systemd credential without following path links."""
    candidate = _absolute_path(path, "operator HMAC credential")
    _need(
        isinstance(expected_file_sha256, str)
        and _RAW_SHA256_RE.fullmatch(expected_file_sha256) is not None,
        "operator HMAC credential SHA-256 must be raw lowercase hex",
    )
    parent, name = _open_parent(candidate)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    assert isinstance(nofollow, int) and nofollow != 0
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent,
        )
    except OSError as exc:
        os.close(parent)
        raise MissionControlError(
            "operator HMAC credential could not be opened exactly"
        ) from exc
    try:
        before = os.fstat(descriptor)
        _need(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(before.st_mode) in {0o400, 0o600}
            and 32 <= before.st_size <= MAX_OPERATOR_HMAC_BYTES,
            "operator HMAC credential custody is invalid",
        )
        chunks: list[bytes] = []
        remaining = MAX_OPERATOR_HMAC_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(4096, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        secret = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
        os.close(parent)
    _need(
        _file_identity(before) == _file_identity(after)
        and len(secret) == before.st_size,
        "operator HMAC credential changed while read",
    )
    _need(
        b"\r" not in secret
        and b"\n" not in secret
        and 32 <= len(secret) <= MAX_OPERATOR_HMAC_BYTES,
        "operator HMAC credential byte contract is invalid",
    )
    observed = hashlib.sha256(secret).hexdigest()
    _need(
        hmac.compare_digest(observed, expected_file_sha256),
        "operator HMAC credential SHA-256 conflicts",
    )
    return secret


def operator_control_reconciler_from_config(
    mission_id: str,
    *,
    normal_inbox: Path | str = DEFAULT_NORMAL_INBOX,
    inflight_inbox: Path | str = DEFAULT_INFLIGHT_INBOX,
    applied_inbox: Path | str = DEFAULT_APPLIED_INBOX,
    rejected_inbox: Path | str = DEFAULT_REJECTED_INBOX,
    hmac_credential_path: Path | str | None,
    hmac_credential_sha256: str,
    max_candidates_per_cycle: int = 128,
) -> OperatorControlInboxReconciler | None:
    """Build the sole-writer inbox adapter or fail closed for SADHANA."""
    path_text = str(hmac_credential_path or "")
    digest = str(hmac_credential_sha256 or "")
    configured = bool(path_text), bool(digest)
    if mission_id == SADHANA_OPERATOR_CAMPAIGN_ID and configured != (True, True):
        raise MissionControlError(
            "SADHANA run requires the exact operator HMAC credential and SHA-256"
        )
    if configured == (False, False):
        return None
    _need(
        configured == (True, True),
        "operator HMAC credential configuration is partial",
    )
    roots = tuple(
        _absolute_path(value, label)
        for value, label in (
            (normal_inbox, "operator normal inbox"),
            (inflight_inbox, "operator inflight inbox"),
            (applied_inbox, "operator applied inbox"),
            (rejected_inbox, "operator rejected inbox"),
        )
    )
    _need(len(set(roots)) == 4, "operator control inbox roots must be distinct")
    secret = load_operator_hmac_credential(
        path_text,
        expected_file_sha256=digest,
    )
    return OperatorControlInboxReconciler(
        normal_inbox=roots[0],
        inflight_inbox=roots[1],
        applied_inbox=roots[2],
        rejected_inbox=roots[3],
        secret=secret,
        max_candidates_per_cycle=max_candidates_per_cycle,
    )


__all__ = [
    "MAX_OPERATOR_HMAC_BYTES",
    "SADHANA_OPERATOR_CAMPAIGN_ID",
    "load_operator_hmac_credential",
    "operator_control_reconciler_from_config",
]
