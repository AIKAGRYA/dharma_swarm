"""Secure stdlib-only reader for a derived, non-authoritative projection."""

from __future__ import annotations

import asyncio
import math
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from api.mission_snapshot_validation import (
    CAMPAIGN_PROJECTION_SCHEMA_VERSION as CAMPAIGN_PROJECTION_SCHEMA_VERSION,
    MissionSnapshotReadError,
    canonical_digest,
    validate_campaign_projection,
)

_canonical_digest = canonical_digest

MISSION_SNAPSHOT_PATH_ENV = "DHARMA_MISSION_SNAPSHOT_PATH"
MISSION_SNAPSHOT_MISSION_ID_ENV = "DHARMA_MISSION_SNAPSHOT_MISSION_ID"
MISSION_SNAPSHOT_CONFIG_DIGEST_ENV = "DHARMA_MISSION_SNAPSHOT_CONFIG_DIGEST"
MISSION_SNAPSHOT_MIN_GENERATION_ENV = "DHARMA_MISSION_SNAPSHOT_MIN_GENERATION"
MISSION_SNAPSHOT_MAX_AGE_ENV = "DHARMA_MISSION_SNAPSHOT_MAX_AGE_SECONDS"

_ENV_NAMES = (
    MISSION_SNAPSHOT_PATH_ENV,
    MISSION_SNAPSHOT_MISSION_ID_ENV,
    MISSION_SNAPSHOT_CONFIG_DIGEST_ENV,
    MISSION_SNAPSHOT_MIN_GENERATION_ENV,
    MISSION_SNAPSHOT_MAX_AGE_ENV,
)
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_MISSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")
_POSITIVE_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_MAX_PROJECTION_BYTES = 32 * 1024 * 1024
_MAX_CONFIGURED_AGE_SECONDS = 3600.0


