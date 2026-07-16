"""Tests for dharma_swarm.stigmergy -- StigmergicMark, StigmergyStore."""

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore, leave_stigmergic_mark


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> StigmergyStore:
    return StigmergyStore(base_path=tmp_path / "stigmergy")


def _make_mark(**kwargs) -> StigmergicMark:
    """Shorthand for building test marks with sensible defaults."""
    defaults = {
        "agent": "test-agent",
        "file_path": "src/main.py",
        "action": "write",
        "observation": "Refactored core loop",
        "salience": 0.5,
    }
    defaults.update(kwargs)
    return StigmergicMark(**defaults)


# ---------------------------------------------------------------------------
# leave_mark
# ---------------------------------------------------------------------------


async def test_leave_mark_returns_id(store: StigmergyStore):
    mark = _make_mark()
    result = await store.leave_mark(mark)
    assert isinstance(result, str)
    assert len(result) == 16
    assert result == mark.id


# ---------------------------------------------------------------------------
# read_marks
# ---------------------------------------------------------------------------


async def test_read_marks_empty(store: StigmergyStore):
    marks = await store.read_marks()
    assert marks == []


async def test_read_marks_after_leave(store: StigmergyStore):
    for i in range(3):
        await store.leave_mark(_make_mark(observation=f"obs {i}"))
    marks = await store.read_marks()
    assert len(marks) == 3


async def test_read_marks_filtered_by_path(store: StigmergyStore):
    await store.leave_mark(_make_mark(file_path="a.py"))
    await store.leave_mark(_make_mark(file_path="b.py"))
    await store.leave_mark(_make_mark(file_path="a.py"))

    a_marks = await store.read_marks(file_path="a.py")
    assert len(a_marks) == 2
    assert all(m.file_path == "a.py" for m in a_marks)

    b_marks = await store.read_marks(file_path="b.py")
    assert len(b_marks) == 1


async def test_read_marks_limit(store: StigmergyStore):
    now = datetime.now(timezone.utc)
    for i in range(5):
        m = _make_mark(observation=f"obs {i}")
        m.timestamp = now + timedelta(seconds=i)
        await store.leave_mark(m)

    marks = await store.read_marks(limit=2)
    assert len(marks) == 2
    # Most recent first
    assert marks[0].timestamp >= marks[1].timestamp


# ---------------------------------------------------------------------------
# hot_paths
# ---------------------------------------------------------------------------


async def test_hot_paths(store: StigmergyStore):
    for _ in range(4):
        await store.leave_mark(_make_mark(file_path="hot.py"))
    await store.leave_mark(_make_mark(file_path="cold.py"))

    hot = await store.hot_paths(window_hours=24, min_marks=3)
    assert len(hot) == 1
    assert hot[0][0] == "hot.py"
    assert hot[0][1] == 4


# ---------------------------------------------------------------------------
# high_salience
# ---------------------------------------------------------------------------


async def test_high_salience(store: StigmergyStore):
    await store.leave_mark(_make_mark(salience=0.3))
    await store.leave_mark(_make_mark(salience=0.8, observation="important"))
    await store.leave_mark(_make_mark(salience=0.9, observation="critical"))
    await store.leave_mark(_make_mark(salience=0.5))

    high = await store.high_salience(threshold=0.7)
    assert len(high) == 2
    assert high[0].salience == 0.9
    assert high[1].salience == 0.8


async def test_access_count_increments_on_reads(store: StigmergyStore):
    await store.leave_mark(
        _make_mark(
            file_path="core.py",
            observation="Retry budget guard needs review",
            salience=0.9,
        )
    )

    recent = await store.read_marks(limit=1)
    assert recent[0].access_count == 1

    high = await store.high_salience(threshold=0.7, limit=1)
    assert high[0].access_count == 2

    relevant = await store.query_relevant(["retry budget"], limit=1)
    assert relevant[0].access_count == 3

    payload = json.loads(store._marks_file.read_text(encoding="utf-8").splitlines()[0])
    assert payload["access_count"] == 3


# ---------------------------------------------------------------------------
# connections_for
# ---------------------------------------------------------------------------


async def test_connections_for(store: StigmergyStore):
    await store.leave_mark(
        _make_mark(file_path="core.py", connections=["utils.py", "models.py"])
    )
    await store.leave_mark(
        _make_mark(file_path="core.py", connections=["models.py", "config.py"])
    )
    await store.leave_mark(
        _make_mark(file_path="other.py", connections=["unrelated.py"])
    )

    conns = await store.connections_for("core.py")
    assert conns == ["config.py", "models.py", "utils.py"]


