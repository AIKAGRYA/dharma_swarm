"""Digest-dedupe guard + expiry maintenance for VectorStore (audit PR-11).

Connection-level helpers extracted from vector_store.py so the guard logic
and its index/FTS hygiene live in one place (and vector_store.py stays inside
the Rule-10 module line budget). Every function raises on failure —
``VectorStore.upsert_with_status`` converts errors into its fail-closed
``guard_error`` status instead of falling back to a blind INSERT.
"""

from __future__ import annotations

import json
import random
import sqlite3

DEDUPE_INDEX_NAME = "idx_vec_documents_source_active"


def ensure_dedupe_index(conn: sqlite3.Connection) -> None:
    """Partial index over active rows — required by the dedupe guard.

    Without it, :func:`active_row_for_digest` / :func:`expire_active_source_rows`
    are full-table scans (measured ~250s per query on the live 61GB
    vectors.db). The one-time build on a large existing DB takes minutes and
    holds the write lock; pre-build offline where that matters:
    sqlite3 vectors.db "CREATE INDEX IF NOT EXISTS
    idx_vec_documents_source_active ON vec_documents(source)
    WHERE valid_until IS NULL" — or call
    ``VectorStore.ensure_dedupe_index_built`` off the event loop.
    """
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (DEDUPE_INDEX_NAME,),
    ).fetchone()
    if row is None:
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {DEDUPE_INDEX_NAME} "
            "ON vec_documents(source) WHERE valid_until IS NULL"
        )
        conn.commit()


def active_row_for_digest(
    conn: sqlite3.Connection,
    source: str,
    digest: str,
) -> int | None:
    # No try/except: guard errors must surface so upsert_with_status can
    # fail closed instead of silently inserting.
    row = conn.execute(
        """
        SELECT id FROM vec_documents
        WHERE source = ?
          AND valid_until IS NULL
          AND json_valid(metadata_json)
          AND json_extract(metadata_json, '$.source_digest') = ?
        ORDER BY id DESC LIMIT 1
        """,
        (source, digest),
    ).fetchone()
    return int(row[0]) if row else None


def expire_active_source_rows(
    conn: sqlite3.Connection,
    source: str,
    replacement_digest: str,
    now_iso: str,
    *,
    has_vec0: bool,
) -> int:
    """Expire prior active rows for a source AND remove their index entries.

    search_vector/search_fts apply the ``valid_until`` filter only AFTER
    limiting KNN/FTS candidates, so expired rows left in vec_embeddings /
    vec_fts crowd active rows out of the candidate pool. The vec_documents
    row itself is kept (bi-temporal history via valid_until); only its
    retrieval-index entries are deleted. The vec_fts delete trigger fires on
    row DELETE, never on this soft-expiry UPDATE, hence the manual
    external-content delete below.

    No try/except: guard errors must surface so upsert_with_status can fail
    closed instead of inserting alongside still-active stale rows.
    """
    rows = conn.execute(
        "SELECT id, content, source FROM vec_documents"
        " WHERE source = ? AND valid_until IS NULL",
        (source,),
    ).fetchall()
    if not rows:
        return 0
    patch = json.dumps({
        "invalidated_at": now_iso,
        "invalidated_reason": "source_digest_replaced",
        "replacement_source_digest": replacement_digest,
    }, sort_keys=True)
    conn.execute(
        """
        UPDATE vec_documents
        SET valid_until = ?,
            metadata_json = json_patch(
                CASE WHEN json_valid(metadata_json) THEN metadata_json ELSE '{}' END,
                ?
            )
        WHERE source = ? AND valid_until IS NULL
        """,
        (now_iso, patch, source),
    )
    embedding_table = "vec_embeddings" if has_vec0 else "vec_embeddings_fallback"
    for doc_id, content, row_source in rows:
        conn.execute(
            f"DELETE FROM {embedding_table} WHERE rowid = ?", (int(doc_id),)
        )
        # FTS5 external-content delete requires the old column values.
        conn.execute(
            "INSERT INTO vec_fts(vec_fts, rowid, content, source)"
            " VALUES ('delete', ?, ?, ?)",
            (int(doc_id), content, row_source),
        )
    return len(rows)


def db_generation(conn: sqlite3.Connection) -> int:
    """Read (stamping once if unset) the database's generation nonce.

    ``PRAGMA user_version`` is unused elsewhere on vectors.db; a nonzero
    random stamp lets resume cursors detect a recreated/replaced database
    file and discard themselves instead of skipping documents whose rows no
    longer exist.
    """
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version == 0:
        version = random.getrandbits(31) | 1
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
    return version
