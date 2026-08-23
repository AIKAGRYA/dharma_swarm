"""Typed request/terminal membrane for the external held-out oracle worker."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import stat
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol


ORACLE_LAUNCH_REQUEST_SCHEMA = "dharma.sadhana.oracle_launch_request.v1"
ORACLE_LAUNCH_TERMINAL_SCHEMA = "dharma.sadhana.oracle_launch_terminal.v1"
ZERO_SHA256 = "sha256:" + "0" * 64
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RAW_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_FAILURE_CODE_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,127}\Z")
_TERMINAL_KEYS = frozenset(
    {
        "schema_version",
        "request_id",
        "request_digest",
        "status",
        "verdict_payload",
        "verdict_sha256",
        "sandbox_evidence_sha256",
        "completed_at",
        "failure_code",
        "terminal_digest",
    }
)
_MAX_PROTOCOL_BYTES = 1_048_576


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


class OracleLauncherError(ValueError):
    """The external oracle request/terminal filesystem membrane is invalid."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise OracleLauncherError(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _need(key not in result, f"oracle protocol duplicates key {key!r}")
        result[key] = value
    return result


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    _need(
        nofollow is not None and directory is not None,
        "oracle launcher custody requires O_NOFOLLOW and O_DIRECTORY",
    )
    return os.O_RDONLY | nofollow | directory


def _open_directory(path: Path, *, owner_uid: int, group_gid: int, mode: int) -> int:
    _need(path.is_absolute(), "oracle protocol root must be absolute")
    flags = _directory_flags()
    descriptor = os.open(os.path.sep, flags)
    try:
        for component in path.parts[1:]:
            _need(component not in {"", ".", ".."}, "oracle protocol path is invalid")
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        details = os.fstat(descriptor)
        _need(
            stat.S_ISDIR(details.st_mode)
            and details.st_uid == owner_uid
            and details.st_gid == group_gid
            and stat.S_IMODE(details.st_mode) == mode,
            "oracle protocol root custody is invalid",
        )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _identity(value: os.stat_result) -> tuple[int, ...]:
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


def _read_file(
    directory: int,
    name: str,
    *,
    owner_uid: int,
    group_gid: int,
    label: str,
) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    _need(nofollow is not None, "oracle launcher custody requires O_NOFOLLOW")
    try:
        descriptor = os.open(name, os.O_RDONLY | nofollow, dir_fd=directory)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise OracleLauncherError(f"{label} could not be opened exactly") from exc
    try:
        before = os.fstat(descriptor)
        _need(
            stat.S_ISREG(before.st_mode)
            and before.st_uid == owner_uid
            and before.st_gid == group_gid
            and stat.S_IMODE(before.st_mode) == 0o600
            and before.st_nlink == 1
            and 0 < before.st_size <= _MAX_PROTOCOL_BYTES,
            f"{label} custody is invalid",
        )
        remaining = _MAX_PROTOCOL_BYTES + 1
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _need(_identity(before) == _identity(after), f"{label} changed while read")
    _need(len(raw) == before.st_size, f"{label} read was incomplete")
    return raw


def _publish_request(directory: int, name: str, raw: bytes) -> None:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    _need(nofollow is not None, "oracle launcher custody requires O_NOFOLLOW")
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
            dir_fd=directory,
        )
    except FileExistsError:
        existing = _read_file(
            directory,
            name,
            owner_uid=os.geteuid(),
            group_gid=os.getegid(),
            label="oracle launch request",
        )
        _need(existing == raw, "oracle launch request replay conflicts")
        return
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            _need(written > 0, "oracle launch request write failed")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory)


def _decode_terminal(raw: bytes, *, path: Path) -> OracleLaunchTerminal:
    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OracleLauncherError("oracle launch terminal is not strict UTF-8 JSON") from exc
    _need(type(payload) is dict, "oracle launch terminal must be an object")
    _need(set(payload) == _TERMINAL_KEYS, "oracle launch terminal fields conflict")
    _need(raw == _canonical_bytes(payload), "oracle launch terminal is not canonical")
    unsigned = dict(payload)
    terminal_digest = unsigned.pop("terminal_digest")
    _need(terminal_digest == _digest(unsigned), "oracle launch terminal digest conflicts")
    try:
        completed_at = datetime.fromisoformat(payload["completed_at"])
    except (TypeError, ValueError) as exc:
        raise OracleLauncherError("oracle launch terminal time is invalid") from exc
    terminal = OracleLaunchTerminal(
        request_id=payload["request_id"],
        request_digest=payload["request_digest"],
        status=payload["status"],
        verdict_payload=payload["verdict_payload"],
        verdict_sha256=payload["verdict_sha256"],
        sandbox_evidence_sha256=payload["sandbox_evidence_sha256"],
        completed_at=completed_at,
        terminal_path=path,
        terminal_digest=terminal_digest,
        failure_code=payload["failure_code"],
    )
    return terminal


