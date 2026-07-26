"""Tests for the quality-quarantine gate (DHARMA_MEMORY_QUALITY_QUARANTINE)."""

import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone

import pytest

from dharma_swarm.context import read_memory_context, read_recent_memories
from dharma_swarm.memory import StrangeLoopMemory
from dharma_swarm.memory_quarantine import (
    MODE_ENFORCE,
    MODE_OFF,
    MODE_SHADOW,
    QUARANTINE_ENV,
    RECEIPT_RELPATH,
    is_quarantined,
    quarantine_mode,
)
from dharma_swarm.models import MemoryLayer

GOOD_TEXT = "I notice an actual gap: error at line 42 in file models.py"
BAD_TEXT = (
    "This is a profound amazing revolutionary transcendent cosmic "
    "awakening definitely"
)


@pytest.fixture
async def mem(tmp_path):
    m = StrangeLoopMemory(tmp_path / "memory.db")
    await m.init_db()
    await m.remember(GOOD_TEXT, layer=MemoryLayer.WITNESS)
    await m.remember(BAD_TEXT, layer=MemoryLayer.WITNESS)
    yield m
    await m.close()


def _receipt_lines(state_dir):
    path = state_dir / RECEIPT_RELPATH
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


# ── mode parsing ─────────────────────────────────────────────────────


def test_mode_defaults_to_shadow(monkeypatch):
    monkeypatch.delenv(QUARANTINE_ENV, raising=False)
    assert quarantine_mode() == MODE_SHADOW


@pytest.mark.parametrize("raw", ["off", "shadow", "enforce", " ENFORCE "])
def test_mode_parses_known_values(monkeypatch, raw):
    monkeypatch.setenv(QUARANTINE_ENV, raw)
    assert quarantine_mode() == raw.strip().lower()


def test_mode_unknown_falls_back_to_shadow(monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, "yolo")
    assert quarantine_mode() == MODE_SHADOW


# ── predicate ────────────────────────────────────────────────────────


def test_is_quarantined_tag_is_authority():
    assert is_quarantined(["low_quality"], 0.9) is True
    assert is_quarantined(["crown_jewel"], 0.1) is False
    assert is_quarantined([], 0.1) is False


def test_is_quarantined_quality_fallback_when_tags_unknown():
    assert is_quarantined(None, 0.3) is True
    assert is_quarantined(None, 0.7) is False
    assert is_quarantined(None, None) is False


def test_sql_twin_matches_python_predicate_exactly():
    """Devin review (PR #1134): a bare `_` in LIKE matches any character, so
    the unescaped pattern also excluded near-miss tags like "lowXquality" —
    diverging from the exact list-membership check in is_quarantined()."""
    from dharma_swarm.memory_quarantine import SQL_NOT_QUARANTINED

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE memories (id INTEGER PRIMARY KEY, tags TEXT)")
    rows = {
        1: ["low_quality"],       # quarantined
        2: ["lowXquality"],       # near-miss: must be SERVED
        3: ["crown_jewel"],       # served
        4: [],                    # served
    }
    for rowid, tags in rows.items():
        conn.execute(
            "INSERT INTO memories (id, tags) VALUES (?, ?)",
            (rowid, json.dumps(tags)),
        )
    served = {
        row[0]
        for row in conn.execute(
            f"SELECT id FROM memories WHERE {SQL_NOT_QUARANTINED}"
        )
    }
    conn.close()
    expected = {rowid for rowid, tags in rows.items() if not is_quarantined(tags, None)}
    assert served == expected == {2, 3, 4}


def test_shadow_receipt_write_failure_is_counted(tmp_path):
    from dharma_swarm.memory_quarantine import (
        RECEIPT_WRITE_FAILURES,
        record_shadow_receipt,
    )

    blocker = tmp_path / "blocker"
    blocker.write_text("")
    before = RECEIPT_WRITE_FAILURES["count"]
    record_shadow_receipt(
        site="t", served=1, would_be_excluded=0, state_dir=blocker / "sub"
    )
    assert RECEIPT_WRITE_FAILURES["count"] == before + 1


# ── StrangeLoopMemory.recall / get_context ───────────────────────────


@pytest.mark.asyncio
async def test_recall_off_serves_low_quality(mem, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_OFF)
    entries = await mem.recall(layer=MemoryLayer.WITNESS, limit=10)
    assert {e.content for e in entries} == {GOOD_TEXT, BAD_TEXT}


@pytest.mark.asyncio
async def test_recall_shadow_serves_legacy_and_stamps_receipt(
    mem, tmp_path, monkeypatch
):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_SHADOW)
    entries = await mem.recall(layer=MemoryLayer.WITNESS, limit=10)
    assert {e.content for e in entries} == {GOOD_TEXT, BAD_TEXT}
    lines = _receipt_lines(tmp_path)
    assert lines, "shadow mode must stamp a receipt line"
    last = lines[-1]
    assert last["site"] == "strange_loop.recall"
    assert last["served"] == 2
    assert last["would_be_excluded"] == 1
    # Discriminators separating pytest/tooling traffic from organism traffic.
    assert last["pid"] == os.getpid()
    assert last["state"] == str(tmp_path)


