"""Palantir Pilot — source-index loading, memory-plane indexing, and query functions.

This module owns `latest_source_index_path`, `memory_plane_db_path`,
`index_workspace_to_memory_plane`, `query_source_index`, and `query_wiki_notes`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.palantir_pilot_manifest import (
    AGENT_ID,
    CALLSIGN,
    DATABASE_SOURCE_KINDS,
    DEFAULT_DHARMA_HOME,
    MEMORY_PLANE_DB,
    RAW_SOURCE_DIR,
    WIKI_HOME,
    WIKI_SOURCE_DIR,
    _utc_now,
)

def latest_source_index_path(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> Path | None:
    """Return the newest Palantir Pilot source-index JSON path, if present."""

    raw_dir = Path(dharma_home).expanduser() / RAW_SOURCE_DIR
    if not raw_dir.exists():
        return None
    paths = sorted(raw_dir.glob("source-index-*.json"))
    return paths[-1] if paths else None


def memory_plane_db_path(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> Path:
    """Return the local Dharma memory-plane DB path for Palantir Pilot receipts."""

    return Path(dharma_home).expanduser() / MEMORY_PLANE_DB


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    current: list[str] = []
    for char in query.lower():
        if char.isalnum():
            current.append(char)
        elif current:
            term = "".join(current)
            if len(term) > 1:
                terms.append(term)
            current = []
    if current:
        term = "".join(current)
        if len(term) > 1:
            terms.append(term)
    return terms


def _score_text(text: str, terms: list[str]) -> int:
    haystack = text.lower()
    return sum(haystack.count(term) for term in terms)


def _score_wiki_note(path: Path, text: str, terms: list[str]) -> int:
    path_text = " ".join([path.name, path.stem, " ".join(path.parts[-5:])])
    score = _score_text(text, terms) + (_score_text(path_text, terms) * 8)
    term_set = set(terms)
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    product_map_query = bool({"product", "family", "families", "compare", "map", "maps"} & term_set)
    named_family_terms = {"foundry", "aip", "ontology", "osdk", "api", "apollo", "gotham", "defense", "learn"}
    broad_product_map_query = product_map_query and len(term_set & named_family_terms) >= 3
    if name.startswith("titanium-"):
        titanium_terms = {
            "bench",
            "blocked",
            "boundary",
            "claim",
            "claims",
            "compare",
            "corpus",
            "debt",
            "dharma",
            "evaluation",
            "expert",
            "exhausted",
            "family",
            "first",
            "gap",
            "gaps",
            "hard",
            "map",
            "maps",
            "mastery",
            "model",
            "operating",
            "principles",
            "product",
            "qa",
            "ratchet",
            "synthesis",
            "swarm",
            "titanium",
            "transfer",
            "unjustified",
            "weak",
        }
        overlap = term_set & titanium_terms
        if overlap:
            score += 900 + (120 * len(overlap))
        if {"first", "principles", "model", "operating"} & term_set and "first-principles" in name:
            score += 1200
        if {"product", "family", "families", "compare", "map", "maps"} & term_set and "product-family" in name:
            score += 1200
            if broad_product_map_query:
                score += 4200
        if {"dharma", "swarm", "transfer", "patterns"} & term_set and "dharma-swarm-application" in name:
            score += 1200
        if {"gap", "gaps", "blocked", "weak", "unjustified", "claims"} & term_set and "gap-ledger" in name:
            score += 1200
        if {"qa", "question", "questions", "expert", "bench", "hard"} & term_set and "expert-qa" in name:
            score += 1200
        if {"corpus", "coverage", "indexed"} & term_set and "corpus-map" in name:
            score += 1200
        if {"next", "synthesis", "debt", "exhausted", "canonical"} & term_set and "synthesis-debt" in name:
            score += 3600
    if {"contribution", "packet"} & term_set and "contributions" in parts:
        score += 2400
    if {"dharma", "swarm", "aip", "governance", "observability", "model"} & term_set and "contributions" in parts:
        score += 1600
    if {"evaluation", "eval"} & term_set and "evals" in parts:
        score += 60
    if "playbook" in term_set and "playbooks" in parts:
        score += 40
    if {"learn", "course", "catalog"} & term_set and path.name == "learn-course-catalog-intake.md":
        score += 1200 if broad_product_map_query else 5200
    if "checkpoint" in term_set:
        if path.name.startswith("checkpoint-"):
            path_lower = path.name.lower()
            score += 6000
            score += sum(2000 for term in term_set if term in path_lower)
        elif path.name in {"source-card-index.md", "query-cookbook.md", "query-smoke-latest.md"}:
            score = max(1, score // 4)
    elif path.name in {"source-card-index.md", "curriculum-index.md", "orientation-index.md", "query-cookbook.md", "query-smoke-latest.md"}:
        score = max(1, score // 12)
    return score


def _load_latest_source_index(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> tuple[Path | None, dict[str, Any]]:
    path = latest_source_index_path(dharma_home)
    if path is None:
        return None, {}
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path, {}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _query_observed_at(packet: dict[str, Any]) -> datetime:
    raw = str(packet.get("observed_at") or "")
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _wiki_markdown_paths(dharma_home: Path | str = DEFAULT_DHARMA_HOME) -> list[Path]:
    home = Path(dharma_home).expanduser()
    paths: list[Path] = []
    wiki_home = home / WIKI_HOME
    if wiki_home.exists():
        paths.append(wiki_home)
    source_dir = home / WIKI_SOURCE_DIR
    if source_dir.exists():
        paths.extend(
            sorted(
                path
                for path in source_dir.rglob("*.md")
                if path.is_file() and "source-cards-archive" not in path.parts
            )
        )
    deduped: dict[str, Path] = {str(path): path for path in paths}
    return [deduped[key] for key in sorted(deduped)]


def _prune_stale_palantir_wiki_documents(db_path: Path, active_paths: set[str]) -> int:
    from dharma_swarm.engine.event_memory import ensure_memory_plane_schema_sync

    with sqlite3.connect(str(db_path)) as db:
        ensure_memory_plane_schema_sync(db)
        rows = db.execute(
            "SELECT doc_id, source_path FROM source_documents WHERE source_kind = ?",
            ("palantir_pilot_wiki",),
        ).fetchall()
        stale_doc_ids = [
            str(doc_id)
            for doc_id, source_path in rows
            if str(source_path) not in active_paths
            or "source-cards-archive" in Path(str(source_path)).parts
        ]
        for doc_id in stale_doc_ids:
            db.execute("DELETE FROM source_chunks WHERE doc_id = ?", (doc_id,))
            db.execute("DELETE FROM source_documents WHERE doc_id = ?", (doc_id,))
        db.commit()
    return len(stale_doc_ids)


def _catalog_documents_from_source_index(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    batch_size: int = 75,
) -> list[tuple[str, str, str, dict[str, Any]]]:
    index_path, payload = _load_latest_source_index(dharma_home)
    rows_raw = payload.get("urls")
    rows = [row for row in rows_raw if isinstance(row, dict)] if isinstance(rows_raw, list) else []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family = str(row.get("family") or "unknown")
        grouped.setdefault(family, []).append(row)

    documents: list[tuple[str, str, str, dict[str, Any]]] = []
    for family in sorted(grouped):
        family_rows = sorted(grouped[family], key=lambda row: str(row.get("loc") or ""))
        lines = [
            f"# Palantir Pilot Source Catalog - {family}",
            "",
            f"Source index: `{index_path or ''}`",
            f"URL count: {len(family_rows)}",
            "",
            "Boundary: public sitemap metadata only. This catalog stores URLs and metadata, not Palantir page bodies or course material.",
            "",
        ]
        size = max(1, batch_size)
        for batch_number, start in enumerate(range(0, len(family_rows), size), start=1):
            end = min(start + size, len(family_rows))
            lines.extend([f"## URLs {start + 1}-{end}", ""])
            for row in family_rows[start:end]:
                lines.append(
                    "- {url} | lastmod={lastmod} | changefreq={changefreq} | sitemap={sitemap}".format(
                        url=str(row.get("loc") or ""),
                        lastmod=str(row.get("lastmod") or ""),
                        changefreq=str(row.get("changefreq") or ""),
                        sitemap=str(row.get("sitemap") or ""),
                    )
                )
            lines.append("")
        metadata = {
            "agent_id": AGENT_ID,
            "callsign": CALLSIGN,
            "family": family,
            "source_index": str(index_path) if index_path else "",
            "url_count": len(family_rows),
            "boundary": "public sitemap metadata only",
        }
        documents.append(
            (
                family,
                f"palantir-pilot/source-catalog/{family}.md",
                "\n".join(lines),
                metadata,
            )
        )
    return documents


def index_workspace_to_memory_plane(
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    db_path: Path | str | None = None,
    source_url_batch_size: int = 75,
) -> dict[str, Any]:
    """Index Palantir Pilot wiki notes and source URL catalogs into Memory Palace.

    The indexed source catalog contains sitemap URL metadata only. It never
    stores Palantir page bodies, Learn course content, videos, labs, or private
    tenant material.
    """

    from dharma_swarm.engine.unified_index import UnifiedIndex

    home = Path(dharma_home).expanduser()
    db = Path(db_path).expanduser() if db_path else memory_plane_db_path(home)
    index = UnifiedIndex(db)

    wiki_paths = _wiki_markdown_paths(home)
    pruned_wiki_documents = _prune_stale_palantir_wiki_documents(
        db,
        {str(path) for path in wiki_paths},
    )
    wiki_documents = 0
    for path in wiki_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        index.index_document(
            "palantir_pilot_wiki",
            str(path),
            text,
            {
                "agent_id": AGENT_ID,
                "callsign": CALLSIGN,
                "source_role": "palantir_pilot_wiki_note",
                "boundary": "original notes and source-grounded summaries only",
            },
        )
        wiki_documents += 1

    source_catalog_documents = 0
    source_urls = 0
    for _family, source_path, text, metadata in _catalog_documents_from_source_index(
        dharma_home=home,
        batch_size=source_url_batch_size,
    ):
        index.index_document(
            "palantir_pilot_source_catalog",
            source_path,
            text,
            metadata,
        )
        source_catalog_documents += 1
        source_urls += int(metadata.get("url_count") or 0)

    return {
        "schema_version": "palantir_pilot.memory_plane_index_receipt.v1",
        "agent": {"id": AGENT_ID, "callsign": CALLSIGN},
        "observed_at": _utc_now(),
        "db_path": str(db),
        "wiki_documents_indexed": wiki_documents,
        "source_catalog_documents_indexed": source_catalog_documents,
        "source_urls_indexed": source_urls,
        "pruned_wiki_documents": pruned_wiki_documents,
        "source_kinds": list(DATABASE_SOURCE_KINDS),
        "storage_boundary": "URLs, metadata, original wiki notes, summaries, and deep-card prose from robots-allowed public www.palantir.com pages; no Learn/course bodies and no private-tenant material",
        "index_stats": index.stats(),
    }


def query_source_index(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 10,
    family: str | None = None,
) -> list[dict[str, Any]]:
    """Search the URL/metadata-only source index.

    The result intentionally contains source metadata only. It never reads or
    returns Palantir page bodies.
    """

    terms = _query_terms(query)
    if not terms:
        return []
    _path, payload = _load_latest_source_index(dharma_home)
    rows = payload.get("urls")
    if not isinstance(rows, list):
        return []

    hits: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_family = str(row.get("family") or "")
        if family and row_family != family:
            continue
        searchable = " ".join(
            str(row.get(key) or "")
            for key in ("loc", "family", "sitemap", "lastmod", "changefreq")
        )
        score = _score_text(searchable, terms)
        if score <= 0:
            continue
        hits.append(
            {
                "score": score,
                "url": str(row.get("loc") or ""),
                "family": row_family,
                "lastmod": str(row.get("lastmod") or ""),
                "sitemap": str(row.get("sitemap") or ""),
            }
        )

    hits.sort(key=lambda item: (-int(item["score"]), item["family"], item["url"]))
    return hits[: max(0, limit)]


def _snippet(text: str, terms: list[str], *, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    lower = collapsed.lower()
    start = 0
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if positions:
        start = max(0, min(positions) - 80)
    end = min(len(collapsed), start + max_chars)
    prefix = "..." if start else ""
    suffix = "..." if end < len(collapsed) else ""
    return f"{prefix}{collapsed[start:end]}{suffix}"


def query_wiki_notes(
    query: str,
    *,
    dharma_home: Path | str = DEFAULT_DHARMA_HOME,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search Palantir Pilot markdown notes and return short snippets."""

    terms = _query_terms(query)
    if not terms:
        return []
    candidates = _wiki_markdown_paths(dharma_home)

    hits: list[dict[str, Any]] = []
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        score = _score_wiki_note(path, text, terms)
        if score <= 0:
            continue
        hits.append(
            {
                "score": score,
                "path": str(path),
                "snippet": _snippet(text, terms),
            }
        )
    hits.sort(key=lambda item: (-int(item["score"]), item["path"]))
    return hits[: max(0, limit)]