# ---------------------------------------------------------------------------
# decay
# ---------------------------------------------------------------------------


async def test_decay(store: StigmergyStore):
    now = datetime.now(timezone.utc)

    old_mark = _make_mark(observation="ancient")
    old_mark.timestamp = now - timedelta(hours=200)
    await store.leave_mark(old_mark)

    fresh_mark = _make_mark(observation="recent")
    fresh_mark.timestamp = now
    await store.leave_mark(fresh_mark)

    archived = await store.decay(max_age_hours=168)
    assert archived == 1

    # Only the fresh mark remains
    remaining = await store.read_marks()
    assert len(remaining) == 1
    assert remaining[0].observation == "recent"

    # Archive file was created
    assert store._archive_file.exists()


# ---------------------------------------------------------------------------
# density
# ---------------------------------------------------------------------------


async def test_density(store: StigmergyStore):
    for _ in range(3):
        await store.leave_mark(_make_mark())
    assert store.density() == 3


async def test_density_empty(store: StigmergyStore):
    assert store.density() == 0


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


async def test_leave_stigmergic_mark_convenience(tmp_path: Path, monkeypatch):
    """The module-level function creates a mark via the singleton store."""
    # Reset singleton and redirect to tmp_path so we don't write to real ~/.dharma/
    monkeypatch.setattr(
        "dharma_swarm.stigmergy._DEFAULT_BASE",
        tmp_path / "stigmergy",
    )
    monkeypatch.setattr("dharma_swarm.stigmergy._default_store", None)
    mark_id = await leave_stigmergic_mark(
        agent="conv-agent",
        file_path="test.py",
        observation="Quick note",
        salience=0.6,
        connections=["related.py"],
        action="scan",
    )
    assert isinstance(mark_id, str)
    assert len(mark_id) == 16

    # Verify the mark landed on disk
    store = StigmergyStore(base_path=tmp_path / "stigmergy")
    marks = await store.read_marks()
    assert len(marks) == 1
    assert marks[0].agent == "conv-agent"
    assert marks[0].action == "scan"


# ---------------------------------------------------------------------------
# Concurrent write safety (atomicity)
# ---------------------------------------------------------------------------


async def test_concurrent_leave_mark_no_data_loss(store: StigmergyStore):
    """Concurrent leave_mark calls must not lose marks."""
    n = 50
    tasks = [
        store.leave_mark(_make_mark(observation=f"concurrent {i}"))
        for i in range(n)
    ]
    await asyncio.gather(*tasks)
    marks = await store.read_marks(limit=n + 10)
    assert len(marks) == n


async def test_decay_does_not_lose_concurrent_marks(tmp_path: Path):
    """A decay running while marks are being written must not discard them.

    The write lock ensures read-then-rewrite in decay serializes with
    leave_mark, so newly appended marks are never lost.
    """
    store = StigmergyStore(base_path=tmp_path / "stigmergy")
    now = datetime.now(timezone.utc)

    # Seed with old marks (will be archived)
    for i in range(5):
        m = _make_mark(observation=f"old {i}")
        m.timestamp = now - timedelta(hours=200)
        await store.leave_mark(m)

    # Seed with recent marks (will survive)
    for i in range(3):
        m = _make_mark(observation=f"recent {i}")
        m.timestamp = now
        await store.leave_mark(m)

    # Run decay and a fresh leave_mark concurrently
    fresh = _make_mark(observation="written during decay")
    fresh.timestamp = now

    archived, _ = await asyncio.gather(
        store.decay(max_age_hours=168),
        store.leave_mark(fresh),
    )
    assert archived == 5

    remaining = await store.read_marks(limit=20)
    observations = {m.observation for m in remaining}
    # The 3 recent marks + 1 written during decay must all survive
    assert "written during decay" in observations
    assert len(remaining) == 4


async def test_decay_does_not_lose_cross_instance_append(tmp_path: Path):
    """A rewrite must retain an append made by another store instance."""
    root = tmp_path / "stigmergy"
    rewriter = StigmergyStore(base_path=root)
    appender = StigmergyStore(base_path=root)
    old = _make_mark(observation="old cross-instance mark")
    old.timestamp = datetime.now(timezone.utc) - timedelta(days=10)
    fresh = _make_mark(observation="cross-instance append")
    await rewriter.leave_mark(old)

    loaded = asyncio.Event()
    resume = asyncio.Event()
    original_load = rewriter._load_marks

    async def paused_load():
        marks = await original_load()
        loaded.set()
        await resume.wait()
        return marks

    rewriter._load_marks = paused_load
    decay_task = asyncio.create_task(rewriter.decay(max_age_hours=1))
    await loaded.wait()
    await appender.leave_mark(fresh)
    resume.set()

    assert await decay_task == 1
    surviving_ids = {mark.id for mark in await appender.read_marks(limit=20)}
    assert fresh.id in surviving_ids