class MissionSnapshotConfigurationError(ValueError):
    """The exact read-model source is absent or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class MissionSnapshotProviderConfig:
    path: Path
    mission_id: str
    config_digest: str
    minimum_generation: int
    max_age_seconds: float

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise MissionSnapshotConfigurationError(
                f"{MISSION_SNAPSHOT_PATH_ENV} must be an absolute path"
            )
        if not _MISSION_ID_RE.fullmatch(self.mission_id):
            raise MissionSnapshotConfigurationError(
                f"{MISSION_SNAPSHOT_MISSION_ID_ENV} must be a bounded identifier"
            )
        if not _SHA256_RE.fullmatch(self.config_digest):
            raise MissionSnapshotConfigurationError(
                f"{MISSION_SNAPSHOT_CONFIG_DIGEST_ENV} must be canonical sha256"
            )
        if (
            isinstance(self.minimum_generation, bool)
            or not isinstance(self.minimum_generation, int)
            or self.minimum_generation < 1
        ):
            raise MissionSnapshotConfigurationError(
                f"{MISSION_SNAPSHOT_MIN_GENERATION_ENV} must be a positive integer"
            )
        if (
            isinstance(self.max_age_seconds, bool)
            or not math.isfinite(self.max_age_seconds)
            or not 0 < self.max_age_seconds <= _MAX_CONFIGURED_AGE_SECONDS
        ):
            raise MissionSnapshotConfigurationError(
                f"{MISSION_SNAPSHOT_MAX_AGE_ENV} must be finite and from 0 to "
                f"{_MAX_CONFIGURED_AGE_SECONDS:g}"
            )


def _parse_positive_int(raw: str, name: str) -> int:
    if not raw or not raw.isascii() or not raw.isdecimal():
        raise MissionSnapshotConfigurationError(f"{name} must be a positive integer")
    value = int(raw, 10)
    if value < 1 or str(value) != raw:
        raise MissionSnapshotConfigurationError(f"{name} must be canonical")
    return value


def _parse_positive_float(raw: str, name: str) -> float:
    if not raw.isascii() or not _POSITIVE_DECIMAL_RE.fullmatch(raw):
        raise MissionSnapshotConfigurationError(
            f"{name} must be a canonical positive decimal"
        )
    try:
        value = float(raw)
    except ValueError as exc:
        raise MissionSnapshotConfigurationError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or not 0 < value <= _MAX_CONFIGURED_AGE_SECONDS:
        raise MissionSnapshotConfigurationError(
            f"{name} must be finite and from 0 to {_MAX_CONFIGURED_AGE_SECONDS:g}"
        )
    return value


def mission_snapshot_provider_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    now: Callable[[], datetime] | None = None,
) -> ImmutableCampaignSnapshotProvider | None:
    """Build the provider only from one complete, explicit environment binding."""
    source = os.environ if environ is None else environ
    values = {name: str(source.get(name, "")) for name in _ENV_NAMES}
    configured = {name for name, value in values.items() if value != ""}
    if not configured:
        return None
    if configured != set(_ENV_NAMES):
        missing = sorted(set(_ENV_NAMES) - configured)
        raise MissionSnapshotConfigurationError(
            "mission snapshot provider configuration is partial: " + ",".join(missing)
        )
    path_raw = values[MISSION_SNAPSHOT_PATH_ENV]
    if path_raw != path_raw.strip():
        raise MissionSnapshotConfigurationError(
            f"{MISSION_SNAPSHOT_PATH_ENV} must be exact"
        )
    config = MissionSnapshotProviderConfig(
        path=Path(path_raw),
        mission_id=values[MISSION_SNAPSHOT_MISSION_ID_ENV],
        config_digest=values[MISSION_SNAPSHOT_CONFIG_DIGEST_ENV],
        minimum_generation=_parse_positive_int(
            values[MISSION_SNAPSHOT_MIN_GENERATION_ENV],
            MISSION_SNAPSHOT_MIN_GENERATION_ENV,
        ),
        max_age_seconds=_parse_positive_float(
            values[MISSION_SNAPSHOT_MAX_AGE_ENV],
            MISSION_SNAPSHOT_MAX_AGE_ENV,
        ),
    )
    return ImmutableCampaignSnapshotProvider(config, now=now)


def _private_regular(identity: os.stat_result) -> bool:
    return (
        stat.S_ISREG(identity.st_mode)
        and identity.st_uid == os.geteuid()
        and stat.S_IMODE(identity.st_mode) == 0o600
        and identity.st_nlink == 1
        and 0 < identity.st_size <= _MAX_PROJECTION_BYTES
    )


def _file_identity(identity: os.stat_result) -> tuple[int, ...]:
    return (
        identity.st_dev,
        identity.st_ino,
        identity.st_uid,
        stat.S_IMODE(identity.st_mode),
        identity.st_nlink,
        identity.st_size,
        identity.st_mtime_ns,
        identity.st_ctime_ns,
    )


def _open_directory_chain(directory: Path) -> list[int]:
    if not directory.is_absolute():  # guarded by config; retain local proof
        raise MissionSnapshotReadError("campaign projection parent must be absolute")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise MissionSnapshotReadError("platform lacks no-follow file admission")
    directory_flags |= nofollow | getattr(os, "O_CLOEXEC", 0)
    descriptors: list[int] = []
    try:
        descriptors.append(os.open(directory.anchor, directory_flags))
        for part in directory.parts[1:]:
            descriptor = os.open(part, directory_flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            identity = os.fstat(descriptor)
            mode = stat.S_IMODE(identity.st_mode)
            sticky_root_directory = bool(
                identity.st_uid == 0 and identity.st_mode & stat.S_ISVTX
            )
            if (
                not stat.S_ISDIR(identity.st_mode)
                or identity.st_uid not in {0, os.geteuid()}
                or (mode & 0o022 and not sticky_root_directory)
            ):
                raise MissionSnapshotReadError(
                    "campaign projection directory lacks private custody"
                )
        return descriptors
    except MissionSnapshotReadError:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise
    except (OSError, ValueError) as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise MissionSnapshotReadError(
            "campaign projection directory cannot be opened securely"
        ) from exc


def _secure_read(path: Path) -> bytes:
    directory_descriptors = _open_directory_chain(path.parent)
    parent_descriptor = directory_descriptors[-1]
    descriptor: int | None = None
    try:
        try:
            entry = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
        except OSError as exc:
            raise MissionSnapshotReadError(
                "campaign projection entry cannot be inspected"
            ) from exc
        if not _private_regular(entry):
            raise MissionSnapshotReadError(
                "campaign projection is not a bounded private regular file"
            )

        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        before = os.fstat(descriptor)
        if not _private_regular(before) or (before.st_dev, before.st_ino) != (
            entry.st_dev,
            entry.st_ino,
        ):
            raise MissionSnapshotReadError(
                "campaign projection custody changed before read"
            )
        chunks: list[bytes] = []
        remaining = _MAX_PROJECTION_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if remaining == 0:
            raise MissionSnapshotReadError("campaign projection exceeds the read limit")
        after = os.fstat(descriptor)
        content = b"".join(chunks)
        if _file_identity(before) != _file_identity(after) or len(content) != after.st_size:
            raise MissionSnapshotReadError(
                "campaign projection changed during the admitted read"
            )
        return content
    except OSError as exc:
        raise MissionSnapshotReadError(
            "campaign projection cannot be opened securely"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for item in reversed(directory_descriptors):
            os.close(item)


class ImmutableCampaignSnapshotProvider:
    """Per-request verifier for one atomically replaced campaign read model."""

    # Deliberately not "immutable_copy": the existing dashboard interprets
    # that string as permission to open generic runtime databases whose session
    # domain cannot contain Orchestrator-owned campaign runs.
    runtime_projection_mode = "unavailable"
    mission_projection_mode = "immutable_campaign_json"

    def __init__(
        self,
        config: MissionSnapshotProviderConfig,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._highest_position = (0, 0)
        self._highest_snapshot_digest = ""
        self._lock = asyncio.Lock()

    async def admit(self) -> None:
        """Require one valid fresh projection before API startup may write."""
        snapshot = await self.get_snapshot(self.config.mission_id)
        if snapshot is None:  # pragma: no cover - exact ID supplied above
            raise MissionSnapshotReadError("campaign projection admission was empty")
        if self._highest_position[1] < 1:
            raise MissionSnapshotReadError(
                "campaign projection has no completed durable cycle"
            )

    async def get_snapshot(self, mission_id: str) -> dict[str, Any] | None:
        if mission_id != self.config.mission_id:
            return None
        async with self._lock:
            worker = asyncio.create_task(asyncio.to_thread(self._read_and_validate))
            try:
                admitted = await asyncio.shield(worker)
            except asyncio.CancelledError as cancellation:
                while not worker.done():
                    try:
                        await asyncio.shield(worker)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                raise cancellation
            snapshot, generation, sequence, snapshot_digest = admitted
            position = (generation, sequence)
            if position < self._highest_position:
                raise MissionSnapshotReadError(
                    "campaign projection position moved backwards"
                )
            if (
                position == self._highest_position
                and snapshot_digest != self._highest_snapshot_digest
            ):
                raise MissionSnapshotReadError(
                    "campaign projection equivocated at one cycle position"
                )
            if position > self._highest_position:
                self._highest_position = position
                self._highest_snapshot_digest = snapshot_digest
            return snapshot

    def _read_and_validate(self) -> tuple[dict[str, Any], int, int, str]:
        return self._validate(_secure_read(self.config.path))

    def _validate(self, content: bytes) -> tuple[dict[str, Any], int, int, str]:
        try:
            return validate_campaign_projection(
                content,
                mission_id=self.config.mission_id,
                config_digest=self.config.config_digest,
                minimum_generation=self.config.minimum_generation,
                max_age_seconds=self.config.max_age_seconds,
                now=self._now(),
            )
        except ValueError as exc:
            raise MissionSnapshotConfigurationError(str(exc)) from exc
