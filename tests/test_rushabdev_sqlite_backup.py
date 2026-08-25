"""Behavioral tests for the fail-closed Rushabdev SQLite backup job."""

from __future__ import annotations

import fcntl
import gzip
import hashlib
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ops" / "rushabdev_sqlite_backup.sh"
REQUIRED_COMMANDS = ("bash", "gzip", "sqlite3")
SQLITE_MANIFEST = (
    Path("data/markets.db"),
    Path("state/calibration.db"),
    Path("state/paper_positions.db"),
)
DUCKDB_MANIFEST_PATH = Path("state/scoreboard.duckdb")

pytestmark = pytest.mark.skipif(
    any(shutil.which(command) is None for command in REQUIRED_COMMANDS),
    reason="backup integration tests require bash, gzip, and sqlite3",
)


def _make_database(path: Path, values: tuple[str, ...] = ("alpha", "beta")) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE memory (id INTEGER PRIMARY KEY, value TEXT)")
        connection.executemany(
            "INSERT INTO memory(value) VALUES (?)", ((value,) for value in values)
        )


def _make_live_manifest(
    source_root: Path,
    market_values: tuple[str, ...] = ("alpha", "beta"),
) -> None:
    for relative in SQLITE_MANIFEST:
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        values = market_values if relative == SQLITE_MANIFEST[0] else (relative.stem,)
        _make_database(path, values)
    duckdb_path = source_root / DUCKDB_MANIFEST_PATH
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    duckdb_path.write_bytes(b"DUCK" * 100)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_backup(
    source_root: Path | str,
    output_dir: Path,
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "RUSHABDEV_SQLITE_ROOT": str(source_root),
            "RUSHABDEV_SQLITE_BACKUP_DIR": str(output_dir),
            "RUSHABDEV_SQLITE_RETENTION_DAYS": "7",
            "RUSHABDEV_SQLITE_RESERVE_BYTES": "0",
            # Keep test staging bounds small while leaving ample headroom for
            # the tiny fixture databases.
            "RUSHABDEV_SQLITE_VERIFY_EXTRA_BYTES": str(1024 * 1024),
            "RUSHABDEV_SQLITE_BUSY_TIMEOUT_MS": "1000",
        }
    )
    env.update(overrides)
    # macOS has BSD flock(2) but no util-linux `flock` executable. Exercise the
    # backup behavior there with a success shim; the dedicated overlap test is
    # separately skipped and only runs where the real executable is available.
    if shutil.which("flock", path=env.get("PATH")) is None:
        shim_dir = output_dir / ".test-tools"
        shim_dir.mkdir(exist_ok=True)
        flock_shim = shim_dir / "flock"
        flock_shim.write_text("#!/bin/sh\nexit 0\n")
        flock_shim.chmod(0o755)
        env["PATH"] = f"{shim_dir}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _archives(output_dir: Path) -> list[Path]:
    return sorted(output_dir.glob("*.sqlite3.gz"))


def _assert_no_partials(output_dir: Path) -> None:
    assert list(output_dir.glob("*.partial")) == []
    assert list(output_dir.glob(".*.partial")) == []