@pytest.mark.asyncio
async def test_recall_enforce_excludes_low_quality(mem, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    entries = await mem.recall(layer=MemoryLayer.WITNESS, limit=10)
    assert [e.content for e in entries] == [GOOD_TEXT]


@pytest.mark.asyncio
async def test_recall_enforce_include_quarantined_override(mem, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    entries = await mem.recall(
        layer=MemoryLayer.WITNESS, limit=10, include_quarantined=True
    )
    assert {e.content for e in entries} == {GOOD_TEXT, BAD_TEXT}


@pytest.mark.asyncio
async def test_recall_enforce_filters_immediate_layer(mem, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    await mem.remember(BAD_TEXT, layer=MemoryLayer.IMMEDIATE)
    await mem.remember(GOOD_TEXT, layer=MemoryLayer.IMMEDIATE)
    entries = await mem.recall(layer=MemoryLayer.IMMEDIATE, limit=10)
    assert [e.content for e in entries] == [GOOD_TEXT]


@pytest.mark.asyncio
async def test_recall_enforce_immediate_filters_before_limit(mem, monkeypatch):
    # Quarantined entries must not consume the limit window: an older good
    # entry still gets served when newer low-quality ones fill the slice.
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    await mem.remember(GOOD_TEXT, layer=MemoryLayer.IMMEDIATE)
    for _ in range(3):
        await mem.remember(BAD_TEXT, layer=MemoryLayer.IMMEDIATE)
    entries = await mem.recall(layer=MemoryLayer.IMMEDIATE, limit=2)
    assert [e.content for e in entries] == [GOOD_TEXT]


@pytest.mark.asyncio
async def test_get_context_enforce_excludes_low_quality(mem, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    context = await mem.get_context()
    assert GOOD_TEXT[:100] in context
    assert "profound amazing" not in context


@pytest.mark.asyncio
async def test_get_context_include_quarantined_override(mem, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    context = await mem.get_context(include_quarantined=True)
    assert "profound amazing" in context


# ── context.py raw SELECT sites ──────────────────────────────────────


@pytest.fixture
def state_dir(tmp_path):
    async def seed():
        m = StrangeLoopMemory(tmp_path / "db" / "memory.db")
        await m.init_db()
        await m.remember(GOOD_TEXT, layer=MemoryLayer.WITNESS)
        await m.remember(BAD_TEXT, layer=MemoryLayer.WITNESS)
        await m.close()

    asyncio.run(seed())
    return tmp_path


def test_read_memory_context_off_serves_low_quality(state_dir, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_OFF)
    out = read_memory_context(state_dir)
    assert "profound amazing" in out


def test_read_memory_context_shadow_serves_and_stamps(state_dir, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_SHADOW)
    out = read_memory_context(state_dir)
    assert "profound amazing" in out
    lines = [
        ln for ln in _receipt_lines(state_dir)
        if ln["site"] == "context.read_memory_context"
    ]
    assert lines
    assert lines[-1]["served"] == 2
    assert lines[-1]["would_be_excluded"] == 1


def test_read_memory_context_enforce_excludes(state_dir, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    out = read_memory_context(state_dir)
    assert "profound amazing" not in out
    assert "notice an actual gap" in out


def test_read_memory_context_include_quarantined(state_dir, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    out = read_memory_context(state_dir, include_quarantined=True)
    assert "profound amazing" in out


def test_read_recent_memories_enforce_excludes(state_dir, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    out = read_recent_memories(state_dir)
    assert "profound amazing" not in out
    assert "notice an actual gap" in out


def test_read_recent_memories_shadow_serves_and_stamps(state_dir, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_SHADOW)
    out = read_recent_memories(state_dir)
    assert "profound amazing" in out
    lines = [
        ln for ln in _receipt_lines(state_dir)
        if ln["site"] == "context.read_recent_memories"
    ]
    assert lines
    assert lines[-1]["would_be_excluded"] == 1


def test_read_recent_memories_include_quarantined(state_dir, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    out = read_recent_memories(state_dir, include_quarantined=True)
    assert "profound amazing" in out


def test_read_recent_memories_legacy_schema_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    conn = sqlite3.connect(str(db_dir / "memory.db"))
    conn.execute(
        "CREATE TABLE memories (id TEXT PRIMARY KEY, timestamp TEXT,"
        " layer TEXT, content TEXT)"
    )
    conn.execute(
        "INSERT INTO memories VALUES (?, ?, ?, ?)",
        ("m1", datetime.now(timezone.utc).isoformat(), "session", BAD_TEXT),
    )
    conn.commit()
    conn.close()
    # Pre-tags schema has nothing tagged: serve legacy instead of erroring.
    out = read_recent_memories(tmp_path)
    assert "profound amazing" in out
