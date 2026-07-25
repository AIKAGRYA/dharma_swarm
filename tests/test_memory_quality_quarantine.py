"""Tests for the quality-quarantine gate (DHARMA_MEMORY_QUALITY_QUARANTINE)."""

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from dharma_swarm.context import read_memory_context, read_recent_memories
from dharma_swarm.engine.conversation_memory import ConversationMemoryStore
from dharma_swarm.engine.event_memory import ensure_memory_plane_schema_sync
from dharma_swarm.memory import StrangeLoopMemory
from dharma_swarm.memory_quarantine import (
    MODE_ENFORCE,
    MODE_OFF,
    MODE_SHADOW,
    QUARANTINE_ENV,
    RECEIPT_RELPATH,
    is_quarantined,
    is_shard_quarantined,
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


def test_is_shard_quarantined():
    assert is_shard_quarantined(BAD_TEXT) is True
    assert is_shard_quarantined(GOOD_TEXT) is False


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


# ── latent_gold ──────────────────────────────────────────────────────


def _seed_shards(store: ConversationMemoryStore) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(str(store.db_path)) as db:
        ensure_memory_plane_schema_sync(db)
        for text in (GOOD_TEXT, BAD_TEXT):
            db.execute(
                "INSERT INTO idea_shards"
                " (shard_id, turn_id, session_id, task_id, shard_kind, state,"
                "  text, salience, novelty, flow_score, source_span,"
                "  metadata_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"shard_{uuid4().hex}", f"turn_{uuid4().hex}", "sess", "task",
                    "insight", "orphaned", text, 0.9, 0.5, 0.5, "", "{}", now,
                ),
            )
        db.commit()


@pytest.fixture
def shard_store(tmp_path):
    store = ConversationMemoryStore(tmp_path / "db" / "memory_plane.db")
    _seed_shards(store)
    return store


def test_latent_gold_off_serves_all(shard_store, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_OFF)
    shards = shard_store.latent_gold("", limit=10)
    assert {s.text for s in shards} == {GOOD_TEXT, BAD_TEXT}


def test_latent_gold_shadow_serves_and_stamps(shard_store, tmp_path, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_SHADOW)
    shards = shard_store.latent_gold("", limit=10)
    assert {s.text for s in shards} == {GOOD_TEXT, BAD_TEXT}
    lines = [
        ln for ln in _receipt_lines(tmp_path)
        if ln["site"] == "conversation_memory.latent_gold"
    ]
    assert lines
    assert lines[-1]["served"] == 2
    assert lines[-1]["would_be_excluded"] == 1


def test_latent_gold_enforce_excludes(shard_store, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    shards = shard_store.latent_gold("", limit=10)
    assert [s.text for s in shards] == [GOOD_TEXT]


def test_latent_gold_include_quarantined_override(shard_store, monkeypatch):
    monkeypatch.setenv(QUARANTINE_ENV, MODE_ENFORCE)
    shards = shard_store.latent_gold("", limit=10, include_quarantined=True)
    assert {s.text for s in shards} == {GOOD_TEXT, BAD_TEXT}