@dataclass(frozen=True, slots=True)
class OracleLaunchRequest:
    campaign_id: str
    mission_id: str
    goal_id: str
    task_id: str
    verifier_run_id: str
    idempotency_key: str
    manifest_digest: str
    evaluator_path: Path
    evaluator_sha256: str
    policy_path: Path
    policy_sha256: str
    input_path: Path
    input_sha256: str
    sandbox_evidence_sha256: str

    @property
    def request_id(self) -> str:
        return hashlib.sha256(self.idempotency_key.encode("utf-8")).hexdigest()

    def as_payload(self) -> dict[str, Any]:
        payload = {
            "schema_version": ORACLE_LAUNCH_REQUEST_SCHEMA,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "campaign_id": self.campaign_id,
            "mission_id": self.mission_id,
            "goal_id": self.goal_id,
            "task_id": self.task_id,
            "verifier_run_id": self.verifier_run_id,
            "manifest_digest": self.manifest_digest,
            "evaluator_path": str(self.evaluator_path),
            "evaluator_sha256": self.evaluator_sha256,
            "policy_path": str(self.policy_path),
            "policy_sha256": self.policy_sha256,
            "input_path": str(self.input_path),
            "input_sha256": self.input_sha256,
            "sandbox_evidence_sha256": self.sandbox_evidence_sha256,
        }
        payload["request_digest"] = _digest(payload)
        return payload

    def validate(self) -> None:
        payload = self.as_payload()
        if (
            _RAW_SHA256_RE.fullmatch(payload["request_id"]) is None
            or not all(
                _SHA256_RE.fullmatch(value) is not None
                for value in (
                    self.manifest_digest,
                    self.evaluator_sha256,
                    self.policy_sha256,
                    self.input_sha256,
                    self.sandbox_evidence_sha256,
                    payload["request_digest"],
                )
            )
            or not all(
                path.is_absolute()
                for path in (self.evaluator_path, self.policy_path, self.input_path)
            )
        ):
            raise ValueError("oracle launch request coordinates are invalid")


@dataclass(frozen=True, slots=True)
class OracleLaunchTerminal:
    request_id: str
    request_digest: str
    status: str
    verdict_payload: dict[str, Any] | None
    verdict_sha256: str
    sandbox_evidence_sha256: str
    completed_at: datetime
    terminal_path: Path
    terminal_digest: str
    failure_code: str = ""

    def validate_for(self, request: OracleLaunchRequest) -> None:
        expected = request.as_payload()
        if (
            not all(
                isinstance(value, str)
                for value in (
                    self.request_id,
                    self.request_digest,
                    self.status,
                    self.verdict_sha256,
                    self.sandbox_evidence_sha256,
                    self.terminal_digest,
                    self.failure_code,
                )
            )
            or self.request_id != request.request_id
            or self.request_digest != expected["request_digest"]
            or self.status not in {"completed", "failed"}
            or self.sandbox_evidence_sha256 != request.sandbox_evidence_sha256
            or self.completed_at.tzinfo is None
            or not self.terminal_path.is_absolute()
            or _SHA256_RE.fullmatch(self.terminal_digest) is None
        ):
            raise ValueError("oracle launch terminal coordinates conflict")
        if self.status == "completed":
            if (
                type(self.verdict_payload) is not dict
                or self.verdict_sha256 != _digest(self.verdict_payload)
                or self.failure_code
            ):
                raise ValueError("completed oracle launch terminal is malformed")
        elif (
            self.verdict_payload is not None
            or self.verdict_sha256 != ZERO_SHA256
            or _FAILURE_CODE_RE.fullmatch(self.failure_code) is None
        ):
            raise ValueError("failed oracle launch terminal is malformed")


class OracleSandboxLauncher(Protocol):
    """Publish/poll a request serviced only by an enforced external worker."""

    @property
    def sandbox_evidence_sha256(self) -> str: ...

    async def launch(self, request: OracleLaunchRequest) -> OracleLaunchTerminal: ...


