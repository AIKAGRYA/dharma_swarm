"""Tests for dharma_swarm.cultivation_observer.

Strategy:
    1. Pure-data tests for the diff function (no substrate touch).
    2. End-to-end snapshot → write → read → diff using a temp state_dir.
    3. Honesty: first run emits no records, only a baseline snapshot.
    4. Contract: outcome kind is stable; no new sqlite/no Path.home() use.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.cultivation_observer import (
    DEFAULT_SEED_CHANNELS,
    METHOD_VERSION,
    OUTCOME_KIND_CULTIVATION_SIGNAL_V1,
    CultivationSnapshot,
    diff_snapshots,
    latest_two_snapshots,
    run_cultivation_observer,
    snapshots_dir,
    take_snapshot,
    write_snapshot,
)
from dharma_swarm.telemetry_plane import TelemetryPlaneStore


def _make_snap(
    *,
    captured_at: datetime,
    tasks: int = 0,
    telos: int = 0,
    stig: int = 0,
    task_tags: dict[str, int] | None = None,
    telos_doms: dict[str, int] | None = None,
    stig_chs: dict[str, int] | None = None,
    task_sig: str = "task-sig-a",
    telos_sig: str = "telos-sig-a",
    stig_sig: str = "stig-sig-a",
) -> CultivationSnapshot:
    return CultivationSnapshot(
        captured_at=captured_at,
        task_count=tasks,
        task_signature=task_sig,
        task_count_by_tag=task_tags or {},
        telos_objective_count=telos,
        telos_signature=telos_sig,
        telos_count_by_domain=telos_doms or {},
        stigmergy_mark_count=stig,
        stigmergy_signature=stig_sig,
        stigmergy_count_by_channel=stig_chs or {},
        seed_channels=DEFAULT_SEED_CHANNELS,
        method_version=METHOD_VERSION,
    )


# ---------------------------------------------------------------------------
# diff_snapshots
# ---------------------------------------------------------------------------


class TestDiffSnapshots:
    def test_no_change_zero_signal(self) -> None:
        now = datetime.now(timezone.utc)
        s = _make_snap(captured_at=now)
        delta = diff_snapshots(s, s, channel="gplot")
        assert delta.signal == 0.0
        assert delta.new_tasks == 0
        assert delta.new_telos_objectives == 0
        assert delta.new_stigmergy_marks == 0
        assert delta.task_content_changed is False

    def test_pure_growth_positive_signal(self) -> None:
        t0 = datetime.now(timezone.utc) - timedelta(days=1)
        t1 = datetime.now(timezone.utc)
        prev = _make_snap(
            captured_at=t0,
            tasks=2, task_tags={"gplot": 1},
            telos=0, telos_doms={"gplot": 0},
            stig=5, stig_chs={"gplot": 5},
        )
        curr = _make_snap(
            captured_at=t1,
            tasks=5, task_tags={"gplot": 4},
            telos=1, telos_doms={"gplot": 1},
            stig=7, stig_chs={"gplot": 7},
            task_sig="task-sig-b",
            telos_sig="telos-sig-b",
            stig_sig="stig-sig-b",
        )
        d = diff_snapshots(prev, curr, channel="gplot")
        assert d.new_tasks == 3
        assert d.new_telos_objectives == 1
        assert d.new_stigmergy_marks == 2
        # weighted: 3*1 + 2*3 + 1*2 = 3 + 6 + 2 = 11
        assert d.signal == pytest.approx(11.0)
        assert d.task_content_changed is True
        assert d.telos_content_changed is True
        assert d.window_seconds == pytest.approx(86400.0, rel=0.01)

    def test_negative_counts_clamped_to_zero(self) -> None:
        # If entities were deleted, we don't fabricate negative cultivation.
        t0 = datetime.now(timezone.utc) - timedelta(days=1)
        t1 = datetime.now(timezone.utc)
        prev = _make_snap(captured_at=t0, tasks=5, task_tags={"gplot": 5})
        curr = _make_snap(captured_at=t1, tasks=2, task_tags={"gplot": 2})
        d = diff_snapshots(prev, curr, channel="gplot")
        assert d.new_tasks == 0
        assert d.signal == 0.0

    def test_content_change_without_count_change(self) -> None:
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        t1 = datetime.now(timezone.utc)
        prev = _make_snap(
            captured_at=t0, tasks=3, task_tags={"gplot": 3}, task_sig="aaa"
        )
        curr = _make_snap(
            captured_at=t1, tasks=3, task_tags={"gplot": 3}, task_sig="bbb"
        )
        d = diff_snapshots(prev, curr, channel="gplot")
        # signal is 0 (no new entities), but content_changed flags True
        assert d.signal == 0.0
        assert d.task_content_changed is True

    def test_per_channel_independence(self) -> None:
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        t1 = datetime.now(timezone.utc)
        prev = _make_snap(
            captured_at=t0, tasks=4, task_tags={"gplot": 2, "gnani": 2}
        )
        curr = _make_snap(
            captured_at=t1,
            tasks=7, task_tags={"gplot": 5, "gnani": 2},
            task_sig="diff",
        )
        d_gplot = diff_snapshots(prev, curr, channel="gplot")
        d_gnani = diff_snapshots(prev, curr, channel="gnani")
        assert d_gplot.new_tasks == 3
        assert d_gnani.new_tasks == 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_write_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sd = Path(tmp)
            snap = _make_snap(
                captured_at=datetime.now(timezone.utc),
                tasks=2, telos=1, stig=3,
            )
            path = write_snapshot(snap, state_dir=sd)
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["task_count"] == 2
            assert data["telos_objective_count"] == 1
            assert "captured_at" in data

    def test_latest_two_snapshots_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sd = Path(tmp)
            s1 = _make_snap(
                captured_at=datetime.now(timezone.utc) - timedelta(hours=2),
                tasks=1, task_sig="s1",
            )
            s2 = _make_snap(
                captured_at=datetime.now(timezone.utc),
                tasks=3, task_sig="s2",
            )
            write_snapshot(s1, state_dir=sd)
            write_snapshot(s2, state_dir=sd)
            prev, curr = latest_two_snapshots(state_dir=sd)
            assert prev is not None and curr is not None
            assert prev.task_count == 1
            assert curr.task_count == 3

    def test_no_snapshots_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prev, curr = latest_two_snapshots(state_dir=Path(tmp))
            assert prev is None and curr is None

    def test_single_snapshot_returns_only_curr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sd = Path(tmp)
            s = _make_snap(captured_at=datetime.now(timezone.utc))
            write_snapshot(s, state_dir=sd)
            prev, curr = latest_two_snapshots(state_dir=sd)
            assert prev is None
            assert curr is not None


# ---------------------------------------------------------------------------
# End-to-end run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_run_emits_no_records() -> None:
    """Honesty: first observation has nothing to diff."""
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        store = TelemetryPlaneStore(db_path=sd / "telemetry.db")
        snap, deltas, records = await run_cultivation_observer(
            state_dir=sd, store=store
        )
        assert snap.task_count == 0
        assert deltas == []
        assert records == []


@pytest.mark.asyncio
async def test_second_run_emits_one_record_per_channel() -> None:
    """A snapshot already exists → diff path runs → one record per channel."""
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        # Pre-seed an older snapshot.
        old = _make_snap(
            captured_at=datetime.now(timezone.utc) - timedelta(days=1),
            tasks=0, task_tags={"gplot": 0, "gnani": 0},
        )
        write_snapshot(old, state_dir=sd)

        store = TelemetryPlaneStore(db_path=sd / "telemetry.db")
        snap, deltas, records = await run_cultivation_observer(
            state_dir=sd, store=store, dry_run=True,
        )
        assert len(deltas) == len(DEFAULT_SEED_CHANNELS)
        assert len(records) == len(DEFAULT_SEED_CHANNELS)
        for rec in records:
            assert rec.outcome_kind == OUTCOME_KIND_CULTIVATION_SIGNAL_V1
            assert rec.subject_id in DEFAULT_SEED_CHANNELS
            assert "channel" in rec.metadata


@pytest.mark.asyncio
async def test_real_write_path_appears_in_substrate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        # Pre-seed.
        old = _make_snap(
            captured_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        write_snapshot(old, state_dir=sd)

        store = TelemetryPlaneStore(db_path=sd / "telemetry.db")
        _snap, _deltas, records = await run_cultivation_observer(
            state_dir=sd, store=store,
        )
        written = await store.list_external_outcomes(
            outcome_kind=OUTCOME_KIND_CULTIVATION_SIGNAL_V1, limit=10,
        )
        assert len(written) == len(records) == len(DEFAULT_SEED_CHANNELS)


@pytest.mark.asyncio
async def test_take_snapshot_smoke_with_empty_substrate() -> None:
    """Even with no substrate present (no DBs), snapshot must not raise."""
    with tempfile.TemporaryDirectory() as tmp:
        snap = await take_snapshot(state_dir=Path(tmp))
        # Empty substrate → zero counts, stable hash.
        assert snap.task_count == 0
        assert snap.telos_objective_count == 0
        assert snap.stigmergy_mark_count == 0
        assert snap.task_signature  # non-empty hash even for empty list


# ---------------------------------------------------------------------------
# Governance / contracts
# ---------------------------------------------------------------------------


def test_no_new_substrate_or_home_dharma() -> None:
    """Anti-slop rules 1 and 2."""
    from dharma_swarm import cultivation_observer

    src = Path(cultivation_observer.__file__).read_text()
    assert "sqlite3.connect" not in src
    assert "aiosqlite.connect" not in src
    assert "Path.home()" not in src


def test_stable_outcome_kind_contract() -> None:
    assert OUTCOME_KIND_CULTIVATION_SIGNAL_V1 == "cultivation_signal_v1"
    assert METHOD_VERSION == "passive_snapshot_diff_v1"


def test_default_channels_match_lodestones() -> None:
    """The default channels MUST be the channels seeded by the lodestone
    boot path. Drift between this constant and the boot-seeder breaks
    the falsifiability mapping."""
    assert "gnani" in DEFAULT_SEED_CHANNELS
    assert "gplot" in DEFAULT_SEED_CHANNELS


def test_snapshots_dir_under_state_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sd = Path(tmp)
        out = snapshots_dir(sd)
        assert out.is_dir()
        assert out.is_relative_to(sd)
