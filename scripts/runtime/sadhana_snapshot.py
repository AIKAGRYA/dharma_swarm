#!/usr/bin/env python3
"""Consistent SADHANA SQLite snapshot and one-way fenced-standby replication."""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import pwd
import re
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

MISSION_ID = "sadhana-10-20260823"
CAMPAIGN_START_UTC = datetime(2026, 8, 22, 17, 15, 12, tzinfo=timezone.utc)
CAMPAIGN_STOP_UTC = datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc)
STATE_ROOT = Path("/var/lib/dharma-sadhana/state")
PROJECTION_SOURCE_ROOT = Path("/var/lib/dharma-sadhana/projection-source")
SNAPSHOT_ROOT = Path("/var/lib/dharma-sadhana/snapshots")
SNAPSHOT_STAGING_ROOT = Path("/var/lib/dharma-sadhana/snapshot-staging")
SNAPSHOT_FINALIZING_ROOT = Path("/var/lib/dharma-sadhana/snapshot-finalizing")
SNAPSHOT_INCOMING_ROOT = Path("/var/lib/dharma-sadhana/snapshot-incoming")
SNAPSHOT_UPLOAD_ROOT = SNAPSHOT_INCOMING_ROOT / "uploads"
SNAPSHOT_ACK_ROOT = SNAPSHOT_INCOMING_ROOT / "acks"
SNAPSHOT_RECEIVER_CLAIM_ROOT = Path("/var/lib/dharma-sadhana/snapshot-receiver-claims")
SNAPSHOT_QUARANTINE_ROOT = Path("/var/lib/dharma-sadhana/snapshot-quarantine")
SNAPSHOT_RECEIPT_ROOT = Path("/var/lib/dharma-sadhana/snapshot-receipts")
SNAPSHOT_OUTBOX_ROOT = Path("/var/lib/dharma-sadhana/snapshot-outbox")
STANDBY_DESTINATION = "dharma-sadhana@100.79.111.89"
STANDBY_PORT = 2222
STANDBY_RRSYNC_ROOT = "/var/lib/dharma-sadhana/snapshot-incoming"
STANDBY_ROOT = "/var/lib/dharma-sadhana/snapshot-incoming/uploads"
STANDBY_UPLOAD_RELATIVE_ROOT = "uploads"
STANDBY_ACK_RELATIVE_ROOT = "acks"
KNOWN_HOSTS = Path("/etc/dharma-sadhana/known_hosts")
READINESS_RECEIPT_NAME = "snapshot-readiness.v1.json"
SNAPSHOT_INTERVAL_SECONDS = 5 * 60
MAX_CAMPAIGN_SNAPSHOTS = 2_880
MIN_FREE_RESERVE_BYTES = 8 * 1024 * 1024 * 1024
SNAPSHOT_ESTIMATE_HEADROOM_NUMERATOR = 5
SNAPSHOT_ESTIMATE_HEADROOM_DENOMINATOR = 4
SNAPSHOT_METADATA_ALLOWANCE_BYTES = 1024 * 1024
RSYNC_PATH = "/usr/bin/rsync"
SSH_PATH = "/usr/bin/ssh"
STANDBY_SSH_OPTIONS = (
    "BatchMode=yes",
    "StrictHostKeyChecking=yes",
    "IdentitiesOnly=yes",
    "PasswordAuthentication=no",
    "KbdInteractiveAuthentication=no",
    "PreferredAuthentications=publickey",
    "PubkeyAuthentication=yes",
    "NumberOfPasswordPrompts=0",
    "RequestTTY=no",
    "ConnectTimeout=10",
    "HostKeyAlgorithms=ssh-ed25519",
)
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_SAFE_ABSOLUTE_PATH_RE = re.compile(r"/[A-Za-z0-9_./-]+")
_SNAPSHOT_STAMP_PATTERN = r"[0-9]{8}T[0-9]{6}Z"
_SNAPSHOT_RELEASE_PREFIX_PATTERN = r"[0-9a-f]{12}"
_SNAPSHOT_ID_PATTERN = (
    rf"{_SNAPSHOT_STAMP_PATTERN}-{_SNAPSHOT_RELEASE_PREFIX_PATTERN}"
)
_SNAPSHOT_DIR_RE = re.compile(
    rf"(?P<stamp>{_SNAPSHOT_STAMP_PATTERN})-"
    rf"(?P<release_prefix>{_SNAPSHOT_RELEASE_PREFIX_PATTERN})"
)
_UPLOAD_DIR_RE = re.compile(
    rf"(?P<snapshot>{_SNAPSHOT_ID_PATTERN})\.upload-"
    r"(?P<digest>[0-9a-f]{64})"
)
_LOCAL_CLAIM_RE = re.compile(
    rf"(?P<snapshot>{_SNAPSHOT_ID_PATTERN})\.claim-[0-9a-f]{{16}}"
)
_UPLOAD_CLAIM_RE = re.compile(
    rf"(?P<upload>{_UPLOAD_DIR_RE.pattern})\.claim-[0-9a-f]{{16}}"
)
_UNSAFE_INCOMING_CLAIM_RE = re.compile(
    rf"(?P<upload>{_UPLOAD_DIR_RE.pattern})\.unsafe-[0-9a-f]{{16}}"
)
_QUARANTINE_SCOPE_RE = re.compile(r"(?:local|standby|incoming)")
_QUARANTINE_REASON_RE = re.compile(r"[a-z][a-z0-9-]{1,63}")
_QUARANTINE_ENTRY_RE = re.compile(
    r"(?P<source>.+)\.quarantine-(?P<scope>local|standby|incoming)-"
    r"(?P<reason>[a-z][a-z0-9-]{1,63})-(?P<token>[0-9a-f]{16})"
)
_OUTBOX_ENTRY_RE = re.compile(
    rf"(?P<snapshot>{_SNAPSHOT_ID_PATTERN})\.outbox\.v1\.json"
)
SNAPSHOT_FILE_NAMES = frozenset(
    {"runtime.db", "tasks.db", "status.json", "snapshot-manifest.json"}
)
SNAPSHOT_SCHEMA_VERSION = "dharma.sadhana.snapshot.v2"
CONSISTENCY_SCHEMA_VERSION = "dharma.sadhana.stable_source_window.v1"
SEMANTIC_PROOF_SCHEMA_VERSION = "dharma.sadhana.snapshot_semantics.v1"
CAMPAIGN_PROJECTION_SCHEMA_VERSION = "dharma.mission_control.read_model.v1"
CAMPAIGN_SESSION_SCHEMA_VERSION = "dharma.mission_control.campaign.v1"
CAMPAIGN_PROJECTION_FIELDS = frozenset(
    {
        "mission_id",
        "session_id",
        "config_digest",
        "generation",
        "cycle_sequence",
        "freshness_seconds",
        "mission_snapshot",
        "owner_executions",
        "campaign_status",
        "supervisor_state",
        "writer_lock_held",
        "latest_cycle_at",
        "transport_state",
        "model_execution_state",
        "acceptance_state",
        "candidate_task_ids",
        "accepted_task_ids",
        "rejected_task_ids",
        "conflicting_acceptance_task_ids",
        "canary_acceptance",
        "invalid_acceptance_receipts",
        "operator_control_state",
        "errors",
        "observed_at",
        "authority",
        "proves_process_liveness",
        "proves_model_execution",
        "proves_semantic_acceptance",
        "projection_schema_version",
        "projection_kind",
        "canonical_state_copied",
        "published_at",
        "fresh_until",
        "projection_content_digest",
    }
)


class SnapshotError(RuntimeError):
    """Snapshot or one-way replication failed closed."""


def standby_ssh_transport(
    *,
    ssh_key: Path,
    known_hosts: Path,
    standby_port: int = STANDBY_PORT,
) -> str:
    """Return the shell-inert, key-only transport pinned to tailnet TCP 2222."""
    if standby_port != STANDBY_PORT:
        raise SnapshotError("standby SSH port differs from the pinned Serve route")
    for path, field in ((ssh_key, "ssh_key"), (known_hosts, "known_hosts")):
        if not path.is_absolute() or not _SAFE_ABSOLUTE_PATH_RE.fullmatch(str(path)):
            raise SnapshotError(f"{field} must be a shell-inert absolute path")
    fragments = [SSH_PATH, "-p", str(STANDBY_PORT), "-i", str(ssh_key)]
    for option in STANDBY_SSH_OPTIONS:
        fragments.extend(("-o", option))
    fragments.extend(("-o", f"UserKnownHostsFile={known_hosts}"))
    return " ".join(fragments)


def standby_ssh_policy_digest() -> str:
    """Bind receipts to the exact noninteractive public-key transport policy."""
    policy = {
        "destination": STANDBY_DESTINATION,
        "port": STANDBY_PORT,
        "ssh_path": SSH_PATH,
        "options": [*STANDBY_SSH_OPTIONS, "UserKnownHostsFile=<pinned>"],
    }
    return hashlib.sha256(_canonical_bytes(policy)).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise SnapshotError("snapshot JSON contains a duplicate key")
        payload[key] = value
    return payload