async def test_decay_blocks_sibling_append_inside_rewrite_window(tmp_path: Path):
    """Same-process stores share a path lock across the authoritative rewrite."""
    root = tmp_path / "stigmergy"
    rewriter = StigmergyStore(base_path=root)
    appender = StigmergyStore(base_path=root)
    old = _make_mark(observation="old same-process mark")
    old.timestamp = datetime.now(timezone.utc) - timedelta(days=10)
    fresh = _make_mark(observation="blocked same-process append")
    await rewriter.leave_mark(old)

    inside_rewrite = asyncio.Event()
    resume_rewrite = asyncio.Event()
    original_load = rewriter._load_marks
    load_count = 0

    async def paused_authoritative_load():
        nonlocal load_count
        marks = await original_load()
        load_count += 1
        if load_count == 2:
            inside_rewrite.set()
            await resume_rewrite.wait()
        return marks

    rewriter._load_marks = paused_authoritative_load
    decay_task = asyncio.create_task(rewriter.decay(max_age_hours=1))
    await asyncio.wait_for(inside_rewrite.wait(), timeout=2)

    append_task = asyncio.create_task(appender.leave_mark(fresh))
    await asyncio.sleep(0.05)
    assert not append_task.done(), "sibling append entered the locked rewrite window"

    resume_rewrite.set()
    assert await asyncio.wait_for(decay_task, timeout=2) == 1
    await asyncio.wait_for(append_task, timeout=2)
    surviving_ids = {mark.id for mark in await appender.read_marks(limit=20)}
    assert fresh.id in surviving_ids


async def test_decay_does_not_lose_cross_process_append(tmp_path: Path):
    """A local-filesystem rewrite serializes with a cooperating writer process."""
    root = tmp_path / "stigmergy"
    attempted = tmp_path / "child-attempted"
    completed = tmp_path / "child-completed"
    rewriter = StigmergyStore(base_path=root)
    old = _make_mark(observation="old cross-process mark")
    old.timestamp = datetime.now(timezone.utc) - timedelta(days=10)
    await rewriter.leave_mark(old)

    child_code = """
import asyncio
import sys
from pathlib import Path
from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore

async def main():
    root, attempted, completed = map(Path, sys.argv[1:])
    mark = StigmergicMark(
        agent="child-process",
        channel="systems",
        file_path="fresh.py",
        observation="fresh cross-process append",
    )
    attempted.write_text("attempted", encoding="utf-8")
    await StigmergyStore(base_path=root).leave_mark(mark)
    completed.write_text(mark.id, encoding="utf-8")

asyncio.run(main())
"""
    original_load = rewriter._load_marks
    load_count = 0
    child: subprocess.Popen[str] | None = None

    async def interleaved_load():
        nonlocal child, load_count
        marks = await original_load()
        load_count += 1
        if load_count == 2:
            child = subprocess.Popen(
                [sys.executable, "-c", child_code, str(root), str(attempted), str(completed)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(200):
                if attempted.exists():
                    break
                await asyncio.sleep(0.01)
            assert attempted.exists(), "child writer never reached leave_mark"
            # Old implementations complete here and are then overwritten. A
            # cooperating locked writer remains blocked until decay replaces
            # the hot file and releases the local advisory lock.
            for _ in range(75):
                if completed.exists():
                    break
                await asyncio.sleep(0.01)
        return marks

    rewriter._load_marks = interleaved_load
    try:
        assert await rewriter.decay(max_age_hours=1) == 1
        assert child is not None
        await asyncio.to_thread(child.wait, 5)
        stdout, stderr = child.communicate()
        assert child.returncode == 0, (stdout, stderr)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)

    fresh_id = completed.read_text(encoding="utf-8")
    surviving_ids = {mark.id for mark in await original_load()}
    assert fresh_id in surviving_ids


async def test_access_decay_atomic_rewrite(store: StigmergyStore):
    """access_decay must not corrupt the marks file."""
    for i in range(10):
        await store.leave_mark(_make_mark(salience=0.5, observation=f"mark {i}"))

    dead = await store.access_decay(decay_factor=0.95)
    # All marks should still be readable (none below 0.1 after one decay pass)
    marks = await store.read_marks(limit=20)
    assert len(marks) == 10
    assert dead == 0  # salience 0.5 * 0.95^2 = 0.45, still above 0.1
