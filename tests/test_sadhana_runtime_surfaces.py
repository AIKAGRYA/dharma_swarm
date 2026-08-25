from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from scripts.runtime import sadhana_immutable_api as immutable_api
from scripts.runtime import sadhana_release as release
from scripts.runtime import sadhana_snapshot as snapshot


class _Provider:
    runtime_projection_mode = "unavailable"

    def __init__(self) -> None:
        self.admitted = False

    async def admit(self) -> None:
        self.admitted = True

    async def get_snapshot(self, mission_id: str):  # noqa: ANN201
        return {
            "mission": {
                "mission_id": mission_id,
                "session_id": f"mission_campaign:{mission_id}",
                "title": "SADHANA",
                "goal": "verified work",
                "operator_id": "operator",
                "status": "active",
                "metadata": {},
                "created_at": None,
                "updated_at": None,
            },
            "tasks": [],
            "attempts": [],
            "leases": [],
            "receipts": [],
            "reconciliation": "coherent",
            "observed_at": "2026-08-22T21:00:00+00:00",
            "authority": "TaskBoard+RuntimeStateStore",
            "proves_executor_liveness": False,
        }


@pytest.mark.asyncio
async def test_observer_has_only_loopback_read_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_STATE_DIR", immutable_api.API_STATE_ROOT)
    monkeypatch.setenv("SADHANA_API_PORT", immutable_api.API_PORT)
    provider = _Provider()
    app = immutable_api.create_app(lambda: provider)
    methods = {
        method for route in app.routes for method in getattr(route, "methods", set())
    }
    assert methods <= {"GET", "HEAD"}
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 40000))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            health = await client.get("/api/health")
            assert health.status_code == 200
            assert health.json()["write_routes"] == 0
            assert health.json()["proves_executor_liveness"] is False
            result = await client.get(
                f"/api/control-surface/missions/{snapshot.MISSION_ID}/snapshot"
            )
            assert result.status_code == 200
            assert result.json()["data"]["runtime_projection_mode"] == "unavailable"
    assert provider.admitted is True


@pytest.mark.asyncio
async def test_loopback_observer_rejects_tailnet_direct_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_STATE_DIR", immutable_api.API_STATE_ROOT)
    monkeypatch.setenv("SADHANA_API_PORT", immutable_api.API_PORT)
    app = immutable_api.create_app(_Provider)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, client=("100.79.111.89", 40000))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            result = await client.get("/api/health")
    assert result.status_code == 403