def _rename_noreplace(
    source_name: str,
    destination_name: str,
    *,
    source_dir_fd: int,
    destination_dir_fd: int,
) -> None:
    """Atomically rename one directory entry without replacement on Linux."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        if sys.platform == "linux":
            raise SnapshotError("renameat2 no-replace is unavailable")
        # Test/development hosts without renameat2 never activate the Linux units.
        try:
            os.stat(
                destination_name,
                dir_fd=destination_dir_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise SnapshotError("snapshot no-replace destination exists")
        os.rename(
            source_name,
            destination_name,
            src_dir_fd=source_dir_fd,
            dst_dir_fd=destination_dir_fd,
        )
        return
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if (
        renameat2(
            source_dir_fd,
            os.fsencode(source_name),
            destination_dir_fd,
            os.fsencode(destination_name),
            1,  # RENAME_NOREPLACE
        )
        != 0
    ):
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise SnapshotError("snapshot no-replace destination exists")
        raise SnapshotError("snapshot no-replace rename failed")


def _guard_campaign_timebox(observed: datetime) -> datetime:
    if observed.tzinfo is None:
        raise SnapshotError("snapshot clock must be timezone-aware")
    admitted = observed.astimezone(timezone.utc)
    if admitted < CAMPAIGN_START_UTC or admitted >= CAMPAIGN_STOP_UTC:
        raise SnapshotError("snapshot invocation is outside the exact campaign timebox")
    return admitted


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise SnapshotError("snapshot write made no progress")
        remaining = remaining[written:]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _require_regular(path: Path, *, private: bool = True) -> os.stat_result:
    try:
        identity = path.lstat()
    except OSError as exc:
        raise SnapshotError(f"snapshot input is unavailable: {path.name}") from exc
    mode = stat.S_IMODE(identity.st_mode)
    if (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or identity.st_nlink != 1
        or identity.st_uid not in {0, os.geteuid()}
        or (private and mode & 0o077)
        or (not private and mode & 0o022)
    ):
        raise SnapshotError(f"snapshot input lacks required custody: {path.name}")
    return identity


def _require_service_input(path: Path) -> os.stat_result:
    identity = _require_regular(path, private=False)
    mode = stat.S_IMODE(identity.st_mode)
    owned_private = identity.st_uid == os.geteuid() and mode == 0o600
    group_scoped = (
        identity.st_uid == 0 and identity.st_gid == os.getegid() and mode == 0o640
    )
    if not (owned_private or group_scoped):
        raise SnapshotError(f"service input lacks scoped custody: {path.name}")
    return identity


def _require_no_symlink_chain(path: Path) -> None:
    if not path.is_absolute():
        raise SnapshotError("snapshot path must be absolute")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            identity = current.lstat()
        except OSError as exc:
            raise SnapshotError("snapshot path chain is unavailable") from exc
        if current.is_symlink():
            raise SnapshotError(f"snapshot path chain contains symlink: {current.name}")
        if current != path and not stat.S_ISDIR(identity.st_mode):
            raise SnapshotError("snapshot parent chain contains a non-directory")


def _require_within(path: Path, root: Path, field: str) -> Path:
    _require_no_symlink_chain(root)
    _require_no_symlink_chain(path)
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise SnapshotError(f"{field} escapes the admitted root") from exc
    return resolved


def _sqlite_source_identity(
    path: Path,
    descriptor: int,
) -> dict[str, int]:
    admitted = _require_regular(path, private=False)
    opened = os.fstat(descriptor)
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_nlink")
    if tuple(getattr(opened, field) for field in fields) != tuple(
        getattr(admitted, field) for field in fields
    ):
        raise SnapshotError(f"SQLite source identity changed: {path.name}")
    return {
        "dev": opened.st_dev,
        "ino": opened.st_ino,
        "size": opened.st_size,
        "mtime_ns": opened.st_mtime_ns,
    }


def _open_sqlite_witness(
    source: Path,
) -> tuple[sqlite3.Connection, int, dict[str, int], int]:
    _require_no_symlink_chain(source)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_NOFOLLOW", 0):
        raise SnapshotError("platform lacks no-follow SQLite admission")
    descriptor = os.open(source, flags)
    try:
        identity = _sqlite_source_identity(source, descriptor)
        source_uri = f"file:{quote(str(source), safe='/')}?mode=ro"
        connection = sqlite3.connect(source_uri, uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            connected_identity = _sqlite_source_identity(source, descriptor)
            if connected_identity != identity:
                raise SnapshotError(f"SQLite source raced during open: {source.name}")
            version = _read_sqlite_data_version(
                connection,
                source_name=source.name,
            )
            return connection, descriptor, identity, version
        except BaseException:
            connection.close()
            raise
    except BaseException:
        os.close(descriptor)
        raise


def _read_sqlite_data_version(
    connection: sqlite3.Connection,
    *,
    source_name: str,
) -> int:
    try:
        row = connection.execute("PRAGMA data_version").fetchone()
    except sqlite3.Error as exc:
        raise SnapshotError(
            f"SQLite data-version could not be read: {source_name}"
        ) from exc
    if (
        row is None
        or len(row) != 1
        or isinstance(row[0], bool)
        or not isinstance(row[0], int)
        or row[0] < 1
    ):
        raise SnapshotError(f"SQLite data-version is invalid: {source_name}")
    return row[0]


def _backup_sqlite_connection(
    reader: sqlite3.Connection,
    destination: Path,
    *,
    source_name: str,
) -> None:
    try:
        with sqlite3.connect(destination) as writer:
            reader.backup(writer)
            journal_mode = writer.execute("PRAGMA journal_mode=DELETE").fetchone()
            if journal_mode is None or str(journal_mode[0]).lower() != "delete":
                raise SnapshotError(
                    f"SQLite backup journal normalization failed: {source_name}"
                )
            result = writer.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise SnapshotError(f"SQLite backup integrity failed: {source_name}")
    except sqlite3.Error as exc:
        raise SnapshotError(f"SQLite online backup failed: {source_name}") from exc
    os.chmod(destination, 0o600)


def _projection_witness(source: Path) -> tuple[bytes, dict[str, int | str]]:
    original = _require_regular(source, private=True)
    if original.st_size > 32 * 1024 * 1024:
        raise SnapshotError("projection exceeds the canonical size bound")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if not getattr(os, "O_NOFOLLOW", 0):
        raise SnapshotError("platform lacks no-follow projection admission")
    descriptor = os.open(source, flags)
    try:
        before = os.fstat(descriptor)
        raw = b""
        while len(raw) <= 32 * 1024 * 1024:
            chunk = os.read(descriptor, min(65_536, 32 * 1024 * 1024 + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    current = source.lstat()
    identity = (
        original.st_dev,
        original.st_ino,
        original.st_size,
        original.st_mtime_ns,
        original.st_nlink,
    )
    if (
        len(raw) > 32 * 1024 * 1024
        or identity
        != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_nlink,
        )
        or identity
        != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_nlink,
        )
        or identity
        != (
            current.st_dev,
            current.st_ino,
            current.st_size,
            current.st_mtime_ns,
            current.st_nlink,
        )
    ):
        raise SnapshotError("projection changed during stable read")
    return raw, {
        "dev": original.st_dev,
        "ino": original.st_ino,
        "size": original.st_size,
        "mtime_ns": original.st_mtime_ns,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _write_projection_copy(raw: bytes, destination: Path) -> None:
    output = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(output, raw)
        os.fsync(output)
    finally:
        os.close(output)


async def _canonical_owner_snapshot(
    runtime_db: Path,
    tasks_db: Path,
    *,
    observed_at: datetime,
) -> dict[str, Any] | None:
    from dharma_swarm.mission_control import MissionControl
    from dharma_swarm.mission_control_evidence import json_value
    from dharma_swarm.runtime_state import RuntimeStateStore
    from dharma_swarm.task_board import TaskBoard
    import dharma_swarm.mission_control as mission_control_module

    runtime = RuntimeStateStore(runtime_db, include_memory_plane=False)
    async def _read_only_init() -> None:
        return None

    runtime.init_db = _read_only_init  # type: ignore[method-assign]
    board = TaskBoard(tasks_db, runtime_state=runtime)
    control = MissionControl(board, runtime)
    original_clock = mission_control_module.utc_now
    mission_control_module.utc_now = lambda: observed_at
    try:
        result = await control.get_snapshot(MISSION_ID)
    finally:
        mission_control_module.utc_now = original_clock
    return None if result is None else json_value(result)


def _projection_payload(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("snapshot projection is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise SnapshotError("snapshot projection must be an object")
    try:
        canonical = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii") + b"\n"
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SnapshotError("snapshot projection is not canonical JSON") from exc
    if raw != canonical:
        raise SnapshotError("snapshot projection bytes are not canonical")
    unsigned = dict(payload)
    supplied_digest = unsigned.pop("projection_content_digest", None)
    expected_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            unsigned,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    if (
        set(payload) != CAMPAIGN_PROJECTION_FIELDS
        or payload.get("projection_schema_version")
        != CAMPAIGN_PROJECTION_SCHEMA_VERSION
        or payload.get("projection_kind") != "derived_read_model"
        or payload.get("canonical_state_copied") is not False
        or supplied_digest != expected_digest
    ):
        raise SnapshotError("snapshot projection schema or content digest differs")
    return payload, raw


def _validate_cross_store_semantics(
    runtime_db: Path,
    tasks_db: Path,
    projection_path: Path,
) -> dict[str, Any]:
    projection, _raw = _projection_payload(projection_path)
    mission_snapshot = projection.get("mission_snapshot")
    if not isinstance(mission_snapshot, dict):
        raise SnapshotError("projection mission snapshot is absent")
    if mission_snapshot.get("reconciliation") != "coherent":
        raise SnapshotError("snapshot reconciliation is not coherent")
    observed_raw = mission_snapshot.get("observed_at")
    try:
        observed_at = datetime.fromisoformat(str(observed_raw))
    except ValueError as exc:
        raise SnapshotError("projection mission observation time differs") from exc
    if observed_at.tzinfo is None:
        raise SnapshotError("projection mission observation time is naive")
    observed_at = observed_at.astimezone(timezone.utc)
    try:
        canonical_snapshot = asyncio.run(
            _canonical_owner_snapshot(
                runtime_db,
                tasks_db,
                observed_at=observed_at,
            )
        )
    except (
        OSError,
        sqlite3.Error,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        raise SnapshotError("canonical owner snapshot could not be rebuilt") from exc
    if canonical_snapshot is None or canonical_snapshot != mission_snapshot:
        raise SnapshotError("projection differs from canonical owner state")
    campaign_session_id = f"mission_campaign:{MISSION_ID}"
    try:
        with sqlite3.connect(f"file:{quote(str(runtime_db), safe='/')}?mode=ro", uri=True) as db:
            row = db.execute(
                "SELECT status, metadata_json FROM sessions WHERE session_id = ?",
                (campaign_session_id,),
            ).fetchone()
            if row is None:
                raise SnapshotError("campaign session is absent from runtime state")
            metadata = json.loads(row[1], object_pairs_hook=_strict_object)
            if not isinstance(metadata, dict):
                raise SnapshotError("campaign session metadata differs")
            generation = metadata.get("generation")
            sequence = metadata.get("last_cycle_sequence")
            config_digest = metadata.get("config_digest")
            if (
                metadata.get("schema_version") != CAMPAIGN_SESSION_SCHEMA_VERSION
                or metadata.get("mission_id") != MISSION_ID
                or projection.get("mission_id") != MISSION_ID
                or projection.get("session_id") != campaign_session_id
                or projection.get("campaign_status") != row[0]
                or projection.get("config_digest") != config_digest
                or projection.get("generation") != generation
                or projection.get("cycle_sequence") != sequence
                or not isinstance(config_digest, str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", config_digest)
                or isinstance(generation, bool)
                or not isinstance(generation, int)
                or generation < 1
                or isinstance(sequence, bool)
                or not isinstance(sequence, int)
                or sequence < 0
            ):
                raise SnapshotError("campaign projection coordinates differ")
            if sequence == 0:
                if (
                    metadata.get("last_cycle_receipt_id") != ""
                    or projection.get("latest_cycle_at") is not None
                ):
                    raise SnapshotError("zero-cycle projection evidence differs")
            else:
                cycle = db.execute(
                    "SELECT receipt_type, correlation_id, payload_json, created_at "
                    "FROM runtime_receipts WHERE receipt_id = ?",
                    (metadata.get("last_cycle_receipt_id"),),
                ).fetchone()
                if cycle is None:
                    raise SnapshotError("latest campaign cycle receipt is absent")
                cycle_payload = json.loads(
                    cycle[2], object_pairs_hook=_strict_object
                )
                if (
                    not isinstance(cycle_payload, dict)
                    or cycle[0] != "mission_campaign_cycle"
                    or cycle[1] != campaign_session_id
                    or cycle_payload.get("schema_version")
                    != CAMPAIGN_SESSION_SCHEMA_VERSION
                    or cycle_payload.get("mission_id") != MISSION_ID
                    or cycle_payload.get("generation") != generation
                    or cycle_payload.get("sequence") != sequence
                    or projection.get("latest_cycle_at") != cycle[3]
                ):
                    raise SnapshotError("latest campaign cycle binding differs")
    except (sqlite3.Error, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("campaign runtime state is invalid") from exc
    return {
        "schema_version": SEMANTIC_PROOF_SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "session_id": campaign_session_id,
        "config_digest": config_digest,
        "generation": generation,
        "cycle_sequence": sequence,
        "projection_schema_valid": True,
        "projection_content_digest_valid": True,
        "canonical_owner_projection_match": True,
        "cross_store_semantics_valid": True,
        "reconciliation_state": "coherent",
        "reconciliation_policy": "reject_noncoherent",
    }


def _manifest_payload(
    *,
    release_sha: str,
    generated_at: datetime,
    snapshot_id: str,
    files: dict[str, str],
    consistency_proof: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "release_sha": release_sha,
        "snapshot_id": snapshot_id,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "source_role": "writer",
        "destination_role": "fenced_standby",
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
        "files": files,
        "consistency_proof": consistency_proof,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    payload["snapshot_digest"] = hashlib.sha256(encoded).hexdigest()
    return payload


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("ascii")


def _write_readiness_receipt(snapshot_root: Path, payload: dict[str, Any]) -> Path:
    receipt = snapshot_root / READINESS_RECEIPT_NAME
    payload = dict(payload)
    payload["receipt_digest"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    raw = _canonical_bytes(payload) + b"\n"
    if receipt.exists() or receipt.is_symlink():
        identity = receipt.lstat()
        if (
            not stat.S_ISREG(identity.st_mode)
            or receipt.is_symlink()
            or identity.st_uid != os.geteuid()
            or stat.S_IMODE(identity.st_mode) != 0o600
            or identity.st_nlink != 1
        ):
            raise SnapshotError("snapshot readiness receipt custody differs")
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{READINESS_RECEIPT_NAME}.", dir=snapshot_root
    )
    temporary = Path(temporary_raw)
    try:
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, receipt)
        directory_descriptor = os.open(
            snapshot_root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    return receipt


def snapshot_capacity_formula(
    *,
    source_bytes: int,
    existing_snapshot_count: int,
    free_bytes: int,
) -> dict[str, int | str]:
    """Return the single campaign-wide immutable-series capacity formula."""
    for value, field in (
        (source_bytes, "source_bytes"),
        (existing_snapshot_count, "existing_snapshot_count"),
        (free_bytes, "free_bytes"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise SnapshotError(f"{field} must be a nonnegative integer")
    if existing_snapshot_count > MAX_CAMPAIGN_SNAPSHOTS:
        remaining = 0
    else:
        remaining = MAX_CAMPAIGN_SNAPSHOTS - existing_snapshot_count
    estimate_unrounded = (
        (source_bytes + SNAPSHOT_METADATA_ALLOWANCE_BYTES)
        * SNAPSHOT_ESTIMATE_HEADROOM_NUMERATOR
        // SNAPSHOT_ESTIMATE_HEADROOM_DENOMINATOR
    )
    estimate_per_snapshot = (
        (estimate_unrounded + 1024 * 1024 - 1) // (1024 * 1024)
    ) * (1024 * 1024)
    required_free_bytes = MIN_FREE_RESERVE_BYTES + estimate_per_snapshot * remaining
    return {
        "status": (
            "ready"
            if remaining > 0 and free_bytes >= required_free_bytes
            else "snapshot_blocked"
        ),
        "remaining_snapshot_count": remaining,
        "estimated_bytes_per_snapshot": estimate_per_snapshot,
        "required_free_bytes_for_remaining_series": required_free_bytes,
    }


def _snapshot_capacity_admission(
    *,
    state_root: Path,
    projection_path: Path,
    snapshot_root: Path,
    readiness_root: Path,
    observed_at: datetime,
    statvfs: Callable[[Path], os.statvfs_result] = os.statvfs,
) -> dict[str, Any]:
    """Fail before staging unless the remaining immutable series fits with reserve."""
    inputs = (
        state_root / "state/runtime.db",
        state_root / "db/tasks.db",
        projection_path,
    )
    source_bytes = 0
    for path in inputs:
        source_bytes += _require_regular(path, private=path == projection_path).st_size
    existing = 0
    for child in snapshot_root.iterdir():
        if child.name.startswith(".snapshot-"):
            raise SnapshotError("stale snapshot staging directory requires review")
        if child.is_dir():
            if child.is_symlink() or not _SNAPSHOT_DIR_RE.fullmatch(child.name):
                raise SnapshotError("snapshot root contains an unknown directory")
            existing += 1
    fs = statvfs(snapshot_root)
    free_bytes = fs.f_bavail * fs.f_frsize
    capacity = snapshot_capacity_formula(
        source_bytes=source_bytes,
        existing_snapshot_count=existing,
        free_bytes=free_bytes,
    )
    payload: dict[str, Any] = {
        "schema_version": "dharma.sadhana.snapshot_capacity_readiness.v1",
        "mission_id": MISSION_ID,
        "observed_at": observed_at.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "status": capacity["status"],
        "existing_snapshot_count": existing,
        "maximum_campaign_snapshot_count": MAX_CAMPAIGN_SNAPSHOTS,
        "remaining_snapshot_count": capacity["remaining_snapshot_count"],
        "snapshot_interval_seconds": SNAPSHOT_INTERVAL_SECONDS,
        "source_bytes": source_bytes,
        "estimated_bytes_per_snapshot": capacity["estimated_bytes_per_snapshot"],
        "free_bytes": free_bytes,
        "minimum_free_reserve_bytes": MIN_FREE_RESERVE_BYTES,
        "required_free_bytes_for_remaining_series": capacity[
            "required_free_bytes_for_remaining_series"
        ],
        "silent_deletion_allowed": False,
        "standby_capacity_proven": False,
        "receipt_digest": "",
    }
    payload_without_digest = dict(payload)
    payload_without_digest.pop("receipt_digest")
    payload["receipt_digest"] = hashlib.sha256(
        _canonical_bytes(payload_without_digest)
    ).hexdigest()
    _write_readiness_receipt(readiness_root, payload_without_digest)
    if capacity["status"] != "ready":
        raise SnapshotError(
            "snapshot capacity is blocked before staging; inspect readiness receipt"
        )
    return payload


def create_snapshot(
    *,
    release_sha: str,
    state_root: Path,
    projection_path: Path,
    snapshot_root: Path,
    staging_root: Path | None = None,
    now: datetime | None = None,
    statvfs: Callable[[Path], os.statvfs_result] = os.statvfs,
) -> Path:
    """Create two online SQLite backups plus an exact immutable projection."""
    if not _COMMIT_RE.fullmatch(release_sha):
        raise SnapshotError("release SHA must be exact")
    admitted_staging_root = staging_root or SNAPSHOT_STAGING_ROOT
    if (
        state_root != STATE_ROOT
        or snapshot_root != SNAPSHOT_ROOT
        or admitted_staging_root != SNAPSHOT_STAGING_ROOT
    ):
        raise SnapshotError("snapshot roots differ from the campaign contract")
    observed = _guard_campaign_timebox(now or datetime.now(timezone.utc)).replace(
        microsecond=0
    )
    _require_within(projection_path, PROJECTION_SOURCE_ROOT, "projection_path")
    snapshot_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    admitted_staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _require_no_symlink_chain(snapshot_root)
    _require_no_symlink_chain(admitted_staging_root)
    if snapshot_root.is_symlink() or admitted_staging_root.is_symlink():
        raise SnapshotError("snapshot roots cannot be symlinks")
    lock_path = admitted_staging_root / ".snapshot.lock"
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SnapshotError("another snapshot already holds the fence") from exc
        _snapshot_capacity_admission(
            state_root=state_root,
            projection_path=projection_path,
            snapshot_root=snapshot_root,
            readiness_root=admitted_staging_root,
            observed_at=observed,
            statvfs=statvfs,
        )
        stamp = observed.strftime("%Y%m%dT%H%M%SZ")
        snapshot_id = f"{stamp}-{release_sha[:12]}"
        candidate = admitted_staging_root / snapshot_id
        if candidate.exists() or candidate.is_symlink():
            raise SnapshotError("snapshot identity already exists")
        staging = Path(
            tempfile.mkdtemp(prefix=".snapshot-", dir=admitted_staging_root)
        )
        try:
            runtime_copy = staging / "runtime.db"
            tasks_copy = staging / "tasks.db"
            projection_copy = staging / "status.json"
            runtime_source = state_root / "state" / "runtime.db"
            tasks_source = state_root / "db" / "tasks.db"
            runtime_connection: sqlite3.Connection | None = None
            tasks_connection: sqlite3.Connection | None = None
            runtime_descriptor = -1
            tasks_descriptor = -1
            try:
                (
                    runtime_connection,
                    runtime_descriptor,
                    runtime_before,
                    runtime_version_before,
                ) = _open_sqlite_witness(runtime_source)
                (
                    tasks_connection,
                    tasks_descriptor,
                    tasks_before,
                    tasks_version_before,
                ) = _open_sqlite_witness(tasks_source)
                projection_raw, projection_before = _projection_witness(
                    projection_path
                )
                window_started = datetime.now(timezone.utc)
                _backup_sqlite_connection(
                    runtime_connection,
                    runtime_copy,
                    source_name=runtime_source.name,
                )
                _backup_sqlite_connection(
                    tasks_connection,
                    tasks_copy,
                    source_name=tasks_source.name,
                )
                _write_projection_copy(projection_raw, projection_copy)
                projection_after_raw, projection_after = _projection_witness(
                    projection_path
                )
                window_ended = datetime.now(timezone.utc)
                runtime_version_after = _read_sqlite_data_version(
                    runtime_connection,
                    source_name=runtime_source.name,
                )
                tasks_version_after = _read_sqlite_data_version(
                    tasks_connection,
                    source_name=tasks_source.name,
                )
                runtime_after = _sqlite_source_identity(
                    runtime_source, runtime_descriptor
                )
                tasks_after = _sqlite_source_identity(
                    tasks_source, tasks_descriptor
                )
            finally:
                if runtime_connection is not None:
                    runtime_connection.close()
                if tasks_connection is not None:
                    tasks_connection.close()
                if runtime_descriptor >= 0:
                    os.close(runtime_descriptor)
                if tasks_descriptor >= 0:
                    os.close(tasks_descriptor)
            if (
                runtime_before != runtime_after
                or tasks_before != tasks_after
                or runtime_version_before != runtime_version_after
                or tasks_version_before != tasks_version_after
                or projection_before != projection_after
                or projection_raw != projection_after_raw
            ):
                raise SnapshotError("snapshot source changed during stable window")
            semantic_proof = _validate_cross_store_semantics(
                runtime_copy,
                tasks_copy,
                projection_copy,
            )
            consistency_proof: dict[str, Any] = {
                "schema_version": CONSISTENCY_SCHEMA_VERSION,
                "method": (
                    "same-connection-data-version+path-identity+projection-sha+"
                    "canonical-owner-reconciliation"
                ),
                "window_started_at": window_started.isoformat(),
                "window_ended_at": window_ended.isoformat(),
                "runtime_db": {
                    "dev": runtime_before["dev"],
                    "ino": runtime_before["ino"],
                    "size_before": runtime_before["size"],
                    "size_after": runtime_after["size"],
                    "mtime_ns_before": runtime_before["mtime_ns"],
                    "mtime_ns_after": runtime_after["mtime_ns"],
                    "data_version_before": runtime_version_before,
                    "data_version_after": runtime_version_after,
                    "stable": True,
                },
                "tasks_db": {
                    "dev": tasks_before["dev"],
                    "ino": tasks_before["ino"],
                    "size_before": tasks_before["size"],
                    "size_after": tasks_after["size"],
                    "mtime_ns_before": tasks_before["mtime_ns"],
                    "mtime_ns_after": tasks_after["mtime_ns"],
                    "data_version_before": tasks_version_before,
                    "data_version_after": tasks_version_after,
                    "stable": True,
                },
                "projection": {
                    "dev_before": projection_before["dev"],
                    "dev_after": projection_after["dev"],
                    "ino_before": projection_before["ino"],
                    "ino_after": projection_after["ino"],
                    "size_before": projection_before["size"],
                    "size_after": projection_after["size"],
                    "mtime_ns_before": projection_before["mtime_ns"],
                    "mtime_ns_after": projection_after["mtime_ns"],
                    "sha256_before": projection_before["sha256"],
                    "sha256_after": projection_after["sha256"],
                    "stable": True,
                },
                "semantic_proof": semantic_proof,
                "cross_domain_consistency_proven": True,
                "claim": "stable_committed_point",
            }
            files = {
                "runtime.db": _sha256(runtime_copy),
                "tasks.db": _sha256(tasks_copy),
                "status.json": _sha256(projection_copy),
            }
            manifest = _manifest_payload(
                release_sha=release_sha,
                generated_at=observed,
                snapshot_id=snapshot_id,
                files=files,
                consistency_proof=consistency_proof,
            )
            manifest_path = staging / "snapshot-manifest.json"
            descriptor = os.open(
                manifest_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                _write_all(
                    descriptor,
                    json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode()
                    + b"\n",
                )
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(staging, candidate)
            directory_descriptor = os.open(
                admitted_staging_root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
            return candidate
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_consistency_proof(
    proof: Any,
    *,
    snapshot: Path,
) -> dict[str, Any]:
    fields = {
        "schema_version",
        "method",
        "window_started_at",
        "window_ended_at",
        "runtime_db",
        "tasks_db",
        "projection",
        "semantic_proof",
        "cross_domain_consistency_proven",
        "claim",
    }
    db_fields = {
        "dev",
        "ino",
        "size_before",
        "size_after",
        "mtime_ns_before",
        "mtime_ns_after",
        "data_version_before",
        "data_version_after",
        "stable",
    }
    projection_fields = {
        "dev_before",
        "dev_after",
        "ino_before",
        "ino_after",
        "size_before",
        "size_after",
        "mtime_ns_before",
        "mtime_ns_after",
        "sha256_before",
        "sha256_after",
        "stable",
    }
    semantic_fields = {
        "schema_version",
        "mission_id",
        "session_id",
        "config_digest",
        "generation",
        "cycle_sequence",
        "projection_schema_valid",
        "projection_content_digest_valid",
        "canonical_owner_projection_match",
        "cross_store_semantics_valid",
        "reconciliation_state",
        "reconciliation_policy",
    }
    if (
        not isinstance(proof, dict)
        or set(proof) != fields
        or proof.get("schema_version") != CONSISTENCY_SCHEMA_VERSION
        or proof.get("method")
        != (
            "same-connection-data-version+path-identity+projection-sha+"
            "canonical-owner-reconciliation"
        )
        or proof.get("cross_domain_consistency_proven") is not True
        or proof.get("claim") != "stable_committed_point"
    ):
        raise SnapshotError("snapshot consistency proof binding differs")
    try:
        started = datetime.fromisoformat(str(proof["window_started_at"]))
        ended = datetime.fromisoformat(str(proof["window_ended_at"]))
    except ValueError as exc:
        raise SnapshotError("snapshot consistency window is invalid") from exc
    if (
        started.tzinfo is None
        or ended.tzinfo is None
        or ended.astimezone(timezone.utc) < started.astimezone(timezone.utc)
    ):
        raise SnapshotError("snapshot consistency window differs")
    for name in ("runtime_db", "tasks_db"):
        value = proof.get(name)
        if not isinstance(value, dict) or set(value) != db_fields:
            raise SnapshotError("snapshot database witness fields differ")
        numeric = {key: item for key, item in value.items() if key != "stable"}
        if (
            value.get("stable") is not True
            or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0
                for item in numeric.values()
            )
            or value["ino"] <= 0
            or value["data_version_before"] < 1
            or value["data_version_before"] != value["data_version_after"]
            or value["size_before"] != value["size_after"]
            or value["mtime_ns_before"] != value["mtime_ns_after"]
        ):
            raise SnapshotError("snapshot database witness is not stable")
    projection = proof.get("projection")
    if not isinstance(projection, dict) or set(projection) != projection_fields:
        raise SnapshotError("snapshot projection witness fields differ")
    projection_numeric = {
        key: value
        for key, value in projection.items()
        if key not in {"stable", "sha256_before", "sha256_after"}
    }
    if (
        projection.get("stable") is not True
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in projection_numeric.values()
        )
        or projection["ino_before"] <= 0
        or projection["dev_before"] != projection["dev_after"]
        or projection["ino_before"] != projection["ino_after"]
        or projection["size_before"] != projection["size_after"]
        or projection["mtime_ns_before"] != projection["mtime_ns_after"]
        or projection["sha256_before"] != projection["sha256_after"]
        or not isinstance(projection["sha256_before"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", projection["sha256_before"])
        or projection["sha256_before"] != _sha256(snapshot / "status.json")
    ):
        raise SnapshotError("snapshot projection witness is not stable")
    semantic = proof.get("semantic_proof")
    if (
        not isinstance(semantic, dict)
        or set(semantic) != semantic_fields
        or semantic.get("schema_version") != SEMANTIC_PROOF_SCHEMA_VERSION
        or semantic.get("mission_id") != MISSION_ID
        or semantic.get("session_id") != f"mission_campaign:{MISSION_ID}"
        or not isinstance(semantic.get("config_digest"), str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", semantic["config_digest"])
        or isinstance(semantic.get("generation"), bool)
        or not isinstance(semantic.get("generation"), int)
        or semantic["generation"] < 1
        or isinstance(semantic.get("cycle_sequence"), bool)
        or not isinstance(semantic.get("cycle_sequence"), int)
        or semantic["cycle_sequence"] < 0
        or semantic.get("projection_schema_valid") is not True
        or semantic.get("projection_content_digest_valid") is not True
        or semantic.get("canonical_owner_projection_match") is not True
        or semantic.get("cross_store_semantics_valid") is not True
        or semantic.get("reconciliation_state") != "coherent"
        or semantic.get("reconciliation_policy") != "reject_noncoherent"
    ):
        raise SnapshotError("snapshot semantic proof binding differs")
    live_semantic = _validate_cross_store_semantics(
        snapshot / "runtime.db",
        snapshot / "tasks.db",
        snapshot / "status.json",
    )
    if live_semantic != semantic:
        raise SnapshotError("snapshot semantic proof differs from owner bytes")
    return dict(proof)


def _snapshot_manifest(
    snapshot: Path,
    *,
    allowed_uids: frozenset[int] | None = None,
    expected_snapshot_id: str | None = None,
    allowed_extra_names: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], str]:
    """Validate an exact closed snapshot tree and return its tree digest."""
    snapshot_id = expected_snapshot_id or snapshot.name
    snapshot_match = _SNAPSHOT_DIR_RE.fullmatch(snapshot_id)
    if snapshot_match is None:
        raise SnapshotError("snapshot directory name differs")
    identity = snapshot.lstat()
    if snapshot.is_symlink() or not stat.S_ISDIR(identity.st_mode):
        raise SnapshotError("snapshot candidate is not a real directory")
    children = {entry.name for entry in snapshot.iterdir()}
    if children != SNAPSHOT_FILE_NAMES | allowed_extra_names:
        raise SnapshotError("snapshot candidate file set differs")
    manifest_path = snapshot / "snapshot-manifest.json"
    admitted_uids = allowed_uids or frozenset({0, os.geteuid()})
    manifest_identity = manifest_path.lstat()
    if (
        manifest_path.is_symlink()
        or not stat.S_ISREG(manifest_identity.st_mode)
        or manifest_identity.st_nlink != 1
        or manifest_identity.st_uid not in admitted_uids
        or stat.S_IMODE(manifest_identity.st_mode) & 0o077
    ):
        raise SnapshotError("snapshot manifest lacks private custody")
    if manifest_identity.st_size > 1024 * 1024:
        raise SnapshotError("snapshot manifest exceeds size bound")
    raw = manifest_path.read_bytes()
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("snapshot manifest is invalid JSON") from exc
    fields = {
        "schema_version",
        "mission_id",
        "release_sha",
        "snapshot_id",
        "generated_at",
        "source_role",
        "destination_role",
        "writer_authority_transferred",
        "standby_activation_requested",
        "files",
        "consistency_proof",
        "snapshot_digest",
    }
    files = payload.get("files") if isinstance(payload, dict) else None
    unsigned = dict(payload) if isinstance(payload, dict) else {}
    unsigned.pop("snapshot_digest", None)
    generated_at_raw = payload.get("generated_at") if isinstance(payload, dict) else None
    try:
        if (
            not isinstance(generated_at_raw, str)
            or not re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:"
                r"[0-9]{2}:[0-9]{2}\+00:00",
                generated_at_raw,
            )
        ):
            raise ValueError("snapshot timestamp is not canonical UTC seconds")
        generated_at = datetime.fromisoformat(generated_at_raw)
    except ValueError as exc:
        raise SnapshotError("snapshot generated_at is invalid") from exc
    if (
        generated_at.tzinfo != timezone.utc
        or generated_at < CAMPAIGN_START_UTC
        or generated_at >= CAMPAIGN_STOP_UTC
        or snapshot_match.group("stamp")
        != generated_at.strftime("%Y%m%dT%H%M%SZ")
    ):
        raise SnapshotError("snapshot generated_at binding differs")
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or raw != _canonical_bytes(payload) + b"\n"
        or payload.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
        or payload.get("mission_id") != MISSION_ID
        or not _COMMIT_RE.fullmatch(str(payload.get("release_sha", "")))
        or snapshot_match.group("release_prefix")
        != str(payload.get("release_sha", ""))[:12]
        or payload.get("snapshot_id") != snapshot_id
        or payload.get("source_role") != "writer"
        or payload.get("destination_role") != "fenced_standby"
        or payload.get("writer_authority_transferred") is not False
        or payload.get("standby_activation_requested") is not False
        or not isinstance(files, dict)
        or set(files) != {"runtime.db", "tasks.db", "status.json"}
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in files.values()
        )
        or payload.get("snapshot_digest")
        != hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    ):
        raise SnapshotError("snapshot manifest binding differs")
    for name, expected_hash in files.items():
        path = snapshot / name
        file_identity = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(file_identity.st_mode)
            or file_identity.st_nlink != 1
            or file_identity.st_uid not in admitted_uids
            or stat.S_IMODE(file_identity.st_mode) & 0o077
        ):
            raise SnapshotError("snapshot file lacks private custody")
        if file_identity.st_size > 16 * 1024 * 1024 * 1024:
            raise SnapshotError("snapshot file exceeds size bound")
        if _sha256(path) != expected_hash:
            raise SnapshotError("snapshot file hash differs")
    _validate_consistency_proof(payload.get("consistency_proof"), snapshot=snapshot)
    tree_payload = {
        "snapshot_id": snapshot_id,
        "snapshot_digest": payload["snapshot_digest"],
        "files": {
            name: _sha256(snapshot / name) for name in sorted(SNAPSHOT_FILE_NAMES)
        },
    }
    return payload, hashlib.sha256(_canonical_bytes(tree_payload)).hexdigest()


def _claim_snapshot_directory(
    source: Path,
    *,
    source_root: Path,
    claim_root: Path,
    quarantine_root: Path,
    receipt_root: Path,
    quarantine_scope: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> Path:
    if source.parent != source_root or source.is_symlink():
        raise SnapshotError("snapshot claim source differs")
    admitted = source.lstat()
    if not stat.S_ISDIR(admitted.st_mode):
        raise SnapshotError("snapshot claim source is not a directory")
    destination = claim_root / f"{source.name}.claim-{secrets.token_hex(8)}"
    if destination.exists() or destination.is_symlink():
        raise SnapshotError("snapshot claim destination already exists")
    source_descriptor = os.open(
        source_root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    destination_descriptor = os.open(
        claim_root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        _rename_noreplace(
            source.name,
            destination.name,
            source_dir_fd=source_descriptor,
            destination_dir_fd=destination_descriptor,
        )
    finally:
        os.close(source_descriptor)
        os.close(destination_descriptor)
    claimed = destination.lstat()
    if (claimed.st_dev, claimed.st_ino) != (admitted.st_dev, admitted.st_ino):
        _quarantine_claim(
            destination,
            quarantine_root=quarantine_root,
            receipt_root=receipt_root,
            source_scope=quarantine_scope,
            reason="source-substitution-during-claim",
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        raise SnapshotError("snapshot candidate changed during root claim")
    _fsync_directory(source_root)
    _fsync_directory(claim_root)
    return destination


def _claim_unsafe_incoming_entry(
    source: Path,
    *,
    incoming_root: Path,
    claim_root: Path,
    quarantine_root: Path,
    receipt_root: Path,
    expected_root_uid: int,
    expected_root_gid: int,
) -> Path:
    """Atomically remove a non-directory deterministic-name poison entry."""
    if source.parent != incoming_root:
        raise SnapshotError("unsafe incoming entry root differs")
    admitted = source.lstat()
    if stat.S_ISDIR(admitted.st_mode) and not stat.S_ISLNK(admitted.st_mode):
        raise SnapshotError("unsafe incoming entry unexpectedly became a directory")
    destination = claim_root / f"{source.name}.unsafe-{secrets.token_hex(8)}"
    source_descriptor = os.open(
        incoming_root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    destination_descriptor = os.open(
        claim_root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        _rename_noreplace(
            source.name,
            destination.name,
            source_dir_fd=source_descriptor,
            destination_dir_fd=destination_descriptor,
        )
    finally:
        os.close(source_descriptor)
        os.close(destination_descriptor)
    claimed = destination.lstat()
    if (claimed.st_dev, claimed.st_ino) != (admitted.st_dev, admitted.st_ino):
        _quarantine_claim(
            destination,
            quarantine_root=quarantine_root,
            receipt_root=receipt_root,
            source_scope="incoming",
            reason="source-substitution-during-claim",
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
        raise SnapshotError("unsafe incoming entry changed during root claim")
    _fsync_directory(incoming_root)
    _fsync_directory(claim_root)
    return destination


def _materialize_frozen_copy(
    source: Path,
    *,
    destination_root: Path,
    snapshot_id: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> Path:
    """Copy stable claimed bytes onto new root-owned inodes before publication."""
    destination = (
        destination_root / f".frozen-{snapshot_id}-{secrets.token_hex(8)}"
    )
    if destination.exists() or destination.is_symlink():
        raise SnapshotError("frozen snapshot staging collision")
    os.mkdir(destination, 0o700)
    for name in sorted(SNAPSHOT_FILE_NAMES):
        source_path = source / name
        identity = source_path.lstat()
        if (
            source_path.is_symlink()
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_nlink != 1
        ):
            raise SnapshotError("snapshot file changed before custody transition")
        source_descriptor = os.open(source_path, os.O_RDONLY | os.O_NOFOLLOW)
        destination_descriptor = os.open(
            destination / name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        try:
            opened = os.fstat(source_descriptor)
            if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
                raise SnapshotError("snapshot file changed during custody transition")
            while True:
                chunk = os.read(source_descriptor, 1024 * 1024)
                if not chunk:
                    break
                _write_all(destination_descriptor, chunk)
            after = os.fstat(source_descriptor)
            if (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ) != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
            ):
                raise SnapshotError("snapshot file changed while copying")
            os.fchown(destination_descriptor, expected_root_uid, expected_root_gid)
            os.fchmod(destination_descriptor, 0o400)
            # Make final content and custody durable before this inode can be
            # renamed into the immutable snapshot namespace.
            os.fsync(destination_descriptor)
        finally:
            os.close(source_descriptor)
            os.close(destination_descriptor)
    directory = os.open(
        destination,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fchown(directory, expected_root_uid, expected_root_gid)
        # Keep the unpublished directory owner-writable.  Darwin refuses a
        # dirfd rename of a 0500 directory; Linux publication also benefits
        # from making the final 0500 transition only after the no-replace
        # rename.  Every contained file is already root-owned 0400 here.
        os.fchmod(directory, 0o700)
        os.fsync(directory)
    finally:
        os.close(directory)
    _snapshot_manifest(
        destination,
        allowed_uids=frozenset({expected_root_uid}),
        expected_snapshot_id=snapshot_id,
    )
    return destination


def _seal_published_snapshot_directory(
    snapshot: Path, *, expected_root_uid: int, expected_root_gid: int
) -> None:
    """Make a root-owned published snapshot non-writable and durable."""
    identity = snapshot.lstat()
    if (
        snapshot.is_symlink()
        or not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) not in {0o700, 0o500}
    ):
        raise SnapshotError("published snapshot directory custody differs")
    for name in SNAPSHOT_FILE_NAMES:
        item = (snapshot / name).lstat()
        if (
            not stat.S_ISREG(item.st_mode)
            or item.st_uid != expected_root_uid
            or item.st_gid != expected_root_gid
            or stat.S_IMODE(item.st_mode) != 0o400
            or item.st_nlink != 1
        ):
            raise SnapshotError("published snapshot file custody differs")
    descriptor = os.open(
        snapshot,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fchmod(descriptor, 0o500)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(snapshot.parent)


def _assert_frozen_snapshot(
    snapshot: Path, *, expected_root_uid: int, expected_root_gid: int
) -> None:
    identity = snapshot.lstat()
    if (
        snapshot.is_symlink()
        or not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) != 0o500
    ):
        raise SnapshotError("final snapshot directory is not immutable")
    for name in SNAPSHOT_FILE_NAMES:
        item = (snapshot / name).lstat()
        if (
            not stat.S_ISREG(item.st_mode)
            or item.st_uid != expected_root_uid
            or item.st_gid != expected_root_gid
            or stat.S_IMODE(item.st_mode) != 0o400
            or item.st_nlink != 1
        ):
            raise SnapshotError("final snapshot file is not immutable")


def _entry_identity_payload(path: Path) -> dict[str, Any]:
    identity = path.lstat()
    if stat.S_ISDIR(identity.st_mode):
        kind = "directory"
    elif stat.S_ISREG(identity.st_mode):
        kind = "regular"
    elif stat.S_ISLNK(identity.st_mode):
        kind = "symlink"
    else:
        kind = "other"
    return {
        "device": identity.st_dev,
        "inode": identity.st_ino,
        "uid": identity.st_uid,
        "gid": identity.st_gid,
        "mode": stat.S_IMODE(identity.st_mode),
        "nlink": identity.st_nlink,
        "size_bytes": identity.st_size,
        "kind": kind,
    }


def _quarantine_receipt_path(receipt_root: Path, quarantine_name: str) -> Path:
    name_digest = hashlib.sha256(quarantine_name.encode("utf-8")).hexdigest()
    return receipt_root / f"quarantine-{name_digest}.v1.json"


def _logical_quarantine_source_name(claim_name: str) -> str:
    for pattern, group in (
        (_LOCAL_CLAIM_RE, "snapshot"),
        (_UPLOAD_CLAIM_RE, "upload"),
        (_UNSAFE_INCOMING_CLAIM_RE, "upload"),
    ):
        match = pattern.fullmatch(claim_name)
        if match is not None:
            return match.group(group)
    return claim_name


def _write_quarantine_receipt(
    quarantined: Path,
    *,
    receipt_root: Path,
    source_entry_name: str,
    source_scope: str,
    reason: str,
    expected_root_uid: int,
    expected_root_gid: int,
    recovered_after_move: bool,
) -> Path:
    identity = _entry_identity_payload(quarantined)
    unsigned: dict[str, Any] = {
        "schema_version": "dharma.sadhana.snapshot_quarantine.v1",
        "mission_id": MISSION_ID,
        "source_scope": source_scope,
        "source_entry_name": source_entry_name,
        "quarantine_entry_name": quarantined.name,
        "reason_code": reason,
        "quarantine_identity": identity,
        "bytes_preserved_by_atomic_rename": True,
        "receipt_recovered_after_move": recovered_after_move,
        "snapshot_accepted": False,
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
        "status": "quarantined_no_acceptance",
    }
    payload = dict(unsigned)
    payload["receipt_digest"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()
    return _write_immutable_receipt(
        _quarantine_receipt_path(receipt_root, quarantined.name),
        payload,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def _validate_quarantine_receipt(
    receipt: Path,
    *,
    quarantined: Path,
    source_entry_name: str,
    source_scope: str,
    reason: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> None:
    identity = receipt.lstat()
    if (
        receipt.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) != 0o400
        or identity.st_nlink != 1
        or identity.st_size > 64 * 1024
    ):
        raise SnapshotError("snapshot quarantine receipt custody differs")
    raw = receipt.read_bytes()
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("snapshot quarantine receipt is invalid") from exc
    fields = {
        "schema_version",
        "mission_id",
        "source_scope",
        "source_entry_name",
        "quarantine_entry_name",
        "reason_code",
        "quarantine_identity",
        "bytes_preserved_by_atomic_rename",
        "receipt_recovered_after_move",
        "snapshot_accepted",
        "writer_authority_transferred",
        "standby_activation_requested",
        "status",
        "receipt_digest",
    }
    unsigned = dict(payload) if isinstance(payload, dict) else {}
    unsigned.pop("receipt_digest", None)
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or raw != _canonical_bytes(payload) + b"\n"
        or payload.get("schema_version") != "dharma.sadhana.snapshot_quarantine.v1"
        or payload.get("mission_id") != MISSION_ID
        or payload.get("source_scope") != source_scope
        or payload.get("source_entry_name") != source_entry_name
        or payload.get("quarantine_entry_name") != quarantined.name
        or payload.get("reason_code") != reason
        or payload.get("quarantine_identity")
        != _entry_identity_payload(quarantined)
        or payload.get("bytes_preserved_by_atomic_rename") is not True
        or not isinstance(payload.get("receipt_recovered_after_move"), bool)
        or payload.get("snapshot_accepted") is not False
        or payload.get("writer_authority_transferred") is not False
        or payload.get("standby_activation_requested") is not False
        or payload.get("status") != "quarantined_no_acceptance"
        or payload.get("receipt_digest")
        != hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    ):
        raise SnapshotError("snapshot quarantine receipt binding differs")


def _quarantine_claim(
    claim: Path,
    *,
    quarantine_root: Path,
    receipt_root: Path,
    source_scope: str,
    reason: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> Path:
    if not _QUARANTINE_SCOPE_RE.fullmatch(source_scope):
        raise SnapshotError("snapshot quarantine scope differs")
    if not _QUARANTINE_REASON_RE.fullmatch(reason):
        raise SnapshotError("snapshot quarantine reason differs")
    source_name = claim.name
    logical_source_name = _logical_quarantine_source_name(source_name)
    source_identity = _entry_identity_payload(claim)
    destination = quarantine_root / (
        f"{source_name}.quarantine-{source_scope}-{reason}-{secrets.token_hex(8)}"
    )
    if destination.exists() or destination.is_symlink():
        raise SnapshotError("snapshot quarantine collision")
    source_descriptor = os.open(
        claim.parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    destination_descriptor = os.open(
        quarantine_root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        _rename_noreplace(
            claim.name,
            destination.name,
            source_dir_fd=source_descriptor,
            destination_dir_fd=destination_descriptor,
        )
    finally:
        os.close(source_descriptor)
        os.close(destination_descriptor)
    _fsync_directory(quarantine_root)
    quarantined_identity = _entry_identity_payload(destination)
    if (
        quarantined_identity["device"],
        quarantined_identity["inode"],
    ) != (source_identity["device"], source_identity["inode"]):
        raise SnapshotError("snapshot quarantine identity changed")
    _write_quarantine_receipt(
        destination,
        receipt_root=receipt_root,
        source_entry_name=logical_source_name,
        source_scope=source_scope,
        reason=reason,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
        recovered_after_move=False,
    )
    return destination


def _reconcile_quarantine_receipts(
    *,
    quarantine_root: Path,
    receipt_root: Path,
    expected_root_uid: int,
    expected_root_gid: int,
) -> list[Path]:
    """Recover typed evidence after a crash between rename and receipt fsync."""
    receipts: list[Path] = []
    for quarantined in sorted(quarantine_root.iterdir(), key=lambda item: item.name):
        match = _QUARANTINE_ENTRY_RE.fullmatch(quarantined.name)
        if match is None:
            continue
        receipt = _quarantine_receipt_path(receipt_root, quarantined.name)
        if receipt.exists() or receipt.is_symlink():
            _validate_quarantine_receipt(
                receipt,
                quarantined=quarantined,
                source_entry_name=_logical_quarantine_source_name(
                    match.group("source")
                ),
                source_scope=match.group("scope"),
                reason=match.group("reason"),
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            continue
        receipts.append(
            _write_quarantine_receipt(
                quarantined,
                receipt_root=receipt_root,
                source_entry_name=_logical_quarantine_source_name(
                    match.group("source")
                ),
                source_scope=match.group("scope"),
                reason=match.group("reason"),
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
                recovered_after_move=True,
            )
        )
    return receipts


def finalize_local_snapshot(
    candidate: Path,
    *,
    staging_root: Path = SNAPSHOT_STAGING_ROOT,
    claim_root: Path = SNAPSHOT_FINALIZING_ROOT,
    snapshot_root: Path = SNAPSHOT_ROOT,
    quarantine_root: Path = SNAPSHOT_QUARANTINE_ROOT,
    receipt_root: Path = SNAPSHOT_RECEIPT_ROOT,
    outbox_root: Path = SNAPSHOT_OUTBOX_ROOT,
    expected_release_sha: str,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    expected_service_uid: int | None = None,
) -> tuple[Path, bool]:
    """Root-claim, validate, and immutably publish one local snapshot."""
    if os.geteuid() != expected_root_uid:
        raise SnapshotError("local snapshot finalization requires root")
    if not _COMMIT_RE.fullmatch(expected_release_sha):
        raise SnapshotError("local finalizer release SHA differs")
    for root in (
        claim_root,
        snapshot_root,
        quarantine_root,
        receipt_root,
        outbox_root,
    ):
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if root.is_symlink() or not stat.S_ISDIR(root.lstat().st_mode):
            raise SnapshotError("snapshot finalization root differs")
    lock_path = claim_root / ".finalize.lock"
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if candidate.parent == claim_root:
            claim_match = _LOCAL_CLAIM_RE.fullmatch(candidate.name)
            if claim_match is None:
                raise SnapshotError("local snapshot claim identity differs")
            snapshot_id = claim_match.group("snapshot")
            claim = candidate
        else:
            if candidate.parent != staging_root or not _SNAPSHOT_DIR_RE.fullmatch(
                candidate.name
            ):
                raise SnapshotError("local snapshot candidate identity differs")
            snapshot_id = candidate.name
            claim = _claim_snapshot_directory(
                candidate,
                source_root=staging_root,
                claim_root=claim_root,
                quarantine_root=quarantine_root,
                receipt_root=receipt_root,
                quarantine_scope="local",
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        if claim.parent != claim_root:
            raise SnapshotError("local snapshot claim identity differs")
        try:
            service_uid = (
                pwd.getpwnam("dharma-sadhana").pw_uid
                if expected_service_uid is None
                else expected_service_uid
            )
            payload, candidate_tree_digest = _snapshot_manifest(
                claim,
                allowed_uids=frozenset({service_uid}),
                expected_snapshot_id=snapshot_id,
            )
            if payload["release_sha"] != expected_release_sha:
                raise SnapshotError("local snapshot release binding differs")
            final = snapshot_root / snapshot_id
            if final.exists() or final.is_symlink():
                if final.is_symlink():
                    raise SnapshotError("final snapshot path is a symlink")
                _existing, final_tree_digest = _snapshot_manifest(
                    final, allowed_uids=frozenset({expected_root_uid})
                )
                if final_tree_digest != candidate_tree_digest:
                    _quarantine_claim(
                        claim,
                        quarantine_root=quarantine_root,
                        receipt_root=receipt_root,
                        source_scope="local",
                        reason="conflicting-final-snapshot",
                        expected_root_uid=expected_root_uid,
                        expected_root_gid=expected_root_gid,
                    )
                    raise SnapshotError("conflicting snapshot replay was quarantined")
                _validate_restorable_snapshot(
                    final,
                    expected_snapshot_id=snapshot_id,
                    expected_root_uid=expected_root_uid,
                    expected_release_sha=expected_release_sha,
                )
                _seal_published_snapshot_directory(
                    final,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                _assert_frozen_snapshot(
                    final,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                shutil.rmtree(claim)
                _fsync_directory(claim_root)
                return final, True
            frozen = _materialize_frozen_copy(
                claim,
                destination_root=claim_root,
                snapshot_id=snapshot_id,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            frozen_payload, frozen_tree_digest = _validate_restorable_snapshot(
                frozen,
                expected_snapshot_id=snapshot_id,
                expected_root_uid=expected_root_uid,
                expected_release_sha=expected_release_sha,
            )
            if (
                frozen_payload != payload
                or frozen_tree_digest != candidate_tree_digest
            ):
                _quarantine_claim(
                    frozen,
                    quarantine_root=quarantine_root,
                    receipt_root=receipt_root,
                    source_scope="local",
                    reason="custody-transition-digest-drift",
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                raise SnapshotError("local snapshot changed across custody transition")
            outbox_unsigned: dict[str, Any] = {
                "schema_version": "dharma.sadhana.snapshot_outbox.v1",
                "mission_id": MISSION_ID,
                "snapshot_id": snapshot_id,
                "snapshot_digest": payload["snapshot_digest"],
                "tree_digest": candidate_tree_digest,
                "release_sha": expected_release_sha,
                "destination": STANDBY_DESTINATION,
                "destination_root": STANDBY_ROOT,
                "writer_authority_transferred": False,
                "standby_activation_requested": False,
                "status": "pending_exact_upload_receipt",
            }
            outbox = dict(outbox_unsigned)
            outbox["receipt_digest"] = hashlib.sha256(
                _canonical_bytes(outbox_unsigned)
            ).hexdigest()
            _write_immutable_receipt(
                outbox_root / f"{snapshot_id}.outbox.v1.json",
                outbox,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            claim_descriptor = os.open(
                claim_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            final_descriptor = os.open(
                snapshot_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            try:
                _rename_noreplace(
                    frozen.name,
                    final.name,
                    source_dir_fd=claim_descriptor,
                    destination_dir_fd=final_descriptor,
                )
            finally:
                os.close(claim_descriptor)
                os.close(final_descriptor)
            _seal_published_snapshot_directory(
                final,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            shutil.rmtree(claim)
            _fsync_directory(claim_root)
            _fsync_directory(snapshot_root)
            _assert_frozen_snapshot(
                final,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            return final, False
        except SnapshotError:
            if claim.exists() and claim.parent == claim_root:
                _quarantine_claim(
                    claim,
                    quarantine_root=quarantine_root,
                    receipt_root=receipt_root,
                    source_scope="local",
                    reason="validation-failed",
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
            raise
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)


def replicate_snapshot(
    snapshot: Path,
    *,
    ssh_key: Path,
    destination: str = STANDBY_DESTINATION,
    destination_root: str = STANDBY_ROOT,
    standby_port: int = STANDBY_PORT,
    known_hosts: Path = KNOWN_HOSTS,
    receipt_root: Path = SNAPSHOT_RECEIPT_ROOT,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    """Upload immutable bytes into AGNI's non-authoritative incoming area."""
    if os.geteuid() != expected_root_uid:
        raise SnapshotError("snapshot replication requires root finalizer custody")
    if (
        destination != STANDBY_DESTINATION
        or destination_root != STANDBY_ROOT
        or standby_port != STANDBY_PORT
    ):
        raise SnapshotError("standby destination differs from the pinned AGNI route")
    for path, field in ((ssh_key, "ssh_key"), (known_hosts, "known_hosts")):
        if not path.is_absolute() or not _SAFE_ABSOLUTE_PATH_RE.fullmatch(str(path)):
            raise SnapshotError(f"{field} must be a shell-inert absolute path")
        _require_no_symlink_chain(path)
    _require_service_input(ssh_key)
    _require_service_input(known_hosts)
    _assert_frozen_snapshot(
        snapshot,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    payload, tree_digest = _snapshot_manifest(
        snapshot, allowed_uids=frozenset({expected_root_uid})
    )
    snapshot_digest = str(payload["snapshot_digest"])
    upload_name = f"{snapshot.name}.upload-{snapshot_digest}"
    if not _UPLOAD_DIR_RE.fullmatch(upload_name):
        raise SnapshotError("standby upload identity differs")
    receipt_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    attempt_receipt = (
        receipt_root / f"{snapshot.name}.writer-upload-attempt.v1.json"
    )
    attempt = {
        "schema_version": "dharma.sadhana.replication_attempt.v1",
        "mission_id": MISSION_ID,
        "snapshot": snapshot.name,
        "snapshot_digest": snapshot_digest,
        "tree_digest": tree_digest,
        "upload_name": upload_name,
        "destination": destination,
        "standby_port": standby_port,
        "ssh_transport_policy_sha256": standby_ssh_policy_digest(),
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
        "status": "writer_upload_completed_receiver_verification_pending",
        "standby_hash_verified": False,
        "standby_readiness_verified": False,
        "receipt_replicated_to_standby": False,
    }
    attempt["receipt_digest"] = hashlib.sha256(_canonical_bytes(attempt)).hexdigest()
    expected_acceptance = _standby_acceptance_payload(payload, tree_digest)
    expected_acceptance_raw = _canonical_bytes(expected_acceptance) + b"\n"
    confirmation = {
        "schema_version": "dharma.sadhana.replication_acceptance.v1",
        "mission_id": MISSION_ID,
        "snapshot": snapshot.name,
        "snapshot_digest": snapshot_digest,
        "tree_digest": tree_digest,
        "release_sha": payload["release_sha"],
        "destination": destination,
        "standby_port": standby_port,
        "ssh_transport_policy_sha256": standby_ssh_policy_digest(),
        "standby_acceptance_receipt_sha256": hashlib.sha256(
            expected_acceptance_raw
        ).hexdigest(),
        "standby_acceptance_receipt_digest": expected_acceptance[
            "receipt_digest"
        ],
        "standby_hash_verified": True,
        "standby_restore_verified": True,
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
        "status": "standby_acceptance_exactly_confirmed",
    }
    confirmation["receipt_digest"] = hashlib.sha256(
        _canonical_bytes(confirmation)
    ).hexdigest()
    confirmation_receipt = (
        receipt_root / f"{snapshot.name}.writer-standby-confirmed.v1.json"
    )
    if confirmation_receipt.exists() or confirmation_receipt.is_symlink():
        return _write_immutable_receipt(
            confirmation_receipt,
            confirmation,
            expected_root_uid=expected_root_uid,
            expected_root_gid=expected_root_gid,
        )
    ssh_transport = standby_ssh_transport(
        ssh_key=ssh_key,
        known_hosts=known_hosts,
        standby_port=standby_port,
    )
    command = (
        RSYNC_PATH,
        "--archive",
        "--no-owner",
        "--no-group",
        "--chmod=Du=rwx,Dgo=,Fu=rw,Fgo=",
        "--ignore-existing",
        "--delay-updates",
        "-e",
        ssh_transport,
        f"{snapshot}/",
        f"{destination}:{STANDBY_UPLOAD_RELATIVE_ROOT}/{upload_name}/",
    )
    completed = runner(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={
            "HOME": "/nonexistent",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
    )
    if completed.returncode != 0:
        raise SnapshotError(
            f"standby replication failed with exit {completed.returncode}"
        )
    ready_unsigned = {
        "schema_version": "dharma.sadhana.snapshot_upload_ready.v1",
        "mission_id": MISSION_ID,
        "snapshot_id": snapshot.name,
        "snapshot_digest": snapshot_digest,
        "tree_digest": tree_digest,
        "release_sha": payload["release_sha"],
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
    }
    ready = dict(ready_unsigned)
    ready["ready_digest"] = hashlib.sha256(
        _canonical_bytes(ready_unsigned)
    ).hexdigest()
    with tempfile.TemporaryDirectory(prefix="sadhana-ready-") as raw_ready_root:
        ready_root = Path(raw_ready_root)
        ready_path = ready_root / ".ready.json"
        ready_path.write_bytes(_canonical_bytes(ready) + b"\n")
        ready_path.chmod(0o600)
        ready_command = (
            RSYNC_PATH,
            "--archive",
            "--no-owner",
            "--no-group",
            "--chmod=Fu=rw,Fgo=",
            "--ignore-existing",
            "-e",
            ssh_transport,
            str(ready_path),
            f"{destination}:{STANDBY_UPLOAD_RELATIVE_ROOT}/{upload_name}/.ready.json",
        )
        ready_completed = runner(
            ready_command,
            check=False,
            capture_output=True,
            text=True,
            env={
                "HOME": "/nonexistent",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
        )
    if ready_completed.returncode != 0:
        raise SnapshotError(
            f"standby ready-marker upload failed with exit {ready_completed.returncode}"
        )
    _write_immutable_receipt(
        attempt_receipt,
        attempt,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    with tempfile.TemporaryDirectory(prefix="sadhana-acceptance-") as raw_ack_root:
        local_ack = Path(raw_ack_root) / confirmation_receipt.name.replace(
            ".writer-standby-confirmed.v1.json", ".standby-acceptance.v1.json"
        )
        local_ack.write_bytes(expected_acceptance_raw)
        local_ack.chmod(0o600)
        compare_command = (
            RSYNC_PATH,
            "--checksum",
            "--dry-run",
            "--itemize-changes",
            "--out-format=%i",
            "--no-motd",
            "-e",
            ssh_transport,
            str(local_ack),
            f"{destination}:{STANDBY_ACK_RELATIVE_ROOT}/{local_ack.name}",
        )
        compared = runner(
            compare_command,
            check=False,
            capture_output=True,
            text=True,
            env={
                "HOME": "/nonexistent",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
        )
    if (
        compared.returncode != 0
        or compared.stdout != ""
        or compared.stderr != ""
    ):
        raise SnapshotError("standby acceptance ACK is not yet exact")
    return _write_immutable_receipt(
        confirmation_receipt,
        confirmation,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def _validate_snapshot_outbox(
    path: Path,
    *,
    outbox_root: Path,
    snapshot_root: Path,
    expected_release_sha: str,
    expected_root_uid: int,
    expected_root_gid: int,
) -> Path:
    """Bind one immutable retry intent to one exact finalized snapshot."""
    if path.parent != outbox_root:
        raise SnapshotError("snapshot outbox root differs")
    name_match = _OUTBOX_ENTRY_RE.fullmatch(path.name)
    if name_match is None:
        raise SnapshotError("snapshot outbox filename differs")
    identity = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_uid != expected_root_uid
        or identity.st_gid != expected_root_gid
        or stat.S_IMODE(identity.st_mode) != 0o400
        or identity.st_nlink != 1
        or identity.st_size > 64 * 1024
    ):
        raise SnapshotError("snapshot outbox custody differs")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("snapshot outbox is invalid JSON") from exc
    fields = {
        "schema_version",
        "mission_id",
        "snapshot_id",
        "snapshot_digest",
        "tree_digest",
        "release_sha",
        "destination",
        "destination_root",
        "writer_authority_transferred",
        "standby_activation_requested",
        "status",
        "receipt_digest",
    }
    unsigned = dict(payload) if isinstance(payload, dict) else {}
    unsigned.pop("receipt_digest", None)
    snapshot_id = name_match.group("snapshot")
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or raw != _canonical_bytes(payload) + b"\n"
        or payload.get("schema_version") != "dharma.sadhana.snapshot_outbox.v1"
        or payload.get("mission_id") != MISSION_ID
        or payload.get("snapshot_id") != snapshot_id
        or not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("snapshot_digest", "")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("tree_digest", "")))
        or payload.get("release_sha") != expected_release_sha
        or payload.get("destination") != STANDBY_DESTINATION
        or payload.get("destination_root") != STANDBY_ROOT
        or payload.get("writer_authority_transferred") is not False
        or payload.get("standby_activation_requested") is not False
        or payload.get("status") != "pending_exact_upload_receipt"
        or payload.get("receipt_digest")
        != hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    ):
        raise SnapshotError("snapshot outbox binding differs")
    snapshot = snapshot_root / snapshot_id
    _assert_frozen_snapshot(
        snapshot,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    manifest, tree_digest = _snapshot_manifest(
        snapshot,
        allowed_uids=frozenset({expected_root_uid}),
        expected_snapshot_id=snapshot_id,
    )
    if (
        manifest["release_sha"] != expected_release_sha
        or manifest["snapshot_digest"] != payload["snapshot_digest"]
        or tree_digest != payload["tree_digest"]
    ):
        raise SnapshotError("snapshot outbox differs from finalized bytes")
    return snapshot


def replicate_pending_outbox(
    *,
    ssh_key: Path,
    destination: str = STANDBY_DESTINATION,
    destination_root: str = STANDBY_ROOT,
    standby_port: int = STANDBY_PORT,
    known_hosts: Path = KNOWN_HOSTS,
    outbox_root: Path = SNAPSHOT_OUTBOX_ROOT,
    snapshot_root: Path = SNAPSHOT_ROOT,
    receipt_root: Path = SNAPSHOT_RECEIPT_ROOT,
    expected_release_sha: str,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[tuple[Path, Path]]:
    """Retry every durable outbox intent until its exact upload receipt exists."""
    results: list[tuple[Path, Path]] = []
    failures: list[str] = []
    for outbox in sorted(outbox_root.iterdir(), key=lambda item: item.name):
        name_match = _OUTBOX_ENTRY_RE.fullmatch(outbox.name)
        if name_match is None:
            if outbox.name.startswith("."):
                continue
            failures.append("unknown-entry")
            continue
        snapshot_id = name_match.group("snapshot")
        try:
            snapshot = _validate_snapshot_outbox(
                outbox,
                outbox_root=outbox_root,
                snapshot_root=snapshot_root,
                expected_release_sha=expected_release_sha,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            receipt = replicate_snapshot(
                snapshot,
                ssh_key=ssh_key,
                destination=destination,
                destination_root=destination_root,
                standby_port=standby_port,
                known_hosts=known_hosts,
                receipt_root=receipt_root,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
                runner=runner,
            )
        except SnapshotError:
            failures.append(snapshot_id)
            continue
        results.append((snapshot, receipt))
    if failures:
        raise SnapshotError(
            "snapshot outbox retry incomplete after attempting every item: "
            + ",".join(failures)
        )
    return results


def _write_immutable_receipt(
    path: Path,
    payload: dict[str, Any],
    *,
    expected_root_uid: int,
    expected_root_gid: int,
) -> Path:
    raw = _canonical_bytes(payload) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _quarantine_partial_publications(path)
    if path.exists() or path.is_symlink():
        identity = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != expected_root_uid
            or identity.st_gid != expected_root_gid
            or stat.S_IMODE(identity.st_mode) != 0o400
            or identity.st_nlink != 1
            or path.read_bytes() != raw
        ):
            raise SnapshotError("immutable snapshot receipt conflicts")
        _fsync_directory(path.parent)
        return path
    _publish_complete_file_noreplace(
        path,
        raw,
        expected_uid=expected_root_uid,
        expected_gid=expected_root_gid,
        mode=0o400,
    )
    return path


def _quarantine_partial_publications(path: Path) -> None:
    """Move crash-left publication temps aside without deleting evidence."""
    parent = path.parent
    target_digest = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:16]
    prefix = f".partial-{target_digest}-"
    incomplete = parent / ".incomplete"
    incomplete.mkdir(mode=0o700, exist_ok=True)
    incomplete_identity = incomplete.lstat()
    if (
        incomplete.is_symlink()
        or not stat.S_ISDIR(incomplete_identity.st_mode)
        or incomplete_identity.st_uid != os.geteuid()
        or stat.S_IMODE(incomplete_identity.st_mode) != 0o700
    ):
        raise SnapshotError("partial-publication quarantine differs")
    parent_descriptor = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    incomplete_descriptor = os.open(
        incomplete,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        for partial in sorted(parent.iterdir(), key=lambda item: item.name):
            if not partial.name.startswith(prefix):
                continue
            identity = partial.lstat()
            if partial.is_symlink() or not stat.S_ISREG(identity.st_mode):
                raise SnapshotError("partial publication has unsafe custody")
            destination = f"{partial.name}.incomplete-{secrets.token_hex(8)}"
            _rename_noreplace(
                partial.name,
                destination,
                source_dir_fd=parent_descriptor,
                destination_dir_fd=incomplete_descriptor,
            )
    finally:
        os.close(parent_descriptor)
        os.close(incomplete_descriptor)
    _fsync_directory(parent)
    _fsync_directory(incomplete)


def _publish_complete_file_noreplace(
    path: Path,
    raw: bytes,
    *,
    expected_uid: int,
    expected_gid: int,
    mode: int,
) -> None:
    """Write/freeze a random temp, then atomically publish its complete inode."""
    _quarantine_partial_publications(path)
    target_digest = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:16]
    temporary = path.parent / f".partial-{target_digest}-{secrets.token_hex(8)}"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    try:
        _write_all(descriptor, raw)
        os.fchown(descriptor, expected_uid, expected_gid)
        os.fchmod(descriptor, mode)
        opened = os.fstat(descriptor)
        if (
            opened.st_uid != expected_uid
            or opened.st_gid != expected_gid
            or stat.S_IMODE(opened.st_mode) != mode
            or opened.st_nlink != 1
            or opened.st_size != len(raw)
        ):
            raise SnapshotError("complete publication temp custody differs")
        # Persist content and final custody metadata on the same inode before
        # making its canonical name durable.
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        parent_descriptor = os.open(
            path.parent,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            try:
                _rename_noreplace(
                    temporary.name,
                    path.name,
                    source_dir_fd=parent_descriptor,
                    destination_dir_fd=parent_descriptor,
                )
            except SnapshotError:
                # A concurrent exact publisher may win the no-replace race.
                # Accept only the identical frozen inode, then move our temp
                # aside as crash/race evidence rather than leaking it forever.
                if path.exists() and not path.is_symlink():
                    winner = path.lstat()
                    if (
                        stat.S_ISREG(winner.st_mode)
                        and winner.st_uid == expected_uid
                        and winner.st_gid == expected_gid
                        and stat.S_IMODE(winner.st_mode) == mode
                        and winner.st_nlink == 1
                        and path.read_bytes() == raw
                    ):
                        os.close(parent_descriptor)
                        parent_descriptor = -1
                        _quarantine_partial_publications(path)
                        _fsync_directory(path.parent)
                        return
                raise
        finally:
            if parent_descriptor >= 0:
                os.close(parent_descriptor)
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        # Any unpromoted inode intentionally remains uniquely named.  The next
        # invocation moves it into the root-only .incomplete quarantine before
        # attempting a new publication; no partial canonical path can exist.


def _write_standby_acceptance_ack(
    path: Path,
    payload: dict[str, Any],
    *,
    expected_root_uid: int,
    expected_service_gid: int,
) -> Path:
    """Publish a root-owned, rrsync-readable, non-writable acceptance ACK."""
    raw = _canonical_bytes(payload) + b"\n"
    parent = path.parent.lstat()
    if (
        path.parent.is_symlink()
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != expected_root_uid
        or parent.st_gid != expected_service_gid
        or stat.S_IMODE(parent.st_mode) != 0o750
    ):
        raise SnapshotError("standby ACK root custody differs")
    _quarantine_partial_publications(path)
    if path.exists() or path.is_symlink():
        identity = path.lstat()
        if (
            path.is_symlink()
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_uid != expected_root_uid
            or identity.st_gid != expected_service_gid
            or stat.S_IMODE(identity.st_mode) != 0o440
            or identity.st_nlink != 1
            or path.read_bytes() != raw
        ):
            raise SnapshotError("standby acceptance ACK conflicts")
        _fsync_directory(path.parent)
        return path
    _publish_complete_file_noreplace(
        path,
        raw,
        expected_uid=expected_root_uid,
        expected_gid=expected_service_gid,
        mode=0o440,
    )
    return path


def _validate_restorable_snapshot(
    snapshot: Path,
    *,
    expected_snapshot_id: str,
    expected_root_uid: int,
    expected_release_sha: str,
) -> tuple[dict[str, Any], str]:
    """Reject a self-consistent but unrestorable snapshot before publication."""
    payload, tree_digest = _snapshot_manifest(
        snapshot,
        allowed_uids=frozenset({expected_root_uid}),
        expected_snapshot_id=expected_snapshot_id,
    )
    if payload["release_sha"] != expected_release_sha:
        raise SnapshotError("restorable snapshot release binding differs")
    for name in ("runtime.db", "tasks.db"):
        try:
            uri = f"file:{quote(str(snapshot / name), safe='/')}?mode=ro"
            with sqlite3.connect(uri, uri=True) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise SnapshotError("snapshot SQLite integrity differs")
        except sqlite3.Error as exc:
            raise SnapshotError("snapshot SQLite could not be restored") from exc
    try:
        json.loads(
            (snapshot / "status.json").read_bytes(),
            object_pairs_hook=_strict_object,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("snapshot projection is invalid JSON") from exc
    return payload, tree_digest


def _restore_drill_receipt_payload(
    manifest: dict[str, Any], tree_digest: str
) -> dict[str, Any]:
    consistency = manifest["consistency_proof"]
    semantic = consistency["semantic_proof"]
    unsigned: dict[str, Any] = {
        "schema_version": "dharma.sadhana.snapshot_restore_drill.v2",
        "mission_id": MISSION_ID,
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_digest": manifest["snapshot_digest"],
        "tree_digest": tree_digest,
        "restored_hashes": {
            name: manifest["files"][name]
            for name in ("runtime.db", "status.json", "tasks.db")
        },
        "sqlite_integrity": "ok",
        "projection_json_valid": True,
        "consistency_proof_digest": hashlib.sha256(
            _canonical_bytes(consistency)
        ).hexdigest(),
        "consistency_claim": consistency["claim"],
        "cross_store_semantics_valid": semantic["cross_store_semantics_valid"],
        "reconciliation_state": semantic["reconciliation_state"],
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
        "status": "PASS",
    }
    payload = dict(unsigned)
    payload["receipt_digest"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()
    return payload


def _standby_acceptance_payload(
    manifest: dict[str, Any], tree_digest: str
) -> dict[str, Any]:
    restore = _restore_drill_receipt_payload(manifest, tree_digest)
    restore_raw = _canonical_bytes(restore) + b"\n"
    consistency = manifest["consistency_proof"]
    semantic = consistency["semantic_proof"]
    unsigned: dict[str, Any] = {
        "schema_version": "dharma.sadhana.standby_snapshot_acceptance.v2",
        "mission_id": MISSION_ID,
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_digest": manifest["snapshot_digest"],
        "tree_digest": tree_digest,
        "release_sha": manifest["release_sha"],
        "replay_policy": "exact_bytes_only",
        "standby_hash_verified": True,
        "standby_restore_verified": True,
        "consistency_proof_digest": hashlib.sha256(
            _canonical_bytes(consistency)
        ).hexdigest(),
        "consistency_claim": consistency["claim"],
        "cross_store_semantics_valid": semantic["cross_store_semantics_valid"],
        "reconciliation_state": semantic["reconciliation_state"],
        "restore_receipt_sha256": hashlib.sha256(restore_raw).hexdigest(),
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
        "status": "PASS",
    }
    payload = dict(unsigned)
    payload["receipt_digest"] = hashlib.sha256(
        _canonical_bytes(unsigned)
    ).hexdigest()
    return payload


def restore_hash_drill(
    snapshot: Path,
    *,
    receipt_root: Path = SNAPSHOT_RECEIPT_ROOT,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
) -> Path:
    """Restore to a disposable root-only scratch tree and re-prove all hashes."""
    if os.geteuid() != expected_root_uid:
        raise SnapshotError("snapshot restore drill requires root")
    _assert_frozen_snapshot(
        snapshot,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    payload, tree_digest = _validate_restorable_snapshot(
        snapshot,
        expected_snapshot_id=snapshot.name,
        expected_root_uid=expected_root_uid,
        expected_release_sha=_snapshot_manifest(
            snapshot, allowed_uids=frozenset({expected_root_uid})
        )[0]["release_sha"],
    )
    receipt_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=".restore-drill-", dir=receipt_root) as raw:
        scratch = Path(raw)
        restored_hashes: dict[str, str] = {}
        for name in ("runtime.db", "tasks.db", "status.json"):
            source = snapshot / name
            destination = scratch / name
            source_descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            destination_descriptor = os.open(
                destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            try:
                while True:
                    chunk = os.read(source_descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    _write_all(destination_descriptor, chunk)
                os.fsync(destination_descriptor)
            finally:
                os.close(source_descriptor)
                os.close(destination_descriptor)
            restored_hashes[name] = _sha256(destination)
            if restored_hashes[name] != payload["files"][name]:
                raise SnapshotError("restored snapshot hash differs")
        for name in ("runtime.db", "tasks.db"):
            try:
                uri = f"file:{quote(str(scratch / name), safe='/')}?mode=ro"
                with sqlite3.connect(uri, uri=True) as connection:
                    if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                        raise SnapshotError("restored SQLite integrity differs")
            except sqlite3.Error as exc:
                raise SnapshotError("restored SQLite could not be opened") from exc
        try:
            json.loads((scratch / "status.json").read_bytes())
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise SnapshotError("restored projection is invalid JSON") from exc
        restored_semantic = _validate_cross_store_semantics(
            scratch / "runtime.db",
            scratch / "tasks.db",
            scratch / "status.json",
        )
        if restored_semantic != payload["consistency_proof"]["semantic_proof"]:
            raise SnapshotError("restored cross-store semantics differ")
    receipt = _restore_drill_receipt_payload(payload, tree_digest)
    if receipt["restored_hashes"] != restored_hashes:
        raise SnapshotError("restore drill receipt hashes differ")
    return _write_immutable_receipt(
        receipt_root / f"{snapshot.name}.restore-drill.v1.json",
        receipt,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )


def _validate_ready_marker(
    upload: Path,
    *,
    expected_upload_id: str,
) -> tuple[dict[str, Any], bytes]:
    ready_path = upload / ".ready.json"
    identity = ready_path.lstat()
    if (
        ready_path.is_symlink()
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_nlink != 1
        or stat.S_IMODE(identity.st_mode) & 0o077
        or identity.st_size > 16 * 1024
    ):
        raise SnapshotError("standby ready marker custody differs")
    raw = ready_path.read_bytes()
    try:
        payload = json.loads(raw, object_pairs_hook=_strict_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("standby ready marker is invalid") from exc
    fields = {
        "schema_version",
        "mission_id",
        "snapshot_id",
        "snapshot_digest",
        "tree_digest",
        "release_sha",
        "writer_authority_transferred",
        "standby_activation_requested",
        "ready_digest",
    }
    unsigned = dict(payload) if isinstance(payload, dict) else {}
    unsigned.pop("ready_digest", None)
    if (
        not isinstance(payload, dict)
        or set(payload) != fields
        or raw != _canonical_bytes(payload) + b"\n"
        or payload.get("schema_version")
        != "dharma.sadhana.snapshot_upload_ready.v1"
        or payload.get("mission_id") != MISSION_ID
        or not _SNAPSHOT_DIR_RE.fullmatch(str(payload.get("snapshot_id", "")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("snapshot_digest", "")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("tree_digest", "")))
        or not _COMMIT_RE.fullmatch(str(payload.get("release_sha", "")))
        or payload.get("writer_authority_transferred") is not False
        or payload.get("standby_activation_requested") is not False
        or payload.get("ready_digest")
        != hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    ):
        raise SnapshotError("standby ready marker binding differs")
    match = _UPLOAD_DIR_RE.fullmatch(expected_upload_id)
    if (
        match is None
        or match.group("snapshot") != payload["snapshot_id"]
        or match.group("digest") != payload["snapshot_digest"]
    ):
        raise SnapshotError("standby upload filename binding differs")
    return payload, raw


def finalize_standby_upload(
    upload: Path,
    *,
    incoming_root: Path = SNAPSHOT_UPLOAD_ROOT,
    ack_root: Path = SNAPSHOT_ACK_ROOT,
    claim_root: Path = SNAPSHOT_RECEIVER_CLAIM_ROOT,
    snapshot_root: Path = SNAPSHOT_ROOT,
    quarantine_root: Path = SNAPSHOT_QUARANTINE_ROOT,
    receipt_root: Path = SNAPSHOT_RECEIPT_ROOT,
    expected_root_uid: int = 0,
    expected_root_gid: int = 0,
    expected_service_uid: int | None = None,
    expected_service_gid: int | None = None,
    expected_release_sha: str,
) -> tuple[Path, Path, bool]:
    """Claim one completed upload and publish it append-only on fenced AGNI."""
    if os.geteuid() != expected_root_uid:
        raise SnapshotError("standby receiver requires root")
    if not _COMMIT_RE.fullmatch(expected_release_sha):
        raise SnapshotError("standby receiver release SHA differs")
    service_account = (
        pwd.getpwnam("dharma-sadhana")
        if expected_service_uid is None or expected_service_gid is None
        else None
    )
    service_uid = (
        service_account.pw_uid
        if expected_service_uid is None and service_account is not None
        else int(expected_service_uid)
    )
    service_gid = (
        service_account.pw_gid
        if expected_service_gid is None and service_account is not None
        else int(expected_service_gid)
    )
    for root in (claim_root, snapshot_root, quarantine_root, receipt_root):
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    ack_root.mkdir(parents=True, exist_ok=True, mode=0o750)
    ack_identity = ack_root.lstat()
    if (
        ack_root.is_symlink()
        or not stat.S_ISDIR(ack_identity.st_mode)
        or ack_identity.st_uid != expected_root_uid
        or ack_identity.st_gid != service_gid
        or stat.S_IMODE(ack_identity.st_mode) != 0o750
    ):
        raise SnapshotError("standby ACK root custody differs")
    lock = os.open(
        claim_root / ".receiver.lock",
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
    )
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if upload.parent == claim_root:
            claim_match = _UPLOAD_CLAIM_RE.fullmatch(upload.name)
            if claim_match is None:
                raise SnapshotError("standby snapshot claim identity differs")
            upload_id = claim_match.group("upload")
            claim = upload
        else:
            if upload.parent != incoming_root or not _UPLOAD_DIR_RE.fullmatch(
                upload.name
            ):
                raise SnapshotError("standby upload identity differs")
            upload_id = upload.name
            claim = _claim_snapshot_directory(
                upload,
                source_root=incoming_root,
                claim_root=claim_root,
                quarantine_root=quarantine_root,
                receipt_root=receipt_root,
                quarantine_scope="standby",
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        if claim.parent != claim_root:
            raise SnapshotError("standby snapshot claim identity differs")
        try:
            ready, _raw = _validate_ready_marker(
                claim, expected_upload_id=upload_id
            )
            manifest, tree_digest = _snapshot_manifest(
                claim,
                allowed_uids=frozenset({service_uid}),
                expected_snapshot_id=ready["snapshot_id"],
                allowed_extra_names=frozenset({".ready.json"}),
            )
            if (
                manifest["snapshot_digest"] != ready["snapshot_digest"]
                or manifest["release_sha"] != ready["release_sha"]
                or manifest["release_sha"] != expected_release_sha
                or tree_digest != ready["tree_digest"]
            ):
                raise SnapshotError("standby upload hashes differ from ready marker")
            final = snapshot_root / ready["snapshot_id"]
            replayed = False
            if final.exists() or final.is_symlink():
                if final.is_symlink():
                    raise SnapshotError("standby final snapshot path is a symlink")
                _existing, final_tree_digest = _snapshot_manifest(
                    final, allowed_uids=frozenset({expected_root_uid})
                )
                if final_tree_digest != tree_digest:
                    raise SnapshotError("standby conflicting replay")
                _validate_restorable_snapshot(
                    final,
                    expected_snapshot_id=ready["snapshot_id"],
                    expected_root_uid=expected_root_uid,
                    expected_release_sha=expected_release_sha,
                )
                _seal_published_snapshot_directory(
                    final,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                _assert_frozen_snapshot(
                    final,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                replayed = True
            else:
                frozen = _materialize_frozen_copy(
                    claim,
                    destination_root=claim_root,
                    snapshot_id=ready["snapshot_id"],
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                frozen_manifest, frozen_tree_digest = _validate_restorable_snapshot(
                    frozen,
                    expected_snapshot_id=ready["snapshot_id"],
                    expected_root_uid=expected_root_uid,
                    expected_release_sha=expected_release_sha,
                )
                if (
                    frozen_manifest != manifest
                    or frozen_tree_digest != tree_digest
                ):
                    _quarantine_claim(
                        frozen,
                        quarantine_root=quarantine_root,
                        receipt_root=receipt_root,
                        source_scope="standby",
                        reason="custody-transition-digest-drift",
                        expected_root_uid=expected_root_uid,
                        expected_root_gid=expected_root_gid,
                    )
                    raise SnapshotError(
                        "standby snapshot changed across custody transition"
                    )
                claim_descriptor = os.open(
                    claim_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                )
                final_descriptor = os.open(
                    snapshot_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                )
                try:
                    _rename_noreplace(
                        frozen.name,
                        final.name,
                        source_dir_fd=claim_descriptor,
                        destination_dir_fd=final_descriptor,
                    )
                finally:
                    os.close(claim_descriptor)
                    os.close(final_descriptor)
                _seal_published_snapshot_directory(
                    final,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                _assert_frozen_snapshot(
                    final,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
            drill = restore_hash_drill(
                final,
                receipt_root=receipt_root,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            receipt = _standby_acceptance_payload(manifest, tree_digest)
            if receipt["restore_receipt_sha256"] != _sha256(drill):
                raise SnapshotError("standby restore receipt binding differs")
            receipt_path = _write_immutable_receipt(
                receipt_root / f"{ready['snapshot_id']}.standby-acceptance.v1.json",
                receipt,
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
            _write_standby_acceptance_ack(
                ack_root / f"{ready['snapshot_id']}.standby-acceptance.v1.json",
                receipt,
                expected_root_uid=expected_root_uid,
                expected_service_gid=service_gid,
            )
            shutil.rmtree(claim)
            _fsync_directory(claim_root)
            return final, receipt_path, replayed
        except SnapshotError:
            if claim.exists() and claim.parent == claim_root:
                _quarantine_claim(
                    claim,
                    quarantine_root=quarantine_root,
                    receipt_root=receipt_root,
                    source_scope="standby",
                    reason="standby-validation-failed",
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
            raise
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)


def finalize_pending_local(
    **kwargs: Any,
) -> list[tuple[Path, bool]]:
    staging_root = Path(kwargs.pop("staging_root", SNAPSHOT_STAGING_ROOT))
    claim_root = Path(kwargs.get("claim_root", SNAPSHOT_FINALIZING_ROOT))
    quarantine_root = Path(kwargs.get("quarantine_root", SNAPSHOT_QUARANTINE_ROOT))
    receipt_root = Path(kwargs.get("receipt_root", SNAPSHOT_RECEIPT_ROOT))
    expected_root_uid = int(kwargs.get("expected_root_uid", 0))
    expected_root_gid = int(kwargs.get("expected_root_gid", 0))
    results: list[tuple[Path, bool]] = []
    failures: list[str] = []
    for root in (staging_root, claim_root, quarantine_root, receipt_root):
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _reconcile_quarantine_receipts(
        quarantine_root=quarantine_root,
        receipt_root=receipt_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    for partial in sorted(claim_root.glob(".frozen-*"), key=lambda item: item.name):
        try:
            _quarantine_claim(
                partial,
                quarantine_root=quarantine_root,
                receipt_root=receipt_root,
                source_scope="local",
                reason="interrupted-local-frozen-copy",
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        except (SnapshotError, FileNotFoundError) as exc:
            failures.append(f"{partial.name}:{exc}")
    for candidate in sorted(staging_root.iterdir(), key=lambda item: item.name):
        if _SNAPSHOT_DIR_RE.fullmatch(candidate.name):
            try:
                results.append(
                    finalize_local_snapshot(
                        candidate, staging_root=staging_root, **kwargs
                    )
                )
            except (SnapshotError, FileNotFoundError) as exc:
                failures.append(f"{candidate.name}:{exc}")
    for claim in sorted(claim_root.iterdir(), key=lambda item: item.name):
        if _LOCAL_CLAIM_RE.fullmatch(claim.name):
            try:
                results.append(
                    finalize_local_snapshot(claim, staging_root=staging_root, **kwargs)
                )
            except (SnapshotError, FileNotFoundError) as exc:
                failures.append(f"{claim.name}:{exc}")
    if failures:
        raise SnapshotError(
            "local snapshot reconciliation incomplete after attempting every item: "
            + ",".join(failures)
        )
    return results


def finalize_pending_standby(
    **kwargs: Any,
) -> list[tuple[Path, Path, bool]]:
    incoming_root = Path(kwargs.pop("incoming_root", SNAPSHOT_UPLOAD_ROOT))
    claim_root = Path(kwargs.get("claim_root", SNAPSHOT_RECEIVER_CLAIM_ROOT))
    quarantine_root = Path(kwargs.get("quarantine_root", SNAPSHOT_QUARANTINE_ROOT))
    receipt_root = Path(kwargs.get("receipt_root", SNAPSHOT_RECEIPT_ROOT))
    expected_root_uid = int(kwargs.get("expected_root_uid", 0))
    expected_root_gid = int(kwargs.get("expected_root_gid", 0))
    results: list[tuple[Path, Path, bool]] = []
    failures: list[str] = []
    for root in (incoming_root, claim_root, quarantine_root, receipt_root):
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _reconcile_quarantine_receipts(
        quarantine_root=quarantine_root,
        receipt_root=receipt_root,
        expected_root_uid=expected_root_uid,
        expected_root_gid=expected_root_gid,
    )
    for partial in sorted(claim_root.glob(".frozen-*"), key=lambda item: item.name):
        try:
            _quarantine_claim(
                partial,
                quarantine_root=quarantine_root,
                receipt_root=receipt_root,
                source_scope="standby",
                reason="interrupted-standby-frozen-copy",
                expected_root_uid=expected_root_uid,
                expected_root_gid=expected_root_gid,
            )
        except (SnapshotError, FileNotFoundError) as exc:
            failures.append(f"{partial.name}:{exc}")
    for upload in sorted(incoming_root.iterdir(), key=lambda item: item.name):
        if _UPLOAD_DIR_RE.fullmatch(upload.name) is None:
            continue
        try:
            identity = upload.lstat()
            if upload.is_symlink() or not stat.S_ISDIR(identity.st_mode):
                unsafe_claim = _claim_unsafe_incoming_entry(
                    upload,
                    incoming_root=incoming_root,
                    claim_root=claim_root,
                    quarantine_root=quarantine_root,
                    receipt_root=receipt_root,
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                _quarantine_claim(
                    unsafe_claim,
                    quarantine_root=quarantine_root,
                    receipt_root=receipt_root,
                    source_scope="incoming",
                    reason="unsafe-deterministic-upload-entry",
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
                continue
            try:
                (upload / ".ready.json").lstat()
            except FileNotFoundError:
                # An incomplete or concurrently withdrawn attempt carries no
                # authority and must not block later ready uploads.
                continue
            results.append(
                finalize_standby_upload(upload, incoming_root=incoming_root, **kwargs)
            )
        except FileNotFoundError:
            failures.append(f"{upload.name}:incoming-entry-disappeared")
        except SnapshotError as exc:
            failures.append(f"{upload.name}:{exc}")
    for unsafe_claim in sorted(claim_root.iterdir(), key=lambda item: item.name):
        if _UNSAFE_INCOMING_CLAIM_RE.fullmatch(unsafe_claim.name):
            try:
                _quarantine_claim(
                    unsafe_claim,
                    quarantine_root=quarantine_root,
                    receipt_root=receipt_root,
                    source_scope="incoming",
                    reason="recovered-unsafe-incoming-claim",
                    expected_root_uid=expected_root_uid,
                    expected_root_gid=expected_root_gid,
                )
            except (SnapshotError, FileNotFoundError) as exc:
                failures.append(f"{unsafe_claim.name}:{exc}")
    for claim in sorted(claim_root.iterdir(), key=lambda item: item.name):
        if _UPLOAD_CLAIM_RE.fullmatch(claim.name):
            try:
                results.append(
                    finalize_standby_upload(
                        claim, incoming_root=incoming_root, **kwargs
                    )
                )
            except (SnapshotError, FileNotFoundError) as exc:
                failures.append(f"{claim.name}:{exc}")
    if failures:
        raise SnapshotError(
            "standby snapshot reconciliation incomplete after attempting every item: "
            + ",".join(failures)
        )
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--mission-id", required=True)
    stage.add_argument("--role", choices=("writer",), required=True)
    stage.add_argument("--release-sha", required=True)
    stage.add_argument("--state-root", type=Path, required=True)
    stage.add_argument("--projection", type=Path, required=True)
    stage.add_argument("--snapshot-root", type=Path, required=True)
    stage.add_argument("--staging-root", type=Path, required=True)
    finalize = commands.add_parser("finalize-local")
    finalize.add_argument("--mission-id", required=True)
    finalize.add_argument("--role", choices=("writer",), required=True)
    finalize.add_argument("--release-sha", required=True)
    finalize.add_argument("--ssh-key", type=Path, required=True)
    finalize.add_argument("--standby", required=True)
    finalize.add_argument("--standby-root", required=True)
    finalize.add_argument("--standby-port", type=int, required=True)
    finalize.add_argument("--known-hosts", type=Path, required=True)
    receiver = commands.add_parser("finalize-standby")
    receiver.add_argument("--mission-id", required=True)
    receiver.add_argument("--role", choices=("standby",), required=True)
    receiver.add_argument("--release-sha", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mission_id != MISSION_ID or not _COMMIT_RE.fullmatch(args.release_sha):
        raise SnapshotError("snapshot CLI campaign binding differs")
    if args.command == "stage":
        candidate = create_snapshot(
            release_sha=args.release_sha,
            state_root=args.state_root,
            projection_path=args.projection,
            snapshot_root=args.snapshot_root,
            staging_root=args.staging_root,
        )
        print(json.dumps({"status": "staged", "candidate": str(candidate)}, sort_keys=True))
        return 0
    if args.command == "finalize-local":
        finalized: list[dict[str, Any]] = []
        for final, replayed in finalize_pending_local(
            expected_release_sha=args.release_sha
        ):
            finalized.append({"snapshot": str(final), "replayed": replayed})
        for final, receipt in replicate_pending_outbox(
            ssh_key=args.ssh_key,
            destination=args.standby,
            destination_root=args.standby_root,
            standby_port=args.standby_port,
            known_hosts=args.known_hosts,
            expected_release_sha=args.release_sha,
        ):
            finalized.append({"snapshot": str(final), "writer_receipt": str(receipt)})
        print(json.dumps({"status": "finalized", "results": finalized}, sort_keys=True))
        return 0
    results: list[dict[str, Any]] = []
    for final, receipt, replayed in finalize_pending_standby(
        expected_release_sha=args.release_sha
    ):
        payload, _tree = _snapshot_manifest(final, allowed_uids=frozenset({0}))
        if payload["release_sha"] != args.release_sha:
            raise SnapshotError("standby snapshot release binding differs")
        results.append(
            {"snapshot": str(final), "receipt": str(receipt), "replayed": replayed}
        )
    print(json.dumps({"status": "standby_finalized", "results": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SnapshotError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, sort_keys=True))
        raise SystemExit(2) from exc
