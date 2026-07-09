"""Term scoring, FTS query shaping, and generic retrieval utilities.

Split out of ``memory_retrieval.py`` (Rule 10 module-line-budget
decomposition). This module holds the leaf/generic scoring helpers with no
dependency on the sidecar/matching layer; ``sidecar_matching.py`` imports
from here, not the other way around. Both are private implementation
helpers of the governed retrieval door in ``memory_retrieval.py``, which
imports the names it needs back for internal use.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.vector_store import VectorStore, _fts_match_query

_SECRETISH_RE = re.compile(
    r"(?is)(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{8,}|\bBearer\s+[A-Za-z0-9._~+/=-]{16,})"
)
_FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9]+", re.UNICODE)
_FTS_STOPWORDS = {
    "and",
    "are",
    "did",
    "does",
    "entity",
    "file",
    "for",
    "from",
    "graph",
    "has",
    "into",
    "in",
    "memory",
    "not",
    "relation",
    "source",
    "stop",
    "what",
    "which",
    "why",
    "was",
    "were",
    "the",
    "this",
    "that",
    "with",
}
_SOURCE_IDENTITY_STOPWORDS = _FTS_STOPWORDS | {
    "concept",
    "concepts",
    "dharma",
    "dhyana",
    "docs",
    "file",
    "knowledge",
    "md",
    "reports",
    "script",
    "scripts",
    "source",
    "swarm",
    "text",
    "users",
    "wiki",
}


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 3)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _sqlite_sequence(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'vec_documents'"
        ).fetchone()
        if row is not None:
            return int(row[0] or 0)
    except Exception:
        return None
    return None


def _table_has_sample(conn: sqlite3.Connection, table: str) -> bool | None:
    try:
        return conn.execute(f"SELECT rowid FROM {table} LIMIT 1").fetchone() is not None
    except Exception:
        return None


def _row_similarity(row: dict[str, Any]) -> float:
    try:
        if "distance" in row:
            return max(0.0, min(1.0, 1.0 - float(row.get("distance", 1.0))))
        return max(0.0, min(1.0, float(row.get("score", 0.0))))
    except (TypeError, ValueError):
        return 0.0


def _sidecar_rows_to_results(
    vector_store: VectorStore,
    rows: list[tuple[sqlite3.Row, float]],
) -> list[dict[str, Any]]:
    return [
        vector_store._row_to_dict(
            row,
            distance=max(0.0, min(1.0, 1.0 - float(score))),
        )
        for row, score in rows
    ]


def _source_identity_terms(source: str) -> set[str]:
    terms: set[str] = set()
    for term in re.findall(r"[A-Za-z0-9]+", source.lower(), flags=re.UNICODE):
        if len(term) <= 1:
            continue
        normalized = _normalized_scoring_term(term)
        if normalized in _SOURCE_IDENTITY_STOPWORDS:
            continue
        terms.add(normalized)
    return terms


def _identity_text(row: dict[str, Any]) -> str:
    source = str(row.get("source", ""))
    titles = _title_text(row)
    return f"{source} {titles}"


def _title_text(row: dict[str, Any]) -> str:
    content = str(row.get("content", ""))
    markdown_title = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
    if markdown_title:
        return markdown_title.group(1)
    frontmatter_title = re.search(r'^title:\s*"?([^"\n]+)"?', content, flags=re.MULTILINE)
    if frontmatter_title:
        return frontmatter_title.group(1)
    title_patterns = (
        r"Observation:\s*(.+?)(?:\nSource file:|\n|$)",
        r"Memory graph entity:\s*(.+?)(?:\n|$)",
        r"Memory graph relation:\s*(.+?)(?:\n|$)",
        r'"goal"\s*:\s*"([^"]+)"',
    )
    titles: list[str] = []
    for pattern in title_patterns:
        match = re.search(pattern, content, flags=re.MULTILINE | re.DOTALL)
        if match:
            titles.append(match.group(1))
    return " ".join(titles)


def _token_overlap_score(query_text: str, candidate_text: str) -> float:
    query_terms = _scoring_terms(query_text)
    candidate_terms = _scoring_terms(candidate_text)
    return _token_overlap_from_terms(query_terms, candidate_terms)


def _token_overlap_from_terms(query_terms: set[str], candidate_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    if not candidate_terms:
        return 0.0
    return len(query_terms & candidate_terms) / len(query_terms)


def _query_term_doc_freq(
    query_terms: set[str],
    slots: Any,
) -> dict[str, int]:
    counts = {term: 0 for term in query_terms}
    for slot in slots:
        candidate_terms = slot.get("candidate_terms", set())
        for term in query_terms & candidate_terms:
            counts[term] += 1
    return counts


def _term_stat_slots(slots: Any) -> list[dict[str, Any]]:
    all_slots = list(slots)
    fts_slots = [slot for slot in all_slots if "fts" in slot.get("channels", ())]
    return fts_slots or all_slots


def _rare_query_terms(term_doc_freq: dict[str, int]) -> set[str]:
    return {term for term, doc_freq in term_doc_freq.items() if doc_freq == 1}


def _weighted_token_overlap_from_terms(
    query_terms: set[str],
    candidate_terms: set[str],
    term_doc_freq: dict[str, int],
    candidate_count: int,
) -> float:
    if not query_terms or not candidate_terms:
        return 0.0
    denominator = 0.0
    numerator = 0.0
    for term in query_terms:
        doc_freq = max(1, int(term_doc_freq.get(term, 0)))
        weight = 1.0 / math.sqrt(doc_freq)
        denominator += weight
        if term in candidate_terms:
            numerator += weight
    if denominator <= 0.0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _scoring_terms(text: str) -> set[str]:
    return set(_ordered_scoring_terms(text))


def _ordered_scoring_terms(text: str) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for term in re.findall(r"[A-Za-z0-9]+", text.lower(), flags=re.UNICODE):
        if len(term) <= 1 or term in _FTS_STOPWORDS:
            continue
        normalized = _normalized_scoring_term(term)
        if normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
    return terms


def _explicit_anchor_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for term in re.findall(r"[A-Za-z0-9]+", text, flags=re.UNICODE):
        if len(term) < 3 or not any(char.isalpha() for char in term):
            continue
        if term.upper() == term:
            normalized = _normalized_scoring_term(term.lower())
            if normalized not in _FTS_STOPWORDS:
                terms.add(normalized)
    return terms


def _tail_intent_terms(text: str) -> set[str]:
    terms = _ordered_scoring_terms(text)
    if len(terms) <= 3:
        return set(terms)
    return set(terms[-3:])


def _normalized_scoring_term(term: str) -> str:
    if term.endswith("ing") and len(term) > 5:
        return term[:-3]
    if term.endswith("ed") and len(term) > 4:
        return term[:-2]
    if term.endswith("es") and len(term) > 4:
        return term[:-2]
    if term.endswith("s") and len(term) > 4:
        return term[:-1]
    return term


def _bounded_fts_match_queries(query_text: str) -> tuple[str, ...]:
    terms = [term for term in _FTS_TOKEN_RE.findall(query_text) if len(term) > 1]
    if not terms:
        return ()

    queries: list[str] = []
    important = [
        term
        for term in terms
        if len(term) > 2 and term.lower() not in _FTS_STOPWORDS
    ]
    for width in (3, 4):
        if len(important) >= width:
            queries.append(_fts_and_query(important[:width]))

    if len(terms) > 1:
        queries.append(_fts_and_query(terms))

    if 1 < len(important) < len(terms):
        queries.append(_fts_and_query(important))
    return tuple(dict.fromkeys(query for query in queries if query))


def _sidecar_fts_match_queries(query_text: str) -> tuple[str, ...]:
    terms = [term for term in _FTS_TOKEN_RE.findall(query_text) if len(term) > 1]
    if not terms:
        return ()
    important = [
        term
        for term in terms
        if len(term) > 2 and term.lower() not in _FTS_STOPWORDS
    ]
    normalized = _normalized_fts_terms(important)
    queries: list[str] = []
    if len(terms) > 1:
        queries.append(_fts_and_query(terms))
    if len(important) > 1:
        queries.append(_fts_and_query(important))
    for width in (4, 3):
        if len(important) >= width:
            window = important[:width]
            queries.append(_fts_and_query(window))
            queries.append(_fts_prefix_and_query(window))
        if len(normalized) >= width:
            window = normalized[:width]
            queries.append(_fts_and_query(window))
            queries.append(_fts_prefix_and_query(window))
    for width in (4, 3, 2):
        if len(important) < width:
            continue
        for index in range(0, len(important) - width + 1):
            window = important[index : index + width]
            queries.append(_fts_and_query(window))
            queries.append(_fts_prefix_and_query(window))
        if len(normalized) >= width:
            for index in range(0, len(normalized) - width + 1):
                window = normalized[index : index + width]
                queries.append(_fts_and_query(window))
                queries.append(_fts_prefix_and_query(window))
    queries.append(_fts_match_query(query_text))
    return tuple(dict.fromkeys(query for query in queries if query))


def _normalized_fts_terms(terms: list[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        lowered = term.lower()
        candidate = term
        if lowered.endswith("ing") and len(term) > 5:
            candidate = term[:-3]
        elif lowered.endswith("ed") and len(term) > 4:
            candidate = term[:-2]
        elif lowered.endswith("es") and len(term) > 4:
            candidate = term[:-2]
        elif lowered.endswith("s") and len(term) > 4:
            candidate = term[:-1]
        out.append(candidate)
    return out


def _fts_and_query(terms: list[str]) -> str:
    return " AND ".join(f'"{term}"' for term in terms)


def _fts_prefix_and_query(terms: list[str]) -> str:
    parts = []
    for term in terms:
        if len(term) >= 4:
            parts.append(f"{term}*")
        else:
            parts.append(f'"{term}"')
    return " AND ".join(parts)


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _ensure_retrieval_telemetry_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_retrieval_query_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_time TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            query_preview TEXT NOT NULL,
            top_doc_id TEXT DEFAULT '',
            top_source TEXT DEFAULT '',
            top_layer TEXT DEFAULT '',
            top_score REAL,
            result_count INTEGER NOT NULL,
            total_ms REAL,
            vector_search_ms REAL,
            fts_search_ms REAL,
            fusion_ms REAL,
            memory_kernel_available INTEGER NOT NULL DEFAULT 0,
            memory_kernel_text_query_supported INTEGER NOT NULL DEFAULT 0,
            memory_kernel_admitted_count INTEGER NOT NULL DEFAULT 0,
            degraded_reasons_json TEXT NOT NULL DEFAULT '[]',
            top_channels_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS memory_retrieval_query_log_time_idx
        ON memory_retrieval_query_log(query_time)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS memory_retrieval_query_log_hash_idx
        ON memory_retrieval_query_log(query_hash)
        """
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _query_preview(text: str, *, max_chars: int = 240) -> str:
    preview = _SECRETISH_RE.sub("[redacted]", text)
    preview = " ".join(preview.split())
    if len(preview) <= max_chars:
        return preview
    return preview[: max(0, max_chars - 3)].rstrip() + "..."


def _is_noisy_vector_only_candidate(
    row: dict[str, Any],
    *,
    query_text: str,
    token_overlap: float,
    exact_match: bool,
) -> bool:
    """Reject common live-store vector noise when lexical evidence is absent."""

    if exact_match:
        return False
    source = str(row.get("source", ""))
    layer = str(row.get("layer", ""))
    if not (source.startswith("evolution_archive:") or layer == "development"):
        return False
    if _identifier_like_query(query_text):
        return True
    return token_overlap < 0.5


def _identifier_like_query(query_text: str) -> bool:
    stripped = query_text.strip()
    if re.search(r"[A-Za-z]+-\d{4}-\d{2}-[A-Za-z0-9-]+", stripped):
        return True
    if re.search(r"\b[A-Za-z0-9]+-[A-Za-z0-9-]+-[A-Za-z0-9-]+\b", stripped):
        return True
    return False


def _content_for_candidate(content: str, include_content: bool) -> tuple[str, tuple[str, ...]]:
    if not include_content:
        return "", ()
    if _SECRETISH_RE.search(content):
        return "[redacted: secret-like content omitted]", ("secret_like_content_redacted",)
    return content[:2000], ()