def test_successful_backup_is_restorable_and_live_database_is_unchanged(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    live_db = source_root / SQLITE_MANIFEST[0]
    _make_live_manifest(source_root, ("alpha", "beta", "gamma"))
    before_digest = _digest(live_db)
    before_mtime = live_db.stat().st_mtime_ns

    result = _run_backup(source_root, output_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "event=backup status=ok" in result.stdout
    assert "event=run status=ok" in result.stdout
    archives = _archives(output_dir)
    assert len(archives) == 3
    archive = next(path for path in archives if "markets.db" in path.name)
    restored = tmp_path / "restored.sqlite3"
    with gzip.open(archive, "rb") as compressed, restored.open("wb") as target:
        shutil.copyfileobj(compressed, target)
    with sqlite3.connect(f"file:{restored}?mode=ro", uri=True) as connection:
        values = connection.execute("SELECT value FROM memory ORDER BY id").fetchall()
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
    assert values == [("alpha",), ("beta",), ("gamma",)]
    assert quick_check == "ok"
    assert _digest(live_db) == before_digest
    assert live_db.stat().st_mtime_ns == before_mtime
    _assert_no_partials(output_dir)


def test_retention_runs_before_creation_and_preserves_verified_keeper(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)

    first_run = _run_backup(source_root, output_dir)
    assert first_run.returncode == 0, first_run.stdout + first_run.stderr
    keeper = next(path for path in _archives(output_dir) if "markets.db" in path.name)
    prefix = keeper.name.rsplit("--", 2)[0]
    obsolete_a = output_dir / f"{prefix}--20000101T000000Z--1.sqlite3.gz"
    obsolete_b = output_dir / f"{prefix}--20010101T000000Z--2.sqlite3.gz"
    shutil.copy2(keeper, obsolete_a)
    shutil.copy2(keeper, obsolete_b)
    old_time = time.time() - 10 * 86400
    for path in (keeper, obsolete_a, obsolete_b):
        os.utime(path, (old_time, old_time))

    second_run = _run_backup(
        source_root,
        output_dir,
        RUSHABDEV_SQLITE_RETENTION_DAYS="0",
    )

    assert second_run.returncode == 0, second_run.stdout + second_run.stderr
    assert "event=retention status=ok" in second_run.stdout
    assert not obsolete_a.exists()
    assert not obsolete_b.exists()
    assert keeper.exists(), "pre-creation retention must preserve one verified backup"
    # Retention is intentionally before creation: the verified old keeper and
    # the newly promoted archive both remain until the next run.
    assert len(list(output_dir.glob(f"{prefix}--*.sqlite3.gz"))) == 2
    _assert_no_partials(output_dir)


def test_database_shrink_does_not_make_old_keeper_unverifiable(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)
    markets = source_root / SQLITE_MANIFEST[0]
    with sqlite3.connect(markets) as connection:
        connection.execute("CREATE TABLE temporary_bulk (payload BLOB)")
        connection.execute(
            "INSERT INTO temporary_bulk(payload) VALUES (zeroblob(?))",
            (20 * 1024 * 1024,),
        )

    first_run = _run_backup(source_root, output_dir)
    assert first_run.returncode == 0, first_run.stdout + first_run.stderr
    first_market_archive = next(
        path for path in _archives(output_dir) if "markets.db" in path.name
    )

    with sqlite3.connect(markets) as connection:
        connection.execute("DROP TABLE temporary_bulk")
        connection.execute("VACUUM")
    assert markets.stat().st_size < 1024 * 1024

    second_run = _run_backup(source_root, output_dir)

    assert second_run.returncode == 0, second_run.stdout + second_run.stderr
    market_archives = [
        path for path in _archives(output_dir) if "markets.db" in path.name
    ]
    assert len(market_archives) == 2
    assert first_market_archive in market_archives
    assert "reason=verification_unavailable" not in second_run.stdout
    _assert_no_partials(output_dir)


def test_insufficient_space_fails_without_removing_old_valid_backup(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)
    initial = _run_backup(source_root, output_dir)
    assert initial.returncode == 0, initial.stdout + initial.stderr
    old_backups = _archives(output_dir)
    assert len(old_backups) == 3
    old_bytes = {path: path.read_bytes() for path in old_backups}
    old_time = time.time() - 10 * 86400
    for path in old_backups:
        os.utime(path, (old_time, old_time))

    free_bytes = shutil.disk_usage(output_dir).free
    verification_headroom = 256 * 1024 * 1024
    if free_bytes <= verification_headroom:
        pytest.skip("capacity fixture requires 256 MiB of verification headroom")

    result = _run_backup(
        source_root,
        output_dir,
        RUSHABDEV_SQLITE_RETENTION_DAYS="0",
        # Leave ample room to restore the tiny keeper, then make the separate
        # preflight requirement exceed that headroom deterministically.
        RUSHABDEV_SQLITE_RESERVE_BYTES=str(free_bytes - verification_headroom),
        RUSHABDEV_SQLITE_VERIFY_EXTRA_BYTES=str(verification_headroom * 2),
    )

    assert result.returncode != 0
    assert "event=capacity status=failed" in result.stdout
    assert "reason=insufficient_space" in result.stdout
    assert "reason=insufficient_space_for_verification" not in result.stdout
    assert _archives(output_dir) == old_backups
    assert {path: path.read_bytes() for path in old_backups} == old_bytes
    _assert_no_partials(output_dir)


def test_prunes_stale_partials_and_zero_byte_final_before_backup(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)
    stale_binary = output_dir / "abandoned.sqlite3.partial"
    stale_gzip = output_dir / "abandoned.sqlite3.gz.partial"
    stale_hidden_restore = output_dir / ".restore-verify.deadbeef.partial"
    zero_final = output_dir / "abandoned.sqlite3.gz"
    stale_binary.write_bytes(b"incomplete")
    stale_gzip.write_bytes(b"incomplete")
    stale_hidden_restore.write_bytes(b"incomplete")
    zero_final.touch()

    result = _run_backup(source_root, output_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("event=prune status=ok") == 4
    assert not stale_binary.exists()
    assert not stale_gzip.exists()
    assert not stale_hidden_restore.exists()
    assert not zero_final.exists()
    assert len(_archives(output_dir)) == 3
    _assert_no_partials(output_dir)


def test_error_after_sqlite_staging_removes_all_partials(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    fake_bin = tmp_path / "bin"
    source_root.mkdir()
    output_dir.mkdir()
    fake_bin.mkdir()
    _make_live_manifest(source_root)
    fake_gzip = fake_bin / "gzip"
    fake_gzip.write_text("#!/bin/sh\nexit 42\n")
    fake_gzip.chmod(0o755)

    result = _run_backup(
        source_root,
        output_dir,
        PATH=f"{fake_bin}:{os.environ['PATH']}",
    )

    assert result.returncode != 0
    assert "reason=gzip_failed" in result.stdout
    assert _archives(output_dir) == []
    _assert_no_partials(output_dir)


def test_archive_fsync_failure_never_publishes_or_receipts_success(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    fake_bin = tmp_path / "bin"
    source_root.mkdir()
    output_dir.mkdir()
    fake_bin.mkdir()
    _make_live_manifest(source_root)
    fake_python = fake_bin / "python3"
    fake_python.write_text("#!/bin/sh\nexit 42\n")
    fake_python.chmod(0o755)

    result = _run_backup(
        source_root,
        output_dir,
        PATH=f"{fake_bin}:{os.environ['PATH']}",
    )

    assert result.returncode != 0
    assert "reason=archive_fsync_failed" in result.stdout
    assert "event=backup status=ok" not in result.stdout
    assert _archives(output_dir) == []
    _assert_no_partials(output_dir)


def test_invalid_database_fails_closed_without_promoting_archive(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)
    for relative in SQLITE_MANIFEST:
        (source_root / relative).write_bytes(b"not a sqlite database\n" * 10)

    result = _run_backup(source_root, output_dir)

    assert result.returncode != 0
    assert "event=backup status=failed" in result.stdout
    assert _archives(output_dir) == []
    _assert_no_partials(output_dir)


def test_rejects_unsafe_paths_without_touching_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "backups"
    output_dir.mkdir()
    sentinel = output_dir / "keep.txt"
    sentinel.write_text("untouched")

    result = _run_backup("relative/source", output_dir)

    assert result.returncode == 64
    assert "reason=source_root_not_absolute" in result.stdout
    assert sentinel.read_text() == "untouched"
    assert _archives(output_dir) == []


def test_duckdb_is_never_opened_by_sqlite_and_has_explicit_skip_receipt(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)

    result = _run_backup(source_root, output_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "event=backup status=skipped kind=duckdb" in result.stdout
    assert "reason=unsupported_no_safe_cli" in result.stdout
    assert "present=1" in result.stdout
    assert len(_archives(output_dir)) == 3


def test_unlisted_database_is_not_silently_added_to_manifest(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)
    _make_database(source_root / "unlisted.db", ("must", "not", "copy"))

    result = _run_backup(source_root, output_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    archives = _archives(output_dir)
    assert len(archives) == 3
    assert all("unlisted.db" not in path.name for path in archives)
    assert "event=manifest status=ok entries=4" in result.stdout


def test_rejects_symlink_lock_without_touching_target(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)
    protected = tmp_path / "protected.txt"
    protected.write_text("must-not-change")
    (output_dir / ".rushabdev-sqlite-backup.lock").symlink_to(protected)

    result = _run_backup(source_root, output_dir)

    assert result.returncode == 64
    assert "reason=lock_path_symlink" in result.stdout
    assert protected.read_text() == "must-not-change"
    assert _archives(output_dir) == []


@pytest.mark.skipif(shutil.which("flock") is None, reason="requires util-linux flock")
def test_flock_prevents_overlapping_run(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    output_dir = tmp_path / "backups"
    source_root.mkdir()
    output_dir.mkdir()
    _make_live_manifest(source_root)
    lock_path = output_dir / ".rushabdev-sqlite-backup.lock"

    with lock_path.open("a") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = _run_backup(source_root, output_dir)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    assert result.returncode == 75
    assert "event=lock status=failed reason=already_running" in result.stdout
    assert _archives(output_dir) == []
