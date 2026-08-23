"""Fail-closed pre-dispatch activation from root-governed observer evidence.

Observer health is a deployment prerequisite only.  This module never turns it
into task, provider, verifier, acceptance, or useful-work evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_contract import MissionControlError


OBSERVER_HEALTH_SCHEMA_VERSION = "dharma.sadhana.observer_health_acceptance.v3"
OBSERVER_HEALTH_ENDPOINT = "http://127.0.0.1:18420/api/health"
OBSERVER_HEALTH_UNIT = "dharma-sadhana-api.service"
OBSERVER_HEALTH_SUCCESS_COUNT = 20
SADHANA_ACTIVATION_CAMPAIGN_ID = "sadhana-10-20260823"
MAX_OBSERVER_HEALTH_BYTES = 64 * 1024
_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RELEASE_RE = re.compile(r"[0-9a-f]{40}\Z")
_UTC_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "campaign_id",
        "release_sha",
        "service_unit_digest",
        "endpoint",
        "probe_started_at",
        "probe_finished_at",
        "consecutive_successes",
        "response_sha256_sequence",
        "listener_process_identity",
        "dispatch_enabled_during_probe",
        "observer_identity_separated",
        "projection_source_separated",
        "canonical_paths_inaccessible",
        "health_is_work_evidence",
        "verdict",
        "receipt_digest",
    }
)
_LISTENER_FIELDS = frozenset(
    {
        "unit",
        "main_pid",
        "proc_start_ticks",
        "cmdline_sha256",
        "socket_inode",
        "uid",
        "gid",
        "forbidden_path_count",
        "canonical_path_visible",
        "release_sha",
    }
)


@dataclass(frozen=True, slots=True)
class ObserverHealthAcceptance:
    campaign_id: str
    release_sha: str
    service_unit_digest: str
    listener_main_pid: int
    listener_proc_start_ticks: int
    listener_socket_inode: int
    receipt_digest: str
    file_sha256: str
    path: Path


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        _need(key not in payload, f"observer health receipt duplicates {key!r}")
        payload[key] = value
    return payload


def _canonical_bytes(payload: Any, *, newline: bool) -> bytes:
    try:
        encoded = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise MissionControlError("observer health receipt is not canonical JSON") from exc
    return encoded + (b"\n" if newline else b"")


def _open_parent(path: Path) -> tuple[int, str]:
    _need(path.is_absolute() and path.name not in {"", ".", ".."},
          "observer health receipt path must be an absolute leaf")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    _need(nofollow is not None and directory is not None,
          "observer health custody requires O_NOFOLLOW and O_DIRECTORY")
    flags = os.O_RDONLY | nofollow | directory
    descriptor = os.open(os.path.sep, flags)
    try:
        for component in path.parent.parts[1:]:
            _need(component not in {"", ".", ".."},
                  "observer health receipt path component is invalid")
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, path.name
    except BaseException:
        os.close(descriptor)
        raise


def _read_exact(path: Path) -> bytes:
    parent, name = _open_parent(path)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    assert nofollow is not None
    try:
        descriptor = os.open(name, os.O_RDONLY | nofollow, dir_fd=parent)
    except OSError as exc:
        os.close(parent)
        raise MissionControlError("observer health receipt could not be opened") from exc
    try:
        before = os.fstat(descriptor)
        mode = stat.S_IMODE(before.st_mode)
        _need(
            stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1
            and before.st_uid in {0, os.geteuid()}
            and mode & 0o022 == 0
            and 0 < before.st_size <= MAX_OBSERVER_HEALTH_BYTES,
            "observer health credential custody is invalid",
        )
        raw = b""
        while len(raw) <= MAX_OBSERVER_HEALTH_BYTES:
            chunk = os.read(descriptor, min(65_536, MAX_OBSERVER_HEALTH_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
        os.close(parent)
    identity = lambda item: (  # noqa: E731
        item.st_dev,
        item.st_ino,
        item.st_uid,
        item.st_gid,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    _need(identity(before) == identity(after) and len(raw) == before.st_size,
          "observer health credential changed while read")
    return raw


def _positive_int(value: Any, label: str) -> int:
    _need(type(value) is int and value > 0, f"{label} must be a positive integer")
    return value


def _utc(value: Any, label: str) -> datetime:
    _need(type(value) is str and _UTC_RE.fullmatch(value) is not None,
          f"{label} must be canonical UTC-Z")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_observer_health_acceptance(
    path: Path | str,
    *,
    expected_file_sha256: str,
    expected_campaign_id: str,
) -> ObserverHealthAcceptance:
    """Validate one exact LoadCredential materialization without any mutation."""
    _need(_RAW_SHA256_RE.fullmatch(expected_file_sha256) is not None,
          "observer health credential SHA-256 must be raw lowercase hex")
    candidate = Path(path).expanduser().absolute()
    raw = _read_exact(candidate)
    observed_file_sha256 = hashlib.sha256(raw).hexdigest()
    _need(observed_file_sha256 == expected_file_sha256,
          "observer health credential file digest conflicts")
    try:
        payload = json.loads(raw.decode("ascii"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MissionControlError("observer health credential is not strict JSON") from exc
    _need(type(payload) is dict and set(payload) == _ROOT_FIELDS,
          "observer health receipt fields are not exact")
    _need(raw == _canonical_bytes(payload, newline=True),
          "observer health receipt bytes are not canonical")
    release_sha = payload["release_sha"]
    unit_digest = payload["service_unit_digest"]
    responses = payload["response_sha256_sequence"]
    listener = payload["listener_process_identity"]
    _need(
        payload["schema_version"] == OBSERVER_HEALTH_SCHEMA_VERSION
        and payload["campaign_id"] == expected_campaign_id
        and isinstance(release_sha, str)
        and _RELEASE_RE.fullmatch(release_sha) is not None
        and isinstance(unit_digest, str)
        and _RAW_SHA256_RE.fullmatch(unit_digest) is not None
        and payload["endpoint"] == OBSERVER_HEALTH_ENDPOINT
        and payload["consecutive_successes"] == OBSERVER_HEALTH_SUCCESS_COUNT
        and type(payload["consecutive_successes"]) is int
        and type(responses) is list
        and len(responses) == OBSERVER_HEALTH_SUCCESS_COUNT
        and all(type(item) is str and _RAW_SHA256_RE.fullmatch(item) for item in responses)
        and payload["dispatch_enabled_during_probe"] is False
        and payload["observer_identity_separated"] is True
        and payload["projection_source_separated"] is True
        and payload["canonical_paths_inaccessible"] is True
        and payload["health_is_work_evidence"] is False
        and payload["verdict"] == "PASS",
        "observer health acceptance claims conflict",
    )
    started = _utc(payload["probe_started_at"], "probe_started_at")
    finished = _utc(payload["probe_finished_at"], "probe_finished_at")
    _need(started <= finished, "observer health probe clock moved backwards")
    _need(type(listener) is dict and set(listener) == _LISTENER_FIELDS,
          "observer listener identity fields are not exact")
    _need(
        listener["unit"] == OBSERVER_HEALTH_UNIT
        and listener["release_sha"] == release_sha
        and type(listener["cmdline_sha256"]) is str
        and _RAW_SHA256_RE.fullmatch(listener["cmdline_sha256"]) is not None
        and _positive_int(listener["main_pid"], "listener main_pid") > 0
        and _positive_int(listener["proc_start_ticks"], "listener start ticks") > 0
        and _positive_int(listener["socket_inode"], "listener socket inode") > 0
        and _positive_int(listener["uid"], "listener uid") > 0
        and _positive_int(listener["gid"], "listener gid") > 0
        and listener["forbidden_path_count"] == 9
        and type(listener["forbidden_path_count"]) is int
        and listener["canonical_path_visible"] is False,
        "observer listener identity conflicts",
    )
    receipt_digest = payload["receipt_digest"]
    _need(type(receipt_digest) is str and _SHA256_RE.fullmatch(receipt_digest) is not None,
          "observer health receipt digest must be sha256")
    canonical = dict(payload)
    canonical.pop("receipt_digest")
    expected_receipt_digest = "sha256:" + hashlib.sha256(
        _canonical_bytes(canonical, newline=False)
    ).hexdigest()
    _need(receipt_digest == expected_receipt_digest,
          "observer health receipt self-digest conflicts")
    return ObserverHealthAcceptance(
        campaign_id=expected_campaign_id,
        release_sha=release_sha,
        service_unit_digest=unit_digest,
        listener_main_pid=listener["main_pid"],
        listener_proc_start_ticks=listener["proc_start_ticks"],
        listener_socket_inode=listener["socket_inode"],
        receipt_digest=receipt_digest,
        file_sha256=observed_file_sha256,
        path=candidate,
    )


class ObserverHealthActivationBarrier:
    """Revalidate the immutable credential before every owner cycle."""

    def __init__(
        self,
        path: Path | str,
        *,
        expected_file_sha256: str,
        expected_campaign_id: str,
    ) -> None:
        self._path = Path(path)
        self._expected_file_sha256 = expected_file_sha256
        self._expected_campaign_id = expected_campaign_id

    def preflight(self) -> ObserverHealthAcceptance:
        return load_observer_health_acceptance(
            self._path,
            expected_file_sha256=self._expected_file_sha256,
            expected_campaign_id=self._expected_campaign_id,
        )

    async def __call__(self) -> None:
        self.preflight()


def activation_barrier_from_config(
    mission_id: str,
    path: Path | str | None,
    expected_file_sha256: str,
) -> ObserverHealthActivationBarrier | None:
    """Require both root-provided credential pins for the production campaign."""
    path_text = str(path or "")
    digest = str(expected_file_sha256 or "")
    configured = bool(path_text), bool(digest)
    if mission_id == SADHANA_ACTIVATION_CAMPAIGN_ID and configured != (True, True):
        raise MissionControlError(
            "SADHANA run requires the exact observer health receipt and SHA-256"
        )
    if configured == (False, False):
        return None
    _need(configured == (True, True),
          "observer health activation configuration is partial")
    barrier = ObserverHealthActivationBarrier(
        Path(path_text).expanduser().absolute(),
        expected_file_sha256=digest,
        expected_campaign_id=mission_id,
    )
    barrier.preflight()
    return barrier


__all__ = [
    "MAX_OBSERVER_HEALTH_BYTES",
    "OBSERVER_HEALTH_ENDPOINT",
    "OBSERVER_HEALTH_SCHEMA_VERSION",
    "OBSERVER_HEALTH_SUCCESS_COUNT",
    "OBSERVER_HEALTH_UNIT",
    "ObserverHealthAcceptance",
    "ObserverHealthActivationBarrier",
    "SADHANA_ACTIVATION_CAMPAIGN_ID",
    "activation_barrier_from_config",
    "load_observer_health_acceptance",
]