def test_observer_surfaces_hash_validated_snapshot_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "snapshot-readiness.v1.json"
    payload = {
        "schema_version": "dharma.sadhana.snapshot_capacity_readiness.v1",
        "mission_id": snapshot.MISSION_ID,
        "observed_at": "2026-08-23T00:00:00Z",
        "status": "snapshot_blocked",
        "free_bytes": 1,
        "required_free_bytes_for_remaining_series": 2,
        "remaining_snapshot_count": 2880,
        "standby_capacity_proven": False,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    payload["receipt_digest"] = hashlib.sha256(canonical).hexdigest()
    receipt.write_bytes(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("ascii")
        + b"\n"
    )
    receipt.chmod(0o600)
    monkeypatch.setattr(immutable_api, "SNAPSHOT_READINESS_PATH", str(receipt))
    readiness = immutable_api._snapshot_readiness()
    assert readiness["status"] == "snapshot_blocked"
    assert readiness["standby_capacity_proven"] is False


def _database(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if value == "runtime":
        from dharma_swarm.runtime_state import RuntimeStateStore

        RuntimeStateStore(path, include_memory_plane=False).init_db_sync()
        observed = datetime(2026, 8, 23, tzinfo=timezone.utc).isoformat()
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE evidence(value TEXT NOT NULL)")
            connection.execute("INSERT INTO evidence(value) VALUES (?)", (value,))
            connection.executemany(
                "INSERT INTO sessions (session_id, operator_id, status, "
                "current_task_id, active_bundle_id, metadata_json, created_at, "
                "updated_at) VALUES (?, ?, ?, '', '', ?, ?, ?)",
                (
                    (
                        f"mission:{snapshot.MISSION_ID}",
                        "operator",
                        "active",
                        json.dumps(
                            {
                                "schema_version": "dharma.mission_control.v1",
                                "mission_id": snapshot.MISSION_ID,
                                "title": "SADHANA",
                                "goal": "verified work",
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        observed,
                        observed,
                    ),
                    (
                        f"mission_campaign:{snapshot.MISSION_ID}",
                        "operator",
                        "active",
                        json.dumps(
                            {
                                "schema_version": (
                                    "dharma.mission_control.campaign.v1"
                                ),
                                "mission_id": snapshot.MISSION_ID,
                                "config_digest": "sha256:" + "c" * 64,
                                "generation": 1,
                                "last_cycle_sequence": 0,
                                "last_cycle_receipt_id": "",
                                "stop_requested": False,
                            },
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        observed,
                        observed,
                    ),
                ),
            )
        return
    if value == "tasks":
        from dharma_swarm.task_board import TaskBoard

        asyncio.run(TaskBoard(path).init_db())
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE evidence(value TEXT NOT NULL)")
            connection.execute("INSERT INTO evidence(value) VALUES (?)", (value,))
        return
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE evidence(value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence(value) VALUES (?)", (value,))


def _write_coherent_projection(
    path: Path,
    *,
    runtime_db: Path,
    tasks_db: Path,
    reconciliation: str = "coherent",
) -> None:
    from dharma_swarm.mission_control_operator_state import (
        initial_operator_control_state,
    )

    observed = datetime(2026, 8, 23, tzinfo=timezone.utc)
    mission_snapshot = asyncio.run(
        snapshot._canonical_owner_snapshot(
            runtime_db,
            tasks_db,
            observed_at=observed,
        )
    )
    assert mission_snapshot is not None
    mission_snapshot["reconciliation"] = reconciliation
    payload = {
        "mission_id": snapshot.MISSION_ID,
        "session_id": f"mission_campaign:{snapshot.MISSION_ID}",
        "config_digest": "sha256:" + "c" * 64,
        "generation": 1,
        "cycle_sequence": 0,
        "freshness_seconds": 30.0,
        "mission_snapshot": mission_snapshot,
        "owner_executions": [],
        "campaign_status": "active",
        "supervisor_state": "unobserved",
        "writer_lock_held": True,
        "latest_cycle_at": None,
        "transport_state": "unobserved",
        "model_execution_state": "unobserved",
        "acceptance_state": "unobserved",
        "candidate_task_ids": [],
        "accepted_task_ids": [],
        "rejected_task_ids": [],
        "conflicting_acceptance_task_ids": [],
        "canary_acceptance": "not_configured",
        "invalid_acceptance_receipts": 0,
        "operator_control_state": initial_operator_control_state(1),
        "errors": [],
        "observed_at": observed.isoformat(),
        "authority": "TaskBoard+RuntimeStateStore+owner execution projection",
        "proves_process_liveness": False,
        "proves_model_execution": False,
        "proves_semantic_acceptance": False,
        "projection_schema_version": snapshot.CAMPAIGN_PROJECTION_SCHEMA_VERSION,
        "projection_kind": "derived_read_model",
        "canonical_state_copied": False,
        "published_at": observed.isoformat(),
        "fresh_until": None,
    }
    unsigned = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    payload["projection_content_digest"] = "sha256:" + hashlib.sha256(
        unsigned
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(snapshot._canonical_bytes(payload) + b"\n")
    path.chmod(0o600)


def _coherent_snapshot_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    reconciliation: str = "coherent",
) -> dict[str, Path]:
    state = tmp_path / "state"
    projection_root = tmp_path / "projection-source"
    snapshots = tmp_path / "snapshots"
    staging = tmp_path / "snapshot-staging"
    runtime_db = state / "state/runtime.db"
    tasks_db = state / "db/tasks.db"
    projection = projection_root / "mission-projection.json"
    _database(runtime_db, "runtime")
    _database(tasks_db, "tasks")
    _write_coherent_projection(
        projection,
        runtime_db=runtime_db,
        tasks_db=tasks_db,
        reconciliation=reconciliation,
    )
    monkeypatch.setattr(snapshot, "STATE_ROOT", state)
    monkeypatch.setattr(snapshot, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(snapshot, "SNAPSHOT_ROOT", snapshots)
    monkeypatch.setattr(snapshot, "SNAPSHOT_STAGING_ROOT", staging)
    monkeypatch.setattr(snapshot, "MIN_FREE_RESERVE_BYTES", 0)
    monkeypatch.setattr(snapshot, "MAX_CAMPAIGN_SNAPSHOTS", 1)
    return {
        "state": state,
        "runtime_db": runtime_db,
        "tasks_db": tasks_db,
        "projection": projection,
        "snapshots": snapshots,
        "staging": staging,
    }


def _create_coherent_snapshot(paths: dict[str, Path]) -> Path:
    return snapshot.create_snapshot(
        release_sha="a" * 40,
        state_root=paths["state"],
        projection_path=paths["projection"],
        snapshot_root=paths["snapshots"],
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )


def _assert_no_snapshot_candidate(paths: dict[str, Path]) -> None:
    assert not any(
        snapshot._SNAPSHOT_DIR_RE.fullmatch(item.name)
        for item in paths["staging"].iterdir()
    )
    assert not any(paths["snapshots"].iterdir())


def _reseal_projection(path: Path, payload: dict[str, object]) -> None:
    unsigned = dict(payload)
    unsigned.pop("projection_content_digest", None)
    payload["projection_content_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            unsigned,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()
    path.write_bytes(snapshot._canonical_bytes(payload) + b"\n")
    path.chmod(0o600)


def _reseal_snapshot_manifest(candidate: Path, payload: dict[str, object]) -> None:
    unsigned = dict(payload)
    unsigned.pop("snapshot_digest", None)
    payload["snapshot_digest"] = hashlib.sha256(
        snapshot._canonical_bytes(unsigned)
    ).hexdigest()
    manifest = candidate / "snapshot-manifest.json"
    manifest.write_bytes(snapshot._canonical_bytes(payload) + b"\n")
    manifest.chmod(0o600)


def _set_runtime_mission_title(runtime_db: Path, title: str) -> None:
    session_id = f"mission:{snapshot.MISSION_ID}"
    with sqlite3.connect(runtime_db) as connection:
        row = connection.execute(
            "SELECT metadata_json FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        assert row is not None
        metadata = json.loads(row[0])
        metadata["title"] = title
        connection.execute(
            "UPDATE sessions SET metadata_json = ? WHERE session_id = ?",
            (
                json.dumps(metadata, separators=(",", ":"), sort_keys=True),
                session_id,
            ),
        )


def _finalized_writer_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    state = tmp_path / "state"
    projection_root = tmp_path / "projection-source"
    snapshots = tmp_path / "writer-snapshots"
    staging = tmp_path / "snapshot-staging"
    claims = tmp_path / "snapshot-finalizing"
    quarantine = tmp_path / "snapshot-quarantine"
    receipts = tmp_path / "snapshot-receipts"
    outbox = tmp_path / "snapshot-outbox"
    _database(state / "state/runtime.db", "runtime")
    _database(state / "db/tasks.db", "tasks")
    projection = projection_root / "mission-projection.json"
    _write_coherent_projection(
        projection,
        runtime_db=state / "state/runtime.db",
        tasks_db=state / "db/tasks.db",
    )
    monkeypatch.setattr(snapshot, "STATE_ROOT", state)
    monkeypatch.setattr(snapshot, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(snapshot, "SNAPSHOT_ROOT", snapshots)
    monkeypatch.setattr(snapshot, "SNAPSHOT_STAGING_ROOT", staging)
    monkeypatch.setattr(snapshot, "MIN_FREE_RESERVE_BYTES", 0)
    monkeypatch.setattr(snapshot, "MAX_CAMPAIGN_SNAPSHOTS", 1)
    candidate = snapshot.create_snapshot(
        release_sha="a" * 40,
        state_root=state,
        projection_path=projection,
        snapshot_root=snapshots,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    final, replayed = snapshot.finalize_local_snapshot(
        candidate,
        staging_root=staging,
        claim_root=claims,
        snapshot_root=snapshots,
        quarantine_root=quarantine,
        receipt_root=receipts,
        outbox_root=outbox,
        expected_release_sha="a" * 40,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
        expected_service_uid=os.geteuid(),
    )
    assert replayed is False
    return {
        "final": final,
        "snapshots": snapshots,
        "staging": staging,
        "claims": claims,
        "quarantine": quarantine,
        "receipts": receipts,
        "outbox": outbox,
    }


def _stage_standby_upload(source: Path, uploads: Path) -> Path:
    manifest, tree_digest = snapshot._snapshot_manifest(
        source, allowed_uids=frozenset({os.geteuid()})
    )
    upload = uploads / f"{source.name}.upload-{manifest['snapshot_digest']}"
    uploads.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, upload)
    upload.chmod(0o700)
    ready_unsigned = {
        "schema_version": "dharma.sadhana.snapshot_upload_ready.v1",
        "mission_id": snapshot.MISSION_ID,
        "snapshot_id": source.name,
        "snapshot_digest": manifest["snapshot_digest"],
        "tree_digest": tree_digest,
        "release_sha": manifest["release_sha"],
        "writer_authority_transferred": False,
        "standby_activation_requested": False,
    }
    ready = dict(ready_unsigned)
    ready["ready_digest"] = hashlib.sha256(
        snapshot._canonical_bytes(ready_unsigned)
    ).hexdigest()
    marker = upload / ".ready.json"
    marker.write_bytes(snapshot._canonical_bytes(ready) + b"\n")
    marker.chmod(0o600)
    return upload


def _reseal_standby_upload_after_file_change(upload: Path) -> Path:
    manifest_path = upload / "snapshot-manifest.json"
    manifest_path.chmod(0o600)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["runtime.db"] = hashlib.sha256(
        (upload / "runtime.db").read_bytes()
    ).hexdigest()
    _reseal_snapshot_manifest(upload, manifest)
    tree_payload = {
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_digest": manifest["snapshot_digest"],
        "files": {
            name: hashlib.sha256((upload / name).read_bytes()).hexdigest()
            for name in sorted(snapshot.SNAPSHOT_FILE_NAMES)
        },
    }
    ready_path = upload / ".ready.json"
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    ready["snapshot_digest"] = manifest["snapshot_digest"]
    ready["tree_digest"] = hashlib.sha256(
        snapshot._canonical_bytes(tree_payload)
    ).hexdigest()
    unsigned_ready = dict(ready)
    unsigned_ready.pop("ready_digest")
    ready["ready_digest"] = hashlib.sha256(
        snapshot._canonical_bytes(unsigned_ready)
    ).hexdigest()
    ready_path.write_bytes(snapshot._canonical_bytes(ready) + b"\n")
    ready_path.chmod(0o600)
    renamed = upload.with_name(
        f"{manifest['snapshot_id']}.upload-{manifest['snapshot_digest']}"
    )
    upload.rename(renamed)
    return renamed


def _rewrite_snapshot_runtime_coherently(candidate: Path) -> None:
    runtime = candidate / "runtime.db"
    runtime.chmod(0o600)
    with sqlite3.connect(runtime) as connection:
        connection.execute("INSERT INTO evidence(value) VALUES ('raced')")
    manifest_path = candidate / "snapshot-manifest.json"
    manifest_path.chmod(0o600)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["files"]["runtime.db"] = hashlib.sha256(runtime.read_bytes()).hexdigest()
    unsigned = dict(payload)
    unsigned.pop("snapshot_digest")
    payload["snapshot_digest"] = hashlib.sha256(
        snapshot._canonical_bytes(unsigned)
    ).hexdigest()
    manifest_path.write_bytes(snapshot._canonical_bytes(payload) + b"\n")
    manifest_path.chmod(0o600)


def test_snapshot_uses_online_backups_and_never_transfers_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    projection_root = tmp_path / "projection-source"
    snapshots = tmp_path / "snapshots"
    staging = tmp_path / "snapshot-staging"
    _database(state / "state/runtime.db", "runtime")
    _database(state / "db/tasks.db", "tasks")
    projection = projection_root / "mission-projection.json"
    _write_coherent_projection(
        projection,
        runtime_db=state / "state/runtime.db",
        tasks_db=state / "db/tasks.db",
    )
    monkeypatch.setattr(snapshot, "STATE_ROOT", state)
    monkeypatch.setattr(snapshot, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(snapshot, "SNAPSHOT_ROOT", snapshots)
    monkeypatch.setattr(snapshot, "SNAPSHOT_STAGING_ROOT", staging)
    monkeypatch.setattr(snapshot, "MIN_FREE_RESERVE_BYTES", 0)
    monkeypatch.setattr(snapshot, "MAX_CAMPAIGN_SNAPSHOTS", 1)
    created = snapshot.create_snapshot(
        release_sha="a" * 40,
        state_root=state,
        projection_path=projection,
        snapshot_root=snapshots,
    )
    manifest = json.loads((created / "snapshot-manifest.json").read_text())
    assert manifest["writer_authority_transferred"] is False
    assert manifest["standby_activation_requested"] is False
    for name, expected in (("runtime.db", "runtime"), ("tasks.db", "tasks")):
        with sqlite3.connect(created / name) as connection:
            assert connection.execute("SELECT value FROM evidence").fetchone() == (
                expected,
            )


def test_snapshot_rejects_runtime_wal_mutation_after_backup_via_retained_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _coherent_snapshot_source(tmp_path, monkeypatch)
    runtime_db = paths["runtime_db"]
    identity_before = runtime_db.lstat()
    stable_main_identity = (
        identity_before.st_dev,
        identity_before.st_ino,
        identity_before.st_size,
        identity_before.st_mtime_ns,
    )
    with sqlite3.connect(f"file:{runtime_db}?mode=ro", uri=True) as fresh_before:
        fresh_version_baseline = fresh_before.execute(
            "PRAGMA data_version"
        ).fetchone()
    assert fresh_version_baseline is not None
    original_backup = snapshot._backup_sqlite_connection
    external_connections: list[sqlite3.Connection] = []
    injected = False

    def mutate_after_runtime_backup(
        reader: sqlite3.Connection,
        destination: Path,
        *,
        source_name: str,
    ) -> None:
        nonlocal injected
        original_backup(reader, destination, source_name=source_name)
        if source_name != "runtime.db" or injected:
            return
        injected = True
        writer = sqlite3.connect(runtime_db)
        assert writer.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO evidence(value) VALUES ('runtime-race')")
        writer.commit()
        external_connections.append(writer)
        identity_after = runtime_db.lstat()
        assert (
            identity_after.st_dev,
            identity_after.st_ino,
            identity_after.st_size,
            identity_after.st_mtime_ns,
        ) == stable_main_identity
        with sqlite3.connect(
            f"file:{runtime_db}?mode=ro", uri=True
        ) as fresh_connection:
            assert (
                fresh_connection.execute("PRAGMA data_version").fetchone()
                == fresh_version_baseline
            ), "a fresh connection resets the witness and would miss this WAL commit"

    monkeypatch.setattr(
        snapshot, "_backup_sqlite_connection", mutate_after_runtime_backup
    )
    try:
        with pytest.raises(snapshot.SnapshotError, match="stable window"):
            _create_coherent_snapshot(paths)
        identity_after = runtime_db.lstat()
        assert (
            identity_after.st_dev,
            identity_after.st_ino,
            identity_after.st_size,
            identity_after.st_mtime_ns,
        ) == stable_main_identity
    finally:
        for connection in external_connections:
            connection.close()
    assert injected is True
    _assert_no_snapshot_candidate(paths)


@pytest.mark.parametrize(
    "race",
    (
        "task_commit_between_backups",
        "projection_atomic_replace",
        "projection_in_place_mutation",
        "runtime_inode_replace",
    ),
)
def test_snapshot_stable_window_rejects_interleaved_source_races(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    race: str,
) -> None:
    paths = _coherent_snapshot_source(tmp_path, monkeypatch)
    original_backup = snapshot._backup_sqlite_connection
    external_connections: list[sqlite3.Connection] = []
    injected = False

    def racing_backup(
        reader: sqlite3.Connection,
        destination: Path,
        *,
        source_name: str,
    ) -> None:
        nonlocal injected
        original_backup(reader, destination, source_name=source_name)
        if injected:
            return
        if race == "task_commit_between_backups" and source_name == "runtime.db":
            writer = sqlite3.connect(paths["tasks_db"])
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("INSERT INTO evidence(value) VALUES ('task-race')")
            writer.commit()
            external_connections.append(writer)
            injected = True
        elif race == "runtime_inode_replace" and source_name == "runtime.db":
            replacement = paths["runtime_db"].with_name(".runtime-replacement.db")
            with sqlite3.connect(paths["runtime_db"]) as source_connection:
                with sqlite3.connect(replacement) as replacement_connection:
                    source_connection.backup(replacement_connection)
                    assert replacement_connection.execute(
                        "PRAGMA integrity_check"
                    ).fetchone() == ("ok",)
            replacement.chmod(0o600)
            os.replace(replacement, paths["runtime_db"])
            injected = True
        elif source_name == "tasks.db" and race == "projection_atomic_replace":
            replacement = paths["projection"].with_name(".projection-replacement")
            replacement.write_bytes(paths["projection"].read_bytes())
            replacement.chmod(0o600)
            os.replace(replacement, paths["projection"])
            injected = True
        elif source_name == "tasks.db" and race == "projection_in_place_mutation":
            raw = paths["projection"].read_bytes()
            changed = raw.replace(b'"SADHANA"', b'"XADHANA"', 1)
            assert changed != raw and len(changed) == len(raw)
            with paths["projection"].open("r+b", buffering=0) as projection_file:
                projection_file.write(changed)
                os.fsync(projection_file.fileno())
            injected = True

    monkeypatch.setattr(snapshot, "_backup_sqlite_connection", racing_backup)
    try:
        with pytest.raises(
            snapshot.SnapshotError,
            match="stable window|SQLite source identity changed",
        ):
            _create_coherent_snapshot(paths)
    finally:
        for connection in external_connections:
            connection.close()
    assert injected is True
    _assert_no_snapshot_candidate(paths)


def test_snapshot_rejects_a_stable_but_stale_owner_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _coherent_snapshot_source(tmp_path, monkeypatch)
    _set_runtime_mission_title(paths["runtime_db"], "SADHANA-CHANGED")

    with pytest.raises(
        snapshot.SnapshotError,
        match="projection differs from canonical owner state",
    ):
        _create_coherent_snapshot(paths)

    _assert_no_snapshot_candidate(paths)


def test_snapshot_rejects_needs_task_projection_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _coherent_snapshot_source(
        tmp_path,
        monkeypatch,
        reconciliation="needs_task_projection",
    )

    with pytest.raises(
        snapshot.SnapshotError,
        match="snapshot reconciliation is not coherent",
    ):
        _create_coherent_snapshot(paths)

    _assert_no_snapshot_candidate(paths)


def test_snapshot_rejects_json_valid_resealed_wrong_projection_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _coherent_snapshot_source(tmp_path, monkeypatch)
    payload = json.loads(paths["projection"].read_text(encoding="utf-8"))
    payload["projection_schema_version"] = "dharma.mission_control.read_model.v0"
    _reseal_projection(paths["projection"], payload)

    with pytest.raises(
        snapshot.SnapshotError,
        match="projection schema or content digest differs",
    ):
        _create_coherent_snapshot(paths)

    _assert_no_snapshot_candidate(paths)


def test_snapshot_manifest_rejects_resealed_consistency_claim_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _coherent_snapshot_source(tmp_path, monkeypatch)
    candidate = _create_coherent_snapshot(paths)
    manifest_path = candidate / "snapshot-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["consistency_proof"]["claim"] = "independent_consistent_copies"
    _reseal_snapshot_manifest(candidate, payload)

    with pytest.raises(
        snapshot.SnapshotError,
        match="snapshot consistency proof binding differs",
    ):
        snapshot._snapshot_manifest(
            candidate,
            allowed_uids=frozenset({os.geteuid()}),
        )


def test_snapshot_capacity_blocks_before_staging_and_surfaces_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    projection_root = tmp_path / "projection-source"
    snapshots = tmp_path / "snapshots"
    staging = tmp_path / "snapshot-staging"
    _database(state / "state/runtime.db", "runtime")
    _database(state / "db/tasks.db", "tasks")
    projection = projection_root / "mission-projection.json"
    _write_coherent_projection(
        projection,
        runtime_db=state / "state/runtime.db",
        tasks_db=state / "db/tasks.db",
    )
    monkeypatch.setattr(snapshot, "STATE_ROOT", state)
    monkeypatch.setattr(snapshot, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(snapshot, "SNAPSHOT_ROOT", snapshots)
    monkeypatch.setattr(snapshot, "SNAPSHOT_STAGING_ROOT", staging)

    class _NoCapacity:
        f_bavail = 1
        f_frsize = 1

    with pytest.raises(snapshot.SnapshotError, match="blocked before staging"):
        snapshot.create_snapshot(
            release_sha="a" * 40,
            state_root=state,
            projection_path=projection,
            snapshot_root=snapshots,
            now=datetime(2026, 8, 23, tzinfo=timezone.utc),
            statvfs=lambda _path: _NoCapacity(),
        )
    readiness = json.loads(
        (staging / snapshot.READINESS_RECEIPT_NAME).read_text(encoding="utf-8")
    )
    assert readiness["status"] == "snapshot_blocked"
    assert readiness["silent_deletion_allowed"] is False
    assert readiness["standby_capacity_proven"] is False
    assert not any(path.name.startswith(".snapshot-") for path in staging.iterdir())


def test_snapshot_rejects_exact_stop_and_fsyncs_published_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    projection_root = tmp_path / "projection-source"
    snapshots = tmp_path / "snapshots"
    staging = tmp_path / "snapshot-staging"
    _database(state / "state/runtime.db", "runtime")
    _database(state / "db/tasks.db", "tasks")
    projection = projection_root / "mission-projection.json"
    _write_coherent_projection(
        projection,
        runtime_db=state / "state/runtime.db",
        tasks_db=state / "db/tasks.db",
    )
    monkeypatch.setattr(snapshot, "STATE_ROOT", state)
    monkeypatch.setattr(snapshot, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(snapshot, "SNAPSHOT_ROOT", snapshots)
    monkeypatch.setattr(snapshot, "SNAPSHOT_STAGING_ROOT", staging)
    with pytest.raises(snapshot.SnapshotError, match="outside the exact"):
        snapshot.create_snapshot(
            release_sha="a" * 40,
            state_root=state,
            projection_path=projection,
            snapshot_root=snapshots,
            now=snapshot.CAMPAIGN_STOP_UTC,
        )
    assert not snapshots.exists()

    real_fsync = snapshot.os.fsync
    fsynced_snapshot_root = False

    def recording_fsync(descriptor: int) -> None:
        nonlocal fsynced_snapshot_root
        identity = os.fstat(descriptor)
        if (
            staging.exists()
            and stat.S_ISDIR(identity.st_mode)
            and identity.st_dev == staging.lstat().st_dev
            and identity.st_ino == staging.lstat().st_ino
        ):
            fsynced_snapshot_root = True
        real_fsync(descriptor)

    monkeypatch.setattr(snapshot.os, "fsync", recording_fsync)
    monkeypatch.setattr(snapshot, "MIN_FREE_RESERVE_BYTES", 0)
    monkeypatch.setattr(snapshot, "MAX_CAMPAIGN_SNAPSHOTS", 1)
    snapshot.create_snapshot(
        release_sha="a" * 40,
        state_root=state,
        projection_path=projection,
        snapshot_root=snapshots,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    assert fsynced_snapshot_root


def test_snapshot_rejects_projection_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    projection_root = tmp_path / "projection-source"
    snapshots = tmp_path / "snapshots"
    staging = tmp_path / "snapshot-staging"
    _database(state / "state/runtime.db", "runtime")
    _database(state / "db/tasks.db", "tasks")
    projection_root.mkdir()
    real = projection_root / "real.json"
    real.write_text("{}\n", encoding="utf-8")
    real.chmod(0o600)
    link = projection_root / "status.json"
    link.symlink_to(real)
    monkeypatch.setattr(snapshot, "STATE_ROOT", state)
    monkeypatch.setattr(snapshot, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(snapshot, "SNAPSHOT_ROOT", snapshots)
    monkeypatch.setattr(snapshot, "SNAPSHOT_STAGING_ROOT", staging)
    with pytest.raises(snapshot.SnapshotError):
        snapshot.create_snapshot(
            release_sha="a" * 40,
            state_root=state,
            projection_path=link,
            snapshot_root=snapshots,
        )


def test_snapshot_replication_receipt_keeps_standby_fenced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    projection_root = tmp_path / "projection-source"
    snapshots = tmp_path / "snapshots"
    staging = tmp_path / "snapshot-staging"
    claims = tmp_path / "snapshot-finalizing"
    quarantine = tmp_path / "snapshot-quarantine"
    receipts = tmp_path / "snapshot-receipts"
    outbox = tmp_path / "snapshot-outbox"
    _database(state / "state/runtime.db", "runtime")
    _database(state / "db/tasks.db", "tasks")
    projection = projection_root / "mission-projection.json"
    _write_coherent_projection(
        projection,
        runtime_db=state / "state/runtime.db",
        tasks_db=state / "db/tasks.db",
    )
    monkeypatch.setattr(snapshot, "STATE_ROOT", state)
    monkeypatch.setattr(snapshot, "PROJECTION_SOURCE_ROOT", projection_root)
    monkeypatch.setattr(snapshot, "SNAPSHOT_ROOT", snapshots)
    monkeypatch.setattr(snapshot, "SNAPSHOT_STAGING_ROOT", staging)
    monkeypatch.setattr(snapshot, "MIN_FREE_RESERVE_BYTES", 0)
    monkeypatch.setattr(snapshot, "MAX_CAMPAIGN_SNAPSHOTS", 1)
    candidate = snapshot.create_snapshot(
        release_sha="a" * 40,
        state_root=state,
        projection_path=projection,
        snapshot_root=snapshots,
        now=datetime(2026, 8, 23, tzinfo=timezone.utc),
    )
    uid = os.geteuid()
    gid = os.getegid()
    snap, replayed = snapshot.finalize_local_snapshot(
        candidate,
        staging_root=staging,
        claim_root=claims,
        snapshot_root=snapshots,
        quarantine_root=quarantine,
        receipt_root=receipts,
        outbox_root=outbox,
        expected_release_sha="a" * 40,
        expected_root_uid=uid,
        expected_root_gid=gid,
        expected_service_uid=uid,
    )
    assert replayed is False
    assert stat.S_IMODE(snap.stat().st_mode) == 0o500
    assert all(stat.S_IMODE((snap / name).stat().st_mode) == 0o400 for name in snapshot.SNAPSHOT_FILE_NAMES)
    key = tmp_path / "replication.key"
    key.write_text("fixture\n", encoding="utf-8")
    key.chmod(0o600)
    known = tmp_path / "known_hosts"
    known.write_text("fixture\n", encoding="utf-8")
    known.chmod(0o600)
    calls: list[tuple[str, ...]] = []

    def runner(argv, **kwargs):  # noqa: ANN001, ANN202
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    receipt = snapshot.replicate_snapshot(
        snap,
        ssh_key=key,
        known_hosts=known,
        receipt_root=receipts,
        expected_root_uid=uid,
        expected_root_gid=gid,
        runner=runner,
    )
    payload = json.loads(receipt.read_text())
    assert payload["writer_authority_transferred"] is False
    assert payload["standby_activation_requested"] is False
    assert payload["status"] == "standby_acceptance_exactly_confirmed"
    assert payload["standby_hash_verified"] is True
    assert payload["standby_restore_verified"] is True
    assert len(calls) == 3 and calls[0][0] == snapshot.RSYNC_PATH
    assert all("--protect-args" not in command for command in calls)
    transport = calls[0][calls[0].index("-e") + 1]
    assert f"{snapshot.SSH_PATH} -p 2222 -i " in transport
    assert "-o IdentitiesOnly=yes" in transport
    assert "-o PasswordAuthentication=no" in transport
    assert "-o KbdInteractiveAuthentication=no" in transport
    assert payload["standby_port"] == 2222
    assert (
        payload["ssh_transport_policy_sha256"]
        == snapshot.standby_ssh_policy_digest()
    )
    assert "--no-owner" in calls[0]
    assert "--no-group" in calls[0]
    assert "--ignore-existing" in calls[0]
    assert calls[0][-1].endswith(f":{snapshot.STANDBY_UPLOAD_RELATIVE_ROOT}/{snap.name}.upload-{json.loads((snap / 'snapshot-manifest.json').read_text())['snapshot_digest']}/")
    assert "--dry-run" in calls[2]
    assert "--checksum" in calls[2]
    assert "--itemize-changes" in calls[2]
    assert "--ignore-existing" not in calls[2]
    assert calls[2][-1].startswith(
        f"{snapshot.STANDBY_DESTINATION}:{snapshot.STANDBY_ACK_RELATIVE_ROOT}/"
    )


def test_nonterminal_upload_attempt_never_suppresses_ack_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    topology = _finalized_writer_snapshot(tmp_path, monkeypatch)
    final = topology["final"]
    receipts = topology["receipts"]
    key = tmp_path / "replication.key"
    key.write_bytes(b"fixture")
    key.chmod(0o600)
    known = tmp_path / "known_hosts"
    known.write_bytes(b"fixture")
    known.chmod(0o600)
    first_calls: list[tuple[str, ...]] = []

    def ack_missing(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        first_calls.append(command)
        stdout = ">fc........\n" if "--dry-run" in command else ""
        return subprocess.CompletedProcess(command, 0, stdout, "")

    with pytest.raises(snapshot.SnapshotError, match="ACK is not yet exact"):
        snapshot.replicate_snapshot(
            final,
            ssh_key=key,
            known_hosts=known,
            receipt_root=receipts,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            runner=ack_missing,
        )
    assert len(first_calls) == 3
    assert (receipts / f"{final.name}.writer-upload-attempt.v1.json").exists()
    assert not (
        receipts / f"{final.name}.writer-standby-confirmed.v1.json"
    ).exists()

    retry_calls: list[tuple[str, ...]] = []

    def ack_exact(argv, **_kwargs):  # noqa: ANN001, ANN202
        command = tuple(argv)
        retry_calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    confirmation = snapshot.replicate_snapshot(
        final,
        ssh_key=key,
        known_hosts=known,
        receipt_root=receipts,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
        runner=ack_exact,
    )
    assert len(retry_calls) == 3, "the prior attempt receipt must not short-circuit"
    confirmed = json.loads(confirmation.read_text(encoding="utf-8"))
    assert confirmed["standby_hash_verified"] is True
    assert confirmed["standby_restore_verified"] is True


def test_pending_outbox_is_fair_when_oldest_item_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outbox_root = tmp_path / "outbox"
    snapshot_root = tmp_path / "snapshots"
    receipt_root = tmp_path / "receipts"
    outbox_root.mkdir()
    snapshot_root.mkdir()
    first_id = "20260822T171512Z-aaaaaaaaaaaa"
    second_id = "20260822T171513Z-aaaaaaaaaaaa"
    for snapshot_id in (first_id, second_id):
        (outbox_root / f"{snapshot_id}.outbox.v1.json").write_bytes(b"fixture")
        (snapshot_root / snapshot_id).mkdir()

    attempted: list[str] = []

    def admit(path: Path, **_kwargs):  # noqa: ANN003, ANN202
        match = snapshot._OUTBOX_ENTRY_RE.fullmatch(path.name)
        assert match is not None
        return snapshot_root / match.group("snapshot")

    def replicate(candidate: Path, **_kwargs):  # noqa: ANN003, ANN202
        attempted.append(candidate.name)
        if candidate.name == first_id:
            raise snapshot.SnapshotError("irreparable oldest snapshot")
        receipt = receipt_root / f"{candidate.name}.confirmed.json"
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_bytes(b"confirmed")
        return receipt

    monkeypatch.setattr(snapshot, "_validate_snapshot_outbox", admit)
    monkeypatch.setattr(snapshot, "replicate_snapshot", replicate)
    with pytest.raises(snapshot.SnapshotError, match=first_id):
        snapshot.replicate_pending_outbox(
            ssh_key=tmp_path / "unused-key",
            outbox_root=outbox_root,
            snapshot_root=snapshot_root,
            receipt_root=receipt_root,
            expected_release_sha="a" * 40,
        )
    assert attempted == [first_id, second_id]
    assert (receipt_root / f"{second_id}.confirmed.json").exists()


def test_standby_reconciliation_attempts_later_ready_upload_after_first_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    incoming = tmp_path / "incoming"
    claims = tmp_path / "claims"
    quarantine = tmp_path / "quarantine"
    receipts = tmp_path / "receipts"
    incoming.mkdir()
    first = incoming / (
        "20260822T171512Z-aaaaaaaaaaaa.upload-" + "1" * 64
    )
    second = incoming / (
        "20260822T171513Z-aaaaaaaaaaaa.upload-" + "2" * 64
    )
    for upload in (first, second):
        upload.mkdir()
        (upload / ".ready.json").write_bytes(b"fixture")
    attempted: list[str] = []

    def finalize(upload: Path, **_kwargs):  # noqa: ANN003, ANN202
        attempted.append(upload.name)
        if upload == first:
            raise snapshot.SnapshotError("source-substitution-during-claim")
        return upload, receipts / "accepted.json", False

    monkeypatch.setattr(snapshot, "finalize_standby_upload", finalize)
    with pytest.raises(snapshot.SnapshotError, match="source-substitution"):
        snapshot.finalize_pending_standby(
            incoming_root=incoming,
            claim_root=claims,
            quarantine_root=quarantine,
            receipt_root=receipts,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert attempted == [first.name, second.name]


@pytest.mark.parametrize(
    ("race", "expected_error"),
    (
        ("unsafe-claim", "unsafe incoming entry changed"),
        ("disappear", "incoming-entry-disappeared"),
    ),
)
def test_unsafe_or_disappearing_incoming_entry_cannot_starve_later_ready_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    race: str,
    expected_error: str,
) -> None:
    incoming = tmp_path / "incoming"
    claims = tmp_path / "claims"
    quarantine = tmp_path / "quarantine"
    receipts = tmp_path / "receipts"
    incoming.mkdir()
    poison = incoming / (
        "20260822T171512Z-aaaaaaaaaaaa.upload-" + "1" * 64
    )
    poison.write_bytes(b"poison")
    valid = incoming / (
        "20260822T171513Z-aaaaaaaaaaaa.upload-" + "2" * 64
    )
    valid.mkdir()
    (valid / ".ready.json").write_bytes(b"fixture")
    attempted: list[str] = []

    if race == "unsafe-claim":

        def raced_claim(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
            raise snapshot.SnapshotError("unsafe incoming entry changed during root claim")

        monkeypatch.setattr(snapshot, "_claim_unsafe_incoming_entry", raced_claim)
    else:
        original_lstat = Path.lstat
        removed = False

        def disappearing_lstat(path: Path):  # noqa: ANN202
            nonlocal removed
            if path == poison and not removed:
                removed = True
                poison.unlink()
            return original_lstat(path)

        monkeypatch.setattr(Path, "lstat", disappearing_lstat)

    def finalize(upload: Path, **_kwargs):  # noqa: ANN003, ANN202
        attempted.append(upload.name)
        return upload, receipts / "accepted.json", False

    monkeypatch.setattr(snapshot, "finalize_standby_upload", finalize)
    with pytest.raises(snapshot.SnapshotError, match=expected_error):
        snapshot.finalize_pending_standby(
            incoming_root=incoming,
            claim_root=claims,
            quarantine_root=quarantine,
            receipt_root=receipts,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert attempted == [valid.name]


@pytest.mark.parametrize(
    "generated_at,expected_error",
    (
        ("2026-13-23T00:00:00+00:00", "generated_at is invalid"),
        ("2026-09-02T00:00:00+00:00", "generated_at binding differs"),
        ("2026-08-23T00:00:01+00:00", "generated_at binding differs"),
    ),
)
def test_snapshot_manifest_binds_valid_campaign_second_and_release_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    generated_at: str,
    expected_error: str,
) -> None:
    source = _finalized_writer_snapshot(tmp_path / "writer", monkeypatch)["final"]
    candidate = tmp_path / "candidate" / source.name
    candidate.parent.mkdir()
    shutil.copytree(source, candidate)
    candidate.chmod(0o700)
    for child in candidate.iterdir():
        child.chmod(0o600)
    manifest_path = candidate / "snapshot-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["generated_at"] = generated_at
    unsigned = dict(payload)
    unsigned.pop("snapshot_digest")
    payload["snapshot_digest"] = hashlib.sha256(
        snapshot._canonical_bytes(unsigned)
    ).hexdigest()
    manifest_path.write_bytes(snapshot._canonical_bytes(payload) + b"\n")
    with pytest.raises(snapshot.SnapshotError, match=expected_error):
        snapshot._snapshot_manifest(
            candidate, allowed_uids=frozenset({os.geteuid()})
        )

    wrong_prefix = candidate.with_name(candidate.name[:-12] + "b" * 12)
    candidate.rename(wrong_prefix)
    payload["generated_at"] = "2026-08-23T00:00:00+00:00"
    payload["snapshot_id"] = wrong_prefix.name
    unsigned = dict(payload)
    unsigned.pop("snapshot_digest")
    payload["snapshot_digest"] = hashlib.sha256(
        snapshot._canonical_bytes(unsigned)
    ).hexdigest()
    manifest_path = wrong_prefix / "snapshot-manifest.json"
    manifest_path.write_bytes(snapshot._canonical_bytes(payload) + b"\n")
    with pytest.raises(snapshot.SnapshotError, match="binding differs"):
        snapshot._snapshot_manifest(
            wrong_prefix, allowed_uids=frozenset({os.geteuid()})
        )


def test_immutable_publication_fsyncs_after_final_custody_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    original_fchown = snapshot.os.fchown
    original_fchmod = snapshot.os.fchmod
    original_fsync = snapshot.os.fsync

    def record_chown(descriptor: int, uid: int, gid: int) -> None:
        events.append("chown")
        original_fchown(descriptor, uid, gid)

    def record_chmod(descriptor: int, mode: int) -> None:
        events.append("chmod")
        original_fchmod(descriptor, mode)

    def record_fsync(descriptor: int) -> None:
        if stat.S_ISREG(os.fstat(descriptor).st_mode):
            events.append("file-fsync")
        original_fsync(descriptor)

    monkeypatch.setattr(snapshot.os, "fchown", record_chown)
    monkeypatch.setattr(snapshot.os, "fchmod", record_chmod)
    monkeypatch.setattr(snapshot.os, "fsync", record_fsync)
    snapshot._write_immutable_receipt(
        tmp_path / "receipts" / "terminal.json",
        {"schema_version": "fixture.v1", "status": "PASS"},
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert events == ["chown", "chmod", "file-fsync"]


def test_standby_quarantines_poison_then_finalizes_and_exactly_replays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _finalized_writer_snapshot(tmp_path / "writer", monkeypatch)
    source = writer["final"]
    uploads = tmp_path / "standby-incoming" / "uploads"
    acks = tmp_path / "standby-incoming" / "acks"
    claims = tmp_path / "standby-claims"
    finals = tmp_path / "standby-snapshots"
    quarantine = tmp_path / "standby-quarantine"
    receipts = tmp_path / "standby-receipts"
    uploads.mkdir(parents=True, mode=0o700)
    acks.mkdir(parents=True, mode=0o750)
    os.chown(acks, -1, os.getegid())
    acks.chmod(0o750)
    poison_name = (
        "20260822T000000Z-bbbbbbbbbbbb.upload-" + "b" * 64
    )
    poison = uploads / poison_name
    poison.write_bytes(b"namespace poison")
    poison.chmod(0o600)
    _stage_standby_upload(source, uploads)
    common = {
        "incoming_root": uploads,
        "ack_root": acks,
        "claim_root": claims,
        "snapshot_root": finals,
        "quarantine_root": quarantine,
        "receipt_root": receipts,
        "expected_root_uid": os.geteuid(),
        "expected_root_gid": os.getegid(),
        "expected_service_uid": os.geteuid(),
        "expected_service_gid": os.getegid(),
        "expected_release_sha": "a" * 40,
    }
    results = snapshot.finalize_pending_standby(**common)
    assert len(results) == 1
    final, acceptance, replayed = results[0]
    assert replayed is False
    assert not poison.exists()
    quarantined = list(quarantine.iterdir())
    assert len(quarantined) == 1
    quarantine_receipts = [
        path
        for path in receipts.iterdir()
        if path.name.startswith("quarantine-")
    ]
    assert len(quarantine_receipts) == 1
    quarantine_payload = json.loads(quarantine_receipts[0].read_text())
    assert quarantine_payload["status"] == "quarantined_no_acceptance"
    assert quarantine_payload["snapshot_accepted"] is False
    assert quarantine_payload["source_entry_name"] == poison_name
    acceptance_bytes = acceptance.read_bytes()
    ack = acks / f"{source.name}.standby-acceptance.v1.json"
    assert ack.read_bytes() == acceptance_bytes
    assert stat.S_IMODE(ack.stat().st_mode) == 0o440
    assert stat.S_IMODE(final.stat().st_mode) == 0o500
    assert (
        receipts / f"{source.name}.restore-drill.v1.json"
    ).exists(), "standby acceptance requires a pre-publish restore/hash drill"

    _stage_standby_upload(source, uploads)
    replay_results = snapshot.finalize_pending_standby(**common)
    assert len(replay_results) == 1
    assert replay_results[0][2] is True
    assert acceptance.read_bytes() == acceptance_bytes
    assert ack.read_bytes() == acceptance_bytes


def test_standby_rejects_a_coherent_tree_swap_across_custody_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = _finalized_writer_snapshot(tmp_path / "writer", monkeypatch)
    source = writer["final"]
    uploads = tmp_path / "standby-incoming" / "uploads"
    acks = tmp_path / "standby-incoming" / "acks"
    claims = tmp_path / "standby-claims"
    finals = tmp_path / "standby-snapshots"
    quarantine = tmp_path / "standby-quarantine"
    receipts = tmp_path / "standby-receipts"
    uploads.mkdir(parents=True, mode=0o700)
    acks.mkdir(parents=True, mode=0o750)
    os.chown(acks, -1, os.getegid())
    acks.chmod(0o750)
    _stage_standby_upload(source, uploads)
    original = snapshot._materialize_frozen_copy

    def swap_then_copy(candidate: Path, **kwargs):  # noqa: ANN003, ANN202
        _rewrite_snapshot_runtime_coherently(candidate)
        return original(candidate, **kwargs)

    monkeypatch.setattr(snapshot, "_materialize_frozen_copy", swap_then_copy)
    with pytest.raises(snapshot.SnapshotError, match="custody transition"):
        snapshot.finalize_pending_standby(
            incoming_root=uploads,
            ack_root=acks,
            claim_root=claims,
            snapshot_root=finals,
            quarantine_root=quarantine,
            receipt_root=receipts,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            expected_service_uid=os.geteuid(),
            expected_service_gid=os.getegid(),
            expected_release_sha="a" * 40,
        )
    assert not list(finals.iterdir())
    assert not list(acks.iterdir())
    assert len(list(quarantine.iterdir())) == 2
    assert len(list(receipts.glob("quarantine-*.v1.json"))) == 2


def test_standby_rejects_resealed_semantic_mismatch_despite_sqlite_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writer = _finalized_writer_snapshot(tmp_path / "writer", monkeypatch)
    source = writer["final"]
    uploads = tmp_path / "standby-incoming" / "uploads"
    acks = tmp_path / "standby-incoming" / "acks"
    claims = tmp_path / "standby-claims"
    finals = tmp_path / "standby-snapshots"
    quarantine = tmp_path / "standby-quarantine"
    receipts = tmp_path / "standby-receipts"
    upload = _stage_standby_upload(source, uploads)
    uploaded_runtime = upload / "runtime.db"
    uploaded_runtime.chmod(0o600)
    _set_runtime_mission_title(uploaded_runtime, "RESEALED-BUT-STALE")
    with sqlite3.connect(uploaded_runtime) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    upload = _reseal_standby_upload_after_file_change(upload)
    acks.mkdir(parents=True, mode=0o750)
    os.chown(acks, -1, os.getegid())
    acks.chmod(0o750)

    with pytest.raises(
        snapshot.SnapshotError,
        match="projection differs from canonical owner state",
    ):
        snapshot.finalize_standby_upload(
            upload,
            incoming_root=uploads,
            ack_root=acks,
            claim_root=claims,
            snapshot_root=finals,
            quarantine_root=quarantine,
            receipt_root=receipts,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
            expected_service_uid=os.geteuid(),
            expected_service_gid=os.getegid(),
            expected_release_sha="a" * 40,
        )

    assert not list(finals.iterdir())
    assert not list(acks.iterdir())
    assert len(list(quarantine.iterdir())) == 1
    assert len(list(receipts.glob("quarantine-*.v1.json"))) == 1


def test_receipt_publication_recovers_partial_and_post_promote_faults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = tmp_path / "snapshot-receipts" / "terminal.json"
    payload = {"schema_version": "fixture.v1", "status": "PASS"}
    original_rename = snapshot._rename_noreplace

    def fail_before_promote(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
        raise snapshot.SnapshotError("injected pre-promotion crash")

    monkeypatch.setattr(snapshot, "_rename_noreplace", fail_before_promote)
    with pytest.raises(snapshot.SnapshotError, match="pre-promotion"):
        snapshot._write_immutable_receipt(
            receipt,
            payload,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert not receipt.exists()
    partials = list(receipt.parent.glob(".partial-*"))
    assert len(partials) == 1

    monkeypatch.setattr(snapshot, "_rename_noreplace", original_rename)
    snapshot._write_immutable_receipt(
        receipt,
        payload,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert receipt.read_bytes() == snapshot._canonical_bytes(payload) + b"\n"
    assert len(list((receipt.parent / ".incomplete").iterdir())) == 1

    second = receipt.parent / "post-promote.json"
    original_fsync_directory = snapshot._fsync_directory
    injected = False

    def fail_after_promote(path: Path) -> None:
        nonlocal injected
        if path == second.parent and second.exists() and not injected:
            injected = True
            raise snapshot.SnapshotError("injected parent-fsync crash")
        original_fsync_directory(path)

    monkeypatch.setattr(snapshot, "_fsync_directory", fail_after_promote)
    with pytest.raises(snapshot.SnapshotError, match="parent-fsync"):
        snapshot._write_immutable_receipt(
            second,
            payload,
            expected_root_uid=os.geteuid(),
            expected_root_gid=os.getegid(),
        )
    assert second.read_bytes() == snapshot._canonical_bytes(payload) + b"\n"
    snapshot._write_immutable_receipt(
        second,
        payload,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )


def test_exact_publication_race_cleans_losing_temp_and_ack_replay_fsyncs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = tmp_path / "snapshot-receipts" / "terminal.json"
    payload = {"schema_version": "fixture.v1", "status": "PASS"}
    raw = snapshot._canonical_bytes(payload) + b"\n"
    original_rename = snapshot._rename_noreplace
    raced = False

    def exact_winner_then_collision(
        source_name: str,
        destination_name: str,
        *,
        source_dir_fd: int,
        destination_dir_fd: int,
    ) -> None:
        nonlocal raced
        if destination_name == receipt.name and not raced:
            raced = True
            receipt.write_bytes(raw)
            os.chown(receipt, -1, os.getegid())
            receipt.chmod(0o400)
            raise snapshot.SnapshotError("destination already exists")
        original_rename(
            source_name,
            destination_name,
            source_dir_fd=source_dir_fd,
            destination_dir_fd=destination_dir_fd,
        )

    monkeypatch.setattr(snapshot, "_rename_noreplace", exact_winner_then_collision)
    snapshot._write_immutable_receipt(
        receipt,
        payload,
        expected_root_uid=os.geteuid(),
        expected_root_gid=os.getegid(),
    )
    assert receipt.read_bytes() == raw
    assert not list(receipt.parent.glob(".partial-*"))
    assert len(list((receipt.parent / ".incomplete").iterdir())) == 1

    ack_root = tmp_path / "acks"
    ack_root.mkdir(mode=0o750)
    os.chown(ack_root, -1, os.getegid())
    ack_root.chmod(0o750)
    ack = ack_root / "accepted.json"
    snapshot._write_standby_acceptance_ack(
        ack,
        payload,
        expected_root_uid=os.geteuid(),
        expected_service_gid=os.getegid(),
    )
    fsynced: list[Path] = []
    original_fsync_directory = snapshot._fsync_directory

    def record_directory(path: Path) -> None:
        fsynced.append(path)
        original_fsync_directory(path)

    monkeypatch.setattr(snapshot, "_fsync_directory", record_directory)
    snapshot._write_standby_acceptance_ack(
        ack,
        payload,
        expected_root_uid=os.geteuid(),
        expected_service_gid=os.getegid(),
    )
    assert ack_root in fsynced


def test_static_topology_has_exact_stop_private_serve_and_no_standby_enable() -> None:
    root = Path(__file__).resolve().parents[1] / "deploy/sadhana/systemd"
    texts = {path.name: path.read_text(encoding="utf-8") for path in root.iterdir()}
    combined = "\n".join(texts.values())
    assert "OnCalendar=2026-09-01 17:15:12 UTC" in combined
    assert "--host 127.0.0.1 --port ${SADHANA_API_PORT}" in combined
    assert "3000" not in combined
    assert "User=dharma-sadhana-dashboard" in combined
    assert (
        "SADHANA_DASHBOARD_SOCKET=/run/dharma-sadhana/dashboard/constellation.sock"
        in combined
    )
    assert (
        "/usr/bin/node /opt/dharma-sadhana/releases/@RELEASE_SHA@/deploy/sadhana/"
        in combined
    )
    assert "ExecStart=/usr/bin/npm" not in combined
    assert (
        "sadhana_release.py tailscale-start --role writer --release-sha "
        "@RELEASE_SHA@" in combined
    )
    assert (
        "sadhana_release.py tailscale-stop --role writer --release-sha "
        "@RELEASE_SHA@" in combined
    )
    assert (
        "Environment=SADHANA_CONTROL_INTERNAL_URL="
        "http://127.0.0.1:18421/v1/operator-control/requests" in combined
    )
    private_serve = texts["dharma-sadhana-private-serve.service"]
    assert (
        "ReadWritePaths=/etc/dharma-sadhana/receipts/preactivation"
        in private_serve
    )
    assert "ReadWritePaths=/run/dharma-sadhana/tailscale" not in private_serve
    assert "ConditionPathExists=/etc/dharma-sadhana/writer-enabled" in combined
    local_watch = texts["dharma-sadhana-snapshot-finalize.path"]
    standby_watch = texts["dharma-sadhana-standby-snapshot-receiver.path"]
    assert "PathExistsGlob=" in local_watch
    assert "DirectoryNotEmpty=/var/lib/dharma-sadhana/snapshot-staging" not in local_watch
    assert "PathExistsGlob=" in standby_watch
    assert (
        "DirectoryNotEmpty=/var/lib/dharma-sadhana/snapshot-incoming"
        not in standby_watch
    )
    assert (
        "Unit=dharma-sadhana-snapshot-finalize.service"
        in texts["dharma-sadhana-snapshot-retry.timer"]
    )
    assert (
        "Unit=dharma-sadhana-standby-snapshot-receiver.service"
        in texts["dharma-sadhana-standby-snapshot-receiver.timer"]
    )
    assert (
        "EnvironmentFile=/etc/dharma-sadhana/verifier.env"
        in texts["dharma-sadhana-supervisor.service.in"]
    )
    assert combined.count("PartOf=dharma-sadhana.target") == 22
    health_barrier = texts["dharma-sadhana-observer-health.service.in"]
    supervisor = texts["dharma-sadhana-supervisor.service.in"]
    assert "Requires=dharma-sadhana-api.service" in health_barrier
    assert "After=dharma-sadhana-api.service" in health_barrier
    assert (
        "Before=dharma-sadhana-dispatch-enable.service "
        "dharma-sadhana-supervisor.service" in health_barrier
    )
    assert "probe-observer-health --role writer --release-sha " in health_barrier
    assert "dharma-sadhana-observer-health.service" in supervisor
    assert "WantedBy=dharma-sadhana-dispatch.target" in supervisor
    assert (
        "LoadCredential=control_hmac_key:/etc/dharma-sadhana/credentials/"
        "control_hmac_key" in supervisor
    )
    assert "LoadCredential=dispatch_activation_receipt:" in supervisor
    assert "LoadCredential=observer_health_receipt:" in supervisor
    assert "LoadCredential=runtime_binding_activation:" in supervisor
    assert (
        "EnvironmentFile=/etc/dharma-sadhana/supervisor-runtime.env"
        in supervisor
    )
    assert "--operator-control-hmac-credential" not in supervisor
    assert "--operator-control-hmac-sha256" not in supervisor
    for flag in (
        "--authority-manifest /etc/dharma-sadhana/inputs/runtime/"
        "sadhana-10-20260823/authority-manifest.json",
        "--observed-input-manifest /etc/dharma-sadhana/inputs/runtime/"
        "sadhana-10-20260823/observed-inputs.json",
        "--held-out-oracle-manifest /etc/dharma-sadhana/inputs/runtime/"
        "sadhana-10-20260823/held-out-oracle.json",
    ):
        assert supervisor.count(flag) == 1
    preparation = texts["dharma-sadhana-runtime-prepare.service.in"]
    assert "User=dharma-sadhana" in preparation
    assert "PrivateNetwork=true" in preparation
    assert "RemainAfterExit=yes" in preparation
    assert release.RUNTIME_PREPARATION_UNIT in release.CAMPAIGN_UNITS
    assert release.RUNTIME_PREPARATION_UNIT in release._ROLLBACK_QUIET_UNITS
    assert "WantedBy=" not in preparation
    assert "[Install]" not in preparation
    assert "PartOf=" not in preparation
    assert "LoadCredential=" not in preparation
    assert "HMAC" not in preparation.upper()
    assert "API_KEY" not in preparation.upper()
    assert (
        "EnvironmentFile=/etc/dharma-sadhana/receipts/releases/"
        "@RELEASE_SHA@/runtime-prep.env" in preparation
    )
    assert "EnvironmentFile=/etc/dharma-sadhana/supervisor.env" not in preparation
    assert preparation.count("EnvironmentFile=") == 1
    assert (
        "--release-admission-receipt "
        "${SADHANA_PREP_RELEASE_ADMISSION_RECEIPT}" in preparation
    )
    assert (
        "--manifest-staging-root ${SADHANA_PREP_MANIFEST_STAGING_ROOT}"
        in preparation
    )
    assert "--verifier-seat ${SADHANA_PREP_VERIFIER_SEAT}" in preparation
    assert (
        "/var/lib/dharma-sadhana/state/release-admission/"
        "staged-release-admission.v1.json" in preparation
    )
    predispatch = texts["dharma-sadhana.target"]
    dispatch = texts["dharma-sadhana-dispatch.target"]
    assert "dharma-sadhana-supervisor.service" not in predispatch
    assert "dharma-sadhana-supervisor.service" in dispatch
    assert "dharma-sadhana-dispatch-enable.service" in dispatch
    assert "WantedBy=" not in dispatch
    oracle = texts["dharma-sadhana-oracle-sandbox.service.in"]
    assert "PrivateNetwork=true" in oracle
    assert "ProtectSystem=strict" in oracle
    assert "NoNewPrivileges=true" in oracle
    assert "TemporaryFileSystem=/tmp:ro /var/tmp:ro /dev/shm:ro" in oracle
    assert "socket socketpair connect bind listen" in oracle
    assert "EnvironmentFile=" not in oracle
    assert "LoadCredential=" not in oracle
    assert "automatic" not in combined.lower()
    stop_starts = [
        line
        for line in texts["dharma-sadhana-campaign-stop.service.in"].splitlines()
        if line.startswith("ExecStart=")
    ]
    assert "systemctl stop dharma-sadhana.target" in stop_starts[0]
    assert "sadhana_release.py persist-stop --role writer" in stop_starts[1]
    stop_service = texts["dharma-sadhana-campaign-stop.service.in"]
    stop_timer = texts["dharma-sadhana-campaign-stop.timer"]
    assert "sadhana_release.py guard-stop --role writer" in stop_service
    assert "PartOf=dharma-sadhana.target" not in stop_service
    assert "PartOf=dharma-sadhana.target" not in stop_timer
    emergency = texts["dharma-sadhana-control-emergency.service.in"]
    assert "After=dharma-sadhana-control-directories.service" in emergency
    assert "Requires=dharma-sadhana-control-directories.service" not in emergency
    assert "PartOf=dharma-sadhana.target" not in emergency
    assert "control_authority_binding" not in emergency.lower()
    assert release.CONTROL_AUTHORITY_BINDING_SHA256 in combined


def test_supervisor_unit_flags_exist_in_current_cli() -> None:
    repo = Path(__file__).resolve().parents[1]
    unit = (
        repo / "deploy/sadhana/systemd/dharma-sadhana-supervisor.service.in"
    ).read_text(encoding="utf-8")
    start_line = next(
        line for line in unit.splitlines() if line.startswith("ExecStart=")
    )
    flags = set(re.findall(r"(?<!\$)(--[a-z][a-z0-9-]+)", start_line))
    help_result = subprocess.run(
        (
            sys.executable,
            str(repo / "scripts/runtime/mission_control_campaign.py"),
            "run",
            "--help",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    missing = sorted(flag for flag in flags if flag not in help_result.stdout)
    assert not missing


def test_runtime_preparation_unit_flags_exist_in_current_cli() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = repo / "scripts/runtime/sadhana_prepare_runtime.py"
    if not script.exists():
        pytest.skip("runtime preparation implementation lands in integration parent")
    unit = (
        repo
        / "deploy/sadhana/systemd/dharma-sadhana-runtime-prepare.service.in"
    ).read_text(encoding="utf-8")
    start_line = next(
        line for line in unit.splitlines() if line.startswith("ExecStart=")
    )
    flags = set(re.findall(r"(?<!\$)(--[a-z][a-z0-9-]+)", start_line))
    help_result = subprocess.run(
        (sys.executable, str(script), "--help"),
        check=True,
        capture_output=True,
        text=True,
    )
    missing = sorted(flag for flag in flags if flag not in help_result.stdout)
    if missing == ["--projection-path"]:
        pytest.skip(
            "projection CLI is supplied by sibling 44237c9d01013d096c12c67d6adf29241965d364"
        )
    assert not missing
    release_script = repo / "scripts/runtime/sadhana_release.py"
    namespace_probe = subprocess.run(
        (
            sys.executable,
            "-c",
            "import runpy; "
            f"runpy.run_path({str(release_script)!r}); "
            "import scripts.runtime.sadhana_prepare_runtime",
        ),
        cwd=Path("/"),
        check=False,
        capture_output=True,
        text=True,
    )
    assert namespace_probe.returncode == 0, namespace_probe.stderr
