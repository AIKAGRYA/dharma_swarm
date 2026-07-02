from __future__ import annotations

import struct
from pathlib import Path

from dharma_swarm.vector_store import VectorStore
from scripts.vector_store_backfill_vec0 import backfill_vec0


def test_backfill_vec0_from_fallback_embeddings(tmp_path, monkeypatch):
    store = VectorStore(state_dir=tmp_path, dim=32)
    _ensure_fallback_table(store)
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)
    doc_id = store.upsert("Backfill canary memory kernel retrieval", source="test")
    assert doc_id > 0

    conn = store._connect()
    try:
        assert conn.execute("SELECT rowid FROM vec_embeddings_fallback LIMIT 1").fetchone()
        assert conn.execute("SELECT rowid FROM vec_embeddings LIMIT 1").fetchone() is None
    finally:
        conn.close()

    receipt = backfill_vec0(
        state_dir=tmp_path,
        batch_size=10,
        max_rows=10,
        start_rowid=0,
        cursor_path=tmp_path / "cursor.json",
        reset_cursor=True,
        dry_run=False,
    )

    assert receipt.selected_rows == 1
    assert receipt.inserted_rows == 1
    assert receipt.vec0_has_rows is True
    assert receipt.fallback_has_rows is True

    repaired = VectorStore(state_dir=tmp_path, dim=32)
    results = repaired.search_vector("memory kernel retrieval", top_k=3)
    assert any(row["id"] == doc_id for row in results)


def test_backfill_vec0_dry_run_does_not_insert(tmp_path, monkeypatch):
    store = VectorStore(state_dir=tmp_path, dim=32)
    _ensure_fallback_table(store)
    monkeypatch.setattr(store, "_has_vec0", lambda conn: False)
    store.upsert("Dry run fallback vector", source="test")

    receipt = backfill_vec0(
        state_dir=tmp_path,
        batch_size=10,
        max_rows=10,
        start_rowid=0,
        cursor_path=tmp_path / "cursor.json",
        reset_cursor=True,
        dry_run=True,
    )

    assert receipt.selected_rows == 1
    assert receipt.inserted_rows == 0
    conn = store._connect()
    try:
        assert conn.execute("SELECT rowid FROM vec_embeddings LIMIT 1").fetchone() is None
    finally:
        conn.close()


def test_backfill_repairs_empty_vec0_dimension(tmp_path):
    store = VectorStore(state_dir=tmp_path, dim=16)
    _ensure_fallback_table(store)
    conn = store._connect()
    try:
        blob = struct.pack("32f", *([0.1] * 32))
        conn.execute(
            """
            INSERT INTO vec_documents(content, source, ingestion_time)
            VALUES ('dimension repair canary', 'test', '2026-01-01T00:00:00+00:00')
            """
        )
        conn.execute(
            "INSERT INTO vec_embeddings_fallback(rowid, embedding) VALUES (?, ?)",
            (1, blob),
        )
        conn.commit()
    finally:
        conn.close()

    receipt = backfill_vec0(
        state_dir=tmp_path,
        batch_size=10,
        max_rows=10,
        start_rowid=0,
        cursor_path=tmp_path / "cursor.json",
        reset_cursor=True,
        dry_run=False,
        repair_empty_vec0_dim=True,
    )

    assert "repaired_empty_vec0_dimension:32" in receipt.warnings
    assert receipt.inserted_rows == 1
    assert receipt.vec0_has_rows is True


def _ensure_fallback_table(store: VectorStore) -> None:
    conn = store._connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vec_embeddings_fallback (
                rowid INTEGER PRIMARY KEY,
                embedding BLOB
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