class FilesystemOracleSandboxLauncher:
    """Publish one exact request and poll a root-finalized immutable terminal."""

    def __init__(
        self,
        *,
        sandbox_evidence_sha256: str,
        request_root: Path | str = "/run/dharma-sadhana/oracle/requests",
        terminal_root: Path | str = "/run/dharma-sadhana/oracle/terminals",
        timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 0.25,
        request_owner_uid: int | None = None,
        request_group_gid: int | None = None,
        terminal_root_owner_uid: int = 0,
        terminal_root_group_gid: int | None = None,
        terminal_owner_uid: int | None = None,
        terminal_group_gid: int | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        _need(
            _SHA256_RE.fullmatch(sandbox_evidence_sha256) is not None,
            "oracle sandbox evidence digest is invalid",
        )
        _need(
            type(timeout_seconds) in {int, float}
            and math.isfinite(timeout_seconds)
            and timeout_seconds > 0,
            "oracle launcher timeout must be positive and finite",
        )
        _need(
            type(poll_interval_seconds) in {int, float}
            and math.isfinite(poll_interval_seconds)
            and 0 < poll_interval_seconds <= timeout_seconds,
            "oracle launcher poll interval is invalid",
        )
        self._sandbox_evidence_sha256 = sandbox_evidence_sha256
        self._request_root = Path(request_root)
        self._terminal_root = Path(terminal_root)
        _need(
            self._request_root != self._terminal_root,
            "oracle request and terminal roots must differ",
        )
        current_uid = os.geteuid()
        current_gid = os.getegid()
        self._request_owner_uid = current_uid if request_owner_uid is None else request_owner_uid
        self._request_group_gid = current_gid if request_group_gid is None else request_group_gid
        self._terminal_root_owner_uid = terminal_root_owner_uid
        self._terminal_root_group_gid = (
            current_gid if terminal_root_group_gid is None else terminal_root_group_gid
        )
        self._terminal_owner_uid = current_uid if terminal_owner_uid is None else terminal_owner_uid
        self._terminal_group_gid = current_gid if terminal_group_gid is None else terminal_group_gid
        self._timeout_seconds = float(timeout_seconds)
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._monotonic = monotonic
        self._sleep = sleep

    @property
    def sandbox_evidence_sha256(self) -> str:
        return self._sandbox_evidence_sha256

    def preflight(self) -> None:
        """Validate both immutable directory custody boundaries without publishing."""
        request_directory = _open_directory(
            self._request_root,
            owner_uid=self._request_owner_uid,
            group_gid=self._request_group_gid,
            mode=0o700,
        )
        os.close(request_directory)
        terminal_directory = _open_directory(
            self._terminal_root,
            owner_uid=self._terminal_root_owner_uid,
            group_gid=self._terminal_root_group_gid,
            mode=0o750,
        )
        os.close(terminal_directory)

    async def launch(self, request: OracleLaunchRequest) -> OracleLaunchTerminal:
        request.validate()
        _need(
            request.sandbox_evidence_sha256 == self._sandbox_evidence_sha256,
            "oracle request conflicts with launcher sandbox evidence",
        )
        request_payload = request.as_payload()
        request_raw = _canonical_bytes(request_payload)
        request_name = f"{request.request_id}.oracle.json"
        terminal_name = f"{request.request_id}.terminal.json"
        request_directory = _open_directory(
            self._request_root,
            owner_uid=self._request_owner_uid,
            group_gid=self._request_group_gid,
            mode=0o700,
        )
        try:
            _publish_request(request_directory, request_name, request_raw)
        finally:
            os.close(request_directory)

        terminal_directory = _open_directory(
            self._terminal_root,
            owner_uid=self._terminal_root_owner_uid,
            group_gid=self._terminal_root_group_gid,
            mode=0o750,
        )
        terminal_path = self._terminal_root / terminal_name
        deadline = self._monotonic() + self._timeout_seconds
        try:
            while True:
                try:
                    raw = _read_file(
                        terminal_directory,
                        terminal_name,
                        owner_uid=self._terminal_owner_uid,
                        group_gid=self._terminal_group_gid,
                        label="oracle launch terminal",
                    )
                except FileNotFoundError:
                    remaining = deadline - self._monotonic()
                    if remaining <= 0:
                        raise TimeoutError("oracle launch terminal was not published")
                    await self._sleep(min(self._poll_interval_seconds, remaining))
                    continue
                terminal = _decode_terminal(raw, path=terminal_path)
                terminal.validate_for(request)
                return terminal
        finally:
            os.close(terminal_directory)


__all__ = [
    "ORACLE_LAUNCH_REQUEST_SCHEMA",
    "ORACLE_LAUNCH_TERMINAL_SCHEMA",
    "FilesystemOracleSandboxLauncher",
    "OracleLaunchRequest",
    "OracleLaunchTerminal",
    "OracleLauncherError",
    "OracleSandboxLauncher",
    "ZERO_SHA256",
]
