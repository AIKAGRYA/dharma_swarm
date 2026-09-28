"""Single-use provenance for immutable Mission Control owner snapshots."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.mission_control_effect_owner import inspect_owner_stores
from dharma_swarm.mission_control_effect_records import OwnerStoreBinding


_CAPABILITY_SECRET = secrets.token_bytes(32)
_CAPABILITIES: dict[str, "_ImmutableSnapshotCapability"] = {}


def _snapshot_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for suffix in ("", "-wal", "-shm", "-journal"):
        candidate = Path(f"{path}{suffix}")
        try:
            info = candidate.stat(follow_symlinks=False)
        except FileNotFoundError:
            digest.update(f"{suffix}:absent".encode("utf-8"))
            continue
        digest.update(
            f"{suffix}:{info.st_dev}:{info.st_ino}:{info.st_size}".encode("utf-8")
        )
        with candidate.open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block)
    return digest.hexdigest()


def _capability_payload(
    source_owners: OwnerStoreBinding,
    destination_owners: OwnerStoreBinding,
    runtime_sha256: str,
    task_sha256: str,
    nonce: str,
) -> bytes:
    return json.dumps(
        {
            "source": source_owners.to_dict(),
            "destination": destination_owners.to_dict(),
            "runtime_sha256": runtime_sha256,
            "task_sha256": task_sha256,
            "nonce": nonce,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True, init=False)
class _ImmutableSnapshotCapability:
    """Unconstructable, process-local capability minted after an exact copy."""

    source_owners: OwnerStoreBinding
    destination_owners: OwnerStoreBinding
    runtime_sha256: str
    task_sha256: str
    nonce: str
    seal: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "immutable snapshot capabilities are minted only by "
            "_copy_immutable_owner_pair"
        )


@dataclass(frozen=True, slots=True)
class _ImmutableSnapshotProvenance:
    """Validated immutable-copy provenance retained by one MissionControl."""

    source_owners: OwnerStoreBinding
    destination_owners: OwnerStoreBinding
    runtime_sha256: str
    task_sha256: str

    def require_intact(
        self, runtime_destination: Path, task_destination: Path
    ) -> OwnerStoreBinding:
        destination = inspect_owner_stores(runtime_destination, task_destination)
        if destination != self.destination_owners:
            raise ValueError("immutable snapshot destination identity drifted")
        if (
            _snapshot_sha256(runtime_destination) != self.runtime_sha256
            or _snapshot_sha256(task_destination) != self.task_sha256
        ):
            raise ValueError("immutable snapshot destination mutated after copy")
        source = inspect_owner_stores(
            Path(self.source_owners.runtime_database_path),
            Path(self.source_owners.task_database_path),
        )
        if source != self.source_owners:
            raise ValueError("immutable snapshot source identity drifted")
        return source

    def require_source_intact(self) -> OwnerStoreBinding:
        source = inspect_owner_stores(
            Path(self.source_owners.runtime_database_path),
            Path(self.source_owners.task_database_path),
        )
        if source != self.source_owners:
            raise ValueError("immutable snapshot source identity drifted")
        return source


def _mint_immutable_snapshot_capability(
    source_owners: OwnerStoreBinding,
    runtime_destination: Path,
    task_destination: Path,
) -> _ImmutableSnapshotCapability:
    """Capture the exact copy destination before exposing a snapshot control."""

    destination_owners = inspect_owner_stores(runtime_destination, task_destination)
    runtime_sha256 = _snapshot_sha256(runtime_destination)
    task_sha256 = _snapshot_sha256(task_destination)
    nonce = secrets.token_hex(32)
    seal = hmac.new(
        _CAPABILITY_SECRET,
        _capability_payload(
            source_owners,
            destination_owners,
            runtime_sha256,
            task_sha256,
            nonce,
        ),
        hashlib.sha256,
    ).hexdigest()
    capability = object.__new__(_ImmutableSnapshotCapability)
    object.__setattr__(capability, "source_owners", source_owners)
    object.__setattr__(capability, "destination_owners", destination_owners)
    object.__setattr__(capability, "runtime_sha256", runtime_sha256)
    object.__setattr__(capability, "task_sha256", task_sha256)
    object.__setattr__(capability, "nonce", nonce)
    object.__setattr__(capability, "seal", seal)
    _CAPABILITIES[nonce] = capability
    return capability


def _consume_immutable_snapshot_capability(
    capability: object,
    runtime_destination: Path,
    task_destination: Path,
) -> _ImmutableSnapshotProvenance:
    """Consume one exact capability after rechecking source and destination."""

    if type(capability) is not _ImmutableSnapshotCapability:
        raise ValueError("immutable snapshot capability is malformed")
    issued = _CAPABILITIES.pop(capability.nonce, None)
    if issued is not capability:
        raise ValueError("immutable snapshot capability was not freshly minted")
    expected_seal = hmac.new(
        _CAPABILITY_SECRET,
        _capability_payload(
            capability.source_owners,
            capability.destination_owners,
            capability.runtime_sha256,
            capability.task_sha256,
            capability.nonce,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(capability.seal, expected_seal):
        raise ValueError("immutable snapshot capability seal is invalid")
    provenance = _ImmutableSnapshotProvenance(
        capability.source_owners,
        capability.destination_owners,
        capability.runtime_sha256,
        capability.task_sha256,
    )
    provenance.require_intact(runtime_destination, task_destination)
    return provenance
