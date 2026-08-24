"""Secure runtime composition for the signed operator-control inbox."""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
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
SYSTEMD_CREDENTIALS_DIRECTORY_ENV = "CREDENTIALS_DIRECTORY"
OPERATOR_HMAC_CREDENTIAL_NAME = "control_hmac_key"
MAX_OPERATOR_HMAC_BYTES = 4096


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
    *,
    environ: Mapping[str, str] | None = None,
) -> bytes:
    values = os.environ if environ is None else environ
    directory_raw = values.get(SYSTEMD_CREDENTIALS_DIRECTORY_ENV, "")
    _need(
        isinstance(directory_raw, str) and bool(directory_raw),
        "operator HMAC credential is unavailable",
    )
    # Configuration selects systemd's directory, never a credential filename.
    credential_directory = _absolute_path(
        directory_raw, "systemd credentials directory"
    )
    candidate = credential_directory / OPERATOR_HMAC_CREDENTIAL_NAME
    parent, name = _open_parent(candidate)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    assert isinstance(nofollow, int) and nofollow != 0
    try:
        directory = os.fstat(parent)
        _need(
            stat.S_ISDIR(directory.st_mode)
            and directory.st_uid in {0, os.geteuid()}
            and stat.S_IMODE(directory.st_mode) in {0o500, 0o700},
            "operator HMAC credential directory custody is invalid",
        )
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
    return secret


def operator_control_reconciler_from_config(
    mission_id: str,
    *,
    normal_inbox: Path | str = DEFAULT_NORMAL_INBOX,
    inflight_inbox: Path | str = DEFAULT_INFLIGHT_INBOX,
    applied_inbox: Path | str = DEFAULT_APPLIED_INBOX,
    rejected_inbox: Path | str = DEFAULT_REJECTED_INBOX,
    credential_environ: Mapping[str, str] | None = None,
    max_candidates_per_cycle: int = 128,
) -> OperatorControlInboxReconciler | None:
    """Build the sole-writer inbox adapter or fail closed for SADHANA."""
    values = os.environ if credential_environ is None else credential_environ
    directory_raw = values.get(SYSTEMD_CREDENTIALS_DIRECTORY_ENV, "")
    configured = isinstance(directory_raw, str) and bool(directory_raw)
    if mission_id == SADHANA_OPERATOR_CAMPAIGN_ID and not configured:
        raise MissionControlError(
            "SADHANA run requires the systemd operator HMAC credential"
        )
    if not configured:
        _need(
            directory_raw is None or directory_raw == "",
            "operator HMAC credential is unavailable",
        )
        return None
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
    secret = load_operator_hmac_credential(environ=values)
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
    "OPERATOR_HMAC_CREDENTIAL_NAME",
    "SADHANA_OPERATOR_CAMPAIGN_ID",
    "SYSTEMD_CREDENTIALS_DIRECTORY_ENV",
    "load_operator_hmac_credential",
    "operator_control_reconciler_from_config",
]
